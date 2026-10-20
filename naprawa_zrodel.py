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

Czyszczenie tekstu (U+F020, mojibake, rozstrzelenia, przeniesienia) jest we
WSPÓLNYM module `czyszczenie_tekstu.py` (bliźniak bajt w bajt z Reżyserem);
tu zostają geometria rozstrzeleń PDF i adaptery stron PDF dla tego modułu.

Moduł niczego nie drukuje — komunikaty należą do notatnika (`load_pdf`,
`load_docx`).
"""
from __future__ import annotations

import io
import re
import unicodedata
from typing import NamedTuple

import czyszczenie_tekstu as _ct

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
# Decyzji o sklejeniu tu NIE ma: `czyszczenie_tekstu.scal_rozstrzelone(...,
# granica=ZNACZNIK_GRANICY)` dostaje tekst z granicami z `oznacz_granice`.
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
    poczatek_linii: bool = False   # przed serią nie ma słowa w tej linii
    nastepny: str | None = None    # słowo za serią w tej linii; None = koniec linii
    odstep_po: float | None = None # odstęp w pt do `nastepny`

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
    """Serie ≥ `MIN_ROZSTRZELENIE` (modułu wspólnego) jednoliterowych słów w jednej linii strony.

    `strona` to `pdfplumber.page.Page` — po `napraw_strone`, jeśli ta była
    potrzebna (akcent jest wtedy doklejony do litery i ma jej położenie).
    Słowa wg `extract_words` z tą samą tolerancją, z jaką `extract_text` stawia
    spację; samodzielny znak łączący (PDF bez naprawy) dokleja się do litery
    przed nim. Linia = to samo `top` (± 1 pt), kolejne słowa w porządku `x0`.
    """
    slowa = strona.extract_words(x_tolerance=x_tolerance)
    serie: list[SeriaRozstrzelona] = []
    run: list[dict] = []
    brzegi = {"przed": "", "po": "", "start": False}
    poprzednie = [None]          # słowo przed bieżącym (do „początku linii”)

    def linia(a, b) -> bool:
        return a is not None and abs(b["top"] - a["top"]) <= 1 and b["x0"] >= a["x0"]

    def zamknij(nastepny=None):
        if len(run) >= _ct.MIN_ROZSTRZELENIE:
            litery = [w["text"] for w in run]
            odstepy = [round(b["x0"] - a["x1"], 2) for a, b in zip(run, run[1:])]
            obok = nastepny is not None and linia(run[-1], nastepny)
            serie.append(SeriaRozstrzelona(
                tuple(litery), _granice_serii(litery, odstepy), tuple(odstepy),
                run[0]["top"], run[0]["x0"], run[-1]["x1"], brzegi["przed"], brzegi["po"],
                brzegi["start"], nastepny["text"] if obok else None,
                round(nastepny["x0"] - run[-1]["x1"], 2) if obok else None))
        run.clear()
        brzegi["przed"] = brzegi["po"] = ""

    def otworz(w):
        if not run:
            brzegi["start"] = not linia(poprzednie[0], w)

    for w in slowa:
        tekst = w["text"]
        if run and brzegi["po"]:          # „и,” zamknęło serię; `w` to jej sąsiad
            zamknij(w)
        ta_sama_linia = bool(run) and linia(run[-1], w)
        if run and ta_sama_linia and tekst and all(unicodedata.combining(z) for z in tekst):
            run[-1] = {**run[-1], "text": run[-1]["text"] + tekst}   # położenie litery, nie akcentu
            continue
        if _ct.litera_pojedyncza(tekst):
            if run and not ta_sama_linia:
                zamknij(w)
            otworz(w)
            run.append(w)
            poprzednie[0] = w
            continue
        # Litera z interpunkcją zdaniową: „и,” kończy serię, „«л” ją zaczyna.
        rdzen_po = tekst.rstrip(_ct.ZAMYKAJACE)
        if run and ta_sama_linia and rdzen_po != tekst and _ct.litera_pojedyncza(rdzen_po):
            run.append({**w, "text": rdzen_po})
            brzegi["po"] = tekst[len(rdzen_po):]
            poprzednie[0] = w
            continue
        zamknij(w)
        rdzen_przed = tekst.lstrip(_ct.OTWIERAJACE)
        if rdzen_przed != tekst and _ct.litera_pojedyncza(rdzen_przed):
            otworz(w)
            run.append({**w, "text": rdzen_przed})
            brzegi["przed"] = tekst[:len(tekst) - len(rdzen_przed)]
        poprzednie[0] = w
    zamknij()
    return serie


# Znak granicy słowa z geometrii, wstawiany w tekst strony dla
# `czyszczenie_tekstu.scal_rozstrzelone(..., granica=ZNACZNIK_GRANICY)` (ten
# zamienia go w wyniku na spację). Prywatny obszar Unicode: nie występuje
# w tekście, nie jest białym znakiem (przeżywa `clean_pdf_text`), nie jest
# literą (bramka źródła go nie widzi) i nie koduje się w Latin-1 (mojibake go
# nie rusza).
ZNACZNIK_GRANICY = chr(0xE000)


def _slowo_wieloliterowe(tekst: str | None) -> bool:
    """Sąsiad jest słowem, a nie dokładnie jedną literą ani samą interpunkcją."""
    return tekst is not None and sum(z.isalpha() for z in tekst) >= 2


def _prawa_granica(seria: SeriaRozstrzelona) -> bool:
    """Prawy brzeg serii: koniec linii, sąsiad-słowo (≥ 2 litery) albo odstęp
    do sąsiada powyżej progu — reguły 1:1 z Reżyserem."""
    if seria.nastepny is None:
        return True
    if _slowo_wieloliterowe(seria.nastepny):
        return True
    import statistics
    return (seria.odstep_po is not None
            and seria.odstep_po > PROG_GRANICY_ROZSTRZELENIA * statistics.median(seria.odstepy))


def oznacz_granice(tekst: str, serie: list[SeriaRozstrzelona]) -> tuple[str, int]:
    """Wstawia `ZNACZNIK_GRANICY` w granice słów serii rozstrzelonych strony.

    Granice WEWNĄTRZ serii z geometrii (`granice`) oraz brzegi serii wg reguł
    wspólnych z Reżyserem:
      * lewy brzeg — zawsze granica, chyba że seria zaczyna linię, a poprzednia
        linia kończy się przeniesieniem („лишь уве- | л и ч и в а е т” to jedno
        słowo);
      * prawy brzeg — granica na końcu linii, przy sąsiedzie-słowie (nie
        dokładnie jedna litera) albo przy odstępie do sąsiada powyżej progu.
    Bez znaczników pojedyncza spacja do sąsiada wyglądałaby dla modułu jak
    urwany kawałek („przyklejone”). Interpunkcja `przed`/`po` stoi przy literze
    jak w tekście; znacznik idzie za nią/przed nią.

    Serie szukamy w kolejności, od kursora, dokładnie w postaci `.tekst()`
    (tak stoją w `extract_text`). Seria, której nie ma w tekście (linia
    zdjęta jako kolontytuł), jest pomijana. Zwraca (tekst, oznaczonych serii).
    """
    nl = chr(10)
    wynik, kursor, n = [], 0, 0
    for seria in serie:
        k = tekst.find(seria.tekst(), kursor)
        if k < 0:
            continue
        koniec = k + len(seria.tekst())
        czesci = [seria.litery[0]]
        for litera, granica in zip(seria.litery[1:], seria.granice):
            czesci.append((" " + ZNACZNIK_GRANICY + " " if granica else " ") + litera)
        lewa = k > 0 and tekst[k - 1] in " " + nl
        if lewa and seria.poczatek_linii and tekst[k - 1] == nl:
            linia_przed = tekst[:k - 1].rsplit(nl, 1)[-1].rstrip()
            lewa = not linia_przed.endswith("-")
        prawa = koniec < len(tekst) and tekst[koniec] in " " + nl and _prawa_granica(seria)
        wynik.append(tekst[kursor:k] + (ZNACZNIK_GRANICY + " " if lewa else "")
                     + seria.przed + "".join(czesci) + seria.po
                     + (" " + ZNACZNIK_GRANICY if prawa else ""))
        kursor = koniec
        n += 1
    wynik.append(tekst[kursor:])
    return "".join(wynik), n


def oczysc_strone_pdf(tekst: str, alfabety) -> tuple[str, dict]:
    """U+F020 i mojibake jednej strony PDF — kolejność jak `oczysc_akapity_docx`.

    Jednostką mojibake jest strona, akapitami jej linie (krótkie linie dostają
    kodowanie, które wygrało w długich liniach strony). Zwraca (tekst,
    {"spacja_symbol": n, "mojibake_linie": n, "kodowania": {...}}).
    """
    linie, spacje = _ct.zamien_spacje_symbol(tekst.split("\n"))
    linie, info = _ct.napraw_mojibake_akapitow(linie, alfabety)
    return "\n".join(linie), {"spacja_symbol": spacje, "mojibake_linie": info["przekodowane"],
                               "kodowania": info["kodowania"]}
