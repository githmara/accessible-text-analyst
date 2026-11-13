"""Testy trybu `run_all.py --warnings-as-errors` (pełna diagnostyka ostrzeżeń).

Tryb wykonuje kopię notatnika na syntetycznym korpusie z diagnostyka.py,
rejestruje każde ostrzeżenie i sprawdza, czy każdy komponent opcjonalny
zadziałał. Łata trzyma się kotwic w kodzie komórek — gdy ktoś zmieni
`cell_langdet` albo `cell_corpus`, ten test pada w CI, zanim tryb zacznie po
cichu pisać do export_results/, czytać config użytkownika albo przestanie
widzieć ostrzeżenia. Jądro Jupytera nie jest potrzebne.

Uruchom:  .venv/Scripts/python .github/scripts/test_run_all.py
"""
import contextlib
import io
import sys
import tempfile
import unittest
import warnings
from pathlib import Path

KORZEN = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KORZEN))

import nbformat  # noqa: E402

import diagnostyka  # noqa: E402
import run_all  # noqa: E402


def _komorka(nb, tag):
    return next(c for i, c in enumerate(nb.cells) if run_all._tag(c, i) == tag)


def _indeks(nb, tag):
    return next(i for i, c in enumerate(nb.cells) if run_all._tag(c, i) == tag)


class TestLataOstrzezen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.fixtures = diagnostyka.zbuduj(cls.tmp / "diag")

    def setUp(self):
        self.nb = nbformat.read(run_all.NOTEBOOK, as_version=4)

    def test_kopia_bez_fikstur(self):
        cel = Path("C:/tmp/ata_warnings_x") / "export_results"
        kopia = run_all.patch_for_warnings(self.nb, cel)
        self.assertEqual(kopia.cells[0].metadata["tags"], [run_all.WARNINGS_TAG])
        self.assertIn("warnings.showwarning = _ata_rejestruj", kopia.cells[0].source)
        langdet = _komorka(kopia, "cell_langdet").source
        self.assertNotIn('warnings.filterwarnings("ignore")', langdet)
        self.assertIn(run_all.WARNINGS_ALWAYS, langdet)
        korpus = _komorka(kopia, "cell_corpus").source
        self.assertIn(f"PROJECT_DIR = Path({str(cel)!r}) / PROJECT_NAME", korpus)
        # Oryginał nietknięty: tryb nie może zapisać łaty do notatnika w repo.
        self.assertEqual(len(kopia.cells), len(self.nb.cells) + 1)
        self.assertIn('warnings.filterwarnings("ignore")', _komorka(self.nb, "cell_langdet").source)

    def test_kopia_z_fikstur_nie_czyta_configa(self):
        kopia = run_all.patch_for_warnings(self.nb, self.tmp / "exp", self.fixtures, "http://127.0.0.1:1/p.html")
        korpus = _komorka(kopia, "cell_corpus").source
        nadpisanie = korpus.index("SOURCE_FILE = " + repr(str(self.fixtures["pdf"])))
        # Nadpisanie stoi PO wczytaniu configa, więc config nic nie zmienia.
        self.assertGreater(nadpisanie, korpus.index("_CONFIG_PATH = None"))
        self.assertIn("ENABLE_SENTIMENT = True", korpus[nadpisanie:])
        self.assertIn(f"OCR_LANGS = {diagnostyka.OCR_JEZYKI!r}", korpus[nadpisanie:])
        self.assertEqual(_indeks(kopia, run_all.LOADERS_TAG), _indeks(kopia, "cell_corpus") + 1)
        qa = next(i for i, c in enumerate(kopia.cells) if run_all._tag(c, i) in run_all.QA_TAGS)
        self.assertEqual(_indeks(kopia, run_all.COMPONENTS_TAG), qa - 1)
        for tag in (run_all.WARNINGS_TAG, run_all.LOADERS_TAG, run_all.COMPONENTS_TAG, "cell_corpus"):
            with self.subTest(komorka=tag):
                compile(_komorka(kopia, tag).source, tag, "exec")

    def test_brak_kotwicy_odmawia(self):
        langdet = _komorka(self.nb, "cell_langdet")
        langdet.source = langdet.source.replace('warnings.filterwarnings("ignore")', "pass")
        with self.assertRaises(ValueError) as e:
            run_all.patch_for_warnings(self.nb, Path("x"))
        self.assertIn("cell_langdet", str(e.exception))

    def test_kotwica_dwa_razy_odmawia(self):
        korpus = _komorka(self.nb, "cell_corpus")
        korpus.source += "\n" + run_all.WARNINGS_ANCHORS[2][1]
        with self.assertRaises(ValueError):
            run_all.patch_for_warnings(self.nb, Path("x"), self.fixtures, "")


class TestRejestr(unittest.TestCase):
    def test_rejestr_widzi_ostrzezenie_polkniete_przez_except(self):
        """Powód rejestru zamiast `error`: kod łapiący wyjątki połykał
        ostrzeżenie zamienione w wyjątek (easyocr w _ocr_image_array)."""
        ns = {}
        with warnings.catch_warnings():
            exec(run_all.WARNINGS_RECORDER, ns)
            try:
                warnings.warn("polkniete", FutureWarning)
                raise ValueError
            except Exception:
                pass
            warnings.warn("drugie", UserWarning)
        self.assertEqual([w[:2] for w in ns["_ATA_OSTRZEZENIA"]],
                         [["FutureWarning", "polkniete"], ["UserWarning", "drugie"]])

    def test_znane_nie_licza_sie_do_wyniku(self):
        pin = ["UserWarning", "'pin_memory' argument is set as true but no accelerator is found", "x.py:1"]
        nowe = ["FutureWarning", "something changes", "y.py:2"]
        bufor = io.StringIO()
        with contextlib.redirect_stdout(bufor):
            self.assertEqual(run_all._print_warnings([("cell_a", [pin, pin]), ("cell_b", [nowe])]), 1)
            self.assertEqual(run_all._print_warnings([("cell_a", [pin])]), 0)
        self.assertIn("FutureWarning: something changes", bufor.getvalue())
        self.assertNotIn("'pin_memory' argument", bufor.getvalue())


class TestFikstury(unittest.TestCase):
    def test_pdf_ma_wszystkie_sciezki(self):
        import pdfplumber
        import naprawa_zrodel
        pliki = diagnostyka.zbuduj(Path(tempfile.mkdtemp()))
        with pdfplumber.open(pliki["pdf"]) as pdf:
            self.assertEqual(len(pdf.pages), 6)
            teksty = [s.extract_text() or "" for s in pdf.pages]
            self.assertTrue(all(diagnostyka.NAGLOWEK in x for x in teksty[:4]))
            self.assertIn("Sigurðsson", teksty[3])
            self.assertIn("(cid:", teksty[4])
            ocena = naprawa_zrodel.napraw_strone(pdf.pages[4], {})
            self.assertGreaterEqual(ocena.znaczniki, naprawa_zrodel.PROG_PODEJRZANYCH)
            self.assertEqual(ocena.nierozwiazane, 0)
            self.assertEqual(teksty[5], "")          # skan: tylko obraz
        from docx import Document
        self.assertIn(diagnostyka.SLOWA_LOADEROW["docx"], Document(pliki["docx"]).paragraphs[0].text)
        self.assertIn(diagnostyka.ROSKA, pliki["txt"].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
