"""Testy naprawa_zrodel.py: bramka i naprawa warstwy tekstu PDF, granice rozstrzeleń
z geometrii podane wspólnemu modułowi czyszczenie_tekstu (jego własne wektory:
czyszczenie_tekstu_wektory.py) oraz czytanie źródła przez bramkę raportu.

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


def _pdf(gidy: str, to_unicode: bool = True, pelna_mapa: bool = False, tj: bytes = b"") -> bytes:
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
    tresc = b"BT /F1 12 Tf 72 700 Td " + (tj or b"<" + gidy.encode() + b"> Tj") + b" ET"
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


class TestRozstrzeleniaGeometria(unittest.TestCase):
    """Granice słów w rozstrzeleniu PDF z odstępów (nie z tekstu)."""

    def test_granice_z_odstepow_i_akcent(self):
        import pdfplumber
        # 12 pt, glif 600/1000 → 7,2 pt; -300 → odstęp 3,6 pt, -900 → 10,8 pt.
        # „А Б В А” | „Б́ В А Б”: akcent (glif 3, szerokość 0) po Б, odstęp za nim
        # 7,2 pt = 2× mediana — to NIE granica (rozstrzelenie za akcentem).
        tj = (b"[<0001> -300 <0002> -300 <0004> -300 <0001> -900 "
              b"<0002> -300 <0003> -300 <0004> -300 <0001> -300 <0002>] TJ")
        with tempfile.TemporaryDirectory() as tmp:
            sciezka = Path(tmp) / "r.pdf"
            sciezka.write_bytes(_pdf("", tj=tj))
            with pdfplumber.open(sciezka) as pdf:
                s = pdf.pages[0]
                n.napraw_strone(s)
                serie = n.serie_rozstrzelone(s)
                tekst = s.extract_text()
        self.assertEqual(len(serie), 1)
        self.assertEqual(serie[0].slowa(), [A + BE + VE + A, BE + AKCENT + VE + A + BE])
        self.assertEqual(serie[0].tekst(), tekst)     # seria stoi w tekście 1:1
        self.assertEqual(len(serie[0].litery), 8)
        # Geometria → znacznik granicy → decyzja wspólnego modułu.
        import czyszczenie_tekstu as ct
        oznaczony, n_ozn = n.oznacz_granice(tekst, serie)
        self.assertEqual(n_ozn, 1)
        slowa_dok = A + BE + VE + A + " " + BE + VE + A + BE
        wynik, licz = ct.scal_rozstrzelone([oznaczony, slowa_dok], granica=n.ZNACZNIK_GRANICY)
        self.assertEqual(wynik[0], A + BE + VE + A + " " + BE + AKCENT + VE + A + BE)
        self.assertEqual(licz["sklejone"], 2)
        # Bez geometrii (sam tekst) seria jest jednym ciągiem i nie jest słowem.
        self.assertEqual(ct.scal_rozstrzelone([tekst, slowa_dok])[0][0], tekst)

    def test_strona_pdf_spacja_symbol_i_mojibake(self):
        from shamanic_locale import alfabety_paczek
        moj = "Áèáëèîòåêà èíñòèòóòà ÿçûêîçíàíèÿ ïðèíÿëà íîâûå êíèãè"
        tekst, info = n.oczysc_strone_pdf(moj + "\n33" + chr(0xF020) + "x", alfabety_paczek())
        self.assertTrue(tekst.startswith("Библиотека института"))
        self.assertEqual((info["spacja_symbol"], info["mojibake_linie"]), (1, 1))


class TestBramkaZrodla(unittest.TestCase):
    """zrodlo_raportu czyta PDF tą samą drogą co load_pdf (naprawa z fontu)."""

    def setUp(self):
        import zrodlo_raportu
        self.z = zrodlo_raportu
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def pdf(self, gidy):
        p = Path(self.tmp.name) / "s.pdf"
        p.write_bytes(_pdf(gidy))
        return str(p)

    def test_podglad_naprawionej_strony_pasuje(self):
        # 20 liter „АБВ…” — tyle, ile podgląd notatnika po naprawie.
        sciezka = self.pdf("000100020004" * 7)
        podglad = (A + BE + VE) * 7
        t = self.z.sprawdz_tresc(sciezka, [podglad])
        self.assertEqual((t.stan, t.znalezione), ("zgodna", 1))

    def test_obcy_podglad_to_rozjazd(self):
        t = self.z.sprawdz_tresc(self.pdf("000100020004" * 7), ["Совсем другой текст о манипуляциях"])
        self.assertEqual(t.stan, "rozjazd")

    def test_strona_nienaprawiona_niesprawdzalna(self):
        t = self.z.sprawdz_tresc(self.pdf("0001000500050005" * 5), [(A + BE + VE) * 7])
        self.assertEqual((t.stan, t.powod), ("niesprawdzalna", "garbled"))


if __name__ == "__main__":
    unittest.main()
