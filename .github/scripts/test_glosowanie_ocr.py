"""Testy glosowanie_ocr.py na sztucznych słownikach i sztucznych odczytach — bez silników OCR i modeli.

Przypadki pochodzą z pomiaru 2026-11-13 na polsko-fińskim slajdzie i fińskich stronach:
polski silnik gubi ä, fiński gubi ą/ę/ł, rosyjski wstawia cyrylicę w łacińskie słowa,
a słownik bez warunku alfabetu przepuszcza formy obce.

Uruchom:  .venv/Scripts/python .github/scripts/test_glosowanie_ocr.py
"""
import sys
import unittest
from collections import namedtuple
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import glosowanie_ocr as g  # noqa: E402
from ocr_windows import Slowo  # noqa: E402


def sl(kod, formy):
    return g.Slownik(kod, g._alfabet(kod), set(formy).__contains__, "test")


SLOWNIKI = {
    "pl": sl("pl", {"Pytaj", "intencją", "to", "pytanie", "ma", "wagę", "Mini", "Zostaw", "dla", "wymaga"}),
    "fi": sl("fi", {"Mitä", "kuuluu", "Minä", "olen", "väsynyt"}),
    "ru": sl("ru", {"та", "Как"}),
}


def wiersz(nr, slowa, y=0):
    """Słowa jednego wiersza w ramkach co 100 px (ta sama ramka u każdego silnika)."""
    return [Slowo(nr, t, 100 * i, y, 90, 40) for i, t in enumerate(slowa)]


class TestSlownik(unittest.TestCase):
    def test_brak_glosu_dla_liczb_i_znakow(self):
        self.assertIsNone(SLOWNIKI["pl"].ocen("12"))
        self.assertIsNone(SLOWNIKI["pl"].ocen("I"))
        self.assertIsNone(SLOWNIKI["pl"].ocen("Mä/Sä"))  # dwa ciągi liter — nie zgadujemy

    def test_interpunkcja_nie_przeszkadza(self):
        self.assertTrue(SLOWNIKI["fi"].ocen("kuuluu?"))

    def test_litery_spoza_alfabetu_odrzucone(self):
        # Ј (serbskie) nie należy do alfabetu rosyjskiego: mieszanka pism z rosyjskiego silnika.
        ru = sl("ru", {chr(0x408) + "аК"})
        self.assertFalse(ru.ocen(chr(0x408) + "аК"))

    def test_wielka_litera_sprowadzana(self):
        self.assertTrue(sl("pl", {"pytanie"}).ocen("Pytanie"))


class TestGlosuj(unittest.TestCase):
    def test_jedyna_forma_slownikowa_wygrywa(self):
        k = {"pl": wiersz(0, ["Pytaj", "z", "intencją"]), "fi": wiersz(0, ["Pytaj", "z", "intencjQ"])}
        w = g.glosuj(k, SLOWNIKI)
        self.assertEqual(w.tekst, "Pytaj z intencją")

    def test_forma_obca_wybrana_z_silnika_swojego_jezyka(self):
        k = {"pl": wiersz(0, ["Miła", "kuuluu?", "wymaga"]), "fi": wiersz(0, ["Mitä", "kuuluu?", "wymaga"])}
        self.assertEqual(g.glosuj(k, SLOWNIKI).tekst, "Mitä kuuluu? wymaga")

    def test_cyrylica_rosyjskiego_silnika_przegrywa_z_kontekstem(self):
        # „та” jest poprawnym słowem rosyjskim, „ma” polskim — rozstrzyga sąsiedztwo.
        k = {"pl": wiersz(0, ["to", "pytanie", "ma", "wagę"]), "ru": wiersz(0, ["to", "pytanie", "та", "wagę"])}
        w = g.glosuj(k, SLOWNIKI)
        self.assertEqual(w.tekst, "to pytanie ma wagę")
        self.assertEqual(w.niejednoznaczne, 1)

    def test_kontekst_wygrywa_z_baza(self):
        # Baza fińska (więcej form na stronie), ale wiersz 1 jest polski: „Mitä” i „ma” są
        # słownikowe, każde we własnym języku — wybiera polski kontekst, nie baza.
        fi = wiersz(0, ["Mitä", "kuuluu", "väsynyt", "olen"]) + wiersz(1, ["to", "pytanie", "Mitä", "wagę"], y=100)
        pl = wiersz(0, ["Mila", "kuuluu", "vasynyt", "olen"]) + wiersz(1, ["to", "pytanie", "ma", "wagę"], y=100)
        w = g.glosuj({"pl": pl, "fi": fi}, SLOWNIKI)
        self.assertEqual(w.baza, "fi")
        self.assertEqual(w.tekst.splitlines()[1], "to pytanie ma wagę")

    def test_remis_sasiadow_rozstrzyga_wiersz(self):
        # Znane ograniczenie (pomiar 2026-11-13): lewy sąsiad polski, prawy fiński, wiersz polski.
        k = {"pl": wiersz(0, ["Zostaw", "Mini", "olen", "dla"]), "fi": wiersz(0, ["Zostaw", "Minä", "olen", "dla"])}
        self.assertEqual(g.glosuj(k, SLOWNIKI).tekst, "Zostaw Mini olen dla")

    def test_bez_formy_slownikowej_jezyk_wiersza(self):
        # „Hämeenlinna” nie ma w żadnym słowniku: bierzemy odczyt silnika języka, który w wierszu przeważa.
        # Baza polska (wiersz 0), wiersz 1 fiński — bez reguły wiersza zostałby polski odczyt bez ä.
        polski = wiersz(0, ["Pytaj", "to", "pytanie", "wymaga"])
        k = {"pl": polski + wiersz(1, ["Mitä", "kuuluu", "Hameenlinna"], y=100),
             "fi": polski + wiersz(1, ["Mitä", "kuuluu", "Hämeenlinna"], y=100)}
        w = g.glosuj(k, SLOWNIKI)
        self.assertEqual(w.baza, "pl")
        self.assertEqual(w.tekst.splitlines()[1], "Mitä kuuluu Hämeenlinna")

    def test_baza_to_silnik_z_najwieksza_liczba_form(self):
        k = {"pl": wiersz(0, ["Mila", "kuuluu", "vasynyt"]), "fi": wiersz(0, ["Mitä", "kuuluu", "väsynyt"])}
        self.assertEqual(g.glosuj(k, SLOWNIKI).baza, "fi")

    def test_slowo_widziane_tylko_przez_inny_silnik_dochodzi_na_miejsce(self):
        # Tak trafiają do tekstu słowa widziane tylko przez easyocr (islandzkie þ/ð).
        baza = wiersz(0, ["Pytaj", "z"]) + wiersz(1, ["to", "pytanie"], y=100)
        k = {"pl": baza, "fi": [Slowo(0, "Minä", 200, 0, 90, 40)]}
        w = g.glosuj(k, SLOWNIKI)
        self.assertEqual(w.tekst.splitlines(), ["Pytaj z Minä", "to pytanie"])
        self.assertEqual(w.dodane, 1)

    def test_slowo_spoza_bazy_bez_formy_slownikowej_pominiete(self):
        baza = wiersz(0, ["Pytaj", "z"])
        w = g.glosuj({"pl": baza, "fi": [Slowo(0, "xqz", 200, 0, 90, 40)]}, SLOWNIKI)
        self.assertEqual((w.tekst, w.dodane), ("Pytaj z", 0))

    def test_slowo_bez_wiersza_bazy_nie_jest_wstawiane(self):
        baza = wiersz(0, ["Pytaj", "z"])
        k = {"pl": baza, "fi": [Slowo(0, "Minä", 0, 5000, 90, 40)]}
        w = g.glosuj(k, SLOWNIKI)
        self.assertEqual(w.tekst, "Pytaj z")
        self.assertEqual(w.dodane, 0)

    def test_brak_slownikow(self):
        self.assertEqual(g.glosuj({"xx": wiersz(0, ["a"])}, SLOWNIKI).slowa, [])


Wynik = namedtuple("Wynik", "slowa bez_silnika")


class TestPlan(unittest.TestCase):
    def test_wszystkie_problemy_w_jednym_bledzie(self):
        def silnik(tag):
            return tag.startswith("pl")

        def slownik(kod):
            if kod == "pl":
                raise LookupError("brak modelu spaCy pl_core_news_lg")
            return SLOWNIKI.get(kod)

        with mock.patch.object(g.ow, "dostepne_jezyki", return_value=["pl"]), \
                mock.patch.object(g.ow, "silnik_dostepny", side_effect=silnik), \
                mock.patch.object(g, "_easyocr_zna", side_effect=lambda k: k == "is"), \
                mock.patch.object(g, "slownik", side_effect=slownik):
            with self.assertRaises(g.BladGlosowania) as e:
                g.zaplanuj(["pl", "fi", "is"])
        problemy = {(p.kod, p.przyczyna) for p in e.exception.problemy}
        # pl: silnik jest, słownika nie; fi: ani Windows, ani easyocr; is: easyocr i słownik są.
        self.assertEqual(problemy, {("pl", "brak_slownika"), ("fi", "brak_silnika")})

    def test_bez_pywinrt_jezyk_idzie_do_easyocr_albo_jest_bledem(self):
        with mock.patch.object(g.ow, "dostepne_jezyki", side_effect=g.ow.OcrNiedostepny("brak pywinrt")), \
                mock.patch.object(g, "_easyocr_zna", return_value=None), \
                mock.patch.object(g, "slownik", side_effect=lambda k: SLOWNIKI.get(k)):
            with self.assertRaises(g.BladGlosowania) as e:
                g.zaplanuj(["pl"])
        self.assertIn("brak pywinrt", e.exception.problemy[0].szczegol)
        self.assertIn("easyocr not installed", e.exception.problemy[0].szczegol)

    def test_nieznany_kod_jest_problemem_nie_wyjatkiem(self):
        # Stare configi miały kody easyocr spoza podstaw (np. "de"): komunikat, nie KeyError.
        with mock.patch.object(g.ow, "dostepne_jezyki", return_value=["pl"]), \
                mock.patch.object(g.ow, "silnik_dostepny", return_value=True), \
                mock.patch.object(g, "slownik", side_effect=lambda k: SLOWNIKI[k]):
            with self.assertRaises(g.BladGlosowania) as e:
                g.zaplanuj(["pl", "xx"])
        self.assertEqual([(p.kod, p.przyczyna) for p in e.exception.problemy], [("xx", "nieznany_jezyk")])

    def test_plan_kompletny(self):
        with mock.patch.object(g.ow, "dostepne_jezyki", return_value=["pl", "fi"]), \
                mock.patch.object(g.ow, "silnik_dostepny", return_value=True), \
                mock.patch.object(g, "slownik", side_effect=lambda k: SLOWNIKI[k]):
            p = g.zaplanuj(["pl", "fi"])
        self.assertEqual(p.windows, {"pl": "pl-PL", "fi": "fi-FI"})
        self.assertEqual(p.easyocr, [])


class TestEasyocrSegmenty(unittest.TestCase):
    def test_segment_dzielony_na_slowa_i_wiersze(self):
        segmenty = [
            ([[200, 100], [380, 100], [380, 140], [200, 140]], "þú ert", 0.9),  # drugi segment wiersza 0
            ([[0, 102], [180, 102], [180, 138], [0, 138]], "Halló heimur", 0.9),
            ([[0, 200], [100, 200], [100, 240], [0, 240]], "Takk", 0.9),
        ]
        # Bez obrazu i bez numpy: runner CI nie ma ani easyocr, ani numpy.
        with mock.patch.object(g, "_segmenty_easyocr", return_value=segmenty):
            slowa = g.slowa_easyocr(None, "is")
        self.assertEqual([(s.linia, s.tekst) for s in slowa],
                         [(0, "Halló"), (0, "heimur"), (0, "þú"), (0, "ert"), (1, "Takk")])
        heimur = slowa[1]
        self.assertEqual(heimur.x, round(6 * 180 / 12))  # „heimur” zaczyna się od 7. znaku z 12
        self.assertEqual(heimur.w, round(6 * 180 / 12))


if __name__ == "__main__":
    unittest.main()
