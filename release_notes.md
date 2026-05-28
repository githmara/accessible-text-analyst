# Release notes

All release entries are appended in reverse-chronological order. On GitHub, the latest entry is copied verbatim into the release body when a tag is pushed.

---

## v1.1.5 — critical fix: shamanic loaders skipped slugification of the project directory

**Severity.** Whenever the source filename's stem ends in `.` or `_` (e.g. `…__przyklad_.docx`), the entire shamanic post-processing layer silently produced zero artefacts while still printing `[ZAKOŃCZONO] Wszystkie artefakty audio są gotowe`. Upgrade is recommended if you run `shamanic_pipeline.py` or `shamanic_ai.py` on a corpus whose filename stem has trailing `.`/`_`. Pure-Python shamanic pipeline only — the notebook, the HTML report, and the NotebookLM Markdown are unaffected.

**The bug.** Five loaders in the codebase resolve `config.source_file` to a project subdirectory under `export_results/`: the notebook's `cell_corpus`, `generate_report.py`, `generate_md.py`, `shamanic_pipeline.py`, and `shamanic_ai.py`. The first three all run the stem through `_slugify(s)`, which ends in `.strip("._")` and therefore drops trailing dots/underscores — so a source file named `…__przyklad_.docx` lands in `export_results/…__przyklad/` (no trailing `_`). But `shamanic_pipeline.get_export_dir` and `shamanic_ai.get_export_dir` were using the bare `Path(source).stem` and therefore looked at `export_results/…__przyklad_/` — a directory that does not exist.

The failure was silent because each `ritual_*` function bails out with an early `if not <csv>.exists(): return` instead of raising, and the wrapping `output_directory.mkdir(parents=True, exist_ok=True)` happily created the (wrong) twin directory on the spot. The result: a warning line `[OSTRZEŻENIE] Katalog … nie istnieje`, four no-op rituals, a misleading `[ZAKOŃCZONO]` line, and an empty `audio_scripts/` subfolder in a brand-new bogus project directory. `detect_corpus_lang()` was collateral damage in the same path — without `accessible_text.html` in the (wrong) directory it fell through to the `en` default, so even the language banner was wrong.

**The fix.** Both `shamanic_pipeline.get_export_dir` and `shamanic_ai.get_export_dir` were rewritten to mirror `_resolve_project_dir` from `generate_report.py` verbatim: a local `_slugify(s, maxlen=80)` (`re.sub(r"[^\w\-\.]+", "_", s).strip("._")[:80] or "_default"`), URL handling via `urlparse` (`{host}_{path}`), bare-filename handling via `_slugify(Path(source).stem)`, and the same `_default` fallback for an empty `source_file`. After the fix the four rituals find their CSVs, `detect_corpus_lang()` reads the right `accessible_text.html`, and the artefacts land alongside the notebook's own exports as the layout has always intended.

The convention is now documented in `CLAUDE.md` ("Every loader in the codebase … probes `config.json` first, then `config.ini`") — what was already true for config probing is now also true for project-directory resolution. A shared helper in `shamanic_locale` was considered and rejected: the rule is "five loaders, identical logic" and copy-paste keeps each loader self-contained, which is the same trade-off the project already made for `_locate_config`.

**Out of scope (deferred).** No cleanup of pre-existing bogus twin directories on disk. If you upgraded after hitting this bug on a real corpus, you will see two sibling directories under `export_results/` — one real (`…_przyklad`, with all CSVs and the new audio_scripts) and one empty (`…_przyklad_`, with only an empty audio_scripts). Delete the empty twin manually; the pipeline will not regenerate it.

**Upgrade.** Pull the new tag. No notebook re-execution required — re-run `shamanic_pipeline.py` (and `shamanic_ai.py` if you use it). No config or dependency change.

### Distribution

Source-only patch release. The GitHub-generated source-code asset attached to the tag is the canonical artefact.

---

## v1.1.4 — housekeeping + RAG accessibility + non-Russian-reader documentation

**Theme.** Three loose ends from the v1.1.3 surgical revert: dead-code cleanup, a localized-filename display mismatch in the markdown narrative, and the realisation that v1.1.3 left the interactive Q&A inaccessible for any reader who does not speak Russian. Plus the missing README documentation explaining *why* the report and the new Q&A HTML are not optional but essentially mandatory for non-Russian users.

### Dead-code cleanup

Eleven orphan YAML files removed: `dictionaries/{en,fi,is,it,pl,ru}/notebook.yaml` and `dictionaries/{en,fi,is,it,pl}/narrative.yaml`. These were written in v1.1 stage 3b/3c for the notebook-narrative localization layer that v1.1.3 reverted. Nothing in the codebase has read them since the revert; `git grep` after the revert returned zero references. `artifacts.yaml`, `reports.yaml`, and `shamanic.yaml` remain — they are still actively read by the shamanic modules, the standalone Python scripts, and the corpus-language-localized theses filename.

### Theses filename display fix in the markdown narrative

The notebook's Russian markdown narrative hardcodes the file name `тезисы.txt` in two places — the intro cell's pipeline overview and the export cell's artefact list. Since v1.1 stage 2 the code actually writes the file under a corpus-language-localized name (`tezy.txt` for Polish, `theses.txt` for English, `teesit.txt` for Finnish, `tilgátur.txt` for Icelandic, `tesi.txt` for Italian — only Russian corpora still get `тезисы.txt`). A Polish reader would therefore see the narrative claim a file exists that is not actually in the export directory.

`generate_report.py` now does a single, targeted substitution before rendering each markdown cell: `source.replace("тезисы.txt", t(target_lang, "theses.filename"))`. Notebook source is unchanged (keeps the v1.0-spirit cleanness); the substitution is scoped to report rendering only. `target_lang` is already detected upstream from the `cell_langdet` stdout, so no new state is introduced.

### RAG accessibility: `cell_qa_rag` now writes `qa_results.html`

Two facts discovered after the v1.1.3 revert shipped:

- Jupyter in a browser hardcodes `lang="en"` on the document and runs on `localhost`. Browsers do not surface the "Translate this page?" prompt for `localhost` pages, and the hardcoded `lang="en"` makes screen readers announce the notebook's Russian narration with an English TTS voice. The VS Code Jupyter extension sidesteps most of this because its list-view does not expose ISO tagging — until you enter the output view (`Ctrl+Shift+↓`), where the same hardcoded-English wall appears.
- Reading the interactive Q&A *requires* entering the output view, because that is where the results are printed. So after v1.1.3 the entire RAG functionality was effectively reserved for Russian-speaking readers: anyone else had to copy-paste each result fragment into a translator just to learn whether their query had even hit anything.

`cell_qa_rag` now keeps its existing stdout (no change for Russian readers) and *additionally* writes the query + top-3 fragments to `export_results/<project>/qa_results.html` and opens that file in the system browser via `webbrowser.open()`. The HTML uses `<html lang="ru">` with minimal hardcoded Russian wrappers (`Вопрос`, `Найденные фрагменты`, `Фрагмент N (сходство: …)`), and wraps the query and every fragment in `<p lang="LANG">` where `LANG` is the corpus language. Outside Jupyter the browser does surface its translate prompt; inside the page the screen reader switches TTS voice per fragment as usual. Each new query overwrites the file. No new YAML dictionary was introduced (the cleanup ethos of this release is no dead YAMLs, not adding more) — the four wrapper strings are inline.

### README documentation: non-Russian-reader workflow

A new subsection `### Reading the output as a non-Russian user` (equivalent translations in `README_pl.md`, `README_ru.md`, `README_fi.md`, `README_is.md`, `README_it.md`) inside the existing `## Accessibility` section. It documents:

- The Jupyter-browser `lang="en"` + localhost problem and the VS Code Jupyter extension as the recommended IDE for accessibility.
- `generate_report.py` as effectively mandatory for non-Russian readers, with explanation of how the report's per-fragment `<span lang="…">` tagging plus a real browser's translate prompt cooperate.
- The new `qa_results.html` auto-open path for RAG.

`fi` / `is` / `it` translations remain drafted-but-unreviewed per the v1.1 known-limitation note.

**Upgrade.** Pull the new tag, re-execute the notebook, re-run `generate_report.py`. No config or dependency change required.

### Distribution

Source-only patch release. The GitHub-generated source-code asset attached to the tag is the canonical artefact.

---

## v1.1.3 — surgical revert: notebook narrative + HTML report back to v1.0 behaviour

**Why.** v1.1's per-fragment language-tagging strategy turned out not to deliver in practice. Modern browsers (Chrome, Edge, Firefox) do not switch TTS voice on inline `<span lang="...">` boundaries with the consistency the design assumed, and they only offer the "translate this page?" prompt based on the document-level `<html lang>` — which under v1.1 was `UI_LANG`, so a Polish reader who actually got Russian fallback text in the narrative was never offered a translation. v1.1.2's explicit per-div `lang` attribute did not fix the underlying browser behaviour either. Different readers prefer different browsers and asking everyone to switch browsers just for one report is a non-starter.

The pragmatic choice: hand the document back to the browser as a single-language Russian artefact, let the browser's built-in "translate this page?" pop up for non-Russian readers, and accept that auto-translation is imperfect rather than ship a tagging scheme the runtime ignores.

**What was reverted.** `accessible_text_analyst.ipynb` and `generate_report.py` are restored to the state at commit `239e529` (v1.1 stage 3a) — i.e. the last commit before notebook narrative was rerouted through `_t(UI_LANG, ...)` and before the HTML report was reframed around `UI_LANG`. Concretely:

- Notebook section headers and the final `cell_summary` report go back to hardcoded Russian.
- `cell_qa_rag`'s greeting goes back to hardcoded Russian.
- `generate_report.py` emits `<html lang="ru">` and `<title>Отчёт: Анализ текста</title>` again; the narrative.yaml swap layer and `NARRATIVE_KEYS` mapping are gone; the per-`<div>` `lang` attribute on `markdown-cell` and `output-box` containers (v1.1.2) is gone.
- `tag_target_language` (corpus-language `<span lang="pl/fi/...">`) and `EN_HARDCODE_PATTERNS` (technical `<span lang="en">`) are kept — they remain useful inside a Russian-default document for the few fragments the browser auto-translator will mishandle.

**What was preserved.** One feature added after v1.0 that survives the revert:

- **Localized theses output filename** (`tezy.txt` / `theses.txt` / `тезисы.txt` / `teesit.txt` / `tilgátur.txt` / `tesi.txt`). Without it, a non-Russian reader navigating the export folder in their file manager hears either total silence (if the SAPI Russian voice is missing) or a mistranslation. The four `t(LANG, "theses.filename")` callsites in `cell_theses`, `cell_export`, and `cell_summary` (guarded) stay.

**Latent bug fix that came out of the revert.** v1.0 / 239e529 already had the `for t in ...:` shadowing pattern that v1.1.1 retroactively patched, but the latent crash never fired because nothing after `cell_topics` called `t()`. After the revert, the four preserved `t(LANG, "theses.filename")` callsites — two of which run *after* `cell_topics` — would crash. Instead of bringing back the v1.1.1-style `from shamanic_locale import t as _t` alias (overkill for four callsites), the two shadowing loop variables were renamed surgically: `cell_topics`' `for t in sorted(df_topics["topic"].unique()):` → `for topic_id in ...`, and `cell_multilang_pass`' `for t in d:` → `for tok in d:`. Twelve lines of mechanical rename; zero functional change. The latent crash is now gone for any `_lg` corpus with topics.

**What stayed localized, untouched.** Everything outside the notebook/HTML-report surface keeps the v1.1 i18n machinery:

- Python-script `print()` output: `generate_report.py`, `generate_md.py`, `shamanic_pipeline.py`, `shamanic_ai.py` all still route stdout through `t(UI_LANG, ...)`. Operators see localized console messages regardless of corpus language.
- Shamanic ritual artefacts: `oracle_script.txt`, `lore_fragments/`, `raw_roots_chant.txt`, `prophecies.txt`, and the four LLM-driven ritual files still render in the corpus language via `t(corpus_lang, ...)` and the YAML dictionaries.
- Localized artefact filenames (theses) as noted above.
- README international versions, language-detection logic, multilingual NER, and all other v1.1 functional features are unchanged.

**Robustness fix: qa_rag skip is now content-based.** The v1.0 logic relied on `cell_id in ["md_qa_rag", "cell_qa_rag"]`, but the v1.0 notebook actually has *numeric* top-level cell IDs, so that check never matched at runtime. The interactive Q&A cell only stayed out of the report because Jupyter UI runs of `input()` produced no output, and the "if no outputs, skip" guard caught it. Running the notebook end-to-end via `nbclient` (the path used to regenerate reports here) breaks that accident: `input()` raises `StdinNotImplementedError`, which lands in the cell's outputs and leaks into the report. `generate_report.py` now detects the Q&A boundary by content markers (`(RAG)` in the markdown header; `EXIT_WORDS` plus `_qa_tfidf` in the code cell) and breaks out of the cell loop entirely. The report ends on `cell_summary`'s "Конец отчёта…" line, as the project convention always intended.

**Orphan files.** `dictionaries/{lang}/notebook.yaml` and `dictionaries/{lang}/narrative.yaml` are still in-tree but no longer read by anyone after this revert. Cleanup is deferred to a separate housekeeping change.

**Documentation imprecision (pre-existing).** The Russian markdown narrative cells still refer to the theses file as `тезисы.txt` (the v1.0 hardcoded name) even though the code now writes the localized filename. This inconsistency predates v1.1.3 and is left as-is to avoid scope creep; for a Russian reader the narrative still reads correctly because their corpus also produces `тезисы.txt`.

**Upgrade.** Pull the new tag, re-execute the notebook, re-run `generate_report.py`. No config or dependency change required.

### Distribution

Source-only patch release. The GitHub-generated source-code asset attached to the tag is the canonical artefact.

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
