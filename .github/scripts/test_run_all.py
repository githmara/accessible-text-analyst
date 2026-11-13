"""Testy trybu `run_all.py --warnings-as-errors` (łata kopii notatnika).

Tryb wykonuje kopię notatnika, w której ostrzeżenia są błędami, a eksporty
lądują w katalogu tymczasowym. Łata trzyma się kotwic w kodzie komórek —
gdy ktoś zmieni `cell_langdet` albo linię `PROJECT_DIR` w `cell_corpus`,
ten test pada w CI, zanim tryb zacznie po cichu pisać do export_results/
albo przestanie widzieć ostrzeżenia. Jądro nie jest potrzebne.

Uruchom:  .venv/Scripts/python .github/scripts/test_run_all.py
"""
import sys
import unittest
from pathlib import Path

KORZEN = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KORZEN))

import nbformat  # noqa: E402

import run_all  # noqa: E402


def _komorka(nb, tag):
    return next(c for i, c in enumerate(nb.cells) if run_all._tag(c, i) == tag)


class TestLataOstrzezen(unittest.TestCase):
    def setUp(self):
        self.nb = nbformat.read(run_all.NOTEBOOK, as_version=4)

    def test_prawdziwy_notatnik_ma_kotwice_i_kopia_jest_zalatana(self):
        cel = Path("C:/tmp/ata_warnings_x") / "export_results"
        kopia = run_all.patch_for_warnings(self.nb, cel)
        pierwsza = kopia.cells[0]
        self.assertEqual(pierwsza.metadata["tags"], [run_all.WARNINGS_TAG])
        self.assertIn(run_all.WARNINGS_ERROR, pierwsza.source)
        langdet = _komorka(kopia, "cell_langdet").source
        self.assertNotIn('warnings.filterwarnings("ignore")', langdet)
        self.assertIn(run_all.WARNINGS_ERROR, langdet)
        korpus = _komorka(kopia, "cell_corpus").source
        self.assertIn(f"PROJECT_DIR = Path({str(cel)!r}) / PROJECT_NAME", korpus)
        self.assertNotIn('Path("export_results") / PROJECT_NAME', korpus)
        # Oryginał nietknięty: tryb nie może zapisać łaty do notatnika w repo.
        self.assertEqual(len(kopia.cells), len(self.nb.cells) + 1)
        self.assertIn('warnings.filterwarnings("ignore")', _komorka(self.nb, "cell_langdet").source)

    def test_brak_kotwicy_odmawia(self):
        langdet = _komorka(self.nb, "cell_langdet")
        langdet.source = langdet.source.replace('warnings.filterwarnings("ignore")', "pass")
        with self.assertRaises(ValueError) as e:
            run_all.patch_for_warnings(self.nb, Path("x"))
        self.assertIn("cell_langdet", str(e.exception))

    def test_kotwica_dwa_razy_odmawia(self):
        korpus = _komorka(self.nb, "cell_corpus")
        korpus.source += "\n" + run_all.WARNINGS_ANCHORS[1][1]
        with self.assertRaises(ValueError):
            run_all.patch_for_warnings(self.nb, Path("x"))

    def test_miejsce_ostrzezenia_z_tracebacku(self):
        esc = chr(27)
        tb = [f"{esc}[31m---------------------------------------------------------------------------{esc}[39m",
              f"{esc}[36mCell In[11], line 104{esc}[39m\n  x = f()",
              f"File ~/.venv/Lib/site-packages/numpy/_core/_methods.py:122, in _mean\n  warnings.warn(",
              f"{esc}[31mRuntimeWarning{esc}[39m: Mean of empty slice"]
        self.assertEqual(run_all._warning_location(tb),
                         ["Cell In[11], line 104",
                          "File ~/.venv/Lib/site-packages/numpy/_core/_methods.py:122, in _mean"])
        self.assertEqual(run_all._warning_location(None), [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
