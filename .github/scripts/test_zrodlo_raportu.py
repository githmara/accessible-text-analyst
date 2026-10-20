"""Testy bramki źródła raportu (zrodlo_raportu.py) i tonu przecieku w Księdze.

Każda odmowa musi zapaść na dowód, a niesprawdzalna treść nie może blokować.
Źródła testowe to pliki .txt (biblioteka standardowa), więc test działa
w CI z samym PyYAML. Uruchom:  python .github/scripts/test_zrodlo_raportu.py
"""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

KORZEN = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KORZEN))
import zrodlo_raportu as z  # noqa: E402

TEKST = ("Syys-\nkuussa 2000–2025 Yhdysvaltain puolustusministeriö teki todella yllättävän päätöksen. "
         "12\n" + "Puretaan vähän tätä logiikkaa ja katsotaan, mitä tekstiviestidiplomatia oikeasti tarkoittaa. " * 40)
INNY = "Совсем другой текст о манипуляциях в средствах массовой информации. " * 60


EKSPORT = "--- Экспорт результатов ---" + chr(10) + "Файлы сохранены в папку: C:/x" + chr(10)


def nb_z(stdout, model="", eksport=EKSPORT):
    cells = [{"cell_type": "code", "metadata": {"tags": ["cell_corpus"]},
              "outputs": [{"output_type": "stream", "name": "stdout", "text": stdout}]},
             {"cell_type": "code", "metadata": {"tags": ["cell_export"]},
              "outputs": [{"output_type": "stream", "name": "stdout", "text": eksport}] if eksport else []}]
    if model:
        cells.append({"cell_type": "code", "metadata": {"tags": ["cell_model"]},
                      "outputs": [{"output_type": "stream", "name": "stdout", "text": model}]})
    return {"cells": cells}


def wydruk(zrodlo, katalog, podglady, wbudowany=False, brak=False):
    s = "[OK] Конфигурация загружена: config.json\n"
    if brak:
        s += f"[ВНИМАНИЕ] Источник не найден: {zrodlo!r}. Используется встроенный пример.\n"
    elif zrodlo:
        s += f"Загрузка из файла: {zrodlo}\n  TXT: разбито на 3 псевдостраниц (~2000 символов каждая).\n"
    if wbudowany or brak:
        s += "Используется встроенный корпус-пример (3 документа).\n"
    s += f"\nКорпус готов: {len(podglady)} документ(ов).\n"
    for i, p in enumerate(podglady):
        s += f"  [{i + 1}] {p[:80]}...\n"
    return s + f"\nКаталог проекта: {katalog}\n"


class TestBramka(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.k = Path(self.tmp.name)
        self.src = self.k / "Puolan_tekstiviesti.txt"
        self.src.write_text(TEKST, encoding="utf-8")
        self.inny = self.k / "inny.txt"
        self.inny.write_text(INNY, encoding="utf-8")
        self.folder = self.k / "export_results" / "Puolan_tekstiviesti"
        self.folder.mkdir(parents=True)
        self.nbp = self.k / "nb.ipynb"
        self.nbp.write_text("{}", encoding="utf-8")
        stary = time.time() - 120
        for n in ("paragraphs.csv", "sentences.csv"):
            (self.folder / n).write_text("x", encoding="utf-8")
            os.utime(self.folder / n, (stary, stary))
        # podgląd tak, jak drukuje go notatnik: po sklejeniu przeniesienia i zwinięciu spacji
        self.podglady = ["Syyskuussa 2000–2025 Yhdysvaltain puolustusministeriö teki todella yllättävän päätöksen.",
                         "Puretaan vähän tätä logiikkaa ja katsotaan, mitä tekstiviestidiplomatia oikeasti"]

    def tearDown(self):
        self.tmp.cleanup()

    def werdykt(self, stdout, source):
        return z.sprawdz(nb_z(stdout), str(source), self.folder, self.nbp)

    def test_zgodne_zrodlo(self):
        w = self.werdykt(wydruk(self.src, self.folder, self.podglady), self.src)
        self.assertTrue(w.ok, w)
        self.assertEqual(w.klucz, "gate_ok_content")
        self.assertEqual(w.argumenty, {"found": 2, "checked": 2})

    def test_usterka_inne_zrodlo(self):
        w = self.werdykt(wydruk(self.src, self.folder, self.podglady), self.inny)
        self.assertFalse(w.ok)
        self.assertEqual(w.klucz, "gate_source_mismatch")

    def test_ukosniki_i_wielkosc_liter_to_ta_sama_sciezka(self):
        inna_pisownia = str(self.src).replace(os.sep, "/")
        w = self.werdykt(wydruk(self.src, self.folder, self.podglady), inna_pisownia)
        self.assertTrue(w.ok, w)

    def test_wbudowany_a_config_wskazuje_plik(self):
        k = self.folder.parent / "_default"
        w = self.werdykt(wydruk("", k, ["I have a significant problem with Word."], wbudowany=True), self.src)
        self.assertEqual(w.klucz, "gate_builtin_vs_config")

    def test_zrodlo_nie_znalezione(self):
        k = self.folder.parent / "_default"
        w = self.werdykt(wydruk(str(self.src), k, ["I have a significant problem."], brak=True), self.src)
        self.assertEqual(w.klucz, "gate_source_not_loaded")

    def test_pusty_config_a_wyjscia_z_pliku(self):
        w = self.werdykt(wydruk(self.src, self.folder, self.podglady), "")
        self.assertEqual(w.klucz, "gate_source_vs_empty")

    def test_inny_katalog(self):
        w = self.werdykt(wydruk(self.src, self.k / "export_results" / "inny", self.podglady), self.src)
        self.assertEqual(w.klucz, "gate_dir_mismatch")

    def test_przebieg_przerwany_przed_eksportem(self):
        nb = nb_z(wydruk(self.src, self.folder, self.podglady), eksport="")
        w = z.sprawdz(nb, str(self.src), self.folder, self.nbp)
        self.assertEqual(w.klucz, "gate_run_incomplete")

    def test_wyjscia_niezapisane(self):
        nowy = time.time() + 120
        os.utime(self.folder / "paragraphs.csv", (nowy, nowy))
        w = self.werdykt(wydruk(self.src, self.folder, self.podglady), self.src)
        self.assertEqual(w.klucz, "gate_outputs_not_saved")

    def test_podmieniona_tresc_pod_ta_sama_sciezka(self):
        self.src.write_text(INNY, encoding="utf-8")
        w = self.werdykt(wydruk(self.src, self.folder, self.podglady), self.src)
        self.assertEqual(w.klucz, "gate_content_mismatch")

    def test_jeden_podglad_z_ocr_nie_blokuje(self):
        w = self.werdykt(wydruk(self.src, self.folder, ["Tekst rozpoznany przez OCR, którego nie ma w warstwie"]
                                + self.podglady), self.src)
        self.assertTrue(w.ok)
        self.assertEqual(w.argumenty, {"found": 2, "checked": 3})

    def test_znieksztalcona_warstwa_nie_blokuje(self):
        self.src.write_text("ɍɬɜɟɪɠɞɟɧɨ ɜ ɤɚɱɟɫɬɜɟ ɭɱɟɛɧɨɝɨ ɩɨɫɨɛɢɹ " * 200, encoding="utf-8")
        w = self.werdykt(wydruk(self.src, self.folder, self.podglady), self.src)
        self.assertTrue(w.ok)
        self.assertEqual((w.klucz, w.argumenty["reason"]), ("gate_ok_path_only", "garbled"))

    def test_url_tylko_sciezka(self):
        url = "https://example.org/artykul"
        s = wydruk("", self.folder, self.podglady).replace("Корпус готов", f"  Загрузка URL: {url}\nКорпус готов", 1)
        w = self.werdykt(s, url)
        self.assertEqual((w.klucz, w.argumenty["reason"]), ("gate_ok_path_only", "url"))

    def test_brak_wyjsc(self):
        w = z.sprawdz({"cells": [{"cell_type": "code", "metadata": {}, "outputs": []}]},
                      str(self.src), self.folder, self.nbp)
        self.assertEqual(w.klucz, "gate_no_outputs")

    def test_stary_notatnik_bez_tagow(self):
        nb = nb_z(wydruk(self.src, self.folder, self.podglady))
        nb["cells"][0]["metadata"] = {}
        self.assertTrue(z.sprawdz(nb, str(self.src), self.folder, self.nbp).ok)

    def test_omorfi_status(self):
        akt = "--- Загрузка языковой модели ---\n  [OK] Подключён omorfi: omorfi_recased.describe.hfst — леммы\n"
        bez = "--- Загрузка языковой модели ---\n[ИНФО] Пакет omorfi не установлен — леммы финского остаются от spaCy.\n"
        blad = "--- Загрузка языковой модели ---\n[ВНИМАНИЕ] Не удалось загрузить omorfi.describe.hfst: boom\n"
        self.assertEqual(z.omorfi_status(nb_z("", akt)), "active")
        self.assertEqual(z.omorfi_status(nb_z("", bez)), "inactive")
        self.assertEqual(z.omorfi_status(nb_z("", blad)), "inactive")
        self.assertEqual(z.omorfi_status(nb_z("", "--- Загрузка языковой модели ---\n[OK] pl\n")), "absent")


class TestTonPrzecieku(unittest.TestCase):
    """ksiega_niedomowien.leak_reason: ton zależy od świadka w analysis_report.html."""

    @classmethod
    def setUpClass(cls):
        try:
            import ksiega_niedomowien as k
        except ImportError as e:  # brak zależności Księgi w środowisku testu
            raise unittest.SkipTest(str(e))
        cls.k = k

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.f = Path(self.tmp.name)
        (self.f / "keywords_tfidf.csv").write_text("term\n", encoding="utf-8")
        stary = time.time() - 120
        os.utime(self.f / "keywords_tfidf.csv", (stary, stary))

    def tearDown(self):
        self.tmp.cleanup()

    def raport(self, status):
        (self.f / "analysis_report.html").write_text(
            f'<html><head><meta name="ata-omorfi" content="{status}"></head></html>', encoding="utf-8")

    def klucz(self):
        tr = self.k.tr
        powod = self.k.leak_reason(self.f, 2.5, "mietia")
        for key in ("reason_grammar_leak_engine", "reason_grammar_leak_no_omorfi",
                    "leak_omorfi_absent", "leak_omorfi_unknown"):
            if tr(self.k.UI_LANG, "kirja." + key, rate="2.50", max=self.k.GRAMMAR_LEAK_MAX,
                  examples="mietia") in powod:
                return key
        return None

    def test_omorfi_byl(self):
        self.raport("active")
        self.assertEqual(self.klucz(), "reason_grammar_leak_engine")

    def test_omorfi_nie_bylo(self):
        self.raport("inactive")
        self.assertEqual(self.klucz(), "reason_grammar_leak_no_omorfi")

    def test_raport_bez_sladu_omorfi(self):
        self.raport("absent")
        self.assertEqual(self.klucz(), "leak_omorfi_absent")

    def test_brak_raportu(self):
        self.assertEqual(self.klucz(), "leak_omorfi_unknown")

    def test_raport_starszy_niz_eksport(self):
        self.raport("active")
        stary = time.time() - 600
        os.utime(self.f / "analysis_report.html", (stary, stary))
        self.assertEqual(self.klucz(), "leak_omorfi_unknown")


class TestCustomPatterns(unittest.TestCase):
    """Audyt 2026-10-20 (M4): loader usuwa dopasowania `custom_patterns`
    przed podglądem, więc bramka czytająca surowy plik odmawiała fałszywie."""

    WZORZEC = r"PUHUJA \d+:"

    def setUp(self):
        import re
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        zdania = ["Hyvää huomenta kaikille kuulijoille", "Tänään puhumme turvallisuudesta",
                  "Kysymys koskee koko Itämeren aluetta", "Vastaus ei ole yksinkertainen"]
        linie = [f"[00:{i:02d}] PUHUJA {i % 3 + 1}: {zdania[i % 4]} numero {i}." for i in range(60)]
        self.src = Path(self.tmp.name) / "litteraatti.txt"
        self.src.write_text("\n".join(linie), encoding="utf-8")
        # Podgląd tak, jak drukuje go notatnik: load_txt usuwa wzorzec i zwija spacje.
        tekst = re.sub(r"[ \t]+", " ", re.sub(self.WZORZEC, "", self.src.read_text(encoding="utf-8"))).strip()
        self.podglady = [tekst[:80].replace("\n", " ")]

    def test_bez_wzorcow_to_rozjazd(self):
        self.assertEqual(z.sprawdz_tresc(str(self.src), self.podglady).stan, "rozjazd")

    def test_wzorce_z_configu_daja_zgodnosc(self):
        t = z.sprawdz_tresc(str(self.src), self.podglady, [self.WZORZEC])
        self.assertEqual((t.stan, t.znalezione), ("zgodna", 1))

    def test_wzorce_bez_dowodu_nie_odmawiaja(self):
        t = z.sprawdz_tresc(str(self.src), ["Kokonaan toinen teksti, jota tiedostossa ei ole lainkaan"],
                            [self.WZORZEC])
        self.assertEqual((t.stan, t.powod), ("niesprawdzalna", "custom_patterns"))


if __name__ == "__main__":
    unittest.main()
