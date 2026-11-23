"""docx_tresc.py — treść pliku .docx w KOLEJNOŚCI DOKUMENTU: akapity, komórki
tabel, pola tekstowe i obrazy.

DLACZEGO (2026-11-22). `load_docx` czytał tylko `doc.paragraphs`, więc po cichu
gubił tabele i obrazy wstawione w dokument. Zmierzone na prezentacji złożonej
z 46 wycinków slajdów (PNG RGBA, bez tekstu alternatywnego): z całego pliku
zostawało jedno zdanie. Decyzja użytkownika z 2026-11-22: „ATA więc ma czytać
OCR bo inaczej projekt nie byłby tym, czym się nazywa” — obrazy idą przez ten
sam OCR co skany PDF (`glosowanie_ocr`), offline.

WSPÓLNA POLITYKA z bliźniakiem w Reżyserze (`core_poliglota.elementy_docx`,
audyt 2.2.0, decyzja użytkownika „Tak, oba”, 2026-11-23):
1. Pola tekstowe (`w:txbxContent`, także w VML; kopia w `mc:Fallback` liczona
   raz) czytane W MIEJSCU: zaraz po akapicie, w którym stoją, z ich obrazami.
   Obiekty akapitu (obrazy, pola, wykresy) idą za jego tekstem, w kolejności XML.
2. Nagłówki i stopki NIE wchodzą do treści; wywołujący zgłasza ich liczbę,
   gdy mają tekst albo obrazy (`Wynik.naglowki` / `Wynik.stopki`).
3. Wykresy (`c:chart`) i SmartArt (`dgm:relIds`) nie są czytane; zgłaszane
   z liczbą, a ich tekst alternatywny (`wp:docPr` descr/title) trafia do
   treści w miejscu elementu.
4. Kontrolki treści (`w:sdt`) na każdym poziomie — blok, wiersz i komórka
   tabeli, w akapicie — oraz `w:customXml`: schodzimy do środka.
5. Śledzenie zmian: treść usunięta (`w:del`, `w:moveFrom`) pomijana razem
   z obrazami; wstawiona (`w:ins`, `w:moveTo`) czytana; `w:fldSimple`
   i `w:sdt` w akapicie — tekst czytany.
6. Ten sam obraz (ta sama część pakietu) użyty wielokrotnie: OCR raz, kolejne
   wystąpienia dostają ten sam wynik (`Wynik.powtorki`); tekst powtarza się
   w miejscach wystąpień — to treść dokumentu.
7. Grupa obrazów: każdy obraz osobno; tekst alternatywny = własny
   `pic:cNvPr` descr/title obrazu, a przy jego braku tekst grupy
   (`wp:docPr`) — ten raz na całą grupę, dla pierwszego obrazu bez własnego.

Pozostałe zasady:
- Obraz: `a:blip` (`r:embed`; `r:link` = obraz poza plikiem) albo VML
  `v:imagedata` (`r:id`, dawniej `o:relid`). Relacja zewnętrzna = obraz
  „zewnętrzny”, brak relacji = błąd z numerem; nic nie znika bez liczby.
- Obraz oznaczony jako dekoracyjny (`adec:decorative`) nie daje treści. Obraz
  bez tekstu alternatywnego idzie do OCR.
- OCR jest WSTRZYKIWANY (`ocr(obraz_PIL, nr, k, razem) -> str`: `nr` = numer
  obrazu w dokumencie, `k` = która to próba OCR, `razem` = liczba RÓŻNYCH
  obrazów do OCR): moduł nie zna silników ani języków, notatnik podaje
  `_ocr_obraz`, bramka źródła (`zrodlo_raportu`) nie podaje nic, testy podają
  atrapę. Wyjątek `OcrNiedostepny` z `ocr` = OCR nie może działać wcale;
  pozostałe obrazy trafiają wtedy do `bez_ocr` bez dalszych prób.
- Pillow na Windows otwiera prawdziwe EMF/WMF (jako „WMF”) i rysuje je
  systemowym GDI — takie obrazy idą do OCR, renderowane w wyższej
  rozdzielczości niż domyślne 72 dpi (`_DPI_WMF`). Poza Windows Pillow ich nie
  narysuje: to błąd odczytu z numerem. `format` = tylko bajty, których Pillow
  nie rozpoznaje (`UnidentifiedImageError`); pusty plik i obraz ponad limit
  Pillow mają własne listy.
- Tekst dokumentu (akapity, komórki, pola tekstowe, teksty alternatywne)
  przechodzi przez wspólne czyszczenie `czyszczenie_tekstu.oczysc_akapity_docx`.
  Tekst z OCR — nie (to nie jest tekst zapisany z PDF).

Moduł nie drukuje (bramka printów): raport składa wywołujący z `Wynik`.
"""
from __future__ import annotations

import io
import posixpath
from dataclasses import dataclass, field
from typing import Callable, Optional

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
_PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"
_C = "http://schemas.openxmlformats.org/drawingml/2006/chart"
_DGM = "http://schemas.openxmlformats.org/drawingml/2006/diagram"
_V = "urn:schemas-microsoft-com:vml"
_O = "urn:schemas-microsoft-com:office:office"
_MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
_ADEC = "http://schemas.microsoft.com/office/drawing/2017/decorative"


def _w(nazwa: str) -> str:
    return f"{{{_W}}}{nazwa}"


_P, _TBL, _TR, _TC = _w("p"), _w("tbl"), _w("tr"), _w("tc")
_SDT, _SDT_CONTENT, _CUSTOM_XML = _w("sdt"), _w("sdtContent"), _w("customXml")
_TXBX = _w("txbxContent")
_T, _TAB, _PTAB, _BR, _CR, _NBH = _w("t"), _w("tab"), _w("ptab"), _w("br"), _w("cr"), _w("noBreakHyphen")
_DEL, _MOVE_FROM = _w("del"), _w("moveFrom")
_BLIP = f"{{{_A}}}blip"
_IMAGEDATA = f"{{{_V}}}imagedata"
_FALLBACK = f"{{{_MC}}}Fallback"
_INLINE = f"{{{_WP}}}inline"
_ANCHOR = f"{{{_WP}}}anchor"
_DOCPR = f"{{{_WP}}}docPr"
_PIC_PIC = f"{{{_PIC}}}pic"
_PIC_CNVPR = f"{{{_PIC}}}cNvPr"
_DECORATIVE = f"{{{_ADEC}}}decorative"
_SHAPE = f"{{{_V}}}shape"
_CHART = f"{{{_C}}}chart"
_DGM_RELIDS = f"{{{_DGM}}}relIds"

# Poddrzewa, których treść nie należy do tekstu akapitu: usunięte zmiany,
# kopia zapasowa mc:Fallback, właściwości (w:pPr ma też w:tab — pozycje
# tabulatorów, nie tabulatory), pola tekstowe (czytane osobno, w miejscu).
_POMIJANE = frozenset({_DEL, _MOVE_FROM, _FALLBACK, _w("pPr"), _w("rPr"), _w("sdtPr")})
_POMIJANE_TEKST = _POMIJANE | {_TXBX}
_OBIEKTY = frozenset({_BLIP, _IMAGEDATA, _CHART, _DGM_RELIDS, _TXBX})
_RELACJE_KOLONTYTULOW = {"header": "naglowki", "footer": "stopki"}

#: EMF/WMF rysowane przez GDI: docelowo do 300 dpi, ale dłuższy bok najwyżej
#: tyle pikseli (OCR i tak tnie wyżej, a pamięć rośnie z kwadratem).
_DPI_WMF = 300
_MAKS_BOK_WMF = 4000


class OcrNiedostepny(RuntimeError):
    """Rzucany przez wstrzyknięty `ocr`, gdy OCR nie może działać wcale."""


@dataclass
class Obraz:
    nr: int                      # 1.. w kolejności dokumentu
    nazwa: str = ""              # np. image3.png (nazwa części w pakiecie)
    klucz: str = ""              # pełna nazwa części — ten sam obraz = ten sam klucz
    typ: str = ""                # content type części
    alt: str = ""                # tekst alternatywny (pusty = brak)
    dekoracyjny: bool = False
    zewnetrzny: bool = False     # relacja zewnętrzna — obraz poza plikiem
    blob: Optional[bytes] = None
    blad: str = ""               # brak relacji albo części


@dataclass
class Wynik:
    akapity: list = field(default_factory=list)       # treść w kolejności dokumentu
    czyszczenie: dict = field(default_factory=dict)   # liczniki oczysc_akapity_docx
    obrazy: int = 0
    tabele: int = 0
    komorki: int = 0                                  # komórki z tekstem
    pola_tekstowe: int = 0                            # przeczytane w:txbxContent
    diagramy: int = 0                                 # wykresy + SmartArt (nieczytane)
    diagramy_alt: int = 0                             # ... z tekstem alternatywnym w treści
    naglowki: int = 0                                 # części nagłówków z treścią (nieczytane)
    stopki: int = 0
    z_alt: list = field(default_factory=list)         # numery obrazów
    ocr_ok: list = field(default_factory=list)
    ocr_puste: list = field(default_factory=list)
    powtorki: list = field(default_factory=list)      # [(nr, nr pierwszego wystąpienia)]
    dekoracyjne: list = field(default_factory=list)
    zewnetrzne: list = field(default_factory=list)
    bez_ocr: list = field(default_factory=list)       # OCR niepodany albo niedostępny
    format: list = field(default_factory=list)        # [(nr, rozszerzenie)] — bajty nierozpoznane
    puste_pliki: list = field(default_factory=list)   # obraz o zerowej długości
    za_duze: list = field(default_factory=list)       # [(nr, "SZERxWYS")] ponad limit Pillow
    bledy: list = field(default_factory=list)         # [(nr, komunikat)]
    ocr_niedostepny: str = ""                         # powód z OcrNiedostepny

    @property
    def pominiete(self) -> int:
        return (len(self.zewnetrzne) + len(self.bez_ocr) + len(self.format)
                + len(self.puste_pliki) + len(self.za_duze) + len(self.bledy))


def zakresy(numery) -> str:
    """[1, 2, 3, 7, 9, 10] -> '1-3, 7, 9-10' (numery stron/obrazów do komunikatu)."""
    nums = sorted(set(numery))
    czesci, i = [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        czesci.append(str(nums[i]) if i == j else f"{nums[i]}-{nums[j]}")
        i = j + 1
    return ", ".join(czesci)


def _przejdz(el, pomijane, zatrzymaj=frozenset()):
    """Potomkowie `el` w kolejności dokumentu, bez poddrzew `pomijane`;
    element z `zatrzymaj` jest zwracany, ale bez schodzenia do środka."""
    for dziecko in el:
        tag = dziecko.tag
        if not isinstance(tag, str) or tag in pomijane:
            continue
        yield dziecko
        if tag not in zatrzymaj:
            yield from _przejdz(dziecko, pomijane, zatrzymaj)


def _tekst_akapitu(p) -> str:
    """Tekst akapitu jak `Paragraph.text` w python-docx (w:t, tabulator,
    złamanie wiersza, twardy dywiz), ale z wstawkami śledzenia zmian,
    `w:sdt` i `w:fldSimple`, bez treści usuniętej i bez pól tekstowych."""
    czesci = []
    for x in _przejdz(p, _POMIJANE_TEKST):
        tag = x.tag
        if tag == _T:
            czesci.append(x.text or "")
        elif tag in (_TAB, _PTAB):
            czesci.append("\t")
        elif tag == _CR or (tag == _BR and x.get(_w("type"), "textWrapping") == "textWrapping"):
            czesci.append("\n")   # łamanie strony/kolumny: "" jak w python-docx
        elif tag == _NBH:
            czesci.append("-")
    return "".join(czesci)


def _alt_atrybuty(el) -> str:
    if el is None:
        return ""
    return (el.get("descr") or "").strip() or (el.get("title") or "").strip()


def _dekoracyjny(el) -> bool:
    return el is not None and any((d.get("val") or "").lower() in ("1", "true")
                                  for d in el.iter(_DECORATIVE))


def _kotwica(el):
    for a in el.iterancestors():
        if a.tag in (_INLINE, _ANCHOR):
            return a
    return None


def _alt_drawingml(blip, uzyte_grupy: set) -> tuple[str, bool]:
    """Własny `pic:cNvPr` obrazu, a przy jego braku `wp:docPr` rysunku —
    ten drugi raz na rysunek (grupa: pierwszy obraz bez własnego tekstu)."""
    wlasny = None
    for a in blip.iterancestors():
        if a.tag == _PIC_PIC:
            wlasny = a.find(f".//{_PIC_CNVPR}")
            break
    kotwica = _kotwica(blip)
    pr = kotwica.find(_DOCPR) if kotwica is not None else None
    dek = _dekoracyjny(wlasny) or _dekoracyjny(pr)
    alt = _alt_atrybuty(wlasny)
    if alt:
        return alt, dek
    alt = _alt_atrybuty(pr)
    if alt and kotwica is not None:
        klucz = kotwica.getroottree().getpath(kotwica)
        if klucz in uzyte_grupy:
            return "", dek
        uzyte_grupy.add(klucz)
    return alt, dek


def _alt_vml(imagedata) -> str:
    alt = (imagedata.get(f"{{{_O}}}title") or "").strip()
    for a in imagedata.iterancestors():
        if a.tag == _SHAPE:
            return (a.get("alt") or "").strip() or alt
    return alt


def _rozwiaz(part, ob: Obraz, rid: str) -> None:
    """Relacja `rid` → bajty obrazu; zewnętrzna albo brakująca relacja z numerem."""
    rel = part.rels.get(rid) if hasattr(part, "rels") else None
    if rel is None:
        ob.blad = f"no relationship {rid}"
        return
    if rel.is_external:
        ob.zewnetrzny = True
        return
    czesc = rel.target_part
    ob.klucz = str(czesc.partname)
    ob.nazwa = posixpath.basename(ob.klucz)
    ob.typ = getattr(czesc, "content_type", "")
    ob.blob = czesc.blob


def _obraz(x, part, licznik: list, uzyte_grupy: set) -> Obraz:
    licznik[0] += 1
    if x.tag == _BLIP:
        rid, link = x.get(f"{{{_R}}}embed"), x.get(f"{{{_R}}}link")
        alt, dek = _alt_drawingml(x, uzyte_grupy)
    else:
        rid = x.get(f"{{{_R}}}id") or x.get(f"{{{_O}}}relid")
        link = x.get(f"{{{_O}}}href")   # stary VML: ścieżka do pliku poza dokumentem
        alt, dek = _alt_vml(x), False
    ob = Obraz(nr=licznik[0], alt=alt, dekoracyjny=dek)
    if rid:
        _rozwiaz(part, ob, rid)
    elif link:
        ob.zewnetrzny = True
    else:
        ob.blad = "no relationship id"
    return ob


def elementy(doc) -> tuple[list, dict]:
    """[("tekst", str) | ("obraz", Obraz) | ("diagram", alt)] w kolejności
    dokumentu, plus liczniki: tabele, komórki z tekstem, pola tekstowe."""
    part = doc.part
    wynik: list = []
    licznik = [0]
    uzyte_grupy: set = set()
    stat = {"tabele": 0, "komorki": 0, "pola_tekstowe": 0}

    def akapit(p) -> bool:
        tekst = _tekst_akapitu(p)
        if tekst.strip():
            wynik.append(("tekst", tekst))
        for x in _przejdz(p, _POMIJANE, zatrzymaj={_TXBX}):
            if x.tag not in _OBIEKTY:
                continue
            if x.tag == _TXBX:
                stat["pola_tekstowe"] += 1
                blok(x)
            elif x.tag in (_CHART, _DGM_RELIDS):
                kotwica = _kotwica(x)
                wynik.append(("diagram", _alt_atrybuty(
                    kotwica.find(_DOCPR) if kotwica is not None else None)))
            else:
                wynik.append(("obraz", _obraz(x, part, licznik, uzyte_grupy)))
        return bool(tekst.strip())

    def opakowania(el, tag):
        """Dzieci `el` o znaczniku `tag`, także owinięte w w:sdt / w:customXml."""
        for d in el:
            if d.tag == tag:
                yield d
            elif d.tag == _SDT:
                tresc = d.find(_SDT_CONTENT)
                if tresc is not None:
                    yield from opakowania(tresc, tag)
            elif d.tag == _CUSTOM_XML:
                yield from opakowania(d, tag)

    def blok(kontener) -> bool:
        """True, gdy któryś akapit tego poziomu (bez tabel zagnieżdżonych) ma tekst."""
        ma_tekst = False
        for el in kontener:
            if el.tag == _P:
                ma_tekst |= akapit(el)
            elif el.tag == _TBL:
                stat["tabele"] += 1
                for tr in opakowania(el, _TR):
                    for tc in opakowania(tr, _TC):
                        if blok(tc):
                            stat["komorki"] += 1
            elif el.tag == _SDT:
                tresc = el.find(_SDT_CONTENT)
                if tresc is not None:
                    ma_tekst |= blok(tresc)
            elif el.tag == _CUSTOM_XML:
                ma_tekst |= blok(el)
        return ma_tekst

    blok(doc.element.body)
    return wynik, stat


def kolontytuly(doc) -> dict:
    """Liczba części nagłówków i stopek, które mają tekst albo obraz.
    Do treści nie wchodzą (polityka 2) — wywołujący je zgłasza."""
    wynik = {"naglowki": 0, "stopki": 0}
    for rel in doc.part.rels.values():
        rodzaj = _RELACJE_KOLONTYTULOW.get(rel.reltype.rsplit("/", 1)[-1])
        if rodzaj is None or rel.is_external:
            continue
        el = getattr(rel.target_part, "element", None)
        if el is None:
            continue
        tekst = any((x.text or "").strip() for x in _przejdz(el, _POMIJANE) if x.tag == _T)
        obraz = any(x.tag in (_BLIP, _IMAGEDATA, _CHART, _DGM_RELIDS) for x in _przejdz(el, _POMIJANE))
        if tekst or obraz:
            wynik[rodzaj] += 1
    return wynik


def _na_bialym(obraz):
    """Przezroczystość na białe tło: `convert("RGB")` w silnikach OCR zrzuca
    kanał alfa, a przezroczyste piksele wycinków bywają czarne — tekst znika."""
    from PIL import Image
    if obraz.mode in ("RGBA", "LA") or (obraz.mode == "P" and "transparency" in obraz.info):
        rgba = obraz.convert("RGBA")
        tlo = Image.new("RGB", rgba.size, (255, 255, 255))
        tlo.paste(rgba, mask=rgba.getchannel("A"))
        return tlo
    if obraz.mode not in ("RGB", "L"):
        return obraz.convert("RGB")
    return obraz


def _rozszerzenie(ob: Obraz) -> str:
    ext = posixpath.splitext(ob.nazwa)[1].lstrip(".").upper()
    return ext or (ob.typ.rsplit("/", 1)[-1].upper() if ob.typ else "?")


def _do_ocr(ob: Obraz) -> bool:
    return not (ob.dekoracyjny or ob.alt or ob.zewnetrzny or ob.blad)


def tresc_docx(doc, ocr: Optional[Callable] = None, alfabety=None) -> Wynik:
    """Treść dokumentu python-docx w kolejności dokumentu (patrz docstring modułu)."""
    from czyszczenie_tekstu import oczysc_akapity_docx
    if alfabety is None:
        from shamanic_locale import alfabety_paczek
        alfabety = alfabety_paczek()
    el, stat = elementy(doc)
    w = Wynik(**stat, **kolontytuly(doc))
    razem = len({e[1].klucz for e in el if e[0] == "obraz" and _do_ocr(e[1])})
    pamiec: dict = {}   # klucz części -> (nr pierwszego wystąpienia, tekst)
    # Sloty treści: (czy_tekst_dokumentu, tekst). Czyszczenie idzie na samym
    # tekście dokumentu, a liczba akapitów się nie zmienia, więc wraca na miejsce.
    sloty: list = []
    for e in el:
        if e[0] == "tekst":
            sloty.append([True, e[1]])
            continue
        if e[0] == "diagram":
            w.diagramy += 1
            if e[1]:
                w.diagramy_alt += 1
                sloty.append([True, e[1]])
            continue
        ob = e[1]
        w.obrazy += 1
        if ob.dekoracyjny:
            w.dekoracyjne.append(ob.nr)
        elif ob.alt:
            w.z_alt.append(ob.nr)
            sloty.append([True, ob.alt])
        elif ob.zewnetrzny:
            w.zewnetrzne.append(ob.nr)
        elif ob.blad:
            w.bledy.append((ob.nr, ob.blad))
        elif ob.klucz in pamiec:
            pierwszy, tekst = pamiec[ob.klucz]
            w.powtorki.append((ob.nr, pierwszy))
            if tekst:
                sloty.append([False, tekst])
        elif ocr is None or w.ocr_niedostepny:
            w.bez_ocr.append(ob.nr)
        else:
            tekst = _odczytaj(ob, ocr, w, len(pamiec) + 1, razem)
            if not (w.bez_ocr and w.bez_ocr[-1] == ob.nr):
                pamiec[ob.klucz] = (ob.nr, tekst)
            if tekst:
                w.ocr_ok.append(ob.nr)
                sloty.append([False, tekst])
    teksty = [s[1] for s in sloty if s[0]]
    czyste, w.czyszczenie = oczysc_akapity_docx(teksty, alfabety)
    it = iter(czyste)
    for s in sloty:
        if s[0]:
            s[1] = next(it)
    w.akapity = [s[1] for s in sloty if s[1].strip()]
    return w


def _otworz(ob: Obraz, w: Wynik):
    """Bajty → obraz RGB/L na białym tle albo None (powód zapisany w `w`)."""
    from PIL import Image, UnidentifiedImageError
    if not ob.blob:
        w.puste_pliki.append(ob.nr)
        return None
    try:
        with Image.open(io.BytesIO(ob.blob)) as surowy:
            if surowy.format == "WMF":   # EMF też: Pillow zgłasza oba jako WMF
                bok = max(surowy.size) or 1
                surowy.load(dpi=max(72, min(_DPI_WMF, 72 * _MAKS_BOK_WMF // bok)))
            else:
                surowy.load()
            obraz = _na_bialym(surowy)
            obraz.load()
            return obraz
    except Image.DecompressionBombError:
        w.za_duze.append((ob.nr, _rozmiar(ob.blob)))
    except UnidentifiedImageError:
        w.format.append((ob.nr, _rozszerzenie(ob)))
    except Exception as e:  # noqa: BLE001 — uszkodzony plik, WMF poza Windows: błąd z numerem
        w.bledy.append((ob.nr, f"{type(e).__name__}: {e}"))
    return None


def _rozmiar(blob: bytes) -> str:
    """Wymiary z nagłówka obrazu bez dekodowania (limit Pillow wyłączony na chwilę)."""
    from PIL import Image
    stary = Image.MAX_IMAGE_PIXELS
    try:
        Image.MAX_IMAGE_PIXELS = None
        with Image.open(io.BytesIO(blob)) as im:
            return f"{im.size[0]}x{im.size[1]}"
    except Exception:  # noqa: BLE001
        return "?"
    finally:
        Image.MAX_IMAGE_PIXELS = stary


def _odczytaj(ob: Obraz, ocr: Callable, w: Wynik, k: int, razem: int) -> str:
    obraz = _otworz(ob, w)
    if obraz is None:
        return ""
    try:
        tekst = (ocr(obraz, ob.nr, k, razem) or "").strip()
    except OcrNiedostepny as e:
        w.ocr_niedostepny = str(e) or "OCR unavailable"
        w.bez_ocr.append(ob.nr)
        return ""
    except Exception as e:  # noqa: BLE001 — błąd jednego obrazu nie zatrzymuje dokumentu
        w.bledy.append((ob.nr, f"{type(e).__name__}: {e}"))
        return ""
    if not tekst:
        w.ocr_puste.append(ob.nr)
    return tekst
