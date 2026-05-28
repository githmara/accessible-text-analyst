# Release notes

All release entries are appended in reverse-chronological order. On GitHub, the latest entry is copied verbatim into the release body when a tag is pushed.

---

## v1.1.2 — accessibility fix: explicit `lang` on report containers

**Severity.** Screen-reader regression for every non-Russian `ui_lang` user. Upgrade strongly recommended if you read the report with NVDA / JAWS / Narrator / VoiceOver / SAPI.

**The bug.** `generate_report.py` wrapped both markdown narrative cells and code-cell stdout outputs in plain `<div>` containers without any `lang` attribute:

```html
<div class="markdown-cell">...</div>
<div class="output-box" aria-label="Вывод системы">...</div>
```

The containers therefore inherited `lang` from `<html lang="UI_LANG">`. For a Polish reader, every diagnostic print from `cell_corpus`, `cell_langdet`, `cell_model`, `cell_pl_corrector`, `cell_tok` … `cell_export` — all of them hardcoded Russian per the documented v1.1 localization scope — was announced in a Polish voice. The same regression would fire on a markdown narrative cell whenever `dictionaries/{ui_lang}/narrative.yaml` was missing a key and the renderer fell back to the notebook's Russian source.

**The fix.** Each container now carries an explicit `lang` attribute:

- Markdown narrative: `lang="UI_LANG"` when the YAML translation exists, `lang="ru"` when the renderer falls back to the notebook source.
- Code-cell stdout: `lang="ru"` by default, `lang="UI_LANG"` only for `cell_summary`, whose stdout is fully localized via `_t(UI_LANG, ...)`.

The document-level `<html lang="UI_LANG">`, headings, and `<title>` are unchanged — they come from `t()` calls and inherit correctly.

**Out of scope (deferred).** `aria-label="Вывод системы"` is still hardcoded Russian; `tag_target_language` does not yet wrap Polish abbreviations like `'m.in.'` in `cell_pl_corrector` diagnostics. Both are separate localization gaps, not the bug fixed here.

**Upgrade.** Re-run `generate_report.py` against an already-executed notebook. No notebook re-execution, config change, or dependency change required.

### Distribution

Source-only patch release. The GitHub-generated source-code asset attached to the tag is the canonical artefact.

---

## v1.1.1 — critical fix: `t()` shadowed by loop variable in `cell_topics`

**Severity.** v1.1 is unusable in its default configuration. Upgrade is strongly recommended.

**The bug.** `cell_topics` contains a `for t in sorted(df_topics["topic"].unique()):` loop that leaks the loop variable into module scope, shadowing the `t` function imported from `shamanic_locale`. After `cell_topics` runs, `t` is bound to a `numpy.int32` (the last KMeans topic label) and every subsequent `t(UI_LANG, ...)` call raises `TypeError: 'numpy.int32' object is not callable`. The failure cascades into `cell_export`, `cell_summary`, and `cell_qa_rag` — i.e. the three cells that produce the user-facing artefacts.

A second instance of the same pattern (`for t in d:`) lives in `cell_multilang_pass` and would shadow `t` with a spaCy `Token` even before `cell_topics` runs.

**Trigger.** Any corpus where the `_lg` spaCy model has word vectors and KMeans succeeds — which is the recommended setup and the documented happy path. In practice every default user hits this on first run.

**The fix.** The import is now aliased: `from shamanic_locale import t as _t`, and all 63 call sites inside the notebook were rewritten to use `_t(...)`. The existing `for t in ...:` loops are left in place — they no longer shadow anything that matters. Aliasing was chosen over renaming the two loop variables because it removes the entire class of bug (any future `for t in ...:` will be harmless) at the cost of a wider but purely mechanical rename. The standalone modules (`generate_report.py`, `generate_md.py`, `shamanic_pipeline.py`, `shamanic_ai.py`) were not changed; they have no loop variables that could shadow `t`.

**Upgrade.** Pull the new tag and re-execute the notebook from the top. No config, dependency, or data changes are required. The HTML report and DOCX export are regenerated from the freshly-executed notebook as usual.

### Distribution

Source-only patch release. The GitHub-generated source-code asset attached to the tag is the canonical artefact.

---

## v1.1 — internationalized interface

**Theme.** A user who sets `ui_lang: "pl"` (or `en` / `ru` / `fi` / `is` / `it`) in `config.json` gets a fully localized experience in the user-facing artefacts: the HTML report, the NotebookLM Markdown, the shamanic ritual stdout, and the notebook's final `cell_summary`. The corpus-content language is still detected automatically per-fragment via `<span lang="...">` — independent from `ui_lang`.

### Highlights

- **UI language config key (`ui_lang`)** — selects from `pl` / `en` / `ru` / `fi` / `is` / `it`; empty or unknown → falls back to `en`. Independent from the corpus language.
- **YAML-based localization layer** — strings live in `dictionaries/{lang}/*.yaml`. Domains: `shamanic.yaml` (ritual headers + shamanic-script stdout), `reports.yaml` (`generate_report` / `generate_md` stdout + report title), `notebook.yaml` (notebook section headers + `cell_summary`), `narrative.yaml` (full markdown narrative for the HTML report), `artifacts.yaml` (corpus-language-localized artefact filenames). PyYAML is now an active dependency. `shamanic_locale.t(lang, key, **kwargs)` flattens nested YAML keys to dotted form (`prophecy.fallback.loc`) and falls back per-key to `en`.
- **Localized analysis report HTML** — `<html lang="...">`, `<title>`, and the entire markdown narrative all follow `ui_lang`. Foreign-corpus fragments still get per-fragment `<span lang="target_lang">`.
- **Localized output artefact names** — `raport_analizy.html` → `analysis_report.html`; `raport_dla_notebooklm.md` → `notebooklm_report.md`. The theses text artefact's *filename* follows the corpus language (`tezy.txt` / `theses.txt` / `тезисы.txt` / `teesit.txt` / `tilgátur.txt` / `tesi.txt`).
- **Config-driven Lumi ornament limits** — `lumi_katla_lines` and `lumi_vieno_lines` replace the hardcoded `LUMI_KATLA_LINES = 8` / `LUMI_VIENO_LINES = 8` constants. `null` or missing key = full content; integer N > 0 = first N non-empty lines.

### Architectural decisions — what is *not* localized, and why

Not every Russian string in the project is routed through the new YAML layer. The localization scope was chosen pragmatically: localize what the **end user** sees, leave alone what the **developer** sees while iterating on the pipeline. We did this deliberately to keep v1.1 shippable and reviewable.

- **Notebook diagnostic stdout stays Russian.** Per-step prints inside `cell_corpus`, `cell_model`, `cell_ner`, `cell_multilang_pass`, `cell_export`, and friends — corpus loading details, OCR progress, token/POS/NER previews, multilingual-pass diagnostics — remain hardcoded Russian. Only the 16 section headers (`--- Title ---`), the entire final `cell_summary` report, and `cell_qa_rag`'s "Q&A ready" greeting follow `ui_lang`. The notebook is a developer-facing tool; the end-user reads `analysis_report.html`, which *is* fully localized.
- **Notebook markdown narrative stays Russian *in the notebook itself*** — but the HTML report swaps in a translation from `dictionaries/{ui_lang}/narrative.yaml` at render time. The notebook remains the authorial Russian source (so it can keep evolving without YAML lockstep), and the translations live in YAML, where editing and reviewing them is far easier than editing JSON-encoded notebook cells.
- **No `dictionaries/ru/narrative.yaml` on purpose.** For `ui_lang == "ru"` the notebook's own markdown cells are the source of truth, so a YAML cannot go stale when the notebook narrative evolves. Other languages need explicit YAML sync after any notebook-narrative change.
- **Preflight `ImportError` prints stay hardcoded English** in `generate_report.py` and `generate_md.py`. If `pyyaml` (or `lingua` / `markdownify` / `beautifulsoup4`) is missing, the localization layer itself cannot load — so a universal English error message is more useful than crashing inside `t()`.
- **`CLAUDE.md` and source-code comments stay English/Russian.** These are developer documentation, not user-facing surface, and translating them adds maintenance cost without user-visible benefit.

### Known limitations

- Translations in **`fi` / `is` / `it`** are drafted but unreviewed by native speakers. Native-speaker feedback after release will refine them — please open a GitHub issue for any rough edges.
- Switching `ui_lang` does *not* re-translate the markdown cells you see when you open the `.ipynb` in Jupyter; the translation kicks in only when you render the HTML report via `generate_report.py`.
- All v1.0 known limitations still apply (no sentiment analysis, `_lg` spaCy models required for topic modeling).

### Migration notes from v1.0

- **Output artefact renames.** `raport_analizy.html` → `analysis_report.html`; `raport_dla_notebooklm.md` → `notebooklm_report.md`. Existing v1.0 outputs on disk will not be picked up by `generate_md.py`; re-run `generate_report.py` to regenerate.
- **Theses filename is now corpus-language-localized.** `тезисы.txt` becomes `tezy.txt` for Polish corpora, `theses.txt` for English, etc. — driven by `dictionaries/{corpus_lang}/artifacts.yaml`.
- **Three new optional `config.json` keys**: `ui_lang`, `lumi_katla_lines`, `lumi_vieno_lines`. All default to no-op behavior (empty string for `ui_lang` → `en`; `null` for Lumi limits → unlimited). Updating `config.example.json` is recommended but not required.
- **`pyyaml` is now an active dependency** in `requirements.txt`. Existing virtual environments need `pip install -r requirements.txt` to pick it up; it is a pure-Python, ~700 KB package with no compilation step.

### Installation

See `README.md` for the full installation guide. The new `pyyaml` dependency installs cleanly on top of v1.0 environments.

### Distribution

Source-only release. The GitHub-generated source-code asset attached to the tag is the canonical artefact.

---

## v1.0 — first public release

**Project goal.** A multilingual NLP pipeline whose output is genuinely consumable by screen readers (NVDA, JAWS, Narrator, VoiceOver, SAPI). Every paragraph and every foreign-language sentence carries its own `lang` attribute, so assistive technology switches voice automatically — even offline. There are no ANSI colors, no emoji, no progress bars, and no pseudographic art in any stdout the pipeline produces.

### Highlights

- **Six supported languages** with full spaCy `_lg` pipelines: Polish, Russian, English, Italian, Finnish, and Icelandic (Icelandic falls back to `spacy.blank("is")` + Hugging Face `mideind/IceBERT-base` for vectors and `mideind/icelandic-ner-MIM-GOLD-22` for NER).
- **Per-fragment language detection** powered by `lingua-language-detector`. The corpus-dominant language drives the spaCy pipeline; every paragraph and every sentence is independently labelled with its ISO 639-1 code.
- **Accessibility-tagged exports** — `accessible_text.html` (with `<p lang="…">` and `<span lang="…">` per fragment) and `accessible_text.docx` (with `<w:lang>` set per `Run` via OOXML).
- **Global HTML report** — `generate_report.py` walks the executed notebook and emits `raport_analizy.html` with foreign-corpus fragments wrapped in `<span lang="target_lang">` and technical English content (POS tags, NER labels, spaCy/Hugging Face model identifiers, ASCII filenames, code blocks) hard-coded as `<span lang="en">` regardless of corpus language.
- **NotebookLM-friendly Markdown** — `generate_md.py` strips the accessibility spans and produces `raport_dla_notebooklm.md` for ingestion into NotebookLM.
- **Shamanic post-processing layer** (optional) — four ritual generators (`oracle`, `lore fragments`, `raw roots`, `prophecies`) plus three LLM-driven voices (`Katla`, `Vieno`, `Lumi`) and a closing spark (`Sami`), all fully localized across the six supported languages.
- **OCR fallback** for scanned PDFs and image inputs (`.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`, `.webp`) via `pypdfium2` + `easyocr`. OCR languages are configurable from `config.json` / `config.ini`. The OCR dependencies are commented out in `requirements.txt` by default — `easyocr` also pulls `torch` and several hundred MB of model weights, so corpora that are not scans get a leaner install.
- **Structural-marker protection** — scene/act/chapter/part/book/section headings (in all six languages, in both square-bracket and bare forms) are preserved through the PDF header/footer-stripping heuristic.
- **Foreign-block re-segmentation** with per-language POS/stopword/lemma diagnostics, plus two-stage multilingual NER with per-sentence model dispatch.
- **Internationalized configuration filename** — the loader accepts both `config.json` and `config.ini` (contents are JSON in either case). The `.ini` extension is a usability concession to non-technical Windows users for whom `.json` has no default handler.
- **Internationalized README** — `README.md` (English) is the canonical version; translations live in `README_pl.md`, `README_ru.md`, `README_fi.md`, `README_is.md`, and `README_it.md`. Each version links to all the others.

### Known limitations

- The notebook narrative, all console output, and `CLAUDE.md` remain Russian/Polish/Russian respectively. Translating those is scoped for v1.1 to keep v1.0 focused on what works.
- Sentiment analysis is deliberately not included. The earlier `cardiffnlp/twitter-xlm-roberta-base-sentiment` cell was removed because the model is twitter-trained and gave near-coin-flip confidences on long-form Finnish/Polish content; the `distilbert-base-uncased-finetuned-sst-2-english` fallback is English-only and produced spurious "100% negative" verdicts for foreign corpora. For an accessibility-first tool, presenting confidently-wrong sentiment to a screen-reader user is worse than presenting nothing.
- The `_lg` spaCy variants are a hard requirement for topic modeling (KMeans needs paragraph vectors). The topic cell self-skips on missing vectors, so partial installations still produce a valid pipeline minus topics.

### Installation

See `README.md` for the full installation guide, including local virtual environments (venv / Anaconda) and Google Colab.

### Distribution

Source-only release. No binaries are produced for v1.0 — the GitHub-generated source-code asset attached to the tag is the canonical artefact.

### License

Released under the [MIT License](LICENSE). The pipeline is distributed as source only, and the notebook is, by nature, editable cell-by-cell through the browser or the VS Code Jupyter extension — the MIT license makes explicit what the format already implies.
