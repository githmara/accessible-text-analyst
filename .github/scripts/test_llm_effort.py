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

    def test_openai_dostaje_reasoning_effort(self):
        k = _Klient([('{"a": "x"}', None, 50)])
        r = lk.chat_json(k, _ustawienia("openai"), "p", SCHEMAT, "n", "en", effort="high")
        self.assertEqual(k.wyslane[0]["reasoning_effort"], "high")
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
        lk.chat_json(k, ust, "p", SCHEMAT, "n", "en", effort="high")
        self.assertNotIn("reasoning_effort", k.wyslane[1])
        self.assertEqual(k.wyslane[1]["response_format"]["type"], "json_schema")   # szczebel ten sam
        lk.chat_json(k, ust, "p", SCHEMAT, "n", "en", effort="high")
        self.assertEqual(len(k.wyslane), 3)
        self.assertNotIn("reasoning_effort", k.wyslane[2])                         # bez jałowego 400

    def test_inny_blad_struktury_dalej_schodzi_po_drabinie(self):
        k = _Klient([_Blad400("response_format json_schema is not supported"), ('{"a": "x"}', None, None)])
        lk.chat_json(k, _ustawienia("openai"), "p", SCHEMAT, "n", "en", effort="high")
        self.assertEqual(k.wyslane[1]["response_format"]["type"], "json_object")
        self.assertEqual(k.wyslane[1]["reasoning_effort"], "high")

    def test_rytualy_bez_effortu_jak_dotad(self):
        k = _Klient([("piesn", None, None)])
        lk.chat_text(k, _ustawienia("openrouter"), [{"role": "user", "content": "x"}], 0.8, "en")
        self.assertEqual(k.wyslane[0]["temperature"], 0.8)
        self.assertNotIn("extra_body", k.wyslane[0])

    def test_ksiega_ma_effort_per_rola(self):
        import ksiega_niedomowien as kn
        self.assertEqual((kn.DRAFTER_EFFORT, kn.FILLER_EFFORT), ("high", "low"))
        self.assertIsNone(kn._effort(SimpleNamespace(effort="default"), "high"))
        self.assertEqual(kn._effort(SimpleNamespace(effort=None), "low"), "low")


if __name__ == "__main__":
    unittest.main()
