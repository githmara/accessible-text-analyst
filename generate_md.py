import re
import sys
from bs4 import BeautifulSoup

try:
    import markdownify
except ImportError:
    print("[BŁĄD] Brak biblioteki markdownify. Wykonaj: pip install markdownify")
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("[BŁĄD] Brak biblioteki beautifulsoup4. Wykonaj: pip install beautifulsoup4")
    sys.exit(1)

INPUT_HTML = "raport_analizy.html"
OUTPUT_MD = "raport_dla_notebooklm.md"

def clean_html_for_notebook(html_content):
    """
    Czyści HTML z tagów dostępnościowych (span lang), 
    które w Markdownie byłyby tylko szumem dla NotebookLM.
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
        print(f"[BŁĄD] Nie znaleziono pliku {INPUT_HTML}")
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

    # 3. Dodatkowy post-processing dla lepszej czytelności w NotebookLM
    # Usuwamy nadmiarowe puste linie
    md_content = re.sub(r'\n{3,}', '\n\n', md_content)

    with open(OUTPUT_MD, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print(f"[OK] Raport Markdown gotowy: {OUTPUT_MD}")

if __name__ == "__main__":
    convert_to_markdown()