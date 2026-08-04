import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from shamanic_locale import get_ui_lang, t

# Język UI (printy w konsoli) — odczytywany z config.json/ini, fallback 'en'.
UI_LANG = get_ui_lang()

try:
    import markdownify
except ImportError:
    print("[ERROR] markdownify library missing. Run: pip install markdownify")
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("[ERROR] beautifulsoup4 library missing. Run: pip install beautifulsoup4")
    sys.exit(1)

CONFIG_CANDIDATES = ("config.json", "config.ini")
EXPORT_ROOT = Path("export_results")
INPUT_HTML_NAME = "analysis_report.html"
OUTPUT_MD_NAME = "gemini_notebook_report.md"


def _locate_config():
    for name in CONFIG_CANDIDATES:
        if Path(name).is_file():
            return name
    return CONFIG_CANDIDATES[0]


CONFIG_PATH = _locate_config()


# Match cell_corpus in the notebook: slugified stem / host_path / "_default".
def _slugify(s, maxlen=80):
    s = re.sub(r"[^\w\-\.]+", "_", s, flags=re.UNICODE).strip("._")
    return s[:maxlen] or "_default"


def _resolve_project_dir(config_path=None):
    if config_path is None:
        config_path = CONFIG_PATH
    try:
        with open(config_path, "r", encoding="utf-8-sig") as f:
            source = (json.load(f).get("source_file") or "").strip()
    except (FileNotFoundError, json.JSONDecodeError):
        source = ""

    if not source:
        name = "_default"
    elif source.startswith(("http://", "https://")):
        u = urlparse(source)
        host = (u.netloc or "url").replace("www.", "")
        path = u.path.strip("/").replace("/", "_") or "index"
        name = _slugify(f"{host}_{path}")
    else:
        name = _slugify(Path(source).stem)
    return EXPORT_ROOT / name


PROJECT_DIR = _resolve_project_dir()
INPUT_HTML = str(PROJECT_DIR / INPUT_HTML_NAME)
OUTPUT_MD = str(PROJECT_DIR / OUTPUT_MD_NAME)

def clean_html_for_notebook(html_content):
    """
    Czyści HTML z tagów dostępnościowych (span lang), które w Markdownie
    byłyby tylko szumem dla Gemini Notebook (dawniej NotebookLM).
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Usuwamy spany, ale zostawiamy ich tekst (unwrapping)
    for span in soup.find_all('span', lang=True):
        span.unwrap()
        
    return str(soup)

def convert_to_markdown():
    try:
        with open(INPUT_HTML, 'r', encoding='utf-8') as f:
            html_raw = f.read()
    except FileNotFoundError:
        print(t(UI_LANG, 'generate_md.error_file_not_found', path=INPUT_HTML))
        return

    # 1. Czyszczenie technicznych tagów dostępnościowych
    html_cleaned = clean_html_for_notebook(html_raw)
    
    # 2. Konwersja na Markdown
    # convert_as_inline_code=True zamieni Twoje divy .output-box na bloki kodu
    md_content = markdownify.markdownify(
        html_cleaned, 
        heading_style="ATX", # Używa hashtagów # zamiast podkreśleń
        code_language="text"
    )

    # 3. Dodatkowy post-processing dla lepszej czytelności w Gemini Notebook
    # Usuwamy nadmiarowe puste linie
    md_content = re.sub(r'\n{3,}', '\n\n', md_content)

    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_MD, 'w', encoding='utf-8') as f:
        f.write(md_content)

    print(t(UI_LANG, 'generate_md.ok_markdown_ready', path=OUTPUT_MD))

if __name__ == "__main__":
    convert_to_markdown()