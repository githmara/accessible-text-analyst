import os
import json
import csv
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Ładowanie klucza z pliku golden_key.env
load_dotenv("golden_key.env")
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def get_export_dir():
    with open('config.json', 'r', encoding='utf-8-sig') as f:
        config = json.load(f)
    basename = Path(config.get('source_file', '')).stem 
    return Path('export_results') / basename

def ritual_entity_transformation(export_dir, output_dir):
    entities_file = export_dir / 'entities.csv'
    if not entities_file.exists():
        return
        
    entities = []
    with open(entities_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            entities.append(row['entity'])
            if len(entities) > 20:
                break
                
    prompt = f"""
    Oto lista encji (osób, miejsc, koncepcji, zjawisk) wyciągniętych z pewnego tekstu: {', '.join(entities)}.
    Zidentyfikuj ukryty motyw tych słów (niezależnie od tego, czy tekst dotyczył kolei, nauki, polityki czy czegokolwiek innego).
    Następnie przekształć te byty w mityczne, nordyckie duchy, lodowe siły natury lub pradawne zjawy, zachowując ich oryginalny kontekst w formie mrocznej metafory.
    Napisz krótki monolog (ok. 10 zdań). 
    Jesteś mroczną wyrocznią. Jak mówi stara pieśń: "Włosy, oczy czarne ma, niczym u szamana". Twój ton jest chłodny, hipnotyzujący i niepokojący.
    Język monologu: napisz w dokładnie tym samym języku, w którym są podane encje (np. polski, rosyjski, angielski, fiński).
    """
    
    print("[LLM] Wywoływanie duchów dla Rytuału Transformacji...")
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": "Jesteś starożytną wyrocznią z północy, przenikającą zasłonę światów."},
                  {"role": "user", "content": prompt}],
        temperature=0.7
    )
    
    script_content = response.choices[0].message.content
    
    output_file = output_dir / 'katla_entity_monologue.txt'
    with open(output_file, 'w', encoding='utf-8') as out:
        out.write("--- MONOLOG ZAMROŻONYCH BYTÓW (GŁOS: KATLA) ---\n\n")
        out.write(script_content)
        
    print(f"[OK] Zapisano monolog Katli w: {output_file.name}")

def ritual_echoes_of_the_old_world(export_dir, output_dir):
    topics_file = export_dir / 'topic_keywords.json'
    sentences_file = export_dir / 'sentences.csv'
    
    if not topics_file.exists() or not sentences_file.exists():
        return
        
    with open(topics_file, 'r', encoding='utf-8-sig') as f:
        topics = json.load(f)
        keywords = []
        for i in range(3):
            if str(i) in topics:
                keywords.extend(topics[str(i)])
                
    sentences = []
    with open(sentences_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            sentences.append(row['sentence'])
            if len(sentences) > 5:
                break
                
    prompt = f"""
    Oto słowa kluczowe z analizowanego tekstu: {', '.join(keywords)}.
    Nie ma znaczenia, czy tekst był o pociągach, czy była to praca magisterska. Uczyń z tych słów pradawny, szamański rytuał.
    Stwórz transową pieśń opartą na tych pojęciach. Jesteś szamanem, o którym mówią: "Włosy, oczy czarne ma, niczym u szamana". Twoja pieśń ma być hipnotyzująca i mroczna.
    Co kilka wersów pieśni wpleć DOKŁADNIE JEDNO z poniższych zdań jako surowe, obce echo z innego wymiaru (pozostaw je w takiej formie, w jakiej są, bez zmian i tłumaczenia):
    1. {sentences[0]}
    2. {sentences[1]}
    3. {sentences[2]}
    Formatuj zdania echa w nawiasach kwadratowych.
    Język pieśni: dostosuj się w pełni do języka, w którym napisane są słowa kluczowe i podane zdania.
    """
    
    print("[LLM] Splecenie wymiarów dla Rytuału Ech...")
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": "Jesteś szamanem o czarnych oczach, wpadającym w głęboki trans."},
                  {"role": "user", "content": prompt}],
        temperature=0.8
    )
    
    script_content = response.choices[0].message.content
    
    output_file = output_dir / 'vieno_echoes_chant.txt'
    with open(output_file, 'w', encoding='utf-8') as out:
        out.write("--- SZAMAŃSKA INWOKACJA ECH (GŁOS: VIENO) ---\n\n")
        out.write(script_content)
        
    print(f"[OK] Zapisano pieśń Vieno w: {output_file.name}")

if __name__ == "__main__":
    print("Inicjowanie zaawansowanych czarów LLM z kluczem z zaświatów...")
    try:
        export_directory = get_export_dir()
        output_directory = export_directory / 'audio_scripts'
        output_directory.mkdir(parents=True, exist_ok=True)
        
        ritual_entity_transformation(export_directory, output_directory)
        ritual_echoes_of_the_old_world(export_directory, output_directory)
        
        print("\n[ZAKOŃCZONO] Magia odprawiona pomyślnie.")
    except Exception as e:
        print(f"[BŁĄD KRYTYCZNY] {e}")