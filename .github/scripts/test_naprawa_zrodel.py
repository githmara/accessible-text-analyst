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


class TestStrzalkiSymbol(unittest.TestCase):
    """2.0 (sonda biuletynów 2026-11-13): strzałki trendu fontu Symbol w PUA."""

    def test_tylko_font_symbol(self):
        class Strona:
            chars = [{"text": chr(0xF0DD), "fontname": "BCDKEE+SymbolMT"},
                     {"text": chr(0xF0DF), "fontname": "Symbol"},
                     {"text": chr(0xF0DF), "fontname": "ABCDEF+Wingdings-Regular"},
                     {"text": "a", "fontname": "BCDKEE+SymbolMT"}]
        s = Strona()
        o = n.napraw_strone(s)
        self.assertEqual([z["text"] for z in s.chars],
                         [chr(0x21D1), chr(0x21D3), chr(0xF0DF), "a"])
        self.assertEqual(o.znaczniki, 0)


class TestZnakZastepczy(unittest.TestCase):
    """2.0 (sonda 2026-11-13): ReportLab zastąpił litery spoza WinAnsi glifem ■ ZapfDingbats."""

    Z = chr(0x25A0)

    def _slownik(self, rangi):
        from slowniki_jezykow import Slownik
        alfabet = frozenset("abcdefghijklmnoprstuwyzóąćęłńśźż") | frozenset("ABCDEFGHIJKLMNOPRSTUWYZÓĄĆĘŁŃŚŹŻ")
        return Slownik("pl", alfabet, rangi.__contains__, "test", ranga=rangi.get)

    def test_zapf_n_staje_sie_kwadratem(self):
        class Strona:
            chars = [{"text": "n", "fontname": "ZapfDingbats"}, {"text": "n", "fontname": "Helvetica"}]
        s = Strona()
        n.napraw_strone(s)
        self.assertEqual([z["text"] for z in s.chars], [self.Z, "n"])

    def test_kandydaci_z_alfabetu_spoza_winansi(self):
        self.assertEqual(n.litery_spoza_winansi(["AĄBÓŁ", "żx"]), "ąłż")   # ó jest w WinAnsi

    def test_rekonstrukcja(self):
        Z = self.Z
        sl = [self._slownik({"się": 7, "sił": 1860, "został": 111, "zostać": 717, "wstęp": 8914,
                             "wstąp": 92769, "łódź": 900, "Łódź": 300, "środowiska": 1027})]
        tekst = (f"Ma si{Z} dobrze. {Z}rodowiska i zosta{Z} oraz WST{Z}P, "
                 f"dalej {Z}ód{Z} i ({Z}{Z}{Z}) oraz xyz{Z}q.")
        (wynik,), info = n.rekonstruuj_zastepcze([tekst], sl, "ąćęłńśźż")
        self.assertEqual(wynik, f"Ma się dobrze. Środowiska i zosta{Z} oraz WSTĘP, "
                                f"dalej Łódź i ({Z}{Z}{Z}) oraz xyz{Z}q.")
        self.assertEqual(info, {"odtworzone": 4, "niejednoznaczne": 1, "nieznane": 1, "poza_slowem": 3})

    def test_wielkie_litery_z_kontekstu(self):
        # Audyt 2.0: strona zaczęta w środku zdania dostawała wielką literę,
        # krótkie słowo w wersalikach małą, a dwukropek liczył się jak kropka.
        Z = self.Z
        sl = [self._slownik({"że": 3, "życie": 40})]
        strony = ["Powiedział wczoraj, ", f"{Z}e nie wie.", f"WIEM, {Z}E TAK", f"badania: {Z}ycie."]
        wynik, _ = n.rekonstruuj_zastepcze(strony, sl, "ąćęłńśźż")
        self.assertEqual(wynik[1:], ["że nie wie.", "WIEM, ŻE TAK", "badania: życie."])
        (pierwsza,), _ = n.rekonstruuj_zastepcze([f"{Z}e to prawda."], sl, "ąćęłńśźż")
        self.assertEqual(pierwsza, "Że to prawda.")          # początek tekstu = początek zdania

    def test_bez_rang_nie_rozstrzyga(self):
        from slowniki_jezykow import Slownik
        Z = self.Z
        sl = [Slownik("fi", frozenset("abcdefghijklmnoprstuvyzäöšž"), {"sää", "söö"}.__contains__, "t")]
        (wynik,), info = n.rekonstruuj_zastepcze([f"s{Z}{Z}"], sl, "šž")
        self.assertEqual(info["nieznane"] + info["niejednoznaczne"], 1)
        self.assertEqual(wynik, f"s{Z}{Z}")


class TestWyprostowanie(unittest.TestCase):
    """2.0: obrót ~1e-8 rad (wykresy biuletynów) robił z liter tekst pionowy."""

    def test_tylko_kat_bliski_zera(self):
        class Strona:
            chars = [{"upright": False, "matrix": (1.114, -7.6e-08, -7.9e-09, 1.114, 0, 0)},
                     {"upright": False, "matrix": (0.0, 1.0, -1.0, 0.0, 0, 0)},      # 90°: oś wykresu
                     {"upright": False, "matrix": (1.0, 0.05, 0.05, 1.0, 0, 0)},     # ~2,9°
                     {"upright": True, "matrix": (1.0, 0.0, 0.0, 1.0, 0, 0)}]
        s = Strona()
        self.assertEqual(n.wyprostuj_znaki(s), 1)
        self.assertEqual([z["upright"] for z in s.chars], [True, False, False, True])


def _pdf_helvetica(tresc: bytes) -> bytes:
    """Jednostronicowy PDF 600×800 z fontem standardowym Helvetica (metryki w pdfminerze)."""
    obiekty = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 800] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(tresc) + tresc + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
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


def _napis(x: float, y: float, tekst: str, rozmiar: int = 9) -> bytes:
    return b"BT /F1 %d Tf %.1f %.1f Td (%s) Tj ET\n" % (rozmiar, x, y, tekst.encode("latin-1"))


PROZA_KOLUMNY = ["Markets continued the rally that started a month",
                 "earlier, while investors kept expecting a deal",
                 "between the parties to reopen shipping routes."]


def _pdf_tabela_liczbowa_i_naglowek() -> bytes:
    """Audyt 2.0: (a) wykres + nagłówek sekcji 12 pt tuż pod nim (dy ~ 10 pt) obok
    prozy 9 pt; (b) tabela 36 obramowanych komórek z liczbami i nazwami wierszy."""
    t = bytearray()
    for i, linia in enumerate(PROZA_KOLUMNY):
        t += _napis(40, 760 - 12 * i, linia)
    t += b"0.5 w\n"
    for i in range(31):
        t += b"350 %d m 550 %d l S\n" % (600 + 3 * i, 600 + 3 * i)
    t += b"350 600 m 350 690 l S\n"
    t += _napis(352, 592, "0 10 20 30", 7)
    t += _napis(350, 578, "Wnioski koncowe", 12)                     # nagłówek: drukiem większym
    for k in range(36):
        x, y = 40 + 85 * (k % 6), 100 + 18 * (k // 6)
        t += b"%d %d 85 18 re S\n" % (x, y)
        t += _napis(x + 3, y + 5, "Przychody" if k % 6 == 0 else str(1000 + 37 * k), 8)
    return _pdf_helvetica(bytes(t))


def _pdf_z_wykresem(tabela_tekstowa: bool = False) -> bytes:
    """Kolumna prozy (x 40–300) obok wykresu (x 350–550, y 500–650): 31 linii siatki,
    oś, 4 słupki, etykieta w środku, kategoria tuż na lewo od osi, liczby osi,
    legenda pod spodem i dłuższa linia źródła dalej. `tabela_tekstowa` dokłada
    tabelę 35 komórek z tekstem — dużo obiektów, ale za dużo liter na wykres."""
    t = bytearray()
    for i, linia in enumerate(PROZA_KOLUMNY):
        t += _napis(40, 640 - 12 * i, linia)
    t += b"0.5 w\n"
    for i in range(31):                                   # siatka pozioma
        t += b"350 %d m 550 %d l S\n" % (500 + 5 * i, 500 + 5 * i)
    t += b"350 500 m 350 650 l S\n"                       # oś pionowa łączy siatkę w skupisko
    for i, h in enumerate((40, 90, 60, 120)):             # słupki
        t += b"%d 500 20 %d re f\n" % (380 + 40 * i, h)
    t += _napis(470, 630, "Alpha")                        # etykieta w obrysie
    t += _napis(330, 560, "Beta", 8)                      # kategoria tuż przy osi (szer. 16,5 pt → dx 3,5 pt)
    t += _napis(352, 490, "10", 7) + _napis(392, 490, "20", 7) + _napis(432, 490, "30", 7)
    t += _napis(380, 478, "May 26", 7)                    # legenda (dy ~ 15 pt)
    t += _napis(350, 455, "Source: Bloomberg data for June 2026", 7)   # proza obok: zostaje
    if tabela_tekstowa:
        for k in range(35):
            x, y = 40 + 80 * (k % 7), 100 + 20 * (k // 7)
            t += b"%d %d 80 20 re S\n" % (x, y) + _napis(x + 4, y + 6, "Lorem ipsum")
    return _pdf_helvetica(bytes(t))


class TestEtykietyWykresow(unittest.TestCase):
    """2.0: etykiety wykresów poza NLP, ale w tekście do odczytu (decyzja 2026-11-15)."""

    def _strona(self, tabela_tekstowa=False):
        import pdfplumber
        with tempfile.TemporaryDirectory() as tmp:
            sciezka = Path(tmp) / "w.pdf"
            sciezka.write_bytes(_pdf_z_wykresem(tabela_tekstowa))
            with pdfplumber.open(sciezka) as pdf:
                s = pdf.pages[0]
                obszary = n.obszary_wykresow(s)
                ile = n.oznacz_wykresy(s)
                return obszary, ile, n.zwin_znaczniki_wykresow(s.extract_text())

    def test_etykiety_oznaczone_proza_nie(self):
        obszary, ile, tekst = self._strona()
        self.assertEqual(len(obszary), 1)
        self.assertNotIn(n.ZNAK_WYKRESU, tekst)           # znaki zwinięte w zakresy
        proza, etykiety = n.rozdziel_wykresy(tekst)
        wyciete = " ".join(e for _p, e in etykiety)
        for slowo in ("Alpha", "Beta", "10", "20", "30", "May"):
            self.assertIn(slowo, wyciete.split())
            self.assertNotIn(slowo, proza.split())
        for linia in PROZA_KOLUMNY + ["Source: Bloomberg data for June 2026"]:
            self.assertIn(linia, proza)
        self.assertEqual(ile, len("Alpha" "Beta" "102030" "May26"))
        # Do odczytu nic nie ginie: każde słowo strony jest albo w prozie, albo w etykietach.
        self.assertEqual(sorted(n.bez_znacznikow_wykresow(tekst).split()),
                         sorted((proza + " " + wyciete).split()))

    def test_tabela_z_tekstem_to_nie_wykres(self):
        obszary, _ile, tekst = self._strona(tabela_tekstowa=True)
        self.assertEqual(len(obszary), 1)                 # tylko wykres, nie tabela
        self.assertIn("Lorem ipsum", n.rozdziel_wykresy(tekst)[0])

    def test_tabela_liczbowa_i_naglowek_pod_wykresem_zostaja_w_nlp(self):
        import pdfplumber
        with tempfile.TemporaryDirectory() as tmp:
            sciezka = Path(tmp) / "t.pdf"
            sciezka.write_bytes(_pdf_tabela_liczbowa_i_naglowek())
            with pdfplumber.open(sciezka) as pdf:
                s = pdf.pages[0]
                obszary = n.obszary_wykresow(s)
                n.oznacz_wykresy(s)
                proza, etykiety = n.rozdziel_wykresy(n.zwin_znaczniki_wykresow(s.extract_text()))
        self.assertEqual(len(obszary), 1)                       # wykres tak, tabela nie
        wyciete = " ".join(e for _p, e in etykiety)
        self.assertIn("0 10 20 30", wyciete)
        self.assertNotIn("Wnioski", wyciete)
        self.assertIn("Wnioski koncowe", proza)
        self.assertIn("Przychody 1037", proza)

    def test_zwijanie_w_obrebie_wiersza(self):
        Z, P, K = n.ZNAK_WYKRESU, n.POCZATEK_WYKRESU, n.KONIEC_WYKRESU
        oznacz = lambda s: "".join(Z + c if not c.isspace() else c for c in s)  # noqa: E731
        tekst = "proza " + oznacz("Ala ma") + " dalej\n" + oznacz("10 20")
        self.assertEqual(n.zwin_znaczniki_wykresow(tekst),
                         "proza " + P + "Ala ma" + K + " dalej\n" + P + "10 20" + K)
        self.assertEqual(n.zwin_znaczniki_wykresow("bez etykiet"), "bez etykiet")

    def test_rozdziel_pozycje_i_sklejanie(self):
        P, K = n.POCZATEK_WYKRESU, n.KONIEC_WYKRESU
        tekst = "Zdanie pierwsze.  " + P + "Oś X" + K + "\n" + P + "10 20" + K + "  zdanie drugie " + P + "maj 26" + K
        proza, et = n.rozdziel_wykresy(tekst)
        self.assertEqual(proza, "Zdanie pierwsze. zdanie drugie")
        # Dwa zakresy rozdzielone samym odstępem = jedno miejsce wycięcia.
        self.assertEqual(et, [(17, "Oś X 10 20"), (len(proza), "maj 26")])
        self.assertEqual(proza[17:], "zdanie drugie")
        self.assertEqual(n.rozdziel_wykresy("bez " + P + "niezamkniety"), ("bez", [(3, "niezamkniety")]))


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
