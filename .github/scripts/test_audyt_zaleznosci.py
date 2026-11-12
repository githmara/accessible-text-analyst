"""Testy kanonu środowiska w audyt_zaleznosci.py (bliźniak Reżysera 19.18).

Pilnują trzech rzeczy, które sprawiają, że granica nie zastyga po cichu:
każdy wpis manifestu ma datę holdu i grupę ryzyka, a hold z wcześniejszego
minora wygasa. Sieć nie jest potrzebna — werdykty liczone są na danych z testu.

Uruchom:  .venv/Scripts/python .github/scripts/test_audyt_zaleznosci.py
"""
import sys
import tempfile
import unittest
from pathlib import Path

KORZEN = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KORZEN))

import audyt_zaleznosci as az  # noqa: E402


def _plik(tresc: str) -> Path:
    d = Path(tempfile.mkdtemp())
    p = d / "plik.txt"
    p.write_text(tresc, encoding="utf-8")
    return p


class TestManifest(unittest.TestCase):
    def test_hold_z_komentarza_i_linia_opcjonalna(self):
        p = _plik("numpy<2.6  # hold: 1.8.0\n"
                  "# torch<2.15  # hold: 1.10.1\n"
                  "# Odkomentuj obie linie, jeśli trzeba\n"
                  "#   omorfi-download\n"
                  "requests<2.35\n")
        wpisy = {w.nazwa: w for w in az.wczytaj_manifest(p)}
        self.assertEqual(set(wpisy), {"numpy", "torch", "requests"})
        self.assertEqual((wpisy["numpy"].spec, wpisy["numpy"].hold, wpisy["numpy"].opcja),
                         ("<2.6", "1.8.0", False))
        self.assertEqual((wpisy["torch"].hold, wpisy["torch"].opcja), ("1.10.1", True))
        self.assertIsNone(wpisy["requests"].hold)

    def test_prawdziwy_manifest_ma_daty_i_grupy(self):
        for w in az.wczytaj_manifest():
            with self.subTest(pakiet=w.nazwa):
                self.assertIn(w.nazwa, az.GRUPY_RYZYKA,
                              "new dependency without a risk group in GRUPY_RYZYKA")
                if w.spec.startswith("<"):
                    self.assertIsNotNone(w.hold, "bound without '# hold: <version>'")


class TestWstrzymanie(unittest.TestCase):
    def test_wygasa_z_nastepnym_minorem(self):
        self.assertEqual(az.ocen_wstrzymanie("trzymana", "1.11.0", (1, 12, 0)), "przeterminowana")
        self.assertEqual(az.ocen_wstrzymanie("trzymana", "1.12.0", (1, 12, 3)), "trzymana")
        self.assertEqual(az.ocen_wstrzymanie("trzymana", "1.12.0", (2, 0, 0)), "przeterminowana")

    def test_bez_daty_i_bez_wersji_projektu(self):
        self.assertEqual(az.ocen_wstrzymanie("trzymana", None, (1, 12, 0)), "niedatowana")
        self.assertEqual(az.ocen_wstrzymanie("trzymana", "1.8.0", None), "trzymana")

    def test_aktualny_pakiet_ze_stara_data_nie_ostrzega(self):
        # Hold liczy się tylko, gdy granica coś wyklucza.
        self.assertEqual(az.ocen_wstrzymanie("ok", "1.0.0", (1, 12, 0)), "ok")
        self.assertEqual(az.ocen_wstrzymanie("dopuszczona", "1.0.0", (1, 12, 0)), "dopuszczona")

    def test_wersja_z_gornej_sekcji_notatek(self):
        p = _plik("# Release notes\n\n## v1.13.0 — tytuł\n\n## v1.12.0 — starszy\n")
        self.assertEqual(az.wersja_projektu(p), (1, 13, 0))
        self.assertIsNone(az.wersja_projektu(_plik("bez sekcji\n")))
        self.assertIsNotNone(az.wersja_projektu())


if __name__ == "__main__":
    unittest.main(verbosity=1)
