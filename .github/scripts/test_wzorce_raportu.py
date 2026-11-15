"""Testy EN_HARDCODE_PATTERNS w generate_report.py: wydruki notatnika o warstwie
tekstu PDF, OCR i czyszczeniu źródeł muszą dostać <span lang="en">.

Bez wzorców z 2026-10-20 NVDA czytała „cid”, „OCR”, „U+F020” głosem
rosyjskim, a ówczesny detektor (Lingua) dawał „Symbol” lang="pl" i „fonttools” lang="fi".
Test nie używa słownikowego kroku 3 raportu — wzorce muszą wystarczyć same.

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
    "  PDF: генератор PDF заменил буквы вне WinAnsi символом ■ — слов восстановлено по словарю: 146.",
    "  PDF: подписи диаграмм, символов: 658. Они остаются для чтения в HTML/DOCX, но исключаются из NLP-анализа.",
]
FRAZY = ["ToUnicode", "fontTools", "pip install fonttools", "cid", "OCR", "U+F020", "Symbol",
         "mojibake", "latin-1&gt;cp1251", "cp1252&gt;iso8859-2", "latin-1&gt;koi8-r", "(cid:602)",
         "PDF", "TXT", "DOCX", "WinAnsi", "HTML", "NLP"]


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

    def test_modele_hf_notatnika_w_jednym_spanie(self):
        # Audyt 2026-11-13: po zmianie modelu NER na grammatek/... organizacji
        # brakowało w _HF_ORG_PREFIXES i NVDA czytała nazwę głosem rosyjskim.
        # Lista modeli idzie z tego samego źródła co audyt zależności.
        import audyt_zaleznosci
        modele = audyt_zaleznosci.modele_hf()
        self.assertTrue(modele)
        for m in modele:
            with self.subTest(model=m):
                # Sąsiednie spany się sklejają („NER: model”), więc wymóg to:
                # cała nazwa wewnątrz jednego spana lang="en".
                self.assertRegex(otaguj(f"  Загрузка NER: {m} ..."),
                                 '<span lang="en">[^<]*' + re.escape(m) + "[^<]*</span>")

    def test_jezyk_korpusu_z_wydruku_notatnika(self):
        # Regresja ATA 2.0 (znaleziona 2026-11-15 na prawdziwym przebiegu): cell_langdet
        # drukuje „Основной язык”, raport szukał „Выбран язык” i każdy korpus dostawał „ru”.
        # Wydruk bierzemy ze ŹRÓDŁA notatnika, więc zmiana komunikatu wywali ten test.
        zrodlo = (KORZEN / "accessible_text_analyst.py").read_text(encoding="utf-8")
        linia = next(l for l in zrodlo.splitlines()
                     if l.startswith("print(") and "[РЕЗУЛЬТАТ]" in l and "язык" in l)
        wyrazenie = linia[len("print("):].rstrip().removesuffix(")")
        wydruk = eval(wyrazenie, {"LANG": "fi", "LANG_NAMES": {"fi": "финский"}})  # noqa: S307
        nb = {"cells": [{"cell_type": "code", "outputs": [{"text": [wydruk]}]}]}
        self.assertEqual(gr.jezyk_korpusu(nb), "fi")
        stary = {"cells": [{"cell_type": "code", "outputs": [{"text": ["Выбран язык: польский (pl)"]}]}]}
        self.assertEqual(gr.jezyk_korpusu(stary), "pl")
        self.assertEqual(gr.jezyk_korpusu({"cells": []}), "ru")

    def test_obcy_odcinek_z_cell_tok_w_swoim_jezyku(self):
        # Audyt 2.0: wydruk „[Документ N] en (блок): …” nie pasował do żadnego
        # wzorca, angielski cytat szedł głosem rosyjskim. Wydruk ze ŹRÓDŁA notatnika.
        from types import SimpleNamespace
        zrodlo = (KORZEN / "accessible_text_analyst.py").read_text(encoding="utf-8")
        linia = next(l.strip() for l in zrodlo.splitlines()
                     if "[Документ {_dokument(_o.start)" in l and "print(" in l)
        wyrazenie = linia[len("print("):].removesuffix(")")
        for blok, kod in ((True, "en"), (False, "pl")):
            with self.subTest(blok=blok):
                wydruk = eval(wyrazenie, {"_dokument": lambda _p: 2,  # noqa: S307
                                          "_o": SimpleNamespace(start=0, jezyk=kod, blok=blok),
                                          "_f": "It was the best of times"})
                t = html.escape(wydruk)
                for wzorzec, zamiana in gr.WZORCE_WIELOJEZYCZNE:
                    t = re.sub(wzorzec, zamiana, t)
                self.assertIn(f'<span lang="{kod}">It was the best of times</span>', t)
                self.assertIn(f'<span lang="en">{kod}</span>', t)

    def test_rosyjskie_slowa_nietkniete(self):
        linia = "  PDF: текст вразрядку — склеено: 342, оставлено: 10."
        self.assertNotIn("вразрядку</span>", otaguj(linia))
        self.assertNotIn('lang="en">склеено', otaguj(linia))


if __name__ == "__main__":
    unittest.main()
