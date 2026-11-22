# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.6
#   kernelspec:
#     display_name: analyst_env
#     language: python
#     name: analyst_env
# ---

# %% [markdown] id="md_intro" tags=["md_intro"]
# # Доступный анализ текста (spaCy · TF-IDF · KMeans)
#
# Полный конвейер текстовой аналитики для языков из `dictionaries/<код>/` (сегодня: польский, русский, английский, итальянский, немецкий, испанский, французский, финский, исландский).  
# Все результаты выводятся через `print()` — без цветовой кодировки и псевдографики.  
# Совместим с экранными читалками **NVDA** и **JAWS**.
#
# **Единственное, что нужно от пользователя:** задать путь к файлу `.pdf`, `.txt` или `.docx` в первой ячейке кода. Если файл не найден — используется встроенный пример.
#
# ---
#
# **Этапы анализа:**
#
# 1. **Загрузка корпуса** — PDF постранично (pdfplumber), TXT, DOCX (python-docx), Markdown (.md), HTML-файл или **URL** (прямой адрес страницы); BeautifulSoup удаляет навигацию, боковые панели и блоки «Похожие статьи» при загрузке из URL или HTML; встроенный пример как запасной вариант.
# 2. **Языки текста** — пользователь перечисляет языки текста (`corpus_languages`); их словари определяют основной язык корпуса, а затем язык каждого слова: иноязычные цитаты и фамилии становятся отрезками со своим языком (`odcinki_jezykowe.py`, без статистического детектора).
# 3. **Языковая модель spaCy** — автоматически выбирается модель версии **Large (lg)**: `pl_core_news_lg`, `ru_core_news_lg`, `en_core_web_lg`, `it_core_news_lg`, `de_core_news_lg`, `es_core_news_lg`, `fr_core_news_lg`, `fi_core_news_lg`; для исландского (`is`) — `spacy.blank("is")` + Hugging Face (`mideind/IceBERT` — векторы, `grammatek/icelandic-ner-bert` — NER, обучен на MIM-GOLD-NER). Модели подгружаются по требованию через `get_nlp(lang)`, защищённый `functools.lru_cache(maxsize=2)`: одновременно в RAM держатся не более двух моделей, остальные вытесняются по принципу LRU.
# 4. **Коррекция текста** — нормализация аббревиатур с пробелами для польского (`m. in.`→`m.in.`), русского (`т. е.`→`т.е.`) и английского (`e. g.`→`e.g.`).
# 5. **Базовый NLP** — токенизация на слова и предложения, фильтрация стоп-слов, лемматизация, POS-теггинг (NOUN/VERB/ADJ/…).
# 6. **Именованные сущности (NER)** — люди, организации, места, даты и другие объекты (с частотной сводкой по всему корпусу).
# 7. **Мешок слов (CountVectorizer)** — матрица частот с языко-специфичными стоп-словами; топ-10 слов и топ-5 биграмм.
# 8. **TF-IDF и автопоиск** — запрос автоматически строится из топ-терминов корпуса; косинусное сходство гарантированно > 0.
# 9. **Структура текста** — предложения из того же единственного прохода spaCy (каждый языковой сегмент — своей моделью) группируются в абзацы по 3–6 предложений; язык предложений и вставок попадает в HTML/DOCX.
# 10. **Ключевые слова** — рейтинговая таблица терминов и фраз (1–3 слова) по средневзвешенному TF-IDF на уровне абзацев.
# 11. **Тезисы** — лучшее по TF-IDF-сумме предложение каждого абзаца; сохраняются в `тезисы.txt` в формате `- предложение`.
# 12. **Тематизация (KMeans)** — кластеризация абзацев по spaCy-векторам; для каждой темы — ключевые слова и пример фрагмента *(требует модели `*_md` или `*_lg` с векторами)*.
# 13. **Экспорт результатов** — CSV (UTF-8 BOM, совместимо с Excel), JSON (ключевые слова тем), TXT (тезисы), `language_spans.csv` (иноязычные отрезки) и **доступный HTML/DOCX** с атрибутом `lang` на каждом абзаце, иноязычном предложении и вставке — экранные читалки автоматически переключают голос на нужный язык.
# 14. **Итоговый отчёт** — все ключевые метрики в одном текстовом блоке.

# %% id="cell_corpus" tags=["cell_corpus"]
# ============================================================
# ВВОД ДАННЫХ: путь к исходному файлу/URL берётся из config.json
# или config.ini (содержимое обоих — JSON). Скопируйте
# config.example.json в config.json (или config.example.ini в
# config.ini) и укажите source_file. Если ни один файл не найден,
# используется встроенный пример.
# ============================================================
import os, re, json, math
from pathlib import Path
from collections import Counter
from urllib.parse import urlparse

from shamanic_locale import t

SOURCE_FILE = ""
CUSTOM_PATTERNS = []
# Языки ТЕКСТА (коды из dictionaries/<код>/podstawy.yaml), ключ "corpus_languages"
# в config.json (прежнее имя "ocr_languages" тоже читается). По ним:
#  - OCR читает сканы и изображения: каждый язык — свой движок, слова
#    выбирает словарь (glosowanie_ocr.py);
#  - словари тех же языков размечают язык каждого слова (odcinki_jezykowe.py),
#    а основной язык — тот, словарь которого знает больше всего слов.
# Указывайте только языки, которые действительно есть в тексте: лишний язык
# замедляет OCR и даёт словарям ложных кандидатов. Финский текст с польскими
# фамилиями: ["fi", "pl"] — фамилии прочтёт польский голос. Смешивать
# латиницу и кириллицу можно (например ["fi", "ru"]).
CORPUS_LANGS = ["en"]
# Опциональный анализ тональности (по умолчанию выключен). Включается ключом
# "enable_sentiment": true в config.json. Это тяжёлая опция (~1,1 ГБ модель
# cardiffnlp при первом запуске) и она НЕ выводит вердикт пользователю —
# результат пишется только в sentiment.csv как «пища» для шаманского слоя.
ENABLE_SENTIMENT = False

# Принимаем config.json и config.ini (содержимое — всегда JSON,
# расширение .ini — лишь косметика для нетехнических пользователей
# на Windows, где тип .json неизвестен, а .ini открывается в блокноте).
_CONFIG_PATH = None
for _name in ("config.json", "config.ini"):
    _candidate = Path(_name)
    if _candidate.is_file():
        _CONFIG_PATH = _candidate
        break
if _CONFIG_PATH is not None:
    try:
        _cfg = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        SOURCE_FILE = (_cfg.get("source_file") or "").strip()
        CUSTOM_PATTERNS = list(_cfg.get("custom_patterns") or [])
        _langs_cfg = _cfg.get("corpus_languages") or _cfg.get("ocr_languages")
        if isinstance(_langs_cfg, list) and _langs_cfg:
            CORPUS_LANGS = [str(x).strip() for x in _langs_cfg if str(x).strip()]
        ENABLE_SENTIMENT = bool(_cfg.get("enable_sentiment", False))
        print(f"[OK] Конфигурация загружена: {_CONFIG_PATH}")
    except Exception as _e:
        print(f"[ВНИМАНИЕ] Не удалось прочитать {_CONFIG_PATH}: {_e}")
else:
    print("[ИНФО] Файл config.json/config.ini не найден — используется встроенный пример.")
    print("       Скопируйте config.example.json в config.json (или config.example.ini в config.ini)")
    print("       и задайте source_file.")

# Wielkie litery wszystkich języków korpusu — suma pól `alfabet` z
# dictionaries/<kod>/podstawy.yaml (łacinka z diakrytykami + cyrylica)
# + Ü, której nie ma żaden alfabet, a otwiera obce nazwy w nagłówkach
# („Fot CPK 521 Über…”) — dawne _WIELKIE ją miało.
from shamanic_locale import wielkie_litery
_WIELKIE = wielkie_litery() + "Ü"


def clean_web_article_start(text, check_window=400):
    """Remove common web-scraping artifacts from extracted article text:
    - Photo credits/view counters: "Fot. CPK 521", standalone "CPK 524"
    - Doubled metadata from responsive layouts: "Author Date Author Date"
    """
    if not text:
        return text
    # Remove photo credit patterns (Polish "Fot." = photo)
    text = re.sub(r"\bFot\.\s+[A-Z][A-Za-z0-9]*\.?\s*\d*\s*", " ", text)
    # Licznik wyświetleń/zdjęć: TYLKO w nagłówku artykułu, nigdy rok, a po
    # liczbie musi stać wielka litera. Na całym tekście ten wzorzec zjadał
    # prozę: „Szczyt NATO 2024 odbył” → „Szczyt odbył”, „PKB 2500 mld”,
    # „BMW 320”, „EU 2030” (audyt 2026-10-15).
    head, tail = text[:check_window], text[check_window:]
    head = re.sub(rf"\b[A-Z]{{2,}}\s+(?!(?:19|20)\d\d\b)\d{{3,}}\s+(?=[{_WIELKIE}])",
                  " ", head)
    # Podwojony tytuł/autor/data z układu responsywnego (mobile + desktop).
    # Granice białych znaków i bez interpunkcji zdaniowej w środku: dawne
    # (.{10,60})\s+\1 zwijało „na przykład na przykładzie” i refren
    # „Тук-тук, кто там? Тук-тук, кто там?”.
    m = re.search(r"(?<!\S)([^\s,;?!…—–](?:[^,;?!…—–]{8,58})[^\s,;?!…—–])\s+\1(?!\S)", head)
    if m and not re.search(r"\.\s", m.group(1)):
        rep = re.escape(m.group(1))
        head = re.sub(r"(?<!\S)(" + rep + r")\s+\1(?!\S)", r"\1", head, count=1)
    return re.sub(r"\s+", " ", head + tail).strip()

def clean_pdf_text(s: str) -> str:
    """Базовая очистка текста из PDF: мягкие дефисы, разорванные слова, пробелы."""
    if not s:
        return ""
    s = s.replace("\u00ad", "")              # мягкий дефис
    s = re.sub(r"(\w)-\n(\w)", r"\1\2", s)  # склейка слов через перенос
    s = s.replace("\n", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

# Структурные маркеры сценариев, пьес и иных текстов с повторяющейся
# разметкой границ. Эти строки могут многократно встречаться на разных
# страницах PDF (например, [scena 1] на каждой странице длинной сцены),
# но НЕ являются колонтитулами и не должны удаляться эвристикой
# strip_repeated_headers — иначе экранизация теряет границы сцен,
# обозначение «[koniec]», «[napis na ekranie]» и подобное.
from shamanic_locale import naglowki_struktury

_STRUCTURAL_PATTERNS = [
    re.compile(r"^\s*\[[^\]]+\]\s*$"),   # [scena 1], [koniec], [napis na ekranie]
    re.compile(r"^\s*\([^)]+\)\s*$"),    # (didaskalia)
    # INT./EXT. poza grupą z końcowym \b: po kropce stoi spacja, więc \b nie
    # pasowało i „INT. KUCHNIA” nie było chronione (audyt 2026-10-15).
    re.compile(r"^\s*(?:INT|EXT)\.", re.IGNORECASE),
    # Słowa scen/aktów/rozdziałów wszystkich języków — pole
    # `naglowki_struktury` w dictionaries/<kod>/podstawy.yaml. FADE IN/OUT
    # i CUT TO to konwencja scenariusza, nie język — zostają tutaj.
    re.compile(
        r"^\s*(?:FADE\s+IN|FADE\s+OUT|CUT\s+TO|"
        + "|".join(re.escape(_w) for _w in naglowki_struktury())
        + r")\b",
        re.IGNORECASE,
    ),
]


def _is_structural_line(line: str) -> bool:
    """True для строк, выглядящих как структурный маркер сценария/пьесы:
    полностью обёрнутые в [...] или (...), либо начинающиеся с
    ключевого слова сцены/акта на одном из поддерживаемых языков.
    Такие строки сохраняются независимо от частоты повторов."""
    stripped = line.strip()
    if not stripped:
        return False
    return any(p.match(stripped) for p in _STRUCTURAL_PATTERNS)


# Linia dialogu/cytatu/punktu: nigdy nie jest kolontytułem.
_DIALOG_LINE = re.compile(r"^\s*[—–\-„\"«»'•*·]")


def _header_key(line):
    """(pełny klucz, rdzeń bez numeru na brzegu, numer albo None)."""
    s = re.sub(r"\s+", " ", line.strip()).lower()
    lead = re.match(r"^(\d+)\s*", s)
    trail = re.search(r"\s*(\d+)$", s)
    num = int(lead.group(1)) if lead else (int(trail.group(1)) if trail else None)
    core = re.sub(r"^\d+\s*|\s*\d+$", "", s).strip()
    return s, core, num


def strip_repeated_headers(raw_pages, min_fraction=0.4, max_line_chars=150, edge=3,
                           margin_lines=None):
    """Удаляет повторяющиеся колонтитулы.

    Kandydatami są WYŁĄCZNIE linie z brzegów strony (pierwsze i ostatnie
    `edge` niepuste) — kolontytuł nie żyje w środku strony. Linia jest
    kolontytułem, gdy powtarza się 1:1 na >= max(3, ceil(N*min_fraction))
    stronach, albo gdy jej rdzeń bez numeru powtarza się, a numer rośnie
    RAZEM ze stroną (stały offset numer − indeks w >= 80% wystąpień).
    Dokumenty krótsze niż 3 strony zostają nietknięte.

    `margin_lines` (od 1.9.1): lista zgodna z `raw_pages` — dla strony z warstwą
    tekstu zbiór linii leżących w pasie marginesu (pozycja z pdfplumber), dla
    strony z OCR `None`. Kandydatem jest wtedy linia z brzegu tekstu ORAZ
    z pasa marginesu, jak w Reżyserze: akapit prozy powtórzony na kilku
    stronach, który po zdjęciu numeru strony wypadł na jej brzeg, nie leży
    w marginesie i zostaje (zmierzone na PDF-ie z Worda).

    Dawna wersja (próg max(2, N*0.25), cała strona, numer zawsze zdejmowany)
    wycinała prozę: refren na 2 z 8 stron, „— Tak, panie — odparł.” na 2 z 4,
    „Lekcja 1/2/3” jako jeden klucz (audyt 2026-10-15). Koszt zmiany: nagłówki
    dokumentów 2-stronicowych i „Pytanie N” na każdej stronie zostają.

    Исключение: строки, соответствующие _STRUCTURAL_PATTERNS (маркеры
    сцен, актов и т.п. в сценариях и пьесах), сохраняются всегда.
    """
    n_pages = len(raw_pages)
    if n_pages < 3:
        return list(raw_pages), set()
    threshold = max(3, math.ceil(n_pages * min_fraction))

    def edges(pi, page):
        ls = [l for l in page.splitlines() if l.strip()]
        base = set(ls[:edge] + ls[-edge:])
        band = margin_lines[pi] if margin_lines is not None else None
        return base if band is None else {l for l in base if l.strip() in band}

    def candidate(line):
        return (len(line.strip()) <= max_line_chars
                and not _is_structural_line(line)
                and not _DIALOG_LINE.match(line))

    exact, core_offsets = Counter(), {}
    for pi, page in enumerate(raw_pages):
        seen_exact, seen_core = set(), set()
        for line in edges(pi, page):
            if not candidate(line):
                continue
            s, core, num = _header_key(line)
            if len(core) <= 5:
                continue
            if s not in seen_exact:
                exact[s] += 1
                seen_exact.add(s)
            if num is not None and core not in seen_core:
                core_offsets.setdefault(core, []).append(num - pi)
                seen_core.add(core)
    bp_exact = {s for s, c in exact.items() if c >= threshold}
    bp_core = {core for core, offs in core_offsets.items()
               if len(offs) >= threshold
               and Counter(offs).most_common(1)[0][1] >= 0.8 * len(offs)}

    protected = 0
    cleaned = []
    for pi, page in enumerate(raw_pages):
        e = edges(pi, page)
        kept = []
        for line in page.splitlines():
            if _is_structural_line(line):
                protected += 1
            elif line in e and candidate(line):
                s, core, num = _header_key(line)
                if s in bp_exact or (num is not None and core in bp_core):
                    continue
            kept.append(line)
        # Bezpiecznik: strona z treścią nie traci WSZYSTKICH linii. Gdy każda
        # linia strony wygląda na kolontytuł (strony o identycznej krótkiej
        # treści), to są dane, nie stopka — strona zostaje w całości.
        if page.strip() and not any(l.strip() for l in kept):
            kept = page.splitlines()
        cleaned.append("\n".join(kept))
    if protected:
        print(f"  Защищено структурных маркеров (сцены/акты/didaskalia): {protected}")
    return cleaned, bp_exact | bp_core

# ============================================================
# OCR: распознавание сканов PDF и изображений ГОЛОСОВАНИЕМ (glosowanie_ocr.py).
# Движок OCR знает один язык за раз: польский меняет финские ä, финский теряет
# ą/ę/ł, русский вставляет кириллицу в латинские слова. Поэтому страницу читает
# движок КАЖДОГО языка из corpus_languages (встроенный OCR Windows; для языка без
# него — Tesseract, сегодня исландский) и дополнительно RapidOCR (запас для
# фото страниц и финского, которого easyocr не знал), а из каждого результата
# берутся словарные формы. Нехватка движка или словаря — ОШИБКА, а не тихо
# пропавший текст (решение 2026-11-13): исправление — изменить corpus_languages
# или установить недостающий компонент.
# ============================================================
_OCR_PLAN = None
_OCR_PLAN_LANGS = None
_OCR_PRICHINY = {
    "nieznany_jezyk": "язык не поддерживается",
    "brak_silnika": "нет движка OCR",
    "brak_slownika": "нет словаря",
}


def _silence_ocr_progress():
    """Глушит tqdm-прогрессбары OCR, чтобы вывод оставался
    дружелюбным к экранным дикторам (NVDA/JAWS)."""
    os.environ.setdefault("TQDM_DISABLE", "1")
    try:
        from functools import partialmethod
        from tqdm import tqdm
        tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)
    except Exception:
        pass


def _ocr_plan(langs):
    """План OCR (движок и словарь каждого языка) — один раз на набор языков:
    словари загружаются секундами. Любая нехватка — RuntimeError после
    печати ВСЕХ проблем сразу, чтобы пользователь исправил их за один заход."""
    global _OCR_PLAN, _OCR_PLAN_LANGS
    key = tuple(langs)
    if _OCR_PLAN is not None and _OCR_PLAN_LANGS == key:
        return _OCR_PLAN
    _silence_ocr_progress()
    import glosowanie_ocr
    print(f"  Подготовка OCR (языки: {list(langs)}): движки и словари...")
    try:
        plan = glosowanie_ocr.zaplanuj(list(langs))
    except glosowanie_ocr.BladGlosowania as _e:
        print("[ОШИБКА] OCR не может работать с языками из corpus_languages:")
        for _p in _e.problemy:
            print(f"  {_p.kod}: {_OCR_PRICHINY.get(_p.przyczyna, _p.przyczyna)} — {_p.szczegol}")
        print("  Исправление: убрать язык из corpus_languages в config.json "
              "или установить недостающий компонент.")
        raise RuntimeError(f"OCR: {_e}") from None
    for _k, _tag in plan.windows.items():
        print(f"    {_k}: движок Windows ({_tag}), словарь: {plan.slowniki[_k].zrodlo}")
    for _k in plan.tesseract:
        print(f"    {_k}: Tesseract, словарь: {plan.slowniki[_k].zrodlo}")
    for _model, _kody in plan.rapid.items():
        print(f"    RapidOCR ({_model}): дополнительное чтение для {', '.join(_kody)}")
    # Лицензия данных словаря (BÍN: CC BY-SA 4.0) требует указания авторства
    # при каждом использовании — оно попадает в вывод ячейки и в отчёт.
    for _uz in sorted({s.uznanie for s in plan.slowniki.values() if s.uznanie}):
        print(f"    Словарь: {_uz}")
    # Модели RapidOCR и Tesseract загружаются здесь, один раз (при первом запуске
    # RapidOCR скачивает их, около 40 МБ), а не на первой странице документа.
    glosowanie_ocr.rozgrzej(plan)
    _OCR_PLAN, _OCR_PLAN_LANGS = plan, key
    return plan


def _ocr_obraz(obraz, langs):
    """Одна страница (PIL.Image) → текст голосованием движков всех языков."""
    import glosowanie_ocr
    wynik = glosowanie_ocr.odczytaj(obraz, list(langs), _ocr_plan(langs))
    return wynik.tekst, wynik


def _pdf_ocr_pages(path, langs, pages=None):
    """Рендерит страницы PDF через pypdfium2 и распознаёт текст голосованием.

    pages — индексы страниц (от 0) для OCR; None = все страницы.
    Возвращает словарь {индекс: текст}. Без pypdfium2 — пустой словарь
    с предупреждением; без движка или словаря языка — RuntimeError (_ocr_plan).
    """
    try:
        import pypdfium2 as pdfium
    except ImportError:
        print("[ВНИМАНИЕ] pypdfium2 не установлен. Выполните: pip install pypdfium2")
        return {}
    # План проверяем ОДИН раз и до рендера: ошибка конфигурации видна сразу.
    _ocr_plan(langs)
    pdf = pdfium.PdfDocument(path)
    pages_text = {}
    total = len(pdf)
    indices = list(range(total)) if pages is None else list(pages)
    try:
        for i in indices:
            page = pdf[i]
            # scale=2.0 → ~144 DPI; высокие страницы режутся на полосы внутри
            # ocr_windows (предел движка Windows 10000 px).
            text, wynik = _ocr_obraz(page.render(scale=2.0).to_pil(), langs)
            page.close()
            pages_text[i] = text
            print(f"  OCR: страница {i+1}/{total} — {len(text)} символов "
                  f"(основа: {wynik.baza}, заменено слов: {wynik.zmiany}, "
                  f"добавлено: {wynik.dodane}).")
    finally:
        pdf.close()
    return pages_text


def load_image(path):
    """Распознаёт текст с изображения голосованием и возвращает его
    как список из одной «псевдостраницы»."""
    from PIL import Image
    print(f"  Изображение: запуск OCR (языки: {CORPUS_LANGS})...")
    with Image.open(path) as _img:
        _img.load()
        text, _wynik = _ocr_obraz(_img, CORPUS_LANGS)
    if not text.strip():
        print("  [ВНИМАНИЕ] OCR не вернул текста — изображение пустое или нечитаемое.")
        return []
    # Применяем CUSTOM_PATTERNS (если определены)
    if CUSTOM_PATTERNS:
        for _cp in CUSTOM_PATTERNS:
            text = re.sub(_cp, "", text)
        text = re.sub(r"\s+", " ", text).strip()
    print(f"  Изображение: распознано {len(text)} символов.")
    return [text]


# Kształt gołego numeru strony: „7”, „- 7 -”, „xii”, „7 / 120”, „7 z 120”,
# „7 of 120”, „7 из 120”, „7 af 120”. Wzorzec 1:1 z `core_pdf._RE_NUMER_STRONY`
# w Reżyserze (bliźniak `formaty_zrodel`). SAM KSZTAŁT NIE WYSTARCZA do
# usunięcia — patrz `_page_numbers_to_drop` (audyt Reżysera 19.13: „II”,
# „MIX”, „did” z marginesu jednej strony znikały, w ATA 1.9.0 tak samo).
_PAGE_NUMBER_LINE = re.compile(
    r"^[-–—\s]*(\d{1,4}|[ivxlcdmIVXLCDM]{1,6})(?:\s*(?:/|z|of|из|af)\s*\d{1,4})?[-–—\s]*$")
# Pas marginesu (ułamek wysokości strony od góry i od dołu), jak w Reżyserze:
# 7%, nie 12% — margines Worda to 8,5% A4, a pas 12% obejmował pierwszą
# i ostatnią linię TREŚCI.
PAGE_MARGIN = 0.07
# Minimalny ułamek stron, na których numer musi rosnąć razem ze stroną.
PAGE_SHARE = 0.25
_ROMAN = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}


def _roman_value(text):
    """Wartość POPRAWNEJ (kanonicznej) liczby rzymskiej, inaczej None."""
    s = text.lower()
    if not s or any(ch not in _ROMAN for ch in s):
        return None
    value = 0
    for a, b in zip(s, s[1:] + " "):
        va, vb = _ROMAN[a], _ROMAN.get(b, 0)
        value += -va if va < vb else va
    if not 0 < value < 4000:
        return None
    canon, rest = "", value
    for v, sym in ((1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"),
                   (90, "xc"), (50, "l"), (40, "xl"), (10, "x"), (9, "ix"),
                   (5, "v"), (4, "iv"), (1, "i")):
        while rest >= v:
            canon += sym
            rest -= v
    return value if canon == s else None


def _page_number_value(text):
    m = _PAGE_NUMBER_LINE.match(text)
    if not m:
        return None
    core = m.group(1)
    return int(core) if core.isdigit() else _roman_value(core)


def _page_text_and_number_candidates(page):
    """(tekst, [(linia, wartość, 'top'|'bottom'), …], {linie w pasie marginesu}).

    Kandydat = linia w górnym/dolnym pasie `PAGE_MARGIN` (pozycja z
    `extract_text_lines`) o kształcie numeru strony. O usunięciu decyduje
    dopiero `_page_numbers_to_drop`, patrząc na cały dokument.
    """
    text = page.extract_text() or ""
    if not text.strip():
        return text, [], set()
    band = page.height * PAGE_MARGIN
    found, margin = [], set()
    for l in page.extract_text_lines():
        side = "top" if l["top"] <= band else ("bottom" if l["bottom"] >= page.height - band else None)
        if side:
            margin.add(l["text"].strip())
        value = _page_number_value(l["text"]) if side else None
        if value is not None:
            found.append((l["text"].strip(), value, side))
    return text, found, margin


def _page_numbers_to_drop(pages):
    """Usuwa gołe numery stron; zwraca (teksty stron, ile usunięto).

    Linia znika tylko wtedy, gdy jej wartość rośnie RAZEM ze stroną — ta sama
    różnica „numer − indeks strony” w tym samym pasie na co najmniej
    max(2, ⌈PAGE_SHARE·N⌉) stronach — i jest wśród 3 pierwszych/ostatnich
    niepustych linii tekstu. Rzymski nagłówek „II” na jednej stronie, słowo
    „MIX” czy rok „2026” w stopce tej różnicy nie dzielą i zostają. Dokument
    jednostronicowy nie traci nic. `strip_repeated_headers` numerów nie łapie
    (rdzeń krótszy niż 6 znaków), więc bez tego numer sklejał się z ostatnim
    zdaniem strony („…erikseen. 2”).
    """
    groups = {}
    for idx, (_text, found, _margin) in enumerate(pages):
        for line, value, side in found:
            groups.setdefault((side, value - idx), set()).add((idx, line))
    need = max(2, math.ceil(len(pages) * PAGE_SHARE))
    drop = set()
    for members in groups.values():
        if len({idx for idx, _ in members}) >= need:
            drop |= members
    texts, removed = [], 0
    for idx, (text, _found, _margin) in enumerate(pages):
        lines = text.splitlines()
        nonempty = [i for i, l in enumerate(lines) if l.strip()]
        edge = set(nonempty[:3] + nonempty[-3:])
        kept = [l for i, l in enumerate(lines) if not (i in edge and (idx, l.strip()) in drop)]
        removed += len(lines) - len(kept)
        texts.append("\n".join(kept))
    return texts, removed


def load_pdf(path):
    """Загружает PDF постранично, удаляет повторяющиеся колонтитулы, очищает текст.

    Страницы без текстового слоя (сканы) распознаются OCR (pypdfium2 +
    голосование движков, glosowanie_ocr) — ТОЛЬКО они и в исходном порядке страниц. До 2026-10-15 OCR
    запускался лишь тогда, когда текста не было НИ НА ОДНОЙ странице: в
    смешанном PDF (текст + вставленные сканы) сканы молча выпадали из корпуса.
    Страницы, оставшиеся пустыми и после OCR (или без OCR), перечисляются
    номерами — их содержимого в корпусе не будет.

    Bramka warstwy tekstu (od 2026-10-20, moduł `naprawa_zrodel`): font bez
    pełnej mapy ToUnicode daje w pdfplumberze znaczniki „(cid:N)”. Najpierw
    `napraw_strone` odczytuje znaki z osadzonego fontu; strona, której font
    nie rozwiązał w całości, a znaczników jest ≥ 3 i ≥ 2% liter, NIE trafia do
    korpusu (ani do Lingui) — idzie do OCR jak skan albo jest wymieniona."""
    try:
        import pdfplumber
    except ImportError:
        print("[ВНИМАНИЕ] pdfplumber не установлен. Выполните: pip install pdfplumber")
        return []
    from naprawa_zrodel import (napraw_strone, usun_znaczniki, zakresy_stron, ZNACZNIK_CID,
                                serie_rozstrzelone, oznacz_granice, oczysc_strone_pdf,
                                ZNACZNIK_GRANICY, wyprostuj_znaki, ZASTEPCZY,
                                litery_spoza_winansi, rekonstruuj_zastepcze,
                                oznacz_wykresy, zwin_znaczniki_wykresow,
                                bez_znacznikow_wykresow)
    from czyszczenie_tekstu import scal_rozstrzelone
    from shamanic_locale import alfabety_paczek
    _fonts = {}
    with pdfplumber.open(path) as pdf:
        total = len(pdf.pages)
        # Naprawa PRZED pierwszym extract_text: pdfplumber buforuje mapę tekstu.
        checks = [napraw_strone(page, _fonts) for page in pdf.pages]
        # Znaki „pionowe” przez obrót ~1e-8 rad (wykresy biuletynów) — inaczej
        # pdfplumber rwie słowa na litery („B lo o m b e rg”).
        _upright = sum(wyprostuj_znaki(page) for page in pdf.pages)
        # Etykiety wykresów (z geometrii) dostają niewidoczny znacznik: zostają
        # do odczytu w HTML/DOCX, a cell_tok wycina je przed NLP.
        _chart = sum(oznacz_wykresy(page) for page in pdf.pages)
        info = [(zwin_znaczniki_wykresow(_t), _f, {zwin_znaczniki_wykresow(_m) for _m in _mg})
                for _t, _f, _mg in (_page_text_and_number_candidates(page) for page in pdf.pages)]
        # Granice słów w tekście rozstrzelonym — z GEOMETRII znaków, nie z tekstu.
        spaced = [serie_rozstrzelone(page) for page in pdf.pages]
    texts, removed_numbers = _page_numbers_to_drop(info)
    # Pas marginesu znany tylko dla stron z warstwą tekstu; strona z OCR → None.
    margins = [m if t.strip() else None for (t, _f, m) in info]
    if removed_numbers:
        print(f"  PDF: удалено номеров страниц: {removed_numbers}.")
    if _upright:
        print(f"  PDF: символов с почти нулевым поворотом, ошибочно считавшихся вертикальными "
              f"(слова рвались на буквы), выпрямлено: {_upright}.")
    if _chart:
        print(f"  PDF: подписи диаграмм (текст внутри и рядом с векторной графикой), символов: "
              f"{_chart}. Они остаются для чтения в HTML/DOCX, но исключаются из NLP-анализа.")
    repaired =[i for i, c in enumerate(checks) if c.naprawiona]
    broken = [i for i, c in enumerate(checks) if c.do_zgloszenia]
    if repaired:
        print(f"  PDF: карта символов шрифта (ToUnicode) неполная на страницах "
              f"{zakresy_stron(repaired)} — текст восстановлен по встроенным шрифтам.")
    if broken:
        try:
            import fontTools  # noqa: F401
            _hint = ""
        except ImportError:
            _hint = " Восстановление по шрифтам требует fontTools: pip install fonttools."
        print(f"  [ВНИМАНИЕ] PDF: текстовый слой нечитаем (неполная карта символов шрифта) "
              f"на страницах {zakresy_stron(broken)}. Этот текст НЕ попадёт в корпус "
              f"и в определение языка.{_hint}")
        for i in broken:
            texts[i], margins[i] = "", None
    # Pojedyncze znaczniki poniżej progu bramki (np. symbol bez mapy): usuwane,
    # nie trafiają do korpusu jako token „cid”.
    _stray = sum(len(ZNACZNIK_CID.findall(t)) for t in texts)
    if _stray:
        texts = [usun_znaczniki(t) for t in texts]
        print(f"  PDF: удалено одиночных нераспознанных символов шрифта (cid): {_stray}.")
    empty = [i for i, t in enumerate(texts) if not t.strip()]
    if empty and total > 0:
        _scans = [i for i in empty if i not in set(broken)]
        if len(_scans) == total:
            print(f"  PDF: ни одна из {total} страниц не содержит извлекаемого текста.")
            print(f"  Предполагается, что это скан. Запуск OCR (языки: {CORPUS_LANGS})...")
        elif _scans:
            print(f"  PDF: страницы без текстового слоя (вероятно, сканы): "
                  f"{', '.join(str(i + 1) for i in _scans)}. "
                  f"Запуск OCR только для них (языки: {CORPUS_LANGS})...")
        if broken:
            print(f"  PDF: страницы с нечитаемым текстовым слоем передаются в OCR "
                  f"(языки: {CORPUS_LANGS}): {zakresy_stron(broken)}.")
        for i, text in _pdf_ocr_pages(path, CORPUS_LANGS, pages=empty).items():
            texts[i] = text
        ocr_ok = [i for i in empty if texts[i].strip()]
        if ocr_ok:
            print(f"  OCR PDF: распознано страниц {len(ocr_ok)} из {len(empty)}.")
    still_empty = [i for i, t in enumerate(texts) if not t.strip()]
    if still_empty:
        print(f"  [ВНИМАНИЕ] Страницы без текста, их содержимого НЕ будет в корпусе: "
              f"{', '.join(str(i + 1) for i in still_empty)}.")
    raw_idx = [i for i, t in enumerate(texts) if t.strip()]
    raw_pages = [texts[i] for i in raw_idx]
    raw_margins = [margins[i] for i in raw_idx]
    skipped = len(still_empty)
    if not raw_pages:
        print("  [ВНИМАНИЕ] OCR не вернул текста ни на одной странице.")
        return []
    # Удаляем повторяющиеся колонтитулы до объединения строк
    cleaned_raw, removed_bp = strip_repeated_headers(raw_pages, margin_lines=raw_margins)
    if removed_bp:
        print(f"  Удалено {len(removed_bp)} повторяющихся колонтитулов:")
        for bp in sorted(removed_bp)[:5]:
            print(f"    - '{bez_znacznikow_wykresow(bp)[:70]}'")   # bez niewidocznych znaczników
        if len(removed_bp) > 5:
            print(f"    ... и ещё {len(removed_bp)-5}")
    # Wspólny moduł `czyszczenie_tekstu` (bliźniak bajt w bajt z Reżyserem):
    # na stronie z liniami — U+F020 i mojibake (jednostka = strona), granice
    # rozstrzeleń z geometrii jako ZNACZNIK_GRANICY; po clean_pdf_text decyzja
    # o sklejeniu rozstrzeleń na całym dokumencie. Przeniesień w PDF moduł nie
    # skleja: dywiz na końcu wiersza łączy clean_pdf_text.
    _alf = alfabety_paczek()
    _sym = _moji = _marked = 0
    _enc = {}
    for _j, _raw in enumerate(cleaned_raw):
        _raw, _n = oznacz_granice(_raw, spaced[raw_idx[_j]])
        _marked += _n
        _raw, _ci = oczysc_strone_pdf(_raw, _alf)
        _sym += _ci["spacja_symbol"]
        _moji += _ci["mojibake_linie"]
        for _k, _v in _ci["kodowania"].items():
            _enc[_k] = _enc.get(_k, 0) + _v
        cleaned_raw[_j] = _raw
    # Применяем финальную очистку
    pages = [p for p in (clean_pdf_text(r) for r in cleaned_raw) if p]
    pages, _roz = scal_rozstrzelone(pages, granica=ZNACZNIK_GRANICY)
    pages = [re.sub(r"\s+", " ", p).strip() for p in pages]
    # Znak zastępczy generatora PDF (■ w miejscu liter spoza WinAnsi, ATA 2.0):
    # rekonstrukcja słownikami języków korpusu — inaczej śmieciowe lematy.
    if any(ZASTEPCZY in p for p in pages):
        from slowniki_jezykow import slownik
        _slow = []
        for _kod in CORPUS_LANGS:
            try:
                _slow.append(slownik(_kod))
            except LookupError as _e:
                print(f"  [ВНИМАНИЕ] PDF: словарь языка {_kod} недоступен ({_e}) — "
                      f"символы-заменители ■ восстанавливаются без него.")
        _kand = litery_spoza_winansi(s.alfabet for s in _slow)
        pages, _zi = rekonstruuj_zastepcze(pages, _slow, _kand)
        print(f"  PDF: генератор PDF заменил буквы вне WinAnsi символом ■ — слов восстановлено "
              f"по словарю: {_zi['odtworzone']}, неоднозначных (■ оставлен): {_zi['niejednoznaczne']}, "
              f"не найдено в словаре: {_zi['nieznane']}, ■ вне слов: {_zi['poza_slowem']}.")
    if _sym:
        print(f"  PDF: символов-пробелов шрифта Symbol (U+F020) заменено обычным пробелом: {_sym}.")
    if _moji:
        print(f"  PDF: исправлена неверная кодировка (mojibake) в строках: {_moji} "
              f"({', '.join(f'{k}: {v}' for k, v in sorted(_enc.items()))}).")
    if any(_roz.values()):
        print(f"  PDF: текст вразрядку (границы слов по положению букв, серий с границами: "
              f"{_marked}) — склеено: {_roz['sklejone']}, оставлено (слова нет в документе): "
              f"{_roz['bez_zmian']}, оставлено (обрывок рядом с другим словом): {_roz['przyklejone']}.")
    print(f"  PDF: {total} страниц, загружено {len(pages)}, пропущено {skipped}.")
    return pages

def load_txt(path, page_size=2000):
    """Загружает текстовый файл и разбивает на псевдостраницы."""
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    # Mojibake („Áèáëèîòåêà”) — wspólny moduł `czyszczenie_tekstu`; jednostka =
    # cały plik, akapity = linie.
    from czyszczenie_tekstu import napraw_mojibake_akapitow
    from shamanic_locale import alfabety_paczek
    _lines, _mi = napraw_mojibake_akapitow(raw.split("\n"), alfabety_paczek())
    if _mi["przekodowane"]:
        raw = "\n".join(_lines)
        print(f"  TXT: исправлена неверная кодировка (mojibake) в строках: {_mi['przekodowane']} "
              f"({', '.join(f'{k}: {v}' for k, v in sorted(_mi['kodowania'].items()))}).")
    pages, text = [], raw.strip()
    # Применяем CUSTOM_PATTERNS
    if CUSTOM_PATTERNS:
        for _cp in CUSTOM_PATTERNS:
            text = re.sub(_cp, "", text)
        # Było r"\\s+" — dosłowny ukośnik + „s”: spacje się nie zwijały,
        # a „C:\s+ścieżka” traciło `\s` (audyt 2026-10-15). `\n` zostaje.
        text = re.sub(r"[ \t]+", " ", text).strip()
    while len(text) > page_size:
        split_at = text.rfind(" ", 0, page_size)
        if split_at == -1:
            split_at = page_size
        pages.append(text[:split_at].strip())
        text = text[split_at:].strip()
    if text:
        pages.append(text)
    print(f"  TXT: разбито на {len(pages)} псевдостраниц (~{page_size} символов каждая).")
    return pages


def _print_text_cleanup(kind, c):
    """Строки отчёта о чистке текста (`czyszczenie_tekstu.oczysc_akapity_docx`)."""
    if c["spacja_symbol"]:
        print(f"  {kind}: символов-пробелов шрифта Symbol (U+F020) заменено обычным пробелом: "
              f"{c['spacja_symbol']}.")
    if c["mojibake_akapity"]:
        print(f"  {kind}: исправлена неверная кодировка (mojibake) в абзацах: {c['mojibake_akapity']}.")
    if c["rozstrzelone_sklejone"] or c["rozstrzelone_bez_zmian"] or c["rozstrzelone_przyklejone"]:
        print(f"  {kind}: текст вразрядку — склеено: {c['rozstrzelone_sklejone']}, "
              f"оставлено (слова нет в документе): {c['rozstrzelone_bez_zmian']}, "
              f"оставлено (обрывок рядом с другим словом): {c['rozstrzelone_przyklejone']}.")
    _h = [c.get(f"przeniesienia_{k}", 0) for k in ("1", "2", "3", "4", "wykluczone")]
    if any(_h):
        print(f"  {kind}: переносы внутри абзацев — склеено: {_h[0] + _h[2]}, "
              f"с сохранением дефиса: {_h[1]}, оставлено: {_h[3]}, не переносы: {_h[4]}.")


def _docx_ocr(obraz, nr, razem):
    """OCR одного изображения из .docx тем же голосованием, что и сканы PDF.
    Нехватка движка или словаря → docx_tresc.OcrNiedostepny: остальные
    изображения пропускаются и перечисляются номерами, текст документа остаётся."""
    import docx_tresc
    try:
        _ocr_plan(CORPUS_LANGS)
    except (RuntimeError, ImportError) as _e:
        raise docx_tresc.OcrNiedostepny(str(_e)) from None
    text, wynik = _ocr_obraz(obraz, CORPUS_LANGS)
    print(f"  OCR: изображение {nr}/{razem} — {len(text.strip())} символов "
          f"(основа: {wynik.baza}, заменено слов: {wynik.zmiany}, добавлено: {wynik.dodane}).")
    return text


def _print_docx_contents(w):
    """Отчёт о таблицах и изображениях .docx: ни одно изображение не пропадает молча."""
    from docx_tresc import zakresy
    if w.tabele:
        print(f"  DOCX: таблиц: {w.tabele}, ячеек с текстом: {w.komorki}.")
    if not w.obrazy:
        return
    print(f"  DOCX: изображений: {w.obrazy} — распознано OCR: {len(w.ocr_ok)}, "
          f"взято из замещающего текста (alt): {len(w.z_alt)}, декоративных: {len(w.dekoracyjne)}.")
    if w.ocr_puste:
        print(f"  [ВНИМАНИЕ] DOCX: OCR не нашёл текста на изображениях: {zakresy(w.ocr_puste)}.")
    if w.bez_ocr:
        print(f"  [ВНИМАНИЕ] DOCX: OCR недоступен, пропущено изображений: {len(w.bez_ocr)} "
              f"(номера: {zakresy(w.bez_ocr)}). Причина выше; исправление: установить "
              f"компоненты OCR из requirements.txt или поправить corpus_languages.")
    for _ext in sorted({e for _, e in w.format}):
        _nums = [n for n, e in w.format if e == _ext]
        print(f"  [ВНИМАНИЕ] DOCX: формат {_ext} не читается, пропущено изображений: "
              f"{len(_nums)} (номера: {zakresy(_nums)}).")
    if w.zewnetrzne:
        print(f"  [ВНИМАНИЕ] DOCX: изображения по внешней ссылке (не внутри файла) пропущены: "
              f"{zakresy(w.zewnetrzne)}.")
    for _nr, _msg in w.bledy:
        print(f"  [ВНИМАНИЕ] DOCX: ошибка чтения изображения {_nr}: {_msg}")


def load_docx(path, page_size=2000):
    """Загружает файл .docx: абзацы, ячейки таблиц и изображения В ПОРЯДКЕ ДОКУМЕНТА.
    Изображение даёт свой замещающий текст (alt), а без него читается OCR
    (docx_tresc.py; до 2026-11-22 таблицы и изображения терялись молча)."""
    try:
        from docx import Document
    except ImportError:
        print("[ВНИМАНИЕ] python-docx не установлен. Выполните: pip install python-docx")
        return []
    doc = Document(path)
    # DOCX zapisany z PDF — wspólny moduł `czyszczenie_tekstu` (bliźniak bajt
    # w bajt z Reżyserem): U+F020 → spacja, mojibake („Áèáëèîòåêà”),
    # rozstrzelenia („у с т о й ч и в о е”), przeniesienia „по- священного”
    # (reguły 1–4; zawieszony łącznik „двух- и трёх…”, myślniki
    # i „по-английски” zostają). Liczba akapitów się nie zmienia.
    # `docx_tresc.tresc_docx` czyści tak tekst dokumentu (akapity, komórki, alt),
    # tekstu z OCR — nie.
    import docx_tresc
    _w = docx_tresc.tresc_docx(doc, ocr=_docx_ocr)
    _print_text_cleanup("DOCX", _w.czyszczenie)
    _print_docx_contents(_w)
    raw = "  ".join(p for p in _w.akapity if p.strip())
    raw = re.sub(r"\s+", " ", raw).strip()
    # Применяем CUSTOM_PATTERNS (если определены)
    if 'CUSTOM_PATTERNS' in globals():
        for pat in CUSTOM_PATTERNS:
            raw = re.sub(pat, "", raw)
    pages, text = [], raw
    while len(text) > page_size:
        split_at = text.rfind(" ", 0, page_size)
        if split_at == -1:
            split_at = page_size
        pages.append(text[:split_at].strip())
        text = text[split_at:].strip()
    if text:
        pages.append(text)
    print(f"  DOCX: извлечено {len(raw)} символов, "
          f"разбито на {len(pages)} псевдостраниц (~{page_size} символов каждая).")
    return pages

# ============================================================
# Стоп-фразы для отсечения блоков «Похожие статьи» / «Read also» и т.п.
# Списки по языкам — поле `stopfrazy_powiazane` в
# dictionaries/<kod>/podstawy.yaml; здесь объединение всех языков.
# ============================================================
from shamanic_locale import nav_rdzenie, nav_slowa, stopfrazy_powiazane

RELATED_ARTICLES_STOPWORDS = stopfrazy_powiazane()
# Stop-fraza musi być CAŁYM tekstem elementu (po zdjęciu „:”, „»”, „…” z końca).
# Do 2026-10-15 wystarczało, że element ją ZAWIERA, i to w każdym <div>/<section>:
# wrapper z całym artykułem pasował pierwszy i artykuł znikał w całości, a zdanie
# „Lekarze polecamy…”, „Мы рекомендуем…”, „lue myös toinen luku” ucinało resztę
# tekstu (audyt, 14 przypadków w 6 językach). Dlatego też zniknęły prefiksy
# „więcej z” i „more from” — przy dopasowaniu całego tekstu były martwe.
_RELATED_SET = frozenset(RELATED_ARTICLES_STOPWORDS)
_RELATED_TAGS = ["h2", "h3", "h4", "h5", "h6", "p", "strong", "b", "span", "li"]

# Klasy/id elementów-śmieci wewnątrz treści — dopasowanie po TOKENACH, nie po
# podciągu: „share” trafiało w „shared-content”, „widget” w „widget_text”,
# „sidebar” w „content-with-sidebar” i usuwało wrapper artykułu.
# Pola `nav_slowa` / `nav_rdzenie` podstaw, suma wszystkich języków: klasy
# CSS bywają angielskie niezależnie od języka treści.
_NAV_INNER_WORDS = nav_slowa()
_NAV_INNER_STEMS = nav_rdzenie()   # tylko jako POCZĄTEK tokenu

_STRIP_TAGS = ["script", "style", "nav", "header", "footer", "aside",
               "noscript", "form", "button", "iframe", "figure"]


def _norm_related(text):
    t = re.sub(r"\s+", " ", text).strip().lower()
    return re.sub(r"[\s:»›→>…]+$", "", t)


def _cut_related_blocks(root):
    """Odcina blok „Zobacz też” / „Читайте также”: nagłówek i wszystko PO nim.

    Kandydatem jest wyłącznie krótki element, którego CAŁY tekst to stop-fraza.
    Wspinamy się do rodzica, dopóki ma ten sam tekst (`<p><strong>Czytaj też
    </strong></p><ul>…` tnie od akapitu), ale nigdy do `root`. Wszystkie
    trafienia od końca — nie `break` po pierwszym.
    """
    hits = [h for h in root.find_all(_RELATED_TAGS)
            if _norm_related(h.get_text()) in _RELATED_SET]
    for hdr in reversed(hits):
        if hdr.parent is None:            # usunięty razem z wcześniejszym rodzeństwem
            continue
        key = _norm_related(hdr.get_text())
        while (hdr.parent is not None and hdr.parent is not root
               and _norm_related(hdr.parent.get_text()) == key):
            hdr = hdr.parent
        for sib in list(hdr.next_siblings):
            if hasattr(sib, "decompose"):
                sib.decompose()
            else:
                sib.extract()
        hdr.decompose()


def _strip_nav_inner(main):
    """Usuwa w `main` elementy o klasie/id z `_NAV_INNER_WORDS` (po tokenach).

    Bezpiecznik: element z co najmniej połową tekstu `main` to wrapper
    artykułu, nie widżet — zostaje.
    """
    total = len(main.get_text(" ", strip=True)) or 1
    for el in list(main.find_all(True)):
        if el.parent is None or not el.attrs:
            continue
        toks = re.split(r"[\s_\-]+", (" ".join(el.get("class") or []) + " "
                                     + (el.get("id") or "")).lower())
        if not any(t in _NAV_INNER_WORDS or t.startswith(_NAV_INNER_STEMS)
                   for t in toks if t):
            continue
        if len(el.get_text(" ", strip=True)) >= 0.5 * total:
            continue
        el.decompose()


def _split_pages(text, page_size):
    pages = []
    while len(text) > page_size:
        split_at = text.rfind(" ", 0, page_size)
        if split_at == -1:
            split_at = page_size
        pages.append(text[:split_at].strip())
        text = text[split_at:].strip()
    if text:
        pages.append(text)
    return pages


def _extract_web_text(html):
    """Wspólny ekstraktor strony WWW dla `load_html` i `load_url`.

    Do 2026-10-15 oba loadery miały kroki 1–5 skopiowane 1:1 (różniły się
    dwoma komentarzami) — poprawka w jednym nie trafiała do drugiego.
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    # 1. Tagi, które nigdy nie zawierają treści artykułu
    for tag in soup(_STRIP_TAGS):
        tag.decompose()
    # 2. Główny kontener treści
    main = (soup.find("main") or soup.find("article")
            or soup.find(id=lambda x: x and any(k in x.lower()
                         for k in ("content", "article", "main", "post", "story")))
            or soup.find(class_=lambda x: x and any(k in " ".join(x).lower()
                         for k in ("entry-content", "post-content", "article-body",
                                   "article-content", "story-body"))))
    if not main:
        candidates = [el for el in soup.find_all(["article", "section", "div"])
                      if el.get_text(strip=True)]
        main = max(candidates, key=lambda e: len(e.get_text()), default=soup)
    # 3. Widżety WEWNĄTRZ main (nie globalnie)
    _strip_nav_inner(main)
    # 4. Blok „Podobne artykuły” / „Related articles”
    _cut_related_blocks(main)
    # 5. Tekst, normalizacja, artefakty scrapingu
    raw_text = re.sub(r"\s+", " ", main.get_text(separator=" ", strip=True)).strip()
    return clean_web_article_start(raw_text)


def load_html(path, page_size=2000):
    """Извлекает основной текст из HTML-файла через BeautifulSoup.
    Удаляет: навигацию, шапку/подвал, боковые панели, блоки
    «Похожие статьи» / «Podobne artykuły» и тексты ссылок-меню.
    """
    try:
        from bs4 import BeautifulSoup  # noqa: F401
    except ImportError:
        print("[ВНИМАНИЕ] beautifulsoup4 не установлен: pip install beautifulsoup4 lxml")
        return []
    with open(path, encoding="utf-8", errors="replace") as _f:
        html = _f.read()
    raw_text = _extract_web_text(html)
    if not raw_text:
        print("[ВНИМАНИЕ] Не удалось извлечь текст из HTML.")
        return []
    pages = _split_pages(raw_text, page_size)
    print(f"  HTML: извлечено {len(raw_text)} символов, "
          f"разбито на {len(pages)} псевдостраниц (~{page_size} символов каждая).")
    return pages


def load_url(url, page_size=2000):
    """Загружает страницу по URL, очищает её BeautifulSoup и разбивает на псевдостраницы.
    Применяет ту же логику очистки, что и load_html():
    удаляет навигацию, боковые панели, блоки «Похожие статьи» и тексты ссылок-меню.
    """
    try:
        import requests
        from bs4 import BeautifulSoup  # noqa: F401
    except ImportError:
        print("[ВНИМАНИЕ] requests или beautifulsoup4 не установлены.")
        print("  pip install requests beautifulsoup4 lxml")
        return []
    print(f"  Загрузка URL: {url}")
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding
        html = resp.text
    except Exception as _e:
        print(f"[ВНИМАНИЕ] Не удалось загрузить URL: {_e}")
        return []
    raw_text = _extract_web_text(html)
    if not raw_text:
        print("[ВНИМАНИЕ] Не удалось извлечь текст со страницы.")
        return []
    pages = _split_pages(raw_text, page_size)
    print(f"  URL: извлечено {len(raw_text)} символов, "
          f"разбито на {len(pages)} псевдостраниц (~{page_size} символов каждая).")
    return pages


# Markdown: rozszerzenia python-markdown. `fenced_code` zamienia ``` na <pre>,
# które wypada z korpusu (kod to nie proza: lematy `def`, `print`, ścieżki);
# `tables` — bez niego wiersz tabeli zostaje tekstem z „|”; `sane_lists` —
# mniej fałszywych <ol> z liczb w zdaniach; `footnotes`, `def_list`, `abbr` —
# bez nich w korpusie zostawały `[^1]`, „: definicja” i „*[SKRÓT]: …”.
# Ta sama lista co `core_markdown.ROZSZERZENIA` w Reżyserze POZA `nl2br`
# (pojedyncze złamanie linii nie ma tu znaczenia — tekst i tak jest spłaszczany).
MD_EXTENSIONS = ["sane_lists", "tables", "fenced_code", "footnotes", "def_list", "abbr"]
# Front matter YAML na samym początku pliku (Jekyll/Hugo/Obsidian).
_MD_FRONT_MATTER = re.compile(r"\A---[ \t]*\r?\n.*?\r?\n---[ \t]*\r?\n", re.S)


def load_md(path, page_size=2000):
    """Markdown → HTML → текст в режиме ДОКУМЕНТА.

    To nie jest strona WWW: bez szukania <main>, bez `_strip_nav_inner`
    i bez `clean_web_article_start` (liczniki zdjęć i podwojone tytuły to
    artefakty scrapingu). Zostaje odcięcie bloku „Zobacz też”, bo bywa
    w notatkach i README. Bloki kodu (``` / wcięte) wypadają w całości,
    tekst linków zostaje, adresy URL nie.
    """
    try:
        import markdown
        from bs4 import BeautifulSoup
    except ImportError:
        print("[ВНИМАНИЕ] markdown или beautifulsoup4 не установлены: "
              "pip install markdown beautifulsoup4")
        return []
    with open(path, encoding="utf-8", errors="replace") as _f:
        raw = _f.read()
    raw = _MD_FRONT_MATTER.sub("", raw, count=1)
    html = markdown.markdown(raw, extensions=MD_EXTENSIONS, output_format="html5")
    soup = BeautifulSoup(html, "html.parser")
    _n_code = len(soup.find_all("pre"))
    for tag in soup(["pre", "script", "style"]):
        tag.decompose()
    # Odnośniki przypisów: numer w tekście i strzałka powrotu „↩” to nie proza.
    for tag in soup.find_all("a", class_=["footnote-ref", "footnote-backref"]):
        tag.decompose()
    # Blok przypisów python-markdown dokleja na KOŃCU dokumentu, czyli za
    # „## Zobacz też” — cięcie zabierało go razem z blokiem (zmierzone).
    _footnotes = soup.find("div", class_="footnote")
    if _footnotes is not None:
        _footnotes.extract()
    _cut_related_blocks(soup)
    if _footnotes is not None:
        soup.append(_footnotes)
    raw_text = re.sub(r"\s+", " ", soup.get_text(separator=" ", strip=True)).strip()
    if not raw_text:
        print("[ВНИМАНИЕ] Не удалось извлечь текст из Markdown.")
        return []
    pages = _split_pages(raw_text, page_size)
    print(f"  MD: извлечено {len(raw_text)} символов (блоков кода пропущено: {_n_code}), "
          f"разбито на {len(pages)} псевдостраниц (~{page_size} символов каждая).")
    return pages

FALLBACK_CORPUS = [
    """I have a significant problem with Word. I am typing a document and suddenly
    it will turn to gibberish, not readable or recognisable, just random symbols.
    One time I was able to get it back but I have just lost an important document.
    When I preview the document in search I can read what I wrote, but as soon as
    I open it it's gone. Please help, I am a writer and can't risk losing my work!""",
    """Machine learning is a field of artificial intelligence that uses statistical
    techniques to give computer systems the ability to learn from data.""",
    """The document processing system encountered multiple errors during the batch
    operation. Files were corrupted and recovery attempts failed.""",
]

corpus = []
if SOURCE_FILE and SOURCE_FILE.startswith(("http://", "https://")):
    corpus = load_url(SOURCE_FILE)
elif SOURCE_FILE and os.path.isfile(SOURCE_FILE):
    ext = os.path.splitext(SOURCE_FILE)[1].lower()
    print(f"Загрузка из файла: {SOURCE_FILE}")
    if ext == ".pdf":
        corpus = load_pdf(SOURCE_FILE)
    elif ext in (".txt", ".text"):
        corpus = load_txt(SOURCE_FILE)
    elif ext == ".docx":
        corpus = load_docx(SOURCE_FILE)
    elif ext in (".html", ".htm"):
        corpus = load_html(SOURCE_FILE)
    elif ext in (".md", ".markdown"):
        corpus = load_md(SOURCE_FILE)
    elif ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"):
        corpus = load_image(SOURCE_FILE)
    else:
        print(f"[ВНИМАНИЕ] Неизвестное расширение: {ext}. "
              f"Поддерживаются: .pdf, .txt, .md, .html, .docx, .png, .jpg, .jpeg, .tif, .tiff, .bmp, .webp")
elif SOURCE_FILE:
    print(f"[ВНИМАНИЕ] Источник не найден: {SOURCE_FILE!r}. Используется встроенный пример.")

_used_fallback = False
if not corpus:
    print("Используется встроенный корпус-пример (3 документа).")
    corpus = FALLBACK_CORPUS
    _used_fallback = True

corpus = [c for c in corpus if c.strip()]
# Etykiety wykresów PDF (load_pdf) niosą niewidoczne znaczniki: podgląd je
# pokazuje bez znaczników, NLP dostaje tekst bez etykiet (rozdziel_wykresy).
from naprawa_zrodel import bez_znacznikow_wykresow, rozdziel_wykresy, POCZATEK_WYKRESU
_N = len(corpus)
print(f"\nКорпус готов: {_N} документ(ов).")
_show = min(5, _N)
for i in range(_show):
    _prev = bez_znacznikow_wykresow(corpus[i]).strip().replace("\n", " ")[:80]
    print(f"  [{i+1}] {_prev}...")
if _N > _show:
    print(f"  ... и ещё {_N - _show} документ(ов) (показаны первые {_show})")

# ============================================================
# PROJECT_DIR: подкаталог в export_results, индивидуальный для источника.
# Для файлов: имя файла без расширения. Для URL: домена_слаг.
# Для встроенного корпуса: _default. Внутри подкаталога файлы перезаписываются.
# ============================================================
def _slugify(s, maxlen=80):
    s = re.sub(r"[^\w\-\.]+", "_", s, flags=re.UNICODE).strip("._")
    return s[:maxlen] or "_default"

if not SOURCE_FILE or not corpus or _used_fallback:
    PROJECT_NAME = "_default"
elif SOURCE_FILE.startswith(("http://", "https://")):
    _u = urlparse(SOURCE_FILE)
    _host = (_u.netloc or "url").replace("www.", "")
    _path = _u.path.strip("/").replace("/", "_") or "index"
    PROJECT_NAME = _slugify(f"{_host}_{_path}")
else:
    PROJECT_NAME = _slugify(Path(SOURCE_FILE).stem)

PROJECT_DIR = Path("export_results") / PROJECT_NAME
PROJECT_DIR.mkdir(parents=True, exist_ok=True)
print(f"\nКаталог проекта: {PROJECT_DIR}")

# %% [markdown] id="md_langdet" tags=["md_langdet"]
# ## 1) Языки текста (словари вместо статистического детектора)
#
# Языки текста задаёт пользователь — ключ `corpus_languages` в `config.json` (прежнее имя `ocr_languages` тоже читается). По тем же языкам работает OCR сканов, а здесь их словари решают, на каком языке **каждое слово**:
#
# - **Основной язык** `LANG` — язык, словарь которого знает больше всего слов корпуса (доля печатается ниже). Он выбирает модель spaCy для основного конвейера.
# - Словари: векторы spaCy (конечный список форм), `omorfi` для финского, BÍN (`islenska`) для исландского — модуль `slowniki_jezykow.py`, общий с голосованием OCR.
# - Разметку слов и иноязычных отрезков делает ячейка токенизации (`odcinki_jezykowe.py`): там же каждый отрезок получает свою модель spaCy — без повторной сегментации.
#
# Почему не статистический детектор (до ATA 2.0 — `lingua`): на 20 финских транскриптах (6047 предложений) он без защитных эвристик давал 127 ложных иноязычных предложений, а с эвристиками пропускал все английские цитаты. Словари объявленных языков находят цитаты и польские фамилии без ложных срабатываний.
#
# > Один язык в `corpus_languages` — словари не загружаются: размечаются только слова другого письма (например, кириллица в латинском тексте).

# %% id="cell_langdet" tags=["cell_langdet"]
# ============================================================
# Языки текста: словари языков из corpus_languages. Основной язык
# LANG — язык, словарь которого знает больше всего слов корпуса;
# остальные размечаются на уровне слов в ячейке токенизации.
# ============================================================
import warnings
warnings.filterwarnings("ignore")
from collections import Counter

import odcinki_jezykowe
import slowniki_jezykow
from shamanic_locale import PODSTAWY

LANG_NAMES = {_k: _p["nazwa_ru"] for _k, _p in PODSTAWY.items()}
SUPPORTED_LANGS = set(LANG_NAMES.keys())
# Алфавиты ВСЕХ основ: письмо (кириллица) размечается и вне corpus_languages.
ALFABETY = {_k: _p["alfabet"] for _k, _p in PODSTAWY.items()}

print("--- Языки текста (словари) ---")
_nieznane = [_k for _k in CORPUS_LANGS if _k not in SUPPORTED_LANGS]
if _nieznane:
    raise ValueError(
        f"corpus_languages: неизвестные коды {_nieznane}. "
        f"Доступные языки: {sorted(SUPPORTED_LANGS)} (каталоги dictionaries/<код>/).")
CORPUS_LANGS = list(dict.fromkeys(CORPUS_LANGS))

if len(CORPUS_LANGS) == 1:
    LANG = CORPUS_LANGS[0]
    SLOWNIKI = {LANG: slowniki_jezykow.slownik_pelny(LANG)}
    print(f"Указан один язык текста — {LANG_NAMES[LANG]} ({LANG}); словари не загружаются.")
    print("  Иноязычные вставки на латинице не размечаются: добавьте их язык в corpus_languages.")
else:
    SLOWNIKI, _bledy = {}, []
    for _k in CORPUS_LANGS:
        try:
            SLOWNIKI[_k] = slowniki_jezykow.slownik(_k)
        except LookupError as _e:
            _bledy.append(f"  {_k} ({LANG_NAMES[_k]}): {_e}")
    if _bledy:
        raise RuntimeError(
            "Словари языков текста недоступны — без них разметка языка невозможна:\n"
            + "\n".join(_bledy)
            + "\nУстановите компоненты или уберите язык из corpus_languages в config.json.")
    for _k, _s in SLOWNIKI.items():
        print(f"  [{_k}] словарь: {_s.zrodlo}")
        if _s.uznanie:
            print(f"       {_s.uznanie}")
    LANG, _udzialy = odcinki_jezykowe.wybierz_baze([rozdziel_wykresy(_c)[0] for _c in corpus], SLOWNIKI)
    print("\nДоля слов корпуса, известных словарю языка:")
    for _k, _u in sorted(_udzialy.items(), key=lambda x: -x[1]):
        print(f"  {LANG_NAMES[_k]} ({_k}): {_u:.1%}")

print(f"\n[РЕЗУЛЬТАТ] Основной язык: {LANG_NAMES.get(LANG, LANG)} ({LANG})")

# %% [markdown] id="md_model" tags=["md_model"]
# ## 2) Загрузка языковой модели spaCy (LRU-кэш)
#
# spaCy использует предобученные модели для токенизации, лемматизации, POS-теггинга и NER.  
# Модель преобладающего языка выбирается **автоматически** по результату предыдущей ячейки.
#
# **Динамическая загрузка моделей:**
#
# - Загрузка инкапсулирована в функцию `get_nlp(lang)`, обёрнутую `functools.lru_cache(maxsize=2)`.
# - В оперативной памяти одновременно держатся не более **двух** моделей spaCy. При запросе третьего языка наименее давно использованная модель вытесняется и освобождается сборщиком мусора — это предотвращает накопление памяти на мультиязычных корпусах.
# - Старое имя `load_nlp_model` сохранено как алиас для обратной совместимости.
#
# > **Важно:** Ноутбук использует модели версии **Large (lg)**, которые содержат полные словарные векторы. Это значительно улучшает качество тематизации (KMeans) и распознавания именованных сущностей (NER) по сравнению с версиями `sm`.
#
# | Язык | Код | Модель |
# |------|-----|--------|
# | English | `en` | `en_core_web_lg` |
# | Polish | `pl` | `pl_core_news_lg` |
# | Russian | `ru` | `ru_core_news_lg` |
# | Italian | `it` | `it_core_news_lg` |
# | German | `de` | `de_core_news_lg` |
# | Spanish | `es` | `es_core_news_lg` |
# | French | `fr` | `fr_core_news_lg` |
# | Finnish | `fi` | `fi_core_news_lg` |
# | Icelandic | `is` | `spacy.blank("is")` + IceBERT (векторы) + icelandic-ner-bert (NER, MIM-GOLD-NER) |
#
# Если модель не установлена, ноутбук использует базовый токенизатор (`spacy.blank`) и сообщает команду для установки.
#
# **Опционально для финского:** если установлен пакет `omorfi` (чистый Python, зависимость `pyhfst`) и скачаны автоматы (`omorfi-download`), к модели добавляется компонент `omorfi_lemmas` — словарные леммы и UD-морфология существенно точнее статистического лемматизатора `fi_core_news_lg`. Кандидаты фильтруются по UPOS от теггера spaCy. Без пакета или автоматов поведение прежнее.

# %% id="cell_model" tags=["cell_model"]
import spacy
from functools import lru_cache

# Поле `spacy` основ; null (исландский) = spaCy не имеет модели —
# для него ниже строится конвейер Hugging Face.
from shamanic_locale import PODSTAWY

MODEL_BY_LANG = {_k: _p["spacy"] for _k, _p in PODSTAWY.items() if _p["spacy"]}

# Hugging Face модели для исландского (нет в spaCy):
# До 2026-11-13 здесь стояли mideind/IceBERT-base и mideind/icelandic-ner-MIM-GOLD-22 —
# таких репозиториев на Hugging Face нет (HTTP 401), поэтому исландский конвейер
# с первого коммита работал без векторов и NER. Существование идентификаторов
# проверяет audyt_zaleznosci.py, а загрузку — run_all.py --warnings-as-errors.
HF_IS_VECTORS = "mideind/IceBERT"
HF_IS_NER = "grammatek/icelandic-ner-bert"
# Метки модели (Person, Location, …) -> метки spaCy, которые читает остальной
# конвейер (shamanic_pipeline ищет PER/LOC/ORG).
IS_NER_LABELS = {"Person": "PER", "Location": "LOC", "Organization": "ORG",
                 "Miscellaneous": "MISC", "Date": "DATE", "Time": "TIME",
                 "Money": "MONEY", "Percent": "PERCENT"}
# Сбои исландского NER по фрагментам (имя исключения); итог печатает cell_ner.
IS_NER_FAILURES = []


def _silence_hf_progress():
    """Тушит progress bars и предупреждения transformers/torch для чистого stdout."""
    import os
    os.environ["TRANSFORMERS_VERBOSITY"] = "error"
    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    try:
        import transformers
        transformers.logging.set_verbosity_error()
        transformers.utils.logging.disable_progress_bar()
    except Exception:
        pass
    # Предупреждение «unauthenticated requests to the HF Hub» приходит из
    # huggingface_hub, а не из transformers, поэтому глушим его отдельно.
    try:
        from huggingface_hub.utils import logging as _hf_logging
        _hf_logging.set_verbosity_error()
    except Exception:
        pass


def _build_icelandic_pipeline(blank_nlp):
    """Добавляет к spacy.blank('is') два HF-компонента: векторы (IceBERT) и NER.
    Если transformers/torch недоступны или сеть упала — возвращает blank без изменений.
    """
    try:
        _silence_hf_progress()
        from transformers import AutoTokenizer, AutoModel, pipeline
        import torch
        import numpy as np
        from spacy.language import Language
        from spacy.tokens import Doc
    except ImportError as _e:
        print(f"[ВНИМАНИЕ] transformers/torch недоступны: {_e}")
        print("  Пайплайн для исландского остаётся базовым (без NER и векторов).")
        return blank_nlp

    # --- Векторы через IceBERT ---
    try:
        print(f"  Загрузка эмбеддингов: {HF_IS_VECTORS} ...")
        _is_tok = AutoTokenizer.from_pretrained(HF_IS_VECTORS)
        _is_mdl = AutoModel.from_pretrained(HF_IS_VECTORS)
        _is_mdl.eval()

        def _is_embed(text):
            text = (text or "").strip()
            if not text:
                return np.zeros(_is_mdl.config.hidden_size, dtype=np.float32)
            with torch.no_grad():
                enc = _is_tok(text, return_tensors="pt", truncation=True, max_length=512)
                out = _is_mdl(**enc)
                mask = enc["attention_mask"].unsqueeze(-1).float()
                pooled = (out.last_hidden_state * mask).sum(1) / mask.sum(1).clamp(min=1)
            return pooled.squeeze(0).cpu().numpy().astype(np.float32)

        @Language.component("icebert_vectors")
        def _icebert_vectors_pipe(doc):
            vec = _is_embed(doc.text)
            doc.user_hooks["vector"] = lambda d: vec
            doc.user_hooks["has_vector"] = lambda d: True
            doc.user_hooks["vector_norm"] = lambda d: float((vec * vec).sum() ** 0.5)
            return doc

        if "icebert_vectors" not in blank_nlp.pipe_names:
            blank_nlp.add_pipe("icebert_vectors", last=True)
        print(f"  [OK] Эмбеддинги активны: размерность {_is_mdl.config.hidden_size}.")
    except Exception as _e:
        print(f"[ВНИМАНИЕ] Не удалось загрузить {HF_IS_VECTORS}: {_e}")
        print("  Тематизация будет пропущена.")

    # --- NER через icelandic-ner-bert (MIM-GOLD-NER) ---
    try:
        print(f"  Загрузка NER: {HF_IS_NER} ...")
        _is_ner = pipeline(
            "token-classification",
            model=HF_IS_NER,
            # Модель видит не больше 512 подтокенов: без stride длинный текст
            # молча обрезался (на тексте в 1002 подтокена — 123 сущности
            # вместо 247, замер 2026-11-13). stride режет его на
            # перекрывающиеся окна. Явный model_max_length=512 — страховка:
            # на transformers 5.22 токенизатор отдаёт 512 и сам, но версия,
            # где предел не задан, роняла бы длинный абзац внутри модели.
            tokenizer=AutoTokenizer.from_pretrained(HF_IS_NER, model_max_length=512),
            # "first": метка слова по первому подтокену. "simple" резал
            # исландские имена на куски (G, ##uð, ##rú вместо Guðrúnu).
            aggregation_strategy="first",
            stride=128,
        )

        @Language.component("icelandic_ner")
        def _icelandic_ner_pipe(doc):
            from spacy.tokens import Span
            text = doc.text or ""
            if not text.strip():
                return doc
            try:
                # Весь текст: окна stride обрабатывают любую длину. Раньше
                # срез [:5000] оставлял без сущностей всё после 5000 знаков
                # документа (cell_ner получает документ целиком).
                results = _is_ner(text) or []
            except Exception as _e:
                # Не молча: первый сбой — с причиной, итог считает cell_ner.
                if not IS_NER_FAILURES:
                    print(f"[ВНИМАНИЕ] Исландский NER не обработал фрагмент: {_e}")
                IS_NER_FAILURES.append(type(_e).__name__)
                return doc
            spans = []
            for r in results:
                start_c = int(r.get("start", 0))
                end_c = int(r.get("end", 0))
                label = str(r.get("entity_group") or r.get("entity") or "MISC")
                label = IS_NER_LABELS.get(label, label)
                if end_c <= start_c:
                    continue
                span = doc.char_span(start_c, end_c, label=label,
                                      alignment_mode="contract")
                if span is not None:
                    spans.append(span)
            try:
                doc.set_ents(spans)
            except Exception:
                pass
            return doc

        if "icelandic_ner" not in blank_nlp.pipe_names:
            blank_nlp.add_pipe("icelandic_ner", last=True)
        print("  [OK] Исландский NER активен.")
    except Exception as _e:
        print(f"[ВНИМАНИЕ] Не удалось загрузить {HF_IS_NER}: {_e}")
        print("  NER для исландского будет пропущен.")

    return blank_nlp


# --- Опциональное уточнение финской морфологии через omorfi ---
# Пакет omorfi (с версии 0.10 — чистый Python, зависимость pyhfst) даёт
# словарную морфологию заметно точнее статистического лемматизатора
# fi_core_news_lg (kytköksistä -> kytkös, а не *kytköknen; pistät -> pistää,
# а не *pisttää). Автоматы скачиваются отдельно командой omorfi-download
# (файлы *.hfst в корне проекта; они в .gitignore). Отсутствие пакета или
# автоматов = мягкая деградация к стандартному поведению spaCy.
OMORFI_MODEL_CANDIDATES = [
    "omorfi_recased.describe.hfst",  # с анализом регистра: Mitä -> mikä
    "omorfi.describe.hfst",
]


def _build_finnish_omorfi(fi_nlp):
    """Добавляет к финской модели компонент omorfi_lemmas: леммы и UD-морфология
    из словарного анализатора omorfi. В pip-версии omorfi нет контекстной
    дизамбигуации, поэтому кандидаты фильтруются по UPOS от теггера spaCy;
    если ни один анализ не совпал по UPOS, остаётся значение spaCy — кроме
    случая, когда лемма spaCy не словарная, а omorfi однозначен (тогда
    берётся только лемма omorfi; для INTJ — лемма повелительных глагольных
    анализов, напр. Oota -> oottaa). Любая проблема (нет пакета, нет автоматов, ошибка
    загрузки) — возврат модели без изменений.
    """
    from pathlib import Path
    try:
        from omorfi.omorfi import Omorfi
        from omorfi.token import Token as _OmorfiToken
    except ImportError:
        print("[ИНФО] Пакет omorfi не установлен — леммы финского остаются от spaCy.")
        print("  Для повышения качества: pip install omorfi, затем omorfi-download")
        return fi_nlp

    _model_path = next((p for p in OMORFI_MODEL_CANDIDATES if Path(p).exists()), None)
    if _model_path is None:
        print("[ИНФО] Автоматы omorfi (*.hfst) не найдены — леммы финского остаются от spaCy.")
        print("  Скачайте их командой: omorfi-download")
        return fi_nlp

    try:
        _om = Omorfi()
        _om.load_analyser(_model_path)
    except Exception as _e:
        print(f"[ВНИМАНИЕ] Не удалось загрузить {_model_path}: {_e}")
        print("  Леммы финского остаются от spaCy.")
        return fi_nlp

    from spacy.language import Language

    @lru_cache(maxsize=65536)
    def _om_lookup(surf):
        """Анализы поверхностной формы: кортежи (UPOS, лемма, UD-feats, вес)."""
        tok = _OmorfiToken.fromsurf(surf)
        _om.analyse(tok)
        out = []
        for a in tok.analyses:
            parts = a.get_lemmas()
            if not parts:
                continue
            lemma = "".join(parts)
            # Сложные слова приходят по частям (trolli+tehdas,
            # epä-+järjestelmällisyys); внутренний дефис убираем, только
            # если его нет в самой поверхностной форме (Itä-Suomi остаётся).
            if "-" in lemma and "-" not in surf:
                lemma = lemma.replace("-", "")
            feats = a.get_ufeats() or {}
            out.append((a.get_upos(), lemma,
                        "|".join(f"{k}={v}" for k, v in sorted(feats.items())),
                        a.weight))
        return tuple(out)

    def _om_mixed_case(a, surf):
        """Лемма с прописными буквами в середине (LuuLIT, maniEK) у словоформы
        без них — артефакт recased-автомата, а не аббревиатура вроде PiS."""
        return any(c.isupper() for c in a[1][1:]) and not any(c.isupper() for c in surf[1:])

    def _om_plausible(surf):
        """Анализы без двух артефактов автомата: «догадки» для незнакомых слов
        (X, лемма = сама строка, вес inf) и выдуманные recased-автоматом
        прописные леммы у строчной словоформы (luulit -> Luul, luuLIT)."""
        low = surf.islower()
        return [a for a in _om_lookup(surf)
                if a[3] != float("inf") and not (low and a[1] != a[1].lower())]

    def _om_is_base(lemma):
        """True, если omorfi признаёт строку леммой (словарной формой) самой себя."""
        if not lemma:
            return False
        return any(a[1].lower() == lemma.lower() for a in _om_plausible(lemma))

    def _omorfi_lemmas_pipe(doc):
        for tok in doc:
            if not tok.is_alpha:
                continue
            matching = [a for a in _om_lookup(tok.text)
                        if a[0] == tok.pos_ and not _om_mixed_case(a, tok.text)]
            if not matching:
                # Словарь и теггер разошлись. По умолчанию доверяем spaCy, но
                # только пока его лемма — настоящая словарная форма. Если omorfi
                # её не знает как лемму (мусор вроде *blokka* <- blokkaa) или она
                # совпадает с непрошедшей лемматизацию словоформой (luulit), а ВСЕ
                # правдоподобные анализы omorfi дают ОДНУ лемму — берём её. Только
                # лемму: UPOS и морфологию оставляем от spaCy. Имена не трогаем
                # (PROPN или прописная буква не в начале предложения): omorfi их
                # часто не знает и подставил бы нарицательное (Tuskia -> *tuska*).
                is_name = tok.pos_ == "PROPN" or (tok.text[:1].isupper() and not tok.is_sent_start)
                if tok.pos_ == "INTJ" and not _om_is_base(tok.lemma_):
                    # Повелительное наклонение в роли междометия (Oota, Odota,
                    # Katso): у omorfi нет INTJ, а NOUN-омоним (oo, партитив
                    # oota) мешает правилу «одна лемма» ниже. Берём лемму
                    # словарных глагольных анализов с Mood=Imp, если она одна.
                    imp_lemmas = {a[1] for a in _om_plausible(tok.text)
                                  if a[0] == "VERB" and a[3] == 0 and "Mood=Imp" in a[2]}
                    if len(imp_lemmas) == 1:
                        tok.lemma_ = next(iter(imp_lemmas))
                        continue
                if not is_name and not _om_is_base(tok.lemma_):
                    # Только словарные анализы (вес 0): угаданные omorfi сложные
                    # слова (tapa+maa, sama+laki) имеют вес >= 10.
                    om_lemmas = {a[1] for a in _om_plausible(tok.text) if a[3] == 0}
                    # Прописная лемма = имя (Valensa -> *Vale* в начале предложения).
                    if len(om_lemmas) == 1 and not next(iter(om_lemmas))[:1].isupper():
                        tok.lemma_ = next(iter(om_lemmas))
                continue
            _upos, lemma, feats, _w = min(matching, key=lambda a: a[3])
            tok.lemma_ = lemma
            if feats:
                try:
                    tok.set_morph(feats)
                except Exception:
                    pass  # экзотическая фича вне схемы UD — лемму уже записали
        return doc

    # Повторный запуск ячейки: spaCy сверяет исходники дубликата через
    # inspect.getsource и вне IPython может упасть с OSError («could not
    # get source code»), поэтому проверяем реестр заранее, а не через except.
    if not Language.has_factory("omorfi_lemmas"):
        Language.component("omorfi_lemmas", func=_omorfi_lemmas_pipe)

    if "omorfi_lemmas" not in fi_nlp.pipe_names:
        fi_nlp.add_pipe("omorfi_lemmas", last=True)
    print(f"  [OK] Подключён omorfi: {_model_path} — леммы и морфология финского уточняются.")
    return fi_nlp


def _pusty_potok(lang):
    """spacy.blank для языка + sentencizer; язык, которого spaCy не знает
    (ImportError E048, напр. se, kl), получает многоязычный «xx»."""
    try:
        nlp_ = spacy.blank(lang)
    except ImportError:
        print(f"[ВНИМАНИЕ] spaCy не знает язык '{lang}' — используется многоязычный spacy.blank('xx').")
        nlp_ = spacy.blank("xx")
    if "sentencizer" not in nlp_.pipe_names:
        nlp_.add_pipe("sentencizer")
    return nlp_


def _load_nlp_model_uncached(lang):
    """Внутренняя загрузка модели без кэша. Используется через get_nlp()."""
    if lang == "is":
        print("[ИНФО] Для исландского spaCy не имеет полной модели — подключаем модели Hugging Face.")
        nlp_ = spacy.blank("is")
        if "sentencizer" not in nlp_.pipe_names:
            nlp_.add_pipe("sentencizer")
        nlp_ = _build_icelandic_pipeline(nlp_)
        return nlp_
    if lang in SUPPORTED_LANGS and lang not in MODEL_BY_LANG:
        # Язык из основ с `spacy: null` и без собственной ветки (как is выше):
        # пустой конвейер своего языка, а не английская модель.
        print(f"[ВНИМАНИЕ] Для языка '{lang}' нет модели spaCy (spacy: null в podstawy.yaml) — используется spacy.blank.")
        return _pusty_potok(lang)
    model_name = MODEL_BY_LANG.get(lang, "en_core_web_lg")
    try:
        nlp_ = spacy.load(model_name)
        print(f"[OK] Загружена модель spaCy: {model_name}")
        if lang == "fi":
            nlp_ = _build_finnish_omorfi(nlp_)
        print(f"     Компоненты конвейера: {nlp_.pipe_names}")
        return nlp_
    except OSError:
        print(f"[ВНИМАНИЕ] Модель '{model_name}' не установлена.")
        print(f"  Установите: python -m spacy download {model_name}")
        print(f"  Доступные модели (lg):")
        for _m in MODEL_BY_LANG.values():
            print(f"    python -m spacy download {_m}")
        return _pusty_potok(lang if lang in SUPPORTED_LANGS else "en")


@lru_cache(maxsize=2)
def get_nlp(lang):
    """Возвращает spaCy-модель для запрошенного языка.

    LRU-кэш ограничен двумя моделями: при загрузке третьей модели
    наименее давно использованная вытесняется и освобождается сборщиком
    мусора. Это защищает от утечки памяти при обработке мультиязычных
    корпусов, где иначе пришлось бы держать все модели одновременно.
    """
    return _load_nlp_model_uncached(lang)


# Совместимость со старым именем
load_nlp_model = get_nlp


print("--- Загрузка языковой модели ---")
nlp = get_nlp(LANG)
stop_words = nlp.Defaults.stop_words
print(f"\nСписок стоп-слов: {len(stop_words)} записей для {LANG_NAMES.get(LANG, LANG)}")
print(f"[ИНФО] LRU-кэш моделей: maxsize=2. Дополнительные модели "
      f"подгружаются по запросу через get_nlp(lang) и автоматически "
      f"вытесняются, не накапливаясь в RAM.")

# %% [markdown] id="md_pl_corrector" tags=["md_pl_corrector"]
# ## Коррекция текста и нормализация аббревиатур
#
# Автоматически исправляет типичные ошибки оформления во всех поддерживаемых языках.
#
# **Для всех языков:**
# - Повторы слов НЕ удаляются: удвоение бывает нормой языка («чуть чуть», «piano piano», «bardzo bardzo»)
# - Схлопывание множественных пробелов
#
# **Нормализация аббревиатур (польский `pl`):**
# - `m.in`, `m. in`, `m.in,` → `m.in.`; `np.,` → `np.`; `tzw.,` → `tzw.`; `tzn.` — полный набор
# - `tj.`, `itd.`, `itp.` — склейка разбитых аббревиатур
#
# **Нормализация аббревиатур (русский `ru`):**
# - `т. е.` → `т.е.`; `т. д.` → `т.д.`; `и т.д.` → единый вид; и другие
#
# **Нормализация аббревиатур (английский `en`):**
# - `e. g.` → `e.g.`; `e.g,` → `e.g.,`; `i. e.` → `i.e.`; `etc .` → `etc.`
#
# > Цель нормализации: предотвратить ложное разбиение предложений токенизатором spaCy на аббревиатурах.
#

# %% id="cell_pl_corrector" tags=["cell_pl_corrector"]
# Коррекция типичных ошибок оформления (только regex, без морфологии).
# Применяется ко всем поддерживаемым языкам.

# ── Удаление паттернов CUSTOM_PATTERNS ───────────────────────────────────
if CUSTOM_PATTERNS:
    _n_custom = 0
    cleaned_custom = []
    for _ci, _ct in enumerate(corpus, 1):
        _fixed = _ct
        for _cp in CUSTOM_PATTERNS:
            _new = re.sub(_cp, "", _fixed)
            if _new != _fixed:
                _n_custom += 1
                _fixed = _new
        _fixed = re.sub(r"  +", " ", _fixed).strip()
        cleaned_custom.append(_fixed)
    corpus = cleaned_custom
    print(f"CUSTOM_PATTERNS: удалено совпадений в {_n_custom} документе(-ах).")

corpus_issues = []

import re

# ── Паттерны аббревиатур по языкам ────────────────────────────────
# Строятся из поля `skrotowce` основ (dictionaries/<kod>/podstawy.yaml):
# многочленная аббревиатура получает шаблон, склеивающий разрядку
# («m. in.» → «m.in.», «т. е.» → «т.е.»). Точка ОБЯЗАТЕЛЬНА: прежние
# шаблоны с необязательной точкой (\bv\.?,?\s, \bart\.?,?\s) дописывали
# точку к обычным словам прозы (решение 2026-10-16).
from shamanic_locale import PODSTAWY, wzorce_skrotowcow

ABBREV_BY_LANG = {_k: wzorce_skrotowcow(_k) for _k in PODSTAWY}
abbrev_patterns = ABBREV_BY_LANG.get(LANG, [])

corrected = []
for i, original in enumerate(corpus, 1):
    fixed = original
    # 1. Языко-специфичные аббревиатуры
    for pattern, replacement in abbrev_patterns:
        new_text = re.sub(pattern, replacement, fixed)
        if new_text != fixed:
            corpus_issues.append((i, "исправлено",
                f"аббревиатура: шаблон '{pattern}' → '{replacement}'"))
            fixed = new_text
    # 2. Повтор слова — УДАЛЕНО 2026-10-15. Zwijanie `\b(\w{2,})\s+\1\b`
    # niszczyło poprawną reduplikację we wszystkich sześciu językach („bardzo
    # bardzo”, „чуть чуть”, „hiljaa hiljaa”, „piano piano”, „had had”,
    # „mjög mjög”) i numery („Tel. 22 22 33 44”). Literówka „the the” kosztuje
    # jeden lemat; zmiana sensu tekstu dla czytnika kosztuje więcej.
    # 3. Множественные пробелы
    fixed = re.sub(r"  +", " ", fixed)
    corrected.append(fixed)

corpus = corrected

if corpus_issues:
    _lang_label = LANG_NAMES.get(LANG, LANG)
    print(f"Коррекция текста ({_lang_label}): "
          f"исправлено {len(corpus_issues)} проблем(ы).")
    for doc_n, kind, desc in corpus_issues[:20]:
        print(f"  [Исправлено] Документ {doc_n}: {desc}")
    if len(corpus_issues) > 20:
        print(f"  ... и ещё {len(corpus_issues)-20} исправлений")
else:
    _lang_label = LANG_NAMES.get(LANG, LANG)
    print(f"Коррекция текста ({_lang_label}): типичных ошибок не обнаружено.")


# %% [markdown] id="md_tok" tags=["md_tok"]
# ## 3) Токенизация
#
# **Токенизация** — разбиение текста на элементарные единицы: слова и знаки препинания.  
# spaCy делает это с учётом языка: правильно обрабатывает апострофы, дефисы, аббревиатуры.  
#
# ### 3.1 Токенизация на слова
# Каждый документ превращается в список токенов. Пробелы исключаются.
#
# ### 3.2 Токенизация на предложения
# spaCy также сегментирует текст на предложения — полезно для анализа структуры и экстрактивного саммари (тезисы).
#
# ### 3.3 Один проход: язык каждого слова
# Перед токенизацией словари языков текста (`corpus_languages`) размечают иноязычные отрезки. Блок (целые предложения) обрабатывает модель его языка, остальное — модель основного языка; вставки внутри предложения получают леммы и POS от модели своего языка. Это ЕДИНСТВЕННЫЙ проход spaCy: предложения, леммы и сущности дальше берутся из него, без повторной сегментации.

# %% id="cell_tok" tags=["cell_tok"]
print("--- Разметка языков и токенизация (один проход spaCy) ---")
import bisect
import re
from collections import defaultdict

# 1. Весь корпус — один поток (как раньше в cell_para): «документы» — это
#    куски источника, и граница куска может пройти посреди предложения.
#    Поток нормализуется по пробелам; DOC_START хранит начало каждого
#    документа в потоке — по нему токены, предложения и сущности
#    возвращаются к своим документам для пошаговых ячеек 3–7.
#    Подписи диаграмм PDF (load_pdf) вырезаются до NLP: в поток попадает
#    только остальной текст, а сами подписи — в PODPISI_WYKRESOW
#    (смещение места выреза в потоке, текст) для чтения в HTML/DOCX.
TEKSTY, PODPISI_WYKRESOW = [], []
_poz = 0
for _c in corpus:
    if POCZATEK_WYKRESU in _c:
        _t, _pw = rozdziel_wykresy(_c)
        PODPISI_WYKRESOW += [(_poz + _p, _e) for _p, _e in _pw]
    else:
        _t = re.sub(r"\s+", " ", _c).strip()
    TEKSTY.append(_t)
    _poz += len(_t) + 1
corpus_nlp = list(TEKSTY)          # CountVectorizer / TF-IDF / QA — без подписей диаграмм
DOC_START = []
_poz = 0
for _t in TEKSTY:
    DOC_START.append(_poz)
    _poz += len(_t) + 1
TEKST = " ".join(TEKSTY)
if PODPISI_WYKRESOW:
    print(f"Подписи диаграмм исключены из NLP: фрагментов — {len(PODPISI_WYKRESOW)}, "
          f"символов — {sum(len(_e) for _p, _e in PODPISI_WYKRESOW)} "
          f"(в HTML/DOCX они останутся отдельными абзацами).")


def _dokument(poz):
    """Индекс документа, которому принадлежит символ потока poz."""
    return max(0, bisect.bisect_right(DOC_START, poz) - 1)


# 2. Язык каждого слова → иноязычные отрезки (odcinki_jezykowe).
ODCINKI = odcinki_jezykowe.odcinki(TEKST, LANG, SLOWNIKI, ALFABETY)
_st = odcinki_jezykowe.statystyka(ODCINKI)
if _st:
    print("Иноязычные отрезки (блок — целые предложения, вставка — внутри предложения):")
    for _k in sorted(_st):
        print(f"  {LANG_NAMES.get(_k, _k)} ({_k}): блоков — {_st[_k]['bloki']}, "
              f"вставок — {_st[_k]['wtracenia']}")
    for _o in ODCINKI[:20]:
        _f = TEKST[_o.start:_o.koniec]
        _f = _f[:80] + ("…" if len(_f) > 80 else "")
        print(f"    [Документ {_dokument(_o.start) + 1}] {_o.jezyk}{' (блок)' if _o.blok else ''}: {_f}")
    if len(ODCINKI) > 20:
        print(f"    ... и ещё {len(ODCINKI) - 20}")
else:
    print(f"Иноязычных отрезков нет: весь текст на основном языке ({LANG}).")

# 3. Сегменты: блок — моделью своего языка (с его сокращениями), остальной
#    текст вместе со вставками — моделью LANG (синтаксис предложения основной).
#    Вставки дополнительно разбирает модель их языка (леммы, POS) — это
#    короткие фрагменты, отдельный прогон дешёвый. Длинные сегменты режутся
#    по границам слов ниже nlp.max_length: парсеру/NER нужно ~1 ГБ временной
#    памяти на 100 000 символов (ошибка E088 у целых книг и крупных PDF).
_NLP_CHUNK = min(getattr(nlp, "max_length", 1_000_000), 200_000)


def _kawalki_tekstu(tekst, start, koniec, max_len=_NLP_CHUNK):
    """Куски [a, b) отрезка текста длиной <= max_len по границам слов."""
    while start < koniec:
        b = min(start + max_len, koniec)
        if b < koniec:
            sp = tekst.rfind(" ", start, b)
            if sp > start:
                b = sp
        yield start, b
        start = b


_zadania = defaultdict(list)  # язык -> [(смещение, текст)]
for _a, _b, _l in odcinki_jezykowe.segmenty(TEKST, LANG, ODCINKI):
    for _ka, _kb in _kawalki_tekstu(TEKST, _a, _b):
        _txt = TEKST[_ka:_kb]
        if _l != LANG:
            for _p, _r in ABBREV_BY_LANG.get(_l, []):
                _txt = re.sub(_p, _r, _txt)
        if _txt.strip():
            _zadania[_l].append((_ka, _txt))
_wstawki = defaultdict(set)   # язык -> {текст вставки}
for _o in ODCINKI:
    if not _o.blok:
        _wstawki[_o.jezyk].add(TEKST[_o.start:_o.koniec])

CZESCI = []                        # [(язык, смещение в потоке, Doc)] в порядке текста
STOP_BY_LANG = {LANG: stop_words}
WSTAWKI_ANALIZA = {}               # (язык, текст вставки) -> {форма: (лемма, POS, тег)}
_unreliable = {}
# Язык за языком: LRU-кэш get_nlp() держит две модели, поэтому сегменты
# одного языка обрабатываются подряд, без перезагрузки моделей.
for _l in [LANG] + sorted((set(_zadania) | set(_wstawki)) - {LANG}):
    _m = nlp if _l == LANG else get_nlp(_l)
    if _l != LANG:
        STOP_BY_LANG[_l] = _m.Defaults.stop_words
        _caps = set(_m.pipe_names)
        _brak = [_n for _n, _ok in (("NER", "ner" in _caps or "icelandic_ner" in _caps),
                                    ("лемматизатор", "lemmatizer" in _caps)) if not _ok]
        if _brak:
            _unreliable[_l] = _brak
    _z = _zadania.get(_l, [])
    for (_off, _txt), _d in zip(_z, _m.pipe(_z_txt for _o, _z_txt in _z)):
        CZESCI.append((_l, _off, _d))
    _ws = sorted(_wstawki.get(_l, ()))
    for _txt, _d in zip(_ws, _m.pipe(_ws)):
        WSTAWKI_ANALIZA[(_l, _txt)] = {
            _tk.text: ((_tk.lemma_ or _tk.text).lower(), _tk.pos_, _tk.tag_) for _tk in _d if _tk.is_alpha}
    print(f"  [{_l}] {LANG_NAMES.get(_l, _l)}: сегментов — {len(_z)}, вставок — {len(_ws)}")
CZESCI.sort(key=lambda x: x[1])

if _unreliable:
    print("\n[ВНИМАНИЕ] Анализ НЕНАДЁЖЕН для иноязычных отрезков следующих языков:")
    for _l, _brak in _unreliable.items():
        print(f"  {_l}: в модели нет компонентов {_brak}")
        if _l == "is":
            print("     Установите: pip install transformers torch (HF-модели исландского)")
        else:
            print(f"     Установите: python -m spacy download {MODEL_BY_LANG.get(_l, '?')}")

# Вставки — для подстановки разбора модели их языка.
_WSTAWKI = sorted((_o.start, _o.koniec, _o.jezyk) for _o in ODCINKI if not _o.blok)


def _wstawka(poz):
    """(start, конец, язык) вставки, содержащей символ потока poz, или None."""
    j = bisect.bisect_right(_WSTAWKI, (poz, float("inf"))) - 1
    if j >= 0 and _WSTAWKI[j][0] <= poz < _WSTAWKI[j][1]:
        return _WSTAWKI[j]
    return None


def _analiza(lang, off, tok):
    """(язык, лемма, POS, тег) токена; внутри вставки — по модели языка вставки."""
    if lang == LANG:
        w = _wstawka(off + tok.idx)
        if w:
            a = WSTAWKI_ANALIZA.get((w[2], TEKST[w[0]:w[1]]), {}).get(tok.text)
            if a:
                return (w[2],) + a
    return lang, (tok.lemma_ or tok.text).lower(), tok.pos_, tok.tag_


def _jest_stop(lang, off, tok):
    """Стоп-слово по списку языка токена (у вставки — языка вставки)."""
    jezyk = _analiza(lang, off, tok)[0]
    return tok.is_stop or tok.text.lower() in STOP_BY_LANG.get(jezyk, stop_words)


# Токены, предложения и сущности по документам (по смещению начала).
# Блок у границы документа обрабатывается своей моделью целиком; его
# токены расходятся по документам так же, по смещению.
TOKENY_DOC = [[] for _ in TEKSTY]
ZDANIA_DOC = [[] for _ in TEKSTY]
ENCJE_DOC = [[] for _ in TEKSTY]
for _l, _off, _d in CZESCI:
    for _tk in _d:
        TOKENY_DOC[_dokument(_off + _tk.idx)].append((_l, _off, _tk))
    for _s in _d.sents:
        ZDANIA_DOC[_dokument(_off + _s.start_char)].append(_s.text.strip())
    for _e in _d.ents:
        ENCJE_DOC[_dokument(_off + _e.start_char)].append((_e.text, _e.label_))


def _tokeny(i):
    """(язык сегмента, смещение, токен) документа i в порядке текста."""
    return TOKENY_DOC[i]


word_tokens = [[_tk.text for _l, _o, _tk in _tokeny(_i) if not _tk.is_space] for _i in range(len(TEKSTY))]
print("\nСловесные токены:")
for i, tokens in enumerate(word_tokens, 1):
    print(f"  Документ {i}: всего токенов — {len(tokens)}")
    print(f"    Первые 20: {tokens[:20]}")

sent_tokens = [[s for s in ZDANIA_DOC[_i] if s] for _i in range(len(TEKSTY))]
print("\nПредложения:")
MAX_SENT_PREVIEW = 3
for i, sents in enumerate(sent_tokens, 1):
    print(f"  Документ {i}: предложений — {len(sents)}")
    for j, s in enumerate(sents[:MAX_SENT_PREVIEW], 1):
        _s = s.replace("\n", " ")[:100]
        print(f"    [{j}] {_s}")
    if len(sents) > MAX_SENT_PREVIEW:
        print(f"    ... и ещё {len(sents) - MAX_SENT_PREVIEW} предложений")


# %% [markdown] id="md_stop" tags=["md_stop"]
# ## 4) Стоп-слова
#
# **Стоп-слова** — служебные слова (артикли, предлоги, местоимения), которые мало несут смысла.  
# Список берётся прямо из загруженной модели spaCy — он уже оптимизирован под язык корпуса.  
# После фильтрации остаются только семантически насыщенные слова.

# %% id="cell_stop" tags=["cell_stop"]
print("--- Фильтрация стоп-слов ---")
print(f"Язык: {LANG_NAMES.get(LANG, LANG)} | Стоп-слов в списке: {len(stop_words)}")
print(f"Выборка (первые 20 по алфавиту): {sorted(list(stop_words))[:20]}")
for _l, _sw in STOP_BY_LANG.items():
    if _l != LANG:
        print(f"Иноязычные отрезки ({_l}): свой список стоп-слов — {len(_sw)} записей")

filtered_tokens = [
    [tok.text for _l, _o, tok in _tokeny(_i) if tok.is_alpha and not _jest_stop(_l, _o, tok)]
    for _i in range(len(TEKSTY))
]
print()
for i, tokens in enumerate(filtered_tokens, 1):
    print(f"  Документ {i}: содержательных слов после фильтрации — {len(tokens)}")
    print(f"    Выборка: {tokens[:20]}")


# %% [markdown] id="md_lemma" tags=["md_lemma"]
# ## 5) Лемматизация
#
# **Лемма** — начальная (словарная) форма слова. Лемматизация приводит все формы к единому виду:  
# «бежит», «бежали», «бегут» → «бежать»; «documents», «document» → «document».  
#
# В отличие от стемминга, лемматизация использует словарь и грамматические правила — результат всегда читаемое слово.  
# В spaCy лемма доступна через `token.lemma_`.

# %% id="cell_lemma" tags=["cell_lemma"]
print("--- Лемматизация ---")
# Лемма иноязычного отрезка — от модели его языка (_analiza), а не от модели LANG.
all_lemmas = [
    [_analiza(_l, _o, t)[1] for _l, _o, t in _tokeny(_i) if t.is_alpha and not _jest_stop(_l, _o, t)]
    for _i in range(len(TEKSTY))
]
pairs = [(t.text, _analiza(_l, _o, t)[1]) for _l, _o, t in _tokeny(0)
         if t.is_alpha and not _jest_stop(_l, _o, t)][:30]
print("Пары исходное слово → лемма (Документ 1, первые 30):")
_h1, _h2, _sep = "Исходное", "Лемма", "-" * 22
print(f"  {_h1:<22} {_h2}")
print(f"  {_sep} -----")
for orig, lemma in pairs:
    changed = "  <-- изменено" if orig.lower() != lemma else ""
    print(f"  {orig:<22} {lemma}{changed}")
print()
for i, lemmas in enumerate(all_lemmas, 1):
    print(f"  Документ {i}: лемм — {len(lemmas)}, уникальных — {len(set(lemmas))}")


# %% [markdown] id="md_pos" tags=["md_pos"]
# ## 6) Части речи (POS-теггинг)
#
# **POS-теггинг** присваивает каждому токену грамматическую роль: существительное, глагол, прилагательное и т.д.  
# spaCy возвращает два уровня:
# - `pos_` — универсальный тег (NOUN, VERB, ADJ, ADV, PROPN …)
# - `tag_` — детальный тег, специфичный для языка
#
# Распределение POS позволяет понять стиль текста: в научных текстах много существительных, в художественных — глаголов и прилагательных.

# %% id="cell_pos" tags=["cell_pos"]
print("--- Разметка частей речи (POS) ---")
print("Теги: NOUN — сущ., VERB — гл., ADJ — прил., ADV — нар., PROPN — имя собств., ...")
for i in range(len(TEKSTY)):
    _anal = [(t.text, _analiza(_l, _o, t), _jest_stop(_l, _o, t))
             for _l, _o, t in _tokeny(i) if t.is_alpha]
    pos_counts = Counter(a[2] for _txt, a, _st in _anal)
    print(f"\nДокумент {i + 1} — распределение частей речи:")
    for pos, cnt in sorted(pos_counts.items(), key=lambda x: -x[1]):
        bar = "#" * min(cnt, 40)
        print(f"  {pos:8s}: {cnt:4d}  {bar}")
    notable = [(_txt, a[2], a[3]) for _txt, a, _st in _anal if not _st][:10]
    print("  Примеры тегированных слов (слово | POS | детальный тег):")
    for txt, pos, tag in notable:
        print(f"    {txt!r:<22} | {pos:<10} | {tag}")


# %% [markdown] id="md_ner" tags=["md_ner"]
# ## 7) Именованные сущности (NER)
#
# **NER** (Named Entity Recognition) находит имена, организации, места, даты, суммы денег и другие упомянутые объекты.  
# spaCy возвращает список `doc.ents`, где у каждой сущности есть текст и метка.  
#
# Типичные метки: PERSON, ORG, GPE (город/страна), DATE, MONEY, PRODUCT.

# %% id="cell_ner" tags=["cell_ner"]
print("--- Именованные сущности (NER) ---")
from collections import OrderedDict

all_ents = []
# Сущности блока находит модель его языка; вставки внутри предложения
# остаются за моделью LANG — двухсловной вставке не хватает контекста для NER.
for i, ents in enumerate(ENCJE_DOC, 1):
    all_ents.extend(ents)
    if not ents:
        print(f"Документ {i}: именованных сущностей не обнаружено.")
        print()
        continue

    # Дедупликация в обрамлении одного документа.
    # Если та же сущность встречается N раз с одинаковой меткой — печатаем один раз.
    # Если встречается с разными метками (модель путается) — печатаем все варианты,
    # потому что это диагностически ценная информация.
    by_text = OrderedDict()
    for txt, label in ents:
        if txt not in by_text:
            by_text[txt] = []
        if label not in by_text[txt]:
            by_text[txt].append(label)

    unique_pairs = [(txt, lab) for txt, labs in by_text.items() for lab in labs]
    n_total = len(ents)
    n_unique = len(unique_pairs)
    inconsistent = [txt for txt, labs in by_text.items() if len(labs) > 1]

    if n_unique < n_total:
        print(f"Документ {i}: найдено сущностей — {n_total} "
              f"(уникальных: {n_unique})")
    else:
        print(f"Документ {i}: найдено сущностей — {n_total}")

    for txt, label in unique_pairs:
        print(f"  [{label}] {txt!r}")

    if inconsistent:
        print(f"  [ДИАГНОСТИКА] Несогласованные классификации в этом документе: "
              f"{len(inconsistent)}")
        for txt in inconsistent[:5]:
            print(f"    {txt!r}: {', '.join(by_text[txt])}")
        if len(inconsistent) > 5:
            print(f"    ... и ещё {len(inconsistent) - 5}")
    print()

if all_ents:
    print("Типы сущностей по всему корпусу:")
    for etype, cnt in Counter(label for _, label in all_ents).most_common():
        print(f"  {etype:<12}: {cnt}")
else:
    print("Именованных сущностей не найдено ни в одном документе.")
if IS_NER_FAILURES:
    print(f"[ВНИМАНИЕ] Исландский NER не обработал фрагментов: {len(IS_NER_FAILURES)} "
          f"({', '.join(sorted(set(IS_NER_FAILURES)))}) — сущности в них не найдены.")

# %% [markdown] id="md_bow" tags=["md_bow"]
# ## 8) Мешок слов (CountVectorizer)
#
# **CountVectorizer** превращает тексты в числовые векторы, считая, сколько раз каждое слово встречается в документе.  
# Результат — матрица «документ × слово», где каждая строка — один документ, а каждый столбец — одно слово.  
#
# ### 8.1 Униграммы (отдельные слова)
# Базовое представление: каждое слово — отдельный признак.
#
# ### 8.2 Биграммы (пары слов)
# Добавляет устойчивые выражения: «machine learning», «natural language», «named entity».

# %% id="cell_bow" tags=["cell_bow"]
print("--- Мешок слов (CountVectorizer) ---")
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer

sklearn_stop = list(stop_words) if stop_words else "english"

vec_uni = CountVectorizer(stop_words=sklearn_stop, min_df=1)
X_uni = vec_uni.fit_transform(corpus_nlp)
vocab_uni = vec_uni.get_feature_names_out()
print(f"Словарь униграмм: {len(vocab_uni)} уникальных терминов")
print(f"Матрица документ×слово: {X_uni.shape}")
df_uni = pd.DataFrame(X_uni.toarray(), columns=vocab_uni,
                      index=[f"Документ {i+1}" for i in range(len(corpus))])
print("\nТоп-10 наиболее частых слов по всему корпусу:")
for term, freq in df_uni.sum().nlargest(10).items():
    _bar = "#" * int(freq)
    print(f"  {term!r:<25}: {int(freq):3d}  {_bar}")

vec_bi = CountVectorizer(ngram_range=(2,2), stop_words=sklearn_stop, max_features=50, min_df=1)
X_bi = vec_bi.fit_transform(corpus_nlp)
vocab_bi = vec_bi.get_feature_names_out()
print(f"\nСловарь биграмм (топ-50): {len(vocab_bi)} уникальных биграмм")
top5_bi = pd.DataFrame(X_bi.toarray(), columns=vocab_bi).sum().nlargest(5)
if not top5_bi.empty:
    print("Топ-5 наиболее частых биграмм:")
    for rank_b, (term, freq) in enumerate(top5_bi.items(), 1):
        print(f"  {rank_b}. {term!r}: {int(freq)}")
else:
    print("Биграммы не найдены (корпус слишком мал).")

vec_tri = CountVectorizer(ngram_range=(3,3), stop_words=sklearn_stop, max_features=50, min_df=1)
X_tri = vec_tri.fit_transform(corpus_nlp)
vocab_tri = vec_tri.get_feature_names_out()
print(f"\nСловарь триграмм (топ-50): {len(vocab_tri)} уникальных триграмм")
top5_tri = pd.DataFrame(X_tri.toarray(), columns=vocab_tri).sum().nlargest(5)
if not top5_tri.empty:
    print("Топ-5 наиболее частых триграмм (трёхсловных выражений):")
    for rank_t, (term, freq) in enumerate(top5_tri.items(), 1):
        print(f"  {rank_t}. {term!r}: {int(freq)}")
else:
    print("Триграммы не найдены (корпус слишком мал).")


# %% [markdown] id="md_tfidf" tags=["md_tfidf"]
# ## 9) TF-IDF и автоматический поиск
#
# **TF-IDF** (Term Frequency — Inverse Document Frequency) взвешивает слова: частые в одном документе, но редкие в остальных, получают высокий вес.  
# Это делает поиск умнее, чем простой подсчёт слов.
#
# **Косинусное сходство** измеряет угол между векторами двух текстов:  
# - 1.0 = полностью совпадают  
# - 0.0 = не имеют ни одного общего слова
#
# **Автоматический запрос:** ноутбук строит запрос из слов с наибольшим средним весом TF-IDF по корпусу.  
# Такой запрос гарантированно даёт косинусное сходство > 0 (никогда не возвращает −1).

# %% id="cell_tfidf" tags=["cell_tfidf"]
print("--- TF-IDF-поиск с автоматическим запросом ---")
import random
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

random.seed(42)
tfidf = TfidfVectorizer(stop_words=sklearn_stop, min_df=1)
tfidf_matrix = tfidf.fit_transform(corpus_nlp)
feature_names = tfidf.get_feature_names_out()
print(f"Матрица TF-IDF: {tfidf_matrix.shape} (документов × признаков)")
print(f"Общий словарь: {len(feature_names)} терминов")

mean_scores = tfidf_matrix.toarray().mean(axis=0)
top_indices = mean_scores.argsort()[::-1]
candidates = [feature_names[i] for i in top_indices
              if feature_names[i].isalpha() and len(feature_names[i]) > 3][:40]
if not candidates:
    candidates = [feature_names[i] for i in top_indices[:10]]
n_terms = random.randint(2, min(4, len(candidates)))
query_terms = random.sample(candidates, n_terms)
AUTO_QUERY = " ".join(query_terms)
print(f"\nАвтозапрос: \"{AUTO_QUERY}\"")
print("(Из топ-терминов TF-IDF — схожесть всегда > 0)")

q_vec = tfidf.transform([AUTO_QUERY])
cosine_scores = linear_kernel(q_vec, tfidf_matrix).flatten()
ranked_order = cosine_scores.argsort()[::-1]
_c1, _c2, _c3 = "Ранг", "Документ", "Схожесть"
print(f"\nРанжирование по запросу \"{AUTO_QUERY}\":\n")
print(f"  {_c1:<6} {_c2:<12} {_c3:<16} Фрагмент")
print("  " + "-" * 72)
for rank, idx2 in enumerate(ranked_order, 1):
    score = cosine_scores[idx2]
    preview = corpus_nlp[idx2].strip().replace("\n", " ")[:60]
    print(f"  {rank:<6} Документ {idx2+1:<5} {score:<16.4f} {preview}...")
best_idx = ranked_order[0]
print(f"\nНаиболее релевантный: Документ {best_idx+1} (косинус = {cosine_scores[best_idx]:.4f})")


# %% [markdown] id="md_para" tags=["md_para"]
# ## Структура текста: абзацы и предложения
#
# Предложения берутся из того же единственного прохода spaCy (ячейка токенизации): каждый языковой сегмент уже разбит на предложения моделью своего языка, поэтому иноязычный блок разрезан по правилам своего языка (сокращения `e.g.`, `esim.`) и повторная сегментация не нужна. Предложения группируются по 3–6 в «абзацы»; эту структуру потребляют тезисы, ключевые слова и тематизация.
#
# Для экспорта сохраняются:
#
# - `sent_langs[i]` — язык `i`-го предложения (язык его сегмента),
# - `sent_wstawki[i]` — иноязычные вставки внутри предложения (смещения и язык),
# - `para_langs[i]` — преобладающий язык абзаца; `para_sentences[i]` и `para_sent_ids[i]` — его предложения.
#
# В `accessible_text.html` вставка получает собственный `<span lang="...">`, в `accessible_text.docx` — свой `Run` с `<w:lang>`: экранная читалка переключает голос ровно на цитате или фамилии, а не на всём предложении.

# %% id="cell_para" tags=["cell_para"]
print("--- Структура текста: абзацы ---")
import numpy as np
import pandas as pd

all_sents, sent_langs, sent_wstawki, sent_lemmas = [], [], [], []
_sent_starts = []   # смещения предложений в потоке — для места подписей диаграмм
# Короткие предложения (≤ 10 символов: «Да.», короткий заголовок) в NLP не
# входят, но в HTML/DOCX остаются на своём месте (аудит 2.0: они пропадали
# из экспорта молча). (смещение, текст, язык).
KROTKIE_ZDANIA = []
for _l, _off, _d in CZESCI:
    for _s in _d.sents:
        _txt = _s.text.strip()
        if len(_txt) <= 10:
            if _txt:
                KROTKIE_ZDANIA.append(
                    (_off + _s.start_char + (len(_s.text) - len(_s.text.lstrip())), _txt, _l))
            continue
        # Смещение предложения в потоке TEKST (для сегментов LANG текст Doc
        # совпадает с потоком; у блоков вставок нет, смещения не нужны).
        _a = _off + _s.start_char + (len(_s.text) - len(_s.text.lstrip()))
        _b = _a + len(_txt)
        _w = []
        if _l == LANG:
            _j = bisect.bisect_left(_WSTAWKI, (_a,))
            if _j > 0 and _WSTAWKI[_j - 1][1] > _a:
                _j -= 1
            while _j < len(_WSTAWKI) and _WSTAWKI[_j][0] < _b:
                _ws, _wk, _wl = _WSTAWKI[_j]
                if _wk > _a:
                    _w.append((max(_ws, _a) - _a, min(_wk, _b) - _a, _wl))
                _j += 1
        all_sents.append(_txt)
        _sent_starts.append(_a)
        sent_langs.append(_l)
        sent_wstawki.append(_w)
        sent_lemmas.append([_analiza(_l, _off, _t)[1] for _t in _s
                            if _t.is_alpha and not _jest_stop(_l, _off, _t)])
print(f"Всего предложений: {len(all_sents)}")

# Абзацы по 3–6 предложений; para_lemmas (для TF-IDF ключевых слов) —
# леммы предложений абзаца, каждое от модели своего языка.
PARA_MIN, PARA_MAX = 3, 6
paragraphs, para_sentences, para_sent_ids, para_lemmas, para_langs = [], [], [], [], []
for _p in range(0, len(all_sents), PARA_MAX):
    _ids = list(range(_p, min(_p + PARA_MAX, len(all_sents))))
    para_sent_ids.append(_ids)
    para_sentences.append([all_sents[_k] for _k in _ids])
    paragraphs.append(" ".join(para_sentences[-1]))
    para_lemmas.append(" ".join(_lem for _k in _ids for _lem in sent_lemmas[_k]))
    para_langs.append(Counter(sent_langs[_k] for _k in _ids).most_common(1)[0][0])
print(f"Сформировано абзацев: {len(paragraphs)} (по {PARA_MIN}–{PARA_MAX} предложений)")

# Подписи диаграмм (вырезаны из NLP в cell_tok) — только для чтения: в HTML/DOCX
# отдельный абзац после абзаца, где стоит последнее предложение перед местом
# выреза (-1 = перед первым абзацем). Абзацы NLP от этого не меняются.
PODPISI_PO_AKAPICIE = defaultdict(list)
for _p, _e in PODPISI_WYKRESOW:
    _n = bisect.bisect_left(_sent_starts, _p)
    PODPISI_PO_AKAPICIE[(_n - 1) // PARA_MAX if _n else -1].append(_e)
if PODPISI_PO_AKAPICIE:
    print(f"  Абзацев с подписями диаграмм (только для HTML/DOCX): {len(PODPISI_PO_AKAPICIE)}")
# Короткое предложение встаёт в экспорте перед первым предложением NLP,
# которое начинается после него (индекс = число предложений перед ним).
KROTKIE_PRZED = defaultdict(list)
for _p, _txt, _l in KROTKIE_ZDANIA:
    KROTKIE_PRZED[bisect.bisect_left(_sent_starts, _p)].append((_txt, _l))
if KROTKIE_ZDANIA:
    print(f"  Коротких предложений (≤ 10 символов) вне NLP, но в HTML/DOCX: {len(KROTKIE_ZDANIA)}")

df_sent = pd.DataFrame({"sent_id": range(1, len(all_sents) + 1), "sentence": all_sents, "lang": sent_langs})
df_para = pd.DataFrame({"para_id": range(1, len(paragraphs) + 1), "paragraph": paragraphs})

# Языково-специфичный паттерн токенов для CountVectorizer / TF-IDF
# Один шаблон для всех языков (shamanic_locale.WZORZEC_TOKENOW): ≥2 любые
# БУКВЫ, дефис и апостроф только между буквами («itä-suome», «dell'anno»),
# без цифр и «_». Шаблон из алфавита корпуса терял «tšekki», «Müller»,
# «łódź» целиком (аудит 2026-10-16); прежний \S{2,} для it/fi/is
# пропускал цифры и знаки препинания.
from shamanic_locale import WZORZEC_TOKENOW
TOKEN_PAT = WZORZEC_TOKENOW

print(f"  Языки абзацев   : {dict(Counter(para_langs))}")
print(f"  Языки предложений: {dict(Counter(sent_langs))}")
_z_wstawkami = sum(1 for _w in sent_wstawki if _w)
print(f"  Предложений с иноязычными вставками: {_z_wstawkami} "
      f"(в HTML/DOCX каждая вставка получит свой lang-тег)")

# %% [markdown] id="md_keywords" tags=["md_keywords"]
# ## Ключевые слова (TF-IDF)
#
# TF-IDF по абзацам выявляет термины, характерные для конкретных фрагментов, но редкие в целом по тексту. Здесь мы получаем рейтинговый список ключевых терминов и фраз (от 1 до 3 слов), отсортированных по средневзвешенному весу TF-IDF.

# %% id="cell_keywords" tags=["cell_keywords"]
print("--- Ключевые слова (TF-IDF) ---")
from sklearn.feature_extraction.text import TfidfVectorizer

kw_tfidf = TfidfVectorizer(
    lowercase=True,
    stop_words=list(stop_words) if stop_words else "english",
    token_pattern=TOKEN_PAT,
    ngram_range=(1, 3),
    min_df=2
)
try:
    Xkw = kw_tfidf.fit_transform(para_lemmas)
    kw_terms  = kw_tfidf.get_feature_names_out()
    kw_scores = Xkw.mean(axis=0).A1
    df_keywords_tfidf = (
        pd.DataFrame({"term": kw_terms, "score": kw_scores})
        # Стабильная сортировка с ничьей по термину: порядок равных весов
        # не зависит от алгоритма сортировки версии numpy/pandas.
        .sort_values(["score", "term"], ascending=[False, True], kind="stable")
        .reset_index(drop=True)
    )
    print(f"Уникальных терминов: {len(kw_terms)}")
    print()
    _h1, _h2, _sep = "Термин", "Вес TF-IDF", "-" * 38
    print(f"  {_h1:<38} {_h2}")
    print(f"  {_sep} ----------")
    for _, row in df_keywords_tfidf.head(25).iterrows():
        _term, _sc = row["term"], row["score"]
        print(f"  {_term:<38} {_sc:.4f}")
except Exception as kw_err:
    print(f"[ВНИМАНИЕ] Не удалось извлечь ключевые слова: {kw_err}")
    print("  Возможная причина: слишком мало текста или все слова в стоп-листе.")
    df_keywords_tfidf = pd.DataFrame(columns=["term", "score"])


# %% [markdown] id="md_theses" tags=["md_theses"]
# ## Тезисы (экстрактивное саммари)
#
# Для каждого абзаца выбирается одно **наиболее информативное предложение** (с максимальной суммой TF-IDF весов). Результат — компактный список тезисов, сохраняемый в файл `тезисы.txt` в формате, удобном для экранных читалок.
#
# Параметр `N_THESES` задаёт максимальное число тезисов в файле.

# %% id="cell_theses" tags=["cell_theses"]
print("--- Тезисы ---")
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np

N_THESES = 15  # максимальное число тезисов
THESES_FILE = str(PROJECT_DIR / t(LANG, "theses.filename"))

# TF-IDF по предложениям
v_sent = TfidfVectorizer(
    lowercase=True,
    stop_words=list(stop_words) if stop_words else "english",
    token_pattern=TOKEN_PAT,
    ngram_range=(1, 2), min_df=1
)
try:
    S_sent = v_sent.fit_transform(df_sent["sentence"].tolist())
    sent_scores = np.asarray(S_sent.sum(axis=1)).ravel()
except Exception:
    sent_scores = np.ones(len(df_sent))

# Для каждого абзаца: найти лучшее предложение.
#
# ВАЖНО: абзацы здесь НЕ пересегментируются заново. Прежняя версия делала
# nlp(para).sents и получала иногда иное число предложений, чем cell_para
# (модель доминирующего языка иначе делит уже склеенный абзац — на реальном
# финском корпусе один абзац из 6 предложений превращался в 7). Из-за этого
# sent_cursor уезжал за границу sent_scores, срез seg оказывался пустым
# и .argmax() падал: "attempt to get argmax of an empty sequence"
# (см. release_notes.md, v1.5.1).
#
# Единственный источник границ — para_sentences, синхронизированный
# с all_sents / df_sent / sent_scores в cell_para (один проход spaCy,
# без пересегментации). Инвариант:
#   sum(len(p) for p in para_sentences) == len(df_sent) == len(sent_scores)
# Ниже он проверяется явно, а срезы дополнительно ограничены по границе
# массива — рассинхронизация приведёт к предупреждению и пропуску абзацев,
# но не к падению ячейки.
_n_scores = len(sent_scores)
if len(paragraphs) != len(para_sentences):
    print(f"[ВНИМАНИЕ] Рассинхронизация абзацев: {len(paragraphs)} абзацев, "
          f"{len(para_sentences)} списков предложений. Тезисы строятся "
          f"только по первым {min(len(paragraphs), len(para_sentences))}.")
_n_para_sents = sum(len(p) for p in para_sentences)
if _n_para_sents != _n_scores:
    print(f"[ВНИМАНИЕ] Предложений в абзацах: {_n_para_sents}, "
          f"оценок TF-IDF: {_n_scores}. Абзацы за границей оценок будут "
          f"пропущены (ожидалось равенство — проверьте cell_para).")

theses_rows = []
sent_cursor = 0
_skipped_paras = 0
for pid, (para, p_sents) in enumerate(zip(paragraphs, para_sentences), 1):
    lo = sent_cursor
    # Курсор двигаем на ПОЛНУЮ длину абзаца (до фильтра по длине),
    # иначе отброшенное короткое предложение сдвинуло бы все следующие
    # абзацы относительно sent_scores.
    sent_cursor += len(p_sents)
    n_avail = max(0, min(sent_cursor, _n_scores) - lo)
    # Кандидаты: (глобальный индекс предложения, текст)
    cand = [(i, s) for i, s in enumerate(p_sents[:n_avail], start=lo)
            if len(s) > 10]
    if not cand:
        _skipped_paras += 1
        continue
    best_i, best_sent = max(cand, key=lambda pair: sent_scores[pair[0]])
    if len(best_sent) >= 40:
        theses_rows.append({"para_id": pid, "sentence": best_sent,
                             "score": float(sent_scores[best_i])})
if _skipped_paras:
    print(f"[ВНИМАНИЕ] Абзацев без оценённых предложений: {_skipped_paras} "
          f"(пропущены).")

df_theses = pd.DataFrame(theses_rows)
print(f"Сформировано тезисов: {len(df_theses)}")
print(f"Показываем первые {min(N_THESES, len(df_theses))}:")
print()
for _, row in df_theses.head(N_THESES).iterrows():
    _pid = int(row["para_id"])
    _sc  = row["score"]
    preview = row["sentence"][:150].replace("\n", " ")
    print(f"  Абзац {_pid:3d} (оценка {_sc:.3f}): {preview}")

# Сохраняем
theses_lines = ["- " + str(row["sentence"]) for _, row in df_theses.iterrows()]
theses_text = "\n".join(theses_lines)
with open(THESES_FILE, "w", encoding="utf-8") as f:
    f.write(theses_text)
print(f"\nТезисы сохранены: {THESES_FILE} ({len(df_theses)} тезисов)")


# %% [markdown] id="md_topics" tags=["md_topics"]
# ## Тематизация (KMeans)
#
# Каждый абзац представляется вектором spaCy, затем кластеризуется алгоритмом KMeans. Для каждой темы выводятся ключевые слова и пример фрагмента.  
#
# **Требование:** модель spaCy должна поддерживать векторы слов (например, `*_lg`). При использовании моделей без векторов тематизация пропускается с соответствующим сообщением.

# %% id="cell_topics" tags=["cell_topics"]
print("--- Тематизация ---")
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np

# Проверяем наличие векторов в модели
_probe = nlp("test" if LANG == "en" else ("польский" if LANG == "ru" else "tekst"))
has_vectors = np.any(_probe.vector != 0) and _probe.has_vector

df_topics = pd.DataFrame()
topic_keywords = {}

if not has_vectors:
    _lg = MODEL_BY_LANG.get(LANG, "en_core_web_lg")
    print("[ВНИМАНИЕ] Модель spaCy не содержит векторов слов.")
    print(f"  Для тематизации установите: python -m spacy download {_lg}")
    print("  Тематизация пропущена.")
elif len(paragraphs) < 4:
    print("[ВНИМАНИЕ] Слишком мало абзацев для тематизации (нужно >= 4).")
else:
    vecs = []
    for para in paragraphs:
        v = nlp(para).vector
        vecs.append(v / (np.linalg.norm(v) + 1e-12))
    X_vec = np.vstack(vecs)
    N_TOPICS = min(6, max(2, len(paragraphs) // 4))
    kmeans = KMeans(n_clusters=N_TOPICS, random_state=42, n_init="auto")
    labels = kmeans.fit_predict(X_vec)
    df_topics = df_para.copy()
    df_topics["topic"] = labels
    print(f"Обнаружено тем: {N_TOPICS}  |  Абзацев: {len(paragraphs)}")
    print()
    # TF-IDF ключевые слова на тему
    for topic_id in sorted(df_topics["topic"].unique()):
        subset = df_topics[df_topics["topic"] == topic_id]["paragraph"].tolist()
        n_para = len(subset)
        try:
            vt = TfidfVectorizer(
                lowercase=True,
                stop_words=list(stop_words) if stop_words else "english",
                token_pattern=TOKEN_PAT,
                ngram_range=(1, 2), min_df=1)
            Xt = vt.fit_transform(subset)
            tt = vt.get_feature_names_out()
            st = Xt.mean(axis=0).A1
            top_t = (pd.DataFrame({"term": tt, "s": st})
                     .sort_values(["s", "term"], ascending=[False, True], kind="stable")
                     .head(8)["term"].tolist())
        except Exception:
            top_t = []
        topic_keywords[int(topic_id)] = top_t
        kw_str = ", ".join(top_t) or "(нет данных)"
        print(f"Тема {topic_id} ({n_para} абзацев):")
        print(f"  Ключевые слова: {kw_str}")
        ex = subset[0][:200].replace("\n", " ")
        print(f"  Пример: {ex}...")
        print()

# %% [markdown] id="md_sentiment" tags=["md_sentiment"]
# ## Анализ тональности (опционально)
#
# Эта ячейка выполняется только если в `config.json` задан ключ `"enable_sentiment": true`.
# Модель `cardiffnlp/twitter-xlm-roberta-base-sentiment` оценивает тональность каждого
# абзаца (негативно / нейтрально / позитивно). Результат сознательно **не** выводится
# пользователю как вердикт — он пишется только в `sentiment.csv` и служит «пищей» для
# шаманского слоя (рытуал Vieno и локальный «подводное течение»). Если опция выключена
# или модель не поднялась (например, отсутствует `tiktoken`), ячейка молча пропускается,
# и весь остальной конвейер работает как прежде — без английского фолбэка.

# %% id="cell_sentiment" tags=["cell_sentiment"]
print("--- Анализ тональности (опционально) ---")
sentiment_written = False
if not ENABLE_SENTIMENT:
    print("Опция выключена (enable_sentiment != true в config.json) — пропуск.")
    print("Шаманский слой использует поведение по умолчанию.")
elif not paragraphs:
    print("Нет абзацев для анализа — пропуск.")
else:
    _silence_hf_progress()
    SENTIMENT_MODEL = "cardiffnlp/twitter-xlm-roberta-base-sentiment"
    _sent_clf = None
    try:
        from transformers import pipeline as _hf_pipeline
        print(f"Загрузка модели тональности: {SENTIMENT_MODEL}")
        print("Первый запуск скачивает веса (~1,1 ГБ), далее — локальный кэш.")
        _sent_clf = _hf_pipeline(
            "sentiment-analysis",
            model=SENTIMENT_MODEL,
            truncation=True,
            max_length=512,
            # Явно CPU и float32: на машине с GPU pipeline сам выбрал бы
            # cuda, и тональность абзацев отличалась бы от CPU-прогона.
            device=-1,
            dtype="float32",
        )
        print("[OK] Модель тональности загружена.")
    except Exception as _exc:
        # Намеренно БЕЗ английского фолбэка: если модель не поднялась — просто
        # пропускаем, sentiment.csv не пишется, и шаманский слой ведёт себя
        # как раньше. Токенизатор XLM-RoBERTa требует ОДНОВРЕМЕННО
        # sentencepiece + protobuf (иначе "Error parsing line b'\x0e' ...")
        # И tiktoken (иначе "tiktoken is required to read a tiktoken file").
        _sent_clf = None
        print(f"[ВНИМАНИЕ] Модель тональности недоступна: {_exc}")
        print("  Анализ тональности пропущен (без фолбэка). Конвейер продолжает работу.")

    if _sent_clf is not None:
        # Нормализация меток: новый формат (negative/neutral/positive)
        # и старый (LABEL_0/LABEL_1/LABEL_2).
        _LABEL_NORM = {
            "negative": "negative", "neutral": "neutral", "positive": "positive",
            "label_0": "negative", "label_1": "neutral", "label_2": "positive",
        }
        _rows = []
        for _i, (_para, _plang) in enumerate(zip(paragraphs, para_langs), 1):
            try:
                _res = _sent_clf(_para[:2000])[0]
                _label = _LABEL_NORM.get(str(_res["label"]).lower(),
                                         str(_res["label"]).lower())
                _score = round(float(_res["score"]), 4)
            except Exception:
                _label, _score = "error", 0.0
            _rows.append({"para_id": _i, "label": _label,
                          "score": _score, "lang": _plang})

        # Сырые данные: ничего не фильтруем (ни по порогу уверенности, ни по
        # иноязычным абзацам) — шаман получает полную картину и решает сам.
        _df_sentiment = pd.DataFrame(_rows, columns=["para_id", "label", "score", "lang"])
        _df_sentiment.to_csv(PROJECT_DIR / "sentiment.csv", index=False, encoding="utf-8-sig")
        sentiment_written = True
        print(f"\nПроанализировано абзацев: {len(_rows)}")
        _dist = Counter(r["label"] for r in _rows)
        for _lab in ("negative", "neutral", "positive"):
            print(f"  {_lab:<9}: {_dist.get(_lab, 0)}")
        if _dist.get("error"):
            print(f"  error    : {_dist['error']} (абзацы, на которых модель упала)")
        print(f"Сохранено (сырые данные для шаманов): {PROJECT_DIR / 'sentiment.csv'}")

# %% [markdown] id="md_export" tags=["md_export"]
# ## Экспорт результатов
#
# Сохраняем все таблицы в папку проекта внутри `export_results/`:
#
# - **CSV** (UTF-8 BOM, открывается в Excel) — предложения, абзацы, тезисы, ключевые слова TF-IDF, сущности, темы.
# - **JSON** — ключевые слова тем.
# - **TXT** — `тезисы.txt` (сохранён на предыдущем шаге).
#
# **Доступный текст с языковыми метками** — два формата для офлайн-чтения экранными читалками и TTS:
#
# - `accessible_text.html` — строится через `BeautifulSoup`. Корневой `<html>` имеет атрибут `lang` основного языка; каждый `<p>` получает свой `lang` (по `para_langs`), а иноязычное предложение или вставка внутри абзаца — собственный `<span lang="...">` (по `sent_langs` и `sent_wstawki`). NVDA и JAWS читают эти теги нативно и переключают голос на лету.
# - `accessible_text.docx` — собирается через `python-docx`. Для каждого `Run` свойство `<w:lang>` прописывается жёстко (`pl-PL`, `ru-RU`, `en-US`, `it-IT`, `de-DE`, `es-ES`, `fr-FR`, `fi-FI`, `is-IS`). Word, встроенный синтезатор Windows (SAPI) и сторонние читалки опираются на этот атрибут офлайн, без обращения к онлайн-детекторам.
#
# Подписи диаграмм из PDF (оси, легенды, названия категорий — распознаются по векторной графике страницы) в NLP-анализ не входят, но в HTML и DOCX остаются для чтения: отдельным абзацем рядом с тем местом текста, где стояла диаграмма.
#
# Эти файлы заменяют прежний плоский `чистый_текст_для_аудио.txt`: вместо одного языкового профиля на весь поток текста читалка теперь получает корректный язык на каждом фрагменте.

# %% id="cell_export" tags=["cell_export"]
print("--- Экспорт результатов ---")
import json

out_dir = PROJECT_DIR  # каталог уже создан в cell_corpus
exported = []

# Предложения
df_sent.to_csv(out_dir / "sentences.csv", index=False, encoding="utf-8-sig")
exported.append("sentences.csv")

# Абзацы
df_para.to_csv(out_dir / "paragraphs.csv", index=False, encoding="utf-8-sig")
exported.append("paragraphs.csv")

# Тезисы CSV + TXT
if len(df_theses) > 0:
    df_theses.to_csv(out_dir / "theses.csv", index=False, encoding="utf-8-sig")
    (out_dir / t(LANG, "theses.filename")).write_text(
        "\n".join(f"- {r['sentence']}" for _, r in df_theses.iterrows()),
        encoding="utf-8")
    exported += ["theses.csv", t(LANG, "theses.filename")]

# Ключевые слова TF-IDF
if len(df_keywords_tfidf) > 0:
    df_keywords_tfidf.to_csv(out_dir / "keywords_tfidf.csv", index=False, encoding="utf-8-sig")
    exported.append("keywords_tfidf.csv")

# Темы
if len(df_topics) > 0:
    df_topics.to_csv(out_dir / "paragraphs_with_topics.csv", index=False, encoding="utf-8-sig")
    exported.append("paragraphs_with_topics.csv")
    (out_dir / "topic_keywords.json").write_text(
        json.dumps(topic_keywords, ensure_ascii=False, indent=2), encoding="utf-8")
    exported.append("topic_keywords.json")

# Именованные сущности
if all_ents:
    pd.DataFrame(all_ents, columns=["entity","label"]).to_csv(
        out_dir / "entities.csv", index=False, encoding="utf-8-sig")
    exported.append("entities.csv")


# ============================================================
# Доступный экспорт с тегированием языка (HTML + DOCX).
# Заменяет прежний плоский «чистый_текст_для_аудио.txt»: каждый
# абзац, иноязычное предложение и иноязычная вставка (цитата, фамилия)
# получает собственный lang-атрибут, благодаря которому NVDA/JAWS/Narrator
# и встроенные TTS-движки автоматически выбирают правильный голос.
# ============================================================
# Поле `locale` основ.
from shamanic_locale import PODSTAWY

LANG_TO_LOCALE = {_k: _p["locale"] for _k, _p in PODSTAWY.items()}


def _kawalki_akapitu(ids):
    """[(текст, язык)] абзаца: предложения своего языка, вставки — своего;
    соседние куски одного языка склеены, пробел между предложениями
    достаётся предыдущему куску."""
    kawalki = []
    # Короткие предложения вне NLP (cell_para) — на своих местах; хвост
    # документа — после последнего предложения последнего абзаца.
    _koniec = len(all_sents) if ids and ids[-1] == len(all_sents) - 1 else None
    for n, k in enumerate(list(ids) + ([_koniec] if _koniec is not None else [])):
        for _t, _jl in KROTKIE_PRZED.get(k, ()):
            if kawalki:
                kawalki.append((" ", kawalki[-1][1]))
            kawalki.append((_t, _jl))
        if k == _koniec:
            break
        txt, jezyk = all_sents[k], sent_langs[k]
        if kawalki:
            kawalki.append((" ", kawalki[-1][1]))
        kursor = 0
        for a, b, wl in sent_wstawki[k]:
            if a > kursor:
                kawalki.append((txt[kursor:a], jezyk))
            kawalki.append((txt[a:b], wl))
            kursor = b
        if kursor < len(txt):
            kawalki.append((txt[kursor:], jezyk))
    scalone = []
    for txt, jezyk in kawalki:
        if scalone and scalone[-1][1] == jezyk:
            scalone[-1] = (scalone[-1][0] + txt, jezyk)
        else:
            scalone.append((txt, jezyk))
    return scalone


def _akapity_eksportu():
    """(язык абзаца, [(текст, язык)]) в порядке чтения: абзацы текста и между
    ними абзацы подписей диаграмм (вырезаны из NLP, но остаются для чтения)."""
    def _podpisi(k):
        if PODPISI_PO_AKAPICIE.get(k):
            yield LANG, [(" ".join(PODPISI_PO_AKAPICIE[k]), LANG)]
    yield from _podpisi(-1)
    if not para_sent_ids and KROTKIE_PRZED:          # текст только из коротких предложений
        yield LANG, [(" ".join(_t for _v in KROTKIE_PRZED.values() for _t, _jl in _v), LANG)]
    for _k, (_p_lang, _ids) in enumerate(zip(para_langs, para_sent_ids)):
        yield _p_lang, _kawalki_akapitu(_ids)
        yield from _podpisi(_k)


# Иноязычные отрезки — отдельный CSV (документ, смещения в нормализованном
# тексте документа, язык, вид, текст): шаманский слой и ручная проверка.
# Блок на границе документа приписан документу своего начала.
pd.DataFrame(
    [{"doc_id": _dokument(_o.start) + 1, "start": _o.start - DOC_START[_dokument(_o.start)],
      "end": _o.koniec - DOC_START[_dokument(_o.start)], "lang": _o.jezyk,
      "kind": "block" if _o.blok else "inline", "text": TEKST[_o.start:_o.koniec]}
     for _o in ODCINKI],
    columns=["doc_id", "start", "end", "lang", "kind", "text"],
).to_csv(out_dir / "language_spans.csv", index=False, encoding="utf-8-sig")
exported.append("language_spans.csv")

# --- HTML с p/span lang ---
try:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<title>Доступный текст с языковыми метками</title></head>"
        "<body></body></html>",
        "html.parser",
    )
    soup.html["lang"] = LANG  # доминирующий язык документа
    body = soup.body
    h1 = soup.new_tag("h1")
    h1.string = "Текст с языковыми метками для экранных читалок"
    body.append(h1)

    for p_lang, kawalki in _akapity_eksportu():
        p_tag = soup.new_tag("p")
        p_tag["lang"] = p_lang
        # Кусок языка абзаца — текст прямо в <p>; иноязычное предложение
        # или вставка — собственный <span lang="...">.
        for txt, jezyk in kawalki:
            if jezyk == p_lang:
                p_tag.append(txt)
            else:
                span = soup.new_tag("span")
                span["lang"] = jezyk
                span.string = txt
                p_tag.append(span)
        body.append(p_tag)

    (out_dir / "accessible_text.html").write_text(str(soup), encoding="utf-8")
    exported.append("accessible_text.html")
except ImportError as _e:
    print(f"[ВНИМАНИЕ] beautifulsoup4 недоступен: {_e} — HTML-экспорт пропущен.")
except Exception as _e:
    print(f"[ВНИМАНИЕ] Не удалось создать HTML: {_e}")

# --- DOCX с w:lang на каждом Run ---
try:
    from docx import Document
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    def _set_run_lang(run, lang_iso):
        """Жёстко прописывает язык на уровне Run через свойство <w:lang>.
        Word и SAPI читают этот атрибут офлайн, что обеспечивает корректное
        произношение без запуска онлайн-детектора.
        """
        locale = LANG_TO_LOCALE.get(lang_iso, lang_iso)
        rPr = run._element.get_or_add_rPr()
        for old in rPr.findall(qn("w:lang")):
            rPr.remove(old)
        lang_el = OxmlElement("w:lang")
        lang_el.set(qn("w:val"), locale)
        lang_el.set(qn("w:eastAsia"), locale)
        lang_el.set(qn("w:bidi"), locale)
        rPr.append(lang_el)

    docx_doc = Document()
    docx_doc.add_heading("Текст с языковыми метками", level=1)
    for _p_lang, kawalki in _akapity_eksportu():
        p = docx_doc.add_paragraph()
        for txt, jezyk in kawalki:
            _set_run_lang(p.add_run(txt), jezyk)
    docx_doc.save(out_dir / "accessible_text.docx")
    exported.append("accessible_text.docx")
except ImportError as _e:
    print(f"[ВНИМАНИЕ] python-docx недоступен: {_e} — DOCX-экспорт пропущен.")
except Exception as _e:
    print(f"[ВНИМАНИЕ] Не удалось создать DOCX: {_e}")

print(f"Файлы сохранены в папку: {out_dir.resolve()}")
for fname in exported:
    print(f"  {fname}")

# %% [markdown] id="md_summary" tags=["md_summary"]
# ## Итоговый отчёт
#
# Ячейка ниже собирает все ключевые результаты анализа в один текстовый отчёт.  
# Формат оптимизирован для чтения экранными читалками (NVDA, JAWS): только текст, без цветов, без псевдографики.

# %% id="cell_summary" tags=["cell_summary"]
print("=" * 70)
print("СВОДНЫЙ ОТЧЁТ ПО АНАЛИЗУ ТЕКСТА")
print("=" * 70)
print()
_src = SOURCE_FILE if SOURCE_FILE else "встроенный пример"
_model = MODEL_BY_LANG.get(LANG, "неизвестна")
print(f"Исходный файл             : {_src}")
print(f"Определённый язык         : {LANG_NAMES.get(LANG, LANG)} ({LANG})")
print(f"Модель spaCy              : {_model}")
print(f"Количество документов     : {len(corpus)}")
print()
total_words = sum(len(wt) for wt in word_tokens)
total_sents = sum(len(st) for st in sent_tokens)
total_content = sum(len(ft) for ft in filtered_tokens)
print(f"Всего токенов             : {total_words}")
print(f"Всего предложений         : {total_sents}")
print(f"Содержательных слов       : {total_content}")
print(f"Размер списка стоп-слов   : {len(stop_words)}")
print()
print(f"Именованных сущностей     : {len(all_ents)}")
if all_ents:
    for etype, cnt in Counter(label for _, label in all_ents).most_common():
        print(f"  {etype:<12}: {cnt}")
print()
print(f"Словарь BoW (UniGram)     : {len(vocab_uni)} терминов")
print(f"Словарь TF-IDF            : {len(feature_names)} терминов")
print()
print(f"Запрос (авто)             : \"{AUTO_QUERY}\"")
_best = ranked_order[0]
print(f"Лучший результат поиска   : Документ {_best+1} (косинус = {cosine_scores[_best]:.4f})")
print("Ранжирование документов (топ-10):")
_rank_show = min(10, len(ranked_order))
for rank, idx2 in enumerate(ranked_order[:_rank_show], 1):
    print(f"  Место {rank}: Документ {idx2+1} — оценка {cosine_scores[idx2]:.4f}")
if len(ranked_order) > _rank_show:
    print(f"  ... (показаны топ-{_rank_show} из {len(ranked_order)})")
print()
if corpus_issues:
    fixes = [(d, desc) for d, k, desc in corpus_issues if k == "исправлено"]
    warns = [(d, desc) for d, k, desc in corpus_issues if k == "предупреждение"]
    if fixes:
        print(f"Автоматически исправлено: {len(fixes)}")
        for d, desc in fixes:
            print(f"  Документ {d}: {desc}")
    if warns:
        print(f"\nПредупреждения (ручная проверка): {len(warns)}")
        for d, desc in warns:
            print(f"  Документ {d}: {desc}")
else:
    print("Проблем в тексте не обнаружено.")
print()
print("Тезисы:")
_n_theses = len(df_theses) if "df_theses" in dir() else 0
print(f"  Сформировано тезисов    : {_n_theses}")
if "df_theses" in dir() and _n_theses > 0:
    _tf = THESES_FILE if "THESES_FILE" in dir() else t(LANG, "theses.filename")
    print(f"  Сохранены в файл        : {_tf}")
    for _, row in df_theses.head(5).iterrows():
        _pid2 = int(row["para_id"])
        _prev2 = row["sentence"][:80].replace("\n"," ")
        print(f"    Абзац {_pid2:3d}: {_prev2}...")
print()
if "topic_keywords" in dir() and topic_keywords:
    print(f"Тем обнаружено            : {len(topic_keywords)}")
    for t, kws in topic_keywords.items():
        _kw = ", ".join(kws[:5])
        print(f"  Тема {t}: {_kw}")
    print()
# === Распределение языков по абзацам/предложениям ===
if "para_langs" in dir():
    from collections import Counter as _CounterSum
    _pd = _CounterSum(para_langs)
    _sd = _CounterSum(sent_langs) if "sent_langs" in dir() else _CounterSum()
    print("Распределение языков (для HTML/DOCX-экспорта):")
    print(f"  По абзацам   : {dict(_pd)}")
    if _sd:
        print(f"  По предложениям: {dict(_sd)}")
    print()
print("=" * 70)
print("Доступный экспорт с языковыми метками:")
_html_path = out_dir / "accessible_text.html" if 'out_dir' in dir() else None
_docx_path = out_dir / "accessible_text.docx" if 'out_dir' in dir() else None
if _html_path and _html_path.exists():
    _html_size = _html_path.stat().st_size
    print(f"  accessible_text.html : {_html_size:,} байт — атрибут lang на каждом <p>/<span>, читалки переключают голос автоматически")
else:
    print("  accessible_text.html : не найден (запустите ячейку экспорта)")
if _docx_path and _docx_path.exists():
    _docx_size = _docx_path.stat().st_size
    print(f"  accessible_text.docx : {_docx_size:,} байт — <w:lang> на каждом Run, корректное произношение в Word/SAPI офлайн")
else:
    print("  accessible_text.docx : не найден (запустите ячейку экспорта)")
print()
print("Конец отчёта. Все результаты совместимы с экранными читалками.")
print("=" * 70)

# %% [markdown] id="md_qa_rag" tags=["md_qa_rag"]
# ## Интерактивная система вопросов и ответов (RAG)
#
# Простой цикл «вопрос — ответ» на основе TF-IDF и косинусного сходства.  
# Введите вопрос — система найдёт 3 наиболее релевантных фрагмента текста из корпуса.
#
# Для выхода введите: **wyjście**, **выход** или **exit**.

# %% id="cell_qa_rag" tags=["cell_qa_rag"]
# ============================================================
# Интерактивная система Q&A на основе TF-IDF (RAG)
# Одиночный запрос — выполните ячейку заново для следующего вопроса.
# ============================================================
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

EXIT_WORDS = {"wyjście", "выход", "exit"}

# Строим индекс TF-IDF по абзацам (paragraphs)
_qa_texts = paragraphs if 'paragraphs' in dir() and paragraphs else corpus_nlp
_qa_stop = list(stop_words) if stop_words else "english"

_qa_tfidf = TfidfVectorizer(
    lowercase=True,
    stop_words=_qa_stop,
    min_df=1
)
try:
    _qa_matrix = _qa_tfidf.fit_transform(_qa_texts)
    print("Система Q&A готова.")
    print(f"Индекс построен по {len(_qa_texts)} фрагментам текста.")
    print("-" * 60)
except Exception as _qa_err:
    print(f"[ОШИБКА] Не удалось построить индекс TF-IDF: {_qa_err}")
    _qa_matrix = None

if _qa_matrix is not None:
    try:
        query = input("Задайте вопрос: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nСессия Q&A завершена.")
        query = ""

    if query and query.lower() not in EXIT_WORDS:
        try:
            _q_vec = _qa_tfidf.transform([query])
            _scores = linear_kernel(_q_vec, _qa_matrix).flatten()
            _top_ids = _scores.argsort()[::-1][:3]

            # Filtrujemy tylko trafienia z score >= 0.001
            relevant = [
                (frag_idx, _scores[frag_idx])
                for frag_idx in _top_ids
                if _scores[frag_idx] >= 0.001
            ]

            print()
            print(f"Вопрос: {query}")
            if relevant:
                print("Наиболее релевантные фрагменты:")
                print("-" * 60)
                for rank_q, (frag_idx, score_q) in enumerate(relevant, 1):
                    fragment = _qa_texts[frag_idx].replace("\n", " ").strip()
                    print(f"{rank_q}. (сходство: {score_q:.4f})")
                    print(f"   {fragment[:400]}")
                    print()
            else:
                print("Совпадений не найдено. Попробуйте другой запрос.")

            # === HTML-вывод + автоматическое открытие в браузере ===
            # Jupyter в браузере хардкодит <html lang="en"> и не показывает
            # подсказку перевода для страниц на localhost. VS Code Jupyter
            # тоже не предлагает перевод. Поэтому пишем тот же результат
            # в HTML-файл и открываем его в системном браузере: там
            # сработает и авто-перевод обёрток, и корректный голос TTS
            # для фрагментов корпуса (<p lang="{LANG}">).
            import html as _qa_html
            import webbrowser
            from pathlib import Path as _QAPath
            _qa_doc = [
                "<!DOCTYPE html>",
                '<html lang="ru">',
                "<head>",
                '<meta charset="utf-8">',
                f"<title>Q&amp;A: {_qa_html.escape(query)[:80]}</title>",
                "<style>body{font-family:Arial,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;line-height:1.6;color:#333}h1,h2{color:#2c3e50}article{background:#f8f9fa;border-left:4px solid #007bff;padding:1rem;margin-bottom:1rem}</style>",
                "</head>",
                "<body><main>",
                "<h1>Вопрос</h1>",
                f'<p lang="{LANG}">{_qa_html.escape(query)}</p>',
                "<h1>Найденные фрагменты</h1>",
            ]
            if relevant:
                for rank_q, (frag_idx, score_q) in enumerate(relevant, 1):
                    fragment = _qa_texts[frag_idx].replace("\n", " ").strip()
                    _qa_doc.append("<article>")
                    _qa_doc.append(f"<h2>Фрагмент {rank_q} (сходство: {score_q:.4f})</h2>")
                    _qa_doc.append(f'<p lang="{LANG}">{_qa_html.escape(fragment)}</p>')
                    _qa_doc.append("</article>")
            else:
                _qa_doc.append("<p>Совпадений не найдено.</p>")
            _qa_doc.append("</main></body></html>")
            _qa_html_path = _QAPath(PROJECT_DIR) / "qa_results.html"
            _qa_html_path.write_text("\n".join(_qa_doc), encoding="utf-8")
            print(f"Результаты также сохранены в HTML: {_qa_html_path}")
            print("Откройте файл в обычном браузере (вне Jupyter), чтобы получить авто-перевод и переключение голоса TTS на фрагментах корпуса.")
            try:
                webbrowser.open(_qa_html_path.as_uri())
            except Exception as _wb_err:
                print(f"[ИНФО] Авто-открытие браузера не удалось: {_wb_err}")

            print("-" * 60)
        except Exception as _qa_exc:
            print(f"[ОШИБКА] {_qa_exc}")
    elif query.lower() in EXIT_WORDS:
        print("Сессия Q&A завершена. До свидания!")
