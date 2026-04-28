# Accessible Text Analyst

A multilingual NLP pipeline designed for **accessibility with screen readers** (NVDA, JAWS, VoiceOver). All code, console output, and reports are crafted to be parsed cleanly by assistive technology: no ANSI colors, no emoji, no progress bars, no box-drawing characters.

The project consists of two files:

- `accessible_text_analyst.ipynb` — a Jupyter notebook with the complete analysis pipeline (38 cells; the in-notebook narrative is in Russian).
- `generate_report.py` — a post-processing script that turns the executed notebook into a single accessible HTML file (`raport_analizy.html`), wrapping foreign-language fragments in `<span lang="...">` so screen readers switch pronunciation correctly.

## What the pipeline does

1. Loads text from a file (`.pdf`, `.txt`, `.docx`, `.html`) or from a URL — stripping repeated headers/footers, sidebars, "Related articles" sections, and similar boilerplate.
2. Detects the corpus language (`langdetect`).
3. Loads the appropriate spaCy model for that language.
4. Tokenization → stop-word filtering → lemmatization → POS tagging → NER.
5. Vector representations: Bag of Words, TF-IDF + auto-query search with cosine ranking.
6. Sentiment analysis (multilingual XLM-RoBERTa from Hugging Face).
7. Structure: sentences → paragraphs (3–6 sentences each) → theses (the best sentence per paragraph).
8. Topic modeling with KMeans over spaCy paragraph vectors.
9. CSV/JSON export + a textual summary report + an HTML report.

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

## Requirements

- Python 3.10 or newer.
- ~3 GB of free disk space for models (spaCy `_lg` + the multilingual Hugging Face sentiment model). Add ~700 MB if you use Icelandic support.
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
# Icelandic: nothing to install manually — HF models are pulled on first run.
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
| `чистый_текст_для_аудио.txt`    | cleaned text ready for a TTS engine / audiobook pipeline |

The HTML file (`raport_analizy.html`) lives in the project root and is global — it always reflects the most recently executed notebook.

## Accessibility

This is the project's central value. Everything below is intentional and must be preserved when the pipeline is modified:

- **No ANSI colors, emoji, or pseudographics in stdout.** A screen reader reads every character literally — `[OK]` instead of "🟢", `---` instead of "───━━━".
- **Silenced progress bars** (`tqdm`, `transformers`, `torch`) — the `cell_sentiment` cell carries the full set of mute flags; `cell_model` applies the same approach when loading Hugging Face models for Icelandic.
- **Per-fragment language tagging in HTML.** `generate_report.py` detects the corpus language and wraps matching fragments in `<span lang="xx">` so the screen reader switches to the correct voice.
- **Linear HTML structure** (`<main>`, proper heading hierarchy).
- **A clean text file for audio.** `чистый_текст_для_аудио.txt` in the project directory can be fed straight into a TTS engine (Whisper / Piper / Read Aloud).

## Repository layout

```
accessible_text_analyst/
├── accessible_text_analyst.ipynb   # main pipeline (38 cells)
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
        └── ...
```

## License

No license has been set yet.
