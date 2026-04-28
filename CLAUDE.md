# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository overview

Two-file project that performs accessibility-oriented multilingual text analytics:

- `accessible_text_analyst.ipynb` — the entire NLP pipeline (38 cells). The notebook narrative and `print()` outputs are in **Russian** and were intentionally written without color, emoji, or pseudographic art so they read cleanly through NVDA/JAWS screen readers.
- `generate_report.py` — standalone post-processor that turns the executed notebook into a single accessible HTML file (`raport_analizy.html`), wrapping foreign-language fragments in `<span lang="...">` so screen readers switch pronunciation correctly.

There is no test suite and no build step.

## Common commands

```bash
# Install dependencies (Python 3.10+ assumed; .venv is in .gitignore)
pip install -r requirements.txt

# spaCy models are NOT in requirements.txt — install the *_lg models for each language you need.
# The notebook's MODEL_BY_LANG hardcodes _lg variants because KMeans topics + NER quality depend on word vectors.
python -m spacy download pl_core_news_lg
python -m spacy download ru_core_news_lg
python -m spacy download en_core_web_lg
python -m spacy download it_core_news_lg
python -m spacy download fi_core_news_lg
# Icelandic (is) intentionally falls back to spacy.blank("is") — no model exists.

# Run the notebook end-to-end
jupyter notebook accessible_text_analyst.ipynb

# After executing the notebook (so its cells contain outputs), generate the HTML report:
python generate_report.py
```

`requirements.txt` lists `nbstripout` — if it has been activated in the local git config, notebook outputs are stripped on commit. `generate_report.py` reads outputs from the `.ipynb` file directly, so the report must be regenerated from a freshly-executed notebook (don't commit-then-report).

## Pipeline architecture (notebook)

The notebook's 38 cells are a linear, stateful pipeline — every cell reuses globals from the previous ones (`corpus`, `LANG`, `nlp`, `stop_words`, `docs`, `para_lemmas`, `df_para`, `df_sent`, etc.). **Do not reorder cells or run them out of order.** The flow:

1. **`cell_corpus`** — only user-facing input: set `SOURCE_FILE` to a `.pdf` / `.txt` / `.docx` / `.html` path or an `http(s)://` URL. Empty string → built-in `FALLBACK_CORPUS`. Loaders strip repeated PDF headers/footers (`strip_repeated_headers`), de-hyphenate, and for HTML/URL run a BeautifulSoup main-content heuristic (`<main>`/`<article>` → id/class containing `content|article|post|story`). `CUSTOM_PATTERNS` is a list of regexes pre-stripped from txt/docx/html.
2. **`cell_langdet`** — `langdetect` votes per document; the dominant language wins. Supported set: `{en, pl, ru, it, fi, is}` (`SUPPORTED_LANGS`).
3. **`cell_model`** — picks model from `MODEL_BY_LANG`; `is` uses `spacy.blank("is")` with sentencizer only.
4. **`cell_pl_corrector`** — regex-only normalization (no morphology). Runs across all languages: collapses doubled words/whitespace; for `pl`/`ru`/`en` normalizes spaced abbreviations (`m. in.` → `m.in.`, `т. е.` → `т.е.`, `e. g.` → `e.g.`).
5. **`cell_tok` → `cell_stop` → `cell_lemma` → `cell_pos` → `cell_ner`** — standard spaCy steps; `stop_words` comes from the loaded model.
6. **`cell_bow`, `cell_tfidf`** — sklearn `CountVectorizer`/`TfidfVectorizer`; auto-query for TF-IDF search is built from top corpus terms so cosine similarity is guaranteed > 0.
7. **`cell_para`** — joins the whole corpus, re-splits via spaCy `sents`, then groups sentences into 3–6-sentence "paragraphs". `para_lemmas`, `df_para`, `df_sent` feed the rest.
8. **`cell_keywords`** (TF-IDF n-grams 1–3 over paragraphs) → **`cell_theses`** (best sentence per paragraph by TF-IDF sum, written to `тезисы.txt`) → **`cell_topics`** (KMeans over spaCy paragraph vectors; **silently skipped if model has no vectors**, hence the `_lg` requirement).
9. **`cell_sentiment`** — Hugging Face `cardiffnlp/twitter-xlm-roberta-base-sentiment` (multilingual, ~1.1 GB on first run); progress bars are explicitly silenced via `transformers.logging` + env vars to keep stdout clean for screen readers.
10. **`cell_export`** — writes CSV (UTF-8 BOM for Excel) and JSON to `export_results/`.
11. **`cell_summary`** — single text block aggregating all metrics; this is the screen-reader-friendly "final report".
12. **`cell_qa_rag`** — interactive TF-IDF retrieval. Excluded from the HTML report by ID (see below).

## HTML report generator

`generate_report.py` reads the saved `.ipynb`, walks `cells`, and emits `raport_analizy.html`. Key behaviors:

- **Target-language detection** — scans cell stdout for `Выбран язык: ... (xx)` and uses `xx` as `target_lang`. The whole `<html>` is `lang="ru"` (the narrative is Russian); foreign content gets per-fragment `<span lang="target_lang">`. When `target_lang == "ru"`, tagging is skipped (everything is already Russian).
- **`tag_target_language`** — a list of regex patterns matches structured output formats (numbered `[1] ...` excerpts, ranked tables, POS tables, lemmatization tables, RAG result rows, etc.) and wraps just the foreign-text portion. When extending the pipeline, output formats must match one of these patterns or content will not be tagged. HTML-escaping happens before regex matching, so quotes appear as `&#x27;`/`&quot;` in the patterns.
- **`REMOVE_NOISE`** (top of file, default `False`) — when `True`, drops Hugging Face/torch loading bars and skips the verbose lemmatization + POS tables entirely. Toggle when producing a reader-facing report vs. a full diagnostic one.
- **Cell exclusion** — `cell_id in ["md_qa_rag", "cell_qa_rag"]` is skipped because the interactive RAG cell has no meaningful static output.

## Conventions

- All in-notebook narration and prints are Russian; Python comments mix Polish and Russian. Preserve the existing language of any cell you edit.
- Never introduce ANSI colors, emoji, progress bars, or box-drawing characters into stdout — the entire project's value is screen-reader cleanliness. Hugging Face/tqdm/transformers progress output is already actively muted in `cell_sentiment`; replicate that pattern for any new model loads.
- The `_lg` spaCy models are a hard requirement for `cell_topics` to do anything; the cell self-skips on missing vectors, so partial pipelines are valid but lose topic modeling.
- `export_results/` and `*.html` are gitignored — generated artifacts only.
