# Release notes

All release entries are appended in reverse-chronological order. On GitHub, the latest entry is copied verbatim into the release body when a tag is pushed.

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
