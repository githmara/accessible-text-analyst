"""glosowanie_ocr.py – OCR wielojęzyczny: każdy język czyta swój silnik, słowa wybiera słownik.

Krok 2 migracji OCR (plan 2026-11-13). Silnik OCR zna jeden język naraz: polski
silnik zamienia fińskie ä na ă/i, fiński gubi ą/ę/ł, rosyjski wstawia cyrylicę
w łacińskie słowa (zmierzone na polsko-fińskim slajdzie). Dlatego stronę czyta
silnik KAŻDEGO języka korpusu, a z każdego wyniku bierzemy możliwie najwięcej form
słownikowych.

Członkowie głosowania (decyzje maintainera 2026-11-13):
- silnik Windows (`ocr_windows`) dla języka, który go ma (dziś 8 z 9 języków
  Reżysera; `podstawy.yaml::locale` wskazuje silnik);
- easyocr dla języka bez silnika Windows (islandzki: easyocr `is` 96–99% słów na
  czystej stronie, Windows bez þ/ð) — PEŁNOPRAWNY członek, a brak zależności to
  BŁĄD (D1): naprawą jest zmiana `ocr_languages` albo instalacja składników.

Słownik języka (forma jest „słownikowa”, gdy jej litery należą do alfabetu z
`podstawy.yaml` I leksykon ją zna — sam leksykon nie wystarcza, bo zna formy obce):
- wektory spaCy w trybie `default` = skończona lista form (pl, en, ru, it: 500–685 tys.,
  ~1,7 s i ~55 MB RAM na język, zmierzone);
- wektory `floret` (fi) znają KAŻDY napis — „intencjQ” przechodził jako fiński —
  więc słownikiem fińskim jest omorfi;
- brak modelu spaCy (is) — słownikiem jest BÍN z pakietu `islenska` (99,2% słów
  z literami islandzkimi; licencja danych CC BY-SA 4.0 wymaga uznania autorstwa
  w interfejsie — `UZNANIE_BIN`).
Gałęzie `kod == "fi"` / `kod == "is"` to logika dla jednego języka (jak w
`cell_model`), nie wyliczanie języków.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Callable, Optional

import ocr_windows as ow
from shamanic_locale import PODSTAWY

KATALOG = Path(__file__).resolve().parent
AUTOMATY_OMORFI = ("omorfi_recased.describe.hfst", "omorfi.describe.hfst")
UZNANIE_BIN = ("The Database of Icelandic Morphology. The Árni Magnússon Institute for "
               "Icelandic Studies. Author and editor Kristín Bjarnadóttir. https://bin.arnastofnun.is")
PROG_IOU = 0.4  # zmierzone w prototypie: ramki tego samego słowa z różnych silników mają IoU ≈ 1,0
_LITERY = re.compile(r"[^\W\d_]+", re.UNICODE)


@dataclass(frozen=True)
class Problem:
    """Język, którego nie da się włączyć do głosowania. `przyczyna`: `brak_silnika` albo `brak_slownika`."""

    kod: str
    przyczyna: str
    szczegol: str


class BladGlosowania(RuntimeError):
    """Co najmniej jeden język z konfiguracji nie może głosować; naprawa: zmienić `ocr_languages` albo doinstalować."""

    def __init__(self, problemy: list[Problem]):
        self.problemy = problemy
        super().__init__("; ".join(f"{p.kod}: {p.przyczyna} ({p.szczegol})" for p in problemy))


# ---------------------------------------------------------------- słowniki


def _rdzen(tekst: str) -> str:
    """Jedyny ciąg liter słowa („kuuluu?” → „kuuluu”); pusty, gdy liter brak albo jest ich kilka ciągów."""
    m = _LITERY.findall(tekst)
    return m[0] if len(m) == 1 else ""


@dataclass
class Slownik:
    kod: str
    alfabet: frozenset
    zna_forme: Callable[[str], bool]
    zrodlo: str

    def ocen(self, slowo: str) -> Optional[bool]:
        """True = forma słownikowa; False = nie; None = brak głosu (mniej niż 2 litery, liczba, znak)."""
        r = _rdzen(slowo)
        if len(r) < 2:
            return None
        if not set(r) <= self.alfabet:
            return False
        return self.zna_forme(r) or (r.lower() != r and self.zna_forme(r.lower()))


def _alfabet(kod: str) -> frozenset:
    a = PODSTAWY[kod]["alfabet"]
    return frozenset(a) | frozenset(a.lower())


def _slownik_spacy(kod: str, model: str) -> Slownik:
    import gc

    import spacy

    nlp = spacy.load(model, exclude=["tok2vec", "tagger", "parser", "ner", "lemmatizer", "attribute_ruler",
                                     "morphologizer", "senter", "trainable_lemmatizer"])
    wek = nlp.vocab.vectors
    if wek.mode != "default":
        raise LookupError(f"wektory {model} w trybie {wek.mode} nie są skończoną listą form")
    s = nlp.vocab.strings
    formy = frozenset(s[k] for k in wek.keys() if k in s)
    del nlp, wek, s
    gc.collect()
    return Slownik(kod, _alfabet(kod), formy.__contains__, f"spaCy {model} ({len(formy)} form)")


def _slownik_omorfi(kod: str) -> Slownik:
    from omorfi.omorfi import Omorfi
    from omorfi.token import Token

    sciezka = next((p for n in AUTOMATY_OMORFI for p in (Path.cwd() / n, KATALOG / n) if p.exists()), None)
    if sciezka is None:
        raise LookupError("brak automatów omorfi (*.hfst) — uruchom omorfi-download w katalogu repo")
    om = Omorfi()
    om.load_analyser(str(sciezka))

    @lru_cache(maxsize=65536)
    def zna(forma: str) -> bool:
        tok = Token.fromsurf(forma)
        om.analyse(tok)
        mala = forma.islower()
        for a in tok.analyses:
            lemat = "".join(a.get_lemmas() or [])
            # Te same dwa artefakty, co w cell_model._om_plausible: zgadywanie (waga inf)
            # i wielka litera w lemacie małej formy, wymyślona przez automat recased.
            if a.weight != float("inf") and lemat and not (mala and lemat != lemat.lower()):
                return True
        return False

    return Slownik(kod, _alfabet(kod), zna, f"omorfi ({sciezka.name})")


def _slownik_bin(kod: str) -> Slownik:
    from islenska import Bin

    b = Bin(add_compounds=True)
    return Slownik(kod, _alfabet(kod), lambda forma: bool(b.lookup(forma)[1]), "BÍN (islenska)")


@lru_cache(maxsize=None)
def slownik(kod: str) -> Slownik:
    """Słownik języka; `LookupError` z instrukcją, gdy brakuje składnika."""
    model = PODSTAWY[kod]["spacy"]
    try:
        if kod == "fi":
            return _slownik_omorfi(kod)
        if kod == "is":
            return _slownik_bin(kod)
        if model:
            return _slownik_spacy(kod, model)
    except ImportError as e:
        raise LookupError(f"brak pakietu: {e.name}") from e
    except OSError as e:  # spacy.load: model niezainstalowany
        raise LookupError(f"brak modelu spaCy {model}: python -m spacy download {model}") from e
    raise LookupError("język nie ma źródła słownika (ani wektorów spaCy, ani leksykonu)")


# ---------------------------------------------------------------- silniki


@dataclass
class PlanOcr:
    """Kto czyta który język: `windows[kod] = tag silnika`, `easyocr` = kody czytane przez easyocr."""

    windows: dict[str, str] = field(default_factory=dict)
    easyocr: list[str] = field(default_factory=list)
    slowniki: dict[str, Slownik] = field(default_factory=dict)


def _easyocr_zna(kod: str) -> Optional[bool]:
    """True/False wg listy easyocr; None, gdy easyocr nie jest zainstalowany."""
    try:
        from easyocr.config import all_lang_list
    except ImportError:
        return None
    return kod in all_lang_list


def zaplanuj(kody: list[str]) -> PlanOcr:
    """Przypisuje każdemu językowi silnik i słownik albo zbiera WSZYSTKIE problemy w jeden `BladGlosowania`."""
    plan, problemy = PlanOcr(), []
    try:
        ow.dostepne_jezyki()
        windows_dziala, powod_windows = True, ""
    except ow.OcrNiedostepny as e:
        windows_dziala, powod_windows = False, str(e)
    for kod in kody:
        tag = PODSTAWY[kod]["locale"]
        if windows_dziala and ow.silnik_dostepny(tag):
            plan.windows[kod] = tag
        else:
            easy = _easyocr_zna(kod)
            if easy:
                plan.easyocr.append(kod)
            else:
                brak = ("silnik Windows niedostępny: " + powod_windows) if not windows_dziala else \
                    f"Windows nie ma silnika {tag} (Ustawienia > Język > pakiet z rozpoznawaniem tekstu)"
                dalej = "easyocr niezainstalowany" if easy is None else "easyocr nie zna tego języka"
                problemy.append(Problem(kod, "brak_silnika", f"{brak}; {dalej}"))
                continue
        try:
            plan.slowniki[kod] = slownik(kod)
        except LookupError as e:
            problemy.append(Problem(kod, "brak_slownika", str(e)))
    if problemy:
        raise BladGlosowania(problemy)
    return plan


@lru_cache(maxsize=4)
def _czytnik_easyocr(kod: str):
    import easyocr

    # To samo obejście co w cell_corpus._get_ocr_reader: easyocr 1.7.2 robi z quantize=False
    # krotkę (False,) i kwantyzuje detektor przez przestarzałe torch.ao.quantization.
    czytnik = easyocr.Reader([kod], gpu=False, verbose=False, quantize=False, detector=False)
    czytnik.quantize = False
    czytnik.setDetector("craft")
    return czytnik


def _segmenty_easyocr(obraz, kod: str) -> list:
    """Surowe segmenty easyocr. numpy przychodzi razem z easyocr, więc importujemy go dopiero tu —
    reszta modułu (i jego testy na runnerze CI bez numpy) obywa się bez niego."""
    import numpy as np

    return _czytnik_easyocr(kod).readtext(np.array(obraz.convert("RGB")), detail=1, paragraph=False)


def slowa_easyocr(obraz, kod: str) -> list[ow.Slowo]:
    """easyocr zwraca SEGMENTY (kilka słów w jednej ramce): dzielimy je na słowa proporcjonalnie
    do liczby znaków, a segmenty o pokrywających się pionowo ramkach składamy w wiersze."""
    segmenty = []
    for ramka, tekst, _pewnosc in _segmenty_easyocr(obraz, kod):
        xs, ys = [p[0] for p in ramka], [p[1] for p in ramka]
        segmenty.append((min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys), tekst))
    segmenty.sort(key=lambda s: (s[1] + s[3] / 2, s[0]))
    wiersze: list[list[tuple]] = []
    for s in segmenty:
        srodek = s[1] + s[3] / 2
        if wiersze:
            ost = wiersze[-1]
            sr_w = sum(x[1] + x[3] / 2 for x in ost) / len(ost)
            wys_w = max(x[3] for x in ost)
            if abs(srodek - sr_w) < 0.5 * max(wys_w, s[3]):
                ost.append(s)
                continue
        wiersze.append([s])
    wynik = []
    for nr, wiersz in enumerate(wiersze):
        for x, y, w, h, tekst in sorted(wiersz):
            czesci = tekst.split()
            if not czesci:
                continue
            na_znak = w / max(1, len(tekst))
            poz = 0
            for c in czesci:
                start = tekst.index(c, poz)
                poz = start + len(c)
                wynik.append(ow.Slowo(nr, c, round(x + start * na_znak), round(y), max(1, round(len(c) * na_znak)),
                                      round(h)))
    return wynik


# ---------------------------------------------------------------- głosowanie


def _iou(a: ow.Slowo, b: ow.Slowo) -> float:
    x0, y0 = max(a.x, b.x), max(a.y, b.y)
    x1, y1 = min(a.x + a.w, b.x + b.w), min(a.y + a.h, b.y + b.h)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    p = (x1 - x0) * (y1 - y0)
    return p / (a.w * a.h + b.w * b.h - p)


@dataclass
class WynikGlosowania:
    slowa: list[ow.Slowo]
    baza: str
    zmiany: int = 0           # słowa wzięte z innego silnika niż baza
    niejednoznaczne: int = 0  # kilka różnych form słownikowych, rozstrzygał kontekst
    dodane: int = 0           # słowa, których baza w ogóle nie widziała
    jezyki: Counter = field(default_factory=Counter)  # język wybranej formy słownikowej

    @property
    def tekst(self) -> str:
        return ow.tekst(self.slowa)


def glosuj(kandydaci: dict[str, list[ow.Slowo]], slowniki: dict[str, Slownik]) -> WynikGlosowania:
    """`kandydaci[kod]` = słowa odczytane silnikiem języka `kod`; zwraca jeden tekst z najlepszych form.

    Kolejność czytania i wiersze daje BAZA: silnik z największą liczbą form słownikowych
    we własnym języku. Każde słowo bazy dostaje kandydatów z innych silników (ta sama ramka,
    IoU > PROG_IOU), a wybór idzie tak:
    1. dokładnie jedna forma słownikowa (we własnym języku silnika, który ją odczytał) → ona;
    2. kilka różnych → język najbliższych jednoznacznych sąsiadów w wierszu (lewy i prawy;
       gdy się różnią — większość wiersza);
    3. żadnej (nazwa własna, liczba, forma spoza leksykonu) → odczyt silnika języka, który
       przeważa w wierszu; bez takiego języka → baza.
    Słowa, których baza nie odczytała wcale, a inny silnik odczytał jako formę słownikową,
    dochodzą do wiersza bazy, z którym najbardziej nachodzą pionowo (bez tego brakowałoby
    słów widzianych tylko przez easyocr).
    """
    kody = [k for k in kandydaci if k in slowniki]
    if not kody:
        return WynikGlosowania([], "")
    ocena = {k: sum(1 for s in kandydaci[k] if slowniki[k].ocen(s.tekst)) for k in kody}
    baza = max(kody, key=lambda k: (ocena[k], len(kandydaci[k])))

    uzyte: dict[str, set[int]] = {k: set() for k in kody}
    pozycje = []  # (słowo bazy, {kod: słowo}, {forma: {kody}})
    for s in kandydaci[baza]:
        warianty = {baza: s}
        for k in kody:
            if k == baza:
                continue
            najl, idx = None, -1
            for i, w in enumerate(kandydaci[k]):
                if i in uzyte[k]:
                    continue
                v = _iou(s, w)
                if v > PROG_IOU and (najl is None or v > _iou(s, najl)):
                    najl, idx = w, i
            if najl is not None:
                warianty[k] = najl
                uzyte[k].add(idx)
        wazne: dict[str, set[str]] = {}
        for k, w in warianty.items():
            if slowniki[k].ocen(w.tekst):
                wazne.setdefault(w.tekst, set()).add(k)
        pozycje.append((s, warianty, wazne))

    def jednoznaczny(p) -> Optional[str]:
        wazne = p[2]
        if len(wazne) == 1:
            js = next(iter(wazne.values()))
            return next(iter(js)) if len(js) == 1 else None
        return None

    jez = [jednoznaczny(p) for p in pozycje]
    wiersz_jez: dict[int, Counter] = {}
    for p, j in zip(pozycje, jez):
        if j:
            wiersz_jez.setdefault(p[0].linia, Counter())[j] += 1

    def przewaga(linia: int) -> Optional[str]:
        c = wiersz_jez.get(linia)
        if not c:
            return None
        (pierwszy, n1), *reszta = c.most_common(2)
        return None if reszta and reszta[0][1] == n1 else pierwszy

    def sasiad(i: int, krok: int) -> Optional[str]:
        linia = pozycje[i][0].linia
        k = i + krok
        while 0 <= k < len(pozycje) and pozycje[k][0].linia == linia:
            if jez[k]:
                return jez[k]
            k += krok
        return None

    wynik = WynikGlosowania([], baza)
    for i, (s, warianty, wazne) in enumerate(pozycje):
        if len(wazne) == 1:
            forma = next(iter(wazne))
            wynik.jezyki[next(iter(wazne[forma]))] += 1
        elif len(wazne) > 1:
            wynik.niejednoznaczne += 1
            lewy, prawy = sasiad(i, -1), sasiad(i, 1)
            kontekst = lewy if lewy == prawy or not prawy else (prawy if not lewy else przewaga(s.linia))
            pasujace = [f for f, js in wazne.items() if kontekst in js]
            forma = pasujace[0] if pasujace else (s.tekst if s.tekst in wazne else next(iter(wazne)))
            wynik.jezyki[kontekst or next(iter(wazne[forma]))] += 1
        else:
            j = przewaga(s.linia)
            forma = warianty[j].tekst if j in warianty else s.tekst
        wynik.zmiany += forma != s.tekst
        wynik.slowa.append(ow.Slowo(s.linia, forma, s.x, s.y, s.w, s.h))

    # Słowa spoza bazy: tylko formy słownikowe, jedna na miejsce (pierwszy silnik wygrywa).
    dodatki: list[ow.Slowo] = []
    for k in kody:
        if k == baza:
            continue
        for i, w in enumerate(kandydaci[k]):
            if i in uzyte[k] or not slowniki[k].ocen(w.tekst):
                continue
            if any(_iou(w, d) > PROG_IOU for d in dodatki) or any(_iou(w, b) > PROG_IOU for b in wynik.slowa):
                continue
            najl_linia, najl_pokrycie = None, 0.0
            for b in wynik.slowa:
                pokrycie = min(w.y + w.h, b.y + b.h) - max(w.y, b.y)
                if pokrycie > najl_pokrycie:
                    najl_linia, najl_pokrycie = b.linia, pokrycie
            if najl_linia is None or najl_pokrycie < 0.5 * w.h:
                continue  # bez wiersza bazy nie wiadomo, gdzie to wstawić — nie zgadujemy kolejności
            dodatki.append(ow.Slowo(najl_linia, w.tekst, w.x, w.y, w.w, w.h))
            wynik.jezyki[k] += 1
    if dodatki:
        wynik.dodane = len(dodatki)
        kolejnosc = _kolejnosc_linii(wynik.slowa)
        wynik.slowa = sorted(wynik.slowa + dodatki, key=lambda s: (kolejnosc[s.linia], s.x))
    return wynik


def _kolejnosc_linii(slowa: list[ow.Slowo]) -> dict[int, int]:
    kolejnosc: dict[int, int] = {}
    for s in slowa:
        kolejnosc.setdefault(s.linia, len(kolejnosc))
    return kolejnosc


# ---------------------------------------------------------------- całość


def odczytaj(obraz, kody: list[str], plan: Optional[PlanOcr] = None) -> WynikGlosowania:
    """Strona (PIL.Image) czytana silnikami wszystkich `kody` i złożona głosowaniem.

    `plan` z `zaplanuj` warto policzyć raz na dokument (słowniki ładują się sekundami);
    bez niego `zaplanuj` rzuca `BladGlosowania`, gdy któryś język nie może głosować.
    """
    plan = plan or zaplanuj(kody)
    kandydaci: dict[str, list[ow.Slowo]] = {}
    if plan.windows:
        w = ow.rozpoznaj(obraz, list(plan.windows.values()))
        if w.bez_silnika:  # silnik zniknął między planem a odczytem (np. odinstalowany pakiet)
            raise BladGlosowania([Problem(k, "brak_silnika", f"Windows nie ma silnika {t}")
                                  for k, t in plan.windows.items() if t in w.bez_silnika])
        for kod, tag in plan.windows.items():
            kandydaci[kod] = w.slowa[tag]
    for kod in plan.easyocr:
        kandydaci[kod] = slowa_easyocr(obraz, kod)
    return glosuj(kandydaci, plan.slowniki)
