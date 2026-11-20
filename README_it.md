# Accessible Text Analyst

Pipeline NLP multilingue progettata per **l'accessibilità con i lettori di schermo** (NVDA, JAWS, VoiceOver, Narrator). Tutto il codice, l'output di console e i report sono pensati per essere interpretati in modo pulito dalla tecnologia assistiva: niente colori ANSI, niente emoji, niente barre di progresso, niente pseudografica.

> **Altre lingue:** [English](README.md) · [polski](README_pl.md) · [русский](README_ru.md) · [suomi](README_fi.md) · [íslenska](README_is.md) · [Deutsch](README_de.md) · [español](README_es.md) · [français](README_fr.md)

> **Stato i18n (v1.0).** È stato tradotto solo il README. La narrazione nel notebook, tutto l'output di console, `CLAUDE.md` e i commenti nel codice rimangono nelle lingue originali (principalmente russo; nei patch e nello strato sciamanico polacco). La traduzione del resto è volutamente rimandata a v1.1 — vedi `release_notes.md`.

## Contenuto del progetto

- `accessible_text_analyst.ipynb` — un notebook Jupyter con la pipeline completa di analisi (42 celle: 21 codice + 21 markdown; la narrazione interna al notebook è in russo). Produce due artefatti di accessibilità (`accessible_text.html`, `accessible_text.docx`) in cui ogni paragrafo e ogni frase in lingua straniera porta il proprio attributo `lang` — lettori di schermo e motori TTS cambiano voce automaticamente, anche offline.
- `generate_report.py` — uno script di post-processing che trasforma il notebook eseguito in un singolo file HTML accessibile (`analysis_report.html`). Avvolge i frammenti in lingua straniera in `<span lang="target_lang">` e, indipendentemente dalla lingua del corpus, marca con `<span lang="en">` i contenuti tecnici inglesi (tag POS, etichette NER, identificativi dei modelli spaCy/Hugging Face, percorsi ASCII). Il codice inline e i blocchi di codice nella narrazione ricevono in massa `lang="en"`. In modalità lettore (`remove_noise: true`) tronca i cicli diagnostici per-documento del notebook ai primi pochi documenti invece di stamparne centinaia.
- `run_all.py` — un launcher dell'intera catena locale gratuita: registra il kernel Jupyter `analyst_env` se manca, esegue il notebook senza interfaccia (senza la cella interattiva delle domande) e ne salva gli output nel `.ipynb`, poi esegue `generate_report.py`, `shamanic_pipeline.py` e, per un corpus finlandese, lo `scan` del Libro del non detto. Non avvia mai un passaggio a pagamento (rituali LLM, voci ElevenLabs, `draft`/`fill` del Libro).
- `generate_diagnostic.py` — un generatore indipendente di un report **diagnostico** completo (`diagnostic_report.html`) costruito direttamente dalle esportazioni CSV/JSON del notebook (non dall'output di `generate_report.py`). Una struttura navigabile e pensata per gli screen reader: un indice `<nav>` più sezioni — ciascuna con il proprio titolo ed elenchi — per una panoramica, i temi con i relativi paragrafi, le tesi, le entità nominate per tipo e le parole chiave principali. Le etichette strutturali seguono `ui_lang`; i frammenti del corpus ricevono `<span lang="…">`, le etichette NER `<span lang="en">`.
- `generate_md.py` — converte `analysis_report.html` in `gemini_notebook_report.md` per Gemini Notebook (in precedenza NotebookLM). Gli span di accessibilità vengono rimossi perché Gemini Notebook non li consuma.
- `shamanic_pipeline.py` *(opzionale)* — un post-processore senza LLM che trasforma gli export CSV/JSON del notebook in artefatti testuali rituali (`oracle_script.txt`, `lore_fragments/`, `raw_roots_chant.txt`, `prophecies.txt` e — quando l'analisi del sentiment opzionale è abilitata — `emotional_undertow.txt`), completamente localizzati nelle nove lingue supportate.
- `shamanic_ai.py` *(opzionale, basato su LLM)* — chiama un LLM (OpenAI per impostazione predefinita; OpenRouter o qualsiasi endpoint compatibile con OpenAI tramite `llm_provider`) per generare quattro voci narrative (`Katla`, `Vieno`, `Lumi`, `Sami`) sopra gli stessi export. Quando il `sentiment.csv` opzionale è presente, Vieno costruisce il suo canto sull'arco emotivo del testo invece che sulle frasi grezze. Richiede la chiave del fornitore scelto in `golden_key.env`.
- `shamanic_voice.py` *(opzionale, richiede ElevenLabs)* — un dispatcher autonomo a esecuzione singola che sintetizza in audio `.mp3` i quattro artefatti narrativi prodotti da `shamanic_ai.py` tramite l'API ElevenLabs, registra ogni successo/fallimento sulla console ed esce (nessun bot, nessun server). Richiede `ELEVENLABS_API_KEY` in `golden_key.env` e una mappatura `voices` nella configurazione.
- `shamanic_locale.py` — il pacchetto di localizzazione per entrambi gli script sciamanici (template, intestazioni e stringhe di fallback di Lumi in tutte e nove le lingue).
- `ksiega_niedomowien.py` *(opzionale, solo finlandese, con un agente)* — il Libro del non detto (*Sanomattomien kirja*): trasforma `raw_roots_chant.txt` in un diario cifrato che cresce in modo incrementale, con lacune che un modello cieco non è riuscito a indovinare. È l'aiutante deterministico della skill in `skills/ksiega-niedomowien/SKILL.md`; l'output della console segue `ui_lang`.
- `helsinki_reacts.py` *(opzionale, con LLM)* — copione satirico di una diretta: Valtteri di Helsinki reagisce con una chat finlandese a una registrazione (una cartella di esportazione o un file di testo). Il prompt di sistema sta fuori dal codice (`helsinki_reacts.example.md`, la tua copia in `helsinki_reacts.md`) e la lingua della diretta segue `ui_lang`. Richiede la chiave del provider scelto in `golden_key.env`.

## Cosa fa la pipeline

1. Carica testo da un file (`.pdf`, `.txt`, `.docx`, `.md`, `.html` o immagini: `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`, `.webp`) o da un URL — rimuovendo intestazioni/piè di pagina ricorrenti, barre laterali, sezioni "Related articles" e simili contenuti modello. PDF scansionati e immagini in input passano all'OCR: ogni lingua di `corpus_languages` legge la pagina con il proprio motore (l'OCR integrato in Windows 10/11, oppure Tesseract per una lingua che Windows non ha — oggi l'islandese), RapidOCR la legge un'altra volta come riserva e un lessico per ciascuna lingua sceglie le forme di dizionario fra tutte le letture.
2. Stabilisce la lingua di ogni parola dai dizionari delle lingue elencate in `corpus_languages` (vedi **La lingua di ogni parola**): la lingua di base guida la pipeline spaCy, mentre citazioni e nomi stranieri diventano segmenti linguistici.
3. Esegue spaCy una sola volta per ogni segmento di testo: il modello della lingua di base elabora il testo di base insieme agli inserti stranieri, e ogni blocco straniero viene elaborato dal modello della sua lingua, caricato su richiesta tramite `get_nlp()` (avvolto in `functools.lru_cache(maxsize=2)`, quindi in cache restano al massimo due modelli). Non c'è alcuna risegmentazione né un secondo passaggio multilingue.
4. Tokenizzazione → filtraggio delle stop-word → lemmatizzazione → POS tagging → NER, ogni token analizzato dal modello della propria lingua.
5. Rappresentazioni vettoriali: Bag of Words, TF-IDF + ricerca con query automatica e ranking coseno.
6. Struttura: frasi → paragrafi (3–6 frasi ciascuno) → tesi (la frase migliore per paragrafo). Ogni frase porta la propria lingua e i propri inserti stranieri; ogni paragrafo la propria lingua prevalente.
7. Modellazione di argomenti con KMeans sui vettori paragrafo di spaCy.
8. *(Opzionale, disattivata per impostazione predefinita)* Punteggio del sentiment per paragrafo con `cardiffnlp/twitter-xlm-roberta-base-sentiment`, scritto in `sentiment.csv`. Il risultato non viene mai mostrato all'utente — esiste solo come alimentazione per lo strato sciamanico. Vedi **Configurazione** (`enable_sentiment`).
9. Export CSV/JSON + un report testuale di sintesi + export HTML e DOCX accessibili + un report HTML globale (`analysis_report.html`).

## Lingue supportate

| Codice | Lingua    | Modello spaCy          | NER / vettori  |
|--------|-----------|------------------------|----------------|
| pl     | polacco   | `pl_core_news_lg`      | spaCy          |
| ru     | russo     | `ru_core_news_lg`      | spaCy          |
| en     | inglese   | `en_core_web_lg`       | spaCy          |
| it     | italiano  | `it_core_news_lg`      | spaCy          |
| de     | tedesco   | `de_core_news_lg`      | spaCy          |
| es     | spagnolo  | `es_core_news_lg`      | spaCy          |
| fr     | francese  | `fr_core_news_lg`      | spaCy          |
| fi     | finlandese| `fi_core_news_lg`      | spaCy          |
| is     | islandese | `spacy.blank("is")` + Hugging Face | `mideind/IceBERT` (vettori), `grammatek/icelandic-ner-bert` (NER) |

Non esiste un modello spaCy completo per l'islandese, quindi due modelli Hugging Face vengono innestati in una pipeline vuota. Il primo download richiede ~1,3 GB di spazio su disco e una connessione internet; le esecuzioni successive riutilizzano la cache HF.

**Miglioramento opzionale della morfologia finlandese (omorfi).** Il lemmatizzatore statistico di `fi_core_news_lg` fatica con la morfologia agglutinante finlandese — produce regolarmente lemmi spazzatura come *kytköknen* o *pisttää*. Se il pacchetto `omorfi` (puro Python) è installato e i suoi automi FST sono stati scaricati (vedi Installazione, passo 5), il notebook aggiunge un componente `omorfi_lemmas` che sostituisce lemmi e tratti morfologici UD con le analisi del dizionario ovunque queste concordino con la parte del discorso del tagger spaCy (`kytköksistä` → `kytkös`, `Euroopassa` → `Eurooppa`, `pistät` → `pistää`). Senza il pacchetto o gli automi la pipeline mantiene silenziosamente il comportamento standard di spaCy.

## La lingua di ogni parola

Le lingue del testo si elencano in `corpus_languages` (`config.json`; il vecchio nome `ocr_languages` viene ancora letto). Dai dizionari di queste lingue il notebook stabilisce:

1. **La lingua di base** (`LANG`) — la lingua il cui dizionario conosce la quota più ampia delle parole del corpus (le quote vengono stampate). Guida la pipeline spaCy principale.
2. **La lingua di ogni parola** (`odcinki_jezykowe.py`). Una parola che il dizionario di base non conosce, ma che conosce il dizionario di un'altra lingua elencata, appartiene a quella lingua; una parola nota a più di esse va all'alfabeto più piccolo che contiene tutte le sue lettere — così una parola inglese non viene presa dal dizionario polacco, che conosce molte forme inglesi, mentre `Łódź` resta polacca. La scrittura è un fatto: una parola in cirillico dentro un testo latino riceve una lingua cirillica anche se nessuna è elencata.
3. **Segmenti stranieri** — almeno due parole straniere consecutive della stessa lingua all'interno di una frase, oppure una parola con lettere che l'alfabeto di base non ha. Un segmento che copre frasi intere è un **blocco** e viene elaborato dal proprio modello spaCy (frasi, NER, lemmi). Un segmento dentro una frase nella lingua di base è un **inserto**: la frase resta al modello di base, e l'inserto riceve lemmi e tag POS dal modello della propria lingua.

L'export porta il risultato: `<span lang="…">` in `accessible_text.html` e un `Run` separato con `<w:lang>` in `accessible_text.docx` per ogni frase straniera e ogni inserto, così il lettore di schermo cambia voce esattamente sulla citazione o sul nome, non sull'intera frase. Tutti i segmenti sono elencati anche in `language_spans.csv`, e `sentences.csv` ha la colonna `lang`.

Dizionari: i vettori spaCy (un elenco finito di forme) per polacco, inglese, russo, italiano, tedesco, spagnolo e francese; `omorfi` per il finlandese; BÍN (`islenska`) per l'islandese — gli stessi dizionari usati dal voto OCR. Con una sola lingua in `corpus_languages` nessun dizionario viene caricato e vengono marcate solo le parole di un'altra scrittura. Un dizionario mancante ferma l'esecuzione con un messaggio che indica la correzione.

**Quali lingue elencare.** Misurato su 20 trascrizioni finlandesi (55.000 parole) in cui compaiono molti nomi polacchi: con `["fi", "en"]` il notebook trova 34 segmenti inglesi (termini e citazioni); con `["fi", "pl", "en"]` trova in più 57 segmenti polacchi — nomi polacchi e qualche espressione polacca, ora letti da una voce polacca invece che finlandese — e nessuna parola inglese finisce al polacco. Quindi:

- elenca ogni lingua da cui il testo riporta **citazioni**;
- per un testo scritto in una lingua che menziona **nomi** di un'altra (nomi polacchi in un testo finlandese), aggiungi la lingua dei nomi: i nomi nella forma base e i nomi con lettere che l'alfabeto di base non ha (`ł`, `ś`) vengono allora letti dalla voce della loro lingua. Un nome declinato solo con lettere dell'alfabeto di base (`Kowalskille`) resta comunque nella lingua di base;
- non elencare una lingua che nel testo non c'è: aggiunge solo falsi candidati.

**Perché non un rilevatore statistico.** Fino ad ATA 1.x `lingua-language-detector` classificava frasi intere. Sulle stesse trascrizioni ha marcato 127 frasi come straniere, quasi tutte a torto; le euristiche necessarie per sopprimerlo lasciavano 2 frasi e nessuna delle citazioni inglesi. ATA 2.0 lo ha rimosso. Il report globale (`generate_report.py`) marca le parole straniere nella narrazione russa con gli stessi dizionari (le lingue di `corpus_languages` più l'inglese).

## Requisiti

- Python 3.12 o superiore (le dipendenze sono testate su Python 3.14).
- ~1,5 GB di spazio libero su disco per i modelli `_lg` di spaCy (uno per lingua). Aggiungi ~1,3 GB se attivi il supporto per l'islandese (Hugging Face `transformers` + `torch` + IceBERT + icelandic-ner-bert). Il NER islandese legge l’intero documento in finestre sovrapposte: circa 4.000 caratteri al secondo su CPU, quindi un libro (1 MB di testo islandese) richiede qualche minuto.
- Supporto OCR (opzionale): i pacchetti `winrt-*` (meno di 1 MB) e, per ogni lingua di `corpus_languages`, il pacchetto di lingua di Windows con il riconoscimento ottico dei caratteri (Impostazioni > Data/ora e lingua > Lingua e area geografica); `rapidocr` con `onnxruntime` (i modelli, circa 40 MB, si scaricano alla prima chiamata OCR); per una lingua senza motore Windows (oggi l'islandese) `tesserocr` e il modello tessdata_best della lingua nella cartella `tessdata` del repository (islandese: https://github.com/tesseract-ocr/tessdata_best/raw/main/isl.traineddata, circa 9,5 MB) più il lessico `islenska` (~62 MB). L'OCR non richiede più `torch`. Un motore o un lessico mancante ferma l'esecuzione con un messaggio che indica la correzione. Lessico islandese: The Database of Icelandic Morphology (BÍN), The Árni Magnússon Institute for Icelandic Studies, autrice e curatrice Kristín Bjarnadóttir, CC BY-SA 4.0.
- Aggiungi ~130 MB se attivi il miglioramento della morfologia finlandese (gli automi FST di `omorfi` scaricati con `omorfi-download`).
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
conda create -n accessible-text-analyst python=3.14
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
# !python -m spacy download de_core_news_lg
# !python -m spacy download es_core_news_lg
# !python -m spacy download fr_core_news_lg
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
python -m spacy download de_core_news_lg
python -m spacy download es_core_news_lg
python -m spacy download fr_core_news_lg

# 3. (Opzionale) Supporto islandese — decommenta `transformers` e
# `torch` in requirements.txt e riesegui `pip install -r requirements.txt`.
# IceBERT e icelandic-ner-bert vengono poi scaricati da Hugging Face alla prima esecuzione.

# 4. (Opzionale) Analisi del sentiment — decommenta `transformers`, `torch`,
# `sentencepiece`, `protobuf` e `tiktoken` in requirements.txt, riesegui
# l'installazione e imposta "enable_sentiment": true in config.json. Il modello
# (~1.1 GB) viene scaricato da Hugging Face alla prima esecuzione e poi messo in cache.
# Tutti e cinque i pacchetti sono necessari insieme per costruire il tokenizer XLM-RoBERTa.

# 5. (Opzionale) Miglioramento della morfologia finlandese — decommenta `omorfi`
# in requirements.txt, riesegui l'installazione, poi scarica gli automi FST
# (~130 MB di file *.hfst estratti nella radice del repository; sono in .gitignore).
# Eseguilo dalla radice del repository:
omorfi-download

# 6. (Facoltativo) Confronta le versioni installate con i limiti di
# requirements.txt e con PyPI. Avvisa soltanto, non blocca nulla:
python audyt_zaleznosci.py
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
  "reacts_llm_provider": "",
  "reacts_model": "",
  "reacts_lang": "",
  "voices": {
    "katla": "",
    "vieno": "",
    "lumi": "",
    "sami": ""
  }
}
```

| Chiave             | Tipo            | Scopo |
|--------------------|-----------------|-------|
| `source_file`      | string          | Percorso a un file (`.pdf`, `.txt`, `.docx`, `.md`, `.html` o un'immagine) **o** un URL (`http://`, `https://`). Una stringa vuota o un file mancante ricade sul corpus di esempio integrato. |
| `custom_patterns`  | string[]        | Lista opzionale di espressioni regolari da rimuovere dal testo grezzo (intestazioni correnti, piè di pagina, contenuti modello ripetitivi). Esempio: `["Editorial: .*", "Copyright \\d{4}"]`. |
| `remove_noise`     | boolean         | Alterna `generate_report.py` tra modalità lettore (`true`, nasconde le barre di caricamento di Hugging Face/torch e le tabelle di lemmatizzazione/POS) e modalità diagnostica completa (`false`). |
| `corpus_languages` | string[]        | Lingue del TESTO (codici dei pacchetti linguistici: `de`, `en`, `es`, `fi`, `fr`, `is`, `it`, `pl`, `ru`); il vecchio nome `ocr_languages` viene ancora letto. I loro dizionari scelgono la lingua di base e la lingua di ogni parola (vedi **La lingua di ogni parola**), e nei PDF scansionati e nelle immagini ciascuna legge la pagina con il proprio motore OCR. Elenca solo le lingue che compaiono davvero nel testo: una lingua in più rallenta l'OCR e aggiunge falsi candidati. Latino e cirillico si possono mescolare (`["fi", "ru"]`). |
| `enable_sentiment` | boolean         | Attiva l'analisi del sentiment per paragrafo opzionale (`false` per impostazione predefinita). Richiede le dipendenze del sentiment commentate (vedi Installazione passo 4). Scrive `sentiment.csv`; il risultato non viene mai mostrato all'utente, alimenta solo lo strato sciamanico (il rituale `emotional_undertow.txt` e il canto di Vieno). In caso di qualsiasi errore di caricamento salta silenziosamente — nessun fallback. |
| `ui_lang`          | string          | Lingua dell'interfaccia per l'output della console e l'attributo `<html lang>` del report generato (`pl` / `en` / `ru` / `fi` / `is` / `it` / `de` / `es` / `fr`). Stringa vuota o codice sconosciuto → fallback `en`. Indipendente dalla lingua del corpus analizzato, che stabiliscono i dizionari di `corpus_languages`. |
| `lumi_katla_lines` | integer o null  | Limite di ornamento opzionale per il dispaccio finale di Lumi in `shamanic_ai.py`: quante righe non vuote del monologo di Katla vede Lumi. `null` o chiave mancante = tutto il contenuto; integer N > 0 = prime N righe. |
| `lumi_vieno_lines` | integer o null  | Come `lumi_katla_lines`, ma per il canto di echi di Vieno. |
| `voices`           | oggetto         | Associa ciascuna voce sciamanica (`katla` / `vieno` / `lumi` / `sami`) a un ID voce ElevenLabs, consumato da `shamanic_voice.py`. Una voce con un ID vuoto o mancante viene saltata. Necessario solo se esegui il dispatcher audio. |
| `llm_provider` | stringa | Fornitore LLM per `shamanic_ai.py` e per il Libro: `openai` (predefinito), `openrouter` oppure `openai_compat`. Ogni fornitore legge da `golden_key.env` solo la propria chiave — vedi *Fornitori LLM e chiavi* più sotto. |
| `llm_model` | stringa | Modello per quel fornitore. Vuoto = predefinito del fornitore (`gpt-6.1-sol` / `openai/gpt-6.1-sol`); obbligatorio per `openai_compat`. |
| `llm_base_url` | stringa | Indirizzo dell'endpoint, letto **solo** da `openai_compat` (es. `http://localhost:1234/v1`). Ignorato da `openai` e `openrouter`, i cui indirizzi sono fissi. |
| `kirja_llm_provider` | stringa | Sostituzione opzionale del fornitore per il Libro (`ksiega_niedomowien.py draft` / `fill`). Vuoto = `llm_provider`. |
| `kirja_drafter_model` | stringa | Modello per `draft` (l'autore delle bozze del Libro via API). Vuoto = predefinito del fornitore, oppure `llm_model` quando il Libro usa il fornitore globale. |
| `kirja_filler_model` | stringa | Modello per `fill` (l'indovino cieco delle lacune del Libro). Stesso ripiego di `kirja_drafter_model`. |
| `reacts_llm_provider` | string | Sostituzione facoltativa del provider per `helsinki_reacts.py`. Vuoto = `llm_provider`. |
| `reacts_model` | string | Modello per `helsinki_reacts.py`. Vuoto = predefinito del provider, oppure `llm_model` quando Helsinki Reacts usa il provider globale. |
| `reacts_lang` | string | Lingua della diretta di `helsinki_reacts.py` (un codice `ui_lang`). Vuoto = `ui_lang`. `fi` = la diretta in finlandese; ogni altra = la sua traduzione con interiezioni finlandesi. |

> **Fornitori LLM e chiavi.** Una chiave è legata a un solo host e non viene mai inviata altrove: `openai` → `OPENAI_API_KEY` → `api.openai.com`; `openrouter` → `OPENROUTER_API_KEY` → `openrouter.ai`; `openai_compat` → `LLM_COMPAT_API_KEY` → `llm_base_url`. Il fornitore si sceglie esplicitamente e non viene mai dedotto da un indirizzo, quindi puntare uno script verso un altro servizio non può né far trapelare la chiave del primo servizio né rompere l'altro script. La chiave precedente alla v1.7.0 `kirja_filler_base_url` (inviava `OPENAI_API_KEY` a qualsiasi indirizzo) viene rifiutata con un messaggio di migrazione. Su OpenRouter gli identificativi dei modelli hanno il prefisso del produttore (`openai/gpt-4o`, `anthropic/claude-sonnet-5.5`), e le impostazioni di privacy dell'account permettono di escludere i fornitori che potrebbero addestrarsi sui tuoi prompt.

> **Analisi del sentiment — costo della CPU.** Con `enable_sentiment: true`, il passaggio per paragrafo è computazionalmente pesante sulla CPU — all'incirca paragonabile all'esecuzione locale del riconoscimento vocale Whisper su CPU. Su macchine più vecchie o con vincoli termici questo carico sostenuto può rappresentare una vera sollecitazione per il processore; attivalo deliberatamente, idealmente su una macchina con una GPU o con margine per un lavoro prolungato a pieno carico.

> **`ui_lang` — ambito della localizzazione.** L'output della console degli script autonomi (`generate_report.py`, `generate_md.py`, `generate_diagnostic.py`, `shamanic_pipeline.py`, `shamanic_ai.py`, `ksiega_niedomowien.py`, `helsinki_reacts.py`) è localizzato tramite `ui_lang`. Lo **stdout del notebook non è** localizzato — è russo hardcoded (solo il nome del file delle tesi segue la lingua del corpus rilevata). Il report in modalità lettore `analysis_report.html` mantiene la narrazione russa del notebook (la sua radice è `<html lang="ru">`); l'artefatto user-facing completamente localizzato tramite `ui_lang` è **`diagnostic_report.html`** prodotto da `generate_diagnostic.py`. Le traduzioni in `fi` / `is` / `it` / `de` / `es` / `fr` sono bozze non revisionate — segnala imprecisioni su GitHub.

> **Percorsi Windows e regex — importante.** Il contenuto della configurazione è JSON, e JSON non ha una sintassi raw-string. Una singola barra inversa fa l'escape del carattere successivo (`\U`, `\d`, `\n` sono speciali), quindi un percorso Windows scritto come `"C:\Users\marek\doc.pdf"` produrrà un errore di parsing JSON. Due modi corretti per scriverlo:
>
> - **Barre normali** (più semplice, funziona anche su Windows): `"C:/Users/marek/doc.pdf"`.
> - **Doppie barre inverse**: `"C:\\Users\\marek\\doc.pdf"`.
>
> La stessa regola si applica a ogni espressione regolare in `custom_patterns`: scrivi `"\\d{4}"`, non `"\d{4}"`; scrivi `"Copyright \\d{4}"`, non `"Copyright \d{4}"`. In JSON non esiste la forma raw-string `r"…"`.

## Esecuzione

Gli script numerati di seguito sono pensati per essere eseguiti **in ordine**: ognuno consuma artefatti prodotti dal passo precedente.

### Scorciatoia: l'intera catena locale (`run_all.py`)

```bash
# notebook -> generate_report.py -> shamanic_pipeline.py -> scan del Libro (solo finlandese)
python run_all.py
# riusa gli output già salvati nel notebook
python run_all.py --skip-notebook
# diagnostica completa degli avvisi delle librerie, indipendente dal config
python run_all.py --warnings-as-errors
```

I passi 1, 2 e 4 qui sotto, più lo `scan` del Libro del non detto per un corpus finlandese, con un solo comando. Eseguilo con il Python del `.venv` del repository: se il kernel `analyst_env` manca, viene registrato per quell'interprete. La catena si ferma al primo passo che fallisce; il codice di uscita 3 significa che il controllo della fonte del report ha rifiutato (vedi passo 2). Il notebook silenzia di proposito gli avvisi delle librerie, perché non finiscano nel report di analisi. `--warnings-as-errors` è una modalità separata di diagnostica completa: ignora `config.json` e fa passare una copia del notebook con un corpus sintetico attraverso ogni componente (un PDF con riparazione dei font e una pagina scansionata per l’OCR, tutti i formati di input e un URL da un server locale, sentiment, islandese, omorfi). Registra ogni avviso, anche quelli sollevati in codice che intercetta le eccezioni, e li stampa tutti sotto l’intestazione della cella, nella formulazione della libreria, con il punto in cui sono stati sollevati. Gli avvisi noti e innocui (`diagnostyka.ZNANE_OSTRZEZENIA`) hanno una riga a parte e non contano. La modalità richiede tutte le dipendenze opzionali di `requirements.txt` e il modello `fi_core_news_lg`, e un componente che non si carica la ferma con un messaggio. Il notebook e `export_results/` restano intatti, il report e i passi successivi non partono; codice di uscita 4 = nuovi avvisi, 0 = nessuno. Il registro copre il modulo `warnings` nel processo del notebook: i messaggi inviati tramite `logging` (ad es. da `transformers`) e gli avvisi dei processi figli ne restano fuori. Se una libreria sostituisce il registro (ad es. `logging.captureWarnings`), la modalità termina con codice 1 invece di un falso «pulito»; lo stesso vale per Ctrl+C, dopo aver stampato gli avvisi raccolti. Eseguilo dopo aver aggiornato le librerie.

### 1. Notebook (obbligatorio)

```bash
jupyter notebook accessible_text_analyst.ipynb
# (Cell → Run All)
# Senza interfaccia (CI): celle 0-39 con nbclient, senza la cella interattiva cell_qa_rag
python -c "import nbformat as f; from nbclient import NotebookClient as C; nb=f.read('accessible_text_analyst.ipynb',4); c=C(nb,timeout=None); c.create_kernel_manager(); c.start_new_kernel(); c.start_new_kernel_client(); [c.execute_cell(x,i) for i,x in enumerate(nb.cells[:40])]; f.write(nb,'accessible_text_analyst.ipynb'); c.km.shutdown_kernel(now=True)"
```

Questa è una pipeline sequenziale con stato globale condiviso. **Non riordinare le celle, e non eseguirle fuori sequenza.** Il notebook scrive `export_results/<project>/sentences.csv`, `paragraphs.csv`, `theses.csv`, `keywords_tfidf.csv`, `paragraphs_with_topics.csv`, `topic_keywords.json`, `entities.csv`, `accessible_text.html`, `accessible_text.docx` e `theses.txt`.

### 2. Report HTML (consigliato)

```bash
python generate_report.py
# → export_results/<project>/analysis_report.html
```

`generate_report.py` legge gli output delle celle direttamente dal file `.ipynb`, quindi il report HTML deve essere generato da un notebook **appena eseguito**. `requirements.txt` elenca `nbstripout` — se è stato attivato nella configurazione git locale, gli output del notebook vengono rimossi al commit. Genera il report _prima_ del commit o disabilita nbstripout per il tuo workflow.

**Controllo della fonte.** Prima di scrivere qualsiasi cosa, `generate_report.py` verifica che gli output del notebook appartengano al `source_file` della configurazione, altrimenti rifiuta (codice di uscita 3, non viene scritto nulla). Tre controlli: il percorso della fonte e la cartella di esportazione stampati dal notebook devono corrispondere alla configurazione, e l'esecuzione salvata deve essere arrivata alla fine della cella di esportazione; `paragraphs.csv` e `sentences.csv` non devono essere più recenti del `.ipynb` (altrimenti gli output dell'ultima esecuzione non sono mai stati salvati — tipico quando si esegue il notebook in VS Code senza salvarlo); e gli inizi di pagina stampati dal notebook devono comparire nel file sorgente (confrontati come sequenza di sole lettere, quindi sillabazioni ricongiunte, numeri di pagina e intestazioni rimossi non contano). Quando il contenuto non si può confrontare — scansioni lette con l'OCR, immagini, URL, livello di testo PDF corrotto — decidono i primi due controlli e la console lo dice. Il report registra anche se omorfi ha partecipato all'esecuzione (`<meta name="ata-omorfi">`); lo legge il Libro del non detto.

Per una vista **diagnostica** strutturata e completa costruita direttamente dalle esportazioni CSV/JSON:

```bash
python generate_diagnostic.py
# → export_results/<project>/diagnostic_report.html
```

`generate_diagnostic.py` legge solo i CSV/JSON esportati, quindi — a differenza di `generate_report.py` — non richiede un notebook appena eseguito, ma solo le esportazioni che il notebook ha scritto. Il risultato è un documento navigabile (indice, intestazioni, elenchi) che copre temi, tesi, entità per tipo e parole chiave principali.

### 3. Markdown adatto a Gemini Notebook (opzionale)

```bash
python generate_md.py
# → export_results/<project>/gemini_notebook_report.md
```

Questo converte il report HTML in un file Markdown con gli span di accessibilità rimossi (Gemini Notebook — in precedenza NotebookLM — non consuma `<span lang="…">`). Eseguilo solo se vuoi caricare il report in Gemini Notebook.

### 4. Post-processore sciamanico senza LLM (opzionale)

```bash
python shamanic_pipeline.py
# → export_results/<project>/audio_scripts/oracle_script.txt
#                                          /raw_roots_chant.txt
#                                          /prophecies.txt
#                                          /lore_fragments/intercepted_log_T*_P*.txt
#                                          /emotional_undertow.txt   # solo se sentiment.csv esiste
```

Genera artefatti testuali rituali direttamente dagli export CSV/JSON del notebook — nessuna chiamata LLM, nessuna rete. Tutte le stringhe provengono da `shamanic_locale.py` e sono completamente localizzate nelle nove lingue supportate. Quando il `sentiment.csv` opzionale è presente, produce anche `emotional_undertow.txt` — una "marea di umore" per paragrafo più un riepilogo di bilanciamento; senza di esso, quel singolo rituale viene semplicemente saltato.

### 5. Post-processore sciamanico LLM (opzionale, richiede una chiave API LLM)

```bash
python shamanic_ai.py
# → export_results/<project>/audio_scripts/katla_entity_monologue.txt
#                                          /vieno_echoes_chant.txt
#                                          /lumi_final_report.txt
#                                          /sami_energetic_spark.txt
```

Richiede la chiave del fornitore scelto (`llm_provider`, predefinito `openai`). Crea `golden_key.env` nella radice del progetto con la chiave che ti serve:

```
OPENAI_API_KEY=sk-...          # llm_provider: openai (default)
OPENROUTER_API_KEY=sk-or-...   # llm_provider: openrouter
LLM_COMPAT_API_KEY=...         # llm_provider: openai_compat (llm_base_url)
```

`golden_key.env` corrisponde a `*.env` in `.gitignore`, quindi non verrà committato. Le quattro voci girano in sequenza:

1. **Katla** trasmuta l'elenco delle entità (`entities.csv`) in un monologo di spiriti settentrionali ghiacciati.
2. **Vieno** intona un canto sull'elenco di parole chiave/argomenti. Per impostazione predefinita vi intreccia cinque frasi grezze dal corpus come echi da un'altra dimensione; quando il `sentiment.csv` opzionale è presente, legge invece l'arco emotivo del testo (umori per paragrafo, sottocampionati per rientrare nel limite di token del modello su corpus lunghi) e lo lascia plasmare la dinamica del canto.
3. **Lumi** legge `prophecies.txt` (obbligatorio) più il monologo di Katla e il canto di Vieno (ornamento opzionale) e produce il dispaccio finale. Le stringhe di fallback localizzate coprono il caso in cui Katla o Vieno manchino.
4. **Sami** legge il rapporto di Lumi e fornisce una sintesi ad alta energia con la scintilla di speranza o un invito all'azione.

### 6. Dispatcher audio sciamanico (opzionale, richiede ElevenLabs)

```bash
python shamanic_voice.py
# → export_results/<project>/audio_scripts/katla_entity_monologue.mp3
#                                          /vieno_echoes_chant.mp3
#                                          /lumi_final_report.mp3
#                                          /sami_energetic_spark.mp3
```

Uno script autonomo a esecuzione singola che legge i quattro artefatti narrativi prodotti da `shamanic_ai.py` e sintetizza ciascuno in un `.mp3` tramite il modello `eleven_multilingual_v2` di ElevenLabs (che rileva automaticamente la lingua parlata, quindi non viene passato alcun parametro di lingua). Registra ogni successo o fallimento sulla console ed esce — non c'è alcun bot, nessun server, nessuna sessione interattiva. Richiede due cose:

- `ELEVENLABS_API_KEY` in `golden_key.env` (lo stesso file che contiene le chiavi LLM).
- una mappatura `voices` in `config.json` / `config.ini` che assegni un ID voce ElevenLabs a ciascuno di `katla`, `vieno`, `lumi`, `sami`. Una voce il cui ID è vuoto o il cui artefatto è mancante viene saltata (esegui prima `shamanic_ai.py`); il fallimento di una voce non interrompe le altre.

> **Privacy e costo.** Come `shamanic_ai.py` con OpenAI, questo script invia il testo degli artefatti a un servizio di terze parti (ElevenLabs) per la sintesi, ed ElevenLabs è un'API **a pagamento**. Il contenuto lascia la tua macchina — non eseguirlo su materiale che non puoi condividere all'esterno.

### 7. Il Libro del non detto (opzionale, solo finlandese, con un agente)

```bash
python ksiega_niedomowien.py scan              # quali cartelle di export_results/ sono idonee
python ksiega_niedomowien.py scan --blocks     # anche blocchi fatti / aperti / rimasti (lento; automatico con --folder)
python ksiega_niedomowien.py status            # avanzamento per cartella: voci, blocchi ovvi, pacchetti aperti
python ksiega_niedomowien.py tidy              # voci sostituite da una voce più recente dello stesso blocco (anteprima; --apply sistema)
python ksiega_niedomowien.py prepare --folder <name> --limit 3
#   → export_results/_kirja_tyotila/<id>/packet.json
python ksiega_niedomowien.py draft <id>        # opzionale: bozza via API + seal, fino a 2 riprove
python ksiega_niedomowien.py seal <id>         # valida draft.json, scrive blind.json
python ksiega_niedomowien.py fill <id>         # opzionale: ipotesi cieche via API, poi judge
python ksiega_niedomowien.py judge <id>        # → export_results/Sanomattomien_kirja.md
# <id> = l'id del pacchetto stampato da prepare, l'inizio del nome della cartella o il percorso della cartella del pacchetto
```

Un gioco costruito su `raw_roots_chant.txt`. Per ogni blocco di 3–6 radici consecutive un LLM scrive una voce di diario finlandese nebulosa con lacune le cui risposte sono porzioni letterali del testo sorgente — devono comparire **sia** in `accessible_text.html` **sia** in `accessible_text.docx`, le due versioni della fonte di verità. Poi un modello separato e cieco prova a riempire le lacune basandosi solo sulla voce; ogni lacuna indovinata è considerata ovvia e il suo frammento viene rimosso. Ciò che resta — KATLA (il sistema di allerta) che legge le radici e VIENO (la narratrice sciamanica) con le lacune non dette — viene aggiunto a `export_results/Sanomattomien_kirja.md`. La chiave delle risposte va in `Sanomattomien_kirja.avain.json` e lo stato in `Sanomattomien_kirja.tila.json`; rieseguire non duplica mai le voci.

Lo script è la metà deterministica (filtri, blocchi, fonte di verità, validazione, giudizio, il Libro). La metà creativa — scrivere `draft.json` — la svolge un agente seguendo `skills/ksiega-niedomowien/SKILL.md` oppure un modello via API con `draft`.

**Filtri di ingresso.** Sono idonee solo le sottocartelle di `export_results/` con un nome finlandese, `<html lang="fi">`, un canto finlandese e nessuna perdita grammaticale; tutto il resto viene rifiutato con un motivo. La riga `roots.header` viene rimossa se presente. Il controllo della *perdita grammaticale* individua i corpora elaborati prima dell'attivazione di omorfi (v1.5.0): sull'intero `keywords_tfidf.csv` conta le forme flesse sopravvissute alla lemmatizzazione e i lemmi spazzatura di spaCy, e rifiuta la cartella oltre 1,0 ogni 100 termini. Richiede omorfi (passo 5 dell'installazione). Quando la cartella ha un `analysis_report.html` aggiornato, il rifiuto per perdita grammaticale dice ciò che il report sa: omorfi ha partecipato all'esecuzione (allora potrebbe essere da correggere il motore stesso — la correzione dei lemmi finlandesi nel notebook; segnala gli esempi), omorfi mancava (installalo e riesegui il notebook) oppure l'esecuzione non aveva alcun passaggio di omorfi. Senza un report aggiornato dice che non si sa.

**Perché solo il finlandese.** Il gioco vive di ciò che la lemmatizzazione lascia non detto, quindi ha senso solo dove ridurre una parola al lemma le toglie un significato reale. Il finlandese è agglutinante: ciò che il polacco o il russo esprimono in parte con preposizioni separate, e l'inglese soprattutto con l'ordine delle parole e le parole funzionali, il finlandese lo racchiude nella parola stessa — quindici casi (`talossa` "nella casa", `talosta` "dalla casa", `taloon` "verso l'interno della casa", `talolle` "alla casa", `talotta` "senza casa"), suffissi possessivi (`taloni` "la mia casa", `talonsa` "la sua/la loro casa"), clitici (`-ko` domanda, `-kin` "anche", `-han` enfasi) e forme verbali che portano insieme persona, tempo, modo e passivo (`tehtäisiinkö` "verrebbe fatto?"). Il canto riduce tutto questo a `TALO` e `TEHDÄ`: spariscono chi, dove, da dove, verso dove, di chi e se — esattamente le lacune che chi ascolta deve riempire. In polacco e in russo il lemma perde la desinenza flessiva, ma buona parte della relazione sta in una parola separata (la preposizione), quindi il lemma non l'ha mai portata da solo; l'inglese perde poco oltre a numero e tempo. L'islandese (quattro casi, in gran parte retti da preposizioni) e l'italiano (preposizioni e articoli, flessione nominale scarsa) sono più vicini rispettivamente al modello polacco-russo e a quello inglese. Tecnicamente lo strumento ha anche bisogno di un analizzatore a dizionario per dimostrare che un canto è privo di grammatica e per ricondurre le radici al testo flesso; in questa pipeline solo il finlandese ne ha uno (omorfi), e le soglie sono state calibrate su corpora finlandesi reali.

**Autore delle bozze via API (`draft`).** Abbassa la soglia d'ingresso: non serve un agente. Lo script invia il pacchetto (il chant, le radici e le frasi della fonte da `truth.sentences`) al fornitore configurato, scrive `draft.json` e lo sigilla; quando `seal` rifiuta la bozza, il modello la riceve indietro insieme alle obiezioni concrete del validatore, fino a 2 riprove (3 tentativi). I codici di uscita sono quelli di `seal` (0 sigillata, 4 ancora rifiutata — correggi l'ultimo `draft.json` a mano o con lo skill). Un `draft.json` esistente non viene mai sovrascritto senza `--force`. Lo skill resta la modalità più forte: riprove illimitate, con l'agente che legge le obiezioni man mano. Una regola non può essere verificata in modo deterministico in nessuna delle due modalità: *non attribuire a persone reali fatti o accuse che non sono nelle frasi della fonte*. La enunciano sia il prompt dell'autore delle bozze sia lo skill, ma niente la controlla — leggi le voci che riguardano persone reali prima di condividerle.

**Indovino cieco (`fill`).** Invia al fornitore configurato solo `blind.json` — mai le risposte né la fonte —, salva `guesses.json` ed esegue subito `judge`. Fornitore: `kirja_llm_provider` (vuoto = `llm_provider`); modello: `kirja_filler_model`; `--provider` / `--model` sostituiscono entrambi. `judge` da solo serve per le ipotesi di un subagente cieco. Sia `draft` sia `fill` chiedono prima uno schema JSON (structured outputs); se l'endpoint lo rifiuta passano alla normale modalità JSON e poi al solo prompt. `fill` riprova due volte quando la risposta è inutilizzabile o manca una lacuna. Ogni risposta inutilizzabile viene salvata nella cartella del pacchetto (`draft_reply_N.txt` / `fill_reply_N.txt`, con `finish_reason` ed eventuale rifiuto), e la console indica dove.

**Collegare la skill.**

- *Claude Code:* copia `skills/ksiega-niedomowien/` in `~/.claude/skills/` (personale) o in `.claude/skills/` nella tua copia del repository. Questo repository esclude `.claude/` tramite `.gitignore`, ed è per questo che la skill è distribuita in `skills/`.
- *App Claude:* comprimi la cartella `ksiega-niedomowien/` in uno ZIP (la cartella stessa deve essere la radice dell'archivio) e aggiungila in **Customize → Skills**; l'esecuzione del codice deve essere attiva e la sessione ha bisogno di accedere alla tua copia del repository, perché gli automi di omorfi e `export_results/` stanno sul tuo disco. Usa la scheda **Code** con una sessione **locale**: nella normale modalità chat o in una sessione cloud, i file letti dall'agente — estratti della fonte inclusi — vengono copiati in un ambiente cloud.
- *Altri agenti:* `SKILL.md` è una semplice procedura in Markdown con intestazione YAML; può seguirla qualsiasi agente in grado di eseguire comandi locali nel repository. Se non può avviare un sottoagente indipendente, usa `fill` per il passo cieco.
- Un assistente solo chat senza esecuzione locale di comandi (ad es. un custom GPT) non può eseguirlo: omorfi e i suoi ~130 MB di automi devono girare accanto ai tuoi dati.

> **Privacy e costo.** Tre livelli, dal minimo al massimo di dati: `fill` invia solo il testo nebuloso della voce (non la fonte); `draft` invia frasi letterali della fonte (`truth.sentences`) e prima della chiamata dice quante sono; un agente che segue lo skill legge estratti della fonte e li invia al proprio fornitore di modelli — e, in una sessione cloud, lavora su una copia dei file nel cloud. Tutte le chiamate API sono a pagamento. Usale solo su materiale che puoi condividere con quei fornitori.

### 8. Helsinki Reacts (opzionale, richiede una chiave API LLM)

```bash
python helsinki_reacts.py <project> [<project> …]
# → export_results/_streams/<project>.md
python helsinki_reacts.py notes.txt             # va bene anche un qualsiasi file di testo
python helsinki_reacts.py <project> --dry-run   # mostra cosa verrebbe inviato, senza inviare nulla
python helsinki_reacts.py <project> --lang en   # lingua della diretta per questa esecuzione
python helsinki_reacts.py <project> --kirja     # aggiunge la voce della cartella nel Libro del non detto
```

Copione satirico di una diretta: Valtteri, streamer di Helsinki, reagisce con la sua chat a una registrazione, e Lumi, una fredda voce di sintesi, legge le donazioni. L'input è il nome di una cartella di `export_results/` (il testo del suo `accessible_text.html` senza markup e titoli) o un qualsiasi file di testo; il copione viene scritto in `export_results/_streams/<nome>.md`, e una nuova esecuzione con lo stesso nome aggiunge `_2`, `_3`.

**Il prompt è tuo.** Il prompt di sistema non è nel codice: quello predefinito, `helsinki_reacts.example.md`, è volutamente essenziale. Copialo in `helsinki_reacts.md` (è in `.gitignore` e viene usato automaticamente quando esiste) e cambia quello che vuoi, oppure indica un file qualsiasi con `--prompt`. Una regola in più o in meno cambia molto la diretta, quindi confronta alcune esecuzioni prima di scegliere una versione. Lo script aggiunge da sé solo ciò che deve funzionare qualunque cosa dica il prompt: la registrazione, la lingua di uscita e — con `--kirja` — il blocco del Libro del non detto.

**Lingua.** `--lang`, poi `reacts_lang` dal config, poi `ui_lang`. Il finlandese dà la diretta stessa, in finlandese corrente; ogni altra lingua ne dà la traduzione, in cui le brevi interiezioni finlandesi restano non tradotte.

**Il Libro del non detto (`--kirja`).** Per una cartella con una voce in `Sanomattomien_kirja.md` la chat riceve il testo nebbioso della voce e le ipotesi mancate del riempitore cieco come teorie su cui litigare. La chiave delle risposte non arriva mai al modello, e una regola fissa impedisce a Valtteri di confrontare una lacuna con la registrazione, perché le lacune nascondono parole della stessa registrazione. Senza una voce, la diretta nasce senza il Libro.

Provider e modello: `reacts_llm_provider` / `reacts_model` (vuoti = `llm_provider` / `llm_model`), sostituiti da `--provider` / `--model`; impegno di ragionamento predefinito `low` (`--effort`). Una risposta più breve di `--min-chars` (1500) viene scartata come rifiuto e stampata nella console.

> **Privacy e costo.** L'intero testo di ogni registrazione va al provider configurato, che è un'API a pagamento; lo script lo dice prima della prima chiamata. Il risultato è una satira sul materiale scritta dall'IA: leggila prima di condividerla, soprattutto se nomina persone reali — nulla verifica che cosa il modello attribuisce loro.

## Output

Ogni corpus analizzato ottiene la propria sottodirectory sotto `export_results/`, denominata in base al file sorgente (percorso ed estensione rimossi) o in base a un `domain_slug` per gli URL. Il corpus di esempio integrato usa `export_results/_default/`.

Ogni sottodirectory contiene:

| File                            | Prodotto da       | Descrizione                                       |
|---------------------------------|-------------------|---------------------------------------------------|
| `sentences.csv`                 | notebook          | ogni frase con il suo indice e la sua lingua (`lang`) |
| `paragraphs.csv`                | notebook          | paragrafi (3–6 frasi ciascuno)                    |
| `theses.csv`, `theses.txt`      | notebook          | una tesi per paragrafo (la frase a TF-IDF più alto); il nome del file `.txt` segue la lingua del corpus (es. `tezy.txt` per il polacco, `тезисы.txt` per il russo) |
| `keywords_tfidf.csv`            | notebook          | parole chiave (uni/bi/trigrammi) con pesi TF-IDF  |
| `paragraphs_with_topics.csv`    | notebook          | paragrafi con il loro argomento KMeans assegnato  |
| `topic_keywords.json`           | notebook          | parole chiave per argomento                       |
| `entities.csv`                  | notebook          | tutte le entità nominate e le loro etichette      |
| `language_spans.csv`            | notebook          | segmenti in lingua straniera: documento, offset dei caratteri, lingua, `block` o `inline`, testo |
| `sentiment.csv`                 | notebook *(opzionale)* | sentiment per paragrafo (`para_id`, `label`, `score`, `lang`) — solo quando `enable_sentiment` è `true`; alimentazione per lo strato sciamanico, mai mostrato all'utente |
| `accessible_text.html`          | notebook          | `lang` su ogni paragrafo più `<span lang>` su ogni frase straniera e ogni inserto (citazione, nome) — i lettori di schermo cambiano voce automaticamente per frammento |
| `accessible_text.docx`          | notebook          | lo stesso contenuto con `<w:lang>` impostato per `Run` (`pl-PL`, `ru-RU`, `en-US`, `it-IT`, `fi-FI`, `is-IS`, `de-DE`, `es-ES`, `fr-FR`) — Word e SAPI lo usano offline, senza rilevatore online |
| `analysis_report.html`           | `generate_report.py` | report HTML globale accessibile                |
| `diagnostic_report.html`         | `generate_diagnostic.py` | report diagnostico strutturato (temi, tesi, entità per tipo, parole chiave) dalle esportazioni CSV/JSON |
| `gemini_notebook_report.md` | `generate_md.py`     | Markdown pronto per Gemini Notebook (in precedenza NotebookLM) |
| `audio_scripts/*.txt`           | `shamanic_pipeline.py`, `shamanic_ai.py` | artefatti testuali rituali / narrativi |
| `audio_scripts/*.mp3`           | `shamanic_voice.py` *(opzionale)* | le quattro voci narrative sintetizzate in audio tramite ElevenLabs |

## Accessibilità

Questo è il valore centrale del progetto. Tutto ciò che segue è intenzionale e deve essere preservato quando la pipeline viene modificata:

- **Niente colori ANSI, emoji o pseudografica in stdout.** Un lettore di schermo legge ogni carattere alla lettera — `[OK]` invece di "🟢", `---` invece di "───━━━".
- **Barre di progresso silenziate** (`tqdm`, `transformers`, `torch`) — `cell_model._silence_hf_progress()` silenzia le barre di caricamento e gli avvisi di Hugging Face/torch prima di scaricare IceBERT e icelandic-ner-bert per l'islandese; `cell_corpus._silence_ocr_progress()` fa lo stesso per i motori OCR.
- **Marcatura `lang` per paragrafo, per frase e per segmento nell'export.** `accessible_text.html` e `accessible_text.docx` portano un codice ISO 639-1 su ogni paragrafo, su ogni frase straniera e su ogni inserto straniero (una citazione o un nome dentro una frase). NVDA, JAWS, Narrator, VoiceOver, Word e SAPI rispettano questi tag e cambiano voce automaticamente — anche offline.
- **Marcatura inglese cablata nel report HTML.** `generate_report.py` avvolge sempre i frammenti tecnici inglesi — tag POS (`NOUN`, `VERB`, `ADJ`), etichette NER (`PER`, `ORG`, `[orgName]`), identificativi dei modelli spaCy / Hugging Face, percorsi ASCII, blocchi di codice — in `<span lang="en">`, così non vengono più pronunciati con la voce russa predefinita del documento.
- **Marcatura per frammento del corpus straniero in HTML.** Quando il corpus non è russo, gli output strutturati (estratti di frasi, elenchi di parole chiave, parole di argomenti, righe di ranking RAG, tabelle di lemmatizzazione) vengono avvolti in `<span lang="target_lang">`.
- **Struttura HTML lineare** (`<main>`, gerarchia di intestazioni corretta).

### Leggere l'output come utente non russofono

La narrazione del notebook e l'output `print()` della maggior parte delle celle sono scritti in russo. Due caratteristiche dell'interfaccia Jupyter lo rendono ostile per gli utenti non russofoni che usano screen reader, e la pipeline include una soluzione specifica per ciascuna:

- **Jupyter nel browser codifica forzatamente `lang="en"` sul documento**, e il prompt "Tradurre questa pagina?" non appare comunque mai per le pagine su `localhost`. Un notebook con narrazione russa viene quindi letto con voce TTS inglese — caos totale. La soluzione pragmatica è l'**estensione Jupyter per VS Code**: la sua vista a lista annuncia solo le etichette `code cell` / `markdown cell` senza tag ISO, puoi premere Invio sulle celle di codice e ↓ saltare le celle markdown senza ascoltarne il contenuto, e il problema dell'inglese cablato è confinato alla vista output (`Ctrl+Shift+↓`), che puoi semplicemente non aprire.
- **`generate_report.py` è praticamente obbligatorio per i lettori non russofoni.** Produce `analysis_report.html` con `<html lang="ru">` e l'insieme completo dei tag `<span lang="…">` per ogni frammento. Aperto in un vero browser (non dentro Jupyter), attiva il prompt "Tradurre questa pagina?" del browser per la narrazione russa, mantenendo allo stesso tempo il cambio di voce TTS sui frammenti del corpus e sui termini tecnici inglesi (POS, NER, nomi dei modelli).
- **Il Q&A interattivo scrive `qa_results.html` e lo apre per te.** `cell_qa_rag` continua a stampare la domanda e i top-3 risultati su stdout — ma scrive anche lo stesso contenuto in `export_results/<project>/qa_results.html` e chiama `webbrowser.open()`, così la pagina si apre nel browser di sistema, dove sia la traduzione che il cambio di voce TTS per frammento funzionano. La vista output in Jupyter, dove `lang="en"` cablato rende gli involucri russi illeggibili per uno screen reader, non è quindi più l'unica via verso il risultato. Ogni nuova query sovrascrive il file.

## Limitazioni note

- **L'origine dei prestiti non viene marcata.** La marcatura linguistica (gli attributi `lang`, vedi *La lingua di ogni parola*) copre le parole che il dizionario di un'altra lingua elencata conosce e i frammenti scritti in un alfabeto straniero: lettere greche, caratteri latini dentro un testo cirillico. Un indicatore esplicito di origine (`греч.`, `łac.`, `z niemieckiego`, `имеет греческое происхождение`) non viene collegato alla parola presa in prestito, e una parola traslitterata nell'alfabeto del testo (`фразис` in un testo russo) mantiene la lingua del corpus. Questi indicatori non hanno una forma fissa (abbreviazione, aggettivo, un'intera locuzione), e marcare il cirillico `фразис` come greco farebbe passare lo screen reader a una voce greca, che suona peggio della voce russa predefinita.
- **Finlandese: la prima parola della frase.** All'inizio di una frase ogni parola ha la maiuscola, e il tagger di spaCy a volte scambia un imperativo o un'interiezione per un nome proprio: `Anna kuulua.` («lascia che si senta») diventa il nome *Anna*, `Oota, miten…` («aspetta, come…») il nome *Oota*. La correzione di omorfi non sovrascrive mai una parola marcata come nome, perché altrimenti i nomi veri diventerebbero parole comuni (*Tuskia* → *tuska*, «angoscia»). Una parola del genere conserva la sua forma scritta come lemma e può comparire negli elenchi dei lemmi, nelle parole chiave e nel canto delle radici (`anna`, `oota`). Quando il tagger considera la parola un'interiezione, omorfi fornisce il verbo (*Oota* → `oottaa`, dalla v1.11.1). Il controllo della perdita grammaticale del Libro del non detto non conta una parola chiave che la fonte usa anche come nome a metà frase (*Anna Maria …*).
- **Nomi scritti senza segni diacritici.** Un nome straniero viene etichettato solo quando la grafia stessa ne dà la prova: lettere che l'alfabeto di base non ha (`Kaczyński`), una forma che conosce solo il lessico di un'altra lingua elencata, oppure un'altra scrittura (`Качиньский` viene etichettato come russo). Molte redazioni tolgono i segni diacritici dai nomi stranieri. Nei titoli RSS raccolti il 15 novembre 2026 (Google News per paese e i feed dei portali stessi), le testate finlandesi hanno scritto *Swiatek* in 8 titoli su 8 e *Kaczynski* in 2 su 3, anche se *Wałęsa* ha conservato le sue lettere in 6 su 7; nei titoli francesi, italiani, spagnoli e svedesi la forma senza segni prevaleva per almeno due di questi tre nomi, mentre le testate tedesche e inglesi conservavano per lo più le lettere e quelle russe traslitterano in cirillico. Un nome senza segni, forme flesse comprese (*Kaczynskin*), è fatto solo di lettere dell'alfabeto di base e in quella forma non compare in nessun lessico, quindi resta nella lingua di base e lo legge la voce di base, qualunque cosa elenchi `corpus_languages`. Il testo da solo non lo decide, e ATA non indovina le lettere tolte: confrontare ogni parola sconosciuta fatta di lettere di base con lessici stranieri privati dei diacritici farebbe cambiare voce anche su parole comuni. Anche un nome di una lingua che qui non ha un pacchetto (*Erdoğan*) resta nella lingua di base.

## Layout del repository

```
accessible_text_analyst/
├── accessible_text_analyst.ipynb   # pipeline principale (42 celle)
├── generate_report.py              # generatore di report HTML (vista lettore)
├── generate_diagnostic.py          # report HTML diagnostico dalle esportazioni CSV/JSON
├── generate_md.py                  # convertitore Markdown per Gemini Notebook
├── shamanic_pipeline.py            # opzionale: post-processore rituale senza LLM
├── shamanic_ai.py                  # opzionale: narratori rituali LLM
├── llm_klient.py                   # scelta del fornitore LLM e della chiave (condivisa)
├── shamanic_voice.py               # opzionale: dispatcher audio ElevenLabs (esecuzione singola)
├── shamanic_locale.py              # pacchetto di localizzazione per lo strato sciamanico
├── ksiega_niedomowien.py           # opzionale: il Libro del non detto (solo finlandese)
├── helsinki_reacts.py              # opzionale: copioni delle dirette Helsinki Reacts (LLM)
├── helsinki_reacts.example.md      # prompt predefinito di Helsinki Reacts (versionato)
├── helsinki_reacts.md              # la tua copia del prompt (in .gitignore)
├── skills/ksiega-niedomowien/SKILL.md  # skill dell'agente per ksiega_niedomowien.py
├── config.example.json             # template di configurazione, estensione JSON (versionato)
├── config.example.ini              # template di configurazione, estensione INI (versionato)
├── config.json / config.ini        # la tua configurazione locale (gitignored)
├── golden_key.env                  # chiavi LLM ed ElevenLabs (gitignored)
├── requirements.txt                # dipendenze pip
├── CLAUDE.md                       # guida per Claude Code
├── README.md                       # README canonico (in inglese)
├── README_pl.md, README_ru.md, …   # traduzioni (collegamento di ritorno in alto)
├── VERSION                         # ciclo di release in preparazione (`X.Y.Z-WIP` fino al rilascio)
├── release_notes.md                # release notes in ordine cronologico inverso
└── export_results/                 # risultati dell'analisi (gitignored)
    ├── Sanomattomien_kirja.md      # il Libro del non detto, aggiornato in modo incrementale
    ├── _streams/                   # copioni di Helsinki Reacts
    └── <project_name>/
        ├── sentences.csv
        ├── paragraphs.csv
        ├── theses.csv
        ├── theses.txt              # nome localizzato per lingua del corpus
        ├── accessible_text.html
        ├── accessible_text.docx
        ├── analysis_report.html
        ├── diagnostic_report.html
        ├── gemini_notebook_report.md
        └── audio_scripts/…
```

## Licenza

Rilasciato sotto [licenza MIT](LICENSE). La pipeline è distribuita solo come sorgente — niente binari — e il notebook è per sua natura modificabile cella per cella tramite il browser o l'estensione Jupyter per VS Code. La licenza MIT rende semplicemente esplicito ciò che il formato già implica.
