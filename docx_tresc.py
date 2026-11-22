"""docx_tresc.py — treść pliku .docx w KOLEJNOŚCI DOKUMENTU: akapity, komórki
tabel i obrazy.

DLACZEGO (2026-11-22). `load_docx` czytał tylko `doc.paragraphs`, więc po cichu
gubił tabele i obrazy wstawione w dokument. Zmierzone na prezentacji złożonej
z 46 wycinków slajdów (PNG RGBA, bez tekstu alternatywnego): z całego pliku
zostawało jedno zdanie. Decyzja użytkownika z 2026-11-22: „ATA więc ma czytać
OCR bo inaczej projekt nie byłby tym, czym się nazywa” — obrazy idą przez ten
sam OCR co skany PDF (`glosowanie_ocr`), offline.

Zasady:
- Kolejność = kolejność elementów w `w:body`: akapit, tabela (wiersz po
  wierszu, komórka po komórce, tabele zagnieżdżone rekurencyjnie), kontrolki
  treści (`w:sdt`). Obrazy akapitu stoją ZA jego tekstem (zwykle obraz ma
  własny, pusty akapit-kotwicę — taki akapit nie daje pustej treści).
- Obraz: `a:blip` (`r:embed`) albo VML `v:imagedata` (`r:id`). Kopia zapasowa
  `mc:Fallback` (VML obok DrawingML tego samego obrazu) jest pomijana, żeby
  obraz nie liczył się dwa razy.
- Tekst alternatywny (`wp:docPr` `descr`, potem `title`; w VML `alt`/`o:title`)
  zastępuje OCR. Obraz oznaczony jako dekoracyjny (`adec:decorative`) nie daje
  treści. Obraz bez tekstu alternatywnego idzie do OCR.
- OCR jest WSTRZYKIWANY (`ocr(obraz_PIL, nr, razem) -> str`): moduł nie zna silników ani
  języków, notatnik podaje `_ocr_obraz`, bramka źródła (`zrodlo_raportu`) nie
  podaje nic, testy podają atrapę. Wyjątek `OcrNiedostepny` z `ocr` = OCR nie
  może działać wcale; pozostałe obrazy trafiają wtedy do `bez_ocr` bez dalszych
  prób. Każdy pominięty obraz jest liczony z numerem — żadnej ciszy.
- Tekst dokumentu (akapity, komórki, teksty alternatywne) przechodzi przez
  wspólne czyszczenie `czyszczenie_tekstu.oczysc_akapity_docx`, jak dotąd
  akapity. Tekst z OCR — nie (to nie jest tekst zapisany z PDF).

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
_V = "urn:schemas-microsoft-com:vml"
_O = "urn:schemas-microsoft-com:office:office"
_MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
_ADEC = "http://schemas.microsoft.com/office/drawing/2017/decorative"

_P = f"{{{_W}}}p"
_TBL = f"{{{_W}}}tbl"
_TR = f"{{{_W}}}tr"
_TC = f"{{{_W}}}tc"
_SDT = f"{{{_W}}}sdt"
_SDT_CONTENT = f"{{{_W}}}sdtContent"
_BLIP = f"{{{_A}}}blip"
_IMAGEDATA = f"{{{_V}}}imagedata"
_FALLBACK = f"{{{_MC}}}Fallback"
_INLINE = f"{{{_WP}}}inline"
_ANCHOR = f"{{{_WP}}}anchor"
_DOCPR = f"{{{_WP}}}docPr"
_DECORATIVE = f"{{{_ADEC}}}decorative"
_SHAPE = f"{{{_V}}}shape"


class OcrNiedostepny(RuntimeError):
    """Rzucany przez wstrzyknięty `ocr`, gdy OCR nie może działać wcale."""


@dataclass
class Obraz:
    nr: int                      # 1.. w kolejności dokumentu
    nazwa: str = ""              # np. image3.png (nazwa części w pakiecie)
    typ: str = ""                # content type części
    alt: str = ""                # tekst alternatywny (pusty = brak)
    dekoracyjny: bool = False
    zewnetrzny: bool = False     # r:link — obraz poza plikiem
    blob: Optional[bytes] = None
    blad: str = ""               # brak części dla identyfikatora relacji


@dataclass
class Wynik:
    akapity: list = field(default_factory=list)       # treść w kolejności dokumentu
    czyszczenie: dict = field(default_factory=dict)   # liczniki oczysc_akapity_docx
    obrazy: int = 0
    tabele: int = 0
    komorki: int = 0                                  # komórki z tekstem
    z_alt: list = field(default_factory=list)         # numery obrazów
    ocr_ok: list = field(default_factory=list)
    ocr_puste: list = field(default_factory=list)
    dekoracyjne: list = field(default_factory=list)
    zewnetrzne: list = field(default_factory=list)
    bez_ocr: list = field(default_factory=list)       # OCR niepodany albo niedostępny
    format: list = field(default_factory=list)        # [(nr, rozszerzenie)]
    bledy: list = field(default_factory=list)         # [(nr, komunikat)]
    ocr_niedostepny: str = ""                         # powód z OcrNiedostepny

    @property
    def pominiete(self) -> int:
        return (len(self.zewnetrzne) + len(self.bez_ocr) + len(self.format)
                + len(self.bledy))


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


def _w_fallback(el) -> bool:
    return any(a.tag == _FALLBACK for a in el.iterancestors())


def _alt_drawingml(blip) -> tuple[str, bool]:
    for a in blip.iterancestors():
        if a.tag in (_INLINE, _ANCHOR):
            pr = a.find(_DOCPR)
            if pr is None:
                return "", False
            alt = (pr.get("descr") or "").strip() or (pr.get("title") or "").strip()
            dek = any((d.get("val") or "").lower() in ("1", "true")
                      for d in pr.iter(_DECORATIVE))
            return alt, dek
    return "", False


def _alt_vml(imagedata) -> str:
    alt = (imagedata.get(f"{{{_O}}}title") or "").strip()
    for a in imagedata.iterancestors():
        if a.tag == _SHAPE:
            return (a.get("alt") or "").strip() or alt
    return alt


def _obrazy_elementu(el, part, licznik: list) -> list:
    """Obrazy wewnątrz elementu (akapitu), w kolejności XML, bez mc:Fallback."""
    wynik = []
    for x in el.iter(_BLIP, _IMAGEDATA):
        if _w_fallback(x):
            continue
        if x.tag == _BLIP:
            rid = x.get(f"{{{_R}}}embed")
            link = x.get(f"{{{_R}}}link")
            alt, dek = _alt_drawingml(x)
        else:
            rid, link = x.get(f"{{{_R}}}id"), None
            alt, dek = _alt_vml(x), False
        if not rid and not link:
            continue
        licznik[0] += 1
        ob = Obraz(nr=licznik[0], alt=alt, dekoracyjny=dek)
        if not rid:
            ob.zewnetrzny = True
        else:
            czesc = part.related_parts.get(rid) if hasattr(part, "related_parts") else None
            if czesc is None:
                ob.blad = f"no part for relationship {rid}"
            else:
                ob.nazwa = posixpath.basename(str(czesc.partname))
                ob.typ = getattr(czesc, "content_type", "")
                ob.blob = czesc.blob
        wynik.append(ob)
    return wynik


def elementy(doc) -> tuple[list, int, int]:
    """[("tekst", str, w_komorce) | ("obraz", Obraz)] w kolejności dokumentu,
    plus liczba tabel i komórek z tekstem."""
    from docx.text.paragraph import Paragraph
    part = doc.part
    body = doc.element.body
    wynik: list = []
    licznik = [0]
    tabele = [0]
    komorki = [0]

    def akapit(p, w_komorce):
        tekst = Paragraph(p, doc._body).text
        if tekst.strip():
            wynik.append(("tekst", tekst, w_komorce))
        for ob in _obrazy_elementu(p, part, licznik):
            wynik.append(("obraz", ob))
        return bool(tekst.strip())

    def blok(kontener, w_komorce=False) -> bool:
        """True, gdy któryś akapit tego poziomu (bez tabel zagnieżdżonych) ma tekst."""
        ma_tekst = False
        for el in kontener.iterchildren():
            if el.tag == _P:
                ma_tekst |= akapit(el, w_komorce)
            elif el.tag == _TBL:
                tabele[0] += 1
                for tr in el.iterchildren(_TR):
                    for tc in tr.iterchildren(_TC):
                        if blok(tc, True):
                            komorki[0] += 1
            elif el.tag == _SDT:
                tresc = el.find(_SDT_CONTENT)
                if tresc is not None:
                    ma_tekst |= blok(tresc, w_komorce)
        return ma_tekst

    blok(body)
    return wynik, tabele[0], komorki[0]


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


def tresc_docx(doc, ocr: Optional[Callable] = None, alfabety=None) -> Wynik:
    """Treść dokumentu python-docx w kolejności dokumentu (patrz docstring modułu)."""
    from czyszczenie_tekstu import oczysc_akapity_docx
    if alfabety is None:
        from shamanic_locale import alfabety_paczek
        alfabety = alfabety_paczek()
    el, tabele, komorki = elementy(doc)
    w = Wynik(tabele=tabele, komorki=komorki)
    razem = sum(1 for e in el if e[0] == "obraz")
    # Sloty treści: (czy_tekst_dokumentu, tekst). Czyszczenie idzie na samym
    # tekście dokumentu, a liczba akapitów się nie zmienia, więc wraca na miejsce.
    sloty: list = []
    for e in el:
        if e[0] == "tekst":
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
        elif ocr is None or w.ocr_niedostepny:
            w.bez_ocr.append(ob.nr)
        else:
            tekst = _odczytaj(ob, ocr, w, razem)
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


def _odczytaj(ob: Obraz, ocr: Callable, w: Wynik, razem: int) -> str:
    from PIL import Image
    try:
        with Image.open(io.BytesIO(ob.blob)) as surowy:
            surowy.load()
            obraz = _na_bialym(surowy)
            obraz.load()
    except Exception:  # noqa: BLE001 — PIL nie zna formatu (EMF/WMF/SVG) albo plik uszkodzony
        w.format.append((ob.nr, _rozszerzenie(ob)))
        return ""
    try:
        tekst = (ocr(obraz, ob.nr, razem) or "").strip()
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
