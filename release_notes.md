# Release notes

All release entries are appended in reverse-chronological order. On GitHub, the latest entry is copied verbatim into the release body when a tag is pushed.

---

## v1.11.0 — broken PDF text layers are detected and rebuilt, and a report can only describe its own source

**Theme.** A 551-page Russian dictionary saved by macOS Preview went into the notebook as `(cid:602)(cid:619)…`: the letter map of its fonts stopped after "М", pdfplumber printed the raw glyph numbers, and language detection called the corpus German. Nothing said that the text layer was garbage. This release detects such pages, rebuilds them from the fonts embedded in the PDF where that is possible, cleans up documents converted from PDF to Word, and adds a gate that keeps a report from being written about a different source. Minor bump: new behaviour, a new dependency (`fonttools`) and a new launcher.

### What changed
- **Text-layer gate for PDFs.** A page whose text is mostly `(cid:N)` markers is never passed on silently. The notebook lists such pages by number, sends them to local OCR when `easyocr` is installed, and otherwise says they were skipped. The corpus language is never chosen from garbage.
- **Repair from the embedded font** (`naprawa_zrodel.py`, new dependency `fonttools<4.68`). For Type0 fonts the character code leads to the glyph number (`CIDToGIDMap` honoured); the glyph is looked up in the font's own `cmap`, then in its glyph names. Only fonts embedded in the PDF are used. A page counts as repaired only when every unmapped code resolves; otherwise it is reported. On the dictionary: 550 of 550 broken pages repaired, about 10 460 stress marks recovered, letters agreeing with the publisher's Word version on 99.9 % of most sampled pages.
- **Shared clean-up module `czyszczenie_tekstu.py`**, byte-for-byte identical with the Director's copy, with test vectors and a runner (`python czyszczenie_tekstu_wektory.py`, now in the release self-test). It joins words split at line ends only with evidence from the same document, joins letter-spaced words (in PDFs the word boundaries come from glyph geometry), replaces Symbol-font spaces and re-encodes text saved in the wrong encoding (Cyrillic read as Latin-1 and similar). Edit it only together with the Director. `.gitattributes` keeps its three files in LF.
- **Source gate in `generate_report.py`** (`zrodlo_raportu.py`, exit code 3, nothing written on refusal). The notebook's printed source path, a completed run, saved outputs and the printed page openings must all match the source in `config.json`. Before, a report about source A could be written into source B's folder, for example after running the notebook in VS Code without saving the outputs. Scans read by OCR, `custom_patterns` and unreadable files make the content check unverifiable instead of refusing.
- **`run_all.py`** registers the `analyst_env` kernel when it is missing or points to an interpreter that no longer exists, runs the notebook without the interactive cell and saves the outputs, then the report, the local shamanic pipeline and, for Finnish corpora, the Book `scan`. A kernel that fails to start no longer wipes the saved outputs.
- **The Book of the Unsaid** reads `<meta name="ata-omorfi">` from the folder's report: when omorfi took part, a grammar-leak refusal says the engine itself may need fixing instead of suggesting another run. The skill in `skills/ksiega-niedomowien/` is complete again (backup comparison after `tidy --apply`, entry format, `fill` failures) and documents the real exit codes.
- **Accessibility of the report.** This cycle's technical terms (`ToUnicode`, `fontTools`, `(cid:N)`, `U+XXXX`, encoding pairs such as `latin-1>cp1251`, `OCR`, `pip install …`) are tagged as English, so NVDA no longer reads them with the Russian or Finnish voice. `generate_report.py` and `run_all.py` write UTF-8 to a redirected console.

### Verified
- Dictionary PDF through the notebook's `load_pdf`: pages 2–551 repaired, page 1 (an image) read by OCR, 0 leftover `(cid:` markers. Dictionary Word file: clean-up counts identical to the Director's (4 830 joined words, 55 letter-spaced words, 253 spaces).
- No false re-encoding across 595 files from disk with ATA's real alphabets; correct Spanish stays unchanged.
- Source gate on 480 files: 0 false refusals; the glitch reproduced before the fix (exit 0, wrong report) and refused after it (exit 3, nothing written).
- A fresh pre-release audit with proof by execution found 11 issues (the release self-test would have failed on ubuntu without `markdown`, a name-keyed font cache, three false refusals of the source gate, `run_all.py` wiping outputs, a console crash); all fixed with tests.
- Translation parity, the console hard-code gate, the language basics audit and every self-test pass.

### Distribution
Source-only release. The GitHub-generated source-code asset attached to the tag is the canonical artefact.

---

## v1.10.3 — replaced entries in the Book of the Unsaid are marked and can be cleaned up

**Theme.** v1.10.2 noted that a folder whose chant changed after an entry was written gets its block back under a new id. That happened: the Polish constitutional court corpus got entry 16 for the same block 1 as entry 12, and `status` printed only "entries 2 (no. 12, 16)", which did not say that 12 was out of date. Patch bump: clearer output and one new command.

### What changed
- **Replaced entries are marked.** When a folder has two records for the same block number, the older one is replaced by the newer one. `status` and `scan` now print it as `12 (replaced by 16)`, or `(replaced by obvious block)` when the newer block was guessed completely. `status` ends with a line that counts them and points to `tidy`.
- **New command `tidy`.** Without options it only lists what it would do. With `--apply`, the newer entry takes the old one's place and number in the Book, all entries are renumbered, the old block is removed from the state file, the key file and the work folder, and the newer record keeps a `replaces` field naming it. Before writing, the Book, the state file and the key file are copied to `*.bak`.
- **Line endings.** The Book is rewritten with its dominant line ending, because entries appended from different systems can mix them.
- **`scan --folder` and `scan --blocks`** also count done blocks that are no longer in the folder's current chant.

### Verified
- On a copy of the real Book: `tidy --apply` moved entry 16 into place 12, the Book had 15 entries numbered 1–15, the state and key files agreed with it, the old packet folder was gone, and a second `tidy` found nothing. The same check with a newer block judged obvious removed the old entry and renumbered the rest.
- Then on the real Book: `status` shows the folder with entry 12 only, and `scan --folder` shows 1 of 9 blocks done with 0 stale entries.
- Translation parity, the console hard-code gate and the language basics audit pass.

### Distribution
Source-only patch release. The GitHub-generated source-code asset attached to the tag is the canonical artefact.

---

## v1.10.2 — the Book of the Unsaid shows how far each folder has got

**Theme.** `ksiega_niedomowien.py scan` listed which folders pass the filters but said nothing about the Book itself, and `status` listed open packets without naming their folder. A folder that already had an entry, or a packet waiting to be judged, looked exactly like a fresh one, so it was easy to work a finished folder again. Patch bump: two commands print more, one new optional flag, nothing to configure.

### What changed
- **`scan`** now prints a Book line under every folder: entries (with their numbers), obvious blocks and open packets with their stage. It reads the Book's state file, the Book itself and the work folder, without omorfi, so it costs nothing.
- **`scan --folder X`** also counts blocks: done, in open packets and left to prepare. The folder name may be given by its start, as in `prepare`. **`scan --blocks`** does the same for every folder; it is opt-in because building the blocks takes a few seconds per folder. `--json` carries all of it under `book`.
- **`status`** groups progress by folder: entries, obvious blocks, and each open packet with its block number and the files it already has. It ends with a hint pointing to `scan --folder` and `scan --blocks`.
- The skill (`skills/ksiega-niedomowien/SKILL.md`) tells the agent to check this progress before `prepare`, and to finish an open packet instead of preparing a new one.

### Note
Blocks are identified by their roots. If a folder's chant changes after an entry was written (for example after re-running the notebook with better lemmas), the old entry still counts under "entries", but its block no longer appears among the current ones, so `scan` can show one entry and 0 blocks done.

### Verified
- Translation parity, the console hard-code gate and the language basics audit pass; the release-script tests pass.
- `status`, `scan --folder` with a name prefix and `scan --blocks` were run on all 29 Finnish export folders.

### Distribution
Source-only patch release. The GitHub-generated source-code asset attached to the tag is the canonical artefact.

---

## v1.10.1 — Finnish lemmas no longer fall back to spaCy's garbage when the tagger and omorfi disagree

**Theme.** A colloquial Finnish Whisper transcript about the Polish constitutional court was refused by the Book of the Unsaid for a grammar leak (2.17, limit 1.0), although omorfi was active in the notebook. Two keywords caused it: *blokka* and *luulit*. spaCy tagged `blokkaa` ("blocks") and `luulit` ("you thought") as nouns, while omorfi knows them only as verbs. The `omorfi_lemmas` component treated that disagreement as "trust spaCy", so spaCy's garbage lemma *blokka* survived, and for `luulit` the recased automaton offered an invented noun compound *LuuLIT*, which matched the noun tag. Patch bump: nothing to configure; Finnish lemmas get more accurate.

### What changed in `cell_model` (Finnish with omorfi only)
- **Lemma fallback.** When no omorfi reading matches spaCy's part of speech, the token used to keep spaCy's lemma. Now omorfi's lemma replaces it if spaCy's lemma is not a dictionary form according to omorfi and every remaining omorfi dictionary reading gives the same lemma. Only the lemma changes; the part of speech and morphology stay spaCy's.
- **Names are left alone.** The fallback skips proper nouns, capitalized words in mid-sentence and capitalized omorfi lemmas, because omorfi often does not know a name and would substitute a common noun (*Tuskia* → *tuska*, *Valensa* → *Vale*).
- **Automaton artefacts are ignored.** omorfi's guess for an unknown word (part of speech X, lemma equal to the word, infinite weight) no longer makes garbage such as *blokka* look like a dictionary word. Compounds that omorfi guesses productively (weight 10 or more: *tapa+maa*, *sama+laki*) are not used by the fallback. Lemmas with capitals in the middle of a lowercase word (*LuuLIT*, *maniEK*) are dropped everywhere; abbreviations such as *PiS* keep their reading because the word itself has the capital.

### Headless execution with nbclient
`nbclient` is now listed in `requirements.txt` as a CI-friendly tool, and the READMEs show how to execute cells 0–39 without Jupyter's interface. The interactive question-and-answer cell is excluded because it ends with an EOF error when nobody can type.

### Verified
- The old and new `cell_model` were run on all 32 Finnish transcripts that have an export folder (84,427 alphabetic tokens). 387 tokens changed lemma, 0.46%. Almost all changes replace a broken lemma with the dictionary one: *kene* → *kuka*, *kritiso* → *kritisoida*, *miljarde* → *miljardi*, *tarvii* → *tarvita*, *eiks* → *ei*, *kanssamme* → *kanssa*. A few colloquial homographs can now get the wrong dictionary word (*kaos* → *kakoa*, *törmät* → *törmä*); before, these had no dictionary lemma at all.
- Notebook cells 0–39 (with sentiment), `generate_report.py` and `shamanic_pipeline.py` were run on the refused corpus. Its keywords now contain *blokata* and *luulla*, the grammar leak is 0.0, and a full Book of the Unsaid cycle produced an entry.

### Distribution
Source-only patch release. The GitHub-generated source-code asset attached to the tag is the canonical artefact.

---

## v1.10.0 — every language defined in one place, and tokens that keep foreign letters

**Theme.** Until now a language existed in about a dozen hand-written lists across the notebook, `generate_report.py` and `shamanic_locale.py`. Nothing connected them, so a seventh language would have passed the translation checks and then silently fallen back to English models and patterns. Each language is now described once, in `dictionaries/<code>/podstawy.yaml`, and every per-language map in the code is derived from it. Building that file showed that some of the old lists were themselves wrong. Minor bump: there is a new required data file per language, and the analysis of the same source can differ.

### One file per language
- `dictionaries/<code>/podstawy.yaml` holds the lingua detector name, the Russian display name used in the notebook output, the locale for `lang=` in the exports, the spaCy model, the alphabet, the diacritics, abbreviations, scene and chapter words, "related articles" stop phrases and the CSS words for web widgets.
- Every field is required. An empty value (`""`, `[]`, `null`) declares that the language has nothing there; a missing field stops every script with a message naming the file and the field.
- The prompts of the shamanic rituals take the language name from the same file, without the old fallback to English.
- Adding a language now means copying a folder, filling in the files and passing the audit below. No Python file needs a new entry.

### Language basics audit
`.github/scripts/audyt_podstaw.py` runs before every release and blocks it on any problem:
- the fields of each `podstawy.yaml`, a lingua name with the folder's ISO code, the locale, alphabet, diacritics and abbreviations, and a `README_<code>.md` for each language;
- a guard that fails when a list of languages comes back into the code: `Language.POLISH`, a dictionary keyed by language codes, a regular expression such as `en|pl|ru`, or a list of language names;
- a check of spaCy's model index for every language whose `spacy` field is `null` (today Icelandic). When spaCy publishes a model, the audit fails and says which line to add. Nothing is installed. If the index cannot be reached, the release waits; a missing index is never reported as a pass.

### Changes in the analysis
- **TF-IDF tokens** (keywords, theses, topic words) are now any run of at least two letters, with a hyphen or apostrophe allowed between letters, for every language. v1.9.1 used `a-z` for English and the Polish or Russian alphabet for those languages, so words with other letters disappeared. On the English Wikipedia article about Kurt Gödel the subject's own name was missing from the keywords, together with "Brünn" and "für". Italian, Finnish and Icelandic used `\S{2,}`, which also counted numbers and punctuation. Numbers no longer count in any language.
- **Abbreviations** are normalised in all six languages, not only Polish, Russian and English. Only spaced multi-part abbreviations are joined ("m. in." → "m.in.", "u. þ. b." → "u.þ.b."), dots are required, and the rules no longer reach across a blank line. The old rules were not safe to repeat: Polish "m.in.:" gained a dot on every pass, Italian "pagg." (pages) was rewritten to "pag.", and rules with an optional dot added dots to ordinary words such as Finnish "v" or Italian "art".
- **Code fragments in the HTML report** recognise Italian and Icelandic multi-part abbreviations. Short fragments such as `os.` or `str.` are not taken for any language.
- **spaCy:** a language without a model gets an empty pipeline in its own language instead of the English model. A language that spaCy does not know at all gets the multilingual one, with a warning.

### Verified
Notebook cells 0–39 were run with v1.9.1 and with this release on one corpus each in Finnish, Polish, Italian and English.
- Finnish: theses and keywords are identical; one topic's word list changed order.
- Polish: apart from the repaired "m.in.", only the order of words in one topic changed.
- Italian: keywords are identical, and 37 of 41 theses are the same. The rest moved because years and page numbers no longer add weight, and "pagg." is no longer rewritten.
- English: keywords now include "Gödel", "Brünn" and "für"; 99 of 104 theses are the same.
- A separate check ran the Italian and English spaCy lemmas, with apostrophes, hyphens, foreign letters and abbreviations, through the old and new token rules. No word was lost.

### Distribution
Source-only minor release. The GitHub-generated source-code asset attached to the tag is the canonical artefact.

---

## v1.9.1 — page numbers and headers are recognised by position, not by shape alone

**Theme.** A pre-release audit of the Director, which shares this PDF logic, proved by execution that a line shaped like a page number was enough to delete it. v1.9.0 inherited that: a lone "II" chapter heading, the word "MIX" or a year in the top or bottom margin of a single page disappeared from the corpus. Patch bump: nothing new to configure, the corpus only keeps more of the source text.

### What changed
- A bare page number is removed only when it advances together with the page — the same difference "number minus page index" in the same top or bottom margin band on at least a quarter of the pages (minimum two). A one-page document loses nothing. Roman numerals count only in their canonical form, so "did" or "IIII" are words.
- The margin band is 7% of the page height instead of 12%. Word's default margin is 8.5% of an A4 page, so the wider band also covered the first and last line of body text.
- On pages with a text layer, a repeated header or footer must also lie in that margin band. A paragraph repeated on several pages that ended up at the edge of the page after the page number was removed is prose and stays. Scanned (OCR) pages keep the previous edge-only rule, because OCR gives no positions.
- A page never loses all its lines to header removal.

### Distribution
Source-only patch release. The GitHub-generated source-code asset attached to the tag is the canonical artefact.

---

## v1.9.0 — Markdown input, safer cleaning, scans inside text PDFs

**Theme.** Two new kinds of input reach the corpus — Markdown files and scanned pages inside an otherwise text PDF — and the cleaning heuristics that run before analysis no longer delete prose. An audit on 2026-10-15 reproduced, by execution, cases in all six languages where the old rules removed whole articles, ordinary sentences and grammatical repetitions. The rule now is that over-cleaning is worse than leftover junk: a heuristic that can hit prose is narrowed or removed, even if a few garbage lemmas remain. Minor bump: a new input format, and the corpus produced from the same source can differ.

### Markdown input
`source_file` may now point to a `.md` or `.markdown` file. It is converted to HTML (`tables`, `fenced_code`, `footnotes`, `def_list`, `abbr`, `sane_lists` — the same set the Director uses, except line-break handling) and read in document mode, without the web-page heuristics: front matter and code blocks are dropped, link text and footnote text are kept, a "See also" section at the end is cut. Task-list boxes `[ ]` and `~~strikethrough~~` markers stay in the text, because python-markdown has no extension for them.

### Web pages and HTML files
`load_html` and `load_url` were two copies of the same code; they now share one extractor, so a fix reaches both.
- The "Related articles / Читайте также / Lue myös" cut now fires only when a short element's whole text is the stop phrase. Before, a phrase anywhere inside a wrapper `div` deleted the whole article, and sentences such as "Мы рекомендуем…" or "lue myös toinen luku" truncated the rest of the text.
- Widgets are recognised by whole class or id tokens, and an element holding at least half of the article is never removed. Before, `shared-content`, `widget_text` or `content-with-sidebar` deleted the article itself.
- The view-counter cleanup runs only in the article head, never on a year, so "NATO 2024", "PKB 2500" and "EU 2030" survive; the removal of a doubled title respects word boundaries.

### PDF
- Pages without a text layer are now read with OCR one by one, in page order, also when the rest of the PDF has text. Before, OCR ran only when no page had text, so scans inserted into a text PDF silently disappeared. Pages that stay empty (no OCR installed, wrong `ocr_languages`) are listed by number.
- Bare page numbers ("7", "- 7 -", "7 / 120") are removed when they sit in the top or bottom margin band of the page, using the same pattern as the Director. They used to stay glued to the last sentence of each page.
- Repeated headers and footers are now looked for only in the first and last three lines of a page, with a higher threshold. Refrains, repeated dialogue lines and numbered lessons are no longer taken for headers. Screenplay markers `INT.` / `EXT.` are now really protected.

### Text correction
Doubled words are no longer collapsed. Repetition is grammatical in all six languages («чуть чуть», «piano piano», «bardzo bardzo», "had had"), and the rule also merged phone numbers. A typo such as "the the" now costs one extra lemma instead.

### Console localization gate
`.github/scripts/bramka_printow.py` checks every script in the repository root and fails the release when a `print()` carries a hard-coded literal instead of `t(UI_LANG, …)`. The notebook is outside the gate, because its output is Russian by design. It found five English "library missing" messages in `generate_md.py` and `generate_report.py`; they now come from `deps.err_missing_lib` in all six languages.

### Distribution
Source-only minor release. The GitHub-generated source-code asset attached to the tag is the canonical artefact.

---

## v1.8.0 — Python 3.14, bounded dependencies and a dependency audit

**Theme.** The project now runs on Python 3.14, and `requirements.txt` finally says which versions were tested. Until now the manifest had no version bounds at all, so a fresh install picked whatever PyPI offered that day. On 2026-10-15 that meant `openai` 3.31 instead of the 2.37 the code was written against, `pandas` 3 and `numpy` 2.5, a combination nobody had run. Minor bump: there is a new command, and the install result changes.

### Python 3.14

- Verified on the same Finnish corpus with Python 3.11 and Python 3.14: notebook cells 0–39 (everything before the interactive Q&A cell, including sentiment and `omorfi`), `shamanic_pipeline.py`, and a full `ksiega_niedomowien.py` cycle (`prepare` → `draft` → `fill` → `judge`) through the API.
- Every export file (`*.csv`, `topic_keywords.json`, `accessible_text.html`, the theses) and every shamanic artefact was **byte-identical** between the two interpreters. `accessible_text.docx` differs only in ZIP compression; its contents are identical.
- All 137 packages, including the optional ones, install from ready-made wheels on Windows x64 for Python 3.14, so nothing has to be compiled.
- `omorfi-download` needs no extra options on Python 3.14 and downloads the same automata (v0.9.9).
- **Minimum Python is now 3.12** (required by `numpy` 2.5 and `lingua-language-detector` 2.2). The READMEs said 3.10 and are corrected in all six languages; the Conda example now creates a Python 3.14 environment.

### Bounded dependencies

Every package in `requirements.txt`, including the commented-out optional ones (sentiment, Icelandic, OCR, `omorfi`), now has an upper bound one minor version above the tested release, for example `openai<3.32` or `torch<2.15`. An optional line stays commented as `# torch<2.15`, so uncommenting it keeps the bound. The file header records the Python version and the date of the test.

### `audyt_zaleznosci.py`

New command: `python audyt_zaleznosci.py`. It compares what is installed with the bounds and with the latest release on PyPI and reports, for each package, one of: up to date, held back by a bound on purpose, newer release allowed by the bound but not tested yet, installed version outside the bound, or missing. Optional packages that are not installed are skipped. It **only warns** and always exits with code 0: this project is not frozen into an installer, you install the dependencies yourself, so an untested release is information for you, not a reason to stop. Messages are shown in `ui_lang`, in all six languages.

### Releases are created from these notes

A new workflow publishes a release by itself when a `## vX.Y.Z — title` section at the top of this file reaches `main` and the tag `vX.Y.Z` does not exist yet. The tag and the release are created together, and the title and body come from that section. An existing tag means there is nothing to do, and a version that is not newer than the latest tag stops the workflow with an error. The workflow runs only on pushes to `main` and on a manual start, and the notes are treated as data, never as commands. This release is the first one published this way.

### TiflotecniaVoices patch

The "New issue" page now links to the Reżyser Audio GPT repository for the TiflotecniaVoices patch for NVDA, which is distributed there.

### Localization

New keys `deps.*` in all six `reports.yaml`.

**Upgrade.** Create a fresh environment on Python 3.12 or newer (3.14 recommended), run `pip install -r requirements.txt`, download the spaCy models you need and, for Finnish, run `omorfi-download` again. Then run `python audyt_zaleznosci.py`. If you use the notebook in Jupyter or VS Code, register the kernel of the new environment again (`python -m ipykernel install --user --name analyst_env`).

### Distribution
Source-only minor release. The GitHub-generated source-code asset attached to the tag is the canonical artefact.

---

## v1.7.1 — the default model moves to `gpt-6.1-sol` before `gpt-4o` is retired

**Theme.** OpenAI retires `gpt-4o` (together with `gpt-4o-mini`, `gpt-4.1` and `gpt-4.1-mini`) on **January 14, 2027**. `gpt-4o` was the default model of both providers that have one, so with an empty `llm_model` the shamanic layer and the Book would have stopped working that day. Patch bump: no new command and no config key changes.

### Default model

| `llm_provider` | before | now |
|---|---|---|
| `openai` | `gpt-4o` | `gpt-6.1-sol` |
| `openrouter` | `openai/gpt-4o` | `openai/gpt-6.1-sol` |

`gpt-6.1-sol` costs the same per output token as `gpt-4o` and less per input token ($2 / $10 per million tokens, against $2.50 / $10). A model set explicitly in `llm_model`, `kirja_drafter_model` or `kirja_filler_model` is not affected.

### Temperature degradation in `shamanic_ai.py`

The four rituals send creative temperatures (Katla 0.7, Vieno 0.8, Lumi 0.65, Sami 0.85). The gpt-6 family accepts only the default value (1) and rejects anything else with HTTP 400, so changing only the name would have made all four rituals fail. Measured before the change on `gpt-6.1-sol` and `gpt-6-luna`.

- The rituals now call the new `llm_klient.chat_text()`. It sends the ritual's temperature first. On a 400 that concerns `temperature` alone, it retries once without it, prints one `[INFO]` line and skips the parameter for that model for the rest of the run.
- Every other error is raised as before. A model that accepts a temperature keeps it, so `gpt-4o` and other models set in the config behave exactly as in v1.7.0. OpenRouter drops an unsupported temperature without an error (measured), so no retry happens there.
- The Book already sent no temperature (`chat_json`), so `draft` and `fill` needed no change.

### Localization

New key `llm.info_no_temperature` in all six `reports.yaml`.

**Upgrade.** Pull. If you want to stay on `gpt-4o` until it is retired, set `"llm_model": "gpt-4o"`. You don't need to re-run the notebook.

### Distribution
Source-only patch release. The GitHub-generated source-code asset attached to the tag is the canonical artefact.

---

## v1.7.0 — LLM providers bound to their keys, API drafter for the Book

**Theme.** Two things. First, an API key can no longer reach a host it was not issued for: until now `fill` and `shamanic_ai.py` shared `OPENAI_API_KEY`, and `kirja_filler_base_url` / `--base-url` decided where it went. Putting an OpenRouter key into that variable broke `shamanic_ai.py`, and forgetting to swap it sent the OpenAI key to a third party. Second, the Book of the Unsaid gets an API drafter, so you no longer need an agent to use it. Minor bump: there is a new command, and one config key is removed.

### LLM providers (`llm_klient.py`, shared)

| `llm_provider` | key in `golden_key.env` | address |
|---|---|---|
| `openai` (default) | `OPENAI_API_KEY` | `api.openai.com`, passed explicitly (the SDK would otherwise honour `OPENAI_BASE_URL` from the environment) |
| `openrouter` | `OPENROUTER_API_KEY` | `openrouter.ai`, fixed; `llm_base_url` is ignored |
| `openai_compat` | `LLM_COMPAT_API_KEY` | `llm_base_url` (required), with `llm_model` (required) |

- New config keys: `llm_provider`, `llm_model`, `llm_base_url`, and for the Book `kirja_llm_provider` (empty = `llm_provider`) and `kirja_drafter_model`. `kirja_filler_model` stays.
- `shamanic_ai.py` uses the same client. With an empty config it behaves exactly as before (OpenAI, `gpt-4o`).
- **Removed:** `kirja_filler_base_url` and `fill --base-url`. A config that still has `kirja_filler_base_url` is refused with a migration message instead of being mapped silently, because a silent mapping would send `OPENAI_API_KEY` to OpenRouter, which is exactly the leak this release closes.

### The Book of the Unsaid

- **Packets are easy to point at.** `draft` / `seal` / `fill` / `judge` take the packet id printed by `prepare` (or its first characters), the start of the corpus folder name (the next packet of that folder that is ready for the command is taken), or the packet folder path. When nothing matches, the script lists the open packets and prints a ready-to-run command. `prepare` prints the next command to run. `prepare` and `scan` also take the folder name without `--folder`.
- **`draft <id>`** — the API writes `draft.json`, which is then validated exactly as `seal` does it. If it is rejected, the model gets the draft back with the validator's concrete objections (in English, while the operator sees them in `ui_lang`). It retries up to 2 times, so 3 attempts in total. Exit codes: 0 = sealed, 4 = still rejected (the last draft stays in the packet for repair by hand or with the skill), 1 = API error. An existing `draft.json` is never overwritten without `--force`. It sends verbatim source sentences (`truth.sentences`) and prints how many before the call. The skill is still the stronger mode: unlimited retries, with the agent reading the objections as it goes.
- **Structured outputs, retries and diagnostics.** `draft` and `fill` first ask for a strict JSON schema. If the endpoint rejects it (400/422), they fall back to `json_object`, then to the prompt alone; the pattern is copied from the director's `core_llm.py`. Rate limits, timeouts and context overflow are never degraded. `fill` retries twice when the reply is unusable or a gap is missing. Every unusable reply is saved in the packet (`draft_reply_N.txt` / `fill_reply_N.txt`, with `finish_reason` and any refusal), and the console prints one diagnostic line. Until now `fill` printed a truncated reply and stopped, so a failure gave no hint of its cause.
- **`fill` now runs `judge` itself** once the guesses are saved. Run `judge` on its own only after a blind subagent.
- `seal` deletes a stale `guesses.json` when it writes a new `blind.json`.
- One rule cannot be checked deterministically: *do not attribute to real people facts or accusations that are not in the source sentences*. The drafter prompt, the skill and the README all state it, but nothing verifies it.
- README §7 now lists three privacy levels (`fill` < `draft` < the agent). It also says to run the skill in the **Code** tab with a **local** session: in plain chat mode or in a cloud session, the files the agent reads are copied to the cloud.

### Localization

New keys: `llm.*` and the `draft` part of `kirja.*`, in all six `reports.yaml`. Removed keys: `kirja.err_no_openai`, `kirja.err_no_key`, `kirja.default_endpoint`.

**Upgrade.** Pull. If your config has `kirja_filler_base_url`, delete it and set `kirja_llm_provider` (or `llm_provider`): use `openrouter` with `OPENROUTER_API_KEY`, or `openai_compat` with `LLM_COMPAT_API_KEY` + `llm_base_url` + `llm_model`. If you put a non-OpenAI key into `OPENAI_API_KEY`, move it to its own variable. You don't need to re-run the notebook.

### Distribution
Source-only minor release. The GitHub-generated source-code asset attached to the tag is the canonical artefact.

---

## v1.6.0 — The Book of the Unsaid (*Sanomattomien kirja*), a Finnish agent skill

**Theme.** A new optional layer on top of the raw-roots chant: `ksiega_niedomowien.py` plus an agent skill (`skills/ksiega-niedomowien/SKILL.md`) that turn `raw_roots_chant.txt` into an incrementally growing cryptic diary from the North. The notebook and the existing shamanic scripts are untouched. Minor bump.

### How it works

For each block of 3–6 consecutive roots an agent writes a misty Finnish entry with gaps whose answers are verbatim spans of the source; a **separate, blind model** tries to fill the gaps from the entry alone; every gap it guesses is judged obvious and its fragment is removed. The rest — KATLA (warning system) reading the roots, VIENO (shamanic narrator) with the unsaid gaps — is appended to `export_results/Sanomattomien_kirja.md`, with the answer key in `Sanomattomien_kirja.avain.json` and the state in `Sanomattomien_kirja.tila.json`. Re-running never duplicates entries.

- **Script = the deterministic half:** `scan`, `prepare`, `seal`, `fill`, `judge`, `status`. Blocks are cut by dynamic programming so each block's truth sits in as few source places as possible; `seal` rejects drafts whose answers are not verbatim in **both** `accessible_text.html` and `accessible_text.docx`, are a root of the block, leak into the text, or copy 7+ consecutive source words; `judge` matches by omorfi lemmas, unknown-name prefixes, compound heads and spelling variants.
- **Agent = the creative half:** writing `draft.json` per the skill. The skill ships under `skills/` because the repo gitignores `.claude/`; copy it into `~/.claude/skills/` or `.claude/skills/`, or zip the folder for the Claude apps (*Customize → Skills*). Any agent that can run local commands can follow the same `SKILL.md`.
- **Blind filler `fill` (optional):** for platforms that cannot spawn an independent subagent, or to use a different model as the guesser. Sends only the answer-free `blind.json` to an OpenAI-compatible Chat Completions endpoint. The key is the same `OPENAI_API_KEY` from `golden_key.env` as in `shamanic_ai.py`; new config keys `kirja_filler_model` (default `gpt-4o`) and `kirja_filler_base_url` (empty = OpenAI; e.g. `https://openrouter.ai/api/v1`, in which case the variable holds that provider's key), overridable with `--model` / `--base-url`.

### Input filters (hard refusal)

Only `export_results/` subfolders with a Finnish name, `<html lang="fi">`, a Finnish chant and **no grammar leak** qualify; anything else (a thesis, Polish documents, pasted text) is refused with a reason, and the skill forbids working around the verdict. The `roots.header` line in any of the six languages is stripped. The grammar-leak score counts, over the full `keywords_tfidf.csv`, Finnish inflected forms that survived lemmatization plus spaCy garbage lemmas (`(B + 2·G)` per 100 terms, threshold 1.0). Calibrated on ~30 real corpora, it rejects exactly the folders produced before omorfi was wired in (v1.5.0) and gives the same verdict with either omorfi automaton.

### Why Finnish only

The game lives on what lemmatization leaves unsaid. Finnish is agglutinative: case endings, possessive suffixes, clitics and verb categories carry *who, where, from where, to where, whose* and *whether* inside the word (`talossa`, `talosta`, `taloon`, `taloni`, `tehtäisiinkö`), so reducing the chant to `TALO`, `TEHDÄ` strips the relations themselves — exactly the gaps a listener fills. In Polish and Russian the lemma loses the ending, but much of the relation sits in a separate preposition; English loses little beyond number and tense; Icelandic and Italian sit closer to the Polish/Russian and English patterns respectively. Technically, proving that a chant is grammar-free and matching roots back to inflected text needs a dictionary analyser, which only Finnish has in this pipeline (omorfi).

### Localization

Console output is fully localized via `ui_lang` (`kirja.*` in all six `reports.yaml`); the Book's own strings are `book.*` in all six `shamanic.yaml` (the Book itself is always Finnish).

**Upgrade.** Pull. For the Book: enable omorfi (Installation step 5), copy the skill as described in README §7, optionally set `kirja_filler_model` / `kirja_filler_base_url`. No notebook re-run required; folders produced before v1.5.0 need a re-run with omorfi to qualify.

### Distribution
Source-only minor release. The GitHub-generated source-code asset attached to the tag is the canonical artefact.

---

## v1.5.2 — `cell_theses`: the v1.5.1 fix, now bullet-proof

**Why.** v1.5.1 was shipped fast, under pressure from a corpus that crashed the notebook. The fix itself was correct — this release validates it and closes the remaining ways the same crash could come back.

**Validation of v1.5.1 (on the corpus that triggered it).** Re-splitting a joined paragraph with the dominant model produced 7 sentences where `cell_para` had produced 6 in exactly one paragraph out of 51 (301 sentences total). That single +1 pushed `sent_cursor` to 301 with 301 scores available, so the last paragraph got an empty slice and `.argmax()` raised. Iterating over `para_sentences` keeps the cursor at exactly 301 — the diagnosis and the fix both hold, and re-running the new loop against the old one over 200 randomized score vectors gives byte-identical theses.

**What was still fragile.** The loop's arithmetic silently depended on a filter that happens to be a no-op today:

- `sent_cursor` advanced by the *filtered* sentence count while `sent_scores` indexes the *unfiltered* one, so a single sentence shorter than 11 characters inside a paragraph would desynchronize every following paragraph — silently mis-scoring theses, and eventually re-raising the same argmax crash. (Today `cell_para` and `cell_foreign_resegment` both drop such sentences before they reach `para_sentences`, so the filter never fires — but nothing enforced that.)
- `if n == 0: continue` skipped the cursor advance entirely, i.e. the same desynchronization with a stronger effect.
- Slices were never bounded by `len(sent_scores)`, so any future mismatch went straight to an empty-sequence `argmax` instead of a diagnosable message.
- `zip(paragraphs, para_sentences)` truncated to the shorter list without a word.

**What changed.** The cursor now advances by the full paragraph length; candidate sentences carry their *global* index, so the score always belongs to the sentence it is reported for; slices are clipped to the score array; and the best sentence is picked with `max()` over a non-empty candidate list, which makes an empty-sequence `argmax` unreachable. The invariant `sum(len(p) for p in para_sentences) == len(df_sent) == len(sent_scores)` is now checked explicitly and any violation prints a Russian `[ВНИМАНИЕ]` line naming the two cells to inspect, plus a count of skipped paragraphs — the cell degrades to a partial result instead of aborting the run. On a healthy pipeline the output is unchanged.

**Upgrade.** Pull, `jupytext --sync`, re-execute the notebook. No config or dependency change.

### Distribution
Source-only patch release. The GitHub-generated source-code asset attached to the tag is the canonical artefact.

---

## v1.5.1 — critical fix: `cell_theses` crashed on empty sequence

**Severity.** A crash in `cell_theses` ("attempt to get argmax of an empty sequence"). Upgrade is recommended if you process texts where re-segmentation differs from the original chunking (especially Finnish corpora using the omorfi dictionary).

**The bug.** The `cell_theses` block used `nlp(para).sents` to re-split paragraphs into sentences for extractive summarization. However, this re-segmentation occasionally produced a different sentence count than the original segmentation performed in `cell_para`. As a result, the `sent_cursor` pointer advanced out of bounds relative to the `sent_scores` array, yielding an empty slice `seg` and crashing on `seg.argmax()`.

**The fix.** The loop now iterates over the already segmented `para_sentences` generated during paragraph construction. This ensures the sentence count per paragraph remains perfectly synchronized with the global `sent_scores` array.

**Upgrade.** Pull the new tag, sync via jupytext, and re-execute the notebook. No config or dependency change is required.

### Distribution
Source-only patch release. The GitHub-generated source-code asset attached to the tag is the canonical artefact.

---

## v1.5.0 — omorfi dictionary morphology for Finnish (and the Gemini Notebook rename)

**Theme.** An optional quality upgrade for Finnish corpora: the notebook can now plug the [omorfi](https://github.com/flammie/omorfi) morphological analyser into `fi_core_news_lg`, replacing the statistical lemmatizer's frequent garbage lemmas (and the near-silent morphologizer) with dictionary analyses. Plus a naming refresh: Google renamed NotebookLM to Gemini Notebook (announced 2026-07-16), and the Markdown artefact follows. Notebook + docs change; the analysis pipeline for the other five languages is untouched. Minor bump.

### New: `omorfi_lemmas` component (optional, Finnish only)

- **What it fixes.** The statistical edit-tree lemmatizer in `fi_core_news_lg` is weak against Finnish agglutinative morphology. Measured on a real Whisper transcript: `kytköksistä` → *kytköknen*, `pistät` → *pisttää*, `trollitehtaat` → *trollitehtas*, `haukut` → *haukua* — all garbage. With omorfi the same tokens lemmatize to `kytkös`, `pistää`, `trollitehdas`, `haukkua`, and every token additionally gets full UD morphological features (`Case`, `Mood`, `Person`, `Tense`, …) via `token.set_morph`. Better lemmas flow into everything lemma-fed: BoW, TF-IDF, keywords, theses, KMeans topics, and the shamanic raw-roots chant.
- **How to enable.** Uncomment `omorfi` in `requirements.txt` (pure Python since omorfi 0.10 — its only dependency is `pyhfst`, so it installs on Windows too), re-install, then run `omorfi-download` from the repo root (~130 MB of `*.hfst` automata, unpacked into the CWD and gitignored). `cell_model` probes `omorfi_recased.describe.hfst` first (handles sentence-initial capitals: `Mitä` → `mikä`), then `omorfi.describe.hfst`.
- **Hybrid disambiguation.** The pip omorfi ships no contextual disambiguation, so the component filters the analysis set by the spaCy tagger's UPOS and takes the lowest-weight match; **when no analysis agrees with the tagger, the token is left untouched** (dictionary and tagger disagree → trust spaCy). Compound lemmas arrive in parts and are joined, dropping inner hyphens unless the surface form itself is hyphenated (`trolli`+`tehdas` → `trollitehdas`, `Itä-Suomi` keeps its hyphen).
- **Soft degradation.** Missing package, missing automata, or a load failure → one info line and the stock spaCy behaviour. The multilingual diagnostic pass benefits automatically (it goes through the same `get_nlp()` cache), so Finnish paragraphs inside a non-Finnish corpus get the upgrade too.
- **Measured cost & coverage.** 100% lexicon coverage on the test transcript (colloquial spoken Finnish), ~1 ms/token before the per-surface-form `lru_cache`; automaton load ~2 s once per model load.
- **Known limits.** Same-UPOS homonyms resolve by dictionary weight, which can pick the wrong reading (`sinä` → the essive-of-`se` reading — harmless in practice, pronouns are stopwords); colloquial pronouns lemmatize to colloquial stems (`sun` → `sä`, where spaCy normalizes to `sinä`). The Finnish prophecy templates in the shamanic layer intentionally **keep** their nominal-prefix workarounds (`paikan {loc}`): proper names are exactly where omorfi's lexicon coverage is weakest, and a wrong nominative in a prophecy reads worse than a safe prefix form.
- `generate_report.py` extended to match: the pipeline-components pattern gained `omorfi_lemmas`, the project-identifiers pattern gained `omorfi-download` / `omorfi` / `pyhfst` / `OMORFI_MODEL_CANDIDATES`, and the ASCII-filename pattern now accepts the `.hfst` extension and multi-dot stems (`omorfi_recased.describe.hfst`), so NVDA does not read them with the document-default Russian voice.

### Renamed: `notebooklm_report.md` → `gemini_notebook_report.md`

Google renamed NotebookLM to Gemini Notebook (2026-07-16); `generate_md.py`'s output artefact and all README references follow. Re-run `generate_md.py` to produce the new filename — existing copies on disk under the old name are neither read nor deleted.

---

## v1.4.0 — ElevenLabs audio dispatcher (and a documented detection gap)

**Theme.** A new optional script, `shamanic_voice.py`, turns the four `shamanic_ai.py` narrative artefacts into spoken `.mp3` audio via ElevenLabs. It replaces an untracked Discord-bot skeleton (`lumi_dispatcher.py`) with a plain run-once script in the same shape as the other shamanic modules. This release also documents — and deliberately declines to build — a loanword-origin detection layer. Optional-layer plus documentation change: the notebook, the analysis pipeline, and the HTML/Markdown/diagnostic reports are untouched. Minor bump.

### New: `shamanic_voice.py` (optional, paid + third-party)

- Reads `katla_entity_monologue.txt`, `vieno_echoes_chant.txt`, `lumi_final_report.txt`, and `sami_energetic_spark.txt` from `audio_scripts/` and POSTs each body to the ElevenLabs `eleven_multilingual_v2` model, writing a sibling `.mp3`. The model auto-detects the spoken language, so no corpus-language parameter is passed.
- Run-once and non-interactive: it logs each success/failure to the console and exits. No Discord, no server, no background thread, no emoji — consistent with the project's screen-reader-clean stdout rule (the old bot skeleton used emoji in every message).
- Follows the same three-valued contract as the rituals (see v1.3.1): a synthesized voice is counted; a missing artefact / empty body / missing voice ID is skipped; an HTTP or synthesis error is raised and caught **per voice**, so one failure does not abort the others. An up-front critical guard reports a missing `audio_scripts/` directory, a missing `ELEVENLABS_API_KEY`, or a missing `voices` mapping.
- New config key **`voices`** maps `katla` / `vieno` / `lumi` / `sami` to ElevenLabs voice IDs (mirrored in `config.example.json` / `.ini`). A voice with an empty or missing ID is skipped. Console strings are localized across all six languages via a new `dispatcher.*` block in `dictionaries/{lang}/reports.yaml` (it is an operator-facing console script, so it lives with `generate_report` / `generate_md`, not in `shamanic.yaml`).
- **No new dependencies:** `requests` and `python-dotenv` were already required; the dropped `discord.py` is gone. `ELEVENLABS_API_KEY` lives in the same gitignored `golden_key.env` as `OPENAI_API_KEY`.

**Privacy & cost.** Like `shamanic_ai.py` with OpenAI, this sends artefact text to a third-party service (ElevenLabs), which is a **paid** API — the content leaves your machine. Do not run it on material you cannot share externally.

### Considered and rejected: loanword-origin detection

A proposed extra detection layer would have spotted explicit borrowing-origin markers in the text (`греч.`, `łac.`, `z niemieckiego`, `имеет греческое происхождение`), stripped the cited foreign material of unsupported languages from the analysis, and ISO-tagged supported ones. It is **not implementable** within this pipeline's paradigm and has been documented as a known limitation instead (`CLAUDE.md`, the `cell_para` section):

- **Markers are an open class** — abbreviation, inflected adjective, prepositional phrase, full verbal description — i.e. relation extraction, not a fixed regex list.
- **No delimitable block** — the etymology is woven into ordinary prose (e.g. *«Слово фразеология имеет греческое происхождение: фразис означает …»*); there is nothing discrete to cut.
- **The cited word is usually transliterated into the host script** (`фразис`, not `φράσις`), so tagging it with the donor language's ISO code would *mislead* the screen reader rather than help it.

The tractable subset — fragments written in an actual foreign *script* — is already covered by the per-fragment `lingua` pass in `cell_para` / `cell_foreign_resegment`. Reliable detection of the rest would require a trained model or an LLM, disproportionate to an otherwise deterministic, offline pipeline.

---

## v1.3.1 — the shamanic layer can no longer lie about success

**Theme.** A robustness hardening of the optional shamanic post-processing layer plus one stray hardcoded string. v1.1.5 fixed the *cause* of one silent-failure case (a slug mismatch that pointed the loaders at a non-existent directory), but the *design* that let the failure pass silently survived: every `ritual_*` bailed with an early `if not <file>.exists(): return`, and the `__main__` printed `[ZAKOŃCZONO] … wszystkie artefakty gotowe` regardless of whether anything had actually been written. This release closes that design gap. Pure shamanic-layer change — the notebook, the HTML/Markdown/diagnostic reports, and all analysis behaviour are untouched. No config or dependency change. Patch bump.

### Rituals now report a three-valued status

Each `ritual_*` in both `shamanic_pipeline.py` and `shamanic_ai.py` now returns a status instead of `None`:

- **produced** → `return True` after the artefact is written;
- **legitimately skipped** → `return False` silently, when a *conditionally-written* input is simply absent;
- **failed** → `raise RuntimeError(...)`, when an input is present but unusable (empty/corrupted), or when a required-but-missing file means the notebook never ran.

The skip-vs-fail line is drawn by which exports the notebook guarantees. `sentences.csv` and `paragraphs.csv` are written by **every** successful export-cell run; `theses.csv`, `keywords_tfidf.csv`, `paragraphs_with_topics.csv`, `topic_keywords.json`, `entities.csv`, and `sentiment.csv` are written **conditionally** (empty result, a non-`_lg` model with no vectors, or sentiment switched off). So a missing *conditional* input is a valid partial pipeline (`return False`); a missing `paragraphs.csv`/`sentences.csv` means the export cell never ran (`raise`).

### No more false `[ZAKOŃCZONO]`

Both `__main__` blocks were rewritten:

- A **critical guard** at the top raises immediately if the export directory or `paragraphs.csv` is missing (`shamanic_ai.py` checks the directory) — the operator gets *"the notebook or its export cell was probably not executed"* instead of a cheerful all-clear over an empty `audio_scripts/`.
- Rituals run through a **per-ritual `try/except` loop**, so one faulty input no longer aborts the independent rituals after it; each failure is reported on its own line.
- The **final message is classified**: any failure → `*.done_with_errors` ("not all rituals succeeded — something went wrong"); zero artefacts produced but no failure → `*.warn_nothing_produced`; otherwise the original `*.done`.

Two message flavours carry the distinction the user actually needs: *probable non-execution of the notebook / its export cell* (`*.err_no_notebook_output`, `*.err_no_export_dir`) versus *something went wrong with a file that is present* (`*.err_faulty_input`).

### Prophecies generate from paragraphs alone

`ritual_etymological_prophesy` used to skip silently when `entities.csv` was absent. But the prophecy templates already fall back to placeholder `loc`/`per`/`org` via `pick()` — and even *with* `entities.csv` present, every slot lands on a fallback whenever none of the sampled paragraphs happened to carry an entity. So entities were never actually required: as long as `paragraphs.csv` parses, the book of prophecies can be cast. The ritual now treats `entities.csv` as a genuinely optional ornament (read it if present, otherwise an empty entity set → all-fallback templates) and produces `prophecies.txt` regardless.

### AI layer: Lumi/Sami stay silent, Vieno now warns

In `shamanic_ai.py`, Lumi and Sami keep their **silent** `return` when `prophecies.txt` (from the local pipeline) or Lumi's report is absent — that just means the local pipeline was not run first, which is not an error. But Vieno's non-sentiment branch, which previously returned silently when it found fewer than 5 raw sentences, now **raises a warning** (`ai.warn_vieno_too_few_sentences`) — a thin or truncated `sentences.csv` is a signal worth surfacing, not swallowing. The warning is raised *before* the OpenAI call, so it costs nothing.

### Localization: the last hardcoded ritual string

`ritual_oracle` wrote the TTS pause marker as a hardcoded Polish `[PAUZA 1.5s]` regardless of corpus language. It now comes from the new `oracle.pause` key (`[PAUSE 1.5s]` / `[ПАУЗА 1.5с]` / `[TAUKO 1.5s]` / `[HLÉ 1.5s]` / `[PAUSA 1.5s]`), localized like every other artefact-body string by `t(corpus_lang, …)`. All the new operator-facing keys (`warn_ritual_failed`, `done_with_errors`, `warn_nothing_produced`, `err_no_notebook_output`, `err_no_export_dir`, `err_faulty_input`, `warn_vieno_too_few_sentences`) are added to all six `dictionaries/{lang}/shamanic.yaml` bundles; `fi`/`is`/`it` remain drafted-but-unreviewed per the standing note.

### Documentation

`CLAUDE.md` gains a "Failure-handling contract" paragraph in the shamanic-layer section documenting the three-valued status, the guaranteed-vs-conditional export split, and the message classification.

**Upgrade.** Pull the new tag and re-run `shamanic_pipeline.py` (and `shamanic_ai.py` if you use it). No notebook re-execution, config, or dependency change required.

### Distribution

Source-only patch release. The GitHub-generated source-code asset attached to the tag is the canonical artefact.

---

## v1.3.0 — optional sentiment analysis as a shamanic feed

**Theme.** Sentiment analysis returns to the pipeline, redesigned. The original `cell_sentiment` was dropped back in `e5ae27c`: it crashed at runtime (a tokenizer-dependency problem), and even working it presented a tweet-trained model's shaky verdicts directly to the screen-reader user. The reanimated version inverts that: it is **opt-in and off by default**, it never shows a verdict to the user, and its only purpose is to feed the optional shamanic layer. Fully backward-compatible — with the flag off (the default) nothing changes — so this is a minor bump.

### New: optional `cell_sentiment` (off by default)

Gated by `enable_sentiment` in `config.json` (default `false`). When on, it scores **each paragraph** (not each document, as the old cell did — the corpus is now joined and re-segmented into paragraphs) with `cardiffnlp/twitter-xlm-roberta-base-sentiment`, and writes **raw, unfiltered** rows to `sentiment.csv` (`para_id`, `label`, `score`, `lang`) — no confidence floor, no outlier exclusion. On any load failure it prints a warning and skips: **no English-model fallback**, `sentiment.csv` is simply not written, and the rest of the pipeline is unchanged. The cell is excluded from `analysis_report.html` (it is feed, not a user-facing result). The notebook is now 42 cells (21 code + 21 markdown).

### New consumers in the shamanic layer

- **`ritual_emotional_undertow`** (`shamanic_pipeline.py`, non-LLM) → `emotional_undertow.txt`: a per-paragraph "mood tide" (localized mood words, in reading order) plus a balance summary. Produced only when `sentiment.csv` exists.
- **Vieno branch** (`shamanic_ai.py`, LLM): when `sentiment.csv` exists, Vieno's chant is built on the text's **emotional arc** instead of five raw sentences. To respect the gpt-4o token-per-minute limit, long corpora are downsampled to ≤ 40 ordered segments (a 2579-paragraph book drops a ~32k-token request to ~1.4k); short corpora (≤ 150 paragraphs) get the full raw rows. Without `sentiment.csv`, Vieno is byte-identical to before.

### Dependencies

The sentiment model needs **five** packages, all commented out in `requirements.txt` by default (mirroring the OCR/Icelandic blocks): `transformers`, `torch`, `sentencepiece`, `protobuf`, `tiktoken`. The last three are all required at once to build the XLM-RoBERTa SentencePiece tokenizer (the model ships no `tokenizer.json`) — missing `sentencepiece`/`protobuf` raises `Error parsing line b'\x0e' ...`, missing `tiktoken` raises `tiktoken is required to read a tiktoken file`. `_silence_hf_progress()` now also quiets the `huggingface_hub` "unauthenticated requests" warning.

**Performance caveat.** On CPU the sentiment pass is heavy — empirically comparable to running local Whisper speech-to-text on CPU. On older or thermally-constrained machines this sustained full-load work can strain the processor; it is opt-in for exactly this reason.

### Documentation

All six READMEs document the optional sentiment feature (the `enable_sentiment` flag, the dependency block, and the two consuming rituals). `CLAUDE.md` gains a "Sentiment as optional shamanic feed" section.

---

## v1.2.0 — jupytext editing workflow, reader-mode report truncation, and a structured diagnostic report

**Theme.** Three independent improvements plus one real bug fix. The developer workflow for editing the notebook moves from fragile one-shot patch scripts to a jupytext pairing; the reader-facing HTML report stops dumping hundreds of kilobytes of per-document diagnostics; and a new standalone script produces a navigable, screen-reader-first diagnostic report from the CSV/JSON exports. Backward-compatible — no config or output-name changes — so this is a minor bump, not a hotfix.

### Bug fix: `cell_para` crashed on large corpora (`E088`)

`cell_para` fed the entire corpus into `nlp()` in one call. spaCy caps a single document at `nlp.max_length` (default 1,000,000 characters; the parser/NER need ~1 GB of temporary memory per 100k chars), so any book-length corpus raised `ValueError [E088]`. The cell now splits the text into chunks below the limit **at word boundaries** and runs `nlp()` per chunk, collecting sentences — keeping peak memory bounded instead of raising the limit (which would have tried to allocate many gigabytes). Short corpora pass through in a single chunk, unchanged.

### Notebook editing moved to a jupytext pairing

The `.claude_patches/` OLD→NEW string-replacement patch scripts are retired. They were not reusable, broke whenever a cell's source changed, and keyed cells by descriptive IDs the notebook had silently lost. The notebook is now **paired with `accessible_text_analyst.py`** (`py:percent`) via jupytext; the pairing lives in the notebook's own metadata (`metadata.jupytext.formats`) so it survives clone and nbstripout. Every cell carries a stable anchor in both `metadata.id` and `metadata.tags` (`cell_corpus` … `cell_qa_rag`, `md_intro` …), both preserved by nbstripout. The `.py` is **committed** for clean reviewable diffs alongside the output-stripped `.ipynb`; a local `pre-commit` hook runs `jupytext --sync` so the two never drift. `jupytext` is now a tooling dependency in `requirements.txt`.

### Reader-mode report truncation (`generate_report.py`)

In reader mode (`remove_noise: true`) the report previously **deleted** the lemmatization and POS sections wholesale while still dumping the full tokenization, stop-word, and NER per-document loops — hundreds of kilobytes of monotone text with no landmarks for a screen reader. It now **truncates instead of deletes**: each per-document loop (`cell_tok` / `cell_stop` / `cell_lemma` / `cell_pos` / `cell_ner`) is cut to the first 5 `Документ N` blocks **per section**, with the rest summarised by the notebook's own formula `... и ещё N документ(ов) (показаны первые 5)`; long TF-IDF/RAG ranking tables are cut to the top 10 rows; and the pseudographic POS histogram bars (`####…`) are stripped (the count already carries the information). On a ~1.2 MB book corpus the report dropped from ~800 KB to ~70 KB, lemmatization/POS are back (shortened, with diagnostic value), and the truncation formulas double as orientation landmarks.

### New: `generate_diagnostic.py` — structured diagnostic report

A third report generator, independent of `generate_report.py` and the shamanic layer. It reads **only** the CSV/JSON exports and emits `diagnostic_report.html`: a `<nav>` table of contents plus sections (each with its own heading and lists) for an overview, topics with their member paragraphs, theses ranked by score, named entities grouped by type with frequency counts, and top keywords. Because the notebook does not export a per-paragraph linguistic breakdown (`sentences.csv` / `entities.csv` carry no `para_id`), the report is organised around what the exports actually contain. Structural labels are localized via the new `dictionaries/{lang}/diagnostic.yaml` (all six languages; `fi`/`is`/`it` drafted-but-unreviewed per the standing note); `<html lang="ui_lang">`; corpus fragments get `<span lang="corpus_lang">` (only when it differs from `ui_lang`), NER labels always `<span lang="en">`.

### Documentation

All six READMEs document `generate_diagnostic.py` (project contents, the "Running" step, the output table, and the repository-layout tree). `CLAUDE.md` gains the jupytext editing workflow, the updated `REMOVE_NOISE` behaviour, and a diagnostic-report section.

**Upgrade.** Pull the new tag. For the `cell_para` fix, re-execute the notebook (mandatory for large corpora that previously crashed) and re-run `generate_report.py`. `pip install -r requirements.txt` to pick up `jupytext`. Run the new `python generate_diagnostic.py` against an export directory whenever you want the structured view. No config change required.

### Distribution

Source-only minor release. The GitHub-generated source-code asset attached to the tag is the canonical artefact.

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
