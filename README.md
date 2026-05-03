# Accessible Text Analyst

A multilingual NLP pipeline designed for **accessibility with screen readers** (NVDA, JAWS, VoiceOver). All code, console output, and reports are crafted to be parsed cleanly by assistive technology: no ANSI colors, no emoji, no progress bars, no box-drawing characters.

The project consists of two files:

- `accessible_text_analyst.ipynb` — a Jupyter notebook with the complete analysis pipeline (36 cells; the in-notebook narrative is in Russian). It also writes two accessibility artefacts (`accessible_text.html`, `accessible_text.docx`) where every paragraph and every foreign-language sentence carries its own `lang` attribute so screen readers and TTS engines switch voice automatically — even offline.
- `generate_report.py` — a post-processing script that turns the executed notebook into a single accessible HTML file (`raport_analizy.html`). It wraps foreign-corpus fragments in `<span lang="target_lang">` and, regardless of corpus language, hardcodes `<span lang="en">` around technical English content (POS tags, NER labels, spaCy/Hugging Face model identifiers, ASCII filenames). Inline code and code blocks in the narrative are blanket-tagged `lang="en"`.

## What the pipeline does

1. Loads text from a file (`.pdf`, `.txt`, `.docx`, `.html`) or from a URL — stripping repeated headers/footers, sidebars, "Related articles" sections, and similar boilerplate.
2. Detects the corpus language with [`lingua-language-detector`](https://github.com/pemistahl/lingua-py). The dominant language drives the spaCy pipeline; the same detector is reused per paragraph and per sentence to power language-tagged export.
3. Loads the appropriate spaCy model on demand. Loading is wrapped in `functools.lru_cache(maxsize=2)` so multilingual corpora never accumulate more than two models in RAM.
4. Tokenization → stop-word filtering → lemmatization → POS tagging → NER.
5. Vector representations: Bag of Words, TF-IDF + auto-query search with cosine ranking.
6. Structure: sentences → paragraphs (3–6 sentences each) → theses (the best sentence per paragraph). Each paragraph and sentence is tagged with its detected ISO 639-1 code.
7. Topic modeling with KMeans over spaCy paragraph vectors.
8. CSV/JSON export + a textual summary report + an accessibility-tagged HTML and DOCX export + a global HTML report (`raport_analizy.html`).

## Supported languages

| Code | Language   | spaCy model            | NER / vectors |
|------|------------|------------------------|----------------|
| pl   | Polish     | `pl_core_news_lg`      | spaCy          |
| ru   | Russian    | `ru_core_news_lg`      | spaCy          |
| en   | English    | `en_core_web_lg`       | spaCy          |
| it   | Italian    | `it_core_news_lg`      | spaCy          |
| fi   | Finnish    | `fi_core_news_lg`      | spaCy          |
| is   | Icelandic  | `spacy.blank("is")` + Hugging Face | `mideind/IceBERT-base` (vectors), `mideind/icelandic-ner-MIM-GOLD-22` (NER) |

There is no full spaCy model for Icelandic, so two Hugging Face models are wired into a blank pipeline. The first download requires ~700 MB of disk space and an internet connection; subsequent runs reuse the HF cache.

## Language detection

Detection runs at three levels:

1. **Corpus-dominant** — `cell_langdet` votes per document and picks the dominant language as `LANG`. Drives the spaCy pipeline.
2. **Per-paragraph** (`para_langs`) — used as the `<p lang="...">` attribute in `accessible_text.html` and as the default `<w:lang>` for each paragraph in `accessible_text.docx`.
3. **Per-sentence** (`sent_langs`) — used to wrap individual sentences in `<span lang="...">` inside mixed-language paragraphs (HTML) or to set `<w:lang>` on per-sentence runs (DOCX).

Per-paragraph and per-sentence detection uses a deliberately **conservative `_safe_detect()` wrapper** in `cell_para`. Trusting raw lingua output causes audible artefacts: lingua misclassifies short Latin fragments dominated by proper names ("Igor de Lendorf" → it, "Mut se mies, Igor" → en), and a screen reader switching to an English voice for "Igor de Lendorf" then back to Finnish for the next sentence sounds worse than reading the proper name with a Finnish accent.

The wrapper applies these rules in order:

1. **Cyrillic anywhere in the fragment → `ru`.** Unambiguous; works on fragments as short as 3 characters.
2. **Fragment shorter than 30 characters → fallback `LANG`.** Lingua is unreliable on short Latin fragments.
3. **Fragment contains `LANG`'s diacritics (e.g. `ä`/`ö` for `fi`, `ąęć` for `pl`) → fallback `LANG`.** A Finnish sentence with an English quote is still Finnish.
4. **Lingua agrees with `LANG`** → keep it.
5. **Lingua disagrees but the detected language has its OWN diacritics in the fragment** (`à` for it, `ż` for pl, `ð` for is) → trust lingua.
6. **Lingua disagrees and the detected language has no characteristic diacritics in the fragment** (typically `en`) → fallback `LANG`.

The motivation for rule 6 is purely phonetic: an English voice reading Finnish/Polish/Italian fragments produces noticeable distortion ("bełkot fonemów"), whereas a Finnish/Polish/Italian voice reading an English quote with a slight accent is intelligible and unobtrusive. The trade-off is that purely-English sentences embedded in a non-English corpus are read in the dominant voice instead of being switched to English. We accept this trade-off because, in practice, screen-reader users have reported the asymmetric quality cost.

Outliers that survive the heuristic are listed in the `cell_para` output for manual review (`Оставшиеся outlier-предложения...`). Same diacritic logic governs the per-`<code>` heuristic (`_classify_code_lang`) in `generate_report.py` and the per-segment lingua fallback (`_lingua_word_fallback`) for path-like ASCII identifiers.

## Requirements

- Python 3.10 or newer.
- ~1.5 GB of free disk space for spaCy `_lg` models (one per language you install). Add ~700 MB if you opt into Icelandic support (Hugging Face `transformers` + `torch` + IceBERT + MIM-GOLD-22).
- An internet connection on the first run (model downloads).

## Installation

```bash
# 1. Python dependencies
pip install -r requirements.txt

# 2. spaCy models — install only the languages you actually need.
# The *_lg variants are required because topic modeling depends on word vectors.
python -m spacy download pl_core_news_lg
python -m spacy download ru_core_news_lg
python -m spacy download en_core_web_lg
python -m spacy download it_core_news_lg
python -m spacy download fi_core_news_lg

# 3. (Optional) Icelandic support — uncomment `transformers` and `torch`
# in requirements.txt and re-run `pip install -r requirements.txt`.
# IceBERT and MIM-GOLD-22 are then pulled from Hugging Face on first run.
```

## Configuration

Copy `config.example.json` to `config.json` (the latter is in `.gitignore`, so each user keeps their own local copy):

```bash
cp config.example.json config.json
```

Contents of `config.json`:

```json
{
  "source_file": "C:/path/to/document.pdf",
  "custom_patterns": []
}
```

- `source_file` — a path to a file (`.pdf`, `.txt`, `.docx`, `.html`) **or** a URL (`http://`, `https://`). An empty string or a missing file falls back to the built-in example corpus.
- `custom_patterns` — an optional list of regular expressions to strip from the raw text (running heads, footers, repetitive boilerplate). Example: `["Editorial: .*", "Copyright \\d{4}"]`.

## Running

```bash
# 1. Run the whole notebook end-to-end
jupyter notebook accessible_text_analyst.ipynb
# (Cell → Run All)

# 2. Generate the accessible HTML report from the executed notebook
python generate_report.py
# → produces raport_analizy.html in the project root
```

**Important:** the notebook is a sequential pipeline with shared global state. Do not reorder cells, and do not run them out of order.

`generate_report.py` reads cell outputs directly from the `.ipynb` file, so the HTML report must be generated from a freshly executed notebook. If you use `nbstripout` (it is listed in `requirements.txt`), keep in mind that commits strip outputs — generate the report _before_ committing, or disable nbstripout for your workflow.

## Output

Every analyzed corpus gets its own subdirectory under `export_results/`, named after the source file (path and extension stripped) or after a `domain_slug` for URLs. The built-in example corpus uses `export_results/_default/`.

Each subdirectory contains:

| File                            | Description                                              |
|---------------------------------|----------------------------------------------------------|
| `sentences.csv`                 | every sentence with its index and paragraph assignment   |
| `paragraphs.csv`                | paragraphs (3–6 sentences each)                          |
| `theses.csv`, `тезисы.txt`      | one thesis per paragraph (the highest-TF-IDF sentence)   |
| `keywords_tfidf.csv`            | keywords (uni/bi/trigrams) with TF-IDF weights           |
| `paragraphs_with_topics.csv`    | paragraphs with their assigned KMeans topic              |
| `topic_keywords.json`           | keywords per topic                                       |
| `entities.csv`                  | all named entities and their labels                      |
| `accessible_text.html`          | paragraph- and sentence-level `lang` attributes — screen readers switch voice automatically per fragment |
| `accessible_text.docx`          | the same content with `<w:lang>` set per `Run` (`pl-PL`, `ru-RU`, `en-US`, `it-IT`, `fi-FI`, `is-IS`) — Word and SAPI use it offline, no online detector required |

The HTML file (`raport_analizy.html`) lives in the project root and is global — it always reflects the most recently executed notebook.

## Accessibility

This is the project's central value. Everything below is intentional and must be preserved when the pipeline is modified:

- **No ANSI colors, emoji, or pseudographics in stdout.** A screen reader reads every character literally — `[OK]` instead of "🟢", `---` instead of "───━━━".
- **Silenced progress bars** (`tqdm`, `transformers`, `torch`) — `cell_model._silence_hf_progress()` mutes Hugging Face/torch loading bars and warnings before pulling IceBERT and MIM-GOLD-22 for Icelandic.
- **Per-paragraph and per-sentence `lang` tagging in the export.** `accessible_text.html` and `accessible_text.docx` carry an ISO 639-1 code on every paragraph (and on every sentence inside mixed-language paragraphs / runs). NVDA, JAWS, Narrator, VoiceOver, Word, and SAPI all honour those tags and switch voice automatically — even offline.
- **Hardcoded English tagging in the HTML report.** `generate_report.py` always wraps technical English fragments — POS tags (`NOUN`, `VERB`, `ADJ`), NER labels (`PER`, `ORG`, `[orgName]`), spaCy / Hugging Face model identifiers, ASCII filenames, code blocks — in `<span lang="en">`, so they are no longer pronounced through the document-default Russian voice.
- **Per-fragment foreign-corpus tagging in HTML.** When the corpus is non-Russian, structured outputs (sentence excerpts, keyword lists, topic words, RAG ranking rows, lemmatization tables) are wrapped in `<span lang="target_lang">`.
- **Linear HTML structure** (`<main>`, proper heading hierarchy).

## Repository layout

```
accessible_text_analyst/
├── accessible_text_analyst.ipynb   # main pipeline (36 cells)
├── generate_report.py              # HTML report generator
├── config.example.json             # config template (versioned)
├── config.json                     # your local configuration (gitignored)
├── requirements.txt                # pip dependencies
├── CLAUDE.md                       # guide for Claude Code
├── README.md                       # this file
└── export_results/                 # analysis outputs (gitignored)
    └── <project_name>/
        ├── sentences.csv
        ├── paragraphs.csv
        ├── theses.csv
        ├── тезисы.txt
        ├── accessible_text.html
        ├── accessible_text.docx
        └── ...
```

## License

No license has been set yet.
