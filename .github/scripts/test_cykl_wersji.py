"""Testy cykl_wersji.py — jawne otwarcie cyklu wydania (stdlib unittest).

Każdy test buduje mini-repo gita w katalogu tymczasowym. Bliźniak:
`test_cykl_wersji.py` w Reżyserze Audio GPT (tam granicą jest domknięcie
importów z `main.py`, tu: wszystko poza `.github/`).

Uruchom:  python .github/scripts/test_cykl_wersji.py
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cykl_wersji as cw  # noqa: E402

KORZEN = Path(__file__).resolve().parents[2]


def _git(katalog, *argumenty):
    subprocess.run(["git", *argumenty], cwd=katalog, check=True, capture_output=True)


class TestCyklWersji(unittest.TestCase):
    def setUp(self):
        katalog = tempfile.TemporaryDirectory(prefix="ata_test_cykl_")
        self.addCleanup(katalog.cleanup)
        self.repo = Path(katalog.name)
        _git(self.repo, "init", "-q")
        _git(self.repo, "config", "user.email", "t@example.invalid")
        _git(self.repo, "config", "user.name", "t")
        (self.repo / ".github").mkdir()
        (self.repo / ".github" / "ci.yml").write_text("a: 1\n", encoding="utf-8")
        (self.repo / "modul.py").write_text("X = 1\n", encoding="utf-8")
        self._version("1.13.0")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-q", "-m", "v1.13.0")
        _git(self.repo, "tag", "v1.13.0")
        stary = os.getcwd()
        os.chdir(self.repo)
        self.addCleanup(os.chdir, stary)

    def _version(self, tekst):
        (self.repo / "VERSION").write_text(tekst + "\n", encoding="utf-8")

    def test_spoczynek_po_wydaniu(self):
        self.assertEqual(cw.stan_cyklu()["stan"], "wydany")

    def test_zmiana_ci_nie_otwiera_cyklu(self):
        (self.repo / ".github" / "ci.yml").write_text("a: 2\n", encoding="utf-8")
        self.assertEqual(cw.stan_cyklu()["stan"], "wydany")

    def test_praca_bez_wip_to_blad(self):
        (self.repo / "modul.py").write_text("X = 2\n", encoding="utf-8")
        stan = cw.stan_cyklu()
        self.assertEqual((stan["stan"], stan["winowajcy"]), ("nieotwarty", ["modul.py"]))
        with self.subTest("kod wyjścia"):
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cw.main([]), 1)

    def test_wip_otwiera_cykl(self):
        (self.repo / "modul.py").write_text("X = 2\n", encoding="utf-8")
        for wersja, typ in (("2.0.0-WIP", "minor/major"), ("1.14-WIP", "minor/major"),
                            ("1.13.1-WIP", "patch")):
            with self.subTest(wersja=wersja):
                self._version(wersja)
                stan = cw.stan_cyklu()
                self.assertEqual((stan["stan"], stan["typ"]), ("wip", typ))

    def test_wip_wydanej_wersji_to_blad(self):
        self._version("1.13.0-WIP")
        self.assertEqual(cw.stan_cyklu()["stan"], "wip_wydanej")

    def test_zamykanie_i_brak_tagow(self):
        self._version("2.0.0")
        self.assertEqual(cw.stan_cyklu()["stan"], "zamykanie")
        _git(self.repo, "tag", "-d", "v1.13.0")
        self.assertEqual(cw.stan_cyklu()["stan"], "nieznany")

    def test_brak_version(self):
        (self.repo / "VERSION").unlink()
        self.assertEqual(cw.stan_cyklu()["stan"], "nieznany")


class TestPrawdziweRepo(unittest.TestCase):
    def test_version_istnieje_i_parsuje_sie(self):
        """`VERSION` jest wymagany od ATA 2.0 (`wydanie.py` bez niego odmawia)."""
        self.assertIsNotNone(cw.czytaj_wersje(KORZEN))


if __name__ == "__main__":
    unittest.main()
