"""
detektor_pism_testy.py — testy wspólnego modułu `detektor_pism` (Reżyser ⟷ ATA).

BLIŹNIAK BAJT W BAJT (klasa „detektor_pism”): ten sam plik w obu repo, tylko
biblioteka standardowa (unittest), alfabety syntetyczne — żaden test nie czyta
paczek projektu. Litery spoza ASCII budowane z kodów (pułapka escape'ów
narzędzi agenta).

Uruchom:  python -m unittest detektor_pism_testy -v
"""

import unittest

import detektor_pism as dp


def c(*kody):
    return "".join(chr(k) for k in kody)


# Alfabet rosyjski (33 wielkie litery) i ukraiński (33): wspólne większość,
# ru ma Ё Ъ Ы Э, uk ma Ґ Є І Ї.
RU = c(*range(0x0410, 0x0430)) + c(0x0401)
UK = (c(*[k for k in range(0x0410, 0x0430) if k not in (0x042A, 0x042B, 0x042D)])
      + c(0x0490, 0x0404, 0x0406, 0x0407))
PL = "ABCDEFGHIJKLMNOPRSTUWYZ"   # alfabet łaciński (syntetyczny, ASCII)

MY_ZHDYOM = c(0x041C, 0x044B, 0x20, 0x0436, 0x0434, 0x0451, 0x043C)   # Мы ждём
PRYWIT = c(0x043F, 0x0440, 0x0438, 0x0432, 0x0456, 0x0442)            # привіт
DOM = c(0x0434, 0x043E, 0x043C)                                       # дом
LOGOS = c(0x03BB, 0x03CC, 0x03B3, 0x03BF, 0x03C2)                     # λόγος


class TestPismo(unittest.TestCase):
    def test_pismo_litery(self):
        self.assertEqual(dp.pismo_znaku("a"), dp.LACINKA)
        self.assertEqual(dp.pismo_znaku(c(0x0436)), dp.CYRYLICA)
        self.assertEqual(dp.pismo_znaku(c(0x03C0)), dp.GREKA)
        self.assertIsNone(dp.pismo_znaku("7"))
        self.assertIsNone(dp.pismo_znaku(c(0x0301)))

    def test_znak_mikro_i_omu_to_greka(self):
        self.assertEqual(dp.pismo_znaku(c(0x00B5)), dp.GREKA)
        self.assertEqual(dp.pismo_znaku(c(0x2126)), dp.GREKA)

    def test_dominujace(self):
        self.assertEqual(dp.dominujace_pismo(MY_ZHDYOM + " ok"), dp.CYRYLICA)
        self.assertEqual(dp.dominujace_pismo("Ala " + LOGOS), dp.GREKA)
        self.assertIsNone(dp.dominujace_pismo("2 + 2 = 4"))

    def test_remis_rozstrzyga_pierwsza_litera(self):
        self.assertEqual(dp.dominujace_pismo("ab" + DOM[:2]), dp.LACINKA)


class TestJezykCyrylicy(unittest.TestCase):
    def test_jedna_paczka_jest_jednoznaczna(self):
        alf = {"pl": PL, "ru": RU}  # audyt-podstaw: ok — alfabety syntetyczne testu, nie dane paczek
        self.assertEqual(dp.jezyki_cyrylickie(alf), ["ru"])
        self.assertEqual(dp.jezyk_cyrylicy(PRYWIT, alf), "ru")

    def test_litera_jednego_alfabetu_rozstrzyga(self):
        alf = {"ru": RU, "uk": UK}
        self.assertEqual(dp.jezyk_cyrylicy(PRYWIT, alf), "uk")
        self.assertEqual(dp.jezyk_cyrylicy(MY_ZHDYOM, alf), "ru")

    def test_litery_wspolne_daja_domyslny(self):
        self.assertEqual(dp.jezyk_cyrylicy(DOM, {"ru": RU, "uk": UK}), "ru")

    def test_bez_ru_wygrywa_pokrycie(self):
        alf = {"uk": UK, "xx": c(0x0410, 0x0411)}
        self.assertEqual(dp.jezyk_cyrylicy(DOM, alf), "uk")

    def test_bez_paczek_cyrylickich_domyslny(self):
        self.assertEqual(dp.jezyk_cyrylicy(DOM, {"pl": PL}), "ru")


class TestOdcinki(unittest.TestCase):
    def test_slowa_tego_pisma_sklejone_w_odcinek(self):
        tekst = "Napis " + DOM + ", " + DOM + " i " + LOGOS + "."
        odc = [(tekst[s:e], p) for s, e, p in dp.odcinki_pism(tekst)]
        self.assertEqual(odc, [("Napis", dp.LACINKA), (DOM + ", " + DOM, dp.CYRYLICA),
                               ("i", dp.LACINKA), (LOGOS, dp.GREKA)])

    def test_litera_przy_cyfrze_i_lacince(self):
        tekst = "2" + c(0x03C0) + "r"
        self.assertEqual([(tekst[s:e], p) for s, e, p in dp.odcinki_pism(tekst)],
                         [(c(0x03C0), dp.GREKA), ("r", dp.LACINKA)])

    def test_akcent_laczacy_nalezy_do_odcinka(self):
        slowo = c(0x043A, 0x043E, 0x0301)           # ко + akcent
        tekst = slowo + " ok"
        self.assertEqual(dp.odcinki_pism(tekst)[0], (0, 3, dp.CYRYLICA))

    def test_apostrof_modyfikujacy_nie_rozcina_slowa(self):
        slowo = c(0x043C, 0x02BC, 0x044F, 0x0441, 0x043E)   # мʼясо
        self.assertIsNone(dp.pismo_znaku(c(0x02BC)))
        self.assertEqual(dp.odcinki_pism(slowo), [(0, 5, dp.CYRYLICA)])

    def test_tekst_bez_liter(self):
        self.assertEqual(dp.odcinki_pism("12, 34."), [])


if __name__ == "__main__":
    unittest.main()
