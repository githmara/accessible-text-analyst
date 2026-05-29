import os
import json
import csv
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse
from openai import OpenAI
from dotenv import load_dotenv

from shamanic_locale import detect_corpus_lang, get_ui_lang, t, LANGUAGE_NAMES

# Język UI (printy w konsoli) — niezależny od języka korpusu. Pobierany
# z config.json/ini, fallback 'en'. Headery artefaktów (katla.header itp.)
# i body LLM-owe nadal idą po języku korpusu, bo TTS i model czytają je
# w mowie korpusu.
UI_LANG = get_ui_lang()

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

# Limity ornamentu dla rytuału Lumi pobierane są z configa
# (lumi_katla_lines, lumi_vieno_lines). Prophecies są szkieletem
# (numerowana lista ~10 wpisów — wpuszczamy w całości). Katla i Vieno
# wpadają jako ornament: brak klucza w configu lub null = cała treść;
# integer N > 0 = pierwsze N niepustych linii treści (bez nagłówka pliku).


def _locate_config():
    # Akceptujemy config.json i config.ini (treść zawsze JSON).
    for name in ('config.json', 'config.ini'):
        if Path(name).is_file():
            return name
    return 'config.json'


def _load_config():
    try:
        with open(_locate_config(), 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _lumi_line_limit(config, key):
    """None = brak limitu (cała treść). Integer N > 0 = limit linii.
    Każda inna wartość (null, 0, ujemna, nie-int) traktowana jako brak limitu."""
    value = config.get(key)
    if value is None:
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _slugify(s, maxlen=80):
    # Mirror cell_corpus / generate_report._slugify — `.strip("._")` usuwa
    # końcowe podkreślniki/kropki, więc np. `..._przyklad_.docx` → katalog
    # `..._przyklad` (a nie `..._przyklad_`).
    s = re.sub(r"[^\w\-\.]+", "_", s, flags=re.UNICODE).strip("._")
    return s[:maxlen] or "_default"


def get_export_dir():
    config = _load_config()
    source_path = (config.get('source_file') or '').strip()
    if not source_path:
        name = "_default"
    elif source_path.startswith(("http://", "https://")):
        u = urlparse(source_path)
        host = (u.netloc or "url").replace("www.", "")
        path = u.path.strip("/").replace("/", "_") or "index"
        name = _slugify(f"{host}_{path}")
    else:
        name = _slugify(Path(source_path).stem)
    return Path('export_results') / name


def ritual_entity_transformation(export_dir, output_dir, lang):
    entities_file = export_dir / 'entities.csv'
    if not entities_file.exists():
        # entities.csv pisane warunkowo (tylko gdy są encje) — brak = dozwolony
        # stan częściowy, pomijamy po cichu.
        return False

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

    print(t(UI_LANG, 'ai.llm_katla'))
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

    print(t(UI_LANG, 'ai.ok_katla', filename=output_file.name))
    return True


def ritual_echoes_of_the_old_world(export_dir, output_dir, lang):
    topics_file = export_dir / 'topic_keywords.json'
    if not topics_file.exists():
        # topic_keywords.json pisane warunkowo (wymaga wektorów modelu _lg) —
        # brak = dozwolony stan częściowy, pomijamy po cichu.
        return False

    with open(topics_file, 'r', encoding='utf-8-sig') as f:
        topics = json.load(f)
        keywords = []
        for i in range(20):
            if str(i) in topics:
                keywords.extend(topics[str(i)])

    language_name = LANGUAGE_NAMES.get(lang, 'English')

    system_message = (
        "You are a shaman with black eyes, falling into a deep trance. "
        "You chant in hypnotic, dark cadences."
    )

    # Rozgałęzienie. Jeśli włączono OPCJONALNY sentyment i się powiódł
    # (sentiment.csv istnieje i ma wiersze), Vieno buduje pieśń na PEŁNEJ,
    # surowej analizie sentymentu — zamiast na 5 surowych zdaniach. Słowa
    # kluczowe zostają w obu wariantach. Jeśli sentymentu nie ma (wyłączony
    # albo coś poszło nie tak — np. brak tiktoken, bez fallbacku), schodzimy
    # na ścieżkę domyślną z echami zdań z sentences.csv (jak dotychczas).
    sentiment_file = export_dir / 'sentiment.csv'
    sentiment_rows = []
    if sentiment_file.exists():
        with open(sentiment_file, 'r', encoding='utf-8-sig') as f:
            sentiment_rows = [r for r in csv.DictReader(f)
                              if (r.get('label') or '').strip()]

    if sentiment_rows:
        # Łuk segmentowy. „Cała surowa analiza" nie mieści się w limicie TPM
        # dla długich korpusów (np. 2579 akapitów = ~32k tokenów > 30k TPM),
        # więc małe korpusy (<= _SENT_MAX_RAW akapitów) dostają pełne surowe
        # wiersze, a większe — downsampling do <= _SENT_SEGMENTS segmentów
        # (dominujący nastrój + miks per segment). Vieno i tak czyta to jako
        # emocjonalny kontur całości, nie potrzebuje 2579 punktów danych.
        _SENT_MAX_RAW = 150
        _SENT_SEGMENTS = 40

        def _label_of(r):
            return (r.get('label') or '').strip().lower()

        total = len(sentiment_rows)
        dist = Counter(_label_of(r) for r in sentiment_rows)
        dist_line = ", ".join(
            f"{lab}: {dist.get(lab, 0)}" for lab in ('negative', 'neutral', 'positive'))

        if total <= _SENT_MAX_RAW:
            mode_note = "the full raw analysis, paragraph by paragraph (label + confidence)"
            body_lines = [
                f"Paragraph {r.get('para_id', '?')} [{r.get('lang', '?')}]: "
                f"{r.get('label', '?')} (confidence {r.get('score', '?')})"
                for r in sentiment_rows
            ]
        else:
            seg = -(-total // _SENT_SEGMENTS)  # ceil — rozmiar jednego segmentu
            mode_note = (f"a downsampled emotional arc of the whole text "
                         f"({total} paragraphs condensed into segments, in reading order)")
            body_lines = []
            for i in range(0, total, seg):
                chunk = sentiment_rows[i:i + seg]
                c = Counter(_label_of(r) for r in chunk)
                dom = c.most_common(1)[0][0] if c else '?'
                mix = ", ".join(f"{k} {v}" for k, v in c.most_common())
                body_lines.append(
                    f"Paragraphs {chunk[0].get('para_id', '?')}-{chunk[-1].get('para_id', '?')}: "
                    f"{dom} (mix: {mix})")

        analysis_block = (
            f"Overall mood distribution across {total} paragraphs: {dist_line}.\n"
            f"Below is {mode_note}:\n\n" + "\n".join(body_lines))

        prompt = f"""Here are the keywords extracted from the analysed text: {', '.join(keywords)}.

This is the emotional cartography of the whole work — read it as the rise and fall of mood from beginning to end: where it sinks into the negative, where it rests in the neutral, where it lifts to the positive.

{analysis_block}

It does not matter whether the text was about trains or a master's thesis. Forge a primal, shamanic trance-chant from the keywords above, and let this emotional arc shape its DYNAMICS — let the chant darken across the negative stretches and let light break through where the mood turns positive. An old Polish folk song captures the voice you channel: "{SHAMAN_QUOTE_PL}" (meaning in English: "{SHAMAN_QUOTE_GLOSS}"). The chant must be hypnotic and dark.

CRITICAL OUTPUT RULES:
- Write the entire chant in {language_name}.
- Every line of the chant — narration, invocation, transitions — must be in {language_name}.
- Do not switch to English. Do not include translations.
- Do not dump the raw analysis back; transmute the moods into imagery and rhythm.
- Do not include the Polish quote or its gloss in your output — they are for your voice only.
- Do not list the keywords verbatim — weave them into the chant.
"""
    else:
        sentences_file = export_dir / 'sentences.csv'
        # sentences.csv pisze KAŻDE udane wykonanie komórki eksportowej. Skoro
        # tematy istnieją (dotarliśmy tu), to jego brak oznacza uszkodzony
        # eksport — sygnalizujemy wyjątkiem, nie cichym pominięciem.
        if not sentences_file.exists():
            raise RuntimeError(t(UI_LANG, 'ai.err_no_notebook_output',
                                 path=sentences_file))

        sentences = []
        with open(sentences_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                sentences.append(row['sentence'])
                if len(sentences) > 5:
                    break
        if len(sentences) < 5:
            # Ostrzegawczy wyjątek: zbyt mało surowych zdań na pełnowartościową
            # pieśń. Przerywamy ten rytuał (ale nie cały potok), żeby nie ogłosić
            # sukcesu przy ubogim/uszkodzonym sentences.csv.
            raise RuntimeError(t(UI_LANG, 'ai.warn_vieno_too_few_sentences',
                                 count=len(sentences)))

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

    print(t(UI_LANG, 'ai.llm_vieno'))
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

    print(t(UI_LANG, 'ai.ok_vieno', filename=output_file.name))
    return True


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
    config = _load_config()
    katla_limit = _lumi_line_limit(config, 'lumi_katla_lines')
    vieno_limit = _lumi_line_limit(config, 'lumi_vieno_lines')
    prophecies_body = _read_artifact_body(audio_dir / 'prophecies.txt')
    katla_body = _read_artifact_body(audio_dir / 'katla_entity_monologue.txt',
                                     katla_limit)
    vieno_body = _read_artifact_body(audio_dir / 'vieno_echoes_chant.txt',
                                     vieno_limit)

    # Szkielet (prophecies) jest twardym wymogiem — bez niego Lumi nie ma
    # czego raportować. Katla i Vieno są opcjonalne (ornament). prophecies.txt
    # powstaje w LOKALNYM potoku (shamanic_pipeline.py), nie tu — jego brak to
    # zwykle „nie odpalono najpierw lokalnego potoku", więc Lumi (a po niej
    # Sami) milkną po cichu, zgodnie z dotychczasowym zachowaniem.
    if not prophecies_body:
        return False

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

    print(t(UI_LANG, 'ai.llm_lumi'))
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

    print(t(UI_LANG, 'ai.ok_lumi', filename=output_file.name))
    return True

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
    # Sami nie ma czego rozjaśniać, jeśli Północ nie przemówiła (Lumi milczała)
    # — milkniemy po cichu, tak jak Lumi.
    if not lumi_content:
        return False
    print(t(UI_LANG, 'ai.llm_sami'))
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

    print(t(UI_LANG, 'ai.ok_sami', filename=output_file.name))
    return True

if __name__ == "__main__":
    print(t(UI_LANG, 'ai.starting'))
    try:
        export_directory = get_export_dir()

        # Krytyczny strażnik. Brak katalogu eksportu = notebook się nie wykonał.
        if not export_directory.exists():
            raise RuntimeError(t(UI_LANG, 'ai.err_no_export_dir',
                                 path=export_directory))

        corpus_lang = detect_corpus_lang(export_directory)
        print(t(UI_LANG, 'ai.info_detected_lang', language=corpus_lang))

        output_directory = export_directory / 'audio_scripts'
        output_directory.mkdir(parents=True, exist_ok=True)

        # Rytuały odpalamy po kolei (Lumi czyta Katlę/Vieno, Sami czyta Lumi),
        # ale każdy w osobnym try: błąd jednego głosu nie ucina pozostałych.
        # Zbieramy wyniki i dopiero na końcu decydujemy o komunikacie końcowym —
        # nie wolno ogłosić sukcesu, jeśli któryś głos zawiódł.
        rituals = (
            ('katla', ritual_entity_transformation),
            ('vieno', ritual_echoes_of_the_old_world),
            ('lumi', ritual_final_dispatch_lumi),
            ('sami', ritual_sami_spark),
        )
        produced = 0
        failures = []
        for name, fn in rituals:
            try:
                if fn(export_directory, output_directory, corpus_lang):
                    produced += 1
            except Exception as e:
                failures.append(name)
                print(t(UI_LANG, 'ai.warn_ritual_failed', ritual=name, error=e))

        if failures:
            print(f"\n{t(UI_LANG, 'ai.done_with_errors', failed=len(failures), total=len(rituals))}")
        elif produced == 0:
            print(f"\n{t(UI_LANG, 'ai.warn_nothing_produced', path=export_directory)}")
        else:
            print(f"\n{t(UI_LANG, 'ai.done')}")
    except Exception as e:
        print(t(UI_LANG, 'ai.fatal_error', error=e))
