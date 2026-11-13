"""diagnostyka.py — syntetyczny korpus pełnej diagnostyki (`run_all.py --warnings-as-errors`).

Tryb ostrzeżeń nie może zależeć od configa użytkownika: ostrzeżenie biblioteki
w komponencie, którego config akurat nie włącza (OCR, sentyment, islandzki,
omorfi, naprawa fontu PDF), byłoby niewidoczne — a potem ktoś zgłasza błąd,
który był zapowiedziany FutureWarningiem. Ten moduł buduje pliki, które
przepuszczają przez notatnik KAŻDĄ ścieżkę:

- `korpus.pdf` — korpus główny: trzy strony fińskiej prozy z powtarzanym
  nagłówkiem i numerem strony (warstwa tekstu, nagłówki, numery stron), strona
  islandzka (przebieg wielojęzyczny -> IceBERT + NER), strona z fontem Type0
  bez pełnej mapy ToUnicode (naprawa przez fontTools) i strona-skan (pypdfium2
  + easyocr);
- `probka.txt|.md|.html|.docx|.png` — pozostałe loadery; `.html` serwuje też
  lokalny serwer dla `load_url`.

Wszystko powstaje w czasie wykonania (Pillow, fontTools, python-docx), bez
plików w repo. Fińskiego modelu spaCy wystarcza jeden: ścieżka spaCy jest ta
sama dla każdego języka, a islandzki idzie gałęzią Hugging Face.
"""
from __future__ import annotations

import io
from pathlib import Path

# Komponenty, bez których diagnostyka nie jest pełna: (nazwa do raportu,
# moduł do importu). Model spaCy i automaty omorfi sprawdza `brakujace()` osobno.
PAKIETY = (
    ("spacy", "spacy"), ("transformers", "transformers"), ("torch", "torch"),
    ("sentencepiece", "sentencepiece"), ("protobuf", "google.protobuf"),
    ("tiktoken", "tiktoken"), ("omorfi", "omorfi"), ("easyocr", "easyocr"),
    ("pypdfium2", "pypdfium2"), ("pillow", "PIL"), ("fonttools", "fontTools"),
    ("python-docx", "docx"), ("pdfplumber", "pdfplumber"), ("requests", "requests"),
)
AUTOMATY_OMORFI = ("omorfi_recased.describe.hfst", "omorfi.describe.hfst")
# Ostrzeżenia zmierzone i uznane za szum środowiska (2026-11-13): tryb pokazuje
# je osobną linią [INFO], ale nie liczy do kodu 4 — inaczej każdy przebieg
# kończyłby się ostrzeżeniem, a nowe, ważne ginęłoby wśród stałych.
# (kategoria, początek treści, dlaczego nieszkodliwe). Dopisuj tylko z dowodem.
ZNANE_OSTRZEZENIA = (
    ("UserWarning", "'pin_memory' argument is set as true but no accelerator",
     "easyocr tworzy DataLoader(pin_memory=True); na CPU torch ignoruje parametr, wynik OCR bez zmian"),
    ("TqdmWarning", "IProgress not found",
     "tqdm.auto w jądrze Jupytera bez ipywidgets; paski postępu i tak są wyłączone"),
)


def znane(kategoria: str, tresc: str) -> bool:
    """Czy ostrzeżenie jest na liście znanych, nieszkodliwych."""
    return any(kategoria == k and tresc.startswith(p) for k, p, _ in ZNANE_OSTRZEZENIA)


JEZYK_SPACY = "fi"
OCR_JEZYKI = ["is", "en"]      # easyocr nie ma fińskiego; łacinka „is” czyta ä/ö
NAGLOWEK = "ATA diagnostiikka - synteettinen korpus"
# Słowa, po których komórka kontrolna poznaje, że dana ścieżka zadziałała.
SLOWO_NAPRAWY = "kirjastonhoitaja"
SLOWA_LOADEROW = {"txt": "tekstitiedosto", "md": "merkintakieli", "html": "verkkosivu",
                  "docx": "asiakirja", "png": "KUVA", "url": "verkkosivu"}
ROSKA = "DIAGROSKA 4711"
WZORZEC_ROSKI = "DIAGROSKA [0-9]+"

FI_STRONY = [
    [
        "Kirjasto avautuu aamulla kello yhdeksän, ja ensimmäiset lukijat odottavat jo ovella.",
        "Kirjaston lukusalissa on hiljaista, vaikka kirjastossa käy päivittäin satoja ihmisiä.",
        "Lapset lainaavat kirjastosta satukirjoja ja aikuiset lukevat sanomalehtiä.",
        "Kirjastonhoitaja neuvoo lukijoita etsimään kirjoja luettelosta.",
        "Uusi kirjasto rakennettiin vanhan rautatieaseman viereen keskelle kaupunkia.",
        "Kaupunki maksoi kirjaston rakentamisen, ja valtio tuki hanketta.",
        "Kirjaston kokoelmassa on romaaneja, runoja, tietokirjoja ja äänikirjoja.",
        "Moni lukija kuuntelee äänikirjoja junassa matkalla töihin.",
        "Illalla kirjastossa järjestetään lukupiiri, jossa keskustellaan romaaneista.",
        "Lukupiirin vetäjä valitsee joka kuukausi uuden romaanin.",
        "Kirjasto sulkeutuu illalla kello kahdeksan.",
        "Viimeiset lukijat palauttavat kirjat automaattiin ennen sulkemista.",
    ],
    [
        "Metsä alkaa heti kaupungin laidalta, ja polku kulkee järven rantaa pitkin.",
        "Metsässä kasvaa kuusia, mäntyjä ja koivuja, ja syksyllä sieltä löytää sieniä.",
        "Järven rannalla on laituri, jolta lapset hyppäävät veteen kesällä.",
        "Talvella järvi jäätyy, ja jäällä hiihdetään ja pilkitään kalaa.",
        "Metsän eläimet liikkuvat aamulla ja illalla, kun ihmisiä on vähän.",
        "Hirvi ylittää polun usein järven pohjoispäässä.",
        "Retkeilijät pitävät metsästä, koska se on hiljainen ja rauhallinen.",
        "Metsän polulla on opasteita, jotka kertovat kasveista ja eläimistä.",
        "Kaupunki suojelee metsää, eikä sinne saa rakentaa uusia taloja.",
        "Järven vesi on puhdasta, ja siinä elää ahvenia ja haukia.",
        "Syksyllä metsä on keltainen ja punainen, ja polulla on paljon lehtiä.",
        "Retkeilijät palaavat metsästä kaupunkiin junalla illalla.",
    ],
    [
        "Juna lähtee asemalta joka tunti, ja matka kaupungista pääkaupunkiin kestää kaksi tuntia.",
        "Junassa on hiljainen vaunu, jossa matkustajat lukevat ja tekevät töitä.",
        "Rautatieasema on kirjaston vieressä, joten moni lukija tulee kirjastoon junalla.",
        "Juna on myöhässä talvella, kun lunta sataa paljon.",
        "Matkustajat odottavat junaa asemalla ja lukevat kirjoja.",
        "Konduktööri tarkastaa liput junan lähdettyä asemalta.",
        "Junan ikkunasta näkyy metsä, järvi ja pieniä kyliä.",
        "Uusi rata rakennettiin metsän läpi, ja matka lyheni puoli tuntia.",
        "Valtio maksoi radan rakentamisen, ja kaupunki maksoi uuden aseman.",
        "Juna saapuu pääkaupunkiin keskipäivällä, ja matkustajat jatkavat töihin.",
        "Illalla juna palaa kaupunkiin, ja matkustajat menevät kotiin.",
        "Asema sulkeutuu yöllä, kun viimeinen juna on lähtenyt.",
    ],
]
IS_STRONA = [
    "Jón Sigurðsson fór frá Reykjavík til Akureyrar með Guðrúnu Helgadóttur í gær.",
    "Þórdís Kolbrún Gylfadóttir ræddi við Landsvirkjun og Háskóla Íslands í Kópavogi.",
    "Björk Guðmundsdóttir söng í Hörpu fyrir fullu húsi á laugardaginn.",
    "Bókasafnið í Hafnarfirði opnar klukkan níu á morgnana alla virka daga.",
    "Lesendur fá lánaðar bækur, tímarit og hljóðbækur á bókasafninu.",
    "Veðrið á Íslandi breytist hratt og ferðamenn verða að fara varlega.",
]
CID_TEKST = "kirjastonhoitaja lainaa kirjoja ja kirjastonhoitaja lukee kirjoja"
SKAN_LINIE = ["KUVA TEKSTISTA", "SKANNATTU SIVU", "JUNA LAHTEE ASEMALTA"]


def brakujace() -> list[str]:
    """Co uniemożliwia pełną diagnostykę: pakiety, model spaCy, automaty omorfi."""
    import importlib.util
    braki = []
    for nazwa, modul in PAKIETY:
        try:
            if importlib.util.find_spec(modul) is None:
                braki.append(nazwa)
        except (ImportError, ValueError):
            braki.append(nazwa)
    if "spacy" not in braki:
        import spacy.util
        from shamanic_locale import PODSTAWY
        model = PODSTAWY[JEZYK_SPACY]["spacy"]
        if not spacy.util.is_package(model):
            braki.append(model)
    katalog = Path(__file__).resolve().parent
    if not any((katalog / p).is_file() for p in AUTOMATY_OMORFI):
        braki.append("omorfi-download (*.hfst)")
    return braki


# --- PDF ---------------------------------------------------------------------

def _pdf_tekst(tekst: str) -> bytes:
    """Napis PDF w WinAnsi (Helvetica): nawiasy i ukośnik wsteczny ucieczką."""
    bs = chr(92)
    for znak in (bs, "(", ")"):
        tekst = tekst.replace(znak, bs + znak)
    return b"(" + tekst.encode("cp1252") + b")"


def _strumien(dane: bytes, slownik: bytes = b"") -> bytes:
    return b"<< /Length %d " % len(dane) + slownik + b">>\nstream\n" + dane + b"\nendstream"


def _font_cid(litery: str) -> bytes:
    """TrueType z glifem na każdą literę (cmap kompletny) — źródło naprawy."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    nazwy = [".notdef"] + [f"g{i}" for i in range(1, len(litery) + 1)]
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(nazwy)
    fb.setupCharacterMap({ord(z): f"g{i}" for i, z in enumerate(litery, 1)})
    glify = {}
    for nazwa in nazwy:
        pen = TTGlyphPen(None)
        pen.moveTo((50, 0)); pen.lineTo((50, 500)); pen.lineTo((450, 500)); pen.lineTo((450, 0))
        pen.closePath()
        glify[nazwa] = pen.glyph()
    fb.setupGlyf(glify)
    fb.setupHorizontalMetrics({k: (600, 50) for k in nazwy})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "Diag", "styleName": "Regular"})
    fb.setupOS2()
    fb.setupPost()
    buf = io.BytesIO()
    fb.save(buf)
    return buf.getvalue()


def _obraz_tekstu(linie: list[str], szer: int = 1200, wys: int = 520):
    """Obraz PIL z tekstem — wejście OCR (skan w PDF i `.png`)."""
    from PIL import Image, ImageDraw, ImageFont
    obraz = Image.new("RGB", (szer, wys), "white")
    rysuj = ImageDraw.Draw(obraz)
    font = ImageFont.load_default(size=64)
    for i, linia in enumerate(linie):
        rysuj.text((60, 60 + i * 140), linia, fill="black", font=font)
    return obraz


def zbuduj_pdf() -> bytes:
    """Korpus główny (6 stron) — patrz docstring modułu."""
    obiekty: list[bytes] = [b"", b""]   # 1 katalog, 2 drzewo stron (uzupełniane na końcu)
    helv = len(obiekty) + 1
    obiekty.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    strony = []

    def strona(tresc: bytes, zasoby: bytes) -> None:
        nr = len(obiekty) + 1
        obiekty.append(b"")            # miejsce na stronę
        obiekty.append(_strumien(tresc))
        obiekty[nr - 1] = (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                           b"/Resources " + zasoby + b" /Contents %d 0 R >>" % (nr + 1))
        strony.append(nr)

    def tekstowa(linie: list[str], numer: int) -> None:
        tresc = b"BT /F1 9 Tf 60 760 Td " + _pdf_tekst(NAGLOWEK) + b" Tj ET\n"
        tresc += b"BT /F1 11 Tf 16 TL 60 720 Td"
        for linia in linie:
            tresc += b" " + _pdf_tekst(linia) + b" Tj T*"
        tresc += b" ET\nBT /F1 9 Tf 300 30 Td " + _pdf_tekst(str(numer)) + b" Tj ET"
        strona(tresc, b"<< /Font << /F1 %d 0 R >> >>" % helv)

    for n, linie in enumerate(FI_STRONY, 1):
        tekstowa(linie, n)
    tekstowa(IS_STRONA, len(FI_STRONY) + 1)

    # Strona z fontem Type0 i UCIĘTĄ mapą ToUnicode (tylko GID 1): pdfplumber
    # oddaje „(cid:N)”, a naprawa_zrodel czyta znaki z cmap osadzonego fontu.
    litery = "".join(dict.fromkeys(CID_TEKST))
    font = _font_cid(litery)
    gidy = "".join(f"{litery.index(z) + 1:04X}" for z in CID_TEKST)
    cmap = (b"/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
            b"/CMapName /Diag def\n1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n"
            b"1 beginbfchar\n<0001> <%04X>\nendbfchar\n" % ord(litery[0])
            + b"endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n")
    f0 = len(obiekty) + 1
    obiekty += [
        b"<< /Type /Font /Subtype /Type0 /BaseFont /DIAGAA+Diag /Encoding /Identity-H "
        b"/DescendantFonts [%d 0 R] /ToUnicode %d 0 R >>" % (f0 + 1, f0 + 3),
        b"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /DIAGAA+Diag "
        b"/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> "
        b"/FontDescriptor %d 0 R /DW 600 /CIDToGIDMap /Identity >>" % (f0 + 2),
        b"<< /Type /FontDescriptor /FontName /DIAGAA+Diag /Flags 4 /FontBBox [0 -200 1000 800] "
        b"/ItalicAngle 0 /Ascent 800 /Descent -200 /CapHeight 700 /StemV 80 /FontFile2 %d 0 R >>" % (f0 + 4),
        _strumien(cmap),
        _strumien(font, b"/Length1 %d " % len(font)),
    ]
    strona(b"BT /F2 12 Tf 60 700 Td <" + gidy.encode() + b"> Tj ET",
           b"<< /Font << /F2 %d 0 R >> >>" % f0)

    # Strona-skan: sam obraz JPEG, bez warstwy tekstu -> OCR.
    buf = io.BytesIO()
    obraz = _obraz_tekstu(SKAN_LINIE)
    obraz.save(buf, format="JPEG", quality=90)
    jpg = buf.getvalue()
    im = len(obiekty) + 1
    obiekty.append(_strumien(jpg, b"/Type /XObject /Subtype /Image /Width %d /Height %d "
                             b"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode "
                             % obraz.size))
    strona(b"q 540 0 0 234 36 480 cm /Im1 Do Q", b"<< /XObject << /Im1 %d 0 R >> >>" % im)

    obiekty[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    obiekty[1] = (b"<< /Type /Pages /Kids [" + b" ".join(b"%d 0 R" % s for s in strony)
                  + b"] /Count %d >>" % len(strony))
    wyj = bytearray(b"%PDF-1.4\n")
    pozycje = []
    for nr, obiekt in enumerate(obiekty, 1):
        pozycje.append(len(wyj))
        wyj += b"%d 0 obj\n" % nr + obiekt + b"\nendobj\n"
    xref = len(wyj)
    wyj += b"xref\n0 %d\n0000000000 65535 f \n" % (len(obiekty) + 1)
    for p in pozycje:
        wyj += b"%010d 00000 n \n" % p
    wyj += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(obiekty) + 1, xref)
    return bytes(wyj)


# --- pozostałe formaty ----------------------------------------------------------

def zbuduj(katalog: Path) -> dict[str, Path]:
    """Zapisuje wszystkie pliki diagnostyki w `katalog`; zwraca {rodzaj: ścieżka}."""
    katalog.mkdir(parents=True, exist_ok=True)
    pliki = {k: katalog / f"probka.{k}" for k in ("txt", "md", "html", "docx", "png")}
    pliki["pdf"] = katalog / "korpus.pdf"
    pliki["pdf"].write_bytes(zbuduj_pdf())
    zdania = FI_STRONY[0][:4]
    pliki["txt"].write_text("\n".join([SLOWA_LOADEROW["txt"] + " " + zdania[0], ROSKA, *zdania[1:]]),
                            encoding="utf-8")
    pliki["md"].write_text(
        "---\ntitle: diag\n---\n\n# " + SLOWA_LOADEROW["md"] + "\n\n" + " ".join(zdania)
        + "\n\n```\nkoodi ei kuulu korpukseen\n```\n\n- " + FI_STRONY[1][0] + "\n",
        encoding="utf-8")
    pliki["html"].write_text(
        "<!doctype html><html lang=\"fi\"><head><meta charset=\"utf-8\"><title>diag</title></head>"
        "<body><nav>valikko</nav><article><h1>" + SLOWA_LOADEROW["html"] + "</h1>"
        + "".join(f"<p>{z}</p>" for z in FI_STRONY[2][:6]) + "</article></body></html>",
        encoding="utf-8")
    from docx import Document
    dok = Document()
    dok.add_paragraph(SLOWA_LOADEROW["docx"] + " " + zdania[0])
    for z in zdania[1:]:
        dok.add_paragraph(z)
    dok.save(pliki["docx"])
    _obraz_tekstu(SKAN_LINIE).save(pliki["png"])
    return pliki
