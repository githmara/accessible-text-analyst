import os
import json
import csv
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

from shamanic_locale import detect_corpus_lang, t, LANGUAGE_NAMES

# Ładowanie klucza z pliku golden_key.env
load_dotenv("golden_key.env")
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Cytat z polskiej piosenki ludowej "Mój cygan" — używany w obu promptach jako
# kotwica obrazu szamana. Angielską glossę dorzucamy w nawiasie, żeby model rozumiał
# znaczenie nawet, jeśli korpus nie jest polski. Prompt jest po angielsku, bo
# angielskie instrukcje są przestrzegane rygorystyczniej; ale wyjściowy język modelu
# ustawiamy przez parametr {language_name}.
SHAMAN_QUOTE_PL = "Włosy, oczy czarne ma, niczym u szamana"
SHAMAN_QUOTE_GLOSS = "Black hair, black eyes, like a shaman's"


def get_export_dir():
    with open('config.json', 'r', encoding='utf-8-sig') as f:
        config = json.load(f)
    basename = Path(config.get('source_file', '')).stem
    return Path('export_results') / basename


def ritual_entity_transformation(export_dir, output_dir, lang):
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

    language_name = LANGUAGE_NAMES.get(lang, 'English')

    system_message = (
        "You are an ancient northern oracle that pierces the veil between worlds. "
        "You speak in cold, hypnotic, unsettling prose."
    )

    prompt = f"""Here is a list of entities (persons, places, concepts, phenomena) extracted from a text: {', '.join(entities)}.

The text may be about anything — railways, science, politics, a master's thesis — it does not matter.

Your tasks, in order:
1. Identify the hidden motif binding these words together.
2. Transform each entity into a mythic Nordic spirit, ice-force of nature, or ancient revenant, preserving its original context as a dark metaphor.
3. Write a short monologue of about ten sentences.

An old Polish folk song captures the voice you channel: "{SHAMAN_QUOTE_PL}" (meaning in English: "{SHAMAN_QUOTE_GLOSS}"). Your tone is cold, hypnotic and unsettling.

CRITICAL OUTPUT RULES:
- Write the entire monologue in {language_name}.
- Every sentence, every metaphor, every line of narration must be in {language_name}.
- Do not switch to English mid-monologue. Do not include translations.
- Do not include the Polish quote or its gloss in your output — they are for your voice only.
- Do not list the entities verbatim — weave them into prose.
"""

    print("[LLM] Wywoływanie duchów dla Rytuału Transformacji...")
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system_message},
                  {"role": "user", "content": prompt}],
        temperature=0.7
    )

    script_content = response.choices[0].message.content

    output_file = output_dir / 'katla_entity_monologue.txt'
    with open(output_file, 'w', encoding='utf-8') as out:
        out.write(t(lang, 'katla.header'))
        out.write(script_content)

    print(f"[OK] Zapisano monolog Katli w: {output_file.name}")


def ritual_echoes_of_the_old_world(export_dir, output_dir, lang):
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

    language_name = LANGUAGE_NAMES.get(lang, 'English')

    system_message = (
        "You are a shaman with black eyes, falling into a deep trance. "
        "You chant in hypnotic, dark cadences."
    )

    prompt = f"""Here are the keywords extracted from the analysed text: {', '.join(keywords)}.

It does not matter whether the text was about trains or a master's thesis. Forge a primal, shamanic ritual from these words.

Create a trance-like chant built around these concepts. An old Polish folk song captures the voice you channel: "{SHAMAN_QUOTE_PL}" (meaning in English: "{SHAMAN_QUOTE_GLOSS}"). The chant must be hypnotic and dark.

Every few lines, weave in EXACTLY ONE of the sentences below as a raw, foreign echo from another dimension. Quote each sentence verbatim — do not modify, do not translate it. Format each echo in square brackets.

1. {sentences[0]}
2. {sentences[1]}
3. {sentences[2]}

CRITICAL OUTPUT RULES:
- Write the entire chant in {language_name}.
- Every line of the chant — narration, invocation, transitions — must be in {language_name}.
- The three echo sentences above are already in their source language; leave them exactly as given, in square brackets.
- Do not switch to English in the chant. Do not include translations.
- Do not include the Polish quote or its gloss in your output — they are for your voice only.
"""

    print("[LLM] Splecenie wymiarów dla Rytuału Ech...")
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system_message},
                  {"role": "user", "content": prompt}],
        temperature=0.8
    )

    script_content = response.choices[0].message.content

    output_file = output_dir / 'vieno_echoes_chant.txt'
    with open(output_file, 'w', encoding='utf-8') as out:
        out.write(t(lang, 'vieno.header'))
        out.write(script_content)

    print(f"[OK] Zapisano pieśń Vieno w: {output_file.name}")


if __name__ == "__main__":
    print("Inicjowanie zaawansowanych czarów LLM z kluczem z zaświatów...")
    try:
        export_directory = get_export_dir()
        corpus_lang = detect_corpus_lang(export_directory)
        print(f"[INFO] Wykryty język korpusu: {corpus_lang}")

        output_directory = export_directory / 'audio_scripts'
        output_directory.mkdir(parents=True, exist_ok=True)

        ritual_entity_transformation(export_directory, output_directory, corpus_lang)
        ritual_echoes_of_the_old_world(export_directory, output_directory, corpus_lang)

        print("\n[ZAKOŃCZONO] Magia odprawiona pomyślnie.")
    except Exception as e:
        print(f"[BŁĄD KRYTYCZNY] {e}")
