# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository overview

Two-file project that performs accessibility-oriented multilingual text analytics:

- `accessible_text_analyst.ipynb` — the entire NLP pipeline (36 cells). The notebook narrative and `print()` outputs are in **Russian** and were intentionally written without color, emoji, or pseudographic art so they read cleanly through NVDA/JAWS screen readers. The notebook itself emits two accessibility artefacts (`accessible_text.html`, `accessible_text.docx`) where every paragraph and every foreign-language sentence carries its own `lang` attribute so screen readers and TTS engines switch voice automatically.
- `generate_report.py` — standalone post-processor that turns the executed notebook into a single accessible HTML file (`raport_analizy.html`). It wraps foreign-language fragments in `<span lang="target_lang">` and **always** wraps technical English fragments (POS tags, NER labels, spaCy/HF model names, ASCII filenames) in `<span lang="en">` regardless of corpus language.

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

The notebook's 36 cells are a linear, stateful pipeline — every cell reuses globals from the previous ones (`corpus`, `LANG`, `LANG_DETECTOR`, `nlp`, `stop_words`, `docs`, `para_lemmas`, `df_para`, `df_sent`, `para_sentences`, `para_langs`, `sent_langs`, etc.). **Do not reorder cells or run them out of order.** The flow:

1. **`cell_corpus`** — only user-facing input: set `SOURCE_FILE` to a `.pdf` / `.txt` / `.docx` / `.html` path or an `http(s)://` URL. Empty string → built-in `FALLBACK_CORPUS`. Loaders strip repeated PDF headers/footers (`strip_repeated_headers`), de-hyphenate, and for HTML/URL run a BeautifulSoup main-content heuristic (`<main>`/`<article>` → id/class containing `content|article|post|story`). `CUSTOM_PATTERNS` is a list of regexes pre-stripped from txt/docx/html.
2. **`cell_langdet`** — uses `lingua-language-detector` (replaced `langdetect` for higher per-fragment accuracy). Determines the dominant corpus language as `LANG`, plus exposes globals `LANG_DETECTOR` and `detect_lang(text)` consumed later by `cell_para` and `cell_export`. Supported set: `{en, pl, ru, it, fi, is}` (`SUPPORTED_LANGS`). Output keeps the format `Выбран язык: <name> (<code>)` so `generate_report.py` can detect the target language.
3. **`cell_model`** — model loading is gated by `get_nlp(lang)` decorated with `functools.lru_cache(maxsize=2)` — at most two spaCy models live in RAM at once, the LRU is evicted on demand. `nlp = get_nlp(LANG)` is loaded eagerly for the dominant language; `MODEL_BY_LANG` provides the `_lg` model names. Icelandic still uses `spacy.blank("is")` + Hugging Face IceBERT vectors + `mideind/icelandic-ner-MIM-GOLD-22` (these require `transformers` + `torch`, which are commented out in `requirements.txt` by default — uncomment for `is` support). The legacy alias `load_nlp_model` is kept.
4. **`cell_pl_corrector`** — regex-only normalization (no morphology). Runs across all languages: collapses doubled words/whitespace; for `pl`/`ru`/`en` normalizes spaced abbreviations (`m. in.` → `m.in.`, `т. е.` → `т.е.`, `e. g.` → `e.g.`).
5. **`cell_tok` → `cell_stop` → `cell_lemma` → `cell_pos` → `cell_ner`** — standard spaCy steps; `stop_words` comes from the loaded model.
6. **`cell_bow`, `cell_tfidf`** — sklearn `CountVectorizer`/`TfidfVectorizer`; auto-query for TF-IDF search is built from top corpus terms so cosine similarity is guaranteed > 0.
7. **`cell_para`** — joins the whole corpus, re-splits via spaCy `sents`, then groups sentences into 3–6-sentence "paragraphs". `para_lemmas`, `df_para`, `df_sent` feed the rest. Builds three additional globals consumed by `cell_export`: `para_sentences` (list of sentence-lists per paragraph), `para_langs` (ISO code per paragraph via lingua), `sent_langs` (ISO code per sentence). A local `_safe_detect()` falls back to `LANG` for fragments too short for reliable detection.
8. **`cell_keywords`** (TF-IDF n-grams 1–3 over paragraphs) → **`cell_theses`** (best sentence per paragraph by TF-IDF sum, written to `тезисы.txt`) → **`cell_topics`** (KMeans over spaCy paragraph vectors; **silently skipped if model has no vectors**, hence the `_lg` requirement).
9. **`cell_export`** — writes CSV (UTF-8 BOM for Excel) and JSON to `export_results/<project_dir>/`. Also produces two accessibility artefacts:
    - `accessible_text.html` — built with BeautifulSoup; `<html lang="LANG">`, `<p lang="para_langs[i]">` per paragraph, `<span lang="sent_langs[j]">` per sentence inside paragraphs whose sentences disagree.
    - `accessible_text.docx` — built with python-docx; each `Run` has `<w:lang val=... eastAsia=... bidi=...>` set via OOXML using `LANG_TO_LOCALE` (`pl-PL`, `ru-RU`, `en-US`, `it-IT`, `fi-FI`, `is-IS`).
    These replace the previous `чистый_текст_для_аудио.txt` flat file. Both are written wrapped in try/except so missing optional deps (bs4, python-docx) only print a warning instead of failing the whole cell.
10. **`cell_summary`** — single text block aggregating all metrics; this is the screen-reader-friendly "final report". Reports `para_langs` and `sent_langs` distribution and the byte sizes of `accessible_text.html` / `accessible_text.docx`.
11. **`cell_qa_rag`** — interactive TF-IDF retrieval. Excluded from the HTML report by ID (see below).

**Sentiment analysis was removed.** The previous `cell_sentiment` (Hugging Face `cardiffnlp/twitter-xlm-roberta-base-sentiment`) was deleted because the model is trained on tweets and gave unreliable, near-coin-flip confidences (~30–50%) on long-form Finnish/Polish content; the fallback `distilbert-base-uncased-finetuned-sst-2-english` is binary, English-only, and produced spurious "100% negative" verdicts for foreign corpora. For an accessibility-first tool, presenting confidently-wrong sentiment to a screen-reader user is worse than presenting nothing. Do not re-add it without solving the domain mismatch first.

## HTML report generator

`generate_report.py` reads the saved `.ipynb`, walks `cells`, and emits `raport_analizy.html`. Key behaviors:

- **Target-language detection** — scans cell stdout for `Выбран язык: ... (xx)` and uses `xx` as `target_lang`. The whole `<html>` is `lang="ru"` (the narrative is Russian); foreign-corpus content gets per-fragment `<span lang="target_lang">`. When `target_lang == "ru"`, the per-fragment target-lang pass is skipped (corpus is already Russian) but the EN-hardcoding pass below still runs.
- **`tag_target_language` (target-lang patterns)** — a list of regex patterns matches structured output formats (numbered `[1] ...` excerpts, ranked tables, POS tables, lemmatization tables, RAG result rows, etc.) and wraps just the foreign-corpus portion. When extending the pipeline, output formats must match one of these patterns or content will not be tagged. HTML-escaping happens before regex matching, so quotes appear as `&#x27;`/`&quot;` in the patterns.
- **EN hardcoding (`EN_HARDCODE_PATTERNS`)** — runs on every report, regardless of `target_lang`. Wraps in `<span lang="en">` the things that are always English regardless of corpus language: spaCy POS tags (`NOUN`, `VERB`, `ADJ`, …), NER labels (`PER`, `ORG`, `[orgName]`, …), spaCy model identifiers (`pl_core_news_lg`, …), Hugging Face model names (`cardiffnlp/...`, `mideind/...`), spaCy pipeline component names (`tok2vec`, `tagger`, `lemmatizer`, …), ASCII filenames with technical extensions (`.csv`, `.json`, `.html`, `.docx`, `.txt`, `.py`, `.md`), the literal `export_results`, and ISO 639-1 codes inside dict-like outputs. Without this pass NVDA reads `VERB`, `cardiffnlp` etc. with the document-default Russian voice. The pass is order-aware: target-lang wrapping runs first, EN hardcoding runs second using `_apply_outside_spans()` so it never wraps content already inside a span. Markdown narrative gets the same treatment for inline `<code>` and `<pre><code>` blocks (`lang="en"` is added blanket-style to every code element, since narrative code is always English).
- **`REMOVE_NOISE`** (top of file, default `False`) — when `True`, drops Hugging Face/torch loading bars and skips the verbose lemmatization + POS tables entirely. Toggle when producing a reader-facing report vs. a full diagnostic one.
- **Cell exclusion** — `cell_id in ["md_qa_rag", "cell_qa_rag"]` is skipped because the interactive RAG cell has no meaningful static output.

When you add a new pipeline step that prints technical English (a new POS tag set, a new HF model id, a new file extension), extend `EN_HARDCODE_PATTERNS`. When you add a new structured output format that wraps corpus content, extend the `patterns` list inside `tag_target_language`.

## Conventions

- All in-notebook narration and prints are Russian; Python comments mix Polish and Russian. Preserve the existing language of any cell you edit.
- Never introduce ANSI colors, emoji, progress bars, or box-drawing characters into stdout — the entire project's value is screen-reader cleanliness. The Hugging Face/tqdm/transformers mute pattern lives in `cell_model._silence_hf_progress()` (used when loading IceBERT/MIM-GOLD-22 for Icelandic); replicate it for any new model loads.
- The `_lg` spaCy models are a hard requirement for `cell_topics` to do anything; the cell self-skips on missing vectors, so partial pipelines are valid but lose topic modeling.
- Notebook patches are applied via one-shot Python scripts under `.claude_patches/` (gitignored). Edit cell sources by writing a new `.py`/`.md` patch file and re-running `apply_patches.py` rather than hand-editing the notebook JSON.
- `export_results/`, `*.html`, and `.claude_patches/` are gitignored — generated artefacts and local tooling only.
