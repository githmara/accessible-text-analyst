# Accessible Text Analyst

A multilingual NLP pipeline designed for **accessibility with screen readers** (NVDA, JAWS, VoiceOver, Narrator). All code, console output, and reports are crafted to be parsed cleanly by assistive technology: no ANSI colors, no emoji, no progress bars, no box-drawing characters.

> **Other languages:** [polski](README_pl.md) · [русский](README_ru.md) · [suomi](README_fi.md) · [íslenska](README_is.md) · [italiano](README_it.md)

> **i18n status (v1.0).** Only the README has been translated. The Jupyter notebook narrative, all console output, `CLAUDE.md`, and the inline code comments remain in their original languages (mostly Russian, with Polish in the patches and the shamanic layer). Translating those is deliberately scoped for v1.1 — see `release_notes.md`.

## Project contents

- `accessible_text_analyst.ipynb` — a Jupyter notebook with the complete analysis pipeline (40 cells: 20 code + 20 markdown; the in-notebook narrative is in Russian). It writes two accessibility artefacts (`accessible_text.html`, `accessible_text.docx`) where every paragraph and every foreign-language sentence carries its own `lang` attribute so screen readers and TTS engines switch voice automatically — even offline.
- `generate_report.py` — a post-processing script that turns the executed notebook into a single accessible HTML file (`analysis_report.html`). It wraps foreign-corpus fragments in `<span lang="target_lang">` and, regardless of corpus language, hardcodes `<span lang="en">` around technical English content (POS tags, NER labels, spaCy/Hugging Face model identifiers, ASCII filenames). Inline code and code blocks in the narrative are blanket-tagged `lang="en"`.
- `generate_md.py` — converts the generated `analysis_report.html` into `notebooklm_report.md` for NotebookLM ingestion. The accessibility spans are unwrapped since NotebookLM does not consume them.
- `shamanic_pipeline.py` *(optional)* — a non-LLM post-processor that turns the notebook's CSV/JSON exports into four ritual text artefacts (`oracle_script.txt`, `lore_fragments/`, `raw_roots_chant.txt`, `prophecies.txt`), all fully localized across the six supported languages.
- `shamanic_ai.py` *(optional, LLM-driven)* — calls OpenAI to generate four narrative voices (`Katla`, `Vieno`, `Lumi`, `Sami`) on top of the same exports. Requires `OPENAI_API_KEY` in `golden_key.env`.
- `shamanic_locale.py` — the localization bundle for both shamanic scripts (templates, headers, and Lumi's fallback strings in all six supported languages).

## What the pipeline does

1. Loads text from a file (`.pdf`, `.txt`, `.docx`, `.html`, or images: `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`, `.webp`) or from a URL — stripping repeated headers/footers, sidebars, "Related articles" sections, and similar boilerplate. Scanned PDFs and image inputs fall back to OCR (`pypdfium2` + `easyocr`).
2. Detects the corpus language with [`lingua-language-detector`](https://github.com/pemistahl/lingua-py). The dominant language drives the spaCy pipeline; the same detector is reused per paragraph and per sentence to power language-tagged export.
3. Loads spaCy models in **two stages**. First, the dominant language's model processes the entire corpus end-to-end (tokenization → stop-words → lemmatization → POS → NER). Then `cell_multilang_pass` re-runs the per-language NLP passes only for paragraphs whose detected language differs from the dominant one — loading each non-dominant model on demand through `get_nlp()`, which is wrapped in `functools.lru_cache(maxsize=2)`. The LRU cache only matters during this second stage; at most two models live in RAM at any time.
4. Tokenization → stop-word filtering → lemmatization → POS tagging → NER (two-stage multilingual with per-sentence model dispatch).
5. Vector representations: Bag of Words, TF-IDF + auto-query search with cosine ranking.
6. Structure: sentences → paragraphs (3–6 sentences each) → theses (the best sentence per paragraph). Each paragraph and sentence is tagged with its detected ISO 639-1 code.
7. Topic modeling with KMeans over spaCy paragraph vectors.
8. CSV/JSON export + a textual summary report + an accessibility-tagged HTML and DOCX export + a global HTML report (`analysis_report.html`).

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
- Add ~700 MB if you opt into OCR support (`easyocr` pulls `torch` plus its detection and recognition models on the first OCR call). If you also enabled Icelandic, the `torch` cost is shared between the two.
- An internet connection on the first run (model downloads).

## Environment setup

Pick one of the three options below. All three end with the same `pip install -r requirements.txt` + spaCy model downloads.

### Option A — local `venv` (recommended for everyday use)

```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
```

The `.venv/` directory is in `.gitignore`. From inside the activated venv, proceed to **Installation** below.

### Option B — Anaconda / Miniconda

```bash
conda create -n accessible-text-analyst python=3.11
conda activate accessible-text-analyst
```

Then proceed to **Installation** below. Anaconda's bundled `pip` works fine — there is no Conda-specific package list for this project.

### Option C — Google Colab (no local install)

Open a new Colab notebook and paste the following into the first cell. This clones the repo, installs the dependencies, and downloads the spaCy models you need.

```python
!git clone https://github.com/<your-fork>/accessible_text_analyst.git
%cd accessible_text_analyst
!pip install -r requirements.txt
!python -m spacy download en_core_web_lg
# Add the lines below only for the languages you actually need:
# !python -m spacy download pl_core_news_lg
# !python -m spacy download ru_core_news_lg
# !python -m spacy download it_core_news_lg
# !python -m spacy download fi_core_news_lg
```

Then upload your `config.json` (or `config.ini`) via the Files panel, set `source_file`, and run the notebook. Note: Colab sessions are ephemeral — downloaded models and `export_results/` artefacts disappear when the runtime is recycled. For long-form analysis, mount Google Drive and write the output there.

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

Copy the example configuration to a local file. Both `config.json` and `config.ini` are accepted — **the file content is JSON in either case**; the `.ini` extension is purely a usability concession to non-technical Windows users for whom `.json` has no default file handler.

```bash
# Pick one:
cp config.example.json config.json
cp config.example.ini  config.ini
```

`config.json` and `config.ini` are both in `.gitignore`, so each user keeps their own local copy.

Contents:

```json
{
  "source_file": "C:/path/to/document.pdf",
  "custom_patterns": [],
  "remove_noise": true,
  "ocr_languages": ["en"],
  "ui_lang": "",
  "lumi_katla_lines": null,
  "lumi_vieno_lines": null
}
```

| Key                | Type            | Purpose |
|--------------------|-----------------|---------|
| `source_file`      | string          | Path to a file (`.pdf`, `.txt`, `.docx`, `.html`, or an image) **or** a URL (`http://`, `https://`). An empty string or a missing file falls back to the built-in example corpus. |
| `custom_patterns`  | string[]        | Optional regular expressions stripped from the raw text (running heads, footers, repetitive boilerplate). Example: `["Editorial: .*", "Copyright \\d{4}"]`. |
| `remove_noise`     | boolean         | Toggles `generate_report.py` between reader-facing mode (`true`, hides Hugging Face/torch loading bars and lemmatization/POS tables) and full diagnostic mode (`false`). |
| `ocr_languages`    | string[]        | Languages for `easyocr` (used only when a PDF is a scan or the source is an image). Within a single `easyocr.Reader` you can only mix languages of the same script — e.g. `["ru", "en"]` for Cyrillic or `["en", "pl", "it", "fi", "is"]` for Latin. |
| `ui_lang`          | string          | UI language for console output and the generated report's `<html lang>` attribute (`pl` / `en` / `ru` / `fi` / `is` / `it`). Empty string or unknown code → falls back to `en`. Independent from the analysed corpus language, which is detected automatically. |
| `lumi_katla_lines` | integer or null | Optional ornament cap for `shamanic_ai.py`'s Lumi dispatch: how many non-empty lines of Katla's monologue Lumi sees. `null` or missing key = full content; integer N > 0 = first N lines. |
| `lumi_vieno_lines` | integer or null | Same as `lumi_katla_lines`, but for Vieno's echo chant. |

> **Windows paths and regex — important.** The config content is JSON, and JSON has no raw-string syntax. A single backslash escapes the next character (`\U`, `\d`, `\n` are special), so a Windows path written `"C:\Users\marek\doc.pdf"` will produce a JSON parse error. Two ways to write it correctly:
>
> - **Forward slashes** (simplest, works on Windows too): `"C:/Users/marek/doc.pdf"`.
> - **Double backslashes**: `"C:\\Users\\marek\\doc.pdf"`.
>
> The same rule applies to every regular expression in `custom_patterns`: write `"\\d{4}"`, not `"\d{4}"`; write `"Copyright \\d{4}"`, not `"Copyright \d{4}"`. There is no `r"…"` raw-string form in JSON.

## Running

The numbered scripts below are intended to be run **in order**: each one consumes artefacts produced by the previous step.

### 1. Notebook (mandatory)

```bash
jupyter notebook accessible_text_analyst.ipynb
# (Cell → Run All)
```

This is a sequential pipeline with shared global state. **Do not reorder cells, and do not run them out of order.** The notebook writes `export_results/<project>/sentences.csv`, `paragraphs.csv`, `theses.csv`, `keywords_tfidf.csv`, `paragraphs_with_topics.csv`, `topic_keywords.json`, `entities.csv`, `accessible_text.html`, `accessible_text.docx`, and `theses.txt`.

### 2. HTML report (recommended)

```bash
python generate_report.py
# → export_results/<project>/analysis_report.html
```

`generate_report.py` reads cell outputs directly from the `.ipynb` file, so the HTML report must be generated from a **freshly executed** notebook. `requirements.txt` lists `nbstripout` — if it has been activated in the local git config, notebook outputs are stripped on commit. Generate the report _before_ committing, or disable nbstripout for your workflow.

### 3. NotebookLM-friendly Markdown (optional)

```bash
python generate_md.py
# → export_results/<project>/notebooklm_report.md
```

This converts the HTML report into a Markdown file with the accessibility spans unwrapped (NotebookLM does not consume `<span lang="…">`). Run this only if you want to feed the report into NotebookLM.

### 4. Shamanic non-LLM post-processor (optional)

```bash
python shamanic_pipeline.py
# → export_results/<project>/audio_scripts/oracle_script.txt
#                                          /raw_roots_chant.txt
#                                          /prophecies.txt
#                                          /lore_fragments/intercepted_log_T*_P*.txt
```

Generates four ritual text artefacts directly from the notebook's CSV/JSON exports — no LLM call, no network. All strings come from `shamanic_locale.py` and are fully localized across the six supported languages.

### 5. Shamanic LLM post-processor (optional, requires OpenAI key)

```bash
python shamanic_ai.py
# → export_results/<project>/audio_scripts/katla_entity_monologue.txt
#                                          /vieno_echoes_chant.txt
#                                          /lumi_final_report.txt
#                                          /sami_energetic_spark.txt
```

This requires an OpenAI API key. Create `golden_key.env` in the project root:

```
OPENAI_API_KEY=sk-...
```

`golden_key.env` matches `*.env` in `.gitignore`, so it will not be committed. The four voices run in sequence:

1. **Katla** transmutes the entity list (`entities.csv`) into a monologue of frozen Northern spirits.
2. **Vieno** chants over the keyword/topic list with five raw sentences from the corpus as foreign-dimension echoes.
3. **Lumi** reads `prophecies.txt` (mandatory) plus Katla's monologue and Vieno's chant (optional ornament) and produces the final dispatch. Localized fallback strings cover the case where Katla or Vieno are missing.
4. **Sami** reads Lumi's report and delivers a high-energy synthesis with the spark of hope or call to action.

## Output

Every analyzed corpus gets its own subdirectory under `export_results/`, named after the source file (path and extension stripped) or after a `domain_slug` for URLs. The built-in example corpus uses `export_results/_default/`.

Each subdirectory contains:

| File                            | Produced by | Description                                              |
|---------------------------------|-------------|----------------------------------------------------------|
| `sentences.csv`                 | notebook    | every sentence with its index and paragraph assignment   |
| `paragraphs.csv`                | notebook    | paragraphs (3–6 sentences each)                          |
| `theses.csv`, `theses.txt`      | notebook    | one thesis per paragraph (highest-TF-IDF sentence); the `.txt` filename follows the corpus language (e.g. `tezy.txt` for Polish, `тезисы.txt` for Russian) |
| `keywords_tfidf.csv`            | notebook    | keywords (uni/bi/trigrams) with TF-IDF weights           |
| `paragraphs_with_topics.csv`    | notebook    | paragraphs with their assigned KMeans topic              |
| `topic_keywords.json`           | notebook    | keywords per topic                                       |
| `entities.csv`                  | notebook    | all named entities and their labels                      |
| `accessible_text.html`          | notebook    | paragraph- and sentence-level `lang` attributes — screen readers switch voice automatically per fragment |
| `accessible_text.docx`          | notebook    | the same content with `<w:lang>` set per `Run` (`pl-PL`, `ru-RU`, `en-US`, `it-IT`, `fi-FI`, `is-IS`) — Word and SAPI use it offline, no online detector required |
| `analysis_report.html`           | `generate_report.py` | global accessible HTML report                  |
| `notebooklm_report.md`      | `generate_md.py`     | NotebookLM-ready Markdown                      |
| `audio_scripts/*.txt`           | `shamanic_pipeline.py`, `shamanic_ai.py` | ritual / narrative text artefacts |

## Accessibility

This is the project's central value. Everything below is intentional and must be preserved when the pipeline is modified:

- **No ANSI colors, emoji, or pseudographics in stdout.** A screen reader reads every character literally — `[OK]` instead of "🟢", `---` instead of "───━━━".
- **Silenced progress bars** (`tqdm`, `transformers`, `torch`) — `cell_model._silence_hf_progress()` mutes Hugging Face/torch loading bars and warnings before pulling IceBERT and MIM-GOLD-22 for Icelandic; `cell_corpus._silence_ocr_progress()` does the same for `easyocr`.
- **Per-paragraph and per-sentence `lang` tagging in the export.** `accessible_text.html` and `accessible_text.docx` carry an ISO 639-1 code on every paragraph (and on every sentence inside mixed-language paragraphs / runs). NVDA, JAWS, Narrator, VoiceOver, Word, and SAPI all honour those tags and switch voice automatically — even offline.
- **Hardcoded English tagging in the HTML report.** `generate_report.py` always wraps technical English fragments — POS tags (`NOUN`, `VERB`, `ADJ`), NER labels (`PER`, `ORG`, `[orgName]`), spaCy / Hugging Face model identifiers, ASCII filenames, code blocks — in `<span lang="en">`, so they are no longer pronounced through the document-default Russian voice.
- **Per-fragment foreign-corpus tagging in HTML.** When the corpus is non-Russian, structured outputs (sentence excerpts, keyword lists, topic words, RAG ranking rows, lemmatization tables) are wrapped in `<span lang="target_lang">`.
- **Linear HTML structure** (`<main>`, proper heading hierarchy).

## Repository layout

```
accessible_text_analyst/
├── accessible_text_analyst.ipynb   # main pipeline (40 cells)
├── generate_report.py              # HTML report generator
├── generate_md.py                  # NotebookLM Markdown converter
├── shamanic_pipeline.py            # optional: non-LLM ritual post-processor
├── shamanic_ai.py                  # optional: LLM-driven ritual narrators
├── shamanic_locale.py              # localization bundle for the shamanic layer
├── config.example.json             # config template, JSON extension (versioned)
├── config.example.ini              # config template, INI extension (versioned)
├── config.json / config.ini        # your local configuration (gitignored)
├── golden_key.env                  # OpenAI API key for shamanic_ai.py (gitignored)
├── requirements.txt                # pip dependencies
├── CLAUDE.md                       # guide for Claude Code
├── README.md                       # this file (canonical, English)
├── README_pl.md, README_ru.md, …   # translations (link back at the top)
├── release_notes.md                # release notes appended in reverse-chrono order
└── export_results/                 # analysis outputs (gitignored)
    └── <project_name>/
        ├── sentences.csv
        ├── paragraphs.csv
        ├── theses.csv
        ├── theses.txt              # name follows corpus language
        ├── accessible_text.html
        ├── accessible_text.docx
        ├── analysis_report.html
        ├── notebooklm_report.md
        └── audio_scripts/…
```

## License

Released under the [MIT License](LICENSE). The pipeline is distributed as source only — no binaries — and the notebook is, by its nature, editable cell-by-cell through the browser or the VS Code Jupyter extension. The MIT license simply makes explicit what the format already implies.
