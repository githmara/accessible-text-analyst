"""Testy ciecie_stron.py (czysta geometria — wszędzie) i ocr_windows.py (WinRT — tylko Windows z pywinrt).

Obrazy są syntetyczne: wiersze „Wiersz NNN …” narysowane Arialem, więc wzorcem jest
to, co narysowano. Najważniejszy przypadek odtwarza Rolki z 2026-11-13: strona
wyższa niż `MaxImageDimension` musi wyjść z KAŻDYM wierszem dokładnie raz — bez
dziury na cięciu i bez duplikatu z zakładki.

Uruchom:  .venv/Scripts/python .github/scripts/test_ocr_windows.py
Na CI (ubuntu) testy WinRT są pomijane z powodem; geometria idzie zawsze.
"""
import asyncio
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ciecie_stron as cs  # noqa: E402
import ocr_windows as ow  # noqa: E402


class TestPasy(unittest.TestCase):
    def test_miesci_sie_bez_ciecia(self):
        self.assertEqual(cs.pasy(9000, 10000, 300), [cs.Pas(0.0, 9000.0, 0.0, 9000.0)])

    def test_pasy_w_limicie_z_zakladka_i_pelnym_pokryciem(self):
        for dl in (10001, 20882, 25000, 54321):
            p = cs.pasy(dl, 10000, 300)
            self.assertGreater(len(p), 1)
            self.assertEqual(p[0].poczatek, 0.0)
            self.assertAlmostEqual(p[-1].koniec, dl)
            for a, b in zip(p, p[1:]):
                self.assertAlmostEqual(a.koniec - b.poczatek, 300)  # zakładka dokładnie taka, jak zamówiono
                self.assertAlmostEqual(a.wlasny_do, b.wlasny_od)  # strefy własne bez dziur i nakładek
            for x in p:
                self.assertLessEqual(x.koniec - x.poczatek, 10000 + 1e-9)

    def test_minimalna_liczba_pasow(self):
        self.assertEqual(len(cs.pasy(19700, 10000, 300)), 2)
        self.assertEqual(len(cs.pasy(19701, 10000, 300)), 3)

    def test_wlasciciel_srodka(self):
        p = cs.pasy(20000, 10000, 300)
        granica = p[0].wlasny_do
        self.assertEqual(cs.wlasciciel(p, granica - 0.5), 0)
        self.assertEqual(cs.wlasciciel(p, granica), 1)
        self.assertEqual(cs.wlasciciel(p, -5), 0)
        self.assertEqual(cs.wlasciciel(p, 10 ** 6), len(p) - 1)

    def test_bledne_parametry(self):
        for args in ((0, 10, 1), (100, 10, 10), (100, 10, -1)):
            with self.assertRaises(ValueError):
                cs.pasy(*args)


class TestBezWindows(unittest.TestCase):
    def test_nie_windows_to_jawny_blad(self):
        with mock.patch.object(ow.sys, "platform", "linux"):
            with self.assertRaises(ow.OcrNiedostepny):
                ow.dostepne_jezyki()

    def test_tekst_sklada_wiersze(self):
        s = [ow.Slowo(0, "Ala", 0, 0, 1, 1), ow.Slowo(0, "ma", 2, 0, 1, 1), ow.Slowo(1, "kota", 0, 5, 1, 1)]
        self.assertEqual(ow.tekst(s), "Ala ma" + chr(10) + "kota")


def _winrt_dziala() -> str:
    try:
        jezyki = ow.dostepne_jezyki()
    except ow.OcrNiedostepny as e:
        return str(e)
    return "" if any(j.startswith("en") for j in jezyki) else "brak silnika en"


POWOD = _winrt_dziala()
ARIAL = Path("C:/Windows/Fonts/arial.ttf")
WYRAZY = "alpha bravo charlie delta echo foxtrot".split()


def _strona(szer, wys, odstep=120, rozmiar=44, lewy=80):
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype(str(ARIAL), rozmiar)
    obraz = Image.new("L", (szer, wys), 255)
    d = ImageDraw.Draw(obraz)
    wiersze = []
    for i, y in enumerate(range(60, wys - odstep, odstep)):
        t = f"Wiersz {i:03d} " + " ".join(WYRAZY[(i + k) % 6] for k in range(3))
        d.text((lewy, y), t, font=f, fill=0)
        wiersze.append(t)
    return obraz, wiersze


def _numery(slowa):
    return [int(m.group(1)) for linia in ow.tekst(slowa).splitlines() for m in [re.search(r"Wiersz (\d{3})", linia)] if m]


@unittest.skipIf(POWOD, f"OCR Windows niedostępny: {POWOD}")
class TestOcrWindows(unittest.TestCase):
    def test_strona_zwykla(self):
        obraz, wiersze = _strona(1800, 1500)
        w = ow.rozpoznaj(obraz, ["en-US"])
        self.assertEqual(w.bez_silnika, [])
        self.assertEqual(_numery(w.slowa["en-US"]), list(range(len(wiersze))))

    def test_wysoka_strona_kazdy_wiersz_raz(self):
        # 25095 = 3 × 8365: bez zakładki cięcie wypada w 8365, w połowie wiersza 069
        # (y = 60 + 120 × 69 = 8340, wysokość ~50 px) — test łapie brak zakładki.
        obraz, wiersze = _strona(1800, 25095)
        self.assertGreater(obraz.height, ow.maks_wymiar())
        w = ow.rozpoznaj(obraz, ["en-US"])
        self.assertEqual(_numery(w.slowa["en-US"]), list(range(len(wiersze))))
        ys = [s.y for s in w.slowa["en-US"] if s.tekst == "Wiersz"]
        self.assertEqual(ys, sorted(ys))  # ramki we współrzędnych całej strony
        self.assertGreater(ys[-1], ow.maks_wymiar())

    def test_szeroka_strona_ramki_w_skali_oryginalu(self):
        # Obraz 12000 px jest zmniejszany do 10000 (×0,83); tekst stoi od x = 600, więc
        # ramka bez przeskalowania z powrotem miałaby x ≈ 500.
        obraz, wiersze = _strona(12000, 1200, rozmiar=90, odstep=200, lewy=600)
        w = ow.rozpoznaj(obraz, ["en-US"])
        self.assertEqual(_numery(w.slowa["en-US"]), list(range(len(wiersze))))
        lewe = [s.x for s in w.slowa["en-US"] if s.tekst == "Wiersz"]
        self.assertTrue(lewe and all(abs(x - 600) < 30 for x in lewe), lewe)

    def test_maly_obraz_powiekszany_ramki_w_skali_oryginalu(self):
        # 500x400 jest powiększany do 2000 (x4). Czcionka 9 px: bez powiększenia silnik en nie
        # czyta ani jednego wiersza (zmierzone 2026-11-14), z powiększeniem — wszystkie.
        # Czcionka 12 px: tekst od x = 40; ramka bez przeskalowania z powrotem miałaby x ≈ 160.
        obraz, wiersze = _strona(500, 400, odstep=27, rozmiar=9, lewy=40)
        self.assertEqual(len(_numery(ow.rozpoznaj(obraz, ["en-US"]).slowa["en-US"])), len(wiersze))
        obraz, wiersze = _strona(500, 400, odstep=36, rozmiar=12, lewy=40)
        w = ow.rozpoznaj(obraz, ["en-US"])
        lewe = [s.x for s in w.slowa["en-US"] if s.tekst == "Wiersz"]
        self.assertTrue(lewe and all(abs(x - 40) < 10 for x in lewe), lewe)

    def test_jezyk_bez_silnika_nie_znika(self):
        obraz, _ = _strona(1200, 600)
        w = ow.rozpoznaj(obraz, ["en-US", "xx-XX"])
        self.assertEqual(w.bez_silnika, ["xx-XX"])
        self.assertIn("en-US", w.slowa)

    def test_locale_z_podstaw_trafia_w_silnik(self):
        # podstawy.yaml::locale ma postać pl-PL, a Windows zgłasza silnik jako `pl`.
        if "pl" not in ow.dostepne_jezyki():
            self.skipTest("brak silnika pl")
        self.assertTrue(ow.silnik_dostepny("pl-PL"))

    def test_z_wnetrza_petli_zdarzen(self):
        obraz, wiersze = _strona(1200, 600)

        async def w_petli():
            return ow.rozpoznaj(obraz, ["en-US"])

        w = asyncio.run(w_petli())
        self.assertEqual(_numery(w.slowa["en-US"]), list(range(len(wiersze))))


if __name__ == "__main__":
    unittest.main()
