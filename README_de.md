# Accessible Text Analyst

Eine mehrsprachige NLP-Pipeline, entworfen für **Barrierefreiheit mit Screenreadern** (NVDA, JAWS, VoiceOver, Sprachausgabe). Der gesamte Code, die Konsolenausgabe und die Berichte sind so gestaltet, dass assistive Technik sie sauber auswerten kann: keine ANSI-Farben, keine Emoji, keine Fortschrittsbalken, keine Rahmenzeichen.

> **Andere Sprachen:** [English](README.md) · [polski](README_pl.md) · [русский](README_ru.md) · [suomi](README_fi.md) · [íslenska](README_is.md) · [italiano](README_it.md) · [español](README_es.md) · [français](README_fr.md)

> **Stand der Übersetzung (v1.0).** Übersetzt wurde nur das README. Die Erzählung im Jupyter-Notebook, die gesamte Konsolenausgabe, `CLAUDE.md` und die Kommentare im Code bleiben in ihren Originalsprachen (überwiegend Russisch, Polnisch in den Patches und in der schamanischen Schicht). Ihre Übersetzung ist bewusst für v1.1 vorgesehen — siehe `release_notes.md`.

## Inhalt des Projekts

- `accessible_text_analyst.ipynb` — ein Jupyter-Notebook mit der vollständigen Analysepipeline (42 Zellen: 21 Code + 21 Markdown; die Erzählung im Notebook ist russisch). Es schreibt zwei barrierefreie Artefakte (`accessible_text.html`, `accessible_text.docx`), in denen jeder Absatz und jeder fremdsprachige Satz ein eigenes `lang`-Attribut trägt, sodass Screenreader und TTS-Engines die Stimme automatisch wechseln — auch offline.
- `generate_report.py` — ein Nachbearbeitungsskript, das das ausgeführte Notebook in eine einzige barrierefreie HTML-Datei (`analysis_report.html`) verwandelt. Es umschließt Fragmente eines fremdsprachigen Korpus mit `<span lang="target_lang">` und setzt unabhängig von der Korpussprache fest `<span lang="en">` um technische englische Inhalte (POS-Tags, NER-Labels, Modellbezeichner von spaCy/Hugging Face, ASCII-Dateinamen). Inline-Code und Codeblöcke in der Erzählung werden pauschal mit `lang="en"` ausgezeichnet. Im Lesemodus (`remove_noise: true`) kürzt es die Diagnoseschleifen des Notebooks pro Dokument auf die ersten paar Dokumente, statt Hunderte davon auszugeben.
- `run_all.py` — ein Starter für die ganze kostenlose lokale Kette: Er registriert den Jupyter-Kernel `analyst_env`, falls er fehlt, führt das Notebook ohne Oberfläche aus (ohne die interaktive Fragezelle) und speichert seine Ausgaben in der `.ipynb`, dann startet er `generate_report.py`, `shamanic_pipeline.py` und, bei einem finnischen Korpus, den `scan` für das Buch des Ungesagten. Einen kostenpflichtigen Schritt startet er nie (LLM-Rituale, ElevenLabs-Stimmen, `draft`/`fill` des Buchs).
- `generate_diagnostic.py` — ein unabhängiger Generator eines vollständigen **Diagnoseberichts** (`diagnostic_report.html`), der direkt aus den CSV/JSON-Exporten des Notebooks gebaut wird (nicht aus der Ausgabe von `generate_report.py`). Eine navigierbare, auf Screenreader ausgerichtete Struktur: ein Inhaltsverzeichnis in `<nav>` plus Abschnitte — jeder mit eigener Überschrift und Listen — für einen Überblick, Themen mit ihren Absätzen, Thesen, benannte Entitäten nach Typ und die wichtigsten Schlüsselwörter. Strukturelle Beschriftungen folgen `ui_lang`; Korpusfragmente bekommen `<span lang="…">`, NER-Labels `<span lang="en">`.
- `generate_md.py` — wandelt den erzeugten `analysis_report.html` in `gemini_notebook_report.md` für Gemini Notebook (früher NotebookLM) um. Die Barrierefreiheits-Spans werden entfernt, weil Gemini Notebook sie nicht verwertet.
- `shamanic_pipeline.py` *(optional)* — ein Nachbearbeiter ohne LLM, der die CSV/JSON-Exporte des Notebooks in rituelle Textartefakte verwandelt (`oracle_script.txt`, `lore_fragments/`, `raw_roots_chant.txt`, `prophecies.txt` und — wenn die optionale Stimmungsanalyse eingeschaltet ist — `emotional_undertow.txt`), vollständig lokalisiert in allen neun unterstützten Sprachen.
- `shamanic_ai.py` *(optional, LLM-gestützt)* — ruft ein LLM auf (standardmäßig OpenAI; OpenRouter oder jeder OpenAI-kompatible Endpunkt über `llm_provider`), um auf denselben Exporten vier erzählende Stimmen zu erzeugen (`Katla`, `Vieno`, `Lumi`, `Sami`). Ist die optionale `sentiment.csv` vorhanden, baut Vieno ihren Gesang auf dem emotionalen Bogen des Textes statt auf Rohsätzen auf. Benötigt den Schlüssel des gewählten Anbieters in `golden_key.env`.
- `shamanic_voice.py` *(optional, benötigt ElevenLabs)* — ein eigenständiger, einmal laufender Dispatcher, der die vier von `shamanic_ai.py` erzeugten Erzählartefakte über die ElevenLabs-API zu `.mp3`-Audio synthetisiert, jeden Erfolg oder Fehlschlag in der Konsole meldet und sich beendet (kein Bot, kein Server). Braucht `ELEVENLABS_API_KEY` in `golden_key.env` und eine Zuordnung `voices` in der Konfiguration.
- `shamanic_locale.py` — das Lokalisierungspaket für beide schamanischen Skripte (Vorlagen, Kopfzeilen und Lumis Ersatztexte in allen neun unterstützten Sprachen).
- `ksiega_niedomowien.py` *(optional, nur Finnisch, agentengestützt)* — das Buch des Ungesagten (*Sanomattomien kirja*): verwandelt `raw_roots_chant.txt` in ein schrittweise wachsendes, rätselhaftes Tagebuch, dessen Lücken ein blindes Modell nicht erraten konnte. Es ist der deterministische Helfer für den Skill in `skills/ksiega-niedomowien/SKILL.md`; seine Konsolenausgabe folgt `ui_lang`.

## Was die Pipeline tut

1. Lädt Text aus einer Datei (`.pdf`, `.txt`, `.docx`, `.md`, `.html` oder Bilder: `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`, `.webp`) oder von einer URL — und entfernt dabei wiederholte Kopf- und Fußzeilen, Seitenleisten, Abschnitte wie „Ähnliche Artikel“ und vergleichbare Textbausteine. Gescannte PDFs und Bildeingaben fallen auf OCR zurück: Jede Sprache aus `corpus_languages` liest die Seite mit ihrer eigenen Engine (der in Windows 10/11 eingebauten OCR oder Tesseract für eine Sprache, die Windows nicht hat — derzeit Isländisch), RapidOCR liest sie zur Sicherheit noch einmal, und ein Wörterbuch jeder Sprache wählt aus allen Lesungen die Wörterbuchformen aus.
2. Bestimmt die Sprache jedes Wortes aus den Wörterbüchern der in `corpus_languages` aufgeführten Sprachen (siehe **Sprache jedes Wortes**): Die Basissprache steuert die spaCy-Pipeline, fremdsprachige Zitate und Namen werden zu Sprachabschnitten.
3. Führt spaCy einmal pro Textsegment aus: Das Modell der Basissprache verarbeitet den Basistext zusammen mit eingebetteten fremdsprachigen Abschnitten, und jeder fremdsprachige Block wird vom Modell seiner eigenen Sprache verarbeitet, das bei Bedarf über `get_nlp()` geladen wird (umhüllt von `functools.lru_cache(maxsize=2)`, sodass höchstens zwei Modelle zwischengespeichert sind). Es gibt keinen Durchgang zur Neusegmentierung und keinen zweiten mehrsprachigen Durchgang.
4. Tokenisierung → Filtern von Stoppwörtern → Lemmatisierung → POS-Tagging → NER, wobei jedes Token vom Modell seiner eigenen Sprache analysiert wird.
5. Vektordarstellungen: Bag of Words, TF-IDF + Suche mit automatisch gebildeter Anfrage und Kosinus-Ranking.
6. Struktur: Sätze → Absätze (je 3–6 Sätze) → Thesen (der beste Satz pro Absatz). Jeder Satz trägt seine Sprache und seine eingebetteten fremdsprachigen Abschnitte; jeder Absatz trägt seine vorherrschende Sprache.
7. Themenmodellierung mit KMeans über die spaCy-Vektoren der Absätze.
8. *(Optional, standardmäßig aus)* Stimmungsbewertung pro Absatz mit `cardiffnlp/twitter-xlm-roberta-base-sentiment`, geschrieben nach `sentiment.csv`. Das Ergebnis wird dem Nutzer nie gezeigt — es dient nur als Futter für die schamanische Schicht. Siehe **Konfiguration** (`enable_sentiment`).
9. CSV/JSON-Export + ein textueller Zusammenfassungsbericht + ein barrierefrei ausgezeichneter HTML- und DOCX-Export + ein globaler HTML-Bericht (`analysis_report.html`).

## Unterstützte Sprachen

| Code | Sprache    | spaCy-Modell           | NER / Vektoren |
|------|------------|------------------------|----------------|
| pl   | Polnisch   | `pl_core_news_lg`      | spaCy          |
| ru   | Russisch   | `ru_core_news_lg`      | spaCy          |
| en   | Englisch   | `en_core_web_lg`       | spaCy          |
| it   | Italienisch| `it_core_news_lg`      | spaCy          |
| de   | Deutsch    | `de_core_news_lg`      | spaCy          |
| es   | Spanisch   | `es_core_news_lg`      | spaCy          |
| fr   | Französisch| `fr_core_news_lg`      | spaCy          |
| fi   | Finnisch   | `fi_core_news_lg`      | spaCy          |
| is   | Isländisch | `spacy.blank("is")` + Hugging Face | `mideind/IceBERT` (Vektoren), `grammatek/icelandic-ner-bert` (NER) |

Für Isländisch gibt es kein vollständiges spaCy-Modell, daher werden zwei Hugging-Face-Modelle in eine leere Pipeline eingebunden. Der erste Download braucht ~1,3 GB Speicherplatz und eine Internetverbindung; spätere Läufe verwenden den HF-Cache.

**Optionale Verbesserung der finnischen Morphologie (omorfi).** Der statistische Lemmatisierer in `fi_core_news_lg` kommt mit der agglutinierenden finnischen Morphologie schlecht zurecht — er erzeugt regelmäßig unbrauchbare Lemmata wie *kytköknen* oder *pisttää*. Ist das reine Python-Paket `omorfi` installiert und sind seine FST-Automaten heruntergeladen (siehe Installation, Schritt 5), hängt das Notebook eine Komponente `omorfi_lemmas` an, die Lemmata und morphologische UD-Merkmale durch Wörterbuchanalysen ersetzt, wo immer sie mit der Wortart des spaCy-Taggers übereinstimmen (`kytköksistä` → `kytkös`, `Euroopassa` → `Eurooppa`, `pistät` → `pistää`). Ohne das Paket oder die Automaten behält die Pipeline stillschweigend das normale Verhalten von spaCy bei.

## Sprache jedes Wortes

Du listest die Sprachen des Textes in `corpus_languages` auf (`config.json`; der alte Name `ocr_languages` wird weiterhin gelesen). Aus den Wörterbüchern dieser Sprachen bestimmt das Notebook:

1. **Basissprache** (`LANG`) — die Sprache, deren Wörterbuch den größten Anteil der Korpuswörter kennt (die Anteile werden ausgegeben). Sie steuert die Haupt-Pipeline von spaCy.
2. **Die Sprache jedes Wortes** (`odcinki_jezykowe.py`). Ein Wort, das das Basiswörterbuch nicht kennt, wohl aber eine andere aufgeführte Sprache, gehört zu dieser Sprache; ein Wort, das mehrere von ihnen kennen, geht an das kleinste Alphabet, das alle seine Buchstaben enthält — so wird ein englisches Wort nicht vom polnischen Wörterbuch vereinnahmt, das viele englische Formen kennt, während `Łódź` polnisch bleibt. Die Schrift ist eine Tatsache: Ein kyrillisches Wort in lateinischem Text bekommt eine kyrillische Sprache, auch wenn keine aufgeführt ist.
3. **Fremdsprachige Abschnitte** — mindestens zwei aufeinanderfolgende fremdsprachige Wörter einer Sprache innerhalb eines Satzes oder ein Wort mit Buchstaben, die dem Basisalphabet fehlen. Ein Abschnitt, der ganze Sätze umfasst, ist ein **Block** und wird von seinem eigenen spaCy-Modell verarbeitet (Sätze, NER, Lemmata). Ein Abschnitt innerhalb eines Satzes in der Basissprache ist ein **eingebetteter Abschnitt**: Der Satz bleibt beim Basismodell, und der Abschnitt bekommt seine Lemmata und POS-Tags vom Modell seiner eigenen Sprache.

Der Export trägt das Ergebnis: `<span lang="…">` in `accessible_text.html` und ein eigener `Run` mit `<w:lang>` in `accessible_text.docx` für jeden fremdsprachigen Satz und jeden eingebetteten Abschnitt, sodass ein Screenreader genau beim Zitat oder beim Namen die Stimme wechselt, nicht beim ganzen Satz. Alle Abschnitte stehen außerdem in `language_spans.csv`, und `sentences.csv` hat eine Spalte `lang`.

Wörterbücher: spaCy-Vektoren (eine endliche Liste von Wortformen) für Polnisch, Englisch, Russisch, Italienisch, Deutsch, Spanisch und Französisch; `omorfi` für Finnisch; BÍN (`islenska`) für Isländisch — dieselben Wörterbücher, die die OCR-Abstimmung verwendet. Mit einer einzigen Sprache in `corpus_languages` wird kein Wörterbuch geladen, und nur Wörter einer anderen Schrift werden ausgezeichnet. Ein fehlendes Wörterbuch hält den Lauf mit einer Meldung an, die die Abhilfe nennt.

**Welche Sprachen aufzuführen sind.** Gemessen an 20 finnischen Transkripten (55.000 Wörter), die viele polnische Namen erwähnen: Mit `["fi", "en"]` findet das Notebook 34 englische Abschnitte (Fachbegriffe und Zitate); mit `["fi", "pl", "en"]` findet es zusätzlich 57 polnische Abschnitte — polnische Namen und einige polnische Wendungen, die nun eine polnische statt einer finnischen Stimme liest — und kein englisches Wort geht ans Polnische. Daher:

- führe jede Sprache auf, deren **Zitate** im Text vorkommen;
- bei einem Text in einer Sprache, der **Namen** aus einer anderen erwähnt (polnische Namen in einem finnischen Text), füge die Sprache der Namen hinzu: Namen in ihrer Grundform und Namen mit Buchstaben, die dem Basisalphabet fehlen (`ł`, `ś`), werden dann von der Stimme ihrer eigenen Sprache gelesen. Ein Name, der nur mit Buchstaben des Basisalphabets gebeugt ist (`Kowalskille`), bleibt in jedem Fall in der Basissprache;
- führe keine Sprache auf, die im Text nicht vorkommt: Sie fügt nur falsche Kandidaten hinzu.

**Warum kein statistischer Detektor.** Bis ATA 1.x hat `lingua-language-detector` ganze Sätze klassifiziert. Auf denselben Transkripten markierte er 127 Sätze als fremdsprachig, fast alle zu Unrecht; die Schutzheuristiken, die nötig waren, um das zu unterdrücken, ließen 2 Sätze übrig und keines der englischen Zitate. ATA 2.0 hat ihn entfernt. Der globale Bericht (`generate_report.py`) zeichnet fremdsprachige Wörter in seiner russischen Erzählung mit denselben Wörterbüchern aus (die Sprachen aus `corpus_languages` plus Englisch).

## Voraussetzungen

- Python 3.12 oder neuer (die Abhängigkeiten sind mit Python 3.14 getestet).
- ~1,5 GB freier Speicherplatz für die spaCy-Modelle `_lg` (eines pro installierter Sprache). Rechne ~1,3 GB hinzu, wenn du die Unterstützung für Isländisch wählst (Hugging Face `transformers` + `torch` + IceBERT + icelandic-ner-bert). Die isländische NER liest das ganze Dokument in überlappenden Fenstern: etwa 4.000 Zeichen pro Sekunde auf der CPU, ein Buch (1 MB isländischer Text) dauert also einige Minuten.
- OCR-Unterstützung (optional): die Pakete `winrt-*` (unter 1 MB) plus, für jede Sprache in `corpus_languages`, das Windows-Sprachpaket mit optischer Zeichenerkennung (Einstellungen > Zeit und Sprache > Sprache und Region); `rapidocr` mit `onnxruntime` (seine Modelle, etwa 40 MB, werden beim ersten OCR-Aufruf heruntergeladen); für eine Sprache ohne Windows-Engine (derzeit Isländisch) `tesserocr` und das tessdata_best-Modell dieser Sprache im Ordner `tessdata` des Repos (Isländisch: https://github.com/tesseract-ocr/tessdata_best/raw/main/isl.traineddata, etwa 9,5 MB) plus das Wörterbuch `islenska` (~62 MB). OCR braucht kein `torch` mehr. Eine fehlende Engine oder ein fehlendes Wörterbuch hält den Lauf mit einer Meldung an, die die Abhilfe nennt. Isländisches Wörterbuch: The Database of Icelandic Morphology (BÍN), The Árni Magnússon Institute for Icelandic Studies, Autorin und Herausgeberin Kristín Bjarnadóttir, CC BY-SA 4.0.
- Rechne ~130 MB hinzu, wenn du die Verbesserung der finnischen Morphologie wählst (die FST-Automaten von `omorfi`, heruntergeladen mit `omorfi-download`).
- Eine Internetverbindung beim ersten Lauf (Modelldownloads).

## Einrichtung der Umgebung

Wähle eine der drei Varianten unten. Alle drei enden mit demselben `pip install -r requirements.txt` + Downloads der spaCy-Modelle.

### Variante A — lokales `venv` (empfohlen für den Alltag)

```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Das Verzeichnis `.venv/` steht in `.gitignore`. Fahre in der aktivierten venv mit **Installation** unten fort.

### Variante B — Anaconda / Miniconda

```bash
conda create -n accessible-text-analyst python=3.14
conda activate accessible-text-analyst
```

Fahre dann mit **Installation** unten fort. Das mitgelieferte `pip` von Anaconda funktioniert problemlos — für dieses Projekt gibt es keine Conda-spezifische Paketliste.

### Variante C — Google Colab (ohne lokale Installation)

Öffne ein neues Colab-Notebook und füge Folgendes in die erste Zelle ein. Das klont das Repo, installiert die Abhängigkeiten und lädt die benötigten spaCy-Modelle herunter.

```python
!git clone https://github.com/<your-fork>/accessible_text_analyst.git
%cd accessible_text_analyst
!pip install -r requirements.txt
!python -m spacy download en_core_web_lg
# Füge die Zeilen unten nur für die Sprachen hinzu, die du wirklich brauchst:
# !python -m spacy download pl_core_news_lg
# !python -m spacy download ru_core_news_lg
# !python -m spacy download it_core_news_lg
# !python -m spacy download fi_core_news_lg
# !python -m spacy download de_core_news_lg
# !python -m spacy download es_core_news_lg
# !python -m spacy download fr_core_news_lg
```

Lade dann deine `config.json` (oder `config.ini`) über den Bereich „Dateien“ hoch, setze `source_file` und führe das Notebook aus. Hinweis: Colab-Sitzungen sind flüchtig — heruntergeladene Modelle und Artefakte in `export_results/` verschwinden, wenn die Laufzeit neu vergeben wird. Für längere Analysen binde Google Drive ein und schreibe die Ausgabe dorthin.

## Installation

```bash
# 1. Python-Abhängigkeiten
pip install -r requirements.txt

# 2. spaCy-Modelle — installiere nur die Sprachen, die du wirklich brauchst.
# Die Varianten *_lg sind nötig, weil die Themenmodellierung von Wortvektoren abhängt.
python -m spacy download pl_core_news_lg
python -m spacy download ru_core_news_lg
python -m spacy download en_core_web_lg
python -m spacy download it_core_news_lg
python -m spacy download fi_core_news_lg
python -m spacy download de_core_news_lg
python -m spacy download es_core_news_lg
python -m spacy download fr_core_news_lg

# 3. (Optional) Unterstützung für Isländisch — entkommentiere `transformers` und `torch`
# in requirements.txt und führe `pip install -r requirements.txt` erneut aus.
# IceBERT und icelandic-ner-bert werden dann beim ersten Lauf von Hugging Face geholt.

# 4. (Optional) Stimmungsanalyse — entkommentiere `transformers`, `torch`,
# `sentencepiece`, `protobuf` und `tiktoken` in requirements.txt, wiederhole die
# Installation und setze "enable_sentiment": true in config.json. Das Modell
# (~1,1 GB) wird beim ersten Lauf von Hugging Face geholt und danach zwischengespeichert.
# Alle fünf Pakete werden zusammen gebraucht, um den XLM-RoBERTa-Tokenizer zu bauen.

# 5. (Optional) Verbesserung der finnischen Morphologie — entkommentiere `omorfi` in
# requirements.txt, wiederhole die Installation und lade dann die FST-Automaten herunter
# (~130 MB *.hfst-Dateien, entpackt ins Wurzelverzeichnis des Repos; sie sind in .gitignore).
# Führe es im Wurzelverzeichnis des Repos aus:
omorfi-download

# 6. (Optional) Vergleiche die installierten Versionen mit den Grenzen in
# requirements.txt und mit PyPI. Es warnt nur, es blockiert nie:
python audyt_zaleznosci.py
```

## Konfiguration

Kopiere die Beispielkonfiguration in eine lokale Datei. Sowohl `config.json` als auch `config.ini` werden akzeptiert — **der Dateiinhalt ist in beiden Fällen JSON**; die Endung `.ini` ist nur ein Entgegenkommen an nicht technisch versierte Windows-Nutzer, für die `.json` kein Standardprogramm hat.

```bash
# Eine wählen:
cp config.example.json config.json
cp config.example.ini  config.ini
```

`config.json` und `config.ini` stehen beide in `.gitignore`, sodass jeder Nutzer seine eigene lokale Kopie behält.

Inhalt:

```json
{
  "source_file": "C:/path/to/document.pdf",
  "custom_patterns": [],
  "remove_noise": true,
  "corpus_languages": ["en"],
  "enable_sentiment": false,
  "ui_lang": "",
  "lumi_katla_lines": null,
  "lumi_vieno_lines": null,
  "llm_provider": "",
  "llm_model": "",
  "llm_base_url": "",
  "kirja_llm_provider": "",
  "kirja_drafter_model": "",
  "kirja_filler_model": "",
  "voices": {
    "katla": "",
    "vieno": "",
    "lumi": "",
    "sami": ""
  }
}
```

| Schlüssel          | Typ             | Zweck |
|--------------------|-----------------|---------|
| `source_file`      | string          | Pfad zu einer Datei (`.pdf`, `.txt`, `.docx`, `.md`, `.html` oder ein Bild) **oder** eine URL (`http://`, `https://`). Eine leere Zeichenkette oder eine fehlende Datei führt zum eingebauten Beispielkorpus. |
| `custom_patterns`  | string[]        | Optionale reguläre Ausdrücke, die aus dem Rohtext entfernt werden (lebende Kolumnentitel, Fußzeilen, wiederkehrende Textbausteine). Beispiel: `["Editorial: .*", "Copyright \\d{4}"]`. |
| `remove_noise`     | boolean         | Schaltet `generate_report.py` zwischen dem Lesemodus (`true`, blendet Ladebalken von Hugging Face/torch und Tabellen zu Lemmatisierung/POS aus) und dem vollständigen Diagnosemodus (`false`) um. |
| `corpus_languages` | string[]        | Sprachen des TEXTES (Codes der Sprachpakete: `de`, `en`, `es`, `fi`, `fr`, `is`, `it`, `pl`, `ru`); der alte Name `ocr_languages` wird weiterhin gelesen. Ihre Wörterbücher wählen die Basissprache und die Sprache jedes Wortes (siehe **Sprache jedes Wortes**), und bei gescannten PDFs und Bildern liest jede von ihnen die Seite mit ihrer eigenen OCR-Engine. Führe nur die Sprachen auf, die im Text wirklich vorkommen: Eine überzählige Sprache verlangsamt die OCR und fügt falsche Kandidaten hinzu. Lateinische und kyrillische Schrift lassen sich mischen (`["fi", "ru"]`). |
| `enable_sentiment` | boolean         | Schaltet die optionale Stimmungsanalyse pro Absatz ein (standardmäßig `false`). Benötigt die auskommentierten Abhängigkeiten für die Stimmungsanalyse (siehe Installation, Schritt 4). Schreibt `sentiment.csv`; das Ergebnis wird dem Nutzer nie gezeigt, es speist nur die schamanische Schicht (das Ritual `emotional_undertow.txt` und Vienos Gesang). Bei jedem Ladefehler wird sie stillschweigend übersprungen — ohne Ersatz. |
| `ui_lang`          | string          | Sprache der Oberfläche für die Konsolenausgabe und das Attribut `<html lang>` des erzeugten Berichts (`pl` / `en` / `ru` / `fi` / `is` / `it` / `de` / `es` / `fr`). Leere Zeichenkette oder unbekannter Code → Rückfall auf `en`. Unabhängig von der Sprache des analysierten Korpus, die die Wörterbücher von `corpus_languages` bestimmen. |
| `lumi_katla_lines` | integer or null | Optionale Begrenzung des Ornaments für Lumis Depesche in `shamanic_ai.py`: wie viele nicht leere Zeilen von Katlas Monolog Lumi sieht. `null` oder fehlender Schlüssel = voller Inhalt; ganze Zahl N > 0 = die ersten N Zeilen. |
| `lumi_vieno_lines` | integer or null | Wie `lumi_katla_lines`, aber für Vienos Echogesang. |
| `voices`           | object          | Ordnet jeder schamanischen Stimme (`katla` / `vieno` / `lumi` / `sami`) eine ElevenLabs-Stimmen-ID zu, verwendet von `shamanic_voice.py`. Eine Stimme mit leerer oder fehlender ID wird übersprungen. Nur nötig, wenn du den Audio-Dispatcher startest. |
| `llm_provider` | string | LLM-Anbieter für `shamanic_ai.py` und das Buch: `openai` (Standard), `openrouter` oder `openai_compat`. Jeder Anbieter liest nur seinen eigenen Schlüssel aus `golden_key.env` — siehe *LLM-Anbieter und Schlüssel* unten. |
| `llm_model` | string | Modell für diesen Anbieter. Leer = das Standardmodell des Anbieters (`gpt-6.1-sol` / `openai/gpt-6.1-sol`); Pflicht für `openai_compat`. |
| `llm_base_url` | string | Adresse des Endpunkts, gelesen **nur** von `openai_compat` (z. B. `http://localhost:1234/v1`). Von `openai` und `openrouter` ignoriert, deren Adressen fest sind. |
| `kirja_llm_provider` | string | Optionaler abweichender Anbieter für das Buch (`ksiega_niedomowien.py draft` / `fill`). Leer = `llm_provider`. |
| `kirja_drafter_model` | string | Modell für `draft` (den API-Entwurfsschreiber des Buchs). Leer = das Standardmodell des Anbieters oder `llm_model`, wenn das Buch den globalen Anbieter verwendet. |
| `kirja_filler_model` | string | Modell für `fill` (den blinden Lückenfüller des Buchs). Gleicher Rückfall wie bei `kirja_drafter_model`. |

> **LLM-Anbieter und Schlüssel.** Ein Schlüssel ist an einen Host gebunden und wird nie anderswohin geschickt: `openai` → `OPENAI_API_KEY` → `api.openai.com`; `openrouter` → `OPENROUTER_API_KEY` → `openrouter.ai`; `openai_compat` → `LLM_COMPAT_API_KEY` → `llm_base_url`. Der Anbieter wird ausdrücklich gewählt und nie aus einer Adresse abgeleitet, sodass das Umlenken eines Skripts auf einen anderen Dienst weder den Schlüssel des ersten Dienstes preisgeben noch das andere Skript kaputtmachen kann. Der Schlüssel `kirja_filler_base_url` aus der Zeit vor v1.7.0 (der `OPENAI_API_KEY` an beliebige Adressen schickte) wird mit einer Migrationsmeldung abgelehnt. Bei OpenRouter tragen Modell-IDs ein Herstellerpräfix (`openai/gpt-4o`, `anthropic/claude-sonnet-5.5`), und in den Datenschutzeinstellungen des Kontos lassen sich Anbieter ausschließen, die mit deinen Prompts trainieren dürfen.

> **Stimmungsanalyse — CPU-Last.** Mit `enable_sentiment: true` ist der Durchgang pro Absatz auf der CPU rechenintensiv — grob vergleichbar mit lokaler Whisper-Spracherkennung auf der CPU. Auf älteren oder thermisch begrenzten Rechnern kann diese Dauerlast den Prozessor spürbar belasten; schalte sie bewusst ein, am besten auf einem Rechner mit GPU oder mit Reserven für längere Volllast.

> **`ui_lang` — Umfang der Lokalisierung.** Die Konsolenausgabe der eigenständigen Skripte (`generate_report.py`, `generate_md.py`, `generate_diagnostic.py`, `shamanic_pipeline.py`, `shamanic_ai.py`, `ksiega_niedomowien.py`) wird über `ui_lang` lokalisiert. Die **Ausgabe des Notebooks nicht** — sie ist fest russisch (nur der Dateiname der Thesen folgt der erkannten Korpussprache). Der `analysis_report.html` im Lesemodus behält die russische Erzählung des Notebooks (seine Wurzel ist `<html lang="ru">`); das vollständig nach `ui_lang` lokalisierte, für Nutzer bestimmte Artefakt ist **`diagnostic_report.html`**, erzeugt von `generate_diagnostic.py`. Die Übersetzungen in `fi` / `is` / `it` / `de` / `es` / `fr` sind Entwürfe und nicht geprüft — melde Unebenheiten bitte auf GitHub.

> **Windows-Pfade und reguläre Ausdrücke — wichtig.** Der Inhalt der Konfiguration ist JSON, und JSON hat keine Syntax für Rohzeichenketten. Ein einzelner Backslash maskiert das nächste Zeichen (`\U`, `\d`, `\n` sind besonders), daher erzeugt ein Windows-Pfad in der Form `"C:\Users\marek\doc.pdf"` einen JSON-Parsefehler. Zwei Arten, ihn richtig zu schreiben:
>
> - **Schrägstriche** (am einfachsten, funktioniert auch unter Windows): `"C:/Users/marek/doc.pdf"`.
> - **Doppelte Backslashes**: `"C:\\Users\\marek\\doc.pdf"`.
>
> Dieselbe Regel gilt für jeden regulären Ausdruck in `custom_patterns`: schreibe `"\\d{4}"`, nicht `"\d{4}"`; schreibe `"Copyright \\d{4}"`, nicht `"Copyright \d{4}"`. In JSON gibt es keine Rohzeichenkette der Form `r"…"`.

## Ausführung

Die nummerierten Skripte unten sind dafür gedacht, **der Reihe nach** ausgeführt zu werden: Jedes verwendet Artefakte, die der vorherige Schritt erzeugt hat.

### Abkürzung: die ganze lokale Kette (`run_all.py`)

```bash
# Notebook -> generate_report.py -> shamanic_pipeline.py -> Scan für das Buch (nur Finnisch)
python run_all.py
# die bereits im Notebook gespeicherten Ausgaben wiederverwenden
python run_all.py --skip-notebook
# vollständige Diagnose der Bibliothekswarnungen, unabhängig von der Konfiguration
python run_all.py --warnings-as-errors
```

Die Schritte 1, 2 und 4 unten sowie bei einem finnischen Korpus der `scan` für das Buch des Ungesagten mit einem Befehl. Führe es mit dem Python aus der `.venv` des Repos aus: Fehlt der Kernel `analyst_env`, wird er für diesen Interpreter registriert. Die Kette hält beim ersten fehlgeschlagenen Schritt an; der Exit-Code 3 bedeutet, dass die Quellenprüfung des Berichts abgelehnt hat (siehe Schritt 2). Das Notebook unterdrückt Bibliothekswarnungen absichtlich, damit sie nicht in den Analysebericht gelangen. `--warnings-as-errors` ist ein eigener Modus der vollständigen Diagnose: Er ignoriert `config.json` und schickt eine Kopie des Notebooks mit einem synthetischen Korpus durch jede Komponente (ein PDF mit Schriftreparatur und eine gescannte Seite für die OCR, jedes Eingabeformat und eine URL von einem lokalen Server, Stimmungsanalyse, Isländisch, omorfi). Er zeichnet jede Warnung auf, auch solche aus Code, der Ausnahmen abfängt, und gibt sie alle unter der Überschrift der Zelle aus, im Wortlaut der Bibliothek und mit der Stelle, an der sie ausgelöst wurden. Bekannte, harmlose Warnungen (`diagnostyka.ZNANE_OSTRZEZENIA`) bekommen eine eigene Zeile und zählen nicht. Der Modus braucht jede optionale Abhängigkeit aus `requirements.txt` und das Modell `fi_core_news_lg`, und eine Komponente, die nicht lädt, hält ihn mit einer Meldung an. Das Notebook und `export_results/` bleiben unverändert, und der Bericht und die späteren Schritte laufen nicht; Exit-Code 4 = neue Warnungen, 0 = keine. Der Rekorder deckt das Modul `warnings` im Prozess des Notebooks ab: Meldungen über `logging` (zum Beispiel von `transformers`) und Warnungen aus Kindprozessen liegen außerhalb. Ersetzt eine Bibliothek den Rekorder (zum Beispiel `logging.captureWarnings`), endet der Modus mit dem Code 1 statt mit einem falschen „sauber“; ebenso Strg+C, nachdem die bis dahin gesammelten Warnungen ausgegeben wurden. Führe ihn nach einem Update der Bibliotheken aus.

### 1. Notebook (Pflicht)

```bash
jupyter notebook accessible_text_analyst.ipynb
# (Cell → Run All)
# Ohne Oberfläche (CI): Zellen 0-39 über nbclient, ohne die interaktive cell_qa_rag
python -c "import nbformat as f; from nbclient import NotebookClient as C; nb=f.read('accessible_text_analyst.ipynb',4); c=C(nb,timeout=None); c.create_kernel_manager(); c.start_new_kernel(); c.start_new_kernel_client(); [c.execute_cell(x,i) for i,x in enumerate(nb.cells[:40])]; f.write(nb,'accessible_text_analyst.ipynb'); c.km.shutdown_kernel(now=True)"
```

Das ist eine sequenzielle Pipeline mit gemeinsamem globalem Zustand. **Ordne die Zellen nicht um und führe sie nicht außer der Reihe aus.** Das Notebook schreibt `export_results/<project>/sentences.csv`, `paragraphs.csv`, `theses.csv`, `keywords_tfidf.csv`, `paragraphs_with_topics.csv`, `topic_keywords.json`, `entities.csv`, `accessible_text.html`, `accessible_text.docx` und `theses.txt`.

### 2. HTML-Berichte (empfohlen)

```bash
python generate_report.py
# → export_results/<project>/analysis_report.html
```

`generate_report.py` liest die Zellausgaben direkt aus der `.ipynb`-Datei, daher muss der HTML-Bericht aus einem **frisch ausgeführten** Notebook erzeugt werden. `requirements.txt` führt `nbstripout` auf — ist es in der lokalen Git-Konfiguration aktiviert, werden die Notebook-Ausgaben beim Commit entfernt. Erzeuge den Bericht _vor_ dem Commit oder schalte nbstripout für deinen Arbeitsablauf ab.

**Quellenprüfung.** Bevor `generate_report.py` irgendetwas schreibt, prüft es, ob die Ausgaben des Notebooks zur `source_file` der Konfiguration gehören, und lehnt andernfalls ab (Exit-Code 3, nichts geschrieben). Drei Prüfungen: Der vom Notebook ausgegebene Quellpfad und Exportordner müssen zur Konfiguration passen, und der gespeicherte Lauf muss das Ende der Exportzelle erreicht haben; `paragraphs.csv` und `sentences.csv` dürfen nicht neuer sein als die `.ipynb` (sonst wurden die Ausgaben des letzten Laufs nie gespeichert — typisch, wenn das Notebook in VS Code ausgeführt und nicht gespeichert wurde); und die vom Notebook ausgegebenen Seitenanfänge müssen in der Quelldatei vorkommen (verglichen als Buchstabenstrom, sodass zusammengefügte Silbentrennung, entfernte Seitenzahlen und lebende Kolumnentitel keine Rolle spielen). Lässt sich der Inhalt nicht vergleichen — per OCR gelesene Scans, Bilder, URLs, eine verstümmelte Textebene im PDF —, entscheiden die ersten beiden Prüfungen, und die Konsole sagt das. Der Bericht vermerkt außerdem, ob omorfi am Lauf beteiligt war (`<meta name="ata-omorfi">`); das Buch des Ungesagten liest das.

Für eine strukturierte, vollständige **Diagnose**ansicht, die direkt aus den CSV/JSON-Exporten gebaut wird:

```bash
python generate_diagnostic.py
# → export_results/<project>/diagnostic_report.html
```

`generate_diagnostic.py` liest nur die exportierten CSV/JSON-Dateien, braucht also — anders als `generate_report.py` — kein frisch ausgeführtes Notebook, nur die Exporte, die das Notebook geschrieben hat. Das Ergebnis ist ein navigierbares Dokument (Inhaltsverzeichnis, Überschriften, Listen) mit Themen, Thesen, Entitäten nach Typ und den wichtigsten Schlüsselwörtern.

### 3. Markdown für Gemini Notebook (optional)

```bash
python generate_md.py
# → export_results/<project>/gemini_notebook_report.md
```

Das wandelt den HTML-Bericht in eine Markdown-Datei ohne die Barrierefreiheits-Spans um (Gemini Notebook — früher NotebookLM — verwertet `<span lang="…">` nicht). Führe es nur aus, wenn du den Bericht in Gemini Notebook einspeisen willst.

### 4. Schamanischer Nachbearbeiter ohne LLM (optional)

```bash
python shamanic_pipeline.py
# → export_results/<project>/audio_scripts/oracle_script.txt
#                                          /raw_roots_chant.txt
#                                          /prophecies.txt
#                                          /lore_fragments/intercepted_log_T*_P*.txt
#                                          /emotional_undertow.txt   # nur wenn sentiment.csv existiert
```

Erzeugt rituelle Textartefakte direkt aus den CSV/JSON-Exporten des Notebooks — kein LLM-Aufruf, kein Netz. Alle Texte stammen aus `shamanic_locale.py` und sind vollständig in allen neun unterstützten Sprachen lokalisiert. Ist die optionale `sentiment.csv` vorhanden, entsteht zusätzlich `emotional_undertow.txt` — „Gefühlsgezeiten“ pro Absatz und eine Bilanz; ohne sie wird nur dieses eine Ritual übersprungen.

### 5. Schamanischer LLM-Nachbearbeiter (optional, benötigt einen LLM-API-Schlüssel)

```bash
python shamanic_ai.py
# → export_results/<project>/audio_scripts/katla_entity_monologue.txt
#                                          /vieno_echoes_chant.txt
#                                          /lumi_final_report.txt
#                                          /sami_energetic_spark.txt
```

Dafür braucht es den Schlüssel des gewählten Anbieters (`llm_provider`, Standard `openai`). Lege im Wurzelverzeichnis des Projekts `golden_key.env` mit dem benötigten Schlüssel an:

```
OPENAI_API_KEY=sk-...          # llm_provider: openai (Standard)
OPENROUTER_API_KEY=sk-or-...   # llm_provider: openrouter
LLM_COMPAT_API_KEY=...         # llm_provider: openai_compat (llm_base_url)
```

`golden_key.env` passt auf `*.env` in `.gitignore` und wird daher nicht committet. Die vier Stimmen laufen nacheinander:

1. **Katla** verwandelt die Liste der Entitäten (`entities.csv`) in einen Monolog gefrorener Geister des Nordens.
2. **Vieno** singt über die Liste der Schlüsselwörter und Themen. Standardmäßig webt sie fünf Rohsätze aus dem Korpus als Echos einer fremden Dimension ein; ist die optionale `sentiment.csv` vorhanden, liest sie stattdessen den emotionalen Bogen des Textes (Stimmungen pro Absatz, bei langen Korpora so verdichtet, dass sie ins Tokenlimit des Modells passen) und lässt ihn die Dynamik des Gesangs formen.
3. **Lumi** liest `prophecies.txt` (Pflicht) sowie Katlas Monolog und Vienos Gesang (optionales Ornament) und verfasst die letzte Depesche. Lokalisierte Ersatztexte decken den Fall ab, dass Katla oder Vieno fehlen.
4. **Sami** liest Lumis Bericht und liefert eine energiegeladene Synthese mit einem Funken Hoffnung oder einem Aufruf zum Handeln.

### 6. Schamanischer Audio-Dispatcher (optional, benötigt ElevenLabs)

```bash
python shamanic_voice.py
# → export_results/<project>/audio_scripts/katla_entity_monologue.mp3
#                                          /vieno_echoes_chant.mp3
#                                          /lumi_final_report.mp3
#                                          /sami_energetic_spark.mp3
```

Ein eigenständiges, einmal laufendes Skript, das die vier von `shamanic_ai.py` erzeugten Erzählartefakte liest und jedes über das ElevenLabs-Modell `eleven_multilingual_v2` zu einer `.mp3` synthetisiert (es erkennt die gesprochene Sprache selbst, daher wird kein Sprachparameter übergeben). Es meldet jeden Erfolg oder Fehlschlag in der Konsole und beendet sich — kein Bot, kein Server, keine interaktive Sitzung. Es braucht zweierlei:

- `ELEVENLABS_API_KEY` in `golden_key.env` (derselben Datei, die die LLM-Schlüssel enthält).
- eine Zuordnung `voices` in `config.json` / `config.ini`, die jeder der Stimmen `katla`, `vieno`, `lumi`, `sami` eine ElevenLabs-Stimmen-ID zuweist. Eine Stimme mit leerer ID oder fehlendem Artefakt wird übersprungen (führe zuerst `shamanic_ai.py` aus); fällt eine Stimme aus, bricht das die anderen nicht ab.

> **Datenschutz und Kosten.** Wie `shamanic_ai.py` mit OpenAI schickt dieses Skript Artefakttext zur Synthese an einen Drittanbieter (ElevenLabs), und ElevenLabs ist eine **kostenpflichtige** API. Der Inhalt verlässt deinen Rechner — führe es nicht auf Material aus, das du nicht nach außen geben darfst.

### 7. Das Buch des Ungesagten (optional, nur Finnisch, agentengestützt)

```bash
python ksiega_niedomowien.py scan              # welche Ordner in export_results/ sich eignen
python ksiega_niedomowien.py scan --blocks     # dazu Blöcke erledigt / offen / übrig (langsam; automatisch mit --folder)
python ksiega_niedomowien.py status            # Fortschritt pro Ordner: Einträge, offensichtliche Blöcke, offene Pakete
python ksiega_niedomowien.py tidy              # durch einen neueren Eintrag desselben Blocks ersetzte Einträge (Vorschau; --apply räumt auf)
python ksiega_niedomowien.py prepare --folder <name> --limit 3
#   → export_results/_kirja_tyotila/<id>/packet.json
python ksiega_niedomowien.py draft <id>        # optional: Entwurf über die API + seal, bis zu 2 Wiederholungen
python ksiega_niedomowien.py seal <id>         # prüft draft.json, schreibt blind.json
python ksiega_niedomowien.py fill <id>         # optional: blinde Rateversuche über die API, dann judge
python ksiega_niedomowien.py judge <id>        # → export_results/Sanomattomien_kirja.md
# <id> = die von prepare ausgegebene Paket-ID, der Anfang des Ordnernamens oder der Pfad zum Paketordner
```

Ein Spiel auf Grundlage von `raw_roots_chant.txt`. Für jeden Block aus 3–6 aufeinanderfolgenden Wurzeln schreibt ein LLM einen nebligen finnischen Tagebucheintrag mit Lücken, deren Antworten wörtliche Ausschnitte des Quelltextes sind — sie müssen in **beiden** Dateien `accessible_text.html` und `accessible_text.docx` vorkommen, den zwei Fassungen der Referenzquelle. Ein separates, blindes Modell versucht dann, die Lücken allein aus dem Eintrag zu füllen; jede erratene Lücke gilt als offensichtlich, und ihr Fragment wird entfernt. Was bleibt — KATLA (das Warnsystem), die die Wurzeln liest, und VIENO (die schamanische Erzählerin) mit den ungesagten Lücken —, wird an `export_results/Sanomattomien_kirja.md` angehängt. Der Lösungsschlüssel kommt nach `Sanomattomien_kirja.avain.json` und der Zustand nach `Sanomattomien_kirja.tila.json`; ein erneuter Lauf dupliziert nie Einträge.

Das Skript ist die deterministische Hälfte (Filter, Blöcke, Referenzquelle, Prüfung, Bewertung, das Buch). Die kreative Hälfte — das Schreiben von `draft.json` — übernimmt entweder ein Agent nach `skills/ksiega-niedomowien/SKILL.md` oder ein API-Modell über `draft`.

**Eingangsfilter.** Zugelassen werden nur Unterordner von `export_results/` mit finnischem Namen, `<html lang="fi">`, finnischem Gesang und ohne Grammatikleck; alles andere wird mit Begründung abgelehnt. Die Zeile `roots.header` wird entfernt, wenn sie vorhanden ist. Die Prüfung auf ein *Grammatikleck* erkennt Korpora, die verarbeitet wurden, bevor omorfi eingeschaltet war (v1.5.0): Über die ganze `keywords_tfidf.csv` zählt sie gebeugte Formen, die die Lemmatisierung überstanden haben, plus unbrauchbare Lemmata von spaCy, und lehnt den Ordner oberhalb von 1,0 pro 100 Begriffe ab. Benötigt omorfi (Installation, Schritt 5). Hat der Ordner einen aktuellen `analysis_report.html`, sagt eine Ablehnung wegen Grammatiklecks, was der Bericht weiß: omorfi war am Lauf beteiligt (dann muss vielleicht die Engine selbst — die finnische Lemmakorrektur im Notebook — repariert werden; melde die Beispiele), omorfi fehlte (installiere es und führe das Notebook erneut aus) oder der Lauf hatte überhaupt keinen omorfi-Schritt. Ohne aktuellen Bericht sagt sie, dass das unbekannt ist.

**Warum nur Finnisch.** Das Spiel lebt von dem, was die Lemmatisierung ungesagt lässt, ergibt also nur dort Sinn, wo das Zurückführen eines Wortes auf sein Lemma echte Bedeutung entfernt. Finnisch ist agglutinierend: Was Polnisch oder Russisch teilweise mit eigenen Präpositionen ausdrücken und Englisch überwiegend mit Wortstellung und Funktionswörtern, packt das Finnische ins Wort selbst — fünfzehn Fälle (`talossa` „im Haus“, `talosta` „aus dem Haus“, `taloon` „ins Haus“, `talolle` „zum Haus“, `talotta` „ohne Haus“), Possessivsuffixe (`taloni` „mein Haus“, `talonsa` „sein/ihr Haus“), Klitika (`-ko` Frage, `-kin` „auch“, `-han` Betonung) und Verbformen, die Person, Tempus, Modus und Passiv zugleich tragen (`tehtäisiinkö` „würde es getan?“). Der Gesang reduziert all das auf `TALO` und `TEHDÄ`: wer, wo, woher, wohin, wessen und ob — alles verschwindet, genau die Lücken, die ein Zuhörer füllen muss. Im Polnischen und Russischen streicht das Lemma die Flexionsendung, doch ein Großteil der Beziehung steckt in einem eigenen Wort (der Präposition), sodass das Lemma sie nie allein getragen hat; Englisch verliert wenig außer Numerus und Tempus. Isländisch (vier Fälle, weitgehend von Präpositionen regiert) und Italienisch (Präpositionen und Artikel, wenig Nominalflexion) stehen dem polnisch-russischen bzw. dem englischen Muster näher. Technisch braucht das Werkzeug außerdem einen Wörterbuchanalysator, um zu belegen, dass ein Gesang grammatikfrei ist, und um Wurzeln dem gebeugten Text zuzuordnen; in dieser Pipeline hat nur Finnisch einen (omorfi), und die Schwellen wurden an echten finnischen Korpora kalibriert.

**API-Entwurfsschreiber (`draft`).** Senkt die Einstiegshürde: Es braucht keinen Agenten. Das Skript schickt das Paket (den Gesang, die Wurzeln und die Quellsätze aus `truth.sentences`) an den konfigurierten Anbieter, schreibt `draft.json` und versiegelt es; lehnt `seal` den Entwurf ab, bekommt das Modell ihn zusammen mit den konkreten Einwänden des Prüfers zurück, bis zu 2 Wiederholungen (3 Versuche). Die Exit-Codes entsprechen `seal` (0 versiegelt, 4 weiterhin abgelehnt — korrigiere die letzte `draft.json` von Hand oder mit dem Skill). Eine vorhandene `draft.json` wird ohne `--force` nie überschrieben. Der Skill bleibt der stärkere Modus: unbegrenzte Wiederholungen, wobei der Agent die Einwände unterwegs liest. Eine Regel lässt sich in keinem der beiden Modi deterministisch prüfen: *schreibe realen Personen keine Tatsachen oder Vorwürfe zu, die nicht in den Quellsätzen stehen*. Der Prompt des Entwurfsschreibers und der Skill nennen sie beide, doch nichts prüft sie — lies Einträge über reale Personen, bevor du sie teilst.

**Blinder Lückenfüller (`fill`).** Schickt nur `blind.json` — nie die Antworten oder die Quelle — an den konfigurierten Anbieter, speichert `guesses.json` und startet sofort `judge`. Anbieter: `kirja_llm_provider` (leer = `llm_provider`); Modell: `kirja_filler_model`; `--provider` / `--model` überschreiben beides. `judge` allein ist für Rateversuche eines blinden Subagenten gedacht. Sowohl `draft` als auch `fill` verlangen zuerst ein JSON-Schema (strukturierte Ausgaben); lehnt der Endpunkt es ab, fallen sie auf den einfachen JSON-Modus zurück, dann auf den Prompt allein. `fill` wiederholt zweimal, wenn die Antwort unbrauchbar ist oder eine Lücke fehlt. Jede unbrauchbare Antwort wird im Paketordner gespeichert (`draft_reply_N.txt` / `fill_reply_N.txt`, mit `finish_reason` und einer etwaigen Ablehnung), und die Konsole sagt, wo.

**Den Skill einbinden.**

- *Claude Code:* kopiere `skills/ksiega-niedomowien/` nach `~/.claude/skills/` (persönlich) oder nach `.claude/skills/` in deinem Checkout. Dieses Repo hat `.claude/` in .gitignore, deshalb liegt der Skill unter `skills/`.
- *Claude-Apps:* packe den Ordner `ksiega-niedomowien/` als ZIP (der Ordner selbst muss die Wurzel des Archivs sein) und füge ihn unter **Customize → Skills** hinzu; die Codeausführung muss eingeschaltet sein, und die Sitzung braucht Zugriff auf deinen Checkout, weil die omorfi-Automaten und `export_results/` auf deiner Festplatte liegen. Verwende den Tab **Code** mit einer **lokalen** Sitzung: Im reinen Chatmodus oder in einer Cloud-Sitzung werden die Dateien, die der Agent liest — Quellausschnitte eingeschlossen —, in eine Cloud-Umgebung kopiert.
- *Andere Agenten:* `SKILL.md` ist eine schlichte Markdown-Anleitung mit YAML-Front-Matter; jeder Agent, der im Repo lokale Befehle ausführen kann, kann ihr folgen. Kann er keinen unabhängigen Subagenten starten, verwende `fill` für den blinden Schritt.
- Ein reiner Chat-Assistent ohne lokale Befehlsausführung (z. B. ein Custom GPT) kann es nicht ausführen: omorfi und seine ~130 MB Automaten müssen neben deinen Daten laufen.

> **Datenschutz und Kosten.** Drei Stufen, von den wenigsten zu den meisten Daten: `fill` schickt nur den nebligen Text des Eintrags (nicht die Quelle); `draft` schickt wörtliche Quellsätze (`truth.sentences`) und gibt vor dem Aufruf aus, wie viele; ein Agent, der dem Skill folgt, liest Quellausschnitte und schickt sie an seinen eigenen Modellanbieter — und arbeitet in einer Cloud-Sitzung auf einer Cloud-Kopie der Dateien. Alle API-Aufrufe sind kostenpflichtig. Verwende sie nur auf Material, das du mit diesen Anbietern teilen darfst.

## Ausgabe

Jedes analysierte Korpus bekommt ein eigenes Unterverzeichnis unter `export_results/`, benannt nach der Quelldatei (ohne Pfad und Endung) oder bei URLs nach einem `domain_slug`. Das eingebaute Beispielkorpus verwendet `export_results/_default/`.

Jedes Unterverzeichnis enthält:

| Datei                           | Erzeugt von | Beschreibung                                             |
|---------------------------------|-------------|----------------------------------------------------------|
| `sentences.csv`                 | Notebook    | jeder Satz mit seinem Index und seiner Sprache (`lang`)  |
| `paragraphs.csv`                | Notebook    | Absätze (je 3–6 Sätze)                                   |
| `theses.csv`, `theses.txt`      | Notebook    | eine These pro Absatz (der Satz mit dem höchsten TF-IDF); der Dateiname der `.txt` folgt der Korpussprache (z. B. `tezy.txt` für Polnisch, `тезисы.txt` für Russisch, `thesen.txt` für Deutsch) |
| `keywords_tfidf.csv`            | Notebook    | Schlüsselwörter (Uni-/Bi-/Trigramme) mit TF-IDF-Gewichten |
| `paragraphs_with_topics.csv`    | Notebook    | Absätze mit ihrem zugewiesenen KMeans-Thema              |
| `topic_keywords.json`           | Notebook    | Schlüsselwörter pro Thema                                |
| `entities.csv`                  | Notebook    | alle benannten Entitäten und ihre Labels                 |
| `language_spans.csv`            | Notebook    | fremdsprachige Abschnitte: Dokument, Zeichenpositionen, Sprache, `block` oder `inline`, Text |
| `sentiment.csv`                 | Notebook *(optional)* | Stimmung pro Absatz (`para_id`, `label`, `score`, `lang`) — nur wenn `enable_sentiment` auf `true` steht; Futter für die schamanische Schicht, dem Nutzer nie gezeigt |
| `accessible_text.html`          | Notebook    | `lang` an jedem Absatz plus `<span lang>` an jedem fremdsprachigen Satz und jedem eingebetteten fremdsprachigen Abschnitt (Zitat, Name) — Screenreader wechseln die Stimme automatisch pro Fragment |
| `accessible_text.docx`          | Notebook    | derselbe Inhalt mit `<w:lang>` pro `Run` (`pl-PL`, `ru-RU`, `en-US`, `it-IT`, `fi-FI`, `is-IS`, `de-DE`, `es-ES`, `fr-FR`) — Word und SAPI nutzen es offline, ohne Online-Detektor |
| `analysis_report.html`           | `generate_report.py` | globaler barrierefreier HTML-Bericht           |
| `diagnostic_report.html`         | `generate_diagnostic.py` | strukturierter Diagnosebericht (Themen, Thesen, Entitäten nach Typ, Schlüsselwörter) aus den CSV/JSON-Exporten |
| `gemini_notebook_report.md` | `generate_md.py`     | Markdown für Gemini Notebook (früher NotebookLM) |
| `audio_scripts/*.txt`           | `shamanic_pipeline.py`, `shamanic_ai.py` | rituelle / erzählende Textartefakte |
| `audio_scripts/*.mp3`           | `shamanic_voice.py` *(optional)* | die vier erzählenden Stimmen, über ElevenLabs zu Audio synthetisiert |

## Barrierefreiheit

Das ist der zentrale Wert des Projekts. Alles Folgende ist beabsichtigt und muss bei Änderungen an der Pipeline erhalten bleiben:

- **Keine ANSI-Farben, Emoji oder Pseudografik in der Ausgabe.** Ein Screenreader liest jedes Zeichen wörtlich — `[OK]` statt „🟢“, `---` statt „───━━━“.
- **Stummgeschaltete Fortschrittsbalken** (`tqdm`, `transformers`, `torch`) — `cell_model._silence_hf_progress()` unterdrückt Ladebalken und Warnungen von Hugging Face/torch, bevor IceBERT und icelandic-ner-bert für Isländisch geholt werden; `cell_corpus._silence_ocr_progress()` tut dasselbe für die OCR-Engines.
- **`lang`-Auszeichnung pro Absatz, Satz und Abschnitt im Export.** `accessible_text.html` und `accessible_text.docx` tragen einen ISO-639-1-Code an jedem Absatz, an jedem fremdsprachigen Satz und an jedem eingebetteten fremdsprachigen Abschnitt (einem Zitat oder Namen innerhalb eines Satzes). NVDA, JAWS, Sprachausgabe, VoiceOver, Word und SAPI beachten diese Auszeichnungen und wechseln die Stimme automatisch — auch offline.
- **Feste englische Auszeichnung im HTML-Bericht.** `generate_report.py` umschließt technische englische Fragmente — POS-Tags (`NOUN`, `VERB`, `ADJ`), NER-Labels (`PER`, `ORG`, `[orgName]`), Modellbezeichner von spaCy / Hugging Face, ASCII-Dateinamen, Codeblöcke — immer mit `<span lang="en">`, sodass sie nicht mehr mit der russischen Standardstimme des Dokuments ausgesprochen werden.
- **Auszeichnung fremdsprachiger Korpusfragmente im HTML.** Ist das Korpus nicht russisch, werden strukturierte Ausgaben (Satzauszüge, Schlüsselwortlisten, Themenwörter, RAG-Ranglistenzeilen, Lemmatisierungstabellen) mit `<span lang="target_lang">` umschlossen.
- **Lineare HTML-Struktur** (`<main>`, korrekte Überschriftenhierarchie).

### Die Ausgabe als nicht russischsprachiger Nutzer lesen

Die Erzählung des Notebooks und die `print()`-Ausgabe der meisten Zellen sind russisch. Zwei Eigenschaften der Jupyter-Oberfläche machen das für nicht russischsprachige Screenreader-Nutzer feindselig, und die Pipeline liefert für beide gezielte Umgehungen:

- **Jupyter im Browser setzt fest `lang="en"` auf das Dokument**, und die Frage „Diese Seite übersetzen?“ erscheint auf `localhost`-Seiten ohnehin nie. Ein russisch erzähltes Notebook wird daher mit einer englischen TTS-Stimme vorgelesen — völliges Chaos. Die pragmatische Abhilfe ist die **Jupyter-Erweiterung für VS Code**: Ihre Listenansicht nennt nur die Bezeichnungen `code cell` / `markdown cell` ohne ISO-Auszeichnung, du kannst mit Enter durch Codezellen und mit ↓ an Markdown-Zellen vorbeigehen, ohne ihren Inhalt anzuhören, und das Problem des festen Englisch beschränkt sich auf die Ausgabeansicht (`Ctrl+Shift+↓`) — die du nicht betreten musst.
- **`generate_report.py` ist für nicht russischsprachige Leser praktisch Pflicht.** Es erzeugt `analysis_report.html` mit `<html lang="ru">` und dem vollständigen Satz von `<span lang="…">`-Auszeichnungen pro Fragment. In einem echten Browser geöffnet (nicht aus Jupyter heraus), löst es für die russische Erzählung die Frage „Diese Seite übersetzen?“ aus und wechselt dennoch die TTS-Stimme pro Fragment für Korpusinhalte und für technische englische Begriffe (POS, NER, Modellnamen).
- **Die interaktive Fragerunde schreibt `qa_results.html` und öffnet sie für dich.** `cell_qa_rag` gibt die Anfrage und die drei besten Treffer weiterhin auf stdout aus — schreibt denselben Inhalt aber auch nach `export_results/<project>/qa_results.html` und ruft `webbrowser.open()` auf, sodass die Seite im Systembrowser landet, wo Übersetzung und Stimmwechsel pro Fragment beide funktionieren. Die Ausgabeansicht in Jupyter, in der das feste `lang="en"` die russischen Umhüllungen für einen Screenreader unlesbar macht, ist damit nicht mehr der einzige Weg zum Ergebnis. Jede neue Anfrage überschreibt die Datei.

## Bekannte Einschränkungen

- **Die Herkunft von Lehnwörtern wird nicht ausgezeichnet.** Die Sprachauszeichnung (die `lang`-Attribute, siehe *Sprache jedes Wortes*) umfasst Wörter, die das Wörterbuch einer anderen aufgeführten Sprache kennt, und Fragmente in einer fremden Schrift: griechische Buchstaben, Latein in einem kyrillischen Text. Ein ausdrücklicher Herkunftshinweis (`греч.`, `łac.`, `z niemieckiego`, `имеет греческое происхождение`) wird nicht mit dem entlehnten Wort verknüpft, und ein in die Schrift des Textes transliteriertes Wort (`фразис` in einem russischen Text) behält die Korpussprache. Solche Hinweise haben keine feste Form (Abkürzung, Adjektiv, eine ganze Wendung), und ein kyrillisches `фразис` als Griechisch auszuzeichnen, ließe den Screenreader auf eine griechische Stimme wechseln, was schlechter ist als die russische Voreinstellung.
- **Finnisch: das erste Wort eines Satzes.** Am Satzanfang ist jedes Wort großgeschrieben, und der spaCy-Tagger hält manchmal einen Imperativ oder eine Interjektion für einen Eigennamen: `Anna kuulua.` („lass es hören“) wird zum Namen *Anna*, `Oota, miten…` („warte, wie…“) zum Namen *Oota*. Die omorfi-Korrektur überschreibt nie ein als Name markiertes Wort, weil sonst echte Namen zu gewöhnlichen Wörtern würden (*Tuskia* → *tuska*, „Qual“). Ein solches Wort behält seine geschriebene Form als Lemma und kann in Lemmalisten, Schlüsselwörtern und im Wurzelgesang auftauchen (`anna`, `oota`). Nennt der Tagger das Wort stattdessen eine Interjektion, liefert omorfi das Verb (*Oota* → `oottaa`, seit v1.11.1). Die Prüfung auf ein Grammatikleck im Buch des Ungesagten zählt kein Schlüsselwort, das die Quelle mitten im Satz auch als Namen verwendet (*Anna Maria …*).
- **Namen ohne ihre diakritischen Zeichen.** Ein fremder Name wird nur markiert, wenn seine Schreibung selbst den Beleg liefert: Buchstaben, die das Basisalphabet nicht hat (`Kaczyński`), eine Form, die nur das Lexikon einer anderen angegebenen Sprache kennt, oder eine andere Schrift (`Качиньский` wird als Russisch markiert). Viele Redaktionen lassen die diakritischen Zeichen fremder Namen weg. In RSS-Schlagzeilen, gesammelt am 15. November 2026 (Google News je Land und die eigenen Feeds der Portale), schrieben finnische Medien *Swiatek* in 8 von 8 Schlagzeilen und *Kaczynski* in 2 von 3, während *Wałęsa* seine Buchstaben in 6 von 7 behielt; in französischen, italienischen, spanischen und schwedischen Schlagzeilen überwog die Form ohne Zeichen bei mindestens zwei dieser drei Namen, deutsche und englische Medien behielten die Buchstaben meist, russische transliterieren ins Kyrillische. Ein Name ohne Zeichen, flektierte Formen eingeschlossen (*Kaczynskin*), besteht nur aus Buchstaben des Basisalphabets und steht in dieser Form in keinem Lexikon, bleibt also in der Basissprache und wird von deren Stimme gelesen, gleich was `corpus_languages` angibt. Der Text allein entscheidet das nicht, und ATA rät die entfernten Buchstaben nicht zurück: Jedes unbekannte Wort aus Basisbuchstaben mit fremden Lexika ohne diakritische Zeichen abzugleichen, würde die Stimme auch bei gewöhnlichen Wörtern umschalten. Auch ein Name aus einer Sprache ohne eigenes Paket hier (*Erdoğan*) bleibt in der Basissprache.

## Aufbau des Repositorys

```
accessible_text_analyst/
├── accessible_text_analyst.ipynb   # Hauptpipeline (42 Zellen)
├── generate_report.py              # Generator des HTML-Berichts (Leseansicht)
├── generate_diagnostic.py          # HTML-Diagnosebericht aus den CSV/JSON-Exporten
├── generate_md.py                  # Konverter zu Markdown für Gemini Notebook
├── shamanic_pipeline.py            # optional: ritueller Nachbearbeiter ohne LLM
├── shamanic_ai.py                  # optional: LLM-gestützte rituelle Erzählerinnen
├── llm_klient.py                   # Wahl von LLM-Anbieter und Schlüssel (gemeinsam)
├── shamanic_voice.py               # optional: ElevenLabs-Audio-Dispatcher (läuft einmal)
├── shamanic_locale.py              # Lokalisierungspaket der schamanischen Schicht
├── ksiega_niedomowien.py           # optional: das Buch des Ungesagten (nur Finnisch)
├── skills/ksiega-niedomowien/SKILL.md  # Agenten-Skill für ksiega_niedomowien.py
├── config.example.json             # Konfigurationsvorlage mit Endung JSON (versioniert)
├── config.example.ini              # Konfigurationsvorlage mit Endung INI (versioniert)
├── config.json / config.ini        # deine lokale Konfiguration (in .gitignore)
├── golden_key.env                  # Schlüssel für LLM und ElevenLabs (in .gitignore)
├── requirements.txt                # pip-Abhängigkeiten
├── CLAUDE.md                       # Leitfaden für Claude Code
├── README.md                       # die kanonische Fassung (Englisch)
├── README_pl.md, README_ru.md, …   # Übersetzungen (Rückverweis oben)
├── VERSION                         # vorbereiteter Release-Zyklus (`X.Y.Z-WIP` bis zum Release)
├── release_notes.md                # Versionshinweise in umgekehrt chronologischer Reihenfolge
└── export_results/                 # Analyseausgaben (in .gitignore)
    ├── Sanomattomien_kirja.md      # das Buch des Ungesagten, schrittweise ergänzt
    └── <project_name>/
        ├── sentences.csv
        ├── paragraphs.csv
        ├── theses.csv
        ├── theses.txt              # Name folgt der Korpussprache
        ├── accessible_text.html
        ├── accessible_text.docx
        ├── analysis_report.html
        ├── diagnostic_report.html
        ├── gemini_notebook_report.md
        └── audio_scripts/…
```

## Lizenz

Veröffentlicht unter der [MIT License](LICENSE). Die Pipeline wird nur als Quellcode verteilt — ohne Binärdateien —, und das Notebook lässt sich seiner Natur nach Zelle für Zelle im Browser oder in der Jupyter-Erweiterung für VS Code bearbeiten. Die MIT-Lizenz macht nur ausdrücklich, was das Format ohnehin nahelegt.
