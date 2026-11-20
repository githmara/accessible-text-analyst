"""Testy helsinki_reacts.py (v2.1.0) — atrapa klienta, zero sieci.

Pilnujemy kontraktu, który ma działać niezależnie od edytowalnego promptu: kolejności
wyboru promptu i języka, wejścia z folderu eksportu, oraz pomostu z Księgą — odpowiedzi
z klucza NIGDY nie trafiają do modelu, a teorie trafiają do właściwych luk.

Uruchom:  python .github/scripts/test_helsinki_reacts.py
"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import helsinki_reacts as hr  # noqa: E402

GAP = hr.GAP

HTML = """<!DOCTYPE html><html lang="fi"><head><meta charset="utf-8"/><title>Otsikko</title></head>
<body><h1>Raportin otsikko</h1><p lang="fi">Ensimmäinen   kappale.</p>
<p lang="fi">Toinen <span lang="pl">Kraków</span> kappale.</p></body></html>"""

# Wpis z trzema lukami w kluczu: 1 i 3 otwarte, 2 usunięta jako oczywista (wpisana w tekst).
KIRJA_MD = f"""# Sanomattomien kirja

---

## Merkintä 1 — Testi

<!-- kirja:id=abc123 | folder=Kansio | block=1 | gaps=2/3 | date=2026-11-20 -->

**KATLA** *(varoitusjärjestelmä)*: LUMI . TUULI .

**VIENO:**

> [whispers] Lumi putoaa {GAP}.
>
> Tuuli kantaa ilmeisen sanan.
>
> Kaikki päättyy {GAP}.

---

## Merkintä 2 — Muu

<!-- kirja:id=zzz999 | folder=Muu | block=1 | gaps=1/1 | date=2026-11-20 -->

**KATLA** *(varoitusjärjestelmä)*: JÄÄ .

**VIENO:**

> Jää {GAP}.
"""
AVAIN = {
    "abc123": {"entry": 1, "folder": "Kansio",
               "open": {"1": "SALAINENVASTAUSYKSI", "3": "SALAINENVASTAUSKOLME"},
               "removed_obvious": [{"gap": "2", "answer": "ilmeisen", "guess": "ilmeisen"}]},
    "zzz999": {"entry": 2, "folder": "Muu", "open": {"1": "SALAINENMUU"}, "removed_obvious": []},
}
GUESSES = {"guesses": {"1": "hiljaa", "2": "ilmeisen", "3": "pimeään"}}


class _Srodowisko(unittest.TestCase):
    """Tymczasowe export_results z folderem, Księgą, kluczem i zgadywaniami."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        exp = base / "export_results"
        (exp / "Kansio").mkdir(parents=True)
        (exp / "Kansio" / hr.HTML_NAME).write_text(HTML, encoding="utf-8")
        (exp / "Sanomattomien_kirja.md").write_text(KIRJA_MD, encoding="utf-8")
        (exp / "Sanomattomien_kirja.avain.json").write_text(json.dumps(AVAIN), encoding="utf-8")
        (exp / "_kirja_tyotila" / "abc123").mkdir(parents=True)
        (exp / "_kirja_tyotila" / "abc123" / "guesses.json").write_text(
            json.dumps(GUESSES), encoding="utf-8")
        self.base, self.exp = base, exp
        self.patches = [
            mock.patch.object(hr, "EXPORT_DIR", exp),
            mock.patch.object(hr, "STREAMS_DIR", exp / "_streams"),
            mock.patch.object(hr, "KIRJA", exp / "Sanomattomien_kirja.md"),
            mock.patch.object(hr, "KIRJA_AVAIN", exp / "Sanomattomien_kirja.avain.json"),
            mock.patch.object(hr, "KIRJA_TYOTILA", exp / "_kirja_tyotila"),
            mock.patch.object(hr, "ROOT", base),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()


class TestPrompt(unittest.TestCase):
    def test_przykladowy_prompt_laduje_sie_bez_komentarzy(self):
        tekst = hr.load_prompt(hr.PROMPT_DEFAULT)
        self.assertTrue(tekst)
        self.assertNotIn("<!--", tekst)
        self.assertNotIn("Edit a COPY", tekst)
        self.assertIn("Valtteri", tekst)

    def test_pusty_albo_brak_pliku_to_none(self):
        with tempfile.TemporaryDirectory() as d:
            sam_komentarz = Path(d) / "p.md"
            sam_komentarz.write_text("<!-- tylko komentarz -->\n", encoding="utf-8")
            self.assertIsNone(hr.load_prompt(sam_komentarz))
            self.assertIsNone(hr.load_prompt(Path(d) / "brak.md"))

    def test_kolejnosc_wyboru_promptu(self):
        with tempfile.TemporaryDirectory() as d:
            lokalny = Path(d) / "helsinki_reacts.md"
            with mock.patch.object(hr, "PROMPT_LOCAL", lokalny):
                self.assertEqual(hr.prompt_path(None), hr.PROMPT_DEFAULT)
                lokalny.write_text("moj", encoding="utf-8")
                self.assertEqual(hr.prompt_path(None), lokalny)
                self.assertEqual(hr.prompt_path("inny.md"), Path("inny.md"))


class TestJezyk(unittest.TestCase):
    def test_kolejnosc_cli_config_ui(self):
        with mock.patch.object(hr, "UI_LANG", "fi"):
            self.assertEqual(hr.stream_language(None, {}), "fi")
            self.assertEqual(hr.stream_language(None, {"reacts_lang": "pl"}), "pl")
            self.assertEqual(hr.stream_language("DE", {"reacts_lang": "pl"}), "de")
            self.assertIsNone(hr.stream_language("xx", {}))

    def test_fi_to_sam_stream_inne_to_przeklad(self):
        self.assertIn("not a translation", hr.language_block("fi"))
        blok = hr.language_block("it")
        self.assertIn("Italian", blok)
        self.assertIn("Finnish interjections", blok)


class TestWejscie(_Srodowisko):
    def test_html_bez_naglowkow_i_tytulu(self):
        tekst = hr.html_to_text(self.exp / "Kansio" / hr.HTML_NAME)
        self.assertEqual(tekst, "Ensimmäinen kappale.\n\nToinen Kraków kappale.")

    def test_folder_plik_i_brak(self):
        src = hr.resolve_source("Kansio")
        self.assertEqual(src[1:], ("Kansio", "Kansio"))
        plik = self.base / "nagranie.txt"
        plik.write_text("teksti", encoding="utf-8")
        self.assertEqual(hr.resolve_source(str(plik))[1:], ("nagranie", None))
        self.assertIsNone(hr.resolve_source("NieMaTakiego"))

    def test_tytul_z_nazwy(self):
        self.assertEqual(hr.title_from_name("PiS-puolueen_verinen__sota"), "PiS-puolueen verinen sota")


class TestKsiega(_Srodowisko):
    def test_luki_numerowane_a_teorie_tylko_otwartych(self):
        tekst, wpisy, teorie = hr.kirja_bridge("Kansio")
        self.assertEqual((wpisy, teorie), (1, 2))
        self.assertIn(f"Lumi putoaa {GAP}(1).", tekst)
        self.assertIn(f"Kaikki päättyy {GAP}(2).", tekst)
        self.assertIn("(1) hiljaa", tekst)
        self.assertIn("(2) pimeään", tekst)   # luka 3 klucza = druga luka tekstu
        self.assertNotIn("[whispers]", tekst)
        self.assertNotIn("Muu", tekst)        # wpis innego folderu nie wchodzi

    def test_odpowiedzi_klucza_nigdy_nie_wychodza(self):
        msg, _, _ = hr.build_user_message(hr.resolve_source("Kansio"), "pl", True)
        for wpis in AVAIN.values():
            for odpowiedz in wpis["open"].values():
                self.assertNotIn(odpowiedz, msg)

    def test_bez_flagi_brak_ksiegi(self):
        msg, wpisy, _ = hr.build_user_message(hr.resolve_source("Kansio"), "pl", False)
        self.assertEqual(wpisy, 0)
        self.assertNotIn("Sanomattomien kirja", msg)
        self.assertNotIn(hr.KIRJA_RULES, msg)

    def test_z_flaga_zasady_i_jezyk_na_koncu(self):
        msg, _, _ = hr.build_user_message(hr.resolve_source("Kansio"), "pl", True)
        self.assertIn(hr.KIRJA_RULES, msg)
        self.assertTrue(msg.endswith(hr.language_block("pl")))

    def test_rozjazd_luk_daje_mgle_bez_teorii(self):
        avain = json.loads(json.dumps(AVAIN))
        avain["abc123"]["open"]["4"] = "X"
        (self.exp / "Sanomattomien_kirja.avain.json").write_text(json.dumps(avain), encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()):
            tekst, wpisy, teorie = hr.kirja_bridge("Kansio")
        self.assertEqual((wpisy, teorie), (1, 0))
        self.assertNotIn("(1) hiljaa", tekst)
        self.assertIn(GAP, tekst)


def _odpowiedz(tresc, finish="stop"):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=tresc), finish_reason=finish)],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=20))


class TestWywolanie(_Srodowisko):
    def _args(self, **kw):
        base = dict(kirja=False, effort="low", min_chars=50)
        base.update(kw)
        return SimpleNamespace(**base)

    def _settings(self):
        return SimpleNamespace(provider="openrouter", model="m", endpoint="e")

    def test_zapis_i_unikalna_nazwa(self):
        src = hr.resolve_source("Kansio")
        tresc = "**Valtteri:** " + "Moi! " * 30
        with mock.patch.object(hr.llm_klient, "chat_text", return_value=_odpowiedz(tresc)) as ct, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(hr.process(src, "PROMPT", (self._settings(), None), self._args(), "fi"))
            self.assertTrue(hr.process(src, "PROMPT", (self._settings(), None), self._args(), "fi"))
        wyslane = ct.call_args.args[2]
        self.assertEqual(wyslane[0], {"role": "system", "content": "PROMPT"})
        self.assertEqual(ct.call_args.kwargs["effort"], "low")
        pliki = sorted(p.name for p in (self.exp / "_streams").iterdir())
        self.assertEqual(pliki, ["Kansio.md", "Kansio_2.md"])

    def test_krotka_odpowiedz_odrzucona(self):
        src = hr.resolve_source("Kansio")
        with mock.patch.object(hr.llm_klient, "chat_text", return_value=_odpowiedz("Nie mogę.")), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertFalse(hr.process(src, "PROMPT", (self._settings(), None), self._args(), "fi"))
        self.assertFalse((self.exp / "_streams").exists())

    def test_main_brak_zrodla_i_dry_run(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(hr.main(["NieMaTakiego", "--dry-run"]), 1)
            self.assertEqual(hr.main(["Kansio", "--dry-run", "--lang", "en"]), 0)
            self.assertEqual(hr.main(["Kansio", "--dry-run", "--lang", "xx"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=1)
