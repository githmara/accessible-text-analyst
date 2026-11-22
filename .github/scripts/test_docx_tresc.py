"""Testy treści .docx w kolejności dokumentu (docx_tresc.py) i jej użycia w bramce źródła.

Dokument jest budowany w teście (python-docx + Pillow), OCR to atrapa — test nie
potrzebuje silników OCR ani modeli. Uruchom:  python .github/scripts/test_docx_tresc.py
"""
import copy
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

KORZEN = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KORZEN))

from docx import Document  # noqa: E402
from docx.opc.packuri import PackURI  # noqa: E402
from docx.oxml import parse_xml  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

import docx_tresc as dt  # noqa: E402
import zrodlo_raportu as z  # noqa: E402

WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"


def png(szer, przezroczysty=False):
    """Obraz o szerokości `szer` (atrapa OCR rozpoznaje po niej, który to obraz).
    Przezroczysty: czarne piksele z alfą 0 i jeden czarny kwadrat — bez
    kompozycji na białym silnik dostałby całą czarną planszę."""
    if przezroczysty:
        im = Image.new("RGBA", (szer, 40), (0, 0, 0, 0))
        ImageDraw.Draw(im).rectangle([2, 2, 10, 10], fill=(0, 0, 0, 255))
    else:
        im = Image.new("RGB", (szer, 40), (255, 255, 255))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    buf.seek(0)
    return buf


def docpr(akapit):
    return akapit._p.find(f".//{{{WP}}}docPr")


def zbuduj(sciezka=None):
    """Akapit, obraz do OCR (przezroczysty), tabela 2x2 z zagnieżdżoną tabelą,
    obraz z alt, obraz dekoracyjny, EMF, obraz w mc:AlternateContent (z VML
    w Fallback), akapit końcowy."""
    d = Document()
    d.add_paragraph("Alfa początek.")
    d.add_paragraph().add_run().add_picture(png(101, przezroczysty=True))   # 1: OCR
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text = "Beta komórka."
    t.cell(0, 1).text = "Gamma komórka."
    t.cell(1, 1).add_table(rows=1, cols=1).cell(0, 0).text = "Zagnieżdżona."
    p = d.add_paragraph()
    p.add_run().add_picture(png(102))                                          # 2: alt
    docpr(p).set("descr", "Delta opis alternatywny.")
    p = d.add_paragraph()
    p.add_run().add_picture(png(103))                                          # 3: dekoracyjny
    docpr(p).append(parse_xml(
        f'<a:extLst xmlns:a="{A}"><a:ext uri="{{C183D7F6-B498-43B3-948B-1728B52AA6E4}}">'
        '<adec:decorative xmlns:adec="http://schemas.microsoft.com/office/drawing/2017/decorative" val="1"/>'
        '</a:ext></a:extLst>'))
    p = d.add_paragraph()
    p.add_run().add_picture(png(104))                                          # 4: EMF
    rid = p._p.find(f".//{{{A}}}blip").get(
        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
    czesc = d.part.related_parts[rid]
    czesc._blob = b"\x01\x00\x00\x00 not a raster image"
    czesc.partname = PackURI("/word/media/image_emf.emf")
    # 5: obraz w mc:AlternateContent; Fallback (VML) wskazuje ten sam rId.
    p = d.add_paragraph()
    p.add_run().add_picture(png(105))
    rysunek = p._p.find(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing")
    rid5 = rysunek.find(f".//{{{A}}}blip").get(
        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
    run = rysunek.getparent()
    alt = parse_xml(
        '<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:v="urn:schemas-microsoft-com:vml" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<mc:Choice Requires="wps"/>'
        f'<mc:Fallback><w:pict><v:shape><v:imagedata r:id="{rid5}"/></v:shape></w:pict></mc:Fallback>'
        '</mc:AlternateContent>')
    alt[0].append(copy.deepcopy(rysunek))
    run.remove(rysunek)
    run.append(alt)
    d.add_paragraph("Epsilon koniec.")
    if sciezka:
        d.save(sciezka)
        return Document(sciezka)
    buf = io.BytesIO()
    d.save(buf)
    buf.seek(0)
    return Document(buf)


class Atrapa:
    def __init__(self, puste=(), blad=(), niedostepny_od=None):
        self.wywolania, self.puste, self.blad, self.niedostepny_od = [], set(puste), set(blad), niedostepny_od
        self.obrazy = []

    def __call__(self, obraz, nr, razem):
        self.wywolania.append((nr, razem))
        self.obrazy.append(obraz)
        if self.niedostepny_od is not None and len(self.wywolania) >= self.niedostepny_od:
            raise dt.OcrNiedostepny("no engine")
        if obraz.width in self.blad:
            raise ValueError("broken")
        if obraz.width in self.puste:
            return "   "
        return f"Tekst obrazu {obraz.width}."


class TestKolejnosc(unittest.TestCase):
    def setUp(self):
        self.doc = zbuduj()

    def test_kolejnosc_dokumentu_tabele_i_obrazy(self):
        ocr = Atrapa()
        w = dt.tresc_docx(self.doc, ocr=ocr)
        self.assertEqual(w.akapity, [
            "Alfa początek.", "Tekst obrazu 101.", "Beta komórka.", "Gamma komórka.",
            "Zagnieżdżona.", "Delta opis alternatywny.", "Tekst obrazu 105.", "Epsilon koniec."])
        self.assertEqual((w.tabele, w.komorki), (2, 3))
        self.assertEqual(w.obrazy, 5)   # Fallback VML nie liczy się drugi raz

    def test_klasyfikacja_obrazow(self):
        w = dt.tresc_docx(self.doc, ocr=Atrapa())
        self.assertEqual(w.ocr_ok, [1, 5])
        self.assertEqual(w.z_alt, [2])
        self.assertEqual(w.dekoracyjne, [3])
        self.assertEqual(w.format, [(4, "EMF")])
        self.assertEqual(w.pominiete, 1)

    def test_przezroczystosc_na_bialym(self):
        ocr = Atrapa()
        dt.tresc_docx(self.doc, ocr=ocr)
        obraz = ocr.obrazy[0]
        self.assertEqual(obraz.mode, "RGB")
        self.assertEqual(obraz.getpixel((50, 30)), (255, 255, 255))
        self.assertEqual(obraz.getpixel((5, 5)), (0, 0, 0))
        self.assertEqual(ocr.wywolania, [(1, 5), (5, 5)])

    def test_akapit_kotwica_nie_daje_pustej_tresci(self):
        w = dt.tresc_docx(self.doc, ocr=Atrapa(puste={101}))
        self.assertTrue(all(a.strip() for a in w.akapity))
        self.assertEqual(w.ocr_puste, [1])
        self.assertNotIn("", w.akapity)

    def test_bez_ocr_liczy_obrazy(self):
        w = dt.tresc_docx(self.doc, ocr=None)
        self.assertEqual(w.bez_ocr, [1, 4, 5])  # format nieznany dopiero przy odczycie
        self.assertIn("Delta opis alternatywny.", w.akapity)
        self.assertEqual(w.pominiete, 3)

    def test_ocr_niedostepny_zatrzymuje_proby(self):
        ocr = Atrapa(niedostepny_od=1)
        w = dt.tresc_docx(self.doc, ocr=ocr)
        self.assertEqual(len(ocr.wywolania), 1)
        # EMF też: bez OCR nie ma po co rozpoznawać formatu, liczy się jako pominięty.
        self.assertEqual(w.bez_ocr, [1, 4, 5])
        self.assertEqual(w.ocr_niedostepny, "no engine")
        self.assertEqual(w.akapity[0], "Alfa początek.")

    def test_blad_jednego_obrazu_nie_zatrzymuje(self):
        w = dt.tresc_docx(self.doc, ocr=Atrapa(blad={101}))
        self.assertEqual([n for n, _ in w.bledy], [1])
        self.assertEqual(w.ocr_ok, [5])

    def test_zakresy(self):
        self.assertEqual(dt.zakresy([7, 1, 2, 3, 9, 10]), "1-3, 7, 9-10")
        self.assertEqual(dt.zakresy([]), "")


class TestBramka(unittest.TestCase):
    def test_bramka_czyta_tabele_i_zapisuje_obrazy(self):
        with tempfile.TemporaryDirectory() as tmp:
            sc = os.path.join(tmp, "d.docx")
            zbuduj(sc)
            stan = {}
            kawalki = list(z._kawalki_docx(sc, stan=stan))
            self.assertIn("Gamma komórka.", kawalki)
            self.assertIn("Delta opis alternatywny.", kawalki)
            self.assertEqual(stan.get("obrazy"), 3)

    def test_podglad_z_ocr_niesprawdzalny_a_nie_odmowa(self):
        with tempfile.TemporaryDirectory() as tmp:
            sc = os.path.join(tmp, "d.docx")
            zbuduj(sc)
            wynik = z.sprawdz_tresc(sc, ["Tekst obrazu sto jeden z prezentacji o prawie"])
            self.assertEqual((wynik.stan, wynik.powod), ("niesprawdzalna", "ocr"))
            wynik = z.sprawdz_tresc(sc, ["Gamma komórka. Zagnieżdżona. Delta opis"])
            self.assertEqual(wynik.stan, "zgodna")


if __name__ == "__main__":
    unittest.main(verbosity=2)
