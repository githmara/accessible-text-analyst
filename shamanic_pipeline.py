import json
import csv
from collections import Counter
from pathlib import Path

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


def get_export_dir():
    # Używamy utf-8-sig by uniknąć problemów z BOM
    with open(_locate_config(), 'r', encoding='utf-8-sig') as f:
        config = json.load(f)

    source_path = config.get('source_file', '')
    basename = Path(source_path).stem

    export_dir = Path('export_results') / basename
    if not export_dir.exists():
        print(t(UI_LANG, 'pipeline.warn_no_export_dir', path=export_dir))

    return export_dir

# ==========================================
# 2. MODUŁY SZAMAŃSKIE
# ==========================================

def ritual_oracle(export_dir, output_dir, lang):
    theses_file = export_dir / 'theses.csv'
    if not theses_file.exists():
        return

    output_file = output_dir / 'oracle_script.txt'

    with open(theses_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        sorted_theses = sorted(reader, key=lambda x: float(x['score']), reverse=True)

    with open(output_file, 'w', encoding='utf-8') as out:
        out.write(t(lang, 'oracle.header'))

        for row in sorted_theses[:10]:
            sentence = row['sentence'].replace('"', '').strip()
            phrases = sentence.split(',')
            for phrase in phrases:
                if phrase.strip():
                    out.write(f"{phrase.strip()}...\n[PAUZA 1.5s]\n")
            out.write("\n")

    print(t(UI_LANG, 'pipeline.ok_oracle', filename=output_file.name))

def ritual_lore_fragments(export_dir, output_dir, lang):
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

            fragment_file = lore_dir / f"intercepted_log_T{topic_id}_P{para_id}.txt"
            with open(fragment_file, 'w', encoding='utf-8') as out:
                out.write(t(lang, 'lore.header', topic_id=topic_id, para_id=para_id))
                out.write(text)

    print(t(UI_LANG, 'pipeline.ok_lore', dirname=lore_dir.name))

def ritual_raw_roots(export_dir, output_dir, lang):
    tfidf_file = export_dir / 'keywords_tfidf.csv'
    if not tfidf_file.exists():
        return

    output_file = output_dir / 'raw_roots_chant.txt'

    with open(tfidf_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        words = [row['term'] for row in reader]

    with open(output_file, 'w', encoding='utf-8') as out:
        out.write(t(lang, 'roots.header'))

        for i in range(0, min(50, len(words)), 3):
            chant = " . ".join(words[i:i + 3])
            out.write(f"{chant.upper()} .\n")

    print(t(UI_LANG, 'pipeline.ok_roots', filename=output_file.name))

def ritual_etymological_prophesy(export_dir, output_dir, lang):
    entities_file = export_dir / 'entities.csv'
    paragraphs_file = export_dir / 'paragraphs.csv'
    if not entities_file.exists() or not paragraphs_file.exists():
        return

    # Częstotliwość encji per etykieta — top-N w obrębie każdej grupy.
    counts_by_label = {}
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
        return

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

# ==========================================
# 3. GŁÓWNY POTOK
# ==========================================

if __name__ == "__main__":
    print(t(UI_LANG, 'pipeline.starting'))

    try:
        export_directory = get_export_dir()
        corpus_lang = detect_corpus_lang(export_directory)
        print(t(UI_LANG, 'pipeline.info_detected_lang', language=corpus_lang))

        output_directory = export_directory / 'audio_scripts'
        output_directory.mkdir(parents=True, exist_ok=True)

        ritual_oracle(export_directory, output_directory, corpus_lang)
        ritual_lore_fragments(export_directory, output_directory, corpus_lang)
        ritual_raw_roots(export_directory, output_directory, corpus_lang)
        ritual_etymological_prophesy(export_directory, output_directory, corpus_lang)

        print(f"\n{t(UI_LANG, 'pipeline.done')}")

    except Exception as e:
        print(t(UI_LANG, 'pipeline.fatal_error', error=e))
