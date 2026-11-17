"""Testy effortu myślenia w llm_klient (v2.0.1) — atrapa klienta, zero sieci.

Modele rozumujące myślą zawsze; brak pola = effort domyślny providera (płatny).
Pilnujemy kształtu pola per provider, ponowienia bez pola po odrzuceniu i tego,
że rytuały (effort=None) nie dostają niczego nowego.

Uruchom:  python .github/scripts/test_llm_effort.py
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import llm_klient as lk  # noqa: E402


class _Blad400(Exception):
    status_code = 400

    def __init__(self, tekst, param=None):
        super().__init__(tekst)
        self.param = param


class _Klient:
    def __init__(self, odpowiedzi):
        self.odpowiedzi = list(odpowiedzi)
        self.wyslane = []
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kw):
        self.wyslane.append(kw)
        nast = self.odpowiedzi.pop(0)
        if isinstance(nast, Exception):
            raise nast
        tekst, rozumowanie, tokeny = nast
        msg = SimpleNamespace(content=tekst, refusal=None, reasoning=rozumowanie)
        usage = SimpleNamespace(completion_tokens_details=SimpleNamespace(reasoning_tokens=tokeny))
        return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="stop")], usage=usage)


def _ustawienia(provider, model="m"):
    return lk.LLMSettings(provider=provider, key_var="K", base_url=f"https://{provider}.test/v1", model=model)


SCHEMAT = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}


class TestEffort(unittest.TestCase):
    def setUp(self):
        lk._NO_EFFORT.clear()
        lk._WORKING_MODE.clear()
        lk._NO_TEMPERATURE.clear()
        lk._THINKING_WARNED.clear()

    def test_openai_dostaje_reasoning_effort(self):
        k = _Klient([('{"a": "x"}', None, 50)])
        r = lk.chat_json(k, _ustawienia("openai"), "p", SCHEMAT, "n", "en", effort="low")
        self.assertEqual(k.wyslane[0]["reasoning_effort"], "low")
        self.assertNotIn("extra_body", k.wyslane[0])
        self.assertEqual(r.reasoning_tokens, 50)

    def test_openrouter_dostaje_reasoning_w_extra_body_i_oddaje_streszczenie(self):
        k = _Klient([('{"a": "x"}', "  Mietin sanaa.  ", 120)])
        r = lk.chat_json(k, _ustawienia("openrouter"), "p", SCHEMAT, "n", "en", effort="low")
        self.assertEqual(k.wyslane[0]["extra_body"], {"reasoning": {"effort": "low"}})
        self.assertEqual(r.reasoning, "Mietin sanaa.")

    def test_compat_i_brak_effortu_nie_wysylaja_pola(self):
        for provider, effort in (("openai_compat", "high"), ("openai", None), ("openrouter", None)):
            k = _Klient([('{"a": "x"}', None, None)])
            lk.chat_json(k, _ustawienia(provider), "p", SCHEMAT, "n", "en", effort=effort)
            self.assertNotIn("reasoning_effort", k.wyslane[0], provider)
            self.assertNotIn("extra_body", k.wyslane[0], provider)

    def test_odrzucony_effort_jedno_ponowienie_bez_pola_i_pamiec(self):
        ust = _ustawienia("openai", "stary-model")
        k = _Klient([_Blad400("Unsupported parameter: 'reasoning_effort'", "reasoning_effort"),
                     ('{"a": "x"}', None, None), ('{"a": "y"}', None, None)])
        lk.chat_json(k, ust, "p", SCHEMAT, "n", "en", effort="low")
        self.assertNotIn("reasoning_effort", k.wyslane[1])
        self.assertEqual(k.wyslane[1]["response_format"]["type"], "json_schema")   # szczebel ten sam
        lk.chat_json(k, ust, "p", SCHEMAT, "n", "en", effort="low")
        self.assertEqual(len(k.wyslane), 3)
        self.assertNotIn("reasoning_effort", k.wyslane[2])                         # bez jałowego 400

    def test_inny_blad_struktury_dalej_schodzi_po_drabinie(self):
        k = _Klient([_Blad400("response_format json_schema is not supported"), ('{"a": "x"}', None, None)])
        lk.chat_json(k, _ustawienia("openai"), "p", SCHEMAT, "n", "en", effort="low")
        self.assertEqual(k.wyslane[1]["response_format"]["type"], "json_object")
        self.assertEqual(k.wyslane[1]["reasoning_effort"], "low")

    def test_rytualy_bez_effortu_jak_dotad(self):
        k = _Klient([("piesn", None, None)])
        lk.chat_text(k, _ustawienia("openrouter"), [{"role": "user", "content": "x"}], 0.8, "en")
        self.assertEqual(k.wyslane[0]["temperature"], 0.8)
        self.assertNotIn("extra_body", k.wyslane[0])

    def test_blad_innego_pola_ze_slowem_reasoning_nie_jest_odrzuceniem_effortu(self):
        # Audyt 2.0.1, Z1: param wskazuje inne pole — treść nie może przeważyć.
        e = _Blad400("response_format is not supported together with reasoning models", "response_format")
        self.assertFalse(lk.is_effort_error(e))
        k = _Klient([e, ('{"a": "x"}', None, None)])
        lk.chat_json(k, _ustawienia("openai"), "p", SCHEMAT, "n", "en", effort="low")
        self.assertEqual(k.wyslane[1]["reasoning_effort"], "low")        # effort nie zatruty
        self.assertFalse(lk._NO_EFFORT)

    def test_blad_formatu_bez_param_nie_jest_odrzuceniem_effortu(self):
        # 2.0.2: OpenRouter nie podaje param — treść nazywająca format nie zdejmuje effortu.
        for tekst in ("response_format json_schema is not supported with reasoning",
                      "Invalid json_schema for reasoning model"):
            self.assertFalse(lk.is_effort_error(_Blad400(tekst)), tekst)
        self.assertTrue(lk.is_effort_error(_Blad400("Reasoning is mandatory for this endpoint")))
        self.assertTrue(lk.is_effort_error(_Blad400("bad value", "reasoning.effort")))
        k = _Klient([_Blad400("response_format is not supported with reasoning"),
                     ('{"a": "x"}', None, None)])
        lk.chat_json(k, _ustawienia("openrouter"), "p", SCHEMAT, "n", "en", effort="low")
        self.assertFalse(lk._NO_EFFORT)

    def test_pamiec_odrzucenia_jest_per_wartosc_effortu(self):
        # Audyt 2.0.1, Z3: odrzucone xhigh nie wyłącza high.
        # Podbity effort idzie tylko przy czytelnym myśleniu — stąd Claude przez OpenRoutera.
        ust = _ustawienia("openrouter", "anthropic/m2")
        k = _Klient([_Blad400("bad value", "reasoning"), ('{"a": "x"}', None, None),
                     ('{"a": "y"}', None, None)])
        lk.chat_json(k, ust, "p", SCHEMAT, "n", "en", effort="xhigh")
        lk.chat_json(k, ust, "p", SCHEMAT, "n", "en", effort="high")
        self.assertEqual(k.wyslane[2]["extra_body"], {"reasoning": {"effort": "high"}})

    def _z_wyjsciem(self, ust, effort, ile=1):
        import contextlib
        import io
        bufor = io.StringIO()
        k = _Klient([('{"a": "x"}', None, None)] * ile)
        with contextlib.redirect_stdout(bufor):
            for _ in range(ile):
                lk.chat_json(k, ust, "p", SCHEMAT, "n", "en", effort=effort)
        return k.wyslane, bufor.getvalue()

    def test_nieczytelne_myslenie_nie_jest_podbijane(self):
        # Pomiar 2026-11-17: GPT przez OpenRoutera = reasoning.encrypted; OpenAI CC = sam licznik.
        for ust in (_ustawienia("openai", "gpt-6.1-sol"), _ustawienia("openrouter", "openai/gpt-6.1-sol")):
            wyslane, wyjscie = self._z_wyjsciem(ust, "high", ile=2)
            pole = wyslane[0].get("reasoning_effort") or wyslane[0]["extra_body"]["reasoning"]["effort"]
            self.assertEqual(pole, "low", ust.provider)
            self.assertEqual(wyjscie.count("does not return readable thinking"), 1, ust.provider)

    def test_czytelne_myslenie_claude_dostaje_high_bez_ostrzezenia(self):
        wyslane, wyjscie = self._z_wyjsciem(_ustawienia("openrouter", "anthropic/claude-sonnet-5.5"), "high")
        self.assertEqual(wyslane[0]["extra_body"], {"reasoning": {"effort": "high"}})
        self.assertNotIn("[WARNING]", wyjscie)

    def test_low_na_gpt_ostrzega_ze_mysli_zawsze(self):
        _, wyjscie = self._z_wyjsciem(_ustawienia("openrouter", "openai/gpt-6.1-sol"), "low")
        self.assertIn("always reasons", wyjscie)
        _, wyjscie = self._z_wyjsciem(_ustawienia("openrouter", "anthropic/claude-sonnet-5.5"), "low")
        self.assertNotIn("[WARNING]", wyjscie)

    def test_compat_ostrzega_o_domyslnym_effortcie(self):
        wyslane, wyjscie = self._z_wyjsciem(_ustawienia("openai_compat", "gpt-6.1-sol"), "high")
        self.assertNotIn("extra_body", wyslane[0])
        self.assertIn("default effort", wyjscie)

    def test_rytualy_bez_effortu_nie_ostrzegaja(self):
        _, wyjscie = self._z_wyjsciem(_ustawienia("openai", "gpt-6.1-sol"), None)
        self.assertNotIn("[WARNING]", wyjscie)

    def test_naglowek_mysli_podaje_effort_ktory_naprawde_poszedl(self):
        import tempfile
        import ksiega_niedomowien as kn
        odp = lk.LLMReply(text="{}", mode="json_schema", finish_reason="stop", refusal="",
                          reasoning_tokens=7, reasoning="Ajattelen.")
        with tempfile.TemporaryDirectory() as tmp:
            cel = Path(tmp) / "draft_thinking_1.txt"
            kn._save_thinking(cel, odp, _ustawienia("openrouter", "openai/gpt-6-luna"))
            self.assertIn("effort: default", cel.read_text(encoding="utf-8"))   # effort_sent puste

    def test_effort_sent_po_obnizeniu_i_po_odrzuceniu(self):
        # Audyt 2.0.1, Z1: nagłówek pliku myślenia nie może podawać effortu, który nie poszedł.
        k = _Klient([('{"a": "x"}', "Ajattelen.", 5)])
        r = lk.chat_json(k, _ustawienia("openrouter", "openai/gpt-6-luna"), "p", SCHEMAT, "n", "en", effort="high")
        self.assertEqual(r.effort_sent, "low")
        k = _Klient([_Blad400("bad", "reasoning"), ('{"a": "x"}', "Ajattelen.", 5)])
        r = lk.chat_json(k, _ustawienia("openrouter", "anthropic/claude-x"), "p", SCHEMAT, "n", "en", effort="high")
        self.assertIsNone(r.effort_sent)
        import tempfile
        import ksiega_niedomowien as kn
        with tempfile.TemporaryDirectory() as tmp:
            cel = Path(tmp) / "draft_thinking_1.txt"
            kn._save_thinking(cel, r, _ustawienia("openrouter", "anthropic/claude-x"))
            self.assertIn("effort: default", cel.read_text(encoding="utf-8"))

    def test_odrzucony_effort_nie_daje_ostrzezenia_mysli_zawsze(self):
        # Audyt 2.0.1, Z3: model, który odrzuca pole, nie rozumuje.
        import contextlib
        import io
        bufor = io.StringIO()
        k = _Klient([_Blad400("Unsupported parameter", "reasoning_effort"), ('{"a": "x"}', None, None)])
        with contextlib.redirect_stdout(bufor):
            lk.chat_json(k, _ustawienia("openai", "gpt-4.1"), "p", SCHEMAT, "n", "en", effort="low")
        self.assertNotIn("always reasons", bufor.getvalue())
        self.assertIn("rejected the thinking setting", bufor.getvalue())

    def test_draft_czysci_stare_mysli_i_podpisuje_nowe(self):
        # Audyt 2.0.1, Z2: myśli innego szkicu nie mogą leżeć obok nowego draft.json.
        import tempfile
        import ksiega_niedomowien as kn
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            for nazwa in ("draft_thinking_1.txt", "draft_thinking_3.txt", "draft_reply_2.txt", "packet.json"):
                (d / nazwa).write_text("stare", encoding="utf-8")
            kn._clear_draft_leftovers(d)
            self.assertEqual(sorted(p.name for p in d.iterdir()), ["packet.json"])
            odp = lk.LLMReply(text="{}", mode="json_schema", finish_reason="stop", refusal="", reasoning_tokens=7, reasoning="Mietin.")
            kn._save_thinking(d / "draft_thinking_1.txt", odp, _ustawienia("openrouter", "m3"))
            tekst = (d / "draft_thinking_1.txt").read_text(encoding="utf-8")
            self.assertTrue(tekst.startswith("provider: openrouter\nmodel: m3\neffort: default\n"))
            self.assertIn("Mietin.", tekst)

    def test_ksiega_ma_effort_per_rola(self):
        import ksiega_niedomowien as kn
        self.assertEqual((kn.DRAFTER_EFFORT, kn.FILLER_EFFORT), ("high", "low"))
        self.assertIsNone(kn._effort(SimpleNamespace(effort="default"), "high"))
        self.assertEqual(kn._effort(SimpleNamespace(effort=None), "low"), "low")


if __name__ == "__main__":
    unittest.main()
