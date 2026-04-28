import json
import re
import sys

NOTEBOOK_PATH = "accessible_text_analyst.ipynb"
OUTPUT_HTML = "raport_analizy.html"

# Ustaw na False, jeśli chcesz w HTMLu widzieć tabele lematyzacji, części mowy i paski ładowania
REMOVE_NOISE = False

try:
    import markdown
except ImportError:
    print("[BŁĄD] Brak biblioteki markdown. Wykonaj: pip install markdown")
    sys.exit(1)

def build_accessible_html():
    with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
        nb = json.load(f)

    # 1. Znajdź język docelowy analizowanego tekstu
    target_lang = "ru" 
    for cell in nb.get("cells", []):
        if cell["cell_type"] == "code":
            for output in cell.get("outputs", []):
                text = "".join(output.get("text", []))
                match = re.search(r'Выбран язык: .*?\((.*?)\)', text)
                if match:
                    target_lang = match.group(1).strip()
                    break

    # 2. Inteligentne tagowanie 
    def tag_target_language(text, lang):
        if lang == "ru":
            return text 
        
        import html
        text = html.escape(text)

        patterns = [
            # Zdania bazowe: [1] Obcy tekst...
            (r'^(\s*\[\d+\]\s+)(.+)$', r'\1<span lang="{}">\2</span>'),
            # Słowa kluczowe (pierwsze 20): Первые 20: [&#x27;Word&#x27;, ...]
            (r'(Первые \d+:\s+)(\[.+\])', r'\1<span lang="{}">\2</span>'),
            # Filtrowanie i stop słowa: Выборка (первые 20 по алфавиту): [&#x27;Word&#x27;, ...]
            (r'(Выборка(?: \(первые \d+ по алфавиту\))?:\s+)(\[.+\])', r'\1<span lang="{}">\2</span>'),
            # Tezy: Абзац 1: Obcy tekst...
            (r'^(.*Абзац\s+\d+(?: \([^)]+\))?:\s+)(.+)$', r'\1<span lang="{}">\2</span>'),
            # Przykłady z tematów: Пример: Obcy tekst
            (r'^(.*Пример:\s+)(.+)$', r'\1<span lang="{}">\2</span>'),
            # Bigramy/Trigramy: 1. &#x27;word&#x27;: 5
            (r"^(\s*\d+\.\s+&#x27;)(.+?)(&#x27;\s*:\s*\d+)$", r'\1<span lang="{}">\2</span>\3'),
            # Entity: [orgName] &#x27;Name&#x27;
            (r"^(\s*\[\w+\]\s+&#x27;)(.+?)(&#x27;)$", r'\1<span lang="{}">\2</span>\3'),
            # Unigramy: &#x27;word&#x27; : 10
            (r"^(\s*&#x27;)(.+?)(&#x27;\s*:\s*\d+.*)$", r'\1<span lang="{}">\2</span>\3'),
            
            # --- NOWE REGULY ---
            # Auto-wyszukiwanie RAG: Автозапрос: &quot;zapytanie&quot;
            (r'(Автозапрос:\s+&quot;)(.+?)(&quot;)', r'\1<span lang="{}">\2</span>\3'),
            # RAG Tytuł wyszukiwania: Ранжирование по запросу &quot;zapytanie&quot;:
            (r'(Ранжирование по запросу\s+&quot;)(.+?)(&quot;.*)', r'\1<span lang="{}">\2</span>\3'),
            # RAG Tabela z rankingiem: 1      Документ 5     0.2214           hallusinoi...
            (r'^(\s*\d+\s+Документ\s+\d+\s+0\.\d{4}\s+)(.+)$', r'\1<span lang="{}">\2</span>'),
            # Tabela TF-IDF:   słowo                 0.1940
            (r'^(\s+)([^\s\d\|]+(?: [^\s\d\|]+)*?)(\s+0\.\d{4})$', r'\1<span lang="{}">\2</span>\3'),
            # Tematyzacja (Słowa kluczowe w grupie): Ключевые слова: słowo, słowo
            (r'^(.*Ключевые слова:\s+)(.+)$', r'\1<span lang="{}">\2</span>'),
            # Tematyzacja z podsumowania: Тема 0: słowo, słowo
            (r'^(.*Тема \d+:\s+)(.+)$', r'\1<span lang="{}">\2</span>'),
            # Zapytanie w sprawozdaniu końcowym
            (r'(Запрос \(авто\)\s+:\s+&quot;)(.+?)(&quot;)', r'\1<span lang="{}">\2</span>\3'),
            
            # POS: &#x27;słowo&#x27; | VERB | V (tagujemy tylko słowo!)
            (r"^(\s*&#x27;)(.+?)(&#x27;\s*\|.*)$", r'\1<span lang="{}">\2</span>\3'),
            # Lematyzacja (tabela):   Słowo     słowo   &lt;-- изменено
            (r"^(\s+)(?!Исходное|-------)([^\s]+)(\s+)(?!Лемма|-----)([^\s]+)(\s*&lt;-- изменено)?$", r'\1<span lang="{0}">\2</span>\3<span lang="{0}">\4</span>\5'),
        ]
        
        lines = text.split('\n')
        tagged_lines = []
        for line in lines:
            for pat, repl in patterns:
                line = re.sub(pat, repl.format(lang), line)
            tagged_lines.append(line)
            
        return '\n'.join(tagged_lines)

    # 3. Mechanizm wycinania szumu (dostępnościowy filtr)
    def clean_noise(text_lines):
        if not REMOVE_NOISE:
            return text_lines
        
        clean_lines = []
        skip_mode = False
        
        for line in text_lines:
            # Wyciszanie pasków ładowania i brzydkich komunikatów
            if "Loading weights" in line or "Materializing param" in line:
                continue
            if "Warning: You are sending unauthenticated requests" in line:
                continue
            
            # Wycinanie gigantycznych tabel lematyzacji i POS
            if "--- Лемматизация ---" in line or "--- Разметка частей речи (POS) ---" in line:
                skip_mode = True
            elif skip_mode and line.startswith("--- "): # Kolejna sensowna sekcja
                skip_mode = False
                
            if not skip_mode:
                clean_lines.append(line)
                
        return clean_lines

    # 4. Budowanie struktury HTML
    html_content = [
        "<!DOCTYPE html>",
        '<html lang="ru">', 
        "<head>",
        '  <meta charset="utf-8">',
        "  <title>Отчёт: Анализ текста</title>",
        "  <style>",
        "    body { font-family: Arial, sans-serif; line-height: 1.6; max-width: 900px; margin: 2rem auto; padding: 0 1rem; color: #333; }",
        "    h1, h2, h3 { color: #2c3e50; margin-top: 2rem; }",
        "    .output-box { background: #f8f9fa; border-left: 4px solid #007bff; padding: 1rem; margin-bottom: 1.5rem; overflow-x: auto; font-family: Consolas, monospace; white-space: pre-wrap; }",
        "    .markdown-cell { margin-bottom: 1.5rem; }",
        "  </style>",
        "</head>",
        "<body>",
        '<main>'
    ]

    # 5. Przetwarzanie komórek
    for cell in nb.get("cells", []):
        cell_id = cell.get("id", "")
        
        if cell_id in ["md_qa_rag", "cell_qa_rag"]:
            continue

        if cell["cell_type"] == "markdown":
            source = "".join(cell.get("source", []))
            md_html = markdown.markdown(source)
            html_content.append(f'<div class="markdown-cell">\n{md_html}\n</div>')

        elif cell["cell_type"] == "code":
            outputs = cell.get("outputs", [])
            if not outputs:
                continue
            
            cell_text_output = ""
            for out in outputs:
                if out.get("output_type") == "stream" and out.get("name") == "stdout":
                    cell_text_output += "".join(out.get("text", []))
                elif out.get("output_type") == "execute_result":
                    cell_text_output += "".join(out.get("data", {}).get("text/plain", []))

            if cell_text_output.strip():
                # Oczyszczenie z szumu
                lines = cell_text_output.split('\n')
                cleaned_lines = clean_noise(lines)
                clean_text = '\n'.join(cleaned_lines)
                
                # Tagowanie
                tagged_output = tag_target_language(clean_text, target_lang)
                if tagged_output.strip():
                    html_content.append(f'<div class="output-box" aria-label="Вывод системы">\n{tagged_output}\n</div>')

    html_content.extend([
        "</main>",
        "</body>",
        "</html>"
    ])

    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write("\n".join(html_content))
    
    print(f"[OK] Pomyślnie wygenerowano dostępny raport HTML: {OUTPUT_HTML}")
    print(f"[INFO] Rozpoznany język docelowy tekstu do tagowania: {target_lang}")
    if REMOVE_NOISE:
        print("[INFO] Tryb usuwania technicznego szumu (lematyzacja, POS, logi) jest AKTYWNY.")

if __name__ == "__main__":
    build_accessible_html()