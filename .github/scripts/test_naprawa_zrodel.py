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


def _font_ttf_litery(litery: str) -> bytes:
    """TrueType z glifami g1…gN → kolejne litery `litery` (tylko w cmap)."""
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
    fb.setupNameTable({"familyName": "Test", "styleName": "Regular"})
    fb.setupOS2()
    fb.setupPost()
    buf = io.BytesIO()
    fb.save(buf)
    return buf.getvalue()


def _pdf_strony(strony) -> bytes:
    """Wielostronicowy PDF; `strony` = [(litery fontu albo None, ciąg hex GID-ów)].

    Każda strona ma WŁASNY obiekt fontu Type0 o tej samej nazwie
    `/BCDEEE+Times` (jak kolejne podzbiory Worda w scalonym PDF-ie), z uciętą
    mapą ToUnicode (tylko GID 1) jak słownik — reszta glifów to „(cid:N)”
    (bez ToUnicode pdfminer sam czytałby `cmap` fontu). None = strona pusta.
    """
    obiekty = [None, None]                       # 1 katalog, 2 drzewo stron
    kids = []
    for wpis in strony:
        litery, gidy = wpis[0], wpis[1]
        opcje = wpis[2] if len(wpis) > 2 else {}
        nazwa_fontu = opcje.get("nazwa", b"BCDEEE+Times")
        nr = len(obiekty) + 1
        if litery is None:
            tresc = b""
            obiekty += [b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents %d 0 R >>" % (nr + 1),
                        b"<< /Length 0 >>\nstream\n\nendstream"]
        else:
            font = opcje.get("font") or _font_ttf_litery(litery)
            cmap = (b"/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
                    b"/CMapName /Test def\n1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n"
                    b"1 beginbfchar\n<0001> <%04X>\nendbfchar\n" % ord(opcje.get("pierwsza", litery[0]))
                    + b"endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n")
            tresc = (b"BT /F1 12 Tf 72 700 Td " + (opcje.get("tj") or b"<" + gidy.encode() + b"> Tj")
                     + b" ET")
            obiekty += [
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>" % (nr + 2, nr + 1),
                b"<< /Length %d >>\nstream\n" % len(tresc) + tresc + b"\nendstream",
                b"<< /Type /Font /Subtype /Type0 /BaseFont /" + nazwa_fontu + b" /Encoding /Identity-H "
                b"/DescendantFonts [%d 0 R] /ToUnicode %d 0 R >>" % (nr + 3, nr + 6),
                b"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /" + nazwa_fontu + b" "
                b"/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> "
                b"/FontDescriptor %d 0 R /DW 600 /CIDToGIDMap /Identity >>" % (nr + 4),
                b"<< /Type /FontDescriptor /FontName /BCDEEE+Times /Flags 4 /FontBBox [0 -200 1000 800] "
                b"/ItalicAngle 0 /Ascent 800 /Descent -200 /CapHeight 700 /StemV 80 /FontFile2 %d 0 R >>" % (nr + 5),
                b"<< /Length %d /Length1 %d >>\nstream\n" % (len(font), len(font)) + font + b"\nendstream",
                b"<< /Length %d >>\nstream\n" % len(cmap) + cmap + b"\nendstream",
            ]
        kids.append(b"%d 0 R" % nr)
    obiekty[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    obiekty[1] = b"<< /Type /Pages /Kids [" + b" ".join(kids) + b"] /Count %d >>" % len(kids)
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


class TestAudytPdf(unittest.TestCase):
    """Przypadki z audytu przed wydaniem (2026-10-20)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def zapisz(self, dane, nazwa="a.pdf"):
        p = Path(self.tmp.name) / nazwa
        p.write_bytes(dane)
        return p

    def test_ta_sama_nazwa_rozne_fonty(self):
        # M2: dwa podzbiory „BCDEEE+Times” (КОТЫ / ДОМА) — każda strona swoim fontem.
        import pdfplumber
        sciezka = self.zapisz(_pdf_strony([("КОТЫ", "00010002000300040001000200030004"),
                                           ("ДОМА", "00010002000300040001000200030004")]))
        pamiec, wynik = {}, []
        with pdfplumber.open(sciezka) as pdf:
            for s in pdf.pages:
                o = n.napraw_strone(s, pamiec)
                wynik.append((s.extract_text(), o.naprawiona))
        self.assertEqual(wynik, [("КОТЫКОТЫ", True), ("ДОМАДОМА", True)])

    def test_bramka_strony_ocr_nie_odmawiaja(self):
        # M3: 5 stron bez warstwy tekstu + 10 z tekstem; podglądy pochodzą z OCR.
        import zrodlo_raportu
        tekst = ("КОТЫ", "0001000200030004" * 6)
        sciezka = self.zapisz(_pdf_strony([(None, "")] * 5 + [tekst] * 10))
        ocr = ["Совсем другой текст, który rozpoznał OCR na stronie skanu"]
        t = zrodlo_raportu.sprawdz_tresc(str(sciezka), ocr)
        self.assertEqual((t.stan, t.powod), ("niesprawdzalna", "ocr"))
        # Kontrola: bez stron-obrazów ten sam podgląd to dowód rozjazdu.
        bez_obrazow = self.zapisz(_pdf_strony([tekst] * 10), "b.pdf")
        self.assertEqual(zrodlo_raportu.sprawdz_tresc(str(bez_obrazow), ocr).stan, "rozjazd")

    def test_bramka_plik_nieczytelny(self):
        # L1: podmieniony / uszkodzony plik — brak wiedzy, nie wyjątek i nie odmowa.
        import zrodlo_raportu
        sciezka = self.zapisz(b"to nie jest PDF " * 50)
        t = zrodlo_raportu.sprawdz_tresc(str(sciezka), ["Совсем другой текст о манипуляциях"])
        self.assertEqual((t.stan, t.powod), ("niesprawdzalna", "unreadable"))



def _font_ttf_glify(nazwy, cmap) -> bytes:
    """TrueType z glifami `nazwy` (po .notdef) i podaną mapą {kod: nazwa}."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    kolejnosc = [".notdef"] + list(nazwy)
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(kolejnosc)
    fb.setupCharacterMap(cmap)
    glify = {}
    for nazwa in kolejnosc:
        pen = TTGlyphPen(None)
        pen.moveTo((50, 0)); pen.lineTo((50, 500)); pen.lineTo((450, 500)); pen.lineTo((450, 0))
        pen.closePath()
        glify[nazwa] = pen.glyph()
    fb.setupGlyf(glify)
    fb.setupHorizontalMetrics({k: (600, 50) for k in kolejnosc})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "Test", "styleName": "Regular"})
    fb.setupOS2()
    fb.setupPost()
    buf = io.BytesIO()
    fb.save(buf)
    return buf.getvalue()


class TestLigaturyIPustaNazwa(unittest.TestCase):
    """Uzupełnienie audytu: glif-ligatura spoza cmap (agl daje 3 znaki) i pusty BaseFont."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # GID 1 „o” (ToUnicode), 2 „f_f_i” (tylko nazwa post → „ffi”), 3 „c”, 4 „e”.
        self.font = _font_ttf_glify(["o", "f_f_i", "c", "e"], {ord("o"): "o", ord("c"): "c", ord("e"): "e"})

    def pdf(self, gidy="", nazwa=b"BCDEEE+Times", tj=b""):
        p = Path(self.tmp.name) / "l.pdf"
        p.write_bytes(_pdf_strony([("o", gidy, {"font": self.font, "pierwsza": "o", "nazwa": nazwa, "tj": tj})]))
        return p

    def test_ligatura_naprawiona_bez_wyjatku(self):
        import pdfplumber
        with pdfplumber.open(self.pdf("0001000200030004" * 3)) as pdf:
            s = pdf.pages[0]
            o = n.napraw_strone(s)
            self.assertEqual(s.extract_text(), "office" * 3)
            # Licznik bramki: jeden glif = jedna pozycja, niezależnie od długości tekstu glifu.
            self.assertEqual((o.litery, o.znaczniki, o.nierozwiazane), (12, 9, 0))
            self.assertTrue(o.naprawiona)

    def test_ligatura_w_rozstrzeleniu(self):
        # „o ffi c e” rozstrzelone: „ffi” nie jest literą pojedynczą, więc nie wchodzi
        # do serii i nie psuje geometrii ani decyzji modułu.
        import pdfplumber
        import czyszczenie_tekstu as ct
        tj = (b"[<0003> -300 <0001> -300 <0004> -300 <0003> -300 <0002> -300 "
              b"<0003> -300 <0001> -300 <0004> -300 <0003>] TJ")
        with pdfplumber.open(self.pdf(tj=tj)) as pdf:
            s = pdf.pages[0]
            n.napraw_strone(s)
            serie = n.serie_rozstrzelone(s)
            tekst = s.extract_text()
        self.assertIn("ffi", tekst)
        self.assertTrue(all(all(ct.litera_pojedyncza(l) for l in x.litery) for x in serie))
        oznaczony, _ = n.oznacz_granice(tekst, serie)
        wynik, _ = ct.scal_rozstrzelone([oznaczony, "coec"], granica=n.ZNACZNIK_GRANICY)
        self.assertEqual(n._ct.bez_laczacych(wynik[0]).replace(" ", ""), tekst.replace(" ", ""))

    def test_pusty_basefont_zgloszony_nie_zgadywany(self):
        import pdfplumber
        with pdfplumber.open(self.pdf("0001000200030004" * 3, nazwa=b"")) as pdf:
            s = pdf.pages[0]
            o = n.napraw_strone(s)
            tekst = s.extract_text()
        # Bez nazwy nie da się powiązać znaku z fontem strony — nic nie zgadujemy.
        self.assertEqual(o.nierozwiazane, o.znaczniki)
        self.assertTrue(o.do_zgloszenia)
        self.assertNotIn("ffi", tekst)


if __name__ == "__main__":
    unittest.main()
