"""Testy helsinki_reacts.py (v2.1.0) — atrapa klienta, zero sieci.

Pilnujemy kontraktu, który ma działać niezależnie od edytowalnego promptu: kolejności
wyboru promptu, języka i effortu, wejścia z folderu eksportu i z pliku, zapisu wyniku,
oraz pomostu z Księgą — odpowiedzi z klucza NIGDY nie trafiają do modelu, ani wprost,
ani przez teorię dzielącą z nimi rdzeń słowa. Testy nie czytają prawdziwego config.json
ani helsinki_reacts.md programisty (audyt 2.1.0, #13).

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
from shamanic_locale import t  # noqa: E402

GAP = hr.GAP

HTML = """<!DOCTYPE html><html lang="fi"><head><meta charset="utf-8"/><title>Otsikko</title></head>
<body><h1>Raportin otsikko</h1><p lang="fi">Ensimmäinen   kappale.</p>
<p lang="fi">Toinen <span lang="pl">Kraków</span> kappale.</p></body></html>"""


def _wpis(nr, id_, folder, fragmenty):
    vieno = "\n>\n".join(f"> {f}" for f in fragmenty)
    return (f"## Merkintä {nr} — Testi\n\n<!-- kirja:id={id_} | folder={folder} | block={nr} | "
            f"gaps=1/1 | date=2026-11-20 -->\n\n**KATLA** *(varoitusjärjestelmä)*: LUMI .\n\n"
            f"**VIENO:**\n\n{vieno}\n\n---\n")


# Kansio: dwa wpisy (numeracja luk ma iść dalej: 1, 2, potem 3). W pierwszym luka 2 klucza
# usunięta jako oczywista (wpisana w tekst). Lahella: teoria „Tusk” dzieli rdzeń z odpowiedzią.
KIRJA_MD = "# Sanomattomien kirja\n\n---\n\n" + "\n".join([
    _wpis(1, "abc123", "Kansio", [f"[whispers] Lumi putoaa {GAP}.", "Tuuli kantaa ilmeisen sanan.",
                                  f"Kaikki päättyy {GAP}."]),
    _wpis(2, "zzz999", "Muu", [f"Jää {GAP}."]),
    _wpis(3, "def456", "Kansio", [f"Toinen lohko {GAP}."]),
    _wpis(4, "nnn111", "Lahella", [f"Presidentti ja {GAP}.", f"Yö {GAP}."]),
])
AVAIN = {
    "abc123": {"folder": "Kansio", "open": {"1": "SALAINENVASTAUSYKSI", "3": "SALAINENVASTAUSKOLME"},
               "removed_obvious": [{"gap": "2", "answer": "ilmeisen", "guess": "ilmeisen"}]},
    "zzz999": {"folder": "Muu", "open": {"1": "SALAINENMUU"}, "removed_obvious": []},
    "def456": {"folder": "Kansio", "open": {"1": "SALAINENKOLMAS"}, "removed_obvious": []},
    "nnn111": {"folder": "Lahella", "open": {"1": "Donald Tusk", "2": "SALAINENYO"}, "removed_obvious": []},
}
GUESSES = {
    "abc123": {"guesses": {"1": "hiljaa", "2": "ilmeisen", "3": "pimeään"}},
    "def456": {"guesses": {"1": "tuuli"}},
    "nnn111": {"guesses": {"1": "Tusk", "2": "kylmä"}},
}


class _Srodowisko(unittest.TestCase):
    """Tymczasowe export_results z folderami, Księgą, kluczem i zgadywaniami; bez configu użytkownika."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        exp = base / "export_results"
        for folder in ("Kansio", "Lahella"):
            (exp / folder).mkdir(parents=True)
            (exp / folder / hr.HTML_NAME).write_text(HTML, encoding="utf-8")
        (exp / "Sanomattomien_kirja.md").write_text(KIRJA_MD, encoding="utf-8")
        (exp / "Sanomattomien_kirja.avain.json").write_text(json.dumps(AVAIN), encoding="utf-8")
        for id_, g in GUESSES.items():
            (exp / "_kirja_tyotila" / id_).mkdir(parents=True)
            (exp / "_kirja_tyotila" / id_ / "guesses.json").write_text(json.dumps(g), encoding="utf-8")
        self.base, self.exp = base, exp
        self.patches = [
            mock.patch.object(hr, "EXPORT_DIR", exp),
            mock.patch.object(hr, "STREAMS_DIR", exp / "_streams"),
            mock.patch.object(hr, "KIRJA", exp / "Sanomattomien_kirja.md"),
            mock.patch.object(hr, "KIRJA_AVAIN", exp / "Sanomattomien_kirja.avain.json"),
            mock.patch.object(hr, "KIRJA_TYOTILA", exp / "_kirja_tyotila"),
            mock.patch.object(hr, "ROOT", base),
            mock.patch.object(hr, "PROMPT_LOCAL", base / "brak_kopii.md"),
            mock.patch.object(hr, "read_config", lambda *a, **k: {}),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def src(self, arg="Kansio"):
        s = hr.resolve_source(arg)
        s.text = hr.read_source(s.path)
        return s


def _wycisz():
    out, err = io.StringIO(), io.StringIO()
    return out, err, contextlib.ExitStack()


class TestPrompt(unittest.TestCase):
    def test_przykladowy_prompt_laduje_sie_bez_komentarzy(self):
        tekst, blad = hr.load_prompt(hr.PROMPT_DEFAULT)
        self.assertIsNone(blad)
        self.assertNotIn("<!--", tekst)
        self.assertNotIn("Edit a COPY", tekst)
        self.assertIn("Valtteri", tekst)

    def test_bledy_pliku_promptu(self):
        with tempfile.TemporaryDirectory() as d:
            sam_komentarz = Path(d) / "p.md"
            sam_komentarz.write_text("<!-- tylko komentarz -->\n", encoding="utf-8")
            self.assertEqual(hr.load_prompt(sam_komentarz), (None, "reacts.err_prompt"))
            self.assertEqual(hr.load_prompt(Path(d) / "brak.md"), (None, "reacts.err_prompt"))
            ansi = Path(d) / "ansi.md"
            ansi.write_bytes("Zażółć gęślą jaźń".encode("cp1250"))
            self.assertEqual(hr.load_prompt(ansi), (None, "reacts.err_prompt_encoding"))

    def test_kolejnosc_wyboru_promptu(self):
        with tempfile.TemporaryDirectory() as d:
            lokalny = Path(d) / "helsinki_reacts.md"
            with mock.patch.object(hr, "PROMPT_LOCAL", lokalny):
                self.assertEqual(hr.prompt_path(None), hr.PROMPT_DEFAULT)
                lokalny.write_text("moj", encoding="utf-8")
                self.assertEqual(hr.prompt_path(None), lokalny)
                self.assertEqual(hr.prompt_path("inny.md"), Path("inny.md"))


class TestJezykIEffort(unittest.TestCase):
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
        self.assertIn("Lumi's donation line", blok)

    def test_effort_automatyczny(self):
        claude = SimpleNamespace(provider="openrouter", model="anthropic/claude-sonnet-5.5")
        gpt = SimpleNamespace(provider="openai", model="gpt-6.1-sol")
        self.assertEqual(hr.effort_for(claude, None), "medium")
        self.assertEqual(hr.effort_for(gpt, None), "low")
        self.assertEqual(hr.effort_for(claude, "high"), "high")


class TestWejscie(_Srodowisko):
    def test_accessible_text_bez_naglowka_ata(self):
        tekst = hr.html_to_text(self.exp / "Kansio" / hr.HTML_NAME)
        self.assertEqual(tekst, "Ensimmäinen kappale.\n\nToinen Kraków kappale.")

    def test_cudzy_html_zachowuje_naglowki_i_granice(self):
        p = self.base / "oma.html"
        p.write_text("<h2>Luku yksi</h2><table><tr><td>Nimi</td><td>Ikä</td></tr>"
                     "<tr><td>Matti</td><td>40</td></tr></table><blockquote>Lainaus</blockquote>"
                     "<section>Osio</section><pre>rivi yksi\nrivi kaksi</pre>", encoding="utf-8")
        tekst = hr.html_to_text(p)
        self.assertEqual(tekst.split("\n\n"), ["Luku yksi", "Nimi Ikä", "Matti 40", "Lainaus",
                                               "Osio", "rivi yksi", "rivi kaksi"])

    def test_rozwiazywanie_zrodel(self):
        self.assertEqual((self.src().name, self.src().folder), ("Kansio", "Kansio"))
        inna_wielkosc = hr.resolve_source("kansio")
        self.assertEqual((inna_wielkosc.name, inna_wielkosc.folder), ("Kansio", "Kansio"))
        sciezka = hr.resolve_source(str(self.exp / "Kansio"))
        self.assertEqual(sciezka.folder, "Kansio")
        html = hr.resolve_source(str(self.exp / "Kansio" / hr.HTML_NAME))
        self.assertEqual((html.name, html.folder), ("Kansio", "Kansio"))
        plik = self.base / "nagranie.txt"
        plik.write_text("teksti", encoding="utf-8")
        z_pliku = hr.resolve_source(str(plik))
        self.assertEqual((z_pliku.name, z_pliku.folder, z_pliku.shadows_folder), ("nagranie", None, False))
        self.assertIsNone(hr.resolve_source("NieMaTakiego"))

    def test_plik_zaslaniajacy_folder_jest_zglaszany(self):
        with tempfile.TemporaryDirectory() as cwd, contextlib.chdir(cwd):
            Path("Kansio").write_text("teksti", encoding="utf-8")
            s = hr.resolve_source("Kansio")
            self.assertTrue(s.shadows_folder)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertTrue(hr._read_all([s]))
            self.assertIn(t(hr.UI_LANG, "reacts.info_file_shadows", name="Kansio"), out.getvalue())

    def test_tytul_z_nazwy(self):
        self.assertEqual(hr.title_from_name("PiS-puolueen_verinen__sota"), "PiS-puolueen verinen sota")


class TestKsiega(_Srodowisko):
    def test_numeracja_ciagla_miedzy_wpisami_i_teorie_otwartych(self):
        tekst, wpisy, teorie = hr.kirja_bridge("Kansio")
        self.assertEqual((wpisy, teorie), (2, 3))
        self.assertIn(f"Lumi putoaa {GAP}(1).", tekst)
        self.assertIn(f"Kaikki päättyy {GAP}(2).", tekst)
        self.assertIn(f"Toinen lohko {GAP}(3).", tekst)
        self.assertIn("(1) hiljaa", tekst)
        self.assertIn("(2) pimeään", tekst)   # luka 3 klucza = druga luka tekstu
        self.assertIn("(3) tuuli", tekst)
        self.assertNotIn("[whispers]", tekst)
        self.assertNotIn("Jää", tekst)        # wpis innego folderu nie wchodzi

    def test_teoria_z_rdzeniem_odpowiedzi_jest_wstrzymana(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            tekst, wpisy, teorie = hr.kirja_bridge("Lahella")
        self.assertEqual((wpisy, teorie), (1, 1))
        self.assertNotIn("Tusk", tekst)
        self.assertIn("(2) kylmä", tekst)
        self.assertIn(t(hr.UI_LANG, "reacts.warn_theories_withheld", id="nnn111", count=1), out.getvalue())

    def test_odpowiedzi_klucza_nigdy_nie_wychodza(self):
        for folder in ("Kansio", "Lahella"):
            with contextlib.redirect_stdout(io.StringIO()):
                msg, _, _ = hr.build_user_message(self.src(folder), "pl", True)
            for wpis in AVAIN.values():
                for odpowiedz in wpis["open"].values():
                    self.assertNotIn(odpowiedz, msg)

    def test_bez_flagi_brak_ksiegi(self):
        msg, wpisy, _ = hr.build_user_message(self.src(), "pl", False)
        self.assertEqual(wpisy, 0)
        self.assertNotIn("Sanomattomien kirja", msg)
        self.assertNotIn(hr.KIRJA_RULES, msg)

    def test_z_flaga_zasady_i_jezyk_na_koncu(self):
        msg, _, _ = hr.build_user_message(self.src(), "pl", True)
        self.assertIn(hr.KIRJA_RULES, msg)
        self.assertTrue(msg.endswith(hr.language_block("pl")))

    def _zly_klucz(self, wpis_abc):
        avain = json.loads(json.dumps(AVAIN))
        avain["abc123"] = wpis_abc
        (self.exp / "Sanomattomien_kirja.avain.json").write_text(json.dumps(avain), encoding="utf-8")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            tekst, wpisy, teorie = hr.kirja_bridge("Kansio")
        return tekst, teorie, err.getvalue()

    def test_rozjazd_liczby_luk(self):
        wpis = json.loads(json.dumps(AVAIN["abc123"]))
        wpis["open"]["4"] = "X"
        tekst, teorie, err = self._zly_klucz(wpis)
        self.assertNotIn("hiljaa", tekst)
        self.assertIn(t(hr.UI_LANG, "reacts.warn_kirja_mismatch", id="abc123", gaps=2, keys=3), err)

    def test_klucz_zlego_ksztaltu(self):
        for zly in (["lista"], {"open": ["lista"]}, {"open": {"a": "X", "1": "Y"}}):
            tekst, teorie, err = self._zly_klucz(zly)
            self.assertNotIn("hiljaa", tekst)
            self.assertIn(t(hr.UI_LANG, "reacts.warn_kirja_key_invalid", id="abc123"), err)

    def test_uszkodzone_zgadywania_sa_zglaszane(self):
        g = self.exp / "_kirja_tyotila" / "abc123" / "guesses.json"
        for tresc in ("{nie json", json.dumps({"guesses": ["lista"]})):
            g.write_text(tresc, encoding="utf-8")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                tekst, _, _ = hr.kirja_bridge("Kansio")
            self.assertNotIn("hiljaa", tekst)
            self.assertIn(t(hr.UI_LANG, "reacts.warn_json_invalid", path=g), err.getvalue())


def _odpowiedz(tresc, finish="stop"):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=tresc), finish_reason=finish)],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=20))


SETTINGS = SimpleNamespace(provider="openrouter", model="anthropic/claude-sonnet-5.5", endpoint="e")
STREAM = "**Valtteri:** " + "Moi! " * 30


class TestZapisIWywolanie(_Srodowisko):
    def _args(self, **kw):
        base = dict(kirja=False, min_chars=50)
        base.update(kw)
        return SimpleNamespace(**base)

    def test_zapis_unikalny_i_bez_crlf(self):
        with mock.patch.object(hr.llm_klient, "chat_text",
                               return_value=_odpowiedz(STREAM.replace(" ", "\r\n", 3))) as ct, \
                contextlib.redirect_stdout(io.StringIO()):
            for _ in range(2):
                self.assertTrue(hr.process(self.src(), "PROMPT", (SETTINGS, None), self._args(), "fi", "medium"))
        self.assertEqual(ct.call_args.args[2][0], {"role": "system", "content": "PROMPT"})
        self.assertEqual(ct.call_args.kwargs["effort"], "medium")
        pliki = sorted(p.name for p in (self.exp / "_streams").iterdir())
        self.assertEqual(pliki, ["Kansio.md", "Kansio_2.md"])
        self.assertNotIn(b"\r", (self.exp / "_streams" / "Kansio.md").read_bytes())

    def test_odrzucona_odpowiedz_trafia_do_pliku(self):
        err = io.StringIO()
        with mock.patch.object(hr.llm_klient, "chat_text", return_value=_odpowiedz("Nie mogę.", "length")), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            self.assertFalse(hr.process(self.src(), "PROMPT", (SETTINGS, None), self._args(), "fi", "low"))
        kept = self.exp / "_streams" / "Kansio.rejected.md"
        self.assertEqual(kept.read_text(encoding="utf-8"), "Nie mogę.\n")
        self.assertFalse((self.exp / "_streams" / "Kansio.md").exists())
        self.assertIn(t(hr.UI_LANG, "reacts.err_rejected", chars=9, min=50, finish="length",
                        path=hr._rel(kept)), err.getvalue())

    def test_ucieta_odpowiedz_ostrzega(self):
        err = io.StringIO()
        with mock.patch.object(hr.llm_klient, "chat_text", return_value=_odpowiedz(STREAM, "length")), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            self.assertTrue(hr.process(self.src(), "PROMPT", (SETTINGS, None), self._args(), "fi", "low"))
        self.assertIn(t(hr.UI_LANG, "reacts.warn_truncated"), err.getvalue())


class TestMain(_Srodowisko):
    def _main(self, argv, chat=None):
        out, err = io.StringIO(), io.StringIO()
        chat = chat or mock.Mock(return_value=_odpowiedz(STREAM))
        with mock.patch.object(hr.llm_klient, "resolve", return_value=SETTINGS), \
                mock.patch.object(hr.llm_klient, "build_client", return_value=None), \
                mock.patch.object(hr.llm_klient, "chat_text", chat), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = hr.main(argv)
        return rc, out.getvalue() + err.getvalue(), chat

    def test_brak_zrodla(self):
        rc, out, chat = self._main(["NieMaTakiego"])
        self.assertEqual(rc, 1)
        self.assertIn(t(hr.UI_LANG, "reacts.err_not_found", names="NieMaTakiego", html=hr.HTML_NAME), out)
        chat.assert_not_called()

    def test_nieznany_jezyk(self):
        rc, out, _ = self._main(["Kansio", "--lang", "xx"])
        self.assertEqual(rc, 1)
        self.assertIn('"xx"', out)

    def test_dry_run_nic_nie_wysyla(self):
        rc, out, chat = self._main(["Kansio", "--dry-run", "--lang", "en"])
        self.assertEqual(rc, 0)
        self.assertIn("Recording title: Kansio", out)
        chat.assert_not_called()

    def test_puste_i_zle_kodowane_zrodlo_nic_nie_kosztuje(self):
        pusty = self.base / "pusty.txt"
        pusty.write_text("  \n", encoding="utf-8")
        ansi = self.base / "ansi.txt"
        ansi.write_bytes("Zażółć".encode("cp1250"))
        for plik, klucz in ((pusty, "reacts.err_empty_source"), (ansi, "reacts.err_source_encoding")):
            rc, out, chat = self._main([str(plik), "Kansio"])
            self.assertEqual(rc, 1)
            self.assertIn(t(hr.UI_LANG, klucz, name=plik), out)
            chat.assert_not_called()

    def test_blad_jednego_zrodla_nie_zatrzymuje_reszty(self):
        chat = mock.Mock(side_effect=[RuntimeError("HTTP 500"), _odpowiedz(STREAM)])
        rc, out, _ = self._main(["Kansio", "Lahella", "--min-chars", "50"], chat)
        self.assertEqual(rc, 1)
        self.assertIn(t(hr.UI_LANG, "reacts.err_call", name="Kansio", error="HTTP 500"), out)
        self.assertIn(t(hr.UI_LANG, "reacts.done", ok=1, total=2), out)
        self.assertTrue((self.exp / "_streams" / "Lahella.md").exists())

    def test_effort_z_cli_i_automatyczny(self):
        _, _, chat = self._main(["Kansio"])
        self.assertEqual(chat.call_args.kwargs["effort"], "medium")
        _, _, chat = self._main(["Kansio", "--effort", "high"])
        self.assertEqual(chat.call_args.kwargs["effort"], "high")


if __name__ == "__main__":
    unittest.main(verbosity=1)
