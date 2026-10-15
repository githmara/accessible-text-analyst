"""Testy parytet.py na tymczasowych katalogach — każdy rozjazd musi zostać złapany.

Uruchom:  python .github/scripts/test_parytet.py   (wymaga PyYAML)
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import parytet as p  # noqa: E402

README_EN = "# T\n\n## A\n\n```bash\n# install\npip install -r requirements.txt\n```\n\n[x](y)\n"


class TestParytet(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.k = Path(self.tmp.name)
        for j in ("pl", "fi"):
            (self.k / "dictionaries" / j).mkdir(parents=True)
            (self.k / "dictionaries" / j / "r.yaml").write_text(
                "a:\n  b: 'x {n}'\n  c: 'y'\n", encoding="utf-8")
        (self.k / "README.md").write_text(README_EN, encoding="utf-8")
        (self.k / "README_fi.md").write_text(README_EN.replace("# install", "# asenna"), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def bledy(self):
        return p.bledy_slownikow(self.k / "dictionaries") + p.bledy_readme(self.k)

    def test_parytet_ok_mimo_przetlumaczonego_komentarza(self):
        self.assertEqual(self.bledy(), [])

    def test_brak_klucza(self):
        (self.k / "dictionaries/fi/r.yaml").write_text("a:\n  b: 'x {n}'\n", encoding="utf-8")
        self.assertTrue(any("key missing: a.c" in b for b in self.bledy()))

    def test_nadmiarowy_klucz(self):
        (self.k / "dictionaries/fi/r.yaml").write_text(
            "a:\n  b: 'x {n}'\n  c: 'y'\n  d: 'z'\n", encoding="utf-8")
        self.assertTrue(any("not in pl: a.d" in b for b in self.bledy()))

    def test_zgubiony_placeholder(self):
        (self.k / "dictionaries/fi/r.yaml").write_text("a:\n  b: 'x'\n  c: 'y'\n", encoding="utf-8")
        self.assertTrue(any("placeholders" in b for b in self.bledy()))

    def test_brak_pliku_w_paczce(self):
        (self.k / "dictionaries/fi/r.yaml").unlink()
        self.assertTrue(any("file missing" in b for b in self.bledy()))

    def test_zmienione_polecenie_w_bloku_kodu(self):
        (self.k / "README_fi.md").write_text(README_EN.replace("requirements.txt", "vaatimukset.txt"), encoding="utf-8")
        self.assertTrue(any("code block 1" in b for b in self.bledy()))

    def test_zgubiony_link_i_naglowek(self):
        (self.k / "README_fi.md").write_text(README_EN.replace("[x](y)", "x").replace("## A", "A"), encoding="utf-8")
        bledy = " ".join(self.bledy())
        self.assertIn("links", bledy)
        self.assertIn("headings", bledy)

    def test_prawdziwe_repo_przechodzi(self):
        self.assertEqual(p.bledy_slownikow(p.KORZEN / "dictionaries") + p.bledy_readme(p.KORZEN), [])


if __name__ == "__main__":
    unittest.main()
