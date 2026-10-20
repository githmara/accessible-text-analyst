"""
czyszczenie_tekstu_wektory.py — runner wektorów testowych `czyszczenie_tekstu.py`.

BLIŹNIAK BAJT W BAJT (Reżyser Audio GPT ⟷ ATA), jak sam moduł i plik
`czyszczenie_tekstu_wektory.json`. Tylko biblioteka standardowa (unittest),
żeby oba repozytoria uruchamiały go bez zmian:

    python czyszczenie_tekstu_wektory.py

Oczekiwania w JSON-ie są wpisane ręcznie — zmiana zachowania modułu wymaga
świadomej zmiany wektora w OBU repozytoriach.
"""

import json
import os
import sys
import unittest

KATALOG = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KATALOG)

import czyszczenie_tekstu as ct  # noqa: E402

with open(os.path.join(KATALOG, "czyszczenie_tekstu_wektory.json"), encoding="utf-8") as _fh:
    DANE = json.load(_fh)


class Wektory(unittest.TestCase):

    def _liczniki(self, liczniki, oczekiwane):
        for klucz, wartosc in oczekiwane.items():
            self.assertEqual(liczniki[klucz], wartosc, klucz)

    def test_spacja_symbol(self):
        for w in DANE["spacja_symbol"]:
            with self.subTest(w["nazwa"]):
                wynik, ile = ct.zamien_spacje_symbol(w["akapity"])
                self.assertEqual(wynik, w["oczekiwane"])
                self.assertEqual(ile, w["liczba"])

    def test_przeniesienia(self):
        for w in DANE["przeniesienia"]:
            with self.subTest(w["nazwa"]):
                wynik, liczniki = ct.napraw_przeniesienia(w["akapity"])
                self.assertEqual(wynik, w["oczekiwane"])
                self._liczniki(liczniki, w["liczniki"])

    def test_rozstrzelone(self):
        for w in DANE["rozstrzelone"]:
            with self.subTest(w["nazwa"]):
                wynik, liczniki = ct.scal_rozstrzelone(w["akapity"], w["granica"])
                self.assertEqual(wynik, w["oczekiwane"])
                self._liczniki(liczniki, w["liczniki"])

    @staticmethod
    def _alfabety(w):
        """Alfabety wektora (np. sytuacja ATA: sześć paczek) albo wspólne."""
        return [frozenset(a) for a in w.get("alfabety", DANE["alfabety"])]

    def test_wiarygodnosc(self):
        for w in DANE["wiarygodnosc"]:
            with self.subTest(w["nazwa"]):
                self.assertEqual(list(ct.wiarygodnosc(w["tekst"], self._alfabety(w))),
                                 w["wynik"])

    def test_mojibake(self):
        for w in DANE["mojibake"]:
            with self.subTest(w["nazwa"]):
                wynik, info = ct.napraw_mojibake(w["tekst"], self._alfabety(w))
                self.assertEqual(wynik, w["oczekiwany"] if w["oczekiwany"] is not None
                                 else w["tekst"])
                self.assertEqual(info["kodowanie"], w["kodowanie"])

    def test_mojibake_akapitow(self):
        for w in DANE["mojibake_akapity"]:
            with self.subTest(w["nazwa"]):
                wynik, info = ct.napraw_mojibake_akapitow(w["akapity"], self._alfabety(w))
                self.assertEqual(wynik, w["oczekiwane"])
                self.assertEqual(info["przekodowane"], w["przekodowane"])

    def test_liczba_akapitow_stala(self):
        akapity = [a for w in DANE["przeniesienia"] for a in w["akapity"]]
        wynik, _ = ct.oczysc_akapity_docx(akapity, DANE["alfabety"])
        self.assertEqual(len(wynik), len(akapity))


if __name__ == "__main__":
    unittest.main()
