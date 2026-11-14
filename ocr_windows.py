"""ocr_windows.py – OCR wbudowany w Windows (Windows.Media.Ocr) przez pywinrt.

Krok 1 migracji OCR (plan 2026-11-13): warstwa dostępu, bez głosowania i bez
podpięcia do notatnika. Zastępuje easyocr tam, gdzie Windows ma silnik języka;
easyocr zostaje członkiem głosowania dla języków bez silnika (islandzki).

Zmierzone 2026-11-13, przed napisaniem modułu:
- silnik `fi` trafia 99–100% słów fińskiego tekstu i zachowuje wszystkie ä/ö,
  a easyocr gubi wszystkie ä/ö (żadna konfiguracja easyocr nie ma `fi`);
- 50–300 ms na stronę na silnik, około 50 razy szybciej niż easyocr na CPU;
- jeden silnik = jeden język: dokument mieszany wymaga kilku przebiegów
  i głosowania (krok 2), dlatego `rozpoznaj` przyjmuje LISTĘ języków i dekoduje
  obraz raz;
- pywinrt i PowerShell (WinRT z Windows PowerShell 5.1) zwracają identyczne
  słowa i ramki; pywinrt jest szybszy (0,7 s zamiast 1,9 s na 4 języki) i działa
  w procesie, bez plików tymczasowych.

Pakiety OCR Windows instaluje system (Ustawienia > Język albo
`Add-WindowsCapability`, z uprawnieniami administratora); brak `is-IS` w katalogu
Windows to fakt (35 pakietów, 2026-11-13). Stan `InstallPending` wymaga restartu.

Zero ciszy: brak pywinrt albo nie-Windows => `OcrNiedostepny`; język bez silnika
=> trafia do `WynikOcr.bez_silnika`, nigdy nie znika bez śladu.
"""

from __future__ import annotations

import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import lru_cache

from ciecie_stron import pasy, wlasciciel

# Zakładka pasa jako ułamek limitu (10000 px => 300 px). Wiersz tekstu po renderze
# ×2 ma około 40–100 px, więc mieści się w połowie zakładki z zapasem.
ZAKLADKA = 0.03


class OcrNiedostepny(RuntimeError):
    """OCR Windows nie działa w tym środowisku (nie Windows albo brak pakietów pywinrt)."""


@dataclass(frozen=True)
class Slowo:
    """Słowo z ramką we współrzędnych CAŁEGO obrazu; `linia` numeruje wiersze od 0 w kolejności czytania."""

    linia: int
    tekst: str
    x: int
    y: int
    w: int
    h: int


@dataclass
class WynikOcr:
    """`slowa[tag]` dla każdego języka z silnikiem; `bez_silnika` = języki, których nie dało się odczytać."""

    slowa: dict[str, list[Slowo]] = field(default_factory=dict)
    bez_silnika: list[str] = field(default_factory=list)


def _winrt():
    """Leniwy import projekcji WinRT; tłumaczy każdą przyczynę braku na `OcrNiedostepny`."""
    if sys.platform != "win32":
        raise OcrNiedostepny("Windows.Media.Ocr works only on Windows 10/11")
    try:
        from winrt.windows.globalization import Language
        from winrt.windows.graphics.imaging import BitmapAlphaMode, BitmapPixelFormat, SoftwareBitmap
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.storage.streams import DataWriter
    except ImportError as e:
        raise OcrNiedostepny(
            "pywinrt packages missing (uncomment the winrt-* lines in requirements.txt "
            f"and run pip install -r requirements.txt): {e}"
        ) from e
    return Language, BitmapAlphaMode, BitmapPixelFormat, SoftwareBitmap, OcrEngine, DataWriter


def dostepne_jezyki() -> list[str]:
    """Tagi BCP-47 zainstalowanych silników, np. `['de-DE', 'en-US', 'fi', 'pl', …]`."""
    OcrEngine = _winrt()[4]
    return [j.language_tag for j in OcrEngine.available_recognizer_languages]


def maks_wymiar() -> int:
    """Limit boku obrazu przyjmowanego przez silnik (10000 px w Windows 11, 2026-11-13)."""
    return int(_winrt()[4].max_image_dimension)


@lru_cache(maxsize=None)
def _silnik(tag: str):
    """Silnik języka albo None. `pl-PL` z `podstawy.yaml::locale` trafia w zainstalowany `pl`."""
    Language, _, _, _, OcrEngine, _ = _winrt()
    try:
        jezyk = Language(tag)
    except Exception:
        return None
    if not OcrEngine.is_language_supported(jezyk):
        return None
    return OcrEngine.try_create_from_language(jezyk)


def silnik_dostepny(tag: str) -> bool:
    return _silnik(tag) is not None


def _bitmapa(obraz):
    """PIL.Image -> SoftwareBitmap Bgra8, w pamięci."""
    _, BitmapAlphaMode, BitmapPixelFormat, SoftwareBitmap, _, DataWriter = _winrt()
    pisarz = DataWriter()
    pisarz.write_bytes(obraz.convert("RGBA").tobytes("raw", "BGRA"))
    return SoftwareBitmap.create_copy_from_buffer(
        pisarz.detach_buffer(), BitmapPixelFormat.BGRA8, obraz.width, obraz.height, BitmapAlphaMode.PREMULTIPLIED
    )


async def _rozpoznaj_bitmape(bmp, silniki: dict) -> dict[str, list[tuple[int, str, float, float, float, float]]]:
    wynik = {}
    for tag, silnik in silniki.items():
        r = await silnik.recognize_async(bmp)
        slowa = []
        for nr, linia in enumerate(r.lines):
            for s in linia.words:
                b = s.bounding_rect
                slowa.append((nr, s.text, b.x, b.y, b.width, b.height))
        wynik[tag] = slowa
    return wynik


def _uruchom(korutyna):
    """`asyncio.run` także z wnętrza działającej pętli (kernel Jupytera ma własną)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(korutyna)
    with ThreadPoolExecutor(max_workers=1) as wykonawca:
        return wykonawca.submit(asyncio.run, korutyna).result()


def rozpoznaj(obraz, tagi: list[str]) -> WynikOcr:
    """Rozpoznaje `obraz` (PIL.Image) silnikiem każdego języka z `tagi`.

    Obraz szerszy niż limit jest zmniejszany proporcjonalnie (ramki wracają do skali
    oryginału); wyższy niż limit jest cięty na pasy z zakładką, a słowo ze strefy
    zakładki zostaje tylko z pasa, który jest właścicielem jego środka.
    """
    from PIL import Image

    wynik = WynikOcr()
    silniki = {}
    for tag in tagi:
        s = _silnik(tag)
        if s is None:
            wynik.bez_silnika.append(tag)
        else:
            silniki[tag] = s
    if not silniki:
        return wynik

    limit = maks_wymiar()
    skala = 1.0
    if obraz.width > limit:
        skala = limit / obraz.width
        obraz = obraz.resize((limit, max(1, round(obraz.height * skala))), Image.LANCZOS)
    podzial = pasy(obraz.height, limit, limit * ZAKLADKA)

    zebrane: dict[str, list[Slowo]] = {tag: [] for tag in silniki}
    nastepna_linia = dict.fromkeys(silniki, 0)
    for i, p in enumerate(podzial):
        y0 = int(p.poczatek)
        wycinek = obraz.crop((0, y0, obraz.width, int(round(p.koniec))))
        surowe = _uruchom(_rozpoznaj_bitmape(_bitmapa(wycinek), silniki))
        for tag, slowa in surowe.items():
            mapa_linii: dict[int, int] = {}
            for nr, tekst, x, y, w, h in slowa:
                if wlasciciel(podzial, y0 + y + h / 2) != i:
                    continue
                if nr not in mapa_linii:
                    mapa_linii[nr] = nastepna_linia[tag]
                    nastepna_linia[tag] += 1
                zebrane[tag].append(Slowo(
                    mapa_linii[nr], tekst,
                    round(x / skala), round((y0 + y) / skala), round(w / skala), round(h / skala),
                ))
    wynik.slowa = zebrane
    return wynik


def tekst(slowa: list[Slowo]) -> str:
    """Słowa złożone w wiersze (spacja w wierszu, nowa linia między wierszami)."""
    wiersze: dict[int, list[str]] = {}
    for s in slowa:
        wiersze.setdefault(s.linia, []).append(s.tekst)
    return "\n".join(" ".join(w) for _, w in sorted(wiersze.items()))
