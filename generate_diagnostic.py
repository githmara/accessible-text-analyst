"""Generator pełnego raportu diagnostycznego z eksportów notebooka.

W przeciwieństwie do `generate_report.py` (który przepisuje stdout komórek
notebooka) oraz modułów szamańskich (które tworzą artefakty TTS), ten skrypt
czyta WYŁĄCZNIE pliki CSV/JSON z `export_results/<project_dir>/` i buduje z nich
ustrukturyzowany, nawigowalny dla czytników ekranu raport HTML
(`diagnostic_report.html`): spis treści, przegląd, tematy z przypisanymi
akapitami, tezy (kluczowe zdania), nazwane encje pogrupowane wg typu oraz
najważniejsze słowa kluczowe.

Cel dostępnościowy: zamiast jednej monolitycznej „ściany" outputu, każda sekcja
ma własny nagłówek (h2/h3) i listę — czytnik ekranu przeskakuje między punktami
orientacyjnymi. Treść korpusu dostaje `lang="<corpus_lang>"`, etykiety NER —
`lang="en"`, a etykiety strukturalne są w `UI_LANG` (zgodnym z `<html lang>`).

Dane (per-akapitowy rozkład tokenów/POS/NER) nie są tu dostępne — notebook ich
nie eksportuje — więc raport organizujemy wokół tego, co MAMY: tematów, tez,
encji i słów kluczowych. Por. `generate_report.py` (widok czytelnika).
"""
import csv
import html as _html
import json
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from shamanic_locale import detect_corpus_lang, get_ui_lang, t

# ── Konfiguracja i ścieżki (konwencja repo: config.json, potem config.ini) ──
UI_LANG = get_ui_lang()
CONFIG_CANDIDATES = ("config.json", "config.ini")
EXPORT_ROOT = Path("export_results")
OUTPUT_NAME = "diagnostic_report.html"

# Limity „pokazujemy pierwsze N" — ta sama filozofia, co skracanie w
# generate_report.py: czytnik ekranu dostaje reprezentatywną próbkę plus liczbę,
# a nie tysiące pozycji. Formuła „... i jeszcze N" jest tu zlokalizowana
# (diagnostic.more_items), bo etykiety raportu są w UI_LANG.
KEEP_TOPIC_PARAS = 100
KEEP_THESES = 100
KEEP_ENTITIES_PER_LABEL = 50
KEEP_KEYWORDS = 100


def _locate_config():
    for name in CONFIG_CANDIDATES:
        if Path(name).is_file():
            return name
    return CONFIG_CANDIDATES[0]


def _slugify(s, maxlen=80):
    import re
    s = re.sub(r"[^\w\-\.]+", "_", s, flags=re.UNICODE).strip("._")
    return s[:maxlen] or "_default"


def _resolve_project_dir(config_path):
    """Mirror cell_corpus / generate_report: slug ze stem-u pliku źródłowego."""
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


# ── Wczytywanie eksportów ──────────────────────────────────────────────────
def _read_csv(path):
    """Wczytaj CSV (UTF-8 z BOM od notebooka) jako listę słowników; [] gdy brak."""
    if not path.is_file():
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _read_json(path):
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


# ── Pomocnicy HTML (lang-tagging) ───────────────────────────────────────────
CORPUS_LANG = "en"  # nadpisane w build_diagnostic_html() po detekcji


def _corpus(text):
    """Owiń treść korpusu w span z lang korpusu (pomiń, gdy == UI_LANG)."""
    esc = _html.escape(str(text))
    if CORPUS_LANG and CORPUS_LANG != UI_LANG:
        return f'<span lang="{CORPUS_LANG}">{esc}</span>'
    return esc


def _en(text):
    """Etykiety techniczne (NER-labels) są zawsze anglojęzyczne."""
    return f'<span lang="en">{_html.escape(str(text))}</span>'


def _more(remaining, shown):
    return t(UI_LANG, "diagnostic.more_items", n=remaining, shown=shown)


def _fscore(value):
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


# ── Sekcje raportu ──────────────────────────────────────────────────────────
def _section_overview(counts):
    out = ['<section aria-labelledby="overview">',
           f'  <h2 id="overview">{_html.escape(t(UI_LANG, "diagnostic.overview_heading"))}</h2>',
           '  <ul>']
    for key, n in counts:
        out.append(f'    <li>{_html.escape(t(UI_LANG, key, n=n))}</li>')
    out.append('  </ul>')
    out.append('</section>')
    return out


def _section_topics(topic_keywords, paras_by_topic):
    out = ['<section aria-labelledby="topics">',
           f'  <h2 id="topics">{_html.escape(t(UI_LANG, "diagnostic.topics_heading"))}</h2>']
    for tid in sorted(topic_keywords, key=lambda k: (len(k), k)):
        kws = topic_keywords.get(tid) or []
        members = paras_by_topic.get(str(tid), [])
        label = _html.escape(t(UI_LANG, "diagnostic.topic_label", id=tid))
        out.append(f'  <h3>{label}</h3>')
        kw_html = ", ".join(_corpus(w) for w in kws)
        out.append(f'  <p>{_html.escape(t(UI_LANG, "diagnostic.topic_keywords"))}{kw_html}</p>')
        shown = members[:KEEP_TOPIC_PARAS]
        ids = ", ".join(str(pid) for pid in shown)
        prefix = _html.escape(t(UI_LANG, "diagnostic.topic_paragraphs", n=len(members)))
        line = f'  <p>{prefix}{ids}'
        if len(members) > KEEP_TOPIC_PARAS:
            line += " " + _html.escape(_more(len(members) - KEEP_TOPIC_PARAS, KEEP_TOPIC_PARAS))
        out.append(line + '</p>')
    out.append('</section>')
    return out


def _section_theses(theses):
    out = ['<section aria-labelledby="theses">',
           f'  <h2 id="theses">{_html.escape(t(UI_LANG, "diagnostic.theses_heading"))}</h2>']
    ranked = sorted(theses, key=lambda r: float(r.get("score") or 0), reverse=True)
    out.append('  <ol>')
    for row in ranked[:KEEP_THESES]:
        prefix = _html.escape(t(UI_LANG, "diagnostic.thesis_item",
                                pid=row.get("para_id", "?"),
                                score=_fscore(row.get("score"))))
        out.append(f'    <li>{prefix}{_corpus(row.get("sentence", ""))}</li>')
    out.append('  </ol>')
    if len(ranked) > KEEP_THESES:
        out.append(f'  <p>{_html.escape(_more(len(ranked) - KEEP_THESES, KEEP_THESES))}</p>')
    out.append('</section>')
    return out


def _section_entities(entities):
    out = ['<section aria-labelledby="entities">',
           f'  <h2 id="entities">{_html.escape(t(UI_LANG, "diagnostic.entities_heading"))}</h2>']
    by_label = {}
    for row in entities:
        by_label.setdefault(row.get("label", "?"), Counter())[row.get("entity", "")] += 1
    # Etykiety wg liczby wystąpień malejąco (najwydatniejszy typ pierwszy).
    for label in sorted(by_label, key=lambda k: -sum(by_label[k].values())):
        counter = by_label[label]
        suffix = _html.escape(t(UI_LANG, "diagnostic.entity_label_suffix", n=len(counter)))
        out.append(f'  <h3>{_en(label)}{suffix}</h3>')
        out.append('  <ul>')
        for ent, cnt in counter.most_common(KEEP_ENTITIES_PER_LABEL):
            out.append(f'    <li>{_corpus(ent)} ({cnt})</li>')
        out.append('  </ul>')
        if len(counter) > KEEP_ENTITIES_PER_LABEL:
            out.append(f'  <p>{_html.escape(_more(len(counter) - KEEP_ENTITIES_PER_LABEL, KEEP_ENTITIES_PER_LABEL))}</p>')
    out.append('</section>')
    return out


def _section_keywords(keywords):
    out = ['<section aria-labelledby="keywords">',
           f'  <h2 id="keywords">{_html.escape(t(UI_LANG, "diagnostic.keywords_heading"))}</h2>']
    ranked = sorted(keywords, key=lambda r: float(r.get("score") or 0), reverse=True)
    out.append('  <ol>')
    for row in ranked[:KEEP_KEYWORDS]:
        out.append(f'    <li>{_corpus(row.get("term", ""))} — {_fscore(row.get("score"))}</li>')
    out.append('  </ol>')
    if len(ranked) > KEEP_KEYWORDS:
        out.append(f'  <p>{_html.escape(_more(len(ranked) - KEEP_KEYWORDS, KEEP_KEYWORDS))}</p>')
    out.append('</section>')
    return out


def _toc():
    items = [
        ("overview", "diagnostic.overview_heading"),
        ("topics", "diagnostic.topics_heading"),
        ("theses", "diagnostic.theses_heading"),
        ("entities", "diagnostic.entities_heading"),
        ("keywords", "diagnostic.keywords_heading"),
    ]
    out = [f'<nav aria-label="{_html.escape(t(UI_LANG, "diagnostic.toc_heading"))}">',
           f'  <h2>{_html.escape(t(UI_LANG, "diagnostic.toc_heading"))}</h2>',
           '  <ul>']
    for anchor, key in items:
        out.append(f'    <li><a href="#{anchor}">{_html.escape(t(UI_LANG, key))}</a></li>')
    out.append('  </ul>')
    out.append('</nav>')
    return out


# ── Główna funkcja ───────────────────────────────────────────────────────────
def build_diagnostic_html():
    global CORPUS_LANG
    config_path = _locate_config()
    project_dir = _resolve_project_dir(config_path)

    paragraphs = _read_csv(project_dir / "paragraphs.csv")
    sentences = _read_csv(project_dir / "sentences.csv")
    entities = _read_csv(project_dir / "entities.csv")
    theses = _read_csv(project_dir / "theses.csv")
    keywords = _read_csv(project_dir / "keywords_tfidf.csv")
    paras_topics = _read_csv(project_dir / "paragraphs_with_topics.csv")
    topic_keywords = _read_json(project_dir / "topic_keywords.json")

    if not any([paragraphs, sentences, entities, theses, keywords]):
        print(t(UI_LANG, "diagnostic.err_no_exports", path=str(project_dir)))
        sys.exit(1)

    CORPUS_LANG = detect_corpus_lang(project_dir)
    print(t(UI_LANG, "diagnostic.info_corpus_lang", language=CORPUS_LANG))

    paras_by_topic = {}
    for row in paras_topics:
        paras_by_topic.setdefault(str(row.get("topic", "")), []).append(row.get("para_id", "?"))

    counts = [
        ("diagnostic.stat_paragraphs", len(paragraphs)),
        ("diagnostic.stat_sentences", len(sentences)),
        ("diagnostic.stat_entities", len(entities)),
        ("diagnostic.stat_topics", len(topic_keywords)),
        ("diagnostic.stat_keywords", len(keywords)),
    ]

    title = _html.escape(t(UI_LANG, "diagnostic.html_title"))
    html = [
        "<!DOCTYPE html>",
        f'<html lang="{UI_LANG}">',
        "<head>",
        '  <meta charset="utf-8">',
        f"  <title>{title}</title>",
        "  <style>",
        "    body { font-family: Arial, sans-serif; line-height: 1.6; max-width: 900px; margin: 2rem auto; padding: 0 1rem; color: #333; }",
        "    h1, h2, h3 { color: #2c3e50; }",
        "    h2 { margin-top: 2.5rem; border-bottom: 1px solid #ddd; padding-bottom: 0.3rem; }",
        "    nav { background: #f8f9fa; border-left: 4px solid #007bff; padding: 0.5rem 1rem; }",
        "    ul, ol { padding-left: 1.5rem; }",
        "    li { margin: 0.2rem 0; }",
        "  </style>",
        "</head>",
        "<body>",
        "<main>",
        f"  <h1>{title}</h1>",
    ]
    html += _toc()
    html += _section_overview(counts)
    html += _section_topics(topic_keywords, paras_by_topic)
    html += _section_theses(theses)
    html += _section_entities(entities)
    html += _section_keywords(keywords)
    html += ["</main>", "</body>", "</html>"]

    project_dir.mkdir(parents=True, exist_ok=True)
    out_path = project_dir / OUTPUT_NAME
    out_path.write_text("\n".join(html), encoding="utf-8")
    print(t(UI_LANG, "diagnostic.ok_generated", path=str(out_path)))


if __name__ == "__main__":
    build_diagnostic_html()
