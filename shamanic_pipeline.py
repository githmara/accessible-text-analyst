import json
import os
import csv
from pathlib import Path

# ==========================================
# 1. KONFIGURACJA I LOKALIZACJA PLIKÓW
# ==========================================

def get_export_dir():
    # Używamy utf-8-sig by uniknąć problemów z BOM
    with open('config.json', 'r', encoding='utf-8-sig') as f:
        config = json.load(f)
    
    source_path = config.get('source_file', '')
    basename = Path(source_path).stem 
    
    export_dir = Path('export_results') / basename
    if not export_dir.exists():
        print(f"[OSTRZEŻENIE] Katalog {export_dir} nie istnieje.")
        
    return export_dir

# ==========================================
# 2. MODUŁY SZAMAŃSKIE
# ==========================================

def ritual_oracle(export_dir, output_dir):
    theses_file = export_dir / 'theses.csv'
    if not theses_file.exists():
        return
        
    output_file = output_dir / 'oracle_script.txt'
    
    with open(theses_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        sorted_theses = sorted(reader, key=lambda x: float(x['score']), reverse=True)
        
    with open(output_file, 'w', encoding='utf-8') as out:
        out.write("--- WYROCZNIA STRUMIENIA ŚWIADOMOŚCI ---\n")
        out.write("Instrukcja TTS: Czytać powoli, z narastającym echem.\n\n")
        
        for row in sorted_theses[:10]:
            sentence = row['sentence'].replace('"', '').strip()
            phrases = sentence.split(',')
            for phrase in phrases:
                if phrase.strip():
                    out.write(f"{phrase.strip()}...\n[PAUZA 1.5s]\n")
            out.write("\n")
            
    print(f"[OK] Wygenerowano Wyrocznię: {output_file.name}")

def ritual_lore_fragments(export_dir, output_dir):
    paragraphs_file = export_dir / 'paragraphs_with_topics.csv'
    if not paragraphs_file.exists():
        return
        
    lore_dir = output_dir / 'lore_fragments'
    lore_dir.mkdir(exist_ok=True)
    
    with open(paragraphs_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            topic_id = row['topic']
            para_id = row['para_id']
            text = row['paragraph'].replace('"', '')
            
            fragment_file = lore_dir / f"log_przechwycony_T{topic_id}_P{para_id}.txt"
            with open(fragment_file, 'w', encoding='utf-8') as out:
                out.write(f"// SYGNATURA ZNALEZISKA: TOPIC-{topic_id} / FRAGMENT-{para_id} //\n")
                out.write("// STATUS: USZKODZONY ZAPIS RADIOWY //\n\n")
                out.write(text)
                
    print(f"[OK] Wygenerowano Znajdźki: {lore_dir.name}/")

def ritual_raw_roots(export_dir, output_dir):
    tfidf_file = export_dir / 'keywords_tfidf.csv'
    if not tfidf_file.exists():
        return
        
    output_file = output_dir / 'raw_roots_chant.txt'
    
    with open(tfidf_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        words = [row['term'] for row in reader]
        
    with open(output_file, 'w', encoding='utf-8') as out:
        out.write("--- RYTUAŁ SUROWYCH RDZENI ---\n")
        out.write("Instrukcja TTS: Odczyt mechaniczny, nieludzki, pozbawiony emocji.\n\n")
        
        for i in range(0, min(50, len(words)), 3):
            chant = " . ".join(words[i:i+3])
            out.write(f"{chant.upper()} .\n")
            
    print(f"[OK] Wygenerowano Surowe Rdzenie: {output_file.name}")

# ==========================================
# 3. GŁÓWNY POTOK
# ==========================================

if __name__ == "__main__":
    print("Inicjowanie szamańskiego potoku przetwarzania...")
    
    try:
        export_directory = get_export_dir()
        
        output_directory = export_directory / 'audio_scripts'
        output_directory.mkdir(parents=True, exist_ok=True)
        
        ritual_oracle(export_directory, output_directory)
        ritual_lore_fragments(export_directory, output_directory)
        ritual_raw_roots(export_directory, output_directory)
        
        print("\n[ZAKOŃCZONO] Wszystkie artefakty audio są gotowe w folderze audio_scripts.")
        
    except Exception as e:
        print(f"[BŁĄD KRYTYCZNY] {e}")