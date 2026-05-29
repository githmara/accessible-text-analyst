import json
import csv
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from shamanic_locale import detect_corpus_lang, get_ui_lang, t

# Język UI (printy w konsoli) — niezależny od języka korpusu. Pobierany
# z config.json/ini, fallback 'en'. Headery artefaktów (oracle.header itp.)
# nadal idą po języku korpusu, bo TTS czyta je w mowie korpusu.
UI_LANG = get_ui_lang()

# ==========================================
# 1. KONFIGURACJA I LOKALIZACJA PLIKÓW
# ==========================================

def _locate_config():
    # Akceptujemy config.json i config.ini (treść zawsze JSON).
    for name in ('config.json', 'config.ini'):
        if Path(name).is_file():
            return name
    return 'config.json'


def _slugify(s, maxlen=80):
    # Mirror cell_corpus / generate_report._slugify — `.strip("._")` usuwa
    # końcowe podkreślniki/kropki, więc np. `..._przyklad_.docx` → katalog
    # `..._przyklad` (a nie `..._przyklad_`).
    s = re.sub(r"[^\w\-\.]+", "_", s, flags=re.UNICODE).strip("._")
    return s[:maxlen] or "_default"


def get_export_dir():
    # Używamy utf-8-sig by uniknąć problemów z BOM
    with open(_locate_config(), 'r', encoding='utf-8-sig') as f:
        config = json.load(f)

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

    export_dir = Path('export_results') / name
    if not export_dir.exists():
        print(t(UI_LANG, 'pipeline.warn_no_export_dir', path=export_dir))

    return export_dir

# ==========================================
# 2. MODUŁY SZAMAŃSKIE
# ==========================================

def ritual_oracle(export_dir, output_dir, lang):
    theses_file = export_dir / 'theses.csv'
    if not theses_file.exists():
        # theses.csv pisane warunkowo (len(df_theses) > 0) — brak = korpus bez
        # tez (np. zbyt krótki). To dozwolony stan częściowy, pomijamy po cichu.
        return False

    output_file = output_dir / 'oracle_script.txt'

    with open(theses_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        sorted_theses = sorted(reader, key=lambda x: float(x['score']), reverse=True)

    if not sorted_theses:
        raise RuntimeError(t(UI_LANG, 'pipeline.err_faulty_input',
                             filename=theses_file.name, ritual='oracle'))

    # Marker pauzy TTS jest częścią artefaktu czytanego głosem korpusu,
    # więc lokalizujemy go po języku korpusu (nie UI).
    pause = t(lang, 'oracle.pause')
    with open(output_file, 'w', encoding='utf-8') as out:
        out.write(t(lang, 'oracle.header'))

        for row in sorted_theses[:10]:
            sentence = row['sentence'].replace('"', '').strip()
            phrases = sentence.split(',')
            for phrase in phrases:
                if phrase.strip():
                    out.write(f"{phrase.strip()}...\n{pause}\n")
            out.write("\n")

    print(t(UI_LANG, 'pipeline.ok_oracle', filename=output_file.name))
    return True

def ritual_lore_fragments(export_dir, output_dir, lang):
    paragraphs_file = export_dir / 'paragraphs_with_topics.csv'
    if not paragraphs_file.exists():
        # Tematy pisane warunkowo (len(df_topics) > 0 — wymaga wektorów modelu
        # _lg). Brak = dozwolony stan częściowy (model bez wektorów), pomijamy.
        return False

    lore_dir = output_dir / 'lore_fragments'
    lore_dir.mkdir(exist_ok=True)

    written = 0
    with open(paragraphs_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            topic_id = row['topic']
            para_id = row['para_id']
            text = row['paragraph'].replace('"', '')

            fragment_file = lore_dir / f"intercepted_log_T{topic_id}_P{para_id}.txt"
            with open(fragment_file, 'w', encoding='utf-8') as out:
                out.write(t(lang, 'lore.header', topic_id=topic_id, para_id=para_id))
                out.write(text)
            written += 1

    if written == 0:
        raise RuntimeError(t(UI_LANG, 'pipeline.err_faulty_input',
                             filename=paragraphs_file.name, ritual='lore'))

    print(t(UI_LANG, 'pipeline.ok_lore', dirname=lore_dir.name))
    return True

def ritual_raw_roots(export_dir, output_dir, lang):
    tfidf_file = export_dir / 'keywords_tfidf.csv'
    if not tfidf_file.exists():
        # keywords_tfidf.csv pisane warunkowo — brak = dozwolony stan częściowy.
        return False

    output_file = output_dir / 'raw_roots_chant.txt'

    with open(tfidf_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        words = [row['term'] for row in reader]

    if not words:
        raise RuntimeError(t(UI_LANG, 'pipeline.err_faulty_input',
                             filename=tfidf_file.name, ritual='raw_roots'))

    with open(output_file, 'w', encoding='utf-8') as out:
        out.write(t(lang, 'roots.header'))

        for i in range(0, min(50, len(words)), 3):
            chant = " . ".join(words[i:i + 3])
            out.write(f"{chant.upper()} .\n")

    print(t(UI_LANG, 'pipeline.ok_roots', filename=output_file.name))
    return True

def ritual_etymological_prophesy(export_dir, output_dir, lang):
    entities_file = export_dir / 'entities.csv'
    paragraphs_file = export_dir / 'paragraphs.csv'
    # paragraphs.csv pisze KAŻDE udane wykonanie komórki eksportowej — jego brak
    # to twardy sygnał, że notebook się nie wykonał (a nie dozwolony stan
    # częściowy). Strażnik w __main__ łapie to wcześniej, ale zostawiamy
    # asekurację na wypadek wywołania rytuału w izolacji.
    if not paragraphs_file.exists():
        raise RuntimeError(t(UI_LANG, 'pipeline.err_no_notebook_output',
                             path=paragraphs_file))

    # entities.csv jest OPCJONALNE dla przepowiedni. Szablony mają fallbacki
    # loc/per/org (przez pick()), a w obecnej konfiguracji i tak wszystkie mogą
    # trafić na fallback, jeśli akurat żaden z wylosowanych paragrafów nie miał
    # encji. Skoro paragraphs.csv parsuje się poprawnie, przepowiednie da się
    # zbudować — brak encji to po prostu zbiór encji pusty, nie powód do
    # pominięcia rytuału.
    counts_by_label = {}
    if entities_file.exists():
        with open(entities_file, 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                ent = (row.get('entity') or '').strip()
                lbl = (row.get('label') or '').strip()
                if ent and lbl:
                    counts_by_label.setdefault(lbl, Counter())[ent] += 1

    def top_n(labels, n=10):
        merged = Counter()
        for lbl in labels:
            merged.update(counts_by_label.get(lbl, Counter()))
        return [e for e, _ in merged.most_common(n)]

    locations = top_n(['LOC', 'GPE'])
    persons   = top_n(['PERSON', 'PER'])
    orgs      = top_n(['ORG'])

    with open(paragraphs_file, 'r', encoding='utf-8-sig') as f:
        paragraphs = list(csv.DictReader(f))
    paragraphs.sort(key=lambda r: len(r.get('paragraph') or ''), reverse=True)
    top_paragraphs = paragraphs[:10]

    if not top_paragraphs:
        raise RuntimeError(t(UI_LANG, 'pipeline.err_faulty_input',
                             filename=paragraphs_file.name, ritual='prophecy'))

    def first_sentence(text):
        # Pierwszy znak kończący zdanie po przynajmniej 10 znakach, ale nie dalej niż 300.
        best = -1
        for end in '.!?':
            i = text.find(end, 10)
            if i != -1 and (best == -1 or i < best):
                best = i
        if 0 <= best <= 300:
            return text[:best + 1].strip()
        return text[:200].strip().rstrip(',;:') + '...'

    templates = t(lang, 'prophecy.templates')
    fallback = {
        'loc': t(lang, 'prophecy.fallback.loc'),
        'per': t(lang, 'prophecy.fallback.per'),
        'org': t(lang, 'prophecy.fallback.org'),
    }

    def pick(seq, idx, key):
        return seq[idx % len(seq)] if seq else fallback[key]

    output_file = output_dir / 'prophecies.txt'
    with open(output_file, 'w', encoding='utf-8') as out:
        out.write(t(lang, 'prophecy.header'))
        for i, p in enumerate(top_paragraphs):
            tpl = templates[i % len(templates)]
            line = tpl.format(
                loc=pick(locations, i, 'loc'),
                per=pick(persons, i, 'per'),
                org=pick(orgs, i, 'org'),
                sentence=first_sentence(p['paragraph']),
            )
            out.write(t(lang, 'prophecy.section', n=i + 1) + '\n')
            out.write(line + '\n\n')

    print(t(UI_LANG, 'pipeline.ok_prophecies', filename=output_file.name))
    return True

def ritual_emotional_undertow(export_dir, output_dir, lang):
    """Lokalny (offline) rytuał karmiony OPCJONALNYM sentiment.csv.

    Brak pliku = sentyment wyłączony albo się nie powiódł → po prostu nie
    tworzymy artefaktu (zachowanie domyślne). Surowe dane: nie filtrujemy
    ani po pewności, ani po języku — bierzemy każdy akapit po kolei i
    układamy z nastrojów „pływ" tekstu (mantra przypływu/odpływu), a na
    końcu dorzucamy bilans."""
    sentiment_file = export_dir / 'sentiment.csv'
    if not sentiment_file.exists():
        # Sentyment jest w pełni opcjonalny (enable_sentiment domyślnie false) —
        # jego brak to NIE błąd, tylko wyłączona funkcja. Pomijamy po cichu.
        return False

    with open(sentiment_file, 'r', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return False

    mood = {
        'negative': t(lang, 'undertow.mood_negative'),
        'neutral':  t(lang, 'undertow.mood_neutral'),
        'positive': t(lang, 'undertow.mood_positive'),
    }

    def mood_word(label):
        return mood.get((label or '').strip().lower(), (label or '?').strip())

    output_file = output_dir / 'emotional_undertow.txt'
    with open(output_file, 'w', encoding='utf-8') as out:
        out.write(t(lang, 'undertow.header'))

        # Pływ: po jednym słowie-nastroju na akapit, po kolei, 4 na linię.
        words = [mood_word(r.get('label')) for r in rows]
        for i in range(0, len(words), 4):
            chant = " . ".join(w.upper() for w in words[i:i + 4])
            out.write(f"{chant} .\n")
        out.write("\n")

        # Bilans pływu (sury liczbowe — szaman widzi całość).
        counts = Counter((r.get('label') or '').strip().lower() for r in rows)
        total = sum(counts.values()) or 1
        out.write(t(lang, 'undertow.summary_header') + "\n")
        for key in ('negative', 'neutral', 'positive'):
            c = counts.get(key, 0)
            out.write(f"{mood[key]}: {c} ({round(c * 100 / total)}%)\n")

    print(t(UI_LANG, 'pipeline.ok_undertow', filename=output_file.name))
    return True

# ==========================================
# 3. GŁÓWNY POTOK
# ==========================================

if __name__ == "__main__":
    print(t(UI_LANG, 'pipeline.starting'))

    try:
        export_directory = get_export_dir()

        # Krytyczny strażnik. paragraphs.csv pisze KAŻDE udane wykonanie komórki
        # eksportowej notebooka. Jego brak (lub brak katalogu) oznacza, że
        # notebook się nie wykonał — przerywamy z czytelnym komunikatem, zamiast
        # po cichu odprawić zero rytuałów i skłamać „[ZAKOŃCZONO]".
        para_csv = export_directory / 'paragraphs.csv'
        if not export_directory.exists() or not para_csv.exists():
            raise RuntimeError(t(UI_LANG, 'pipeline.err_no_notebook_output',
                                 path=para_csv))

        corpus_lang = detect_corpus_lang(export_directory)
        print(t(UI_LANG, 'pipeline.info_detected_lang', language=corpus_lang))

        output_directory = export_directory / 'audio_scripts'
        output_directory.mkdir(parents=True, exist_ok=True)

        # Lokalne rytuały są od siebie niezależne: błąd jednego (wadliwy plik
        # wejściowy) nie przerywa pozostałych. Zbieramy wyniki i dopiero na
        # końcu decydujemy, czy wolno ogłosić sukces.
        rituals = (
            ('oracle', ritual_oracle),
            ('lore', ritual_lore_fragments),
            ('raw_roots', ritual_raw_roots),
            ('prophecy', ritual_etymological_prophesy),
            ('undertow', ritual_emotional_undertow),
        )
        produced = 0
        failures = []
        for name, fn in rituals:
            try:
                if fn(export_directory, output_directory, corpus_lang):
                    produced += 1
            except Exception as e:
                failures.append(name)
                print(t(UI_LANG, 'pipeline.warn_ritual_failed', ritual=name, error=e))

        if failures:
            # Coś poszło nie tak — nie wolno udawać, że wszystko gotowe.
            print(f"\n{t(UI_LANG, 'pipeline.done_with_errors', failed=len(failures), total=len(rituals))}")
        elif produced == 0:
            # Katalog istnieje, ale żaden artefakt nie powstał — pipeline ledwo
            # się wykonał albo eksport jest niekompletny.
            print(f"\n{t(UI_LANG, 'pipeline.warn_nothing_produced', path=export_directory)}")
        else:
            print(f"\n{t(UI_LANG, 'pipeline.done')}")

    except Exception as e:
        print(t(UI_LANG, 'pipeline.fatal_error', error=e))
