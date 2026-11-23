"""Testy treści .docx w kolejności dokumentu (docx_tresc.py) i jej użycia w bramce źródła.

Dokumenty są budowane w teście (python-docx + Pillow), OCR to atrapa — test nie
potrzebuje silników OCR ani modeli. Test prawdziwego EMF (GDI) idzie tylko na
Windows. Wspólna polityka z Reżyserem (punkty 1–7) — docstring `docx_tresc.py`.
Uruchom:  python .github/scripts/test_docx_tresc.py
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
from docx.opc.constants import RELATIONSHIP_TYPE as RT  # noqa: E402
from docx.opc.packuri import PackURI  # noqa: E402
from docx.oxml import parse_xml  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

import docx_tresc as dt  # noqa: E402
import zrodlo_raportu as z  # noqa: E402

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"
NS = (f'xmlns:w="{W}" xmlns:a="{A}" xmlns:r="{R}" xmlns:wp="{WP}" xmlns:pic="{PIC}" '
      'xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office" '
      'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
      'xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup" '
      'xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" '
      'xmlns:dgm="http://schemas.openxmlformats.org/drawingml/2006/diagram" '
      'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"')


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


def blip_rid(akapit):
    return akapit._p.find(f".//{{{A}}}blip").get(f"{{{R}}}embed")


def obraz_akapit(d, szer, descr=None):
    p = d.add_paragraph()
    p.add_run().add_picture(png(szer))
    if descr is not None:
        docpr(p).set("descr", descr)
    return p


def dodaj_xml(d, xml):
    body = d.element.body
    el = parse_xml(xml)
    body.insert(len(body) - 1, el)   # przed w:sectPr
    return el


def otworz(d):
    buf = io.BytesIO()
    d.save(buf)
    buf.seek(0)
    return Document(buf)


def zbuduj(sciezka=None):
    """Akapit, obraz do OCR (przezroczysty), tabela 2x2 z zagnieżdżoną tabelą,
    obraz z alt, obraz dekoracyjny, nierozpoznane bajty, obraz w
    mc:AlternateContent (z VML w Fallback), akapit końcowy."""
    d = Document()
    d.add_paragraph("Alfa początek.")
    d.add_paragraph().add_run().add_picture(png(101, przezroczysty=True))   # 1: OCR
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text = "Beta komórka."
    t.cell(0, 1).text = "Gamma komórka."
    t.cell(1, 1).add_table(rows=1, cols=1).cell(0, 0).text = "Zagnieżdżona."
    obraz_akapit(d, 102, "Delta opis alternatywny.")                           # 2: alt
    p = obraz_akapit(d, 103)                                                   # 3: dekoracyjny
    docpr(p).append(parse_xml(
        f'<a:extLst xmlns:a="{A}"><a:ext uri="{{C183D7F6-B498-43B3-948B-1728B52AA6E4}}">'
        '<adec:decorative xmlns:adec="http://schemas.microsoft.com/office/drawing/2017/decorative" val="1"/>'
        '</a:ext></a:extLst>'))
    p = obraz_akapit(d, 104)                                                   # 4: bajty nie-obrazu
    czesc = d.part.related_parts[blip_rid(p)]
    czesc._blob = b"\x01\x00\x00\x00 not a raster image"
    czesc.partname = PackURI("/word/media/image_emf.emf")
    # 5: obraz w mc:AlternateContent; Fallback (VML) wskazuje ten sam rId.
    p = obraz_akapit(d, 105)
    rysunek = p._p.find(f".//{{{W}}}drawing")
    rid5 = blip_rid(p)
    run = rysunek.getparent()
    alt = parse_xml(f'<mc:AlternateContent {NS}><mc:Choice Requires="wps"/>'
                    f'<mc:Fallback><w:pict><v:shape><v:imagedata r:id="{rid5}"/></v:shape></w:pict></mc:Fallback>'
                    '</mc:AlternateContent>')
    alt[0].append(copy.deepcopy(rysunek))
    run.remove(rysunek)
    run.append(alt)
    d.add_paragraph("Epsilon koniec.")
    if sciezka:
        d.save(sciezka)
        return Document(sciezka)
    return otworz(d)


class Atrapa:
    def __init__(self, puste=(), blad=(), niedostepny_od=None):
        self.wywolania, self.puste, self.blad, self.niedostepny_od = [], set(puste), set(blad), niedostepny_od
        self.obrazy = []

    def __call__(self, obraz, nr, k, razem):
        self.wywolania.append((nr, k, razem))
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
        w = dt.tresc_docx(self.doc, ocr=Atrapa())
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
        self.assertEqual(w.format, [(4, "EMF")])   # bajty nie-obrazu, nie prawdziwy EMF
        self.assertEqual(w.pominiete, 1)

    def test_przezroczystosc_na_bialym(self):
        ocr = Atrapa()
        dt.tresc_docx(self.doc, ocr=ocr)
        obraz = ocr.obrazy[0]
        self.assertEqual(obraz.mode, "RGB")
        self.assertEqual(obraz.getpixel((50, 30)), (255, 255, 255))
        self.assertEqual(obraz.getpixel((5, 5)), (0, 0, 0))
        # (nr, k, razem): razem = różne obrazy do OCR (1, 4, 5), nie wszystkie obrazy
        self.assertEqual(ocr.wywolania, [(1, 1, 3), (5, 3, 3)])

    def test_akapit_kotwica_nie_daje_pustej_tresci(self):
        w = dt.tresc_docx(self.doc, ocr=Atrapa(puste={101}))
        self.assertTrue(all(a.strip() for a in w.akapity))
        self.assertEqual(w.ocr_puste, [1])

    def test_bez_ocr_liczy_obrazy(self):
        w = dt.tresc_docx(self.doc, ocr=None)
        self.assertEqual(w.bez_ocr, [1, 4, 5])
        self.assertIn("Delta opis alternatywny.", w.akapity)
        self.assertEqual(w.pominiete, 3)

    def test_ocr_niedostepny_zatrzymuje_proby(self):
        ocr = Atrapa(niedostepny_od=1)
        w = dt.tresc_docx(self.doc, ocr=ocr)
        self.assertEqual(len(ocr.wywolania), 1)
        # EMF też: bez OCR nie ma po co rozpoznawać formatu, liczy się jako pominięty.
        self.assertEqual(w.bez_ocr, [1, 4, 5])
        self.assertEqual(w.ocr_niedostepny, "no engine")

    def test_blad_jednego_obrazu_nie_zatrzymuje(self):
        w = dt.tresc_docx(self.doc, ocr=Atrapa(blad={101}))
        self.assertEqual([n for n, _ in w.bledy], [1])
        self.assertEqual(w.ocr_ok, [5])

    def test_zakresy(self):
        self.assertEqual(dt.zakresy([7, 1, 2, 3, 9, 10]), "1-3, 7, 9-10")
        self.assertEqual(dt.zakresy([]), "")


class TestPolityka(unittest.TestCase):
    """Wspólna polityka z Reżyserem i znaleziska audytu 2.2.0 (F3–F11)."""

    def test_pole_tekstowe_w_miejscu_z_obrazem_i_raz(self):          # F3, polityka 1
        d = Document()
        d.add_paragraph("Przed polem.")
        obraz = obraz_akapit(d, 301)
        rid = blip_rid(obraz)
        rysunek = copy.deepcopy(obraz._p.find(f".//{{{W}}}drawing"))
        d.element.body.remove(obraz._p)
        pole = ('<w:txbxContent><w:p><w:r><w:t>TEKST W POLU</w:t></w:r></w:p>'
                '<w:p><w:r/></w:p></w:txbxContent>')
        p = dodaj_xml(d, f'<w:p {NS}><w:r><w:t>Kotwica pola.</w:t></w:r><w:r><mc:AlternateContent>'
                         '<mc:Choice Requires="wps"><w:drawing><wp:anchor><wp:docPr id="9" name="Pole"/>'
                         '<a:graphic><a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">'
                         f'<wps:wsp><wps:txbx>{pole}</wps:txbx></wps:wsp></a:graphicData></a:graphic></wp:anchor>'
                         '</w:drawing></mc:Choice><mc:Fallback><w:pict><v:shape><v:textbox>'
                         f'{pole}</v:textbox></v:shape></w:pict></mc:Fallback></mc:AlternateContent></w:r></w:p>')
        for kopia in p.iter(f"{{{W}}}txbxContent"):
            kopia[1][0].append(copy.deepcopy(rysunek))
        d.add_paragraph("Po polu.")
        w = dt.tresc_docx(otworz(d), ocr=Atrapa())
        self.assertEqual(w.akapity, ["Przed polem.", "Kotwica pola.", "TEKST W POLU",
                                     "Tekst obrazu 301.", "Po polu."])
        self.assertEqual((w.pola_tekstowe, w.obrazy), (1, 1))
        self.assertTrue(rid)

    def test_kolontytuly_zglaszane_nie_czytane(self):                  # F3, polityka 2
        d = Document()
        d.add_paragraph("Treść ciała.")
        d.sections[0].header.paragraphs[0].add_run().add_picture(png(401))
        d.sections[0].footer.paragraphs[0].text = "TEKST STOPKI"
        w = dt.tresc_docx(otworz(d), ocr=Atrapa())
        self.assertEqual(w.akapity, ["Treść ciała."])
        self.assertEqual((w.naglowki, w.stopki, w.obrazy), (1, 1, 0))
        pusty = dt.tresc_docx(otworz(Document()), ocr=None)
        self.assertEqual((pusty.naglowki, pusty.stopki), (0, 0))

    def test_wykres_i_smartart_zglaszane_alt_w_miejscu(self):          # F3, polityka 3
        d = Document()
        d.add_paragraph("Przed wykresem.")
        dodaj_xml(d, f'<w:p {NS}><w:r><w:drawing><wp:inline><wp:docPr id="11" name="W" descr="ALT WYKRESU"/>'
                     '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/chart">'
                     '<c:chart r:id="rId900"/></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>')
        dodaj_xml(d, f'<w:p {NS}><w:r><w:drawing><wp:inline><wp:docPr id="12" name="S"/>'
                     '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/diagram">'
                     '<dgm:relIds r:dm="rId901" r:lo="rId902" r:qs="rId903" r:cs="rId904"/></a:graphicData>'
                     '</a:graphic></wp:inline></w:drawing></w:r></w:p>')
        d.add_paragraph("Po.")
        w = dt.tresc_docx(otworz(d), ocr=None)
        self.assertEqual(w.akapity, ["Przed wykresem.", "ALT WYKRESU", "Po."])
        self.assertEqual((w.diagramy, w.diagramy_alt, w.obrazy), (2, 1, 0))

    def test_sdt_wiersza_komorki_i_customxml(self):                     # F4, polityka 4
        d = Document()
        t = d.add_table(rows=2, cols=2)
        t.cell(0, 0).text = "Wiersz zwykły."
        t.cell(1, 0).text = "WIERSZ W KONTROLCE"
        t.cell(1, 1).text = "KOMÓRKA W KONTROLCE"
        tr = t._tbl.findall(f"{{{W}}}tr")[1]
        tc = tr.findall(f"{{{W}}}tc")[1]
        sdt_c = parse_xml(f'<w:sdt {NS}><w:sdtPr/><w:sdtContent/></w:sdt>')
        tr.replace(tc, sdt_c)
        sdt_c[1].append(tc)
        sdt_r = parse_xml(f'<w:sdt {NS}><w:sdtPr/><w:sdtContent/></w:sdt>')
        t._tbl.replace(tr, sdt_r)
        sdt_r[1].append(tr)
        dodaj_xml(d, f'<w:customXml {NS} w:element="s"><w:p><w:r><w:t>TEKST W CUSTOMXML</w:t></w:r></w:p></w:customXml>')
        w = dt.tresc_docx(otworz(d), ocr=None)
        self.assertEqual(w.akapity, ["Wiersz zwykły.", "WIERSZ W KONTROLCE", "KOMÓRKA W KONTROLCE",
                                     "TEKST W CUSTOMXML"])
        self.assertEqual(w.komorki, 3)

    def test_sledzenie_zmian_sdt_i_pole_proste(self):                   # F5, polityka 5
        d = Document()
        p = obraz_akapit(d, 501)
        r_ = p._p.find(f"{{{W}}}r")
        usun = parse_xml(f'<w:del {NS} w:id="1" w:author="x"/>')
        p._p.replace(r_, usun)
        usun.append(r_)
        dodaj_xml(d, f'<w:p {NS}><w:pPr><w:tabs><w:tab w:val="left" w:pos="720"/></w:tabs></w:pPr>'
                     '<w:r><w:t xml:space="preserve">Stary </w:t></w:r>'
                     '<w:del w:id="2" w:author="x"><w:r><w:delText>USUNIĘTY</w:delText></w:r></w:del>'
                     '<w:moveFrom w:id="3" w:author="x"><w:r><w:t>PRZENIESIONY STĄD</w:t></w:r></w:moveFrom>'
                     '<w:ins w:id="4" w:author="x"><w:r><w:t>WSTAWIONY</w:t></w:r></w:ins>'
                     '<w:moveTo w:id="5" w:author="x"><w:r><w:t xml:space="preserve"> TUTAJ</w:t></w:r></w:moveTo>'
                     '<w:sdt><w:sdtPr><w:alias w:val="x"/></w:sdtPr><w:sdtContent><w:r><w:t xml:space="preserve"> SDT</w:t>'
                     '</w:r></w:sdtContent></w:sdt><w:fldSimple w:instr="AUTHOR"><w:r><w:tab/><w:t>POLE</w:t></w:r>'
                     '</w:fldSimple></w:p>')
        w = dt.tresc_docx(otworz(d), ocr=Atrapa())
        self.assertEqual(w.akapity, ["Stary WSTAWIONY TUTAJ SDT\tPOLE"])
        self.assertEqual(w.obrazy, 0)   # obraz usunięty śledzeniem zmian

    def test_tekst_akapitu_jak_python_docx(self):                       # F5: zwykłe akapity bez zmian
        d = Document()
        p = d.add_paragraph("Raz")
        p.add_run().add_tab()
        p.add_run("dwa").add_break()
        p.add_run("trzy")
        from docx.enum.text import WD_BREAK
        p.add_run("cztery").add_break(WD_BREAK.PAGE)
        d.add_paragraph().add_run("link")
        for akapit in otworz(d).paragraphs:
            self.assertEqual(dt._tekst_akapitu(akapit._p), akapit.text)

    def test_vml_orelid_i_zewnetrzny(self):                             # F6, F7
        d = Document()
        rid, _ = d.part.get_or_add_image(png(601))
        dodaj_xml(d, f'<w:p {NS}><w:r><w:pict><v:shape><v:imagedata o:relid="{rid}"/></v:shape></w:pict></w:r></w:p>')
        rid_z = d.part.relate_to("http://example.invalid/obraz.png", RT.IMAGE, is_external=True)
        dodaj_xml(d, f'<w:p {NS}><w:r><w:pict><v:shape><v:imagedata r:id="{rid_z}"/></v:shape></w:pict></w:r></w:p>')
        dodaj_xml(d, f'<w:p {NS}><w:r><w:pict><v:shape><v:imagedata r:id="rId999"/></v:shape></w:pict></w:r></w:p>')
        dodaj_xml(d, f'<w:p {NS}><w:r><w:pict><v:shape><v:imagedata/></v:shape></w:pict></w:r></w:p>')
        w = dt.tresc_docx(otworz(d), ocr=Atrapa())
        self.assertEqual(w.akapity, ["Tekst obrazu 601."])
        self.assertEqual(w.zewnetrzne, [2])
        self.assertEqual([n for n, _ in w.bledy], [3, 4])
        self.assertEqual(w.obrazy, 4)

    def test_pusty_i_za_duzy_to_nie_format(self):                      # F8
        d = Document()
        pusty = d.part.related_parts[blip_rid(obraz_akapit(d, 801))]
        duzy = d.part.related_parts[blip_rid(obraz_akapit(d, 802))]
        pusty._blob = b""
        b = io.BytesIO()
        Image.new("1", (14000, 14000), 1).save(b, "PNG")
        duzy._blob = b.getvalue()
        ocr = Atrapa()
        w = dt.tresc_docx(otworz(d), ocr=ocr)
        self.assertEqual(w.puste_pliki, [1])
        self.assertEqual(w.za_duze, [(2, "14000x14000")])
        self.assertEqual((w.format, w.bledy, ocr.wywolania), ([], [], []))
        self.assertIsNotNone(Image.MAX_IMAGE_PIXELS)   # limit przywrócony

    def test_grupa_wlasny_alt_przed_grupowym(self):                     # F9, polityka 7
        d = Document()
        p1 = obraz_akapit(d, 901)
        p2 = obraz_akapit(d, 902)
        p3 = obraz_akapit(d, 903)
        pics = [p._p.find(f".//{{{PIC}}}pic") for p in (p1, p2, p3)]
        pic2, pic3 = copy.deepcopy(pics[1]), copy.deepcopy(pics[2])
        pic2.find(f".//{{{PIC}}}cNvPr").set("descr", "Opis drugiego obrazu.")
        for p in (p2, p3):
            d.element.body.remove(p._p)
        gd = p1._p.find(f".//{{{A}}}graphicData")
        gd.remove(pics[0])
        gd.set("uri", "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup")
        wgp = parse_xml(f'<wpg:wgp {NS}/>')
        for pic in (pics[0], pic2, pic3):
            wgp.append(pic)
        gd.append(wgp)
        docpr(p1).set("descr", "Schemat grupy.")
        w = dt.tresc_docx(otworz(d), ocr=Atrapa())
        self.assertEqual(w.akapity, ["Schemat grupy.", "Opis drugiego obrazu.", "Tekst obrazu 903."])
        self.assertEqual((w.z_alt, w.ocr_ok), ([1, 2], [3]))

    def test_ten_sam_obraz_ocr_raz(self):                               # F10, polityka 6
        d = Document()
        for i in range(3):
            d.add_paragraph(f"Slajd {i}.")
            d.add_paragraph().add_run().add_picture(png(1001))   # python-docx: jedna część
        ocr = Atrapa()
        w = dt.tresc_docx(otworz(d), ocr=ocr)
        self.assertEqual(ocr.wywolania, [(1, 1, 1)])
        self.assertEqual(w.powtorki, [(2, 1), (3, 1)])
        self.assertEqual(w.akapity.count("Tekst obrazu 1001."), 3)
        self.assertEqual(w.ocr_ok, [1])

    @unittest.skipUnless(sys.platform == "win32", "EMF rysuje GDI Windows")
    def test_prawdziwy_emf_idzie_do_ocr(self):                          # F11
        import ctypes
        from ctypes import wintypes
        gdi = ctypes.windll.gdi32
        gdi.CreateEnhMetaFileW.restype = wintypes.HDC
        gdi.CreateEnhMetaFileW.argtypes = [wintypes.HDC, wintypes.LPCWSTR, ctypes.c_void_p, wintypes.LPCWSTR]
        gdi.CloseEnhMetaFile.restype = wintypes.HANDLE
        gdi.CloseEnhMetaFile.argtypes = [wintypes.HDC]
        gdi.TextOutW.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.LPCWSTR, ctypes.c_int]
        gdi.DeleteEnhMetaFile.argtypes = [wintypes.HANDLE]
        gdi.Rectangle.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
        with tempfile.TemporaryDirectory() as tmp:
            sc = os.path.join(tmp, "w.emf")
            hdc = gdi.CreateEnhMetaFileW(None, sc, None, None)
            gdi.Rectangle(hdc, 0, 0, 600, 200)
            gdi.TextOutW(hdc, 20, 50, "EMF", 3)
            gdi.DeleteEnhMetaFile(gdi.CloseEnhMetaFile(hdc))
            dane = Path(sc).read_bytes()
        d = Document()
        czesc = d.part.related_parts[blip_rid(obraz_akapit(d, 1101))]
        czesc._blob = dane
        czesc.partname = PackURI("/word/media/image1.emf")
        rozmiary = []
        w = dt.tresc_docx(otworz(d), ocr=lambda o, n, k, r: rozmiary.append((o.mode, o.size)) or "EMF")
        self.assertEqual((w.format, w.bledy, w.ocr_ok), ([], [], [1]))
        self.assertEqual(rozmiary[0][0], "RGB")
        with Image.open(io.BytesIO(dane)) as im:
            self.assertGreater(rozmiary[0][1][0], im.size[0])   # render powyżej 72 dpi


def funkcje_notatnika(*nazwy, **globalne):
    """Funkcje z accessible_text_analyst.py (para jupytext) wyjęte przez AST —
    notatnika nie da się zaimportować (komórki mają skutki uboczne)."""
    import ast
    zrodlo = (KORZEN / "accessible_text_analyst.py").read_text(encoding="utf-8")
    drzewo = ast.parse(zrodlo)
    defs = [n for n in drzewo.body if isinstance(n, ast.FunctionDef) and n.name in nazwy]
    assert len(defs) == len(nazwy), nazwy
    ns = dict(globalne)
    exec(compile(ast.Module(body=defs, type_ignores=[]), "notatnik", "exec"), ns)
    return ns


class TestNotatnik(unittest.TestCase):
    """F1, F2: błąd przygotowania OCR w load_docx (`_docx_ocr`, `_print_docx_contents`)."""

    def test_blad_przygotowania_raz_i_powod_w_komunikacie(self):
        class DownloadFileException(Exception):   # rapidocr bez sieci: zwykły Exception
            pass
        wywolania = []

        def _ocr_plan(langs):
            wywolania.append(langs)
            raise DownloadFileException("no network")

        ns = funkcje_notatnika("_docx_ocr", "_print_docx_contents", _ocr_plan=_ocr_plan,
                               CORPUS_LANGS=["ru", "pl"], _ocr_obraz=None)
        d = Document()
        for szer in (11, 12, 13):
            obraz_akapit(d, szer)
        w = dt.tresc_docx(otworz(d), ocr=ns["_docx_ocr"])
        self.assertEqual(len(wywolania), 1)
        self.assertEqual(w.bez_ocr, [1, 2, 3])
        self.assertEqual(w.bledy, [])
        bufor = io.StringIO()
        stary, sys.stdout = sys.stdout, bufor
        try:
            ns["_print_docx_contents"](w)
        finally:
            sys.stdout = stary
        self.assertIn("Причина: DownloadFileException: no network", bufor.getvalue())


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
