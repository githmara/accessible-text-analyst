"""Testy naprawa_zrodel.py: bramka i naprawa warstwy tekstu PDF, przeniesienia DOCX.

PDF jest syntetyczny i odtwarza przypadek słownika z 2026-10-20: font
Type0/Identity-H z osadzonym TrueType i UCIĘTĄ mapą ToUnicode (tylko „А”).
Znaki odzyskuje się z `cmap` fontu, z nazw `post` (glif bez wpisu w `cmap`),
akcent U+0301 dokleja się do poprzedniej litery, a glif bez żadnej informacji
zostaje nierozwiązany i strona trafia do zgłoszenia.

Uruchom:  .venv/Scripts/python .github/scripts/test_naprawa_zrodel.py
(wymaga pdfplumber i fonttools — jak notatnik).
"""
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import naprawa_zrodel as n  # noqa: E402

A, BE, VE, AKCENT = chr(0x410), chr(0x411), chr(0x412), chr(0x301)


def _font_ttf() -> bytes:
    """TrueType: .notdef, A1→А, B1→Б, acc→U+0301 (w cmap), uni0412 (tylko post), glyph5."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    nazwy = [".notdef", "A1", "B1", "acc", "uni0412", "glyph5"]
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(nazwy)
    fb.setupCharacterMap({0x410: "A1", 0x411: "B1", 0x301: "acc"})
    glify = {}
    for nazwa in nazwy:
        pen = TTGlyphPen(None)
        pen.moveTo((50, 0)); pen.lineTo((50, 500)); pen.lineTo((450, 500)); pen.lineTo((450, 0))
        pen.closePath()
        glify[nazwa] = pen.glyph()
    fb.setupGlyf(glify)
    fb.setupHorizontalMetrics({k: (0 if k == "acc" else 600, 50) for k in nazwy})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "Test", "styleName": "Regular"})
    fb.setupOS2()
    fb.setupPost()
    buf = io.BytesIO()
    fb.save(buf)
    return buf.getvalue()


def _pdf(gidy: str, to_unicode: bool = True, pelna_mapa: bool = False) -> bytes:
    """Jednostronicowy PDF; `gidy` — ciąg hex kodów Identity-H w Tj."""
    font = _font_ttf()
    if pelna_mapa:
        cmap_body = (b"5 beginbfchar\n<0001> <0410>\n<0002> <0411>\n<0003> <0301>\n"
                     b"<0004> <0412>\n<0005> <0413>\nendbfchar\n")
    else:
        cmap_body = b"1 beginbfchar\n<0001> <0410>\nendbfchar\n"
    cmap = (b"/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
            b"/CMapName /Test def\n1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n"
            + cmap_body + b"endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n")
    tresc = b"BT /F1 12 Tf 72 700 Td <" + gidy.encode() + b"> Tj ET"
    obiekty = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(tresc) + tresc + b"\nendstream",
        b"<< /Type /Font /Subtype /Type0 /BaseFont /ABCDEF+Test /Encoding /Identity-H "
        b"/DescendantFonts [6 0 R]" + (b" /ToUnicode 8 0 R" if to_unicode else b"") + b" >>",
        b"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /ABCDEF+Test "
        b"/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> "
        b"/FontDescriptor 7 0 R /DW 600 /W [3 [0]] /CIDToGIDMap /Identity >>",
        b"<< /Type /FontDescriptor /FontName /ABCDEF+Test /Flags 4 /FontBBox [0 -200 1000 800] "
        b"/ItalicAngle 0 /Ascent 800 /Descent -200 /CapHeight 700 /StemV 80 /FontFile2 9 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(cmap) + cmap + b"\nendstream",
        b"<< /Length %d /Length1 %d >>\nstream\n" % (len(font), len(font)) + font + b"\nendstream",
    ]
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


class TestPdf(unittest.TestCase):
    def setUp(self):
        # addCleanup działa LIFO: katalog znika po zamknięciu PDF (Windows
        # nie usunie otwartego pliku).
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def strona(self, pdf_bytes):
        import pdfplumber
        sciezka = Path(self.tmp.name) / "t.pdf"
        sciezka.write_bytes(pdf_bytes)
        pdf = pdfplumber.open(sciezka)
        self.addCleanup(pdf.close)
        return pdf.pages[0]

    def test_bez_naprawy_pdfplumber_daje_znaczniki(self):
        tekst = self.strona(_pdf("0001000200030004")).extract_text()
        self.assertEqual(tekst.count("(cid:"), 3)

    def test_naprawa_cmap_post_i_akcent(self):
        s = self.strona(_pdf("0001000200030004"))
        o = n.napraw_strone(s)
        self.assertEqual((o.znaczniki, o.nierozwiazane), (3, 0))
        self.assertTrue(o.znieksztalcona and o.naprawiona and not o.do_zgloszenia)
        # Б z cmap, U+0301 doklejony do Б bez spacji, В z nazwy post „uni0412”.
        self.assertEqual(s.extract_text(), A + BE + AKCENT + VE)

    def test_glif_bez_informacji_zostaje_do_zgloszenia(self):
        s = self.strona(_pdf("00010002000400050005"))
        o = n.napraw_strone(s)
        self.assertEqual(o.nierozwiazane, 2)
        self.assertTrue(o.znieksztalcona and o.do_zgloszenia and not o.naprawiona)

    def test_pelna_mapa_nic_nie_zmienia(self):
        s = self.strona(_pdf("000100020004", pelna_mapa=True))
        o = n.napraw_strone(s)
        self.assertEqual((o.znaczniki, o.nierozwiazane), (0, 0))
        self.assertFalse(o.znieksztalcona)
        self.assertEqual(s.extract_text(), A + BE + VE)

    def test_mapa_glifow_nieczytelny_font(self):
        self.assertEqual(n.mapa_glifow(b""), {})
        self.assertEqual(n.mapa_glifow(b"to nie jest font"), {})

    def test_prog_bramki(self):
        self.assertFalse(n.czy_znieksztalcona(1000, 2))     # < 3 znaczników
        self.assertFalse(n.czy_znieksztalcona(1000, 19))    # < 2% liter
        self.assertTrue(n.czy_znieksztalcona(1000, 20))
        self.assertTrue(n.czy_znieksztalcona(3, 3))

    def test_zakresy_stron(self):
        self.assertEqual(n.zakresy_stron([1, 2, 3, 7, 9, 10]), "2–4, 8, 10–11")
        self.assertEqual(n.zakresy_stron([]), "")


class TestDocx(unittest.TestCase):
    # Tło „słownika”: formy poświadczone gdzie indziej i spójnik z czołówki.
    TLO = (["посвященного издания", "коронавирус и пандемия"] * 3
           + ["ковид-контакт", "ковид", "и"] * 2)

    def sklej(self, *akapity):
        wynik, licz = n.sklej_przeniesienia(list(akapity) + self.TLO)
        return wynik[:len(akapity)], licz

    def test_przeniesienie_poswiadczone(self):
        self.assertEqual(self.sklej("издания, по- священного теме")[0], ["издания, посвященного теме"])

    def test_przeniesienie_nieposwiadczone(self):
        self.assertEqual(self.sklej("заканчи- вался срок")[0], ["заканчивался срок"])

    def test_zawieszony_lacznik_zostaje(self):
        for tekst in ("двух- и трёхкомнатный", "пред- и постпандемийный"):
            wynik, licz = self.sklej(tekst)
            self.assertEqual(wynik, [tekst])
            self.assertEqual(licz["zostaw"], 1)

    def test_myslniki_i_lacznik_bez_spacji_nietkniete(self):
        tekst = "слово — слово, 1990–2000, по-английски, слово - слово"
        self.assertEqual(self.sklej(tekst)[0], [tekst])

    def test_czlon_zlozenia_zachowuje_lacznik(self):
        self.assertEqual(self.sklej("с ковид- трупами")[0], ["с ковид-трупами"])

    def test_wielka_litera_i_inne_pismo(self):
        self.assertEqual(self.sklej("Мать- Природа")[0], ["Мать-Природа"])
        for tekst in ("IT- индустрии", "root- корневой", "РЕКУРСИЯ- То же", "Приставка е- в слове"):
            self.assertEqual(self.sklej(tekst)[0], [tekst])

    def test_przez_granice_akapitu_tylko_z_dowodem(self):
        akapity = ["издания, по-", "священного теме", "", "заканчи-", "вался срок",
                   "раздел -И-", "Не хвались"] + self.TLO
        style = ["Body Text"] * len(akapity)
        wynik, sklejone, zostawione = n.sklej_przez_akapity(akapity, style)
        self.assertEqual(wynik[0], "издания, посвященного теме")
        self.assertEqual(wynik[2:6], ["заканчи-", "вался срок", "раздел -И-", "Не хвались"])
        self.assertEqual((sklejone, zostawione), (1, 2))

    def test_przez_granice_inny_styl_zostaje(self):
        akapity = ["издания, по-", "священного теме"] + self.TLO
        style = ["Body Text", "Heading 3"] + ["Body Text"] * len(self.TLO)
        wynik, sklejone, _ = n.sklej_przez_akapity(akapity, style)
        self.assertEqual(sklejone, 0)
        self.assertEqual(wynik[:2], akapity[:2])


if __name__ == "__main__":
    unittest.main()
