"""Testy audyt_podstaw.py — sabotaże na kopii `dictionaries/` i kodu.

Każdy test psuje jedno miejsce i sprawdza, że audyt to łapie. Podmiana musi
trafić dokładnie raz — inaczej test pada głośno, zamiast po cichu sprawdzać
niezmieniony plik. Sonda spaCy dostaje sztuczny indeks i sztuczny „dysk”,
więc testy nie potrzebują sieci.

Uruchom:  .venv/Scripts/python .github/scripts/test_audyt_podstaw.py
(wymaga PyYAML i lingua-language-detector)
"""
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audyt_podstaw as a  # noqa: E402

sl = a.sl
INDEKS = {"en_core_web_lg": {"3.8"}, "pl_core_news_lg": {"3.8"}, "ru_core_news_lg": {"3.8"},
          "it_core_news_lg": {"3.8"}, "fi_core_news_lg": {"3.8"}}


def nic_na_dysku(_nazwa):
    return False


class TestAudytPodstaw(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.k = Path(self.tmp.name)
        shutil.copytree(a.KORZEN / "dictionaries", self.k / "dictionaries")
        for p in list(a.KORZEN.glob("README*.md")) + list(a.KORZEN.glob("*.py")):
            shutil.copy(p, self.k / p.name)

    def tearDown(self):
        self.tmp.cleanup()

    def popsuj(self, wzgledna, stary, nowy):
        sciezka = self.k / wzgledna
        s = sciezka.read_text(encoding="utf-8")
        self.assertEqual(s.count(stary), 1, f"sabotage target not unique in {wzgledna}: {stary!r}")
        sciezka.write_text(s.replace(stary, nowy), encoding="utf-8")

    def bledy(self, indeks=INDEKS, dysk=nic_na_dysku):
        podstawy, bledy = a.bledy_podstaw(self.k / "dictionaries")
        kody = set(podstawy) or {p.name for p in sl._katalogi_jezykow(self.k / "dictionaries")}
        nazwy = {p["lingua"].lower() for p in podstawy.values()}
        bledy += a.bledy_readme(self.k, kody) + a.bledy_wyliczen(self.k, kody, nazwy)
        if podstawy:
            bledy += a.bledy_spacy(podstawy, indeks, dysk)
        return bledy

    def zawiera(self, fragment, **kw):
        bledy = self.bledy(**kw)
        self.assertTrue(any(fragment in x for x in bledy), f"{fragment!r} not in {bledy}")

    # --- stan wyjściowy ---

    def test_kopia_bez_sabotazu_przechodzi(self):
        self.assertEqual(self.bledy(), [])

    # --- usunięty wpis JEDNEGO języka (fi) ---

    def test_usuniete_pole_fi(self):
        for pole, linia in (("locale", "locale: fi-FI\n"), ("spacy", "spacy: fi_core_news_lg\n"),
                            ("diakrytyki", 'diakrytyki: "äö"\n'), ("lingua", "lingua: FINNISH\n"),
                            ("nav_rdzenie", "nav_rdzenie: [liittyv]\n")):
            with self.subTest(pole=pole):
                self.tearDown()
                self.setUp()
                self.popsuj("dictionaries/fi/podstawy.yaml", linia, "")
                self.zawiera(f'field "{pole}" missing')

    def test_brak_pliku_podstaw_fi(self):
        (self.k / "dictionaries/fi/podstawy.yaml").unlink()
        self.zawiera("podstawy.yaml: missing")

    def test_brak_readme_fi(self):
        (self.k / "README_fi.md").unlink()
        self.zawiera("README_fi.md missing")

    def test_siodmy_jezyk_bez_podstaw(self):
        (self.k / "dictionaries/sv").mkdir()
        bledy = self.bledy()
        self.assertTrue(any("sv" in b and "podstawy.yaml: missing" in b for b in bledy), bledy)

    # --- treść ---

    def test_jezyk_niezgodny_z_folderem(self):
        self.popsuj("dictionaries/fi/podstawy.yaml", "jezyk: fi\n", "jezyk: is\n")
        self.zawiera("jezyk 'is' != folder 'fi'")

    def test_lingua_innego_jezyka(self):
        self.popsuj("dictionaries/fi/podstawy.yaml", "lingua: FINNISH", "lingua: ESTONIAN")
        self.zawiera("is ISO 'et', not 'fi'")

    def test_lingua_nieistniejace(self):
        self.popsuj("dictionaries/fi/podstawy.yaml", "lingua: FINNISH", "lingua: SUOMI")
        self.zawiera("'SUOMI' is not a lingua.Language member")

    def test_zle_locale(self):
        self.popsuj("dictionaries/fi/podstawy.yaml", "locale: fi-FI", "locale: sv-FI")
        self.zawiera("does not start with 'fi-'")

    def test_diakrytyk_spoza_alfabetu(self):
        self.popsuj("dictionaries/fi/podstawy.yaml", 'diakrytyki: "äö"', 'diakrytyki: "äöü"')
        self.zawiera("diakrytyki must be lowercase letters of alfabet")

    def test_skrotowiec_bez_kropki(self):
        self.popsuj("dictionaries/fi/podstawy.yaml", "esim., ", "esim, ")
        self.zawiera("skrotowiec 'esim' must be letters with at least one dot")

    def test_naglowek_malymi(self):
        self.popsuj("dictionaries/fi/podstawy.yaml", "[NÄYTÖS,", "[näytös,")
        self.zawiera("naglowki_struktury entry 'näytös'")

    # --- sonda spaCy ---

    def test_islandzki_model_pojawil_sie_w_indeksie(self):
        indeks = dict(INDEKS, is_core_news_md={"3.9"})
        self.zawiera("spaCy now publishes 'is_core_news_md' (spaCy 3.9) — set `spacy: is_core_news_md`",
                     indeks=indeks)

    def test_islandzki_model_juz_na_dysku(self):
        self.zawiera("'is_core_news_lg' is installed on this machine but `spacy:` is still null",
                     dysk=lambda n: n == "is_core_news_lg")

    def test_zadeklarowany_model_spoza_indeksu(self):
        self.popsuj("dictionaries/fi/podstawy.yaml", "fi_core_news_lg", "fi_core_news_xl")
        self.zawiera("'fi_core_news_xl' is not in the spaCy model index")

    def test_brak_sieci_to_nie_zielone(self):
        with self.assertRaises(a.BladSondy):
            a.pobierz_indeks("http://127.0.0.1:9/compatibility.json")

    # --- nawrót wyliczeń w kodzie ---

    def test_nawrot_mapy_w_kodzie(self):
        self.popsuj("generate_report.py", "_SUPPORTED_LANGS = set(PODSTAWY)",
                    '_SUPPORTED_LANGS = {"en", "pl", "ru"}')
        self.zawiera("generate_report.py:")
        self.zawiera("collection of language codes ['en', 'pl', 'ru']")

    def test_nawrot_language_w_kodzie(self):
        self.popsuj("shamanic_locale.py", "from_languages(*lingua_jezyki())",
                    "from_languages(Language.FINNISH)")
        self.zawiera("shamanic_locale.py:")
        self.zawiera("Language.FINNISH")

    def test_wyjatek_punktowy_z_powodem(self):
        self.popsuj("generate_report.py", "_SUPPORTED_LANGS = set(PODSTAWY)",
                    '_SUPPORTED_LANGS = {"en", "pl", "ru"}  # audyt-podstaw: ok — test')
        self.assertEqual(self.bledy(), [])

    # --- pochodne w shamanic_locale ---

    def test_skrotowce_nie_ruszaja_prozy(self):
        proza = {
            "pl": "Poszedł po chleb. W r. 2020 było źle, art. 5 mówi, że v i po.",
            "fi": "Hän meni kotiin. Ko talo oli vt. johtajan, po. suuntaan os. 5.",
            "it": "L'arte è bella. Il cap. 3 e l'art. 7, n. 4; sig.ra Rossi.",
            "en": "He said no. See p. 4 and pp. 5-6; Dr. Who met Mr. X.",
            "ru": "Он ушёл, т.е. пропал. Ул. Ленина, проф. Иванов.",
            "is": "Hann fór heim. Sjá bls. 4, t.d. hér.",
        }
        for kod, tekst in proza.items():
            for wzor, forma in sl.wzorce_skrotowcow(kod):
                with self.subTest(kod=kod, forma=forma):
                    self.assertEqual(re.sub(wzor, forma, tekst), tekst)

    def test_skrotowce_scalaja_rozstrzelone(self):
        for kod, tekst, oczekiwany in (("pl", "m. in. psy", "m.in. psy"),
                                       ("ru", "и т. д. и т.  п.", "и т.д. и т.п."),
                                       ("is", "u. þ. b. tíu", "u.þ.b. tíu"),
                                       ("en", "e. g. this", "e.g. this")):
            for wzor, forma in sl.wzorce_skrotowcow(kod):
                tekst = re.sub(wzor, forma, tekst)
            self.assertEqual(tekst, oczekiwany)

    def test_skrotowce_idempotentne(self):
        # Stary wzorzec `\bm\.\s*in\.?,?\b` dopisywał kropkę przy każdym
        # przebiegu: „m.in.:” → „m.in..:” → „m.in...:” (zmierzone 2026-10-16).
        for kod, p in sl.PODSTAWY.items():
            for tekst in [f"x {s}: y" for s in p["skrotowce"]] + ["zawiera m.in..: y"]:
                raz = tekst
                for wzor, forma in sl.wzorce_skrotowcow(kod):
                    raz = re.sub(wzor, forma, raz)
                dwa = raz
                for wzor, forma in sl.wzorce_skrotowcow(kod):
                    dwa = re.sub(wzor, forma, dwa)
                with self.subTest(kod=kod, tekst=tekst):
                    self.assertEqual(raz, dwa)
                    self.assertEqual(raz, tekst)

    def test_niejednoznaczny_skrotowiec_wypada(self):
        warianty = sl.warianty_skrotowcow()
        self.assertFalse(any("prof." in w for w in warianty.values()))
        self.assertIn("m.in.", warianty["pl"])
        self.assertIn("т. е.", warianty["ru"])

    # --- ustalenia audytu commita 2a6d54d ---

    def test_kod_rozpoznaje_dawne_skroty_a_nie_python(self):
        w = sl.warianty_skrotowcow()
        for kod, zapisy in (("pl", ["np", "np.", "tzw", "itd", "itp", "tj", "tzn", "ww", "m.in"]),
                            ("en", ["etc", "vs", "cf", "e.g"]), ("ru", ["напр."])):
            for z in zapisy:
                with self.subTest(kod=kod, zapis=z):
                    self.assertIn(z, w[kod])
        for z in ("os.", "str.", "n.", "v.", "r.", "p."):   # wygląda jak kod Pythona
            with self.subTest(zapis=z):
                self.assertFalse(any(z in zb for zb in w.values()))

    def test_skrotowiec_kodu_spoza_skrotowcow(self):
        self.popsuj("dictionaries/en/podstawy.yaml", "skrotowce_kodu: [etc.,", "skrotowce_kodu: [ibid.,")
        self.zawiera("skrotowce_kodu entry 'ibid.' is not in skrotowce")

    def test_wzorzec_tokenow_nie_gubi_slow(self):
        tokeny = re.findall(sl.WZORZEC_TOKENOW, "tšekki šakki itä-suome müller gödel são "
                            "dell'anno łódź jón-páll x2 _ab 1999 -kissa koira- ab")
        for slowo in ("tšekki", "šakki", "itä-suome", "müller", "gödel", "são",
                      "dell'anno", "łódź", "jón-páll", "kissa", "koira", "ab"):
            with self.subTest(slowo=slowo):
                self.assertIn(slowo, tokeny)
        for smiec in ("x2", "_ab", "1999", "-kissa", "koira-"):
            with self.subTest(smiec=smiec):
                self.assertNotIn(smiec, tokeny)

    def test_skrotowiec_nie_skleja_przez_pusta_linie(self):
        wzory = dict((f, w) for w, f in sl.wzorce_skrotowcow("it"))
        self.assertEqual(re.sub(wzory["ad es."], "ad es.", "ad\n\nes. x"), "ad\n\nes. x")
        wzory = dict((f, w) for w, f in sl.wzorce_skrotowcow("pl"))
        self.assertEqual(re.sub(wzory["m.in."], "m.in.", "m.\n\nin. x"), "m.\n\nin. x")
        self.assertEqual(re.sub(wzory["m.in."], "m.in.", "m.\nin. x"), "m.in. x")

    def test_nawrot_alternatywy_kodow_w_regexie(self):
        self.popsuj("generate_report.py", '(r"(\\()(" + _KODY + r")(\\))",',
                    '(r"(\\()(en|pl|ru|it|fi|is)(\\))",')
        self.zawiera("regex alternation of languages ['en', 'fi', 'is', 'it', 'pl', 'ru']")

    def test_nawrot_alternatywy_nazw_w_regexie(self):
        self.popsuj("generate_report.py", 'nazwy_regex() + r"|"', 'r"English|Polish|Russian|"')
        self.zawiera("regex alternation of languages ['English', 'Polish', 'Russian']")

    def test_nawrot_lingua_language_przez_modul(self):
        self.popsuj("shamanic_locale.py", "from_languages(*lingua_jezyki())",
                    "from_languages(lingua.Language.POLISH)")
        self.zawiera("Language.POLISH")

    def test_nawrot_split_kodow(self):
        self.popsuj("generate_report.py", "_SUPPORTED_LANGS = set(PODSTAWY)",
                    '_SUPPORTED_LANGS = set("en pl ru".split())')
        self.zawiera("'...'.split() of language codes ['en', 'pl', 'ru']")

    def test_katalog_pomocniczy_nie_jest_jezykiem(self):
        (self.k / "dictionaries/_szkice").mkdir()
        (self.k / "dictionaries/.cache").mkdir()
        self.assertEqual(self.bledy(), [])

    def test_wartosc_bool_podpowiada_cudzyslow(self):
        self.popsuj("dictionaries/fi/podstawy.yaml", "nazwa_ru: финский", "nazwa_ru: no")
        self.zawiera("quote the value")

    def test_lista_zamiast_mapy(self):
        (self.k / "dictionaries/fi/podstawy.yaml").write_text("- jezyk: fi\n", encoding="utf-8")
        self.zawiera("must be a mapping of fields, not list")

    def test_sonda_rozroznia_siec_od_trwalego_bledu(self):
        import io
        import urllib.error
        import urllib.request
        oryginal = urllib.request.urlopen

        def podmien(wyjatek=None, tresc=b""):
            class Odp:
                def __enter__(self): return self
                def __exit__(self, *_): return False
                def read(self): return tresc

            def urlopen(*_a, **_k):
                if wyjatek:
                    raise wyjatek
                return Odp()
            urllib.request.urlopen = urlopen

        # Atrapy HTTPError trzymają strumień odpowiedzi — zamykane w `finally`,
        # inaczej Python sprząta je sam z ResourceWarning (widoczne w logu CI 2026-10-21).
        e404 = urllib.error.HTTPError("u", 404, "nf", {}, io.BytesIO())
        e503 = urllib.error.HTTPError("u", 503, "x", {}, io.BytesIO())
        try:
            for opis, kw, trwaly in (
                    ("404", {"wyjatek": e404}, True),
                    ("503", {"wyjatek": e503}, False),
                    ("dns", {"wyjatek": urllib.error.URLError("dns")}, False),
                    ("json", {"tresc": b"<html>"}, True),
                    ("ksztalt", {"tresc": b'{"models": {}}'}, True)):
                with self.subTest(opis=opis):
                    podmien(**kw)
                    with self.assertRaises(a.BladSondy) as k:
                        a.pobierz_indeks("https://example.invalid/i.json")
                    self.assertEqual(k.exception.trwaly, trwaly)
                    self.assertIn("https://example.invalid/i.json", str(k.exception))
        finally:
            urllib.request.urlopen = oryginal
            e404.close()
            e503.close()

    def test_siec_nie_zaslania_innych_bledow(self):
        import contextlib
        import io
        (self.k / "README_fi.md").unlink()
        stary_korzen, stara_sonda = a.KORZEN, a.pobierz_indeks

        def bez_sieci(*_):
            raise a.BladSondy("cannot verify spaCy models: x", trwaly=False)
        a.KORZEN, a.pobierz_indeks = self.k, bez_sieci
        try:
            wyjscie = io.StringIO()
            with contextlib.redirect_stdout(wyjscie):
                kod = a.main()
        finally:
            a.KORZEN, a.pobierz_indeks = stary_korzen, stara_sonda
        self.assertEqual(kod, 3)
        self.assertIn("README_fi.md missing", wyjscie.getvalue())
        self.assertIn("network problem", wyjscie.getvalue())


if __name__ == "__main__":
    unittest.main()
