"""Testy naprawa_zrodel.py: bramka i naprawa warstwy tekstu PDF, czyszczenie tekstu
(U+F020, rozstrzelenia, przeniesienia — wspólna specyfikacja z Reżyserem) oraz
czytanie źródła przez bramkę raportu (zrodlo_raportu.py).

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


class TestPrzeniesienia(unittest.TestCase):
    """Wspólna specyfikacja z Reżyserem — wektory obowiązkowe, identyczne w obu projektach."""

    def jeden(self, tekst, *tlo):
        wynik, licz = n.sklej_przeniesienia([tekst, *tlo])
        return wynik[0], licz

    def test_wektory_obowiazkowe(self):
        przypadki = [
            (("издания, по- священного теме", "посвященное издание"), "издания, посвященного теме", 3),
            (("государст- венный",), "государственный", 3),
            (("бело- голубых", "голубых тонов"), "бело- голубых", 4),
            (("двух- и трёхкомнатный", "и так и этак"), "двух- и трёхкомнатный", 4),
            (("с ковид- диссидентов", "о ковид-диссидентов"), "с ковид-диссидентов", 2),
            (("по-английски",), "по-английски", None),
            (("gazeta-obozrenie- birulevo.ru",), "gazeta-obozrenie- birulevo.ru", "wykluczone"),
            (("ПО- СВЯЩЕННОГО",), "ПО- СВЯЩЕННОГО", "wykluczone"),
        ]
        for (tekst, *tlo), oczekiwany, regula in przypadki:
            with self.subTest(tekst=tekst):
                wynik, licz = self.jeden(tekst, *tlo)
                self.assertEqual(wynik, oczekiwany)
                if regula is None:
                    self.assertEqual(sum(licz.values()), 0)
                else:
                    self.assertEqual(licz[regula], 1)

    def test_regula_1_przed_2(self):
        self.assertEqual(self.jeden("корона- вирус", "коронавирус", "корона-вирус")[0], "коронавирус")

    def test_kandydat_sam_sie_nie_liczy(self):
        # Jedyne wystąpienie „венный” to prawy fragment kandydata — reguła 3, nie 4.
        self.assertEqual(self.jeden("государст- венный")[1][3], 1)

    def test_interpunkcja_zdania_to_nie_adres(self):
        self.assertEqual(self.jeden("«мелодра- мы».")[0], "«мелодрамы».")
        self.assertEqual(self.jeden("vvs- syzran.ru 09.06.2020")[0], "vvs- syzran.ru 09.06.2020")

    def test_rozne_pisma_i_myslniki(self):
        tekst = "IT- индустрии; слово — слово, 1990–2000, слово - слово"
        self.assertEqual(self.jeden(tekst)[0], tekst)

    def test_wiele_spacji(self):
        self.assertEqual(self.jeden("выдержи-   вают")[0], "выдерживают")

    def test_przez_granice_akapitu(self):
        akapity = ["издания, по-", "священного теме", "", "раздел -И-", "Не хвались",
                   "государст-", "", "венный", "бело-", "голубых", "голубых тонов"]
        style = ["Body Text"] * len(akapity)
        wynik, licz = n.sklej_przez_akapity(akapity, style)
        self.assertEqual(wynik[0], "издания, посвященного теме")
        self.assertIn("раздел -И-", wynik)          # wielka litera: wykluczone
        self.assertIn("государст-", wynik)          # pusty akapit między: bez bezpiecznika
        self.assertIn("бело-", wynik)               # reguła 4
        self.assertEqual((licz[3], licz[4], licz["wykluczone"], licz["bez_bezpiecznika"]), (1, 1, 1, 1))

    def test_przez_granice_inny_styl(self):
        wynik, licz = n.sklej_przez_akapity(["издания, по-", "священного теме"], ["Body Text", "Heading 3"])
        self.assertEqual(licz["bez_bezpiecznika"], 1)
        self.assertEqual(wynik, ["издания, по-", "священного теме"])


class TestRozstrzeleniaIPua(unittest.TestCase):
    def test_seria_poswiadczona_sklejona(self):
        wynik, s, p = n.sklej_rozstrzelenia(["дается у с т о й ч и в о е сочетание", "устойчивое"])
        self.assertEqual((wynik[0], s, p), ("дается устойчивое сочетание", 1, 0))

    def test_seria_nieposwiadczona_zostaje(self):
        tekst = "Ж ё л т а я з о н а"
        self.assertEqual(n.sklej_rozstrzelenia([tekst, "жёлтая зона"])[0][0], tekst)

    def test_dwie_spacje_rozdzielaja_slowa(self):
        wynik, s, _ = n.sklej_rozstrzelenia(["Ж ё л т а я  з о н а", "жёлтая зона"])
        self.assertEqual((wynik[0], s), ("Жёлтая  зона", 2))

    def test_akcent_w_serii(self):
        wynik, s, _ = n.sklej_rozstrzelenia(["з о" + AKCENT + " н а", "зона"])
        self.assertEqual(wynik[0], "зо" + AKCENT + "на")

    def test_jednoliterowe_slowa_nie_sklejane(self):
        # „а и в с” — cztery prawdziwe słowa jednoliterowe; „аивс” nie jest słowem.
        tekst = "а и в с о к у я"
        self.assertEqual(n.sklej_rozstrzelenia([tekst, "и в с а"])[0][0], tekst)

    def test_trzy_litery_to_nie_seria(self):
        self.assertEqual(n.sklej_rozstrzelenia(["в с е", "все"])[0][0], "в с е")

    def test_spacja_pua(self):
        pua = chr(0xF020)
        wynik, cz = n.oczysc_akapity([pua + " " + pua + "\t— вариант"])
        self.assertEqual((wynik[0], cz.spacje_pua), ("   \t— вариант", 2))


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
