"""Testy EN_HARDCODE_PATTERNS w generate_report.py: wydruki notatnika o warstwie
tekstu PDF, OCR i czyszczeniu źródeł muszą dostać <span lang="en">.

Bez wzorców z 2026-10-20 NVDA czytała „cid”, „OCR”, „U+F020” głosem
rosyjskim, a lingua dawała „Symbol” lang="pl" i „fonttools” lang="fi".
Test nie używa zgadywania lingua (krok 3 raportu) — wzorce muszą wystarczyć same.

Uruchom:  python .github/scripts/test_wzorce_raportu.py   (stdlib + PyYAML)
"""
import html
import re
import sys
import unittest
from pathlib import Path

KORZEN = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KORZEN))
import generate_report as gr  # noqa: E402

LINIE = [
    "  PDF: карта символов шрифта (ToUnicode) неполная на страницах 2–551 — текст восстановлен по встроенным шрифтам.",
    "  [ВНИМАНИЕ] PDF: текстовый слой нечитаем (неполная карта символов шрифта) на страницах 3, 7–9. "
    "Восстановление по шрифтам требует fontTools: pip install fonttools.",
    "  PDF: удалено одиночных нераспознанных символов шрифта (cid): 4.",
    "  PDF: страницы с нечитаемым текстовым слоем передаются в OCR (языки: ['ru', 'en']): 3, 7–9.",
    "  PDF: символов-пробелов шрифта Symbol (U+F020) заменено обычным пробелом: 2.",
    "  PDF: исправлена неверная кодировка (mojibake) в строках: 496 (latin-1>cp1251: 496).",
    "  TXT: исправлена неверная кодировка (mojibake) в строках: 12 (cp1252>iso8859-2: 10, latin-1>koi8-r: 2).",
    "  DOCX: символов-пробелов шрифта Symbol (U+F020) заменено обычным пробелом: 253.",
    "  Сырой слой: (cid:602)(cid:619)",
]
FRAZY = ["ToUnicode", "fontTools", "pip install fonttools", "cid", "OCR", "U+F020", "Symbol",
         "mojibake", "latin-1&gt;cp1251", "cp1252&gt;iso8859-2", "latin-1&gt;koi8-r", "(cid:602)",
         "PDF", "TXT", "DOCX"]


def otaguj(linia: str) -> str:
    tekst = html.escape(linia, quote=True)
    return gr._coalesce_same_lang_spans(gr._apply_outside_spans(tekst, gr.EN_HARDCODE_PATTERNS))


class TestWzorceRaportu(unittest.TestCase):
    def test_kazda_fraza_w_lang_en(self):
        wynik = "\n".join(otaguj(l) for l in LINIE)
        poza = re.sub(r'<span lang="en">.*?</span>', "", wynik, flags=re.S)
        for f in FRAZY:
            with self.subTest(fraza=f):
                self.assertIn(f, wynik)
                self.assertNotIn(f, poza)

    def test_para_kodowan_to_jeden_span(self):
        self.assertIn('<span lang="en">latin-1&gt;cp1251</span>', otaguj(LINIE[5]))

    def test_kodowania_z_modulu(self):
        # Każde kodowanie wspólnego modułu dostaje span — lista nie jest przepisana ręcznie.
        for k in gr.ZRODLA_MOJIBAKE + gr.CELE_MOJIBAKE:
            with self.subTest(kodowanie=k):
                self.assertIn(f'<span lang="en">{k}</span>', otaguj(f"кодировка {k} найдена"))

    def test_rosyjskie_slowa_nietkniete(self):
        linia = "  PDF: текст вразрядку — склеено: 342, оставлено: 10."
        self.assertNotIn("вразрядку</span>", otaguj(linia))
        self.assertNotIn('lang="en">склеено', otaguj(linia))


if __name__ == "__main__":
    unittest.main()
