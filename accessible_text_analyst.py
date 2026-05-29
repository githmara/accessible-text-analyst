# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.3
#   kernelspec:
#     display_name: analyst_env
#     language: python
#     name: analyst_env
# ---

# %% [markdown] id="md_intro" tags=["md_intro"]
# # Доступный анализ текста (spaCy · TF-IDF · KMeans)
#
# Полный конвейер текстовой аналитики с поддержкой **польского, русского, английского, итальянского, финского и исландского** языков.  
# Все результаты выводятся через `print()` — без цветовой кодировки и псевдографики.  
# Совместим с экранными читалками **NVDA** и **JAWS**.
#
# **Единственное, что нужно от пользователя:** задать путь к файлу `.pdf`, `.txt` или `.docx` в первой ячейке кода. Если файл не найден — используется встроенный пример.
#
# ---
#
# **Этапы анализа:**
#
# 1. **Загрузка корпуса** — PDF постранично (pdfplumber), TXT, DOCX (python-docx), HTML-файл или **URL** (прямой адрес страницы); BeautifulSoup удаляет навигацию, боковые панели и блоки «Похожие статьи» при загрузке из URL или HTML; встроенный пример как запасной вариант.
# 2. **Определение языка** — `lingua-language-detector` определяет преобладающий язык корпуса и одновременно служит детектором для отдельных абзацев и предложений (используется на этапе экспорта).
# 3. **Языковая модель spaCy** — автоматически выбирается модель версии **Large (lg)**: `pl_core_news_lg`, `ru_core_news_lg`, `en_core_web_lg`, `it_core_news_lg`, `fi_core_news_lg`; для исландского (`is`) — `spacy.blank("is")` + Hugging Face (IceBERT, MIM-GOLD-22). Модели подгружаются по требованию через `get_nlp(lang)`, защищённый `functools.lru_cache(maxsize=2)`: одновременно в RAM держатся не более двух моделей, остальные вытесняются по принципу LRU.
# 4. **Коррекция текста** — удаление точных повторов слов (все языки); нормализация аббревиатур с пробелами для польского (`m. in.`→`m.in.`), русского (`т. е.`→`т.е.`) и английского (`e. g.`→`e.g.`).
# 5. **Базовый NLP** — токенизация на слова и предложения, фильтрация стоп-слов, лемматизация, POS-теггинг (NOUN/VERB/ADJ/…).
# 6. **Именованные сущности (NER)** — люди, организации, места, даты и другие объекты (с частотной сводкой по всему корпусу).
# 7. **Мешок слов (CountVectorizer)** — матрица частот с языко-специфичными стоп-словами; топ-10 слов и топ-5 биграмм.
# 8. **TF-IDF и автопоиск** — запрос автоматически строится из топ-терминов корпуса; косинусное сходство гарантированно > 0.
# 9. **Структура текста** — весь корпус объединяется в поток, делится на предложения (spaCy) и группируется в абзацы по 3–6 предложений; для каждого абзаца и предложения lingua фиксирует ISO-код языка, который позже попадает в HTML/DOCX.
# 10. **Ключевые слова** — рейтинговая таблица терминов и фраз (1–3 слова) по средневзвешенному TF-IDF на уровне абзацев.
# 11. **Тезисы** — лучшее по TF-IDF-сумме предложение каждого абзаца; сохраняются в `тезисы.txt` в формате `- предложение`.
# 12. **Тематизация (KMeans)** — кластеризация абзацев по spaCy-векторам; для каждой темы — ключевые слова и пример фрагмента *(требует модели `*_md` или `*_lg` с векторами)*.
# 13. **Экспорт результатов** — CSV (UTF-8 BOM, совместимо с Excel), JSON (ключевые слова тем), TXT (тезисы) и **доступный HTML/DOCX** с атрибутом `lang` на каждом абзаце/предложении — экранные читалки автоматически переключают голос на нужный язык.
# 14. **Итоговый отчёт** — все ключевые метрики в одном текстовом блоке.

# %% id="cell_corpus" tags=["cell_corpus"]
# ============================================================
# ВВОД ДАННЫХ: путь к исходному файлу/URL берётся из config.json
# или config.ini (содержимое обоих — JSON). Скопируйте
# config.example.json в config.json (или config.example.ini в
# config.ini) и укажите source_file. Если ни один файл не найден,
# используется встроенный пример.
# ============================================================
import os, re, json
from pathlib import Path
from collections import Counter
from urllib.parse import urlparse

from shamanic_locale import t

SOURCE_FILE = ""
CUSTOM_PATTERNS = []
# Языки для OCR (easyocr). В одной инстанции Reader можно сочетать только
# языки одного скрипта: например ["ru", "en"] для кириллицы или
# ["en", "pl", "it", "fi", "is"] для латиницы. Если корпус — скан или
# изображение, выставите ocr_languages в config.json под скрипт документа.
OCR_LANGS = ["en"]
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
        _ocr_cfg = _cfg.get("ocr_languages")
        if isinstance(_ocr_cfg, list) and _ocr_cfg:
            OCR_LANGS = [str(x).strip() for x in _ocr_cfg if str(x).strip()]
        ENABLE_SENTIMENT = bool(_cfg.get("enable_sentiment", False))
        print(f"[OK] Конфигурация загружена: {_CONFIG_PATH}")
    except Exception as _e:
        print(f"[ВНИМАНИЕ] Не удалось прочитать {_CONFIG_PATH}: {_e}")
else:
    print("[ИНФО] Файл config.json/config.ini не найден — используется встроенный пример.")
    print("       Скопируйте config.example.json в config.json (или config.example.ini в config.ini)")
    print("       и задайте source_file.")

def clean_web_article_start(text, check_window=400):
    """Remove common web-scraping artifacts from extracted article text:
    - Photo credits/view counters: "Fot. CPK 521", standalone "CPK 524"
    - Doubled metadata from responsive layouts: "Author Date Author Date"
    """
    if not text:
        return text
    # Remove photo credit patterns (Polish "Fot." = photo)
    text = re.sub(r"\bFot\.\s+[A-Z][A-Za-z0-9]*\.?\s*\d*\s*", " ", text)
    # Remove ALL-CAPS word + 3-digit number that leaked in as view/photo counter
    text = re.sub(r"\b[A-Z]{2,}\s+\d{3,}\s+", " ", text)
    # Remove doubled short phrases in the first check_window chars
    # (responsive design often repeats title/author/date for mobile+desktop)
    head = text[:check_window]
    m = re.search(r"(.{10,60})\s+\1", head)
    if m:
        repeated = re.escape(m.group(1))
        text = re.sub(r"(" + repeated + r")\s+\1", r"\1", text, count=1)
    return re.sub(r"\s+", " ", text).strip()

def clean_pdf_text(s: str) -> str:
    """Базовая очистка текста из PDF: мягкие дефисы, разорванные слова, пробелы."""
    if not s:
        return ""
    s = s.replace("\u00ad", "")              # мягкий дефис
    s = re.sub(r"(\w)-\n(\w)", r"\1\2", s)  # склейка слов через перенос
    s = s.replace("\n", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _norm_line(line: str) -> str:
    """Нормализация строки для сравнения: убираем ведущие/замыкающие цифры."""
    s = re.sub(r"^\s*\d+\s*", "", line.strip())
    s = re.sub(r"\s*\d+\s*$", "", s.strip())
    return re.sub(r"\s+", " ", s).lower().strip()

# Структурные маркеры сценариев, пьес и иных текстов с повторяющейся
# разметкой границ. Эти строки могут многократно встречаться на разных
# страницах PDF (например, [scena 1] на каждой странице длинной сцены),
# но НЕ являются колонтитулами и не должны удаляться эвристикой
# strip_repeated_headers — иначе экранизация теряет границы сцен,
# обозначение «[koniec]», «[napis na ekranie]» и подобное.
_STRUCTURAL_PATTERNS = [
    re.compile(r"^\s*\[[^\]]+\]\s*$"),   # [scena 1], [koniec], [napis na ekranie]
    re.compile(r"^\s*\([^)]+\)\s*$"),    # (didaskalia)
    re.compile(
        r"^\s*(?:"
        # ru (сцены/акты + главы/части)
        r"АКТ|ДЕЙСТВИЕ|СЦЕНА|КАРТИНА|ЯВЛЕНИЕ|ЭПИЛОГ|ПРОЛОГ|ФИНАЛ|КОНЕЦ|"
        r"ГЛАВА|ЧАСТЬ|КНИГА|РАЗДЕЛ|"
        # pl (sceny/akty + rozdziały)
        r"AKT|SCENA|OBRAZ|EPILOG|PROLOG|FINAŁ|KONIEC|"
        r"ROZDZIAŁ|CZĘŚĆ|KSIĘGA|SEKCJA|"
        # en (scenes/acts + chapters; screenplay headings)
        r"ACT|SCENE|EPILOGUE|PROLOGUE|FINALE|END|"
        r"CHAPTER|PART|BOOK|SECTION|"
        r"FADE\s+IN|FADE\s+OUT|CUT\s+TO|INT\.|EXT\.|"
        # it (scene/atti + capitoli)
        r"ATTO|EPILOGO|PROLOGO|FINE|"
        r"CAPITOLO|PARTE|LIBRO|SEZIONE|"
        # fi (näytökset/kohtaukset + luvut)
        r"NÄYTÖS|KOHTAUS|LOPPU|EPILOGI|PROLOGI|"
        r"LUKU|OSA|KIRJA|JAKSO|"
        # is (þættir/atriði + kaflar)
        r"ÞÁTTUR|ATRIÐI|ENDIR|EPILOGUR|FORLEIKUR|"
        r"KAFLI|HLUTI|BÓK"
        r")\b",
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


def strip_repeated_headers(raw_pages, min_fraction=0.25, max_line_chars=150):
    """Удаляет повторяющиеся колонтитулы.
    Строки, встречающиеся (после удаления цифр) в >= min_fraction страниц,
    считаются колонтитулами и удаляются из всех страниц.

    Исключение: строки, соответствующие _STRUCTURAL_PATTERNS (маркеры
    сцен, актов и т.п. в сценариях и пьесах), сохраняются всегда — даже
    если они формально подпадают под порог повторов. Без этого
    исключения PDF-сценарии теряли бы границы сцен и подобные пометки.
    """
    threshold = max(2, int(len(raw_pages) * min_fraction))
    line_counts = Counter()
    for page in raw_pages:
        seen = set()
        for line in page.splitlines():
            if not line.strip() or len(line.strip()) > max_line_chars:
                continue
            if _is_structural_line(line):
                # Защищённая строка не должна попадать в кандидаты —
                # иначе порог может быть достигнут и она исчезла бы
                # из всех страниц при удалении.
                continue
            n = _norm_line(line)
            if len(n) > 5 and n not in seen:
                line_counts[n] += 1
                seen.add(n)
    boilerplate = {n for n, c in line_counts.items() if c >= threshold}
    protected = 0
    cleaned = []
    for page in raw_pages:
        kept = []
        for line in page.splitlines():
            if _is_structural_line(line):
                kept.append(line)
                protected += 1
                continue
            if _norm_line(line) not in boilerplate:
                kept.append(line)
        cleaned.append("\n".join(kept))
    if protected:
        print(f"  Защищено структурных маркеров (сцены/акты/didaskalia): {protected}")
    return cleaned, boilerplate

# ============================================================
# OCR: распознавание сканов PDF и изображений через easyocr.
# Загружаем Reader лениво — модели ~70 МБ скачиваются при первом вызове.
# ============================================================
_OCR_READER = None
_OCR_READER_LANGS = None


def _silence_ocr_progress():
    """Глушит tqdm-прогрессбары easyocr/torch, чтобы вывод оставался
    дружелюбным к экранным дикторам (NVDA/JAWS)."""
    os.environ.setdefault("TQDM_DISABLE", "1")
    try:
        from functools import partialmethod
        from tqdm import tqdm
        tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)
    except Exception:
        pass


def _get_ocr_reader(langs):
    """Возвращает (и кэширует) easyocr.Reader для заданного списка языков.
    При смене языков пересоздаёт инстанс."""
    global _OCR_READER, _OCR_READER_LANGS
    key = tuple(langs)
    if _OCR_READER is not None and _OCR_READER_LANGS == key:
        return _OCR_READER
    try:
        _silence_ocr_progress()
        import easyocr
    except ImportError:
        print("[ВНИМАНИЕ] easyocr не установлен. Выполните: pip install easyocr")
        return None
    print(f"  Инициализация OCR (easyocr, языки: {list(langs)})...")
    try:
        _OCR_READER = easyocr.Reader(list(langs), gpu=False, verbose=False)
        _OCR_READER_LANGS = key
    except Exception as _e:
        print(f"[ВНИМАНИЕ] Не удалось инициализировать easyocr: {_e}")
        return None
    return _OCR_READER


def _ocr_image_array(image_or_path, langs):
    """Запускает OCR на массиве numpy, PIL-объекте или пути к файлу.
    Возвращает текст, склеенный по строкам/абзацам."""
    reader = _get_ocr_reader(langs)
    if reader is None:
        return ""
    try:
        results = reader.readtext(image_or_path, detail=0, paragraph=True)
    except Exception as _e:
        print(f"[ВНИМАНИЕ] OCR не смог обработать изображение: {_e}")
        return ""
    return "\n".join(s for s in results if s and s.strip())


def _pdf_ocr_pages(path, langs):
    """Рендерит PDF постранично через pypdfium2 и распознаёт текст.
    Возвращает список текстов (по странице)."""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        print("[ВНИМАНИЕ] pypdfium2 не установлен. Выполните: pip install pypdfium2")
        return []
    try:
        import numpy as np
    except ImportError:
        print("[ВНИМАНИЕ] numpy не установлен — нужен для OCR PDF.")
        return []
    pdf = pdfium.PdfDocument(path)
    pages_text = []
    total = len(pdf)
    try:
        for i in range(total):
            page = pdf[i]
            # scale=2.0 → ~144 DPI, разумный баланс качества OCR и скорости
            bitmap = page.render(scale=2.0)
            pil_img = bitmap.to_pil()
            arr = np.array(pil_img)
            text = _ocr_image_array(arr, langs)
            page.close()
            if text.strip():
                pages_text.append(text)
            print(f"  OCR: страница {i+1}/{total} — {len(text)} символов.")
    finally:
        pdf.close()
    return pages_text


def load_image(path):
    """Распознаёт текст с изображения через easyocr и возвращает его
    как список из одной «псевдостраницы»."""
    print(f"  Изображение: запуск OCR (языки: {OCR_LANGS})...")
    text = _ocr_image_array(path, OCR_LANGS)
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


def load_pdf(path):
    """Загружает PDF постранично, удаляет повторяющиеся колонтитулы, очищает текст.
    Если ни одна страница не дала извлекаемого текста — считаем PDF сканом
    и запускаем OCR (pypdfium2 + easyocr)."""
    try:
        import pdfplumber
    except ImportError:
        print("[ВНИМАНИЕ] pdfplumber не установлен. Выполните: pip install pdfplumber")
        return []
    raw_pages, skipped = [], 0
    with pdfplumber.open(path) as pdf:
        total = len(pdf.pages)
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text.strip():
                raw_pages.append(text)
            else:
                skipped += 1
    # Если pdfplumber не извлёк ни одной страницы текста — типичный скан.
    # Запускаем OCR через pypdfium2 + easyocr.
    if not raw_pages and total > 0:
        print(f"  PDF: ни одна из {total} страниц не содержит извлекаемого текста.")
        print(f"  Предполагается, что это скан. Запуск OCR (языки: {OCR_LANGS})...")
        raw_pages = _pdf_ocr_pages(path, OCR_LANGS)
        if not raw_pages:
            print("  [ВНИМАНИЕ] OCR не вернул текста ни на одной странице.")
            return []
        skipped = max(0, total - len(raw_pages))
        print(f"  OCR PDF: распознано страниц {len(raw_pages)} из {total}.")
    # Удаляем повторяющиеся колонтитулы до объединения строк
    cleaned_raw, removed_bp = strip_repeated_headers(raw_pages)
    if removed_bp:
        print(f"  Удалено {len(removed_bp)} повторяющихся колонтитулов:")
        for bp in sorted(removed_bp)[:5]:
            print(f"    - '{bp[:70]}'")
        if len(removed_bp) > 5:
            print(f"    ... и ещё {len(removed_bp)-5}")
    # Применяем финальную очистку
    pages = [p for p in (clean_pdf_text(r) for r in cleaned_raw) if p]
    print(f"  PDF: {total} страниц, загружено {len(pages)}, пропущено {skipped}.")
    return pages

def load_txt(path, page_size=2000):
    """Загружает текстовый файл и разбивает на псевдостраницы."""
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    pages, text = [], raw.strip()
    # Применяем CUSTOM_PATTERNS
    if CUSTOM_PATTERNS:
        for _cp in CUSTOM_PATTERNS:
            text = re.sub(_cp, "", text)
        text = re.sub(r"\\s+", " ", text).strip()
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


def load_docx(path, page_size=2000):
    """Загружает файл .docx и извлекает текст из всех абзацев документа."""
    try:
        from docx import Document
    except ImportError:
        print("[ВНИМАНИЕ] python-docx не установлен. Выполните: pip install python-docx")
        return []
    doc = Document(path)
    raw = "  ".join(p.text for p in doc.paragraphs if p.text.strip())
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
# Покрывают все поддерживаемые языки: pl, ru, en, it, fi, is.
# ============================================================
RELATED_ARTICLES_STOPWORDS = [
    # Polski
    "podobne artykuły", "podobne wpisy", "powiązane artykuły", "powiązane wpisy",
    "polecane artykuły", "polecamy", "czytaj też", "czytaj także",
    "również cię zainteresuje", "może cię zainteresować", "zobacz również",
    "więcej z", "więcej na ten temat",
    # Русский
    "похожие статьи", "похожие материалы", "подобные статьи",
    "читайте также", "смотрите также", "вам также может понравиться",
    "рекомендуем", "ещё по теме",
    # English
    "related articles", "related posts", "see also", "read also",
    "you may also like", "you might also like", "may also like",
    "more from", "more like this", "trending now",
    "recommended for you", "you might enjoy",
    # Italiano
    "articoli correlati", "leggi anche", "potrebbe interessarti anche",
    "scopri di più", "ti potrebbe interessare", "altri articoli",
    # Suomi
    "aiheeseen liittyviä artikkeleita", "lue myös", "lisää aiheesta",
    "saatat pitää myös", "katso myös", "lisää aiheeseen liittyen",
    # Íslenska
    "tengdar greinar", "lesa meira", "sjá einnig", "tengt efni",
    "þér gæti einnig líkað",
]

def load_html(path, page_size=2000):
    """Извлекает основной текст из HTML-файла через BeautifulSoup.
    Удаляет: навигацию, шапку/подвал, боковые панели, блоки
    «Похожие статьи» / «Podobne artykuły» и тексты ссылок-меню.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("[ВНИМАНИЕ] beautifulsoup4 не установлен: pip install beautifulsoup4 lxml")
        return []
    with open(path, encoding="utf-8", errors="replace") as _f:
        html = _f.read()
    soup = BeautifulSoup(html, "html.parser")
    # 1. Remove tags that never contain article text
    for tag in soup(["script","style","nav","header","footer","aside",
                      "noscript","form","button","iframe","figure"]):
        tag.decompose()
    # 2. Find the main content container
    main = (soup.find("main") or soup.find("article")
            or soup.find(id=lambda x: x and any(k in x.lower()
                         for k in ("content","article","main","post","story")))
            or soup.find(class_=lambda x: x and any(k in " ".join(x).lower()
                         for k in ("entry-content","post-content","article-body",
                                   "article-content","story-body"))))
    if not main:
        # last resort: largest block
        candidates = [el for el in soup.find_all(["article","section","div"])
                       if el.get_text(strip=True)]
        main = max(candidates, key=lambda e: len(e.get_text()), default=soup)
    # 3. Remove nav/boilerplate elements INSIDE main (not globally)
    _NAV_INNER = ["related","podobne","powiązane","comment","komentarz",
                  "social","share","advertisement","reklama","banner","popup",
                  "widget","subscribe","newsletter","sidebar","correlati",
                  "liittyv","tengd"]
    for el in list(main.find_all(True)):
        if not el.attrs:
            continue
        _cls = " ".join(el.get("class") or []).lower()
        _id  = (el.get("id") or "").lower()
        if any(p in _cls or p in _id for p in _NAV_INNER):
            el.decompose()
    # 4. Cut off "Podobne artykuły" / "Related articles" sections
    for hdr in main.find_all(["h1","h2","h3","h4","h5","p","div","section"]):
        if any(sw in hdr.get_text().lower() for sw in RELATED_ARTICLES_STOPWORDS):
            for sib in list(hdr.next_siblings):
                sib.decompose() if hasattr(sib, "decompose") else None
            hdr.decompose()
            break
    # 5. Extract, normalise and clean web artifacts
    raw_text = re.sub(r"\s+", " ", main.get_text(separator=" ", strip=True)).strip()
    raw_text = clean_web_article_start(raw_text)
    if not raw_text:
        print("[ВНИМАНИЕ] Не удалось извлечь текст из HTML.")
        return []
    pages = []
    text = raw_text
    while len(text) > page_size:
        split_at = text.rfind(" ", 0, page_size)
        if split_at == -1:
            split_at = page_size
        pages.append(text[:split_at].strip())
        text = text[split_at:].strip()
    if text:
        pages.append(text)
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
        from bs4 import BeautifulSoup
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
    soup = BeautifulSoup(html, "html.parser")
    # 1. Remove tags that never contain article text
    for tag in soup(["script","style","nav","header","footer","aside",
                      "noscript","form","button","iframe","figure"]):
        tag.decompose()
    # 2. Find the main content container
    main = (soup.find("main") or soup.find("article")
            or soup.find(id=lambda x: x and any(k in x.lower()
                         for k in ("content","article","main","post","story")))
            or soup.find(class_=lambda x: x and any(k in " ".join(x).lower()
                         for k in ("entry-content","post-content","article-body",
                                   "article-content","story-body"))))
    if not main:
        candidates = [el for el in soup.find_all(["article","section","div"])
                       if el.get_text(strip=True)]
        main = max(candidates, key=lambda e: len(e.get_text()), default=soup)
    # 3. Remove nav/boilerplate elements INSIDE main (not globally)
    _NAV_INNER = ["related","podobne","powiązane","comment","komentarz",
                  "social","share","advertisement","reklama","banner","popup",
                  "widget","subscribe","newsletter","sidebar","correlati",
                  "liittyv","tengd"]
    for el in list(main.find_all(True)):
        if not el.attrs:
            continue
        _cls = " ".join(el.get("class") or []).lower()
        _id  = (el.get("id") or "").lower()
        if any(p in _cls or p in _id for p in _NAV_INNER):
            el.decompose()
    # 4. Cut off "Podobne artykuły" / "Related articles" sections
    for hdr in main.find_all(["h1","h2","h3","h4","h5","p","div","section"]):
        if any(sw in hdr.get_text().lower() for sw in RELATED_ARTICLES_STOPWORDS):
            for sib in list(hdr.next_siblings):
                sib.decompose() if hasattr(sib, "decompose") else None
            hdr.decompose()
            break
    # 5. Extract, normalise and clean web artifacts
    raw_text = re.sub(r"\s+", " ", main.get_text(separator=" ", strip=True)).strip()
    raw_text = clean_web_article_start(raw_text)
    if not raw_text:
        print("[ВНИМАНИЕ] Не удалось извлечь текст со страницы.")
        return []
    pages, text = [], raw_text
    while len(text) > page_size:
        split_at = text.rfind(" ", 0, page_size)
        if split_at == -1:
            split_at = page_size
        pages.append(text[:split_at].strip())
        text = text[split_at:].strip()
    if text:
        pages.append(text)
    print(f"  URL: извлечено {len(raw_text)} символов, "
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
    elif ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"):
        corpus = load_image(SOURCE_FILE)
    else:
        print(f"[ВНИМАНИЕ] Неизвестное расширение: {ext}. "
              f"Поддерживаются: .pdf, .txt, .html, .docx, .png, .jpg, .jpeg, .tif, .tiff, .bmp, .webp")
elif SOURCE_FILE:
    print(f"[ВНИМАНИЕ] Источник не найден: {SOURCE_FILE!r}. Используется встроенный пример.")

_used_fallback = False
if not corpus:
    print("Используется встроенный корпус-пример (3 документа).")
    corpus = FALLBACK_CORPUS
    _used_fallback = True

corpus = [c for c in corpus if c.strip()]
_N = len(corpus)
print(f"\nКорпус готов: {_N} документ(ов).")
_show = min(5, _N)
for i in range(_show):
    _prev = corpus[i].strip().replace("\n", " ")[:80]
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
# ## 1) Определение языка (lingua)
#
# Используется библиотека [`lingua-language-detector`](https://github.com/pemistahl/lingua-py) — статистический детектор на основе n-грамм и словарей. На коротких фрагментах и при частых переключениях языка она заметно точнее `langdetect`, что критично для пер-абзацного и пер-предложного тегирования.
#
# **Архитектура:**
#
# - На этом шаге детектор определяет **преобладающий язык** всего корпуса и сохраняет его в глобальную переменную `LANG`. Этот код выбирает модель spaCy для основного NLP-конвейера.
# - Глобальный объект `LANG_DETECTOR` и функция `detect_lang(text)` остаются доступными в последующих ячейках. На шаге «Структура текста» они применяются к каждому абзацу и каждому предложению, формируя списки `para_langs` и `sent_langs`.
# - Эти списки потребляет ячейка экспорта: каждый `<p lang="...">` в HTML и каждый `Run` в DOCX получает корректный ISO-код, и экранная читалка (NVDA, JAWS, Narrator, VoiceOver) автоматически переключает голос/произношение на нужный язык.
#
# Поддерживаемые языки: **польский** (`pl`), **русский** (`ru`), **английский** (`en`), **итальянский** (`it`), **финский** (`fi`), **исландский** (`is`).
#
# > Если корпус содержит смешанные языки, преобладающий язык получает spaCy-модель, остальные — отмечаются в HTML/DOCX через атрибут `lang`.

# %% id="cell_langdet" tags=["cell_langdet"]
# ============================================================
# Определение языка через lingua-language-detector.
# Глобальный детектор LANG_DETECTOR доступен в последующих ячейках
# для распознавания языка отдельных абзацев и предложений.
# ============================================================
import warnings
warnings.filterwarnings("ignore")
from lingua import Language, LanguageDetectorBuilder
from collections import Counter

LANG_NAMES = {"en": "английский", "pl": "польский", "ru": "русский",
              "it": "итальянский", "fi": "финский", "is": "исландский"}
SUPPORTED_LANGS = set(LANG_NAMES.keys())

# Lingua: статичный набор поддерживаемых языков.
# Точность детектора заметно выше langdetect на коротких фрагментах
# и при частых переключениях языка внутри документа.
_LINGUA_LANGS = [Language.ENGLISH, Language.POLISH, Language.RUSSIAN,
                 Language.ITALIAN, Language.FINNISH, Language.ICELANDIC]
LANG_DETECTOR = LanguageDetectorBuilder.from_languages(*_LINGUA_LANGS).build()


def detect_lang(text):
    """Возвращает ISO 639-1 код в нижнем регистре или None.
    Используется как для целого корпуса, так и для отдельных абзацев/предложений
    при формировании HTML/DOCX-экспорта с lang-атрибутами.
    """
    if not text or len(text.strip()) < 3:
        return None
    try:
        lang_obj = LANG_DETECTOR.detect_language_of(text)
    except Exception:
        return None
    if lang_obj is None:
        return None
    return lang_obj.iso_code_639_1.name.lower()


def detect_corpus_language(texts):
    """Определяет преобладающий язык корпуса.
    Возвращает ISO-код победителя (например, 'fi'). Документы с иным языком
    отмечаются в логе, чтобы пользователь видел гетерогенность корпуса;
    позднее ячейка экспорта расставит lang-атрибуты на каждом абзаце.
    """
    detections = [detect_lang(t[:1000]) for t in texts]
    valid = [l for l in detections if l]
    if not valid:
        print("[ВНИМАНИЕ] Язык не определён. Используется английский.")
        return "en"
    counts = Counter(valid)
    winner = "en"
    for lang, _ in counts.most_common():
        if lang in SUPPORTED_LANGS:
            winner = lang
            break
    outliers = [i for i, l in enumerate(detections) if l and l != winner]
    if outliers:
        print(f"Преобладающий язык: {LANG_NAMES.get(winner, winner)} ({winner})")
        print(f"Документов с иным языком: {len(outliers)} (будут отмечены "
              f"в HTML/DOCX через атрибут lang)")
        for idx in sorted(outliers)[:10]:
            print(f"  Документ {idx+1}: определён как '{detections[idx]}'")
        if len(outliers) > 10:
            print(f"  ... и ещё {len(outliers)-10}")
    else:
        print(f"Язык определён единогласно: "
              f"{LANG_NAMES.get(winner, winner)} ({winner})")
    print(f"Всего документов: {len(texts)}, типичных: "
          f"{len(valid)-len(outliers)}, нетипичных: {len(outliers)}")
    print(f"Все определения: {dict(counts)}")
    return winner


print("--- Определение языка (lingua) ---")
LANG = detect_corpus_language(corpus)
print(f"\n[РЕЗУЛЬТАТ] Выбран язык: {LANG_NAMES.get(LANG, LANG)} ({LANG})")

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
# | Finnish | `fi` | `fi_core_news_lg` |
# | Icelandic | `is` | `spacy.blank("is")` + IceBERT (векторы) + MIM-GOLD-22 (NER) |
#
# Если модель не установлена, ноутбук использует базовый токенизатор (`spacy.blank`) и сообщает команду для установки.

# %% id="cell_model" tags=["cell_model"]
import spacy
from functools import lru_cache

MODEL_BY_LANG = {
    "en": "en_core_web_lg",
    "pl": "pl_core_news_lg",
    "ru": "ru_core_news_lg",
    "it": "it_core_news_lg",
    "fi": "fi_core_news_lg",
}

# Hugging Face модели для исландского (нет в spaCy):
HF_IS_VECTORS = "mideind/IceBERT-base"
HF_IS_NER = "mideind/icelandic-ner-MIM-GOLD-22"


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

    # --- Векторы через IceBERT-base ---
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

    # --- NER через icelandic-ner-MIM-GOLD-22 ---
    try:
        print(f"  Загрузка NER: {HF_IS_NER} ...")
        _is_ner = pipeline(
            "token-classification",
            model=HF_IS_NER,
            aggregation_strategy="simple",
        )

        @Language.component("icelandic_ner")
        def _icelandic_ner_pipe(doc):
            from spacy.tokens import Span
            text = doc.text or ""
            if not text.strip():
                return doc
            try:
                results = _is_ner(text[:5000]) or []
            except Exception:
                return doc
            spans = []
            for r in results:
                start_c = int(r.get("start", 0))
                end_c = int(r.get("end", 0))
                label = str(r.get("entity_group") or r.get("entity") or "MISC")
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


def _load_nlp_model_uncached(lang):
    """Внутренняя загрузка модели без кэша. Используется через get_nlp()."""
    if lang == "is":
        print("[ИНФО] Для исландского spaCy не имеет полной модели — подключаем модели Hugging Face.")
        nlp_ = spacy.blank("is")
        if "sentencizer" not in nlp_.pipe_names:
            nlp_.add_pipe("sentencizer")
        nlp_ = _build_icelandic_pipeline(nlp_)
        return nlp_
    model_name = MODEL_BY_LANG.get(lang, "en_core_web_lg")
    try:
        nlp_ = spacy.load(model_name)
        print(f"[OK] Загружена модель spaCy: {model_name}")
        print(f"     Компоненты конвейера: {nlp_.pipe_names}")
        return nlp_
    except OSError:
        print(f"[ВНИМАНИЕ] Модель '{model_name}' не установлена.")
        print(f"  Установите: python -m spacy download {model_name}")
        print(f"  Доступные модели (lg):")
        print(f"    python -m spacy download en_core_web_lg")
        print(f"    python -m spacy download pl_core_news_lg")
        print(f"    python -m spacy download ru_core_news_lg")
        print(f"    python -m spacy download it_core_news_lg")
        print(f"    python -m spacy download fi_core_news_lg")
        valid_blanks = {"en", "pl", "ru", "it", "fi"}
        nlp_ = spacy.blank(lang if lang in valid_blanks else "en")
        if "sentencizer" not in nlp_.pipe_names:
            nlp_.add_pipe("sentencizer")
        return nlp_


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
# - Удаление точных повторов слов (`the the`, `jest jest`, `что что` и т.п.)
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
ABBREV_BY_LANG = {
    "pl": [
        # m.in. – między innymi (różne zapisy z brakiem lub nadmiarem kropek/spacji)
        (r"\bm\.\s*in\.?,?\b",        "m.in."),
        (r"\bmi\.in\.?\b",              "m.in."),
        (r"\bm\.\s+in\.",               "m.in."),
        # np. – na przykład
        (r"\bnp\.?,?\s",                 "np. "),
        (r"\bn\.\s*p\.\b",             "np."),
        # tzw. – tak zwany
        (r"\btzw\.?,?\s",                "tzw. "),
        (r"\bt\.\s*z\.\s*w\.\b",    "tzw."),
        # tzn. – to znaczy
        (r"\btzn\.?,?\s",                "tzn. "),
        (r"\bt\.\s*z\.\s*n\.\b",    "tzn."),
        # tj. – to jest
        (r"\bt\.\s*j\.\b",             "tj."),
        # itd. / itp.
        (r"\bi\.\s*t\.\s*d\.\b",    "itd."),
        (r"\bi\.\s*t\.\s*p\.\b",    "itp."),
        # ww. – wyżej wymieniony
        (r"\bww\.?,?\s",                 "ww. "),
        # jw. – jak wyżej
        (r"\bjw\.?,?\s",                 "jw. "),
        # dr / prof / mgr / inż – tytuły
        (r"\bdr\s+hab\.?\s",            "dr hab. "),
        (r"\bdr\.?\s",                   "dr "),
        (r"\bprof\.?\s",                 "prof. "),
        (r"\bmgr\.?\s",                  "mgr "),
        (r"\bin\u017c\.?\s",            "in\u017c. "),
        # ul. / al. / pl. – adresy
        (r"\bul\.?,?\s",                 "ul. "),
        (r"\bal\.?,?\s",                 "al. "),
        (r"\bpl\.?,?\s",                 "pl. "),
        # r. – rok; nr – numer; str. – strona
        (r"\br\.?,?\s",                  "r. "),
        (r"\bnr\s*\.?,?\s",             "nr "),
        (r"\bstr\.?,?\s",                "str. "),
    ],
    "ru": [
        (r"\b\u0442\.\s+\u0435\.",             "\u0442.\u0435."),    # т. е. → т.е.
        (r"\b\u0442\.\s+\u0434\.",             "\u0442.\u0434."),    # т. д. → т.д.
        (r"\b\u0442\.\s+\u043f\.",             "\u0442.\u043f."),    # т. п. → т.п.
        (r"\b\u0442\.\s+\u043a\.",             "\u0442.\u043a."),    # т. к. → т.к.
        (r"\b\u0442\.\s+\u043d\.",             "\u0442.\u043d."),    # т. н. → т.н.
        (r"\b\u0438\.\s+\u043e\.",             "\u0438.\u043e."),    # и. о. → и.о.
        (r"\b\u0441\.\s+\u0433\.",             "\u0441.\u0433."),    # с. г. → с.г.
        (r"\b\u043d\.\s+\u044d\.",             "\u043d.\u044d."),    # н. э. → н.э.
        (r"\b\u0432\.\s+\u0442\.\s+\u0447\.", "\u0432.\u0442.\u0447."),  # в. т. ч. → в.т.ч.
        # и т.д. / и т.п. – с пробелом внутри
        (r"\u0438\s+\u0442\.\s*\u0434\.",     "\u0438 \u0442.\u0434."),   # и т.д.
        (r"\u0438\s+\u0442\.\s*\u043f\.",     "\u0438 \u0442.\u043f."),   # и т.п.
        # проф. / акад. / др. – титулы
        (r"\b\u043f\u0440\u043e\u0444\.?,?\s", "\u043f\u0440\u043e\u0444. "),  # проф.
        (r"\b\u0430\u043a\u0430\u0434\.?,?\s", "\u0430\u043a\u0430\u0434. "), # акад.
        (r"\b\u0434\u043e\u0446\.?,?\s",        "\u0434\u043e\u0446. "),         # доц.
        # ул. / пр. / пер. – адреса
        (r"\b\u0443\u043b\.?,?\s",               "\u0443\u043b. "),    # ул.
        (r"\b\u043f\u0440\.?,?\s",               "\u043f\u0440. "),    # пр.
        (r"\b\u043f\u0435\u0440\.?,?\s",        "\u043f\u0435\u0440. "),  # пер.
    ],
    "en": [
        (r"\be\.\s+g\.",       "e.g."),    # e. g. → e.g.
        (r"\be\.g,",             "e.g.,"),   # e.g, → e.g.,
        (r"\bi\.\s+e\.",       "i.e."),    # i. e. → i.e.
        (r"\bi\.e,",             "i.e.,"),   # i.e, → i.e.,
        (r"\bU\.\s+S\.",       "U.S."),    # U. S. → U.S.
        (r"\bU\.\s+K\.",       "U.K."),    # U. K. → U.K.
        (r"\betc\s+\.",         "etc."),    # etc . → etc.
        (r"\bvs\.\s+",          "vs. "),    # vs.  → vs. (normalizacja)
        (r"\bDr\.\s+",          "Dr. "),    # Dr.  (tytuł)
        (r"\bMr\.\s{2,}",       "Mr. "),    # Mr.  (tytuł)
        (r"\bMrs\.\s{2,}",      "Mrs. "),   # Mrs. (tytuł)
        (r"\bProf\.\s+",        "Prof. "),  # Prof.
        (r"\bSt\.\s+",          "St. "),    # St. (Saint / Street)
        (r"\bFig\.\s+",         "Fig. "),   # Fig. (Figure)
        (r"\bNo\.\s+",          "No. "),    # No. (Number)
        (r"\bp\.\s+",           "p. "),     # p. (page)
        (r"\bpp\.\s+",          "pp. "),    # pp. (pages)
    ],
    "it": [
        (r"\bad\s+es\.?,?\b",  "ad es."),  # ad esempio
        (r"\becc\.?,?\b",       "ecc."),    # eccetera
        (r"\bdott\.?,?\s",      "dott. "),  # dottore
        (r"\bprof\.?,?\s",      "prof. "),  # professore
        (r"\bpagg?\.?,?\s",     "pag. "),   # pagina
        (r"\bsig\.?,?\s",       "sig. "),   # signore
        (r"\bsig\.?ra\.?,?\s", "sig.ra "), # signora
        (r"\bart\.?,?\s",       "art. "),   # articolo
        (r"\bcap\.?,?\s",       "cap. "),   # capitolo
        (r"\bn\.\s*ro?\.?\b", "n."),      # numero
        (r"\bcfr\.?,?\s",       "cfr. "),   # confronta
        (r"\bvol\.?,?\s",       "vol. "),   # volume
        (r"\bpag\.?,?\s",       "pag. "),   # pagina (alias)
    ],
    "fi": [
        (r"\besim\.?,?\s",      "esim. "),  # esimerkiksi
        (r"\bjne\.?,?\b",       "jne."),    # ja niin edelleen
        (r"\bym\.?,?\b",        "ym."),     # ynnä muuta
        (r"\bns\.?,?\s",        "ns. "),    # niin sanottu
        (r"\btms\.?,?\b",       "tms."),    # tai muuta sellaista
        (r"\bko\.?,?\s",        "ko. "),    # kyseinen / kyseessä oleva
        (r"\bpo\.?,?\s",        "po. "),    # pohjoiseen / pohjoinen
        (r"\bvt\.?,?\s",        "vt. "),    # virkaatekevä
        (r"\bprof\.?,?\s",      "prof. "),  # professori
        (r"\bdr\.?,?\s",        "dr. "),    # tohtori
        (r"\bos\.?,?\s",        "os. "),    # osasto
        (r"\bv\.?,?\s",         "v. "),     # vuosi / versus
    ],
    "is": [
        (r"\bt\.\s*d\.?,?\b",             "t.d."),      # til dæmis
        (r"\b\u00fe\.\s*e\.?,?\b",        "\u00fe.e."),  # þ.e. – það er
        (r"\bm\.\s*a\.?,?\b",             "m.a."),      # meðal annars
        (r"\bu\.\s*\u00fe\.\s*b\.?,?\b", "u.\u00fe.b."),  # u.þ.b. – um það bil
        (r"\bo\.\s*s\.\s*frv\.?,?\b",  "o.s.frv."),  # og svo framvegis
        (r"\bdr\.?,?\s",                    "dr. "),       # doktor
        (r"\bprof\.?,?\s",                  "prof. "),     # prófessor
        (r"\bbls\.?,?\s",                   "bls. "),      # blaðsíða (strona)
        (r"\bskv\.?,?\s",                   "skv. "),      # samkvæmt (zgodnie z)
        (r"\bfh\.?,?\s",                    "fh. "),       # fyrir hönd (w imieniu)
    ],
}
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
    # 2. Повтор слова (все языки, без учёта регистра)
    def _fix_repeat(m):
        w = m.group(1)
        corpus_issues.append((i, "исправлено",
            f"повтор слова: '{w} {w}' → '{w}'"))
        return w
    fixed = re.sub(r"\b(\w{2,})\s+\1\b", _fix_repeat, fixed,
                   flags=re.IGNORECASE)
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
# spaCy также сегментирует текст на предложения — полезно для анализа структуры, экстрактивного саммари (тезисы) и пер-предложного определения языка перед HTML/DOCX-экспортом.

# %% id="cell_tok" tags=["cell_tok"]
print("--- Токенизация ---")
docs = [nlp(t) for t in corpus]

word_tokens = [[tok.text for tok in doc if not tok.is_space] for doc in docs]
print("Словесные токены:")
for i, tokens in enumerate(word_tokens, 1):
    print(f"  Документ {i}: всего токенов — {len(tokens)}")
    print(f"    Первые 20: {tokens[:20]}")

sent_tokens = [[s.text.strip() for s in doc.sents if s.text.strip()] for doc in docs]
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

filtered_tokens = [
    [tok.text for tok in doc if tok.is_alpha and tok.text.lower() not in stop_words]
    for doc in docs
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
all_lemmas = [
    [t.lemma_.lower() for t in doc if t.is_alpha and t.text.lower() not in stop_words]
    for doc in docs
]
doc0 = docs[0]
content_toks = [t for t in doc0 if t.is_alpha and t.text.lower() not in stop_words]
pairs = [(t.text, t.lemma_.lower()) for t in content_toks[:30]]
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
for i, doc in enumerate(docs, 1):
    pos_pairs = [(t.text, t.pos_) for t in doc if t.is_alpha]
    pos_counts = Counter(pos for _, pos in pos_pairs)
    print(f"\nДокумент {i} — распределение частей речи:")
    for pos, cnt in sorted(pos_counts.items(), key=lambda x: -x[1]):
        bar = "#" * min(cnt, 40)
        print(f"  {pos:8s}: {cnt:4d}  {bar}")
    notable = [(t.text, t.pos_, t.tag_) for t in doc
               if t.is_alpha and t.text.lower() not in stop_words][:10]
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
for i, doc in enumerate(docs, 1):
    ents = [(ent.text, ent.label_) for ent in doc.ents]
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
X_uni = vec_uni.fit_transform(corpus)
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
X_bi = vec_bi.fit_transform(corpus)
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
X_tri = vec_tri.fit_transform(corpus)
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
tfidf_matrix = tfidf.fit_transform(corpus)
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
    preview = corpus[idx2].strip().replace("\n", " ")[:60]
    print(f"  {rank:<6} Документ {idx2+1:<5} {score:<16.4f} {preview}...")
best_idx = ranked_order[0]
print(f"\nНаиболее релевантный: Документ {best_idx+1} (косинус = {cosine_scores[best_idx]:.4f})")


# %% [markdown] id="md_para" tags=["md_para"]
# ## Структура текста: абзацы и предложения
#
# Объединяем весь корпус в единый поток, делим spaCy-сентензайзером на предложения и группируем их по 3–6 в «абзацы». Эту структуру потребляют последующие шаги (тезисы, ключевые слова, тематизация).
#
# Дополнительно для каждого абзаца и каждого предложения `lingua` фиксирует ISO-код языка:
#
# - `para_langs[i]` — язык `i`-го абзаца целиком,
# - `sent_langs[i]` — язык `i`-го предложения,
# - `para_sentences[i]` — список предложений, входящих в `i`-й абзац (нужен ячейке экспорта).
#
# Этот пер-фрагментный язык записывается в `accessible_text.html` (`<p lang="...">`, при необходимости `<span lang="...">`) и в `accessible_text.docx` (`<w:lang>` на уровне `Run`), благодаря чему экранные читалки и TTS-движки переключают голос автоматически.

# %% id="cell_para" tags=["cell_para"]
print("--- Структура текста: абзацы ---")
import re, numpy as np
import pandas as pd

# Объединяем все страницы/куски корпуса в один поток
full_text = " ".join(c.replace("\n", " ") for c in corpus)
full_text = re.sub(r"\s+", " ", full_text).strip()
print(f"Общий объём текста: {len(full_text)} символов")

# Разбиваем на предложения (spaCy).
# spaCy ограничивает длину одного документа nlp.max_length (по умолчанию
# 1 000 000 символов): парсеру/NER нужно ~1 ГБ временной памяти на каждые
# 100 000 символов, поэтому длинные корпуса (целые книги, OCR крупных PDF)
# превышают лимит и валятся с ошибкой E088. Чтобы не поднимать лимит (это
# грозит аллокацией многих гигабайт), режем поток на куски по границам слов
# и прогоняем nlp по частям, собирая предложения. Куски держим заметно ниже
# лимита, поэтому пиковая память остаётся в пределах ~2 ГБ на вызов.
_NLP_CHUNK = min(getattr(nlp, "max_length", 1_000_000), 200_000)


def _iter_text_chunks(text, max_len):
    """Делит text на куски <= max_len по границам слов (без разрыва слова)."""
    n = len(text)
    if n <= max_len:
        yield text
        return
    start = 0
    while start < n:
        end = min(start + max_len, n)
        if end < n:
            sp = text.rfind(" ", start, end)
            if sp > start:
                end = sp
        yield text[start:end].strip()
        start = end


all_sents = []
if len(full_text) > _NLP_CHUNK:
    print(f"Текст длиннее {_NLP_CHUNK} символов — обрабатываем кусками "
          f"(ограничение spaCy nlp.max_length).")
for _chunk in _iter_text_chunks(full_text, _NLP_CHUNK):
    if not _chunk:
        continue
    _doc = nlp(_chunk)
    all_sents.extend(s.text.strip() for s in _doc.sents
                     if len(s.text.strip()) > 10)
print(f"Всего предложений: {len(all_sents)}")

# Группируем в абзацы по 3-6 предложений.
# Параллельно сохраняем para_sentences — список списков предложений каждого абзаца,
# понадобится для пер-предложного тегирования языка в HTML/DOCX-экспорте.
PARA_MIN, PARA_MAX = 3, 6
paragraphs, para_sentences = [], []
buf = []
for sent in all_sents:
    buf.append(sent)
    if len(buf) >= PARA_MAX:
        paragraphs.append(" ".join(buf))
        para_sentences.append(buf[:])
        buf = []
if buf:
    paragraphs.append(" ".join(buf))
    para_sentences.append(buf[:])
print(f"Сформировано абзацев: {len(paragraphs)} (по {PARA_MIN}–{PARA_MAX} предложений)")

df_sent = pd.DataFrame({"sent_id": range(1, len(all_sents)+1), "sentence": all_sents})
df_para = pd.DataFrame({"para_id": range(1, len(paragraphs)+1), "paragraph": paragraphs})

# Языково-специфичный паттерн токенов для CountVectorizer / TF-IDF
TOKEN_PAT = {
    "pl": r"(?u)\b[a-ząćęłńóśźż]{2,}\b",
    "ru": r"(?u)\b[а-яё]{2,}\b",
    "en": r"(?u)\b[a-z]{2,}\b",
}.get(LANG, r"(?u)\b\S{2,}\b")

# Лемматизируем абзацы (понадобится для TF-IDF)
def to_lemma_str(text):
    out = []
    for t in nlp(text):
        if not t.is_alpha or t.is_stop or t.text.lower() in stop_words:
            continue
        out.append((t.lemma_ or t.text).lower())
    return " ".join(out)

para_lemmas = [to_lemma_str(p) for p in paragraphs]
print("Лемматизация абзацев завершена.")

# === Детекция языка на уровне абзацев и предложений (lingua) ===
# Эти списки потребляет ячейка экспорта — каждый <p>/<span> в HTML
# и каждый Run в DOCX получает атрибут lang, что позволяет
# экранным читалкам автоматически переключать голос/произношение.
print("\nДетекция языка по абзацам и предложениям (lingua) ...")

# Диакритики, типичные для каждого из поддерживаемых языков. Используются
# как «защитник» fallback-языка: если предложение содержит знак,
# характерный для основного языка корпуса (например, финские ä/ö),
# почти наверняка оно тоже на этом языке — даже если lingua ошибочно
# классифицирует его на основе вкраплённых иноязычных слов.
_LANG_DIACRITICS = {
    "fi": "äöÄÖ",
    "pl": "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ",
    "is": "áéíóúýæöþðÁÉÍÓÚÝÆÖÞÐ",
    "it": "àèéìòùÀÈÉÌÒÙ",
    # ru — авто-детекция по кириллическому Unicode-блоку в lingua
    # en — без диакритик
}

# Минимальная длина предложения, при которой можно доверять lingua.
# На фрагментах короче ~30 символов lingua часто ошибается на проприальных
# именах: «Igor de Lendorf» (16 знаков) → it, «Se on strategista» (18) → it,
# «Mut se mies, Igor» (18) → en. Все эти три на самом деле финские.
_MIN_RELIABLE_LEN = 30


def _is_cyrillic_char(ch):
    """Проверяет, попадает ли символ в кириллический Unicode-блок."""
    code = ord(ch)
    return 0x0400 <= code <= 0x04FF


def _safe_detect(text, fallback=LANG):
    """Консервативная детекция языка с предпочтением fallback.

    Идея: голос экранной читалки на fallback-языке (fi/pl/it/is),
    читающий иноязычные вкрапления с лёгким акцентом, звучит существенно
    лучше, чем английский голос, фонетически коверкающий обрывки финского
    или польского. Поэтому в неоднозначных случаях оставляем fallback.

    Стратегия (по приоритету):

    1. Кириллица в тексте → ru. Однозначный сигнал; работает даже на
       коротких фрагментах ("Тут текст." — 10 знаков).

    2. Слишком короткий фрагмент (<30 символов) → fallback. Lingua на
       коротких латинских фрагментах часто ошибается на именах
       собственных: «Igor de Lendorf» → it, «Mut se mies, Igor» → en.

    3. Содержит диакритики fallback (например, ä/ö для fi, ąęć для pl) →
       fallback. Финское предложение с английской цитатой остаётся
       финским ("Joo, ja tää on Strategic Lawsuit Against Public...").

    4. Lingua — если возвращает fallback, оставляем.

    5. Lingua → другой язык, у которого есть СВОИ диакритики В ЭТОМ
       фрагменте (например, фр. à в "à propos") → доверяем lingua.

    6. Lingua → язык без специфических диакритик (типично en) →
       fallback. "Se tulee englannin sanoista deny, attack, reverse
       victim and offender." — половина слов английских, но хочется,
       чтобы финский голос прочитал предложение целиком, а не
       английский голос ломал фонетику финского начала.
    """
    text = text.strip()
    if not text or len(text) < 3:
        return fallback

    # 1. Кириллица — однозначный сигнал
    if any(_is_cyrillic_char(ch) for ch in text):
        if "ru" in SUPPORTED_LANGS:
            return "ru"

    # 2. Короткие → fallback
    if len(text) < _MIN_RELIABLE_LEN:
        return fallback

    # 3. Диакритик-хинт fallback-языка
    fallback_marks = _LANG_DIACRITICS.get(fallback, "")
    if fallback_marks and any(ch in text for ch in fallback_marks):
        return fallback

    # 4. Lingua
    iso = detect_lang(text)
    if iso is None or iso not in SUPPORTED_LANGS:
        return fallback
    if iso == fallback:
        return iso

    # 5. Detected lang со своими диакритиками в тексте → доверяем lingua
    iso_marks = _LANG_DIACRITICS.get(iso, "")
    if iso_marks and any(ch in text for ch in iso_marks):
        return iso

    # 6. Detected lang без характерных диакритик (типично en) → fallback.
    # См. doc-string выше: фонетически предпочтительнее.
    return fallback

para_langs = [_safe_detect(p) for p in paragraphs]
sent_langs = [_safe_detect(s) for s in all_sents]

from collections import Counter as _Counter
_para_dist = _Counter(para_langs)
_sent_dist = _Counter(sent_langs)
print(f"  Языки абзацев   : {dict(_para_dist)}")
print(f"  Языки предложений: {dict(_sent_dist)}")

# Подсчитываем абзацы с внутренним смешением языков (хотя бы одно
# предложение отличается от языка всего абзаца).
_mixed = 0
for p_lang, sents in zip(para_langs, para_sentences):
    s_langs_local = [_safe_detect(s) for s in sents]
    if any(sl != p_lang for sl in s_langs_local):
        _mixed += 1
print(f"  Абзацев со смешанными языками: {_mixed}/{len(paragraphs)} "
      f"(в HTML/DOCX каждое такое предложение получит свой lang-тег)")

# === Диагностика оставшихся outlier-предложений ===
# После эвристик _safe_detect (короткие → fallback, диакритик-хинт)
# здесь печатаем те предложения, которые всё ещё классифицированы
# как НЕ-fallback. Это либо легитимные иноязычные вкрапления,
# либо false positives, которые стоит проверить вручную.
_outlier_sents = [(idx, s, sl)
                  for idx, (s, sl) in enumerate(zip(all_sents, sent_langs), 1)
                  if sl != LANG]
if _outlier_sents:
    print(f"\n  Оставшиеся outlier-предложения с языком, отличным от "
          f"{LANG_NAMES.get(LANG, LANG)} ({LANG}): {len(_outlier_sents)}")
    print(f"  (после короткой-фильтрации и диакритик-хинта; обычно это "
          f"легитимные вкрапления цитат)")
    for idx, sent, sl in _outlier_sents[:20]:
        _prev = sent[:90] + ("…" if len(sent) > 90 else "")
        print(f"    [предл. {idx}] обнаружен как "
              f"{LANG_NAMES.get(sl, sl)} ({sl}): {_prev}")
    if len(_outlier_sents) > 20:
        print(f"    ... и ещё {len(_outlier_sents) - 20}")
else:
    print(f"\n  Все предложения классифицированы как "
          f"{LANG_NAMES.get(LANG, LANG)} ({LANG}) — outlier'ов нет.")

# %% [markdown] id="md_foreign_resegment" tags=["md_foreign_resegment"]
# ## Реегментация иноязычных блоков
#
# В предыдущей ячейке весь корпус был разбит на предложения **доминирующей** spaCy-моделью. Если в корпусе встречаются непрерывные иноязычные блоки (например, длинная цитата на финском внутри польского текста), модель LANG не знает иноязычных сокращений (`ad es.`, `e.g.`, `esim.`) и может ошибочно принять точку после них за конец предложения — иноязычный фрагмент разрывается пополам, а внутри двух «половинок» теряется контекст.
#
# Эта ячейка ищет последовательности из **двух и более подряд идущих предложений на одном и том же иноязычном языке** (по `sent_langs` из cell_para) и заново обрабатывает каждый такой блок собственной моделью:
#
# 1. Применяется `ABBREV_BY_LANG[lang]` — языко-специфичная нормализация сокращений из cell_pl_corrector;
# 2. `get_nlp(lang)(блок)` — корректная сегментация на предложения.
#
# Затем перестраиваются `all_sents`, `sent_langs`, `paragraphs`, `para_sentences`, `para_langs`, `df_sent`, `df_para` и (защитно) `para_lemmas`. Следующая ячейка двухстадийного анализа уже работает на исправленных границах.
#
# Если в корпусе нет иноязычных предложений — или они есть, но не образуют блоков ≥2 — ячейка завершается мгновенно с информативным сообщением, не загружая никаких дополнительных моделей.

# %% id="cell_foreign_resegment" tags=["cell_foreign_resegment"]
print("--- Реegmentация иноязычных блоков ---")
# Доминирующая spaCy-модель в cell_para разбила корпус на предложения
# по правилам своего языка. Иноязычные сокращения (it. "ad es.", en. "e.g.",
# fi. "esim.") модель не знает, поэтому точка после такого сокращения
# часто ошибочно интерпретируется как конец предложения — иноязычный
# фрагмент рвётся пополам.
#
# Эта ячейка ищет последовательности из ≥2 подряд идущих предложений
# на одном и том же не-LANG языке (по sent_langs из cell_para) и заново
# обрабатывает их СОБСТВЕННОЙ моделью:
#   1) языко-специфичная нормализация сокращений ABBREV_BY_LANG[lang]
#   2) get_nlp(lang)(блок) → новые границы предложений
#
# Затем перестраиваются all_sents / sent_langs / paragraphs /
# para_sentences / para_langs / df_sent / df_para и (defensively)
# para_lemmas. Cell_multilang_pass далее работает на уже исправленных
# границах.
#
# LRU-кэш get_nlp() ограничивает RAM двумя моделями.

from collections import Counter as _C_seg

# === Быстрый выход 1: в корпусе нет иноязычных предложений ===
_foreign_count = sum(1 for sl in sent_langs if sl != LANG)
if _foreign_count == 0:
    print(f"  Все предложения на основном языке "
          f"({LANG_NAMES.get(LANG, LANG)}, {LANG}). "
          f"Реegmentация не требуется.")
else:
    # === Поиск runs: ≥2 подряд предложений одного не-LANG языка ===
    _runs = []  # (lang, start, end)  end — exclusive
    _i = 0
    while _i < len(all_sents):
        _cur_lang = sent_langs[_i]
        _j = _i
        while _j < len(all_sents) and sent_langs[_j] == _cur_lang:
            _j += 1
        if (_cur_lang != LANG
                and _cur_lang in SUPPORTED_LANGS
                and _j - _i >= 2):
            _runs.append((_cur_lang, _i, _j))
        _i = _j

    # === Быстрый выход 2: иноязычные есть, но нет блоков ≥2 ===
    if not _runs:
        print(f"  Иноязычных предложений: {_foreign_count}, "
              f"но ни одного непрерывного блока из ≥2. "
              f"Реegmentация не требуется (одиночные вкрапления "
              f"обработает следующая ячейка для NER/лемм).")
    else:
        print(f"  Найдено блоков ≥2 подряд иноязычных предложений: "
              f"{len(_runs)}")
        for _rl, _rs, _re in _runs:
            print(f"    [{_rl}] предложения {_rs + 1}-{_re} "
                  f"(длина блока: {_re - _rs})")
        print()

        # === Обработка runs: abbrev + spaCy → новые предложения ===
        _new_sents = []
        _new_langs = []
        _cursor = 0
        _runs_sorted = sorted(_runs, key=lambda r: r[1])
        for _rl, _rs, _re in _runs_sorted:
            # Копируем неперерабатываемый хвост [_cursor, _rs)
            for _k in range(_cursor, _rs):
                _new_sents.append(all_sents[_k])
                _new_langs.append(sent_langs[_k])
            # Обрабатываем блок [_rs, _re)
            _block = " ".join(all_sents[_rs:_re])
            # (a) Языко-специфичные сокращения
            _patterns = ABBREV_BY_LANG.get(_rl, [])
            for _p, _r in _patterns:
                _block = re.sub(_p, _r, _block)
            # (b) Сегментация правильной моделью
            _run_nlp = get_nlp(_rl)
            _doc = _run_nlp(_block)
            _ns = [s.text.strip() for s in _doc.sents
                   if len(s.text.strip()) > 10]
            # (c) Записываем результат
            for _s in _ns:
                _new_sents.append(_s)
                _new_langs.append(_rl)
            print(f"    [{_rl}] блок {_rs + 1}-{_re}: "
                  f"было {_re - _rs} предложений → стало {len(_ns)}")
            _cursor = _re
        # Хвост после последнего run
        for _k in range(_cursor, len(all_sents)):
            _new_sents.append(all_sents[_k])
            _new_langs.append(sent_langs[_k])

        _delta = len(_new_sents) - len(all_sents)
        all_sents = _new_sents
        sent_langs = _new_langs
        print(f"\n  Итого предложений: {len(all_sents)} "
              f"({'+' if _delta >= 0 else ''}{_delta} к исходным)")

        # === Перестройка абзацев по тем же 3-6 предложений ===
        paragraphs, para_sentences = [], []
        _buf = []
        for _sent in all_sents:
            _buf.append(_sent)
            if len(_buf) >= PARA_MAX:
                paragraphs.append(" ".join(_buf))
                para_sentences.append(_buf[:])
                _buf = []
        if _buf:
            paragraphs.append(" ".join(_buf))
            para_sentences.append(_buf[:])

        # === para_langs — доминирующий язык внутри каждого абзаца ===
        para_langs = []
        _si = 0
        for _sip in para_sentences:
            _cnt = _C_seg()
            for _ in _sip:
                _cnt[sent_langs[_si]] += 1
                _si += 1
            para_langs.append(_cnt.most_common(1)[0][0])

        # === df_sent / df_para ===
        df_sent = pd.DataFrame({"sent_id": range(1, len(all_sents) + 1),
                                "sentence": all_sents})
        df_para = pd.DataFrame({"para_id": range(1, len(paragraphs) + 1),
                                "paragraph": paragraphs})

        # === Defensive: para_lemmas align по новым абзацам ===
        # cell_multilang_pass нормально пересоберёт para_lemmas с учётом
        # языковой модели каждого предложения. Но если он по какой-то
        # причине early-return-ит (например, после re-segmentации все
        # фрагменты стали короче 10 символов и filter их выбросил),
        # длины para_lemmas и paragraphs не должны расходиться —
        # cell_keywords ожидает совпадения.
        para_lemmas = [to_lemma_str(p) for p in paragraphs]

        print(f"\n  Абзацев пересобрано: {len(paragraphs)}")
        print(f"  Языки абзацев   : {dict(_C_seg(para_langs))}")
        print(f"  Языки предложений: {dict(_C_seg(sent_langs))}")

# %% [markdown] id="md_multilang_pass" tags=["md_multilang_pass"]
# ## Двухстадийный мультиязычный анализ (NER + лемматизация)
#
# Если корпус содержит фрагменты на нескольких языках, доминирующая модель spaCy некорректно лемматизирует слова и неверно классифицирует именованные сущности в иноязычных предложениях. Эта ячейка устраняет проблему: каждое предложение, чей язык (определённый lingua в предыдущей ячейке) отличается от основного, повторно обрабатывается через `get_nlp(sent_lang)`.
#
# LRU-кэш в `cell_model` ограничивает использование RAM двумя моделями одновременно — третья вытесняет наименее использованную. Это позволяет последовательно прогнать корпус через несколько моделей без накопления всех в памяти.
#
# После выполнения ячейки `all_ents` и `para_lemmas` пересобираются с учётом языка каждого предложения, поэтому экспорт ключевых слов, тезисов, тем и сущностей опирается на корректную морфологию.
#
# При отсутствии необходимой модели spaCy (или `transformers`/`torch` для исландского) ячейка во время своего исполнения выводит явное предупреждение о ненадёжности анализа для затронутых предложений и подсказывает команду установки.

# %% id="cell_multilang_pass" tags=["cell_multilang_pass"]
print("--- Двухстадийный мультиязычный анализ (NER + лемматизация) ---")
# Первая стадия NER уже выполнена в cell_ner на доминирующей модели (LANG).
# Здесь — вторая стадия: для каждого предложения, чей язык по lingua
# отличается от LANG, мы заново прогоняем его через правильную модель
# spaCy (или blank-fallback с предупреждением), а затем пересобираем
# all_ents (для экспорта/сводки) и para_lemmas (для TF-IDF ключевых слов).
#
# LRU-кэш get_nlp() удерживает максимум две модели; третья вытесняет
# наименее использованную, поэтому RAM-расход ограничен независимо от
# числа языков в корпусе.

from collections import defaultdict, Counter as _C2


# === Быстрый выход: в корпусе нет иноязычных предложений. ===
# all_ents (cell_ner) и para_lemmas (cell_para) уже корректны —
# пересчитывать те же самые предложения той же самой моделью бессмысленно.
_foreign_count = sum(1 for sl in sent_langs if sl != LANG)
if _foreign_count == 0:
    print(f"  В корпусе нет предложений на языках, отличных от "
          f"{LANG_NAMES.get(LANG, LANG)} ({LANG}).")
    print(f"  Стадия 2 не требуется — all_ents (cell_ner) и "
          f"para_lemmas (cell_para) уже корректны.")
else:
    def _model_capabilities(nlp_):
        """Возвращает множество компонентов в пайплайне модели.
        Blank-fallback (spacy.blank) лишён 'ner', 'lemmatizer', 'tagger' —
        мы используем этот факт для обнаружения отсутствующих моделей."""
        return set(nlp_.pipe_names)


    # Стадия 1 NER сохраняется для сравнения
    _stage1_ents = list(all_ents)

    # Группируем все предложения по обнаруженному языку
    _sent_by_lang = defaultdict(list)
    for _s, _sl in zip(all_sents, sent_langs):
        _sent_by_lang[_sl].append(_s)

    print(f"Иноязычных предложений: {_foreign_count} из {len(all_sents)}")
    print(f"Распределение по языкам: "
          f"{dict({k: len(v) for k, v in _sent_by_lang.items()})}")
    print()

    # Языки, для которых анализ окажется неполным
    _unreliable = {}

    # new_sent_ents[sent_text] -> [(ent_text, label), ...]
    # new_sent_lemmas[sent_text] -> [lemma, ...]
    # Используем dict (а не list по индексу), потому что одно и то же
    # предложение может встретиться в корпусе несколько раз — нам достаточно
    # обработать его один раз.
    new_sent_ents = {}
    new_sent_lemmas = {}

    # === Per-language диагностика для иноязычного контента ===
    # cell_stop / cell_lemma / cell_pos работали ТОЛЬКО на доминирующей
    # модели — поэтому для чужих слов выдавали либо случайный POS из-за
    # омонимии (например, "on" существует в pl/fi/en и доминирующая модель
    # вернёт тег по своим вероятностям), либо X. Здесь восполняем: для
    # каждого иноязычного языка собираем POS-распределение, счётчик
    # отфильтрованных стоп-слов и сэмпл пар форма→лемма правильной моделью.
    _per_lang_diag = {}  # lang -> dict со счётчиками

    for foreign_lang, foreign_sents in _sent_by_lang.items():
        # Дедуплицируем внутри языка для экономии вызовов модели
        unique_sents = list(dict.fromkeys(foreign_sents))

        if foreign_lang == LANG:
            # Доминирующий язык: используем уже загруженную nlp.
            target_nlp = nlp
            target_stop = stop_words
        elif foreign_lang in SUPPORTED_LANGS:
            print(f"  [Стадия 2] Язык '{foreign_lang}' "
                  f"({LANG_NAMES.get(foreign_lang, foreign_lang)}): "
                  f"предложений — {len(foreign_sents)} "
                  f"(уникальных: {len(unique_sents)}). Загружаем модель ...")
            target_nlp = get_nlp(foreign_lang)
            target_stop = target_nlp.Defaults.stop_words
        else:
            # Язык вне SUPPORTED_LANGS — оставляем стадию 1 как есть для этих
            # предложений (но их у нас не должно быть, т.к. lingua-набор
            # совпадает с SUPPORTED_LANGS).
            continue

        caps = _model_capabilities(target_nlp)
        has_ner = ("ner" in caps) or ("icelandic_ner" in caps)
        has_lemma = "lemmatizer" in caps
        has_tagger = "tagger" in caps or "morphologizer" in caps

        if foreign_lang != LANG and (not has_ner or not has_lemma):
            missing = []
            if not has_ner:
                missing.append("NER")
            if not has_lemma:
                missing.append("лемматизатор")
            if not has_tagger:
                missing.append("POS-таггер")
            model_name = MODEL_BY_LANG.get(foreign_lang, "(модель неизвестна)")
            print(f"  [ВНИМАНИЕ] Полная модель для языка '{foreign_lang}' недоступна.")
            print(f"     Отсутствуют компоненты: {missing}.")
            print(f"     Затронуто предложений: {len(foreign_sents)}.")
            print(f"     Анализ этих фрагментов БУДЕТ НЕНАДЁЖНЫМ.")
            if foreign_lang == "is":
                print(f"     Установите: pip install transformers torch")
                print(f"     (для исландского spaCy не имеет полной модели — нужны HF-веса)")
            else:
                print(f"     Установите: python -m spacy download {model_name}")
            _unreliable[foreign_lang] = {
                "missing": missing,
                "sentence_count": len(foreign_sents),
                "unique_sentences": len(unique_sents),
            }

        # Инициализируем диагностический контейнер только для иноязычного.
        # Доминирующий язык уже разобран ячейками cell_stop / cell_lemma /
        # cell_pos, дублировать вывод незачем.
        if foreign_lang != LANG:
            _per_lang_diag[foreign_lang] = {
                "pos_counts": _C2(),
                "all_alpha": 0,
                "content_count": 0,
                "lemma_changed": 0,
                "lemma_pair_sample": [],
                "stop_filtered": 0,
                "has_tagger": has_tagger,
                "has_lemma": has_lemma,
            }

        for s in unique_sents:
            d = target_nlp(s)
            new_sent_ents[s] = [(ent.text, ent.label_) for ent in d.ents]
            new_sent_lemmas[s] = [
                (t.lemma_ or t.text).lower()
                for t in d
                if t.is_alpha and not t.is_stop and t.text.lower() not in target_stop
            ]

            # Собираем per-language диагностику только для foreign.
            if foreign_lang != LANG:
                _diag = _per_lang_diag[foreign_lang]
                for tok in d:
                    if not tok.is_alpha:
                        continue
                    _diag["all_alpha"] += 1
                    if tok.pos_:
                        _diag["pos_counts"][tok.pos_] += 1
                    is_stop_word = tok.is_stop or tok.text.lower() in target_stop
                    if is_stop_word:
                        _diag["stop_filtered"] += 1
                    else:
                        _diag["content_count"] += 1
                        _lem = (tok.lemma_ or tok.text).lower()
                        if _lem != tok.text.lower():
                            _diag["lemma_changed"] += 1
                            if len(_diag["lemma_pair_sample"]) < 15:
                                _diag["lemma_pair_sample"].append((tok.text, _lem))

    # === Per-language диагностика: восполнение cell_stop/lemma/pos ===
    # Печатается ДО пересборки all_ents, чтобы блок "Полный анализ
    # иноязычных фрагментов" шёл сразу за сообщениями загрузки моделей.
    if _per_lang_diag:
        print()
        print("=== Полный анализ иноязычных фрагментов "
              "(POS, стоп-слова, леммы) ===")
        print("Восполняет cell_stop / cell_lemma / cell_pos, которые работали")
        print("только на доминирующей модели и поэтому для чужих слов давали")
        print("либо тег X, либо случайный POS из-за межъязыковой омонимии")
        print("(например, 'on' существует в pl/fi/en — доминирующая модель")
        print("вернёт случайный тег по своим вероятностям).")
        for _fl in sorted(_per_lang_diag.keys()):
            _diag = _per_lang_diag[_fl]
            print()
            print(f"  [{_fl}] {LANG_NAMES.get(_fl, _fl)}:")
            print(f"    Всего alpha-токенов:              "
                  f"{_diag['all_alpha']}")
            _pct_c = (100 * _diag["content_count"]
                      / max(1, _diag["all_alpha"]))
            print(f"    Содержательных (не стоп-слова):   "
                  f"{_diag['content_count']} ({_pct_c:.1f}%)")
            print(f"    Отфильтровано стоп-слов:          "
                  f"{_diag['stop_filtered']}")
            if _diag["has_lemma"]:
                _pct_l = (100 * _diag["lemma_changed"]
                          / max(1, _diag["content_count"]))
                print(f"    Лемматизировано (форма изменена): "
                      f"{_diag['lemma_changed']}/{_diag['content_count']} "
                      f"({_pct_l:.1f}%)")
            else:
                print(f"    Лемматизация недоступна (нет лемматизатора).")
            if _diag["has_tagger"] and _diag["pos_counts"]:
                _total_pos = sum(_diag["pos_counts"].values())
                _x_n = _diag["pos_counts"].get("X", 0)
                print(f"    POS-распределение (всего: {_total_pos}, "
                      f"X/неклассиф.: {_x_n}):")
                for _pos, _cnt in _diag["pos_counts"].most_common():
                    _bar = "#" * min(_cnt, 30)
                    print(f"      {_pos:<8}: {_cnt:4d}  {_bar}")
            else:
                print(f"    POS-теги: модель не имеет таггера "
                      f"(POS-анализ для этого языка пропущен).")
            if _diag["lemma_pair_sample"]:
                print(f"    Лемматизация (примеры изменений, до 15):")
                for _orig, _lem in _diag["lemma_pair_sample"]:
                    print(f"      [{_fl}] {_orig!r:<24} → {_lem!r}")

    # === Пересборка all_ents с правильной модели на каждое предложение ===
    _all_ents_v2 = []
    for _s in all_sents:
        _all_ents_v2.extend(new_sent_ents.get(_s, []))

    # === Пересборка para_lemmas с учётом языковых границ предложений ===
    # Каждое предложение каждого абзаца получает леммы от своей языковой модели.
    _para_lemmas_v2 = []
    for sents_in_para in para_sentences:
        bag = []
        for s in sents_in_para:
            bag.extend(new_sent_lemmas.get(s, []))
        _para_lemmas_v2.append(" ".join(bag))

    # === Диагностика ===
    print()
    print(f"NER: стадия 1 — {len(_stage1_ents)} сущностей | "
          f"стадия 2 — {len(_all_ents_v2)} сущностей")

    _s1_set = _C2(_stage1_ents)
    _s2_set = _C2(_all_ents_v2)
    _added_pairs = sum(c for k, c in _s2_set.items() if k not in _s1_set)
    _removed_pairs = sum(c for k, c in _s1_set.items() if k not in _s2_set)
    print(f"  Появилось во второй стадии: {_added_pairs}")
    print(f"  Исчезло (вероятно, ошибки доминирующей модели): {_removed_pairs}")

    # Сущности из иноязычных фрагментов — самая ценная диагностика
    _foreign_sample = []
    for foreign_lang, foreign_sents in _sent_by_lang.items():
        if foreign_lang == LANG:
            continue
        seen = set()
        for s in foreign_sents:
            for txt, lab in new_sent_ents.get(s, []):
                key = (foreign_lang, txt, lab)
                if key in seen:
                    continue
                seen.add(key)
                _foreign_sample.append(key)

    if _foreign_sample:
        print()
        print(f"Сущности, извлечённые корректной моделью из иноязычных "
              f"фрагментов (уникальных: {len(_foreign_sample)}, показываем до 20):")
        for fl, txt, lab in _foreign_sample[:20]:
            print(f"  [{fl}] [{lab}] {txt!r}")
        if len(_foreign_sample) > 20:
            print(f"  ... и ещё {len(_foreign_sample) - 20}")

    print()
    print("Финальное распределение типов сущностей (после слияния):")
    for etype, cnt in _C2(label for _, label in _all_ents_v2).most_common():
        print(f"  {etype:<12}: {cnt}")

    # Обновляем глобалы — последующие ячейки (cell_keywords, cell_export,
    # cell_summary) автоматически подхватят пересобранные значения.
    all_ents = _all_ents_v2
    para_lemmas = _para_lemmas_v2

    print()
    if _unreliable:
        print("[ИТОГ] Анализ НЕНАДЁЖЕН для следующих языков:")
        for lng, info in _unreliable.items():
            print(f"  {lng}: предложений — {info['sentence_count']} "
                  f"(уникальных — {info['unique_sentences']}), "
                  f"отсутствуют — {info['missing']}")
        print("  Рекомендация: установите недостающие модели и перезапустите ноутбук с этой ячейки.")
    else:
        print("Все необходимые модели загружены. Двухстадийный анализ выполнен полностью.")

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
        .sort_values("score", ascending=False)
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

# Для каждого абзаца: найти лучшее предложение
theses_rows = []
sent_cursor = 0
for pid, para in enumerate(paragraphs, 1):
    para_sents = [s.text.strip() for s in nlp(para).sents if len(s.text.strip()) > 10]
    n = len(para_sents)
    if n == 0:
        continue
    seg = sent_scores[sent_cursor:sent_cursor + n]
    best_i = int(seg.argmax())
    best_sent = para_sents[best_i]
    if len(best_sent) >= 40:
        theses_rows.append({"para_id": pid, "sentence": best_sent,
                             "score": float(seg[best_i])})
    sent_cursor += n

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
            top_t = pd.DataFrame({"term": tt, "s": st}).sort_values("s", ascending=False).head(8)["term"].tolist()
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
# - `accessible_text.html` — строится через `BeautifulSoup`. Корневой `<html>` имеет атрибут `lang` преобладающего языка; каждый `<p>` получает свой `lang` (по `para_langs`), а внутри смешанных абзацев каждое предложение оборачивается в `<span lang="...">` (по `sent_langs`). NVDA и JAWS читают эти теги нативно и переключают голос на лету.
# - `accessible_text.docx` — собирается через `python-docx`. Для каждого `Run` свойство `<w:lang>` прописывается жёстко (`pl-PL`, `ru-RU`, `en-US`, `it-IT`, `fi-FI`, `is-IS`). Word, встроенный синтезатор Windows (SAPI) и сторонние читалки опираются на этот атрибут офлайн, без обращения к онлайн-детекторам.
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
# абзац (а при смешанных языках — каждое предложение) получает
# собственный lang-атрибут, благодаря которому NVDA/JAWS/Narrator
# и встроенные TTS-движки автоматически выбирают правильный голос.
# ============================================================
LANG_TO_LOCALE = {
    "en": "en-US", "pl": "pl-PL", "ru": "ru-RU",
    "it": "it-IT", "fi": "fi-FI", "is": "is-IS",
}

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

    for para_text, p_lang, sents in zip(paragraphs, para_langs, para_sentences):
        s_langs_local = [_safe_detect(s) for s in sents]
        p_tag = soup.new_tag("p")
        p_tag["lang"] = p_lang
        if all(sl == p_lang for sl in s_langs_local):
            # Однородный абзац — атрибут lang только на <p>
            p_tag.string = para_text
        else:
            # Смешанный — каждое предложение в собственном <span lang="...">
            for i_s, (sent, sl) in enumerate(zip(sents, s_langs_local)):
                span = soup.new_tag("span")
                span["lang"] = sl
                span.string = sent + (" " if i_s < len(sents) - 1 else "")
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
    for para_text, p_lang, sents in zip(paragraphs, para_langs, para_sentences):
        s_langs_local = [_safe_detect(s) for s in sents]
        p = docx_doc.add_paragraph()
        if all(sl == p_lang for sl in s_langs_local):
            run = p.add_run(para_text)
            _set_run_lang(run, p_lang)
        else:
            for i_s, (sent, sl) in enumerate(zip(sents, s_langs_local)):
                tail = " " if i_s < len(sents) - 1 else ""
                run = p.add_run(sent + tail)
                _set_run_lang(run, sl)
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
_qa_texts = paragraphs if 'paragraphs' in dir() and paragraphs else corpus
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
