"""Testy odcinki_jezykowe: wybór bazy, odcinki obce, reguła alfabetu, bloki i segmenty.

Słowniki są listami form (bez spaCy/omorfi), alfabety z prawdziwych podstaw — tak jak
w test_glosowanie_ocr. Uruchomienie: python -m unittest discover -s .github/scripts -p "test_odcinki*"
"""
import sys
import unittest
from pathlib import Path

KORZEN = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KORZEN))

import odcinki_jezykowe as oj  # noqa: E402
import slowniki_jezykow as sj  # noqa: E402
from shamanic_locale import PODSTAWY  # noqa: E402

ALFABETY = {k: p["alfabet"] for k, p in PODSTAWY.items()}


def slownik(kod, *formy):
    return sj.Slownik(kod, sj._alfabet(kod), set(formy).__contains__, "test")


FI = slownik("fi", "tää", "on", "hyvä", "ja", "se", "tulee", "sanoista", "puhui", "Against", "and", "hän", "sanoi")
EN = slownik("en", "Strategic", "Lawsuit", "Against", "Public", "Participation", "and", "lot", "of", "fun",
             "This", "is", "good", "It", "was", "great", "deny", "attack", "on", "Lodz")
PL = slownik("pl", "Łódź", "Lodz", "dobry", "jest", "Public", "Wałęsa")


def odc(tekst, *slowniki):
    sl = {s.kod: s for s in slowniki}
    return oj.odcinki(tekst, slowniki[0].kod, sl, ALFABETY)


class TestBaza(unittest.TestCase):
    def test_baza_jezyk_znajacy_najwiecej(self):
        baza, udzialy = oj.wybierz_baze(["tää on hyvä ja se tulee Public"], {"en": EN, "fi": FI})
        self.assertEqual(baza, "fi")
        self.assertGreater(udzialy["fi"], udzialy["en"])

    def test_pusty_korpus_pierwszy_jezyk(self):
        self.assertEqual(oj.wybierz_baze([""], {"fi": FI, "en": EN})[0], "fi")


class TestOdcinki(unittest.TestCase):
    def test_cytat_w_zdaniu_to_wtracenie(self):
        t = "Tää on Strategic Lawsuit Against Public Participation ja se tulee."
        (o,) = odc(t, FI, EN)
        self.assertEqual((t[o.start:o.koniec], o.jezyk, o.blok),
                         ("Strategic Lawsuit Against Public Participation", "en", False))

    def test_most_znany_bazie_nie_na_brzegu(self):
        # „Against” zna fi i en: w środku cytatu łączy, na końcu odcinka nie wchodzi.
        t = "Se tulee Strategic Lawsuit Against ja hyvä."
        (o,) = odc(t, FI, EN)
        self.assertEqual(t[o.start:o.koniec], "Strategic Lawsuit")

    def test_dwa_slowa_bazy_rozcinaja(self):
        t = "Strategic Lawsuit and and Public Participation"
        self.assertEqual([t[o.start:o.koniec] for o in odc(t, FI, EN)],
                         ["Strategic Lawsuit", "Public Participation"])

    def test_pojedyncze_obce_slowo_z_liter_bazy_zostaje(self):
        self.assertEqual(odc("Tää on deny ja se tulee.", FI, EN), [])

    def test_jednoliterowe_nie_rozcina(self):
        t = "Hän sanoi a lot of fun ja se tulee."
        (o,) = odc(t, FI, EN)
        self.assertEqual(t[o.start:o.koniec], "a lot of fun"[2:])

    def test_nie_przez_koniec_zdania(self):
        self.assertEqual(odc("Tää on deny. Attack se tulee.", FI, EN), [])

    def test_regula_alfabetu_ascii_do_en(self):
        # „Public” znają pl i en: najmniejszy alfabet, który je mieści, to en.
        t = "Tää on Public Participation ja hyvä."
        (o,) = odc(t, FI, PL, EN)
        self.assertEqual(o.jezyk, "en")

    def test_regula_alfabetu_litera_polska(self):
        t = "Hän puhui Łódź ja se tulee."
        (o,) = odc(t, FI, PL, EN)
        self.assertEqual((t[o.start:o.koniec], o.jezyk), ("Łódź", "pl"))

    def test_nieznane_slowo_z_litera_spoza_bazy(self):
        # Odmienione po fińsku nazwisko nie jest w żadnym słowniku, ale „ł” czyta tylko głos pl.
        t = "Hän puhui Wałęsalle ja se tulee."
        (o,) = odc(t, FI, PL, EN)
        self.assertEqual((t[o.start:o.koniec], o.jezyk), ("Wałęsalle", "pl"))

    def test_nieznane_slowo_z_liter_bazy_dziedziczy(self):
        self.assertEqual(odc("Hän puhui Kowalskille ja se tulee.", FI, PL, EN), [])

    def test_cyrylica_bez_jezyka_cyrylickiego_w_korpusie(self):
        t = "Hän sanoi привет ja se tulee."
        (o,) = odc(t, FI, EN)
        self.assertEqual((t[o.start:o.koniec], o.jezyk), ("привет", "ru"))


class TestBloki(unittest.TestCase):
    def test_cale_zdanie_to_blok_z_kropka(self):
        t = "Tää on hyvä. This is good. Se tulee."
        (o,) = odc(t, FI, EN)
        self.assertEqual((t[o.start:o.koniec], o.blok), ("This is good.", True))

    def test_kolejne_zdania_scalone(self):
        t = "Tää on hyvä. This is good. It was great! Se tulee."
        (o,) = odc(t, FI, EN)
        self.assertEqual(t[o.start:o.koniec], "This is good. It was great!")

    def test_segmenty_pokrywaja_tekst(self):
        t = "Tää on hyvä. This is good. Se tulee Strategic Lawsuit ja hyvä."
        o = odc(t, FI, EN)
        seg = oj.segmenty(t, "fi", o)
        self.assertEqual("".join(t[a:b] for a, b, _ in seg), t)
        self.assertEqual([j for *_r, j in seg], ["fi", "en", "fi"])
        self.assertEqual(oj.statystyka(o), {"en": {"bloki": 1, "wtracenia": 1}})


if __name__ == "__main__":
    unittest.main()
