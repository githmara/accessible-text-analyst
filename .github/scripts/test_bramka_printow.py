"""Testy bramka_printow.py na tymczasowym katalogu — każdy hard-kod musi zostać złapany.

Uruchom:  python .github/scripts/test_bramka_printow.py   (tylko stdlib)
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bramka_printow as b  # noqa: E402


class TestBramkaPrintow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.k = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def wynik(self, kod, nazwa="skrypt.py"):
        (self.k / nazwa).write_text(kod, encoding="utf-8")
        return b.main(self.k)

    def test_czyste_przechodzi(self):
        kod = ("print(t(UI_LANG, 'dispatcher.ok', path=p))\n"
               "print(tr(UI_LANG, 'kirja.scan'))\n"
               "print(f\"  - {t(UI_LANG, 'a.b')}: {x}\")\n"
               "print()\nprint('  - ', x, ' : ')\n"
               "print(f\"       ! {v['warning']}\")\n"
               "print(d['status'])\n")
        self.assertEqual(self.wynik(kod), 0)

    def test_goly_literal(self):
        self.assertEqual(self.wynik("print('[ERROR] library missing')\n"), 1)

    def test_literal_w_fstringu(self):
        self.assertEqual(self.wynik("print(f'Saved {path}')\n"), 1)

    def test_konkatenacja_i_ifexp(self):
        self.assertEqual(self.wynik("print('Plik: ' + t(UI_LANG, 'x'))\n"), 1)
        self.assertEqual(self.wynik("print(t(UI_LANG, 'x') if ok else 'failed')\n"), 1)

    def test_cyrylica_tez_jest_litera(self):
        self.assertEqual(self.wynik("print('Готово')\n"), 1)

    def test_wyjatek_wymaga_powodu(self):
        self.assertEqual(self.wynik("print('OK')  # bramka-printow: ok — znacznik protokołu\n"), 0)
        self.assertEqual(self.wynik("print('OK')  # bramka-printow: ok\n"), 1)

    def test_notatnik_wylaczony_a_nowy_skrypt_objety(self):
        (self.k / "accessible_text_analyst.py").write_text("print('Корпус готов')\n", encoding="utf-8")
        self.assertEqual(b.main(self.k), 0)
        self.assertEqual(self.wynik("print('nowy skrypt')\n", nazwa="nowy.py"), 1)

    def test_prawdziwe_repo_przechodzi(self):
        self.assertEqual(b.main(), 0)


if __name__ == "__main__":
    unittest.main()
