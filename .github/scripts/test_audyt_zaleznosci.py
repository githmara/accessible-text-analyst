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

    def test_drugi_zegar_wiek_bez_nowego_minora(self):
        # Budzik: projekt nie wydaje, wiec zegar wersji stoi - hold wygasa po czasie.
        limit = az.WIEK_HOLDU_DNI
        self.assertEqual(az.ocen_wstrzymanie("trzymana", "1.12.0", (1, 12, 0), limit), "trzymana")
        self.assertEqual(az.ocen_wstrzymanie("trzymana", "1.12.0", (1, 12, 0), limit + 1),
                         "przeterminowana_wiek")
        self.assertEqual(az.ocen_wstrzymanie("ok", "1.12.0", (1, 12, 0), 999), "ok")

    def test_wiek_linii_z_git_blame(self):
        wieki = az.wiek_linii_manifestu()
        if not wieki:
            self.skipTest("git blame unavailable")
        self.assertIn("numpy", wieki)
        self.assertIn("torch", wieki)          # linia opcjonalna tez sie liczy

    def test_wiek_tylko_z_linii_hold(self):
        """Komentarz nagłówka „# fonttools 4.67.0: …” stał przed wpisem i dawał
        fonttools wiek komentarza zamiast linii z granicą (audyt 2026-11-13)."""
        import os
        import subprocess
        from datetime import date
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            plik = repo / "requirements.txt"
            env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                   "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}

            def commit(tresc, data):
                plik.write_text(tresc, encoding="utf-8")
                e = {**env, "GIT_AUTHOR_DATE": data, "GIT_COMMITTER_DATE": data}
                subprocess.run(["git", "add", "."], cwd=repo, check=True, env=e)
                subprocess.run(["git", "commit", "-qm", "x"], cwd=repo, check=True, env=e)

            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            commit("# fonttools 4.67.0: stary komentarz\n", "2020-01-01T12:00:00")
            commit("# fonttools 4.67.0: stary komentarz\nfonttools<4.69  # hold: 1.13.0\n"
                   "# torch<2.16  # hold: 1.13.0\n", "2026-01-01T12:00:00")
            wieki = az.wiek_linii_manifestu(plik, dzis=date(2026, 1, 11))
            self.assertEqual(wieki, {"fonttools": 10, "torch": 10})
            # Komentarz prozą z `hold:` nad wpisem nie podaje wieku (bliźniak
            # Reżysera, audyt 2026-11-13) — tu `_WPIS` wymaga całej linii-wpisu.
            commit("# fonttools: hold: 1.13.0 przedluzony\nfonttools<4.69  # hold: 1.13.0\n",
                   "2026-01-05T12:00:00")
            self.assertEqual(az.wiek_linii_manifestu(plik, dzis=date(2026, 1, 11)), {"fonttools": 10})
            # Płytki klon: blame odmłodziłby hold — wiek nieznany, nie świeży.
            klon = Path(tmp) / "klon"
            subprocess.run(["git", "clone", "-q", "--depth", "1", repo.as_uri(), str(klon)],
                           check=True, capture_output=True)
            self.assertTrue(az._klon_plytki(klon))
            self.assertEqual(az.wiek_linii_manifestu(klon / "requirements.txt"), {})

    def test_modele_hf_z_notatnika(self):
        """Audyt 2026-11-13: oba modele islandzkie wskazywały nieistniejące
        repozytoria — audyt musi widzieć każdą nazwę, także wciętą w komórce."""
        modele = az.modele_hf()
        self.assertIn("grammatek/icelandic-ner-bert", modele)
        self.assertIn("mideind/IceBERT", modele)
        self.assertIn("cardiffnlp/twitter-xlm-roberta-base-sentiment", modele)
        p = _plik('HF_X = "a/b"\n    SENTIMENT_MODEL = "c/d-1.0"\nHF_X = "a/b"\nINNE = "e/f"\n'
                  "OPENROUTER_MODEL = 'anthropic/claude'\n"
                  "NER: str = 'g/h'\n"
                  "pipeline('ner', model=HF_X, tokenizer=AutoTokenizer.from_pretrained(NER))\n"
                  "pipeline('x', model=SENTIMENT_MODEL)\n"
                  'AutoModel.from_pretrained("i/j")\n'
                  "pipeline('y', model='k/l')\n")
        # Od użycia: stała nieprzekazana do modelu (OPENROUTER_MODEL, INNE) nie
        # jest nazwą Hubu; apostrofy, adnotacja i literał w wywołaniu — są.
        self.assertEqual(az.modele_hf(p), ["a/b", "g/h", "c/d-1.0", "i/j", "k/l"])

    def test_model_hf_istnieje_rozroznia_brak_od_sieci(self):
        import io
        import urllib.error
        from unittest import mock

        def blad(kod):
            return urllib.error.HTTPError("u", kod, "x", {}, io.BytesIO())

        with mock.patch("urllib.request.urlopen", side_effect=blad(401)):
            self.assertIs(az.model_hf_istnieje("mideind/IceBERT-base"), False)
        with mock.patch("urllib.request.urlopen", side_effect=blad(503)):
            self.assertIsNone(az.model_hf_istnieje("x/y"))
        with mock.patch("urllib.request.urlopen", side_effect=OSError("offline")):
            self.assertIsNone(az.model_hf_istnieje("x/y"))

    def test_znacznik_budzika(self):
        import json
        from datetime import date
        p = Path(tempfile.mkdtemp()) / "z.json"
        self.assertTrue(az.zapisz_znacznik(["x"], p, dzis=date(2026, 11, 12)))
        dane = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual((dane["format"], dane["data"], dane["do_decyzji"]),
                         (1, "2026-11-12", ["x"]))

    def test_wersja_z_gornej_sekcji_notatek(self):
        p = _plik("# Release notes\n\n## v1.13.0 — tytuł\n\n## v1.12.0 — starszy\n")
        self.assertEqual(az.wersja_projektu(p), (1, 13, 0))
        self.assertIsNone(az.wersja_projektu(_plik("bez sekcji\n")))
        self.assertIsNotNone(az.wersja_projektu())


if __name__ == "__main__":
    unittest.main(verbosity=1)
