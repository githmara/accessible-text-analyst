"""naprawa_zrodel.py — naprawy warstwy tekstu źródeł: PDF (font) i DOCX (przeniesienia).

Część PDF: bramka jakości warstwy tekstu i naprawa z wbudowanego fontu.

Objaw (zmierzony 2026-10-20 na słowniku z macOS Quartz scalonym przez
ilovepdf): font Type0/Identity-H ma UCIĘTĄ mapę ToUnicode (ostatni bfrange
`<023a><0246>` → А…М), więc pdfplumber dla reszty liter oddaje znaczniki
„(cid:602)(cid:619)…”. Bez bramki trafiały do korpusu, a Lingua zgadywała
z nich język (`de`).

Dwie warstwy, w tej kolejności:

1. NAPRAWA (`napraw_strone`) — dla fontu CID kod znaku z „(cid:N)” to CID,
   a CID → numer glifu daje `CIDToGIDMap` (brak/„Identity” = ten sam numer).
   Znak glifu czytamy z programu fontu osadzonego w PDF (`mapa_glifow`:
   odwrócony najlepszy `cmap`, uzupełniony nazwami `post` przez fontTools.agl).
   Bez stałych przesunięć i bez list języków — wszystko z fontu.
2. BRAMKA (`czy_znieksztalcona`) — strona jest zniekształcona, gdy znaczników
   CID jest co najmniej `PROG_PODEJRZANYCH` i co najmniej `UDZIAL_PODEJRZANYCH`
   jej liter. Strona liczy się jako NAPRAWIONA tylko wtedy, gdy rozwiązały się
   WSZYSTKIE jej znaczniki; inaczej zostaje zgłoszona (bramka = siatka
   bezpieczeństwa za naprawą).

Progi 1:1 z bliźniakiem w Reżyserze (`core_pdf.PROG_PODEJRZANYCH` /
`UDZIAL_PODEJRZANYCH`, klasa `formaty_zrodel`); `mapa_glifow` ma tę samą
semantykę co `core_pdf.mapa_glifow`. Sygnał jest inny: tam flaga PDFium
`HasUnicodeMapError` + litery spoza paczek, tu znacznik pdfplumbera „(cid:N)”,
który sam jest bezpośrednim sygnałem braku mapowania.

Część tekstowa (`oczysc_akapity`: U+F020, rozstrzelenia, przeniesienia) —
WSPÓLNA specyfikacja z Reżyserem, patrz komentarz nad `_SLOWO`.

Moduł niczego nie drukuje — komunikaty należą do notatnika (`load_pdf`,
`load_docx`).
"""
from __future__ import annotations

import io
import re
import unicodedata
from collections import Counter
from typing import NamedTuple

PROG_PODEJRZANYCH = 3
UDZIAL_PODEJRZANYCH = 0.02

ZNACZNIK_CID = re.compile(r"\(cid:(\d+)\)")
_CALY_ZNACZNIK = re.compile(r"^\(cid:(\d+)\)$")


class OcenaStrony(NamedTuple):
    """Wynik `napraw_strone` dla jednej strony."""
    litery: int          # litery strony + znaczniki CID (po jednym na znak)
    znaczniki: int       # znaczniki „(cid:N)” PRZED naprawą
    nierozwiazane: int   # znaczniki, których font nie rozwiązał

    @property
    def znieksztalcona(self) -> bool:
        """Strona przed naprawą przekracza próg bramki."""
        return czy_znieksztalcona(self.litery, self.znaczniki)

    @property
    def naprawiona(self) -> bool:
        """Zniekształcona, ale font rozwiązał każdy znacznik."""
        return self.znieksztalcona and self.nierozwiazane == 0

    @property
    def do_zgloszenia(self) -> bool:
        """Zniekształcona i nie w pełni naprawiona — tekstu nie wolno użyć."""
        return self.znieksztalcona and self.nierozwiazane > 0


def czy_znieksztalcona(litery: int, podejrzane: int) -> bool:
    """Próg bramki: ≥ `PROG_PODEJRZANYCH` i ≥ `UDZIAL_PODEJRZANYCH` liter."""
    return podejrzane >= PROG_PODEJRZANYCH and podejrzane >= UDZIAL_PODEJRZANYCH * max(litery, 1)


def mapa_glifow(dane: bytes) -> dict[int, str]:
    """Numer glifu → znak(i) wg programu fontu; `{}`, gdy fontu nie da się czytać.

    Odwrócony `cmap` ma pierwszeństwo (przy kilku punktach kodowych na glif
    bierzemy najniższy — spacja przed NBSP), nazwy `post` uzupełniają glify,
    których `cmap` nie zna (zmierzone: BoldItalic słownika, 40/51 z `cmap`).
    Semantyka 1:1 z `core_pdf.mapa_glifow` w Reżyserze.
    """
    if not dane:
        return {}
    try:
        from fontTools import agl
        from fontTools.ttLib import TTFont
        font = TTFont(io.BytesIO(dane), lazy=True)
        kolejnosc = font.getGlyphOrder()
        numery = {nazwa: nr for nr, nazwa in enumerate(kolejnosc)}
        mapa: dict[int, str] = {}
        for kod, nazwa in sorted((font.getBestCmap() or {}).items()):
            if nazwa in numery:
                mapa.setdefault(numery[nazwa], chr(kod))
        for nr, nazwa in enumerate(kolejnosc):
            if nr not in mapa:
                znak = agl.toUnicode(nazwa)
                if znak and not znak.isspace():
                    mapa[nr] = znak
        return mapa
    except Exception:  # noqa: BLE001 — font nieczytelny = brak naprawy, bramka zostaje
        return {}


def _r(obiekt):
    from pdfminer.pdftypes import resolve1
    return resolve1(obiekt)


def _nazwa(obiekt) -> str:
    """Nazwa PDF (`/ABCDEF+Times`) albo bajty → tekst, jak `fontname` pdfplumbera."""
    obiekt = _r(obiekt)
    nazwa = getattr(obiekt, "name", obiekt)
    if isinstance(nazwa, bytes):
        nazwa = nazwa.decode("latin-1", "replace")
    return str(nazwa or "")


def _dane_strumienia(obiekt) -> bytes:
    try:
        return _r(obiekt).get_data()
    except Exception:  # noqa: BLE001
        return b""


def mapa_cid_fontu(font_dict) -> dict[int, str]:
    """CID → znak(i) dla fontu Type0 (słownik `/Font` z PDF); `{}` dla innych.

    Fonty proste (Type1/TrueType bez `DescendantFonts`) nie są naprawiane: kod
    znaku → glif zależy tam od `Encoding` i podtabeli `cmap`, a ich znaczniki
    zostają dla bramki.
    """
    font_dict = _r(font_dict) or {}
    potomne = _r(font_dict.get("DescendantFonts")) or []
    if not potomne:
        return {}
    cid_font = _r(potomne[0]) or {}
    opis = _r(cid_font.get("FontDescriptor")) or {}
    dane = b""
    for klucz in ("FontFile2", "FontFile3", "FontFile"):
        if klucz in opis:
            dane = _dane_strumienia(opis[klucz])
            break
    glify = mapa_glifow(dane)
    if not glify:
        return {}
    mapa_gid = _r(cid_font.get("CIDToGIDMap"))
    if mapa_gid is None or _nazwa(mapa_gid) == "Identity" or not hasattr(mapa_gid, "get_data"):
        return glify
    surowe = _dane_strumienia(mapa_gid)
    wynik = {}
    for cid in range(len(surowe) // 2):
        gid = int.from_bytes(surowe[2 * cid:2 * cid + 2], "big")
        if gid and gid in glify:
            wynik[cid] = glify[gid]
    return wynik


def _fonty_zasobow(zasoby, wynik: dict, odwiedzone: set) -> None:
    """Zbiera {BaseFont: słownik fontu} z zasobów strony i jej Form XObjectów."""
    zasoby = _r(zasoby) or {}
    if id(zasoby) in odwiedzone:
        return
    odwiedzone.add(id(zasoby))
    for font in (_r(zasoby.get("Font")) or {}).values():
        font = _r(font) or {}
        nazwa = _nazwa(font.get("BaseFont"))
        if nazwa:
            wynik.setdefault(nazwa, font)
    for xobj in (_r(zasoby.get("XObject")) or {}).values():
        xobj = _r(xobj)
        attrs = getattr(xobj, "attrs", None) or {}
        if _nazwa(attrs.get("Subtype")) == "Form" and "Resources" in attrs:
            _fonty_zasobow(attrs["Resources"], wynik, odwiedzone)


def _czy_laczacy(tekst: str) -> bool:
    return bool(tekst) and all(unicodedata.combining(z) for z in tekst)


def napraw_strone(strona, pamiec: dict | None = None) -> OcenaStrony:
    """Podmienia znaczniki „(cid:N)” w `strona.chars` na znaki z osadzonego fontu.

    `strona` to `pdfplumber.page.Page`; wywołaj PRZED pierwszym
    `extract_text*` (pdfplumber buforuje mapę tekstu). `pamiec` to pamięć
    podręczna dokumentu {BaseFont: mapa CID → znak} — nazwa podzbioru
    („WNVQEB+TimesNewRomanPSMT”) jest w pliku unikalna.

    Znak łączący (U+0301 akcentu) dokleja się do POPRZEDNIEGO znaku tej samej
    linii, zamiast zostać osobnym znakiem o zerowej szerokości: pdfplumber
    wstawiał po nim spację („ДОКОРО́ ННЫЙ”), bo kolejna litera stoi dalej niż
    tolerancja od jego pozycji wewnątrz poprzedniej litery.
    """
    if pamiec is None:
        pamiec = {}
    znaki = strona.chars
    litery = 0
    do_naprawy = []
    for poz, z in enumerate(znaki):
        tekst = z.get("text") or ""
        m = _CALY_ZNACZNIK.match(tekst)
        if m:
            litery += 1
            do_naprawy.append((poz, int(m.group(1))))
        elif tekst.isalpha():
            litery += 1
    if not do_naprawy:
        return OcenaStrony(litery, 0, 0)
    fonty: dict = {}
    _fonty_zasobow(getattr(strona.page_obj, "resources", None), fonty, set())
    nierozwiazane = 0
    laczace = []
    for poz, cid in do_naprawy:
        z = znaki[poz]
        nazwa = z.get("fontname") or ""
        if nazwa not in pamiec:
            pamiec[nazwa] = mapa_cid_fontu(fonty[nazwa]) if nazwa in fonty else {}
        nowy = pamiec[nazwa].get(cid)
        if not nowy:
            nierozwiazane += 1
            continue
        z["text"] = nowy
        if _czy_laczacy(nowy):
            laczace.append(poz)
    for poz in reversed(laczace):
        # Bazą jest najbliższy wcześniejszy znak niebędący spacją: w tekście
        # rozstrzelonym („К и т ́ а й”) między literą a akcentem stoi spacja.
        baza = poz - 1
        while baza >= 0 and baza >= poz - 3 and (znaki[baza].get("text") or "").isspace():
            baza -= 1
        if baza < 0:
            continue
        z, poprzedni = znaki[poz], znaki[baza]
        ptekst = poprzedni.get("text") or ""
        if (not ptekst or ptekst.isspace() or _CALY_ZNACZNIK.match(ptekst)
                or abs(z["top"] - poprzedni["top"]) > max(z.get("size") or 0, 1)
                # W tekście rozstrzelonym akcent stoi ZA literą (o odstęp
                # rozstrzelenia, s. 81 słownika: 4,1 pt) — do jednej szerokości litery.
                or not (poprzedni["x0"] - 1 <= z["x0"]
                        <= poprzedni["x1"] + max(poprzedni["x1"] - poprzedni["x0"], 1))):
            continue
        poprzedni["text"] = ptekst + z["text"]
        del znaki[poz]
    return OcenaStrony(litery, len(do_naprawy), nierozwiazane)


def usun_znaczniki(tekst: str) -> str:
    """Tekst bez pozostałych znaczników „(cid:N)”."""
    return ZNACZNIK_CID.sub("", tekst)


def zakresy_stron(indeksy) -> str:
    """[1, 2, 3, 7] (od 0) → „2–4, 8” — numery od 1, ciągi jako zakresy.

    Zwięźle dla czytnika ekranu: 550 numerów wyliczonych po kolei to minuta
    czytania, „2–551” to sekunda.
    """
    nums = sorted({i + 1 for i in indeksy})
    czesci, i = [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        czesci.append(str(nums[i]) if i == j else f"{nums[i]}–{nums[j]}")
        i = j + 1
    return ", ".join(czesci)


# ---------------------------------------------------------------------------
# Tekst ze źródeł konwertowanych z PDF: U+F020, rozstrzelenia, przeniesienia
# ---------------------------------------------------------------------------
# WSPÓLNA SPECYFIKACJA z Reżyserem (decyzja użytkownika 2026-10-20 „Hybryda”:
# jedna semantyka dla obu bliźniaków, klasa `formaty_zrodel`). Kolejność kroków
# jest częścią specyfikacji: U+F020 → rozstrzelenia → przeniesienia; każdy krok
# liczy słowa dokumentu na SWOIM wejściu.
#
# Słowo dokumentu = `_SLOWO`: litery z pojedynczymi łącznikami w środku
# („ковид-диссидентов”), całe — nie przylega do litery, cyfry, „_” ani „-”;
# klucz casefold, bez znaków łączących. Fragment przeniesienia „бело-” słowem
# nie jest (przylega do „-”), prawy fragment „голубых” po spacji — jest.

_SPACJA_PUA = chr(0xF020)    # spacja z fontu symboli (Wingdings) — wcięcia list w DOCX z PDF
_SLOWO = re.compile(r"(?<![\w-])[^\W\d_]+(?:-[^\W\d_]+)*(?![\w-])")
# Kandydat przeniesienia: token kończący się literą, „-”, ≥ 1 spacja, token
# zaczynający się literą (wielkość, pismo i wykluczenia sprawdza `_przeniesienie`).
_PRZENIESIENIE = re.compile(r"(?<!\S)(\S*[^\W\d_])- +([^\W\d_]\S*)")
# Znaki, które wykluczają kandydata, gdy stoją W tokenie (adresy, slugi).
_ZNAKI_ADRESU = frozenset("./@:_" + chr(0xFF20))
# Interpunkcja zdaniowa zdejmowana z brzegu tokenu przed tym testem: kropka
# końca zdania po „мы.” nie czyni z niego adresu.
_BRZEG_LEWY = "«„“\"'([‹"
_BRZEG_PRAWY = ".,;:!?…»”\"')]›"
MIN_ROZSTRZELENIE = 4        # tyle co najmniej jednoliterowych tokenów w serii


def _bez_znakow_laczacych(tekst: str) -> str:
    return "".join(z for z in tekst if not unicodedata.combining(z))


def slowa_dokumentu(akapity) -> Counter:
    """Licznik słów dokumentu (`_SLOWO`, casefold, bez znaków łączących)."""
    licz: Counter = Counter()
    for akapit in akapity:
        for m in _SLOWO.finditer(_bez_znakow_laczacych(akapit)):
            licz[m.group(0).casefold()] += 1
    return licz


def _pismo(znak: str) -> str:
    """Pierwsze słowo nazwy Unicode: LATIN, CYRILLIC, …"""
    return unicodedata.name(znak, "?").split(" ", 1)[0]


def zamien_spacje_pua(tekst: str) -> tuple[str, int]:
    """U+F020 → zwykła spacja (przed normalizacją spacji w loaderze)."""
    n = tekst.count(_SPACJA_PUA)
    return (tekst.replace(_SPACJA_PUA, " ") if n else tekst), n


# --- rozstrzelenia -----------------------------------------------------------

def _jednoliterowy(token: str) -> bool:
    """Litera + ewentualne znaki łączące (akcent): „о́”."""
    rdzen = _bez_znakow_laczacych(token)
    return len(rdzen) == 1 and rdzen.isalpha() and token[:1] == rdzen


def sklej_rozstrzelenia(akapity: list[str], slowa: Counter | None = None
                        ) -> tuple[list[str], int, int]:
    """Skleja tekst rozstrzelony „у с т о й ч и в о е” → „устойчивое”.

    Seria = co najmniej `MIN_ROZSTRZELENIE` tokenów jednoliterowych (litera +
    znaki łączące) rozdzielonych POJEDYNCZYMI spacjami; dwie spacje i więcej
    rozdzielają słowa. Seria jest sklejana tylko wtedy, gdy sklejona forma
    (casefold, bez znaków łączących) jest słowem dokumentu — jednoliterowe
    słowa („в к с о и а у я”, „w z i”) obok siebie nie tworzą słowa, więc nie
    są sklejane. Zwraca (akapity, sklejone serie, pozostawione serie).
    """
    if slowa is None:
        slowa = slowa_dokumentu(akapity)
    sklejone = pozostawione = 0
    wynik = []
    for akapit in akapity:
        czesci = re.split(r"( +)", akapit)       # [token, sep, token, sep, …]
        if len(czesci) < 2 * MIN_ROZSTRZELENIE - 1:
            wynik.append(akapit)
            continue
        out: list[str] = []
        i = 0
        while i < len(czesci):
            j = i
            if i % 2 == 0 and _jednoliterowy(czesci[i]):
                while (j + 2 < len(czesci) and czesci[j + 1] == " "
                       and _jednoliterowy(czesci[j + 2])):
                    j += 2
            if (j - i) // 2 + 1 >= MIN_ROZSTRZELENIE:
                razem = "".join(czesci[i:j + 1:2])
                if slowa[_bez_znakow_laczacych(razem).casefold()]:
                    out.append(razem)
                    sklejone += 1
                else:
                    out.extend(czesci[i:j + 1])
                    pozostawione += 1
                i = j + 1
            else:
                out.append(czesci[i])
                i += 1
        wynik.append("".join(out))
    return wynik, sklejone, pozostawione


# --- przeniesienia -----------------------------------------------------------

def _rdzen(token: str, brzeg: str, z_lewej: bool) -> tuple[str, str]:
    """(otoczka, rdzeń): interpunkcja zdaniowa zdjęta z jednego brzegu tokenu."""
    if z_lewej:
        k = len(token) - len(token.lstrip(brzeg))
        return token[:k], token[k:]
    k = len(token.rstrip(brzeg))
    return token[k:], token[:k]


def _wykluczony(rdzen: str) -> bool:
    return any(z in _ZNAKI_ADRESU or z.isdigit() for z in rdzen)


def _regula(lewy: str, prawy: str, slowa: Counter) -> int:
    """Reguła 1–4 wspólnej specyfikacji dla kandydata (lewy, prawy).

    Liczniki są z CAŁEGO dokumentu bez samego kandydata: jego prawy fragment
    liczy się jako słowo (stoi po spacji), więc odejmujemy to jedno wystąpienie.
    1. „L+R” jest słowem → sklej bez łącznika;
    2. „L-R” jest słowem → sklej z łącznikiem;
    3. R nie jest samodzielnym słowem → sklej bez łącznika;
    4. inaczej bez zmian („бело- голубых”, „двух- и трёх…”).
    """
    if slowa[(lewy + prawy).casefold()]:
        return 1
    if slowa[(lewy + "-" + prawy).casefold()]:
        return 2
    wlasne = 1 if _SLOWO.fullmatch(prawy) else 0
    return 3 if slowa[prawy.casefold()] - wlasne <= 0 else 4


def _przeniesienie(lewy_tok: str, prawy_tok: str):
    """(otoczka L, L, R, otoczka R) albo None, gdy kandydat jest wykluczony."""
    ol, lewy = _rdzen(lewy_tok, _BRZEG_LEWY, True)
    orr, prawy = _rdzen(prawy_tok, _BRZEG_PRAWY, False)
    if (not lewy or not prawy or not lewy[-1].isalpha() or not prawy[0].islower()
            or prawy.endswith("-") or _wykluczony(lewy) or _wykluczony(prawy)
            or _pismo(lewy[-1]) != _pismo(prawy[0])):
        return None
    return ol, lewy, prawy, orr


def _zlacz(lewy: str, prawy: str, regula: int) -> str:
    return lewy + ("-" if regula == 2 else "") + prawy


def sklej_przeniesienia(akapity: list[str], slowa: Counter | None = None
                        ) -> tuple[list[str], Counter]:
    """Przeniesienia „wyraz- wyraz” WEWNĄTRZ akapitu wg wspólnej specyfikacji.

    Kandydat: token kończący się literą, „-”, jedna lub więcej spacji, token
    zaczynający się MAŁĄ literą tego samego pisma. Wykluczony, gdy w którymś
    tokenie (po zdjęciu interpunkcji zdaniowej z brzegu) stoi „.”, „/”, „@”,
    „＠”, „:”, „_” albo cyfra, albo gdy prawy zaczyna się wielką literą
    („ПО- СВЯЩЕННОГО”). Decyzja: `_regula`. Myślniki i łącznik bez spacji
    („по-английски”) nie są kandydatami z definicji.

    Zwraca (akapity, licznik: 1/2/3/4 = reguła, "wykluczone").
    """
    if slowa is None:
        slowa = slowa_dokumentu(akapity)
    licz: Counter = Counter()

    def zamien(m):
        k = _przeniesienie(m.group(1), m.group(2))
        if k is None:
            licz["wykluczone"] += 1
            return m.group(0)
        ol, lewy, prawy, orr = k
        r = _regula(lewy, prawy, slowa)
        licz[r] += 1
        return m.group(0) if r == 4 else ol + _zlacz(lewy, prawy, r) + orr

    return [_PRZENIESIENIE.sub(zamien, a) if "-" in a else a for a in akapity], licz


_KONIEC = re.compile(r"(?<!\S)(\S*[^\W\d_])-$")
_POCZATEK = re.compile(r"^([^\W\d_]\S*)")


def sklej_przez_akapity(akapity: list[str], style: list[str],
                        slowa: Counter | None = None) -> tuple[list[str], Counter]:
    """Przeniesienie przez granicę akapitu — te same reguły 1–4 co w akapicie.

    Bezpiecznik ATA ponad specyfikację: akapit kończy się „litera-”, NASTĘPNY
    akapit (bez pustego między nimi) ma ten sam styl i zaczyna się literą;
    granica akapitu gra rolę spacji. Poza tym (inny styl, pusty akapit) bez
    zmian, a wielka litera („-И-” → „Не хвались…”) jest wykluczona jak w akapicie.
    `akapity` — wszystkie akapity dokumentu z pustymi; `style` — nazwy stylów.
    Zwraca (akapity, licznik: 1/2/3/4, "wykluczone", "bez_bezpiecznika").
    """
    if slowa is None:
        slowa = slowa_dokumentu(akapity)
    licz: Counter = Counter()
    wynik: list[str] = []
    i = 0
    while i < len(akapity):
        tekst = akapity[i]
        m = _KONIEC.search(tekst) if tekst.endswith("-") else None
        if m:
            nast = akapity[i + 1] if i + 1 < len(akapity) else ""
            p = _POCZATEK.match(nast)
            if not (p and i + 1 < len(style) and style[i + 1] == style[i]):
                licz["bez_bezpiecznika"] += 1
            else:
                k = _przeniesienie(m.group(1), p.group(1))
                if k is None:
                    licz["wykluczone"] += 1
                else:
                    ol, lewy, prawy, orr = k
                    r = _regula(lewy, prawy, slowa)
                    licz[r] += 1
                    if r != 4:
                        wynik.append(tekst[:m.start()] + ol + _zlacz(lewy, prawy, r) + orr
                                     + nast[p.end():])
                        i += 2
                        continue
        wynik.append(tekst)
        i += 1
    return wynik, licz


class CzyszczenieTekstu(NamedTuple):
    spacje_pua: int
    rozstrzelenia_sklejone: int
    rozstrzelenia_pozostawione: int
    przeniesienia: Counter           # w akapicie: 1/2/3/4, "wykluczone"
    przez_akapity: Counter           # jw. + "bez_bezpiecznika"


def oczysc_akapity(akapity: list[str], style: list[str] | None = None,
                   przeniesienia: bool = True) -> tuple[list[str], CzyszczenieTekstu]:
    """Cały potok w kolejności specyfikacji: U+F020 → rozstrzelenia → przeniesienia.

    Wspólne wejście `load_docx` i `load_pdf` oraz bramki źródła raportu
    (`zrodlo_raportu`). Bez `style` przez granicę akapitu nie sklejamy.
    `przeniesienia=False` dla PDF: tam przeniesienie końca wiersza skleja już
    `clean_pdf_text` (dywiz na końcu wiersza), a „wyraz- wyraz” w jednym
    wierszu PDF to
    prawdziwy zawieszony łącznik albo myślnik.
    """
    pua = 0
    tmp = []
    for a in akapity:
        a, n = zamien_spacje_pua(a)
        pua += n
        tmp.append(a)
    tmp, roz_s, roz_p = sklej_rozstrzelenia(tmp)
    slowa = slowa_dokumentu(tmp)
    przez: Counter = Counter()
    if style is not None:
        tmp, przez = sklej_przez_akapity(tmp, style, slowa)
    prz: Counter = Counter()
    if przeniesienia:
        tmp, prz = sklej_przeniesienia(tmp, slowa)
    return tmp, CzyszczenieTekstu(pua, roz_s, roz_p, prz, przez)


# ---------------------------------------------------------------------------
# PDF: granice słów w tekście rozstrzelonym z GEOMETRII znaków
# ---------------------------------------------------------------------------
# W warstwie tekstu PDF rozstrzelenie i odstęp między słowami dają TĘ SAMĄ
# pojedynczą spację („в о́ й н ы.”), więc reguła tekstowa łączyła słowa albo je
# rwała. Granicę widać dopiero w położeniu liter (słownik, s. 55): odstęp między
# literami 4,1 pt, między słowami 11,5 pt, a po literze z akcentem 8,3 pt
# (rozstrzelenie dokłada odstęp także za akcentem, ≈ jeden odstęp liter).
# Próg 1,5, nie 1,8 jak w Reżyserze: w Земской (pdfplumber, spacje w warstwie
# tekstu) odstęp słów to tylko 1,77–1,9× odstępu liter (6,47 vs 3,66 pt) i przy
# 1,8 „существительных неод…” się zlewały; odstępy liter wahają się do 1,2×.
# Po literze z akcentem granica dopiero powyżej (PROG + 1) × mediana: 8,3 pt
# to nie granica, 17,96 pt („Волна́ какая”, s. 42) — tak; zakaz bezwzględny
# zlewał takie słowa.
# Decyzji o sklejeniu tu NIE ma: należy do wspólnego modułu (etap 4, część 2).
PROG_GRANICY_ROZSTRZELENIA = 1.5   # granica: odstęp > PROG × mediana odstępów serii


class SeriaRozstrzelona(NamedTuple):
    """Seria jednoliterowych słów pdfplumbera w jednej linii strony."""
    litery: tuple            # „з”, „о́”, „н”, „а” — litera z ewentualnymi znakami łączącymi
    granice: tuple           # len(litery) - 1; True = granica słowa ZA literą i
    odstepy: tuple           # odstępy w pt między kolejnymi literami
    top: float
    x0: float
    x1: float
    przed: str = ""          # interpunkcja przed pierwszą literą („«л е …”)
    po: str = ""             # interpunkcja za ostatnią („… к и,”)

    def slowa(self) -> list[str]:
        """Słowa wg geometrii: [„Жёлтая”, „зо́на”]."""
        wynik, biezace = [], self.litery[0]
        for litera, granica in zip(self.litery[1:], self.granice):
            if granica:
                wynik.append(biezace)
                biezace = litera
            else:
                biezace += litera
        wynik.append(biezace)
        return wynik

    def tekst(self) -> str:
        """Tak, jak seria stoi w `extract_text`: litery przez pojedynczą spację."""
        return self.przed + " ".join(self.litery) + self.po


def _granice_serii(litery: list, odstepy: list) -> tuple:
    import statistics
    mediana = statistics.median(odstepy)
    return tuple(
        g > (PROG_GRANICY_ROZSTRZELENIA + (1 if unicodedata.combining(litery[i][-1]) else 0)) * mediana
        for i, g in enumerate(odstepy))


def serie_rozstrzelone(strona, x_tolerance: float = 3) -> list[SeriaRozstrzelona]:
    """Serie ≥ `MIN_ROZSTRZELENIE` jednoliterowych słów w jednej linii strony.

    `strona` to `pdfplumber.page.Page` — po `napraw_strone`, jeśli ta była
    potrzebna (akcent jest wtedy doklejony do litery i ma jej położenie).
    Słowa wg `extract_words` z tą samą tolerancją, z jaką `extract_text` stawia
    spację; samodzielny znak łączący (PDF bez naprawy) dokleja się do litery
    przed nim. Linia = to samo `top` (± 1 pt), kolejne słowa w porządku `x0`.
    """
    slowa = strona.extract_words(x_tolerance=x_tolerance)
    serie: list[SeriaRozstrzelona] = []
    run: list[dict] = []
    brzegi = {"przed": "", "po": ""}

    def zamknij():
        if len(run) >= MIN_ROZSTRZELENIE:
            litery = [w["text"] for w in run]
            odstepy = [round(b["x0"] - a["x1"], 2) for a, b in zip(run, run[1:])]
            serie.append(SeriaRozstrzelona(tuple(litery), _granice_serii(litery, odstepy),
                                           tuple(odstepy), run[0]["top"], run[0]["x0"], run[-1]["x1"],
                                           brzegi["przed"], brzegi["po"]))
        run.clear()
        brzegi["przed"] = brzegi["po"] = ""

    for w in slowa:
        tekst = w["text"]
        ta_sama_linia = bool(run) and abs(w["top"] - run[-1]["top"]) <= 1 and w["x0"] >= run[-1]["x0"]
        if run and ta_sama_linia and tekst and all(unicodedata.combining(z) for z in tekst):
            run[-1] = {**run[-1], "text": run[-1]["text"] + tekst}   # położenie litery, nie akcentu
            continue
        if _jednoliterowy(tekst):
            if run and not ta_sama_linia:
                zamknij()
            run.append(w)
            continue
        # Litera z interpunkcją zdaniową: „и,” kończy serię, „«л” ją zaczyna.
        rdzen_po = tekst.rstrip(_BRZEG_PRAWY)
        if run and ta_sama_linia and rdzen_po != tekst and _jednoliterowy(rdzen_po):
            run.append({**w, "text": rdzen_po})
            brzegi["po"] = tekst[len(rdzen_po):]
            zamknij()
            continue
        zamknij()
        rdzen_przed = tekst.lstrip(_BRZEG_LEWY)
        if rdzen_przed != tekst and _jednoliterowy(rdzen_przed):
            run.append({**w, "text": rdzen_przed})
            brzegi["przed"] = tekst[:len(tekst) - len(rdzen_przed)]
    zamknij()
    return serie
