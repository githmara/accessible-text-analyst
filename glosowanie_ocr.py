"""glosowanie_ocr.py – OCR wielojęzyczny: każdy język czyta swój silnik, słowa wybiera słownik.

Krok 2 migracji OCR (plan 2026-11-13). Silnik OCR zna jeden język naraz: polski
silnik zamienia fińskie ä na ă/i, fiński gubi ą/ę/ł, rosyjski wstawia cyrylicę
w łacińskie słowa (zmierzone na polsko-fińskim slajdzie). Dlatego stronę czyta
silnik KAŻDEGO języka korpusu, a z każdego wyniku bierzemy możliwie najwięcej form
słownikowych.

Członkowie głosowania (decyzje maintainera 2026-11-13):
- silnik Windows (`ocr_windows`) dla języka, który go ma (dziś 8 z 9 języków
  Reżysera; `podstawy.yaml::locale` wskazuje silnik);
- Tesseract (tessdata_best) dla języka bez silnika Windows (islandzki) — zastąpił easyocr
  2026-11-14: na zdegradowanych stronach is 0,80-0,95 wobec 0,01-0,08, bez torch;
- RapidOCR (PP-OCRv6 dla łacinki, v5 eslav dla cyrylicy) dla KAŻDEGO języka, który model
  obejmuje — zapas, którego fiński nie miał (easyocr nie zna fi); na zdjęciach stron
  około dwa razy więcej słów słownikowych niż easyocr.
Brak któregokolwiek członka to BŁĄD (D1): naprawą jest zmiana `corpus_languages` albo
instalacja składników. Obietnicę offline OCR skanów i zdjęć daje szablon kontaktowy
Reżysera, więc kryteria bramki z planu migracji są obowiązkiem.

Słowniki języków żyją w `slowniki_jezykow.py` (od ATA 2.0 wspólne z tagowaniem
odcinków językowych w notatniku i w raporcie); ten moduł je reeksportuje.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Optional

import ocr_windows as ow
from shamanic_locale import PODSTAWY
from slowniki_jezykow import (AUTOMATY_OMORFI, UZNANIE_BIN, Slownik,  # noqa: F401 (API modułu)
                              _alfabet, _rdzen, slownik)

KATALOG = Path(__file__).resolve().parent
PROG_IOU = 0.4  # zmierzone w prototypie: ramki tego samego słowa z różnych silników mają IoU ≈ 1,0
PROG_PODOBIENSTWA = 0.6  # tekst „tego samego słowa” przy ramkach szacowanych z segmentów (_to_samo_slowo)
_LITERY = re.compile(r"[^\W\d_]+", re.UNICODE)


@dataclass(frozen=True)
class Problem:
    """Język, którego nie da się włączyć do głosowania. `przyczyna`: `nieznany_jezyk`, `brak_silnika`
    albo `brak_slownika`; `szczegol` po angielsku (techniczny, z poleceniem naprawy) — notatnik
    dokłada nagłówek we własnym języku."""

    kod: str
    przyczyna: str
    szczegol: str


class BladGlosowania(RuntimeError):
    """Co najmniej jeden język z konfiguracji nie może głosować; naprawa: zmienić `corpus_languages` albo doinstalować."""

    def __init__(self, problemy: list[Problem]):
        self.problemy = problemy
        super().__init__("; ".join(f"{p.kod}: {p.przyczyna} ({p.szczegol})" for p in problemy))


# ---------------------------------------------------------------- silniki


@dataclass
class PlanOcr:
    """Kto czyta który język. `windows[kod]` = tag silnika Windows; `tesseract` = kody czytane
    Tesseractem (języki bez silnika Windows); `rapid[model]` = kody, pod którymi głosuje JEDEN
    odczyt RapidOCR tym modelem (model wielojęzyczny czyta stronę raz, a każdy język ocenia
    ten odczyt własnym słownikiem)."""

    windows: dict[str, str] = field(default_factory=dict)
    tesseract: list[str] = field(default_factory=list)
    rapid: dict[str, list[str]] = field(default_factory=dict)
    slowniki: dict[str, Slownik] = field(default_factory=dict)


KATALOG_TESSDATA = KATALOG / "tessdata"
URL_TESSDATA = "https://github.com/tesseract-ocr/tessdata_best/raw/main/{plik}"
MODEL_RAPID_LACINKA = "v6"     # PP-OCRv6 small, wielojęzyczny (domyślny model RapidOCR 3.10)
MODEL_RAPID_CYRYLICA = "eslav"  # PP-OCRv5 mobile, wschodniosłowiański (v6 nie ma cyrylicy)
POLECENIE_PIP = "uncomment it in requirements.txt and run pip install -r requirements.txt"


def _kod_tesseract(kod: str) -> str:
    """Nazwa modelu Tesseracta = pole `iso639_3` podstaw (is -> isl)."""
    return PODSTAWY[kod]["iso639_3"]


def _tessdata() -> Path:
    zmienna = os.environ.get("TESSDATA_PREFIX")
    return Path(zmienna) if zmienna else KATALOG_TESSDATA


def _problem_tesseracta(kod: str) -> Optional[str]:
    """None, gdy Tesseract może czytać język; inaczej opis naprawy."""
    try:
        import tesserocr  # noqa: F401
    except ImportError:
        return "tesserocr not installed: " + POLECENIE_PIP
    plik = f"{_kod_tesseract(kod)}.traineddata"
    if not (_tessdata() / plik).is_file():
        return f"Tesseract model {plik} missing in {_tessdata()}: download {URL_TESSDATA.format(plik=plik)}"
    return None


@lru_cache(maxsize=1)
def _jezyki_rapid_lacinka() -> frozenset:
    """Języki modelu v6 wg default_models.yaml pakietu rapidocr — źródłem listy jest pakiet, nie ten plik."""
    import rapidocr
    import yaml

    dane = yaml.safe_load((Path(rapidocr.__file__).parent / "default_models.yaml").read_text(encoding="utf-8"))
    return frozenset(dane["model_routes"]["_defs"]["ppocrv6_langs"])


def _model_rapid(kod: str) -> Optional[str]:
    """Model RapidOCR obejmujący język albo None; ImportError, gdy rapidocr nie jest zainstalowany."""
    import detektor_pism

    if any(detektor_pism.pismo_znaku(c) == detektor_pism.CYRYLICA for c in PODSTAWY[kod]["alfabet"]):
        return MODEL_RAPID_CYRYLICA
    return MODEL_RAPID_LACINKA if kod in _jezyki_rapid_lacinka() else None


def zaplanuj(kody: list[str]) -> PlanOcr:
    """Przypisuje każdemu językowi silniki i słownik albo zbiera WSZYSTKIE problemy w jeden `BladGlosowania`."""
    plan, problemy = PlanOcr(), []
    try:
        ow.dostepne_jezyki()
        windows_dziala, powod_windows = True, ""
    except ow.OcrNiedostepny as e:
        windows_dziala, powod_windows = False, str(e)
    for kod in kody:
        if kod not in PODSTAWY:
            problemy.append(Problem(kod, "nieznany_jezyk", "supported: " + ", ".join(sorted(PODSTAWY))))
            continue
        tag = PODSTAWY[kod]["locale"]
        if windows_dziala and ow.silnik_dostepny(tag):
            plan.windows[kod] = tag
        else:
            brak_t = _problem_tesseracta(kod)
            if brak_t is not None:
                brak = ("Windows OCR unavailable: " + powod_windows) if not windows_dziala else \
                    (f"Windows has no OCR engine for {tag} (Settings > Time & language > Language & region: "
                     "add the language with the optical character recognition feature)")
                problemy.append(Problem(kod, "brak_silnika", f"{brak}; {brak_t}"))
                continue
            plan.tesseract.append(kod)
        # RapidOCR: drugi członek każdego języka, który jego model obejmuje — zapas na strony,
        # na których silnik języka zawodzi (zdjęcia, giloszowane tło, fiński bez easyocr; pomiar
        # 2026-11-14). Wymagany jak reszta: obietnicę offline OCR daje szablon kontaktowy Reżysera.
        try:
            model = _model_rapid(kod)
        except ImportError:
            problemy.append(Problem(kod, "brak_silnika", "rapidocr not installed: " + POLECENIE_PIP))
            continue
        if model:
            plan.rapid.setdefault(model, []).append(kod)
        try:
            plan.slowniki[kod] = slownik(kod)
        except LookupError as e:
            problemy.append(Problem(kod, "brak_slownika", str(e)))
    if problemy:
        raise BladGlosowania(problemy)
    return plan


def _powieksz(obraz):
    """Ta sama reguła małego obrazu co w ocr_windows (Tesseract też czyta drobny druk słabo)."""
    from PIL import Image

    s = ow.MIN_DLUZSZY_BOK / max(obraz.size)
    if s <= 1:
        return obraz, 1.0
    return obraz.resize((round(obraz.width * s), round(obraz.height * s)), Image.LANCZOS), s


@lru_cache(maxsize=None)
def _tesseract(kod: str):
    import tesserocr

    return tesserocr.PyTessBaseAPI(path=str(_tessdata()), lang=_kod_tesseract(kod))


def slowa_tesseract(obraz, kod: str) -> list[ow.Slowo]:
    import tesserocr

    api = _tesseract(kod)
    o, s = _powieksz(obraz.convert("RGB"))
    api.SetImage(o)
    api.Recognize()
    wynik, linia, it, ril = [], -1, api.GetIterator(), tesserocr.RIL
    while True:
        if not it.Empty(ril.WORD):
            if it.IsAtBeginningOf(ril.TEXTLINE):
                linia += 1
            tekst, ramka = it.GetUTF8Text(ril.WORD), it.BoundingBox(ril.WORD)
            if tekst and tekst.strip() and ramka:
                x0, y0, x1, y1 = ramka
                wynik.append(ow.Slowo(max(linia, 0), tekst.strip(), round(x0 / s), round(y0 / s),
                                      round((x1 - x0) / s), round((y1 - y0) / s)))
        if not it.Next(ril.WORD):
            break
    return wynik


@lru_cache(maxsize=None)
def _czytnik_rapid(model: str):
    from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR

    # RapidOCR loguje z kolorami ANSI (każde ładowanie i pobranie modelu) — w wyjściu notatnika
    # czytanym przez NVDA to śmieci (pomiar 2026-11-14: 20 linii na przebieg). Poziom loggera
    # konstruktor nadpisuje wartością Global.log_level, więc ustawiamy go TU, nie przez logging;
    # błąd i tak kończy się wyjątkiem.
    parametry = {"Global.log_level": "critical"}
    if model == MODEL_RAPID_CYRYLICA:
        parametry.update({"Rec.lang_type": LangRec.ESLAV, "Rec.ocr_version": OCRVersion.PPOCRV5,
                          "Rec.model_type": ModelType.MOBILE})
    return RapidOCR(params=parametry)


def rozgrzej(plan: PlanOcr) -> None:
    """Ładuje modele RapidOCR (pierwsze użycie pobiera je z sieci) i Tesseracta raz, przy planie —
    inaczej pierwsza strona dokumentu niesie kilka sekund ładowania (zdjęcie: 8,6 s zamiast 2 s)."""
    import numpy as np
    from PIL import Image, ImageDraw

    probka = Image.new("RGB", (240, 60), "white")
    ImageDraw.Draw(probka).text((10, 20), "OCR 2026", fill="black")
    for model in plan.rapid:
        # Tekst na próbce, bo model rozpoznawania ładuje się dopiero przy pierwszej znalezionej ramce.
        _czytnik_rapid(model)(np.array(probka.resize((480, 120))))
    for kod in plan.tesseract:
        _tesseract(kod)


def _segmenty_rapid(obraz, model: str) -> list:
    """Surowe segmenty RapidOCR (ramka, tekst, pewność). numpy importowany dopiero tu — testy
    modułu idą na runnerze CI bez niego."""
    import numpy as np

    r = _czytnik_rapid(model)(np.array(obraz.convert("RGB")))
    return [] if r.boxes is None else list(zip(r.boxes, r.txts, r.scores))


def slowa_rapid(obraz, model: str) -> list[ow.Slowo]:
    return _slowa_z_segmentow(_segmenty_rapid(obraz, model))


def _slowa_z_segmentow(surowe: list) -> list[ow.Slowo]:
    """RapidOCR zwraca SEGMENTY (kilka słów w jednej ramce): dzielimy je na słowa proporcjonalnie
    do liczby znaków, a segmenty o pokrywających się pionowo ramkach składamy w wiersze."""
    segmenty = []
    for ramka, tekst, _pewnosc in surowe:
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


def _to_samo_slowo(a: ow.Slowo, b: ow.Slowo) -> bool:
    """To samo słowo w tym samym miejscu, także gdy ramki mają różny kształt: silniki czytające
    SEGMENTY (RapidOCR) dzielą je na słowa proporcjonalnie do znaków, więc ich ramka bywa
    przesunięta wobec ramki z Windows i IoU spada poniżej progu — bez tego testu to samo słowo
    trafiało do tekstu dwa razy („THE THE”, pomiar 2026-11-14). Samo nachodzenie ramek nie
    wystarcza (łapało sąsiada: Calibri d0 0,969 -> 0,938), więc tekst musi być podobny."""
    if _iou(a, b) > PROG_IOU:
        return True
    pion = min(a.y + a.h, b.y + b.h) - max(a.y, b.y)
    poziom = min(a.x + a.w, b.x + b.w) - max(a.x, b.x)
    if pion < 0.5 * min(a.h, b.h) or poziom < 0.3 * min(a.w, b.w):
        return False
    return SequenceMatcher(None, a.tekst.lower(), b.tekst.lower()).ratio() >= PROG_PODOBIENSTWA


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


def glosuj(kandydaci: dict[str, list[ow.Slowo]], slowniki: dict[str, Slownik],
           kolejnosc: str = "silnik") -> WynikGlosowania:
    """`kandydaci[kod]` = słowa odczytane silnikiem języka `kod` (klucz `kod@silnik` = silnik
    wielojęzyczny oceniany słownikiem `kod`); zwraca jeden tekst z najlepszych form.

    Kolejność czytania i wiersze daje BAZA: silnik z największą liczbą form słownikowych
    we własnym języku (`kolejnosc="wiersze"` przestawia wynik na wiersze wizualne strony).
    Każde słowo bazy dostaje kandydatów z innych silników (`_to_samo_slowo`), a wybór idzie tak:
    1. dokładnie jedna forma słownikowa (we własnym języku silnika, który ją odczytał) → ona;
    2. kilka różnych → ta, którą odczytało najwięcej RÓŻNYCH silników; przy remisie język
       najbliższych jednoznacznych sąsiadów w wierszu (lewy i prawy; gdy się różnią —
       większość wiersza);
    3. żadnej (nazwa własna, liczba, forma spoza leksykonu) → odczyt silnika języka, który
       przeważa w wierszu; bez takiego języka → baza.
    Słowa, których baza nie odczytała wcale, a inny silnik odczytał jako formę słownikową,
    dochodzą do wiersza bazy, z którym najbardziej nachodzą pionowo (bez tego brakowałoby
    słów widzianych tylko przez jeden silnik, np. islandzkich þ/ð).
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
                # Para = to samo słowo (_to_samo_slowo), nie tylko IoU > PROG_IOU: ramki słów
                # z segmentów są szacowane. Z kilku kandydatów wygrywa największe IoU.
                if not _to_samo_slowo(s, w):
                    continue
                if najl is None or _iou(s, w) > _iou(s, najl):
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
        elif len(wazne) > 1 and (lider := _wiekszosc_silnikow(wazne)):
            # Kilka form słownikowych, ale jedną odczytało więcej RÓŻNYCH silników: „Mitä” (silnik
            # fi i RapidOCR) wygrywa z „Miła” (tylko silnik pl), zanim zdecyduje sąsiedztwo.
            wynik.niejednoznaczne += 1
            forma = lider
            wynik.jezyki[_jezyk(next(iter(wazne[forma])))] += 1
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
            if any(_to_samo_slowo(w, d) for d in dodatki) or any(_to_samo_slowo(w, b) for b in wynik.slowa):
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
    if kolejnosc == "wiersze":
        wynik.slowa = _wiersze_wizualne(wynik.slowa)
    return wynik


def _wiersze_wizualne(slowa: list[ow.Slowo]) -> list[ow.Slowo]:
    """Tryb `kolejnosc="wiersze"` (opt-in): czytanie wierszami wizualnymi strony, od góry, w wierszu
    od lewej. Linie silnika, których środki leżą na tej samej wysokości, łączą się w jeden wiersz.

    Domyślna jest kolejność silnika: Windows czyta bloki, które uzna za kolumny, więc tabelę
    czyta kolumnami, ale prozy w kolumnach (karty slajdu) nie przeplata. Pomiar 2026-11-14:
    wiersze podnoszą tabelę workbooka s14 z 0,755 do 0,859, ale przeplatają karty Notatnika
    s12 (0,565 -> 0,536); wykrywanie tabel i akapity w stylu easyocr nie dały wygranej na obu."""
    linie: dict[int, list[ow.Slowo]] = {}
    for s in slowa:
        linie.setdefault(s.linia, []).append(s)
    opis = sorted(((sum(s.y + s.h / 2 for s in ls) / len(ls), max(s.h for s in ls), min(s.x for s in ls), nr)
                   for nr, ls in linie.items()))
    wiersze: list[list[tuple]] = []
    for o in opis:
        if wiersze:
            ost = wiersze[-1]
            sr = sum(x[0] for x in ost) / len(ost)
            if abs(o[0] - sr) < 0.5 * max(max(x[1] for x in ost), o[1]):
                ost.append(o)
                continue
        wiersze.append([o])
    wynik = []
    for nr, w in enumerate(wiersze):
        for s in sorted((s for o in w for s in linie[o[3]]), key=lambda s: s.x):
            wynik.append(ow.Slowo(nr, s.tekst, s.x, s.y, s.w, s.h))
    return wynik


def _silnik_klucza(klucz: str) -> str:
    """Klucz kandydata `kod` = silnik języka `kod` (Windows albo Tesseract); `kod@silnik` = jeden
    silnik wielojęzyczny (RapidOCR) wpisany pod każdym językiem ze słownikiem tego języka."""
    return klucz.split("@", 1)[1] if "@" in klucz else klucz


def _jezyk(klucz: str) -> str:
    return klucz.split("@", 1)[0]


def _wiekszosc_silnikow(wazne: dict[str, set[str]]) -> Optional[str]:
    """Forma odczytana przez najwięcej różnych silników albo None przy remisie."""
    poparcie = sorted(((len({_silnik_klucza(k) for k in ks}), f) for f, ks in wazne.items()), reverse=True)
    return poparcie[0][1] if poparcie[0][0] > poparcie[1][0] else None


def _kolejnosc_linii(slowa: list[ow.Slowo]) -> dict[int, int]:
    kolejnosc: dict[int, int] = {}
    for s in slowa:
        kolejnosc.setdefault(s.linia, len(kolejnosc))
    return kolejnosc


# ---------------------------------------------------------------- całość


def odczytaj(obraz, kody: list[str], plan: Optional[PlanOcr] = None, kolejnosc: str = "silnik") -> WynikGlosowania:
    """Strona (PIL.Image) czytana silnikami wszystkich `kody` i złożona głosowaniem.

    `plan` z `zaplanuj` warto policzyć raz na dokument (słowniki ładują się sekundami);
    bez niego `zaplanuj` rzuca `BladGlosowania`, gdy któryś język nie może głosować.
    """
    plan = plan or zaplanuj(kody)
    kandydaci: dict[str, list[ow.Slowo]] = {}
    if plan.windows:
        w = ow.rozpoznaj(obraz, list(plan.windows.values()))
        if w.bez_silnika:  # silnik zniknął między planem a odczytem (np. odinstalowany pakiet)
            raise BladGlosowania([Problem(k, "brak_silnika", f"Windows OCR engine {t} disappeared during the run")
                                  for k, t in plan.windows.items() if t in w.bez_silnika])
        for kod, tag in plan.windows.items():
            kandydaci[kod] = w.slowa[tag]
    for kod in plan.tesseract:
        kandydaci[kod] = slowa_tesseract(obraz, kod)
    slowniki = dict(plan.slowniki)
    for model, kody_modelu in plan.rapid.items():
        slowa = slowa_rapid(obraz, model)
        for kod in kody_modelu:
            kandydaci[f"{kod}@rapid"], slowniki[f"{kod}@rapid"] = slowa, plan.slowniki[kod]
    return glosuj(kandydaci, slowniki, kolejnosc)
