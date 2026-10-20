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

Część DOCX (`sklej_przeniesienia`) — patrz jej docstring.

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
# DOCX: przeniesienia wewnątrz akapitu
# ---------------------------------------------------------------------------
# Kandydat: litery, ASCII „-”, JEDNA spacja, litery — „по- священного”. Półpauza,
# pauza i łącznik bez spacji („по-английски”) nie są kandydatami z definicji.
_PRZENIESIENIE = re.compile(r"([^\W\d_]+)- ([^\W\d_]+)")
_SLOWO = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*")
# Zawieszony łącznik („двух- и трёхкомнатный”, „jedno- lub dwuosobowy”,
# „pre- and post-war”): prawy fragment to krótkie słowo z czołówki frekwencji
# dokumentu (spójnik), a po nim stoi spacja. Czołówka, nie „jakiekolwiek
# samodzielne słowo”: sylaby „на”, „ца”, „ков” też bywają słowami
# („заблокирова- на”, „прин- ца”) — zmierzone na słowniku, 205 → 10.
SPOJNIK_MAKS = 4
SPOJNIK_RANGA = 60
# Lewy fragment co najmniej tej długości, poświadczony jako pierwszy człon
# złożenia z łącznikiem („ковид-контакт”), to człon złożenia, nie sylaba —
# o ile sam jest też samodzielnym słowem („интернет- чушь”) albo prawy fragment
# rozpoczyna jakieś słowo dokumentu („ковид- трупами”). Sylaba-człon bez obu
# („короновирус- ный” — „ный” nie zaczyna słowa) jest sklejana. Zmierzone na
# słowniku: ~70 złożeń zachowanych, ~7 pomyłek („пара- лизовала”, „ком- плекта”).
CZLON_MIN = 3


class _Slownik(NamedTuple):
    slowa: Counter            # słowa i złożenia (małe litery)
    czlony: Counter           # pierwsze człony złożeń z łącznikiem
    poczatki: list            # posortowane słowa i człony — test „zaczyna słowo”
    czolowka: frozenset       # SPOJNIK_RANGA najczęstszych słów bez łącznika


def _slownik_dokumentu(akapity: list[str]) -> _Slownik:
    """Słownik z tekstu, w którym kandydaci są wycięci.

    Słownikiem jest SAM dokument — bez list języków i bez modelu. Wycięcie
    kandydatów jest konieczne: inaczej „ния” z „попада- ния” liczyłoby się
    jako samodzielne słowo.
    """
    slowa: Counter = Counter()
    czlony: Counter = Counter()
    for akapit in akapity:
        for w in _SLOWO.findall(_PRZENIESIENIE.sub(" ", akapit)):
            w = w.lower()
            slowa[w] += 1
            if "-" in w:
                czlony[w.split("-", 1)[0]] += 1
    czesci = {c for w in slowa for c in w.split("-")}
    proste = Counter({w: n for w, n in slowa.items() if "-" not in w})
    czolowka = frozenset(w for w, _ in proste.most_common(SPOJNIK_RANGA))
    return _Slownik(slowa, czlony, sorted(czesci), czolowka)


def _zaczyna_slowo(fragment: str, poczatki: list) -> bool:
    import bisect
    i = bisect.bisect_left(poczatki, fragment)
    return i < len(poczatki) and poczatki[i].startswith(fragment)


def _pismo(tekst: str) -> str:
    """Pierwsze słowo nazwy Unicode pierwszej litery: LATIN, CYRILLIC, …"""
    return unicodedata.name(tekst[0], "?").split(" ", 1)[0]


def _decyzja(lewy: str, prawy: str, dalej: str, sl: _Slownik) -> str:
    """'sklej' | 'lacznik' (zostaw „-”, usuń spację) | 'zostaw'."""
    razem, z_lacznikiem = (lewy + prawy).lower(), (lewy + "-" + prawy).lower()
    a, b = sl.slowa[razem], sl.slowa[z_lacznikiem]
    if len(lewy) < 2 or len(prawy) < 2:
        # Dzielenie wyrazu zostawia na wierszu ≥ 2 znaki: „двух- и”, „Приставка
        # е- в” to nie przeniesienia. Wolno tylko poświadczony łącznik („кого-л.”).
        return "lacznik" if b > a else "zostaw"
    if a or b:                      # dokument sam zna jedną z form
        return "sklej" if a >= b else "lacznik"
    if lewy.isupper() and prawy[0].isupper() and not prawy.isupper():
        return "zostaw"             # „ЯЗЫК- То же”: hasło wersalikami + zdanie (OCR)
    if (len(lewy) >= CZLON_MIN and sl.czlony[lewy.lower()]
            and (sl.slowa[lewy.lower()] or _zaczyna_slowo(prawy.lower(), sl.poczatki))):
        return "lacznik"            # „ковид- трупами”, „COVID- субсидиях” ← „ковид-контакт”
    if _pismo(lewy) != _pismo(prawy):
        return "zostaw"             # „root- корневой”: nie sylaby jednego słowa
    if prawy[0].isupper():          # „Мать- Природа”, „Бен- Гурион”
        return "lacznik"
    if len(prawy) <= SPOJNIK_MAKS and prawy.lower() in sl.czolowka and dalej.startswith(" "):
        return "zostaw"             # zawieszony łącznik: „аудио- и видео…”
    return "sklej"


def sklej_przeniesienia(akapity: list[str]) -> tuple[list[str], Counter]:
    """Skleja przeniesienia „wyraz- wyraz” WEWNĄTRZ akapitów DOCX.

    Plik zapisany z PDF (np. przez konwerter) niesie dawne przeniesienia
    końca wiersza jako „по- священного”. Kolejność decyzji (`_decyzja`):
    1. fragment jednoliterowy — bez zmian, chyba że dokument poświadcza formę
       z łącznikiem („кого-л.”); dzielenie wyrazu zostawia na wierszu ≥ 2 znaki
       („двух- и трёх…”, „Приставка е- в”);
    2. dokument poświadcza formę sklejoną albo z łącznikiem — wygrywa częstsza;
    2a. lewy cały wersalikami, prawy zaczyna się wielką literą (hasło + zdanie
        z OCR: „РЕКУРСИЯ- То же”) — bez zmian;
    3. lewy fragment to poświadczony człon złożenia i zarazem słowo, albo prawy
       zaczyna jakieś słowo dokumentu — łącznik zostaje („COVID- субсидиях”);
    4. fragmenty w różnych pismach — bez zmian („root- корневой”);
    5. prawy fragment od wielkiej litery — łącznik zostaje („Мать-Природа”);
    6. krótki prawy fragment z czołówki frekwencji, a po nim spacja —
       zawieszony łącznik, bez zmian („аудио- и видео…”);
    7. inaczej — przeniesienie, sklejamy.
    Przeniesień PRZEZ granicę akapitu nie sklejamy: akapit kończący się
    „litera-” bywa hasłem słownika („КОРОНА-”) albo członem zawieszonym.

    Zwraca (akapity, liczniki decyzji: sklej / lacznik / zostaw).
    """
    sl = _slownik_dokumentu(akapity)
    licz: Counter = Counter()
    wynik = []
    for akapit in akapity:
        def zamien(m):
            lewy, prawy = m.group(1), m.group(2)
            d = _decyzja(lewy, prawy, akapit[m.end():m.end() + 1], sl)
            licz[d] += 1
            if d == "sklej":
                return lewy + prawy
            if d == "lacznik":
                return lewy + "-" + prawy
            return m.group(0)
        wynik.append(_PRZENIESIENIE.sub(zamien, akapit))
    return wynik, licz


_KONIEC_PRZENIESIENIA = re.compile(r"([^\W\d_]+)-$")
_POCZATEK = re.compile(r"[^\W\d_]+")


def sklej_przez_akapity(akapity: list[str], style: list[str]) -> tuple[list[str], int, int]:
    """Skleja przeniesienie przez granicę akapitu TYLKO, gdy jest dowiedzione.

    Dowód = cztery warunki naraz: akapit kończy się „litera-”, NASTĘPNY akapit
    (bez pustego między nimi) ma ten sam styl, zaczyna się małą literą, a forma
    sklejona albo z łącznikiem jest poświadczona gdzie indziej w dokumencie.
    Reszta zostaje, bo w słowniku koniec akapitu „litera-” to też nagłówek
    sekcji („-И-” → „Не хвались…”), hasło („КОРОНА-”) albo urwany przypis.
    `akapity` — wszystkie akapity dokumentu, z pustymi; `style` — nazwy stylów.
    Zwraca (akapity, sklejone, pozostawione).
    """
    sl = _slownik_dokumentu(akapity)
    wynik: list[str] = []
    sklejone = pozostawione = 0
    i = 0
    while i < len(akapity):
        tekst = akapity[i]
        m = _KONIEC_PRZENIESIENIA.search(tekst)
        if m:
            nast = akapity[i + 1] if i + 1 < len(akapity) else ""
            p = _POCZATEK.match(nast)
            decyzja = None
            if (p and nast[:1].islower() and style[i + 1] == style[i]
                    and len(m.group(1)) >= 2 and len(p.group(0)) >= 2):
                lewy, prawy = m.group(1), p.group(0)
                a = sl.slowa[(lewy + prawy).lower()]
                b = sl.slowa[(lewy + "-" + prawy).lower()]
                if a or b:
                    decyzja = "sklej" if a >= b else "lacznik"
            if decyzja:
                wynik.append((tekst[:-1] if decyzja == "sklej" else tekst) + nast)
                sklejone += 1
                i += 2
                continue
            pozostawione += 1
        wynik.append(tekst)
        i += 1
    return wynik, sklejone, pozostawione
