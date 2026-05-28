# Accessible Text Analyst

Pipeline NLP multilingue progettata per **l'accessibilità con i lettori di schermo** (NVDA, JAWS, VoiceOver, Narrator). Tutto il codice, l'output di console e i report sono pensati per essere interpretati in modo pulito dalla tecnologia assistiva: niente colori ANSI, niente emoji, niente barre di progresso, niente pseudografica.

> **Altre lingue:** [English](README.md) · [polski](README_pl.md) · [русский](README_ru.md) · [suomi](README_fi.md) · [íslenska](README_is.md)

> **Stato i18n (v1.0).** È stato tradotto solo il README. La narrazione nel notebook, tutto l'output di console, `CLAUDE.md` e i commenti nel codice rimangono nelle lingue originali (principalmente russo; nei patch e nello strato sciamanico polacco). La traduzione del resto è volutamente rimandata a v1.1 — vedi `release_notes.md`.

## Contenuto del progetto

- `accessible_text_analyst.ipynb` — un notebook Jupyter con la pipeline completa di analisi (40 celle: 20 codice + 20 markdown; la narrazione interna al notebook è in russo). Produce due artefatti di accessibilità (`accessible_text.html`, `accessible_text.docx`) in cui ogni paragrafo e ogni frase in lingua straniera porta il proprio attributo `lang` — lettori di schermo e motori TTS cambiano voce automaticamente, anche offline.
- `generate_report.py` — uno script di post-processing che trasforma il notebook eseguito in un singolo file HTML accessibile (`analysis_report.html`). Avvolge i frammenti in lingua straniera in `<span lang="target_lang">` e, indipendentemente dalla lingua del corpus, marca con `<span lang="en">` i contenuti tecnici inglesi (tag POS, etichette NER, identificativi dei modelli spaCy/Hugging Face, percorsi ASCII). Il codice inline e i blocchi di codice nella narrazione ricevono in massa `lang="en"`.
- `generate_md.py` — converte `analysis_report.html` in `notebooklm_report.md` per NotebookLM. Gli span di accessibilità vengono rimossi perché NotebookLM non li consuma.
- `shamanic_pipeline.py` *(opzionale)* — un post-processore senza LLM che trasforma gli export CSV/JSON del notebook in quattro artefatti testuali rituali (`oracle_script.txt`, `lore_fragments/`, `raw_roots_chant.txt`, `prophecies.txt`), completamente localizzati nelle sei lingue supportate.
- `shamanic_ai.py` *(opzionale, basato su LLM)* — chiama OpenAI per generare quattro voci narrative (`Katla`, `Vieno`, `Lumi`, `Sami`) sopra gli stessi export. Richiede `OPENAI_API_KEY` in `golden_key.env`.
- `shamanic_locale.py` — il pacchetto di localizzazione per entrambi gli script sciamanici (template, intestazioni e stringhe di fallback di Lumi in tutte e sei le lingue).

## Cosa fa la pipeline

1. Carica testo da un file (`.pdf`, `.txt`, `.docx`, `.html` o immagini: `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`, `.webp`) o da un URL — rimuovendo intestazioni/piè di pagina ricorrenti, barre laterali, sezioni "Related articles" e simili contenuti modello. PDF scansionati e immagini in input ricadono su OCR (`pypdfium2` + `easyocr`).
2. Rileva la lingua del corpus con [`lingua-language-detector`](https://github.com/pemistahl/lingua-py). La lingua dominante guida la pipeline spaCy; lo stesso rilevatore viene riutilizzato a livello di paragrafo e di frase per l'export con marcatori di lingua.
3. Carica i modelli spaCy **in due fasi**. Prima il modello della lingua dominante elabora l'intero corpus dall'inizio alla fine (tokenizzazione → stop-word → lemmatizzazione → POS → NER). Poi `cell_multilang_pass` riesegue le passate NLP specifiche per lingua solo per i paragrafi il cui linguaggio rilevato differisce da quello dominante — caricando ogni modello non dominante su richiesta tramite `get_nlp()`, incapsulato in `functools.lru_cache(maxsize=2)`. La cache LRU conta solo in questa seconda fase; in nessun momento ci sono più di due modelli in RAM.
4. Tokenizzazione → filtraggio delle stop-word → lemmatizzazione → POS tagging → NER (NER multilingue a due stadi con dispatch del modello per frase).
5. Rappresentazioni vettoriali: Bag of Words, TF-IDF + ricerca con query automatica e ranking coseno.
6. Struttura: frasi → paragrafi (3–6 frasi ciascuno) → tesi (la frase migliore per paragrafo). Ogni paragrafo e ogni frase viene marcato con il proprio codice ISO 639-1 rilevato.
7. Modellazione di argomenti con KMeans sui vettori paragrafo di spaCy.
8. Export CSV/JSON + un report testuale di sintesi + export HTML e DOCX accessibili + un report HTML globale (`analysis_report.html`).

## Lingue supportate

| Codice | Lingua    | Modello spaCy          | NER / vettori  |
|--------|-----------|------------------------|----------------|
| pl     | polacco   | `pl_core_news_lg`      | spaCy          |
| ru     | russo     | `ru_core_news_lg`      | spaCy          |
| en     | inglese   | `en_core_web_lg`       | spaCy          |
| it     | italiano  | `it_core_news_lg`      | spaCy          |
| fi     | finlandese| `fi_core_news_lg`      | spaCy          |
| is     | islandese | `spacy.blank("is")` + Hugging Face | `mideind/IceBERT-base` (vettori), `mideind/icelandic-ner-MIM-GOLD-22` (NER) |

Non esiste un modello spaCy completo per l'islandese, quindi due modelli Hugging Face vengono innestati in una pipeline vuota. Il primo download richiede ~700 MB di spazio su disco e una connessione internet; le esecuzioni successive riutilizzano la cache HF.

## Rilevamento della lingua

Il rilevamento avviene a tre livelli:

1. **Dominante nel corpus** — `cell_langdet` vota per documento e sceglie la lingua dominante come `LANG`. Guida la pipeline spaCy.
2. **Per paragrafo** (`para_langs`) — usato come attributo `<p lang="...">` in `accessible_text.html` e come `<w:lang>` predefinito per ciascun paragrafo in `accessible_text.docx`.
3. **Per frase** (`sent_langs`) — usato per avvolgere singole frasi in `<span lang="...">` all'interno di paragrafi misti per lingua (HTML) o per impostare `<w:lang>` sui run per frase (DOCX).

Il rilevamento per paragrafo e per frase usa un **wrapper `_safe_detect()` deliberatamente conservativo** in `cell_para`. Affidarsi all'output grezzo di lingua produce artefatti udibili: lingua classifica erroneamente brevi frammenti latini dominati da nomi propri ("Igor de Lendorf" → it, "Mut se mies, Igor" → en), e un lettore di schermo che passa a voce inglese per "Igor de Lendorf" e torna al finlandese per la frase successiva suona peggio di un nome proprio letto con accento finlandese.

Il wrapper applica le seguenti regole in ordine:

1. **Cirillico ovunque nel frammento → `ru`.** Inequivocabile; funziona anche su frammenti di 3 caratteri.
2. **Frammento più corto di 30 caratteri → fallback `LANG`.** Lingua non è affidabile su brevi frammenti latini.
3. **Il frammento contiene i diacritici di `LANG`** (es. `ä`/`ö` per `fi`, `ąęć` per `pl`) → fallback `LANG`. Una frase finlandese con una citazione inglese è comunque una frase finlandese.
4. **Lingua concorda con `LANG`** → accettata.
5. **Lingua dissente, ma la lingua rilevata ha i SUOI diacritici caratteristici nel frammento** (`à` per it, `ż` per pl, `ð` per is) → ci si fida di lingua.
6. **Lingua dissente e la lingua rilevata non ha diacritici caratteristici nel frammento** (tipicamente `en`) → fallback `LANG`.

La motivazione della regola 6 è puramente fonetica: una voce inglese che legge frammenti finlandesi/polacchi/italiani produce una distorsione udibile, mentre una voce finlandese/polacca/italiana che legge una citazione inglese con un lieve accento è intelligibile e non intrusiva. Il compromesso è che frasi puramente inglesi incorporate in un corpus non inglese vengono lette con la voce dominante invece di passare all'inglese. Accettiamo questo compromesso perché, in pratica, gli utenti di lettori di schermo hanno segnalato il costo qualitativo asimmetrico.

Gli outlier che sopravvivono all'euristica vengono elencati nell'output di `cell_para` per la revisione manuale (`Оставшиеся outlier-предложения...`). La stessa logica dei diacritici governa l'euristica per `<code>` (`_classify_code_lang`) in `generate_report.py` e il fallback lingua per segmento (`_lingua_word_fallback`) per identificatori ASCII simili a percorsi.

## Requisiti

- Python 3.10 o superiore.
- ~1,5 GB di spazio libero su disco per i modelli `_lg` di spaCy (uno per lingua). Aggiungi ~700 MB se attivi il supporto per l'islandese (Hugging Face `transformers` + `torch` + IceBERT + MIM-GOLD-22).
- Aggiungi ~700 MB se attivi il supporto OCR (`easyocr` scarica `torch` insieme ai propri modelli di rilevamento e riconoscimento alla prima chiamata OCR). Se hai abilitato anche l'islandese, il costo di `torch` è condiviso tra le due.
- Connessione internet alla prima esecuzione (download dei modelli).

## Configurazione dell'ambiente

Scegli una delle tre opzioni qui sotto. Tutte e tre finiscono con lo stesso `pip install -r requirements.txt` + download dei modelli spaCy.

### Opzione A — `venv` locale (consigliata per uso quotidiano)

```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
```

La directory `.venv/` è in `.gitignore`. Dall'interno del venv attivato, prosegui con **Installazione** qui sotto.

### Opzione B — Anaconda / Miniconda

```bash
conda create -n accessible-text-analyst python=3.11
conda activate accessible-text-analyst
```

Poi prosegui con **Installazione**. Il `pip` incluso in Anaconda funziona bene — non c'è una lista pacchetti Conda specifica per questo progetto.

### Opzione C — Google Colab (nessuna installazione locale)

Apri un nuovo notebook Colab e incolla nella prima cella:

```python
!git clone https://github.com/<your-fork>/accessible_text_analyst.git
%cd accessible_text_analyst
!pip install -r requirements.txt
!python -m spacy download en_core_web_lg
# Aggiungi le righe sottostanti solo per le lingue di cui hai effettivamente bisogno:
# !python -m spacy download pl_core_news_lg
# !python -m spacy download ru_core_news_lg
# !python -m spacy download it_core_news_lg
# !python -m spacy download fi_core_news_lg
```

Poi carica `config.json` (o `config.ini`) tramite il pannello Files, imposta `source_file` ed esegui il notebook. Nota: le sessioni Colab sono effimere — modelli scaricati e artefatti `export_results/` spariscono quando il runtime viene riciclato. Per analisi prolungate monta Google Drive e scrivi l'output lì.

## Installazione

```bash
# 1. Dipendenze Python
pip install -r requirements.txt

# 2. Modelli spaCy — installa solo le lingue di cui hai effettivamente bisogno.
# Le varianti *_lg sono richieste perché la modellazione di argomenti dipende dai vettori parola.
python -m spacy download pl_core_news_lg
python -m spacy download ru_core_news_lg
python -m spacy download en_core_web_lg
python -m spacy download it_core_news_lg
python -m spacy download fi_core_news_lg

# 3. (Opzionale) Supporto islandese — decommenta `transformers` e
# `torch` in requirements.txt e riesegui `pip install -r requirements.txt`.
# IceBERT e MIM-GOLD-22 vengono poi scaricati da Hugging Face alla prima esecuzione.
```

## Configurazione

Copia la configurazione di esempio in un file locale. Sono accettati sia `config.json` sia `config.ini` — **il contenuto è JSON in entrambi i casi**; l'estensione `.ini` è una concessione di usabilità per gli utenti Windows non tecnici per i quali `.json` non ha un gestore predefinito.

```bash
# Scegli uno:
cp config.example.json config.json
cp config.example.ini  config.ini
```

`config.json` e `config.ini` sono entrambi in `.gitignore`, quindi ogni utente mantiene la propria copia locale.

Contenuto:

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

| Chiave             | Tipo            | Scopo |
|--------------------|-----------------|-------|
| `source_file`      | string          | Percorso a un file (`.pdf`, `.txt`, `.docx`, `.html` o un'immagine) **o** un URL (`http://`, `https://`). Una stringa vuota o un file mancante ricade sul corpus di esempio integrato. |
| `custom_patterns`  | string[]        | Lista opzionale di espressioni regolari da rimuovere dal testo grezzo (intestazioni correnti, piè di pagina, contenuti modello ripetitivi). Esempio: `["Editorial: .*", "Copyright \\d{4}"]`. |
| `remove_noise`     | boolean         | Alterna `generate_report.py` tra modalità lettore (`true`, nasconde le barre di caricamento di Hugging Face/torch e le tabelle di lemmatizzazione/POS) e modalità diagnostica completa (`false`). |
| `ocr_languages`    | string[]        | Lingue per `easyocr` (usate solo quando un PDF è una scansione o la sorgente è un'immagine). All'interno di una singola `easyocr.Reader` si possono mescolare solo lingue dello stesso alfabeto — ad es. `["ru", "en"]` per il cirillico o `["en", "pl", "it", "fi", "is"]` per il latino. |
| `ui_lang`          | string          | Lingua dell'interfaccia per l'output della console e l'attributo `<html lang>` del report generato (`pl` / `en` / `ru` / `fi` / `is` / `it`). Stringa vuota o codice sconosciuto → fallback `en`. Indipendente dalla lingua del corpus analizzato, che viene rilevata automaticamente. |
| `lumi_katla_lines` | integer o null  | Limite di ornamento opzionale per il dispaccio finale di Lumi in `shamanic_ai.py`: quante righe non vuote del monologo di Katla vede Lumi. `null` o chiave mancante = tutto il contenuto; integer N > 0 = prime N righe. |
| `lumi_vieno_lines` | integer o null  | Come `lumi_katla_lines`, ma per il canto di echi di Vieno. |

> **`ui_lang` — ambito della localizzazione.** L'output della console dei quattro script attorno alla pipeline (`generate_report.py`, `generate_md.py`, `shamanic_pipeline.py`, `shamanic_ai.py`) è completamente localizzato. Il notebook stesso è localizzato *parzialmente* — i 16 header di sezione (`--- Titolo ---`), l'intero report finale `cell_summary` e il saluto "Q&A pronto" di `cell_qa_rag` seguono `ui_lang`, ma le stampe diagnostiche per ogni passaggio (dettagli di caricamento del corpus, avanzamento OCR, anteprime di token/POS/NER, diagnostica del passaggio multilingue) rimangono in russo. Il notebook è uno strumento per sviluppatori; **l'artefatto user-facing completamente localizzato è `analysis_report.html`** prodotto da `generate_report.py`. Le traduzioni in `fi` / `is` / `it` sono bozze non revisionate — segnala imprecisioni su GitHub.

> **Percorsi Windows e regex — importante.** Il contenuto della configurazione è JSON, e JSON non ha una sintassi raw-string. Una singola barra inversa fa l'escape del carattere successivo (`\U`, `\d`, `\n` sono speciali), quindi un percorso Windows scritto come `"C:\Users\marek\doc.pdf"` produrrà un errore di parsing JSON. Due modi corretti per scriverlo:
>
> - **Barre normali** (più semplice, funziona anche su Windows): `"C:/Users/marek/doc.pdf"`.
> - **Doppie barre inverse**: `"C:\\Users\\marek\\doc.pdf"`.
>
> La stessa regola si applica a ogni espressione regolare in `custom_patterns`: scrivi `"\\d{4}"`, non `"\d{4}"`; scrivi `"Copyright \\d{4}"`, non `"Copyright \d{4}"`. In JSON non esiste la forma raw-string `r"…"`.

## Esecuzione

Gli script numerati di seguito sono pensati per essere eseguiti **in ordine**: ognuno consuma artefatti prodotti dal passo precedente.

### 1. Notebook (obbligatorio)

```bash
jupyter notebook accessible_text_analyst.ipynb
# (Cell → Run All)
```

Questa è una pipeline sequenziale con stato globale condiviso. **Non riordinare le celle, e non eseguirle fuori sequenza.** Il notebook scrive `export_results/<project>/sentences.csv`, `paragraphs.csv`, `theses.csv`, `keywords_tfidf.csv`, `paragraphs_with_topics.csv`, `topic_keywords.json`, `entities.csv`, `accessible_text.html`, `accessible_text.docx` e `theses.txt`.

### 2. Report HTML (consigliato)

```bash
python generate_report.py
# → export_results/<project>/analysis_report.html
```

`generate_report.py` legge gli output delle celle direttamente dal file `.ipynb`, quindi il report HTML deve essere generato da un notebook **appena eseguito**. `requirements.txt` elenca `nbstripout` — se è stato attivato nella configurazione git locale, gli output del notebook vengono rimossi al commit. Genera il report _prima_ del commit o disabilita nbstripout per il tuo workflow.

### 3. Markdown adatto a NotebookLM (opzionale)

```bash
python generate_md.py
# → export_results/<project>/notebooklm_report.md
```

Questo converte il report HTML in un file Markdown con gli span di accessibilità rimossi (NotebookLM non consuma `<span lang="…">`). Eseguilo solo se vuoi caricare il report in NotebookLM.

### 4. Post-processore sciamanico senza LLM (opzionale)

```bash
python shamanic_pipeline.py
# → export_results/<project>/audio_scripts/oracle_script.txt
#                                          /raw_roots_chant.txt
#                                          /prophecies.txt
#                                          /lore_fragments/intercepted_log_T*_P*.txt
```

Genera quattro artefatti testuali rituali direttamente dagli export CSV/JSON del notebook — nessuna chiamata LLM, nessuna rete. Tutte le stringhe provengono da `shamanic_locale.py` e sono completamente localizzate nelle sei lingue supportate.

### 5. Post-processore sciamanico LLM (opzionale, richiede chiave OpenAI)

```bash
python shamanic_ai.py
# → export_results/<project>/audio_scripts/katla_entity_monologue.txt
#                                          /vieno_echoes_chant.txt
#                                          /lumi_final_report.txt
#                                          /sami_energetic_spark.txt
```

Richiede una chiave API OpenAI. Crea `golden_key.env` nella radice del progetto:

```
OPENAI_API_KEY=sk-...
```

`golden_key.env` corrisponde a `*.env` in `.gitignore`, quindi non verrà committato. Le quattro voci girano in sequenza:

1. **Katla** trasmuta l'elenco delle entità (`entities.csv`) in un monologo di spiriti settentrionali ghiacciati.
2. **Vieno** intona un canto sull'elenco di parole chiave/argomenti, intrecciandovi cinque frasi grezze dal corpus come echi da un'altra dimensione.
3. **Lumi** legge `prophecies.txt` (obbligatorio) più il monologo di Katla e il canto di Vieno (ornamento opzionale) e produce il dispaccio finale. Le stringhe di fallback localizzate coprono il caso in cui Katla o Vieno manchino.
4. **Sami** legge il rapporto di Lumi e fornisce una sintesi ad alta energia con la scintilla di speranza o un invito all'azione.

## Output

Ogni corpus analizzato ottiene la propria sottodirectory sotto `export_results/`, denominata in base al file sorgente (percorso ed estensione rimossi) o in base a un `domain_slug` per gli URL. Il corpus di esempio integrato usa `export_results/_default/`.

Ogni sottodirectory contiene:

| File                            | Prodotto da       | Descrizione                                       |
|---------------------------------|-------------------|---------------------------------------------------|
| `sentences.csv`                 | notebook          | ogni frase con il suo indice e l'assegnazione al paragrafo |
| `paragraphs.csv`                | notebook          | paragrafi (3–6 frasi ciascuno)                    |
| `theses.csv`, `theses.txt`      | notebook          | una tesi per paragrafo (la frase a TF-IDF più alto); il nome del file `.txt` segue la lingua del corpus (es. `tezy.txt` per il polacco, `тезисы.txt` per il russo) |
| `keywords_tfidf.csv`            | notebook          | parole chiave (uni/bi/trigrammi) con pesi TF-IDF  |
| `paragraphs_with_topics.csv`    | notebook          | paragrafi con il loro argomento KMeans assegnato  |
| `topic_keywords.json`           | notebook          | parole chiave per argomento                       |
| `entities.csv`                  | notebook          | tutte le entità nominate e le loro etichette      |
| `accessible_text.html`          | notebook          | attributi `lang` a livello di paragrafo e frase — i lettori di schermo cambiano voce automaticamente per frammento |
| `accessible_text.docx`          | notebook          | lo stesso contenuto con `<w:lang>` impostato per `Run` (`pl-PL`, `ru-RU`, `en-US`, `it-IT`, `fi-FI`, `is-IS`) — Word e SAPI lo usano offline, senza rilevatore online |
| `analysis_report.html`           | `generate_report.py` | report HTML globale accessibile                |
| `notebooklm_report.md`      | `generate_md.py`     | Markdown pronto per NotebookLM                 |
| `audio_scripts/*.txt`           | `shamanic_pipeline.py`, `shamanic_ai.py` | artefatti testuali rituali / narrativi |

## Accessibilità

Questo è il valore centrale del progetto. Tutto ciò che segue è intenzionale e deve essere preservato quando la pipeline viene modificata:

- **Niente colori ANSI, emoji o pseudografica in stdout.** Un lettore di schermo legge ogni carattere alla lettera — `[OK]` invece di "🟢", `---` invece di "───━━━".
- **Barre di progresso silenziate** (`tqdm`, `transformers`, `torch`) — `cell_model._silence_hf_progress()` silenzia le barre di caricamento e gli avvisi di Hugging Face/torch prima di scaricare IceBERT e MIM-GOLD-22 per l'islandese; `cell_corpus._silence_ocr_progress()` fa lo stesso per `easyocr`.
- **Marcatura `lang` per paragrafo e per frase nell'export.** `accessible_text.html` e `accessible_text.docx` portano un codice ISO 639-1 su ogni paragrafo (e su ogni frase all'interno di paragrafi / run misti per lingua). NVDA, JAWS, Narrator, VoiceOver, Word e SAPI rispettano questi tag e cambiano voce automaticamente — anche offline.
- **Marcatura inglese cablata nel report HTML.** `generate_report.py` avvolge sempre i frammenti tecnici inglesi — tag POS (`NOUN`, `VERB`, `ADJ`), etichette NER (`PER`, `ORG`, `[orgName]`), identificativi dei modelli spaCy / Hugging Face, percorsi ASCII, blocchi di codice — in `<span lang="en">`, così non vengono più pronunciati con la voce russa predefinita del documento.
- **Marcatura per frammento del corpus straniero in HTML.** Quando il corpus non è russo, gli output strutturati (estratti di frasi, elenchi di parole chiave, parole di argomenti, righe di ranking RAG, tabelle di lemmatizzazione) vengono avvolti in `<span lang="target_lang">`.
- **Struttura HTML lineare** (`<main>`, gerarchia di intestazioni corretta).

## Layout del repository

```
accessible_text_analyst/
├── accessible_text_analyst.ipynb   # pipeline principale (40 celle)
├── generate_report.py              # generatore di report HTML
├── generate_md.py                  # convertitore Markdown per NotebookLM
├── shamanic_pipeline.py            # opzionale: post-processore rituale senza LLM
├── shamanic_ai.py                  # opzionale: narratori rituali LLM
├── shamanic_locale.py              # pacchetto di localizzazione per lo strato sciamanico
├── config.example.json             # template di configurazione, estensione JSON (versionato)
├── config.example.ini              # template di configurazione, estensione INI (versionato)
├── config.json / config.ini        # la tua configurazione locale (gitignored)
├── golden_key.env                  # chiave OpenAI per shamanic_ai.py (gitignored)
├── requirements.txt                # dipendenze pip
├── CLAUDE.md                       # guida per Claude Code
├── README.md                       # README canonico (in inglese)
├── README_pl.md, README_ru.md, …   # traduzioni (collegamento di ritorno in alto)
├── release_notes.md                # release notes in ordine cronologico inverso
└── export_results/                 # risultati dell'analisi (gitignored)
    └── <project_name>/
        ├── sentences.csv
        ├── paragraphs.csv
        ├── theses.csv
        ├── theses.txt              # nome localizzato per lingua del corpus
        ├── accessible_text.html
        ├── accessible_text.docx
        ├── analysis_report.html
        ├── notebooklm_report.md
        └── audio_scripts/…
```

## Licenza

Rilasciato sotto [licenza MIT](LICENSE). La pipeline è distribuita solo come sorgente — niente binari — e il notebook è per sua natura modificabile cella per cella tramite il browser o l'estensione Jupyter per VS Code. La licenza MIT rende semplicemente esplicito ciò che il formato già implica.
