"""Testy wydanie.py — stdlib unittest (ATA nie ma pytesta w zależnościach).

Uruchom:  python .github/scripts/test_wydanie.py
Workflow odpala je przed każdą decyzją o wydaniu.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wydanie as w  # noqa: E402

NOTATKI = """# Release notes

intro

---

## v1.8.0 — Python 3.14, bounds

**Theme.** Body line.

### Distribution
Source-only.

---

## v1.7.1 — older

Old body.
"""
TAGI = "a\trefs/tags/v1.0\nb\trefs/tags/v1.0^{}\nc\trefs/tags/v1.7.1\nd\trefs/tags/v1.1.5^{}\n"


class TestWydanie(unittest.TestCase):
    def test_pierwsza_sekcja_tag_tytul_tresc(self):
        tag, wersja, tytul, tresc = w.pierwsza_sekcja(NOTATKI)
        self.assertEqual((tag, wersja), ("v1.8.0", (1, 8, 0)))
        self.assertEqual(tytul, "v1.8.0 — Python 3.14, bounds")
        self.assertTrue(tresc.startswith("**Theme.**"))
        self.assertTrue(tresc.endswith("Source-only."))
        self.assertNotIn("v1.7.1", tresc)
        self.assertNotIn("---", tresc)

    def test_ostatnia_sekcja_w_pliku(self):
        _, _, _, tresc = w.pierwsza_sekcja("## v2.0.0 — last\n\nOnly body.\n")
        self.assertEqual(tresc, "Only body.")

    def test_tagi_dwuczlonowe_i_adnotowane(self):
        self.assertEqual(w.wersje_tagow(TAGI), {(1, 0, 0), (1, 7, 1)})

    def test_decyzje(self):
        tagi = {(1, 0, 0), (1, 7, 1)}
        self.assertEqual(w.decyzja((1, 8, 0), tagi), "wydaj")
        self.assertEqual(w.decyzja((1, 7, 1), tagi), "pomin")
        self.assertEqual(w.decyzja((1, 0, 0), set()), "wydaj")
        with self.assertRaises(w.BladWydania):
            w.decyzja((1, 7, 0), tagi)

    def test_zly_naglowek_i_pusta_tresc(self):
        for zle in ("## 1.8.0 — no v\n\nbody", "## v1.8 — two parts\n\nbody",
                    "## v1.8.0\n\nno title", "nothing at all"):
            with self.assertRaises(w.BladWydania, msg=zle):
                w.pierwsza_sekcja(zle)
        with self.assertRaises(w.BladWydania):
            w.pierwsza_sekcja("## v1.8.0 — empty\n\n---\n\n## v1.7.0 — x\n\nb")

    def test_tytul_nie_przenosi_znakow_sterujacych_powloki(self):
        # Tytuł trafia do pliku, nie do powłoki — ale i tak nie może zawierać
        # nowej linii, bo `## …` jest dopasowywane do końca linii.
        _, _, tytul, _ = w.pierwsza_sekcja("## v3.0.0 — a $(rm -rf /) `x`\nbody\n")
        self.assertEqual(tytul, "v3.0.0 — a $(rm -rf /) `x`")
        self.assertNotIn("\n", tytul)

    def test_version_musi_zrownac_sie_z_sekcja(self):
        """Od ATA 2.0: wydanie tylko przy `VERSION` == sekcja, bez `-WIP`."""
        w.zgodnosc_z_version((2, 0, 0), "2.0.0\n")
        for zly in (None, "2.0.0-WIP", "2.0-WIP", "1.13.0", "2.0.1", "dwa"):
            with self.assertRaises(w.BladWydania, msg=zly):
                w.zgodnosc_z_version((2, 0, 0), zly)
        # `X.Y` bez patcha to ta sama wersja co `X.Y.0`.
        w.zgodnosc_z_version((2, 0, 0), "2.0")

    def test_main_odmawia_wydania_przy_wip(self):
        """Ścieżka workflowu: nowa sekcja + `VERSION` z `-WIP` = błąd, a sekcja
        już otagowana = spokojny `pomin` niezależnie od `VERSION`."""
        import os
        import tempfile
        katalog = tempfile.TemporaryDirectory(prefix="ata_test_wydanie_")
        self.addCleanup(katalog.cleanup)
        k = Path(katalog.name)
        (k / "release_notes.md").write_text(NOTATKI, encoding="utf-8")
        (k / "tagi.txt").write_text(TAGI, encoding="utf-8")
        stary = os.getcwd()
        os.chdir(k)
        self.addCleanup(os.chdir, stary)
        stare_argv = sys.argv
        self.addCleanup(setattr, sys, "argv", stare_argv)
        sys.argv = ["wydanie.py", str(k / "tagi.txt")]
        os.environ["RUNNER_TEMP"] = str(k)
        self.addCleanup(os.environ.pop, "RUNNER_TEMP", None)
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            (k / "VERSION").write_text("1.8.0-WIP\n", encoding="utf-8")
            self.assertEqual(w.main(), 1)
            (k / "VERSION").write_text("1.8.0\n", encoding="utf-8")
            self.assertEqual(w.main(), 0)
            (k / "tagi.txt").write_text(TAGI + "e\trefs/tags/v1.8.0\n", encoding="utf-8")
            (k / "VERSION").write_text("1.9.0-WIP\n", encoding="utf-8")
            self.assertEqual(w.main(), 0)


if __name__ == "__main__":
    unittest.main()
