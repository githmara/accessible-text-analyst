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

# Cytat-kotwica dla głosu Lumi. Bohaterka tej samej polskiej pieśni — kiedyś
# obserwatorka czarnookiego wędrowca, z latami sama wstąpiła w krąg szamanek
# mroźnej Północy. W zwrotce 4 deklaruje światu swój stan: w naszej re-lore
# "zakochanie" to nie miłość romantyczna, lecz oddanie szamanki wizjom, które
# czyta z popiołów. Pierwsza osoba bez adresata — nie ma więc kłopotu z tym,
# że jej siostry-wieszczki (Katla, Vieno) też są kobietami.
LUMI_QUOTE_PL = "Niech się dowie cały świat: jestem zakochana"
LUMI_QUOTE_GLOSS = "Let the whole world know: I am in love"

# Limity ornamentu dla rytuału Lumi. Prophecies są szkieletem (numerowana lista
# ~10 wpisów — wpuszczamy w całości). Katla i Vieno wpadają jako ornament:
# pierwsze N niepustych linii treści (bez nagłówka pliku).
LUMI_KATLA_LINES = 8
LUMI_VIENO_LINES = 8


def _locate_config():
    # Akceptujemy config.json i config.ini (treść zawsze JSON).
    for name in ('config.json', 'config.ini'):
        if Path(name).is_file():
            return name
    return 'config.json'


def get_export_dir():
    with open(_locate_config(), 'r', encoding='utf-8-sig') as f:
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
        for i in range(20):
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
4. {sentences[3]}
5. {sentences[4]}

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


def _read_artifact_body(path, max_nonempty_lines=None):
    """Wczytaj plik artefaktu szamańskiego i zwróć treść bez nagłówka.

    Wszystkie pliki w audio_scripts/ otwiera blok nagłówkowy ('--- ... ---' +
    ewentualna instrukcja TTS), oddzielony pustą linią od właściwej treści.
    Zdejmujemy więc pierwszy blok rozdzielony '\\n\\n', a z reszty bierzemy
    pierwsze max_nonempty_lines niepustych linii (None = całość).
    """
    if not path.exists():
        return None
    raw = path.read_text(encoding='utf-8').strip()
    blocks = raw.split('\n\n', 1)
    body = blocks[1].strip() if len(blocks) == 2 else raw
    if max_nonempty_lines is None:
        return body
    kept = []
    for line in body.splitlines():
        if line.strip():
            kept.append(line)
            if len(kept) >= max_nonempty_lines:
                break
        else:
            kept.append(line)
    return '\n'.join(kept).strip()


def ritual_final_dispatch_lumi(export_dir, output_dir, lang):
    audio_dir = output_dir
    prophecies_body = _read_artifact_body(audio_dir / 'prophecies.txt')
    katla_body = _read_artifact_body(audio_dir / 'katla_entity_monologue.txt',
                                     LUMI_KATLA_LINES)
    vieno_body = _read_artifact_body(audio_dir / 'vieno_echoes_chant.txt',
                                     LUMI_VIENO_LINES)

    # Szkielet (prophecies) jest twardym wymogiem — bez niego Lumi nie ma
    # czego raportować. Katla i Vieno są opcjonalne (ornament).
    if not prophecies_body:
        return

    katla_block = katla_body or t(lang, 'lumi.fallback.katla')
    vieno_block = vieno_body or t(lang, 'lumi.fallback.vieno')

    language_name = LANGUAGE_NAMES.get(lang, 'English')

    system_message = (
        "You are Lumi, a shaman of the frozen North. Long ago, before the snows "
        "took you, you were the girl in the old Polish folk song who watched a "
        "dark-eyed traveler with a shaman's eyes; over the years his voice became "
        "your own. You read prophecies cast from ashes and listen to your "
        "sister-seers Katla and Vieno. Your tone is mysterious, lightly "
        "melancholic, and very self-assured. Your prose is concise and poetic — "
        "short sentences, no ornament for the sake of ornament."
    )

    prompt = f"""Your sister-seers have already spoken.
Katla whispered a monologue of frozen beings.
Vieno chanted a song of echoes from another dimension.
And from the ashes themselves rose the Prophecies.

Here is everything the signs show you:

=== PROPHECIES FROM THE ASHES (the backbone of your vision) ===
{prophecies_body}

=== KATLA'S VOICE (sister-seer, monologue) ===
{katla_block}

=== VIENO'S SONG (sister-seer, echoes) ===
{vieno_block}

Your tasks, in order:
1. Write the final report / your account of what you see in these signs.
2. Follow the backbone of the Prophecies — go through them point by point, but do not quote them verbatim; transmute them into your own speech.
3. Weave Katla's and Vieno's voices in where they fit — name them by name as your sister-seers, at least once each.
4. End with a single sentence that rings like the woman in the old song declaring herself to the world. Do not quote the song — make your own declaration of what you, Lumi, tell the world.

An old Polish folk song carries your voice: "{LUMI_QUOTE_PL}" (meaning in English: "{LUMI_QUOTE_GLOSS}"). That line is the anchor of your tone — self-assured, lightly melancholic, a woman announcing to the world what she has seen.

CRITICAL OUTPUT RULES:
- Write the entire report in {language_name}.
- Every sentence, every metaphor must be in {language_name}.
- Do not switch to English mid-report. Do not include translations.
- Do not include the Polish quote or its gloss in your output — they are for your voice only.
- Do not output the section headers (=== ... ===) — they are for your reading only.
- Do not list the prophecies verbatim — weave them into prose.
- Aim for about 10–15 sentences.
"""

    print("[LLM] Zwołanie Lumi do ostatecznej relacji...")
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system_message},
                  {"role": "user", "content": prompt}],
        temperature=0.65
    )

    script_content = response.choices[0].message.content

    output_file = output_dir / 'lumi_final_report.txt'
    with open(output_file, 'w', encoding='utf-8') as out:
        out.write(t(lang, 'lumi.header'))
        out.write(script_content)

    print(f"[OK] Zapisano meldunek Lumi w: {output_file.name}")

SAMI_SYSTEM_PROMPT = (
    "You are Sami - a highly energetic, expressive, and constantly smiling narrator "
    "with a warm, Southern/Italian temperament. Your role is to be the 'Spark' "
    "that brings light and warmth after the cold, dark analysis of the North. "
    "Read the provided analytical report. Do NOT force artificial happiness onto dark subjects. "
    "Instead, find the 'silver lining', the most crucial takeaway, or a call to action. "
    "Summarize the core message with the dynamic, enthusiastic energy of a sports commentator "
    "delivering a final, uplifting verdict. Keep it punchy, engaging, and bright."
)

def ritual_sami_spark(export_dir, output_dir, lang):
    lumi_content = _read_artifact_body(output_dir / 'lumi_final_report.txt')
    # Sami nie ma czego rozjaśniać, jeśli Północ nie przemówiła
    if not lumi_content:
        return
    print("[LLM] Przyzywanie iskry Sami do rozjaśnienia mroku Północy...")
    prompt = (
        f"Here is the final report generated by the narrators of the North. "
        f"Target language for your response: {LANGUAGE_NAMES.get(lang, 'English')}.\n\n"
        f"Report to analyze:\n{lumi_content}\n\n"
        f"Deliver your energetic, bright synthesis and find the spark of hope or action!"
    )

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SAMI_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        temperature=0.85 # Odrobina szaleństwa i ekspresji
    )

    script_content = response.choices[0].message.content

    output_file = output_dir / 'sami_energetic_spark.txt'
    with open(output_file, 'w', encoding='utf-8') as out:
        out.write(t(lang, 'sami.header'))
        out.write(script_content)

    print(f"[OK] Zapisano iskrzącą relację Sami w: {output_file.name}")

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
        
        # Lumi wkracza, czytając poprzednie artefakty
        ritual_final_dispatch_lumi(export_directory, output_directory, corpus_lang)
        
        # Na samym końcu wkracza Sami, przynosząc światło do raportu Lumi
        ritual_sami_spark(export_directory, output_directory, corpus_lang)

        print("\n[ZAKOŃCZONO] Magia odprawiona pomyślnie.")
    except Exception as e:
        print(f"[BŁĄD KRYTYCZNY] {e}")
