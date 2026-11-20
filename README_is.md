# Accessible Text Analyst

Fjöltyngd NLP-leiðsla hönnuð með **aðgengi fyrir skjálesara** í huga (NVDA, JAWS, VoiceOver, Narrator). Allur kóði, úttak í skel og skýrslur eru sett upp þannig að hjálpartæknin geti lesið þau hreint: engir ANSI-litir, engin tjáningartákn (emoji), engar framvinduslíkur, engin gervigrafík.

> **Önnur tungumál:** [English](README.md) · [polski](README_pl.md) · [русский](README_ru.md) · [suomi](README_fi.md) · [italiano](README_it.md) · [Deutsch](README_de.md) · [español](README_es.md) · [français](README_fr.md)

> **i18n staða (v1.0).** Aðeins README hefur verið þýtt. Frásögn í minnisbókinni, allt skel-úttak, `CLAUDE.md` og athugasemdir í kóða halda sínum upprunalegu tungumálum (aðallega rússnesku; í patchum og shamanísku lagi pólsku). Þýðing á öðru er meðvitað frestað til v1.1 — sjá `release_notes.md`.

## Innihald verkefnisins

- `accessible_text_analyst.ipynb` — Jupyter-minnisbók með heilli greiningarleiðslu (42 hólf: 21 kóða + 21 markdown; frásögnin innan minnisbókarinnar er á rússnesku). Hún skrifar tvö aðgengisgripi (`accessible_text.html`, `accessible_text.docx`), þar sem hver málsgrein og hver erlend setning ber sitt eigið `lang`-eiginleika — skjálesarar og TTS-vélar skipta um rödd sjálfkrafa, jafnvel án nets.
- `generate_report.py` — eftirvinnsluforrit sem breytir framkvæmdri minnisbók í eina aðgengilega HTML-skrá (`analysis_report.html`). Það vefur erlend brot inn í `<span lang="target_lang">` og — óháð tungumáli safnsins — þvingar `<span lang="en">` utan um tæknilegt enskt innihald (POS-merki, NER-merki, auðkenni spaCy/Hugging Face líkana, ASCII-skráarnöfn). Inline-kóði og kóðablokkir í frásögn fá öll `lang="en"` í einu lagi. Í lesendaham (`remove_noise: true`) styttir það skjalkvíslar greiningarlykkjur minnisbókarinnar niður í fyrstu fáu skjölin í stað þess að prenta hundruð.
- `run_all.py` — ræsir fyrir alla ókeypis staðbundnu keðjuna: skráir Jupyter-kjarnann `analyst_env` ef hann vantar, keyrir minnisbókina án viðmóts (án gagnvirka spurningahólfsins) og vistar úttak hennar í `.ipynb`, keyrir svo `generate_report.py`, `shamanic_pipeline.py` og, fyrir finnskt textasafn, `scan` fyrir Bók hins ósagða. Hann ræsir aldrei greitt skref (LLM-helgisiði, ElevenLabs-raddir, `draft`/`fill` bókarinnar).
- `generate_diagnostic.py` — sjálfstæður smiður á heildstæðri **greiningarskýrslu** (`diagnostic_report.html`) sem byggð er beint á CSV/JSON-útflutningi minnisbókarinnar (ekki á úttaki `generate_report.py`). Aðgengileg uppbygging fyrir skjálesara: efnisyfirlit `<nav>` ásamt köflum — hver með eigin fyrirsögn og listum — fyrir yfirlit, þemu með málsgreinum, tesur, nafngreinda nafnliði eftir tegund og helstu lykilorð. Byggingartextar fylgja `ui_lang`; brot úr safninu fá `<span lang="…">`, NER-merki `<span lang="en">`.
- `generate_md.py` — breytir `analysis_report.html` í `gemini_notebook_report.md` fyrir Gemini Notebook (áður NotebookLM). Aðgengis-spans eru afpökkuð því Gemini Notebook notar þau ekki.
- `shamanic_pipeline.py` *(valfrjálst)* — eftirvinnsluforrit án LLM sem breytir CSV/JSON-útflutningi minnisbókarinnar í helgisiðatextagripi (`oracle_script.txt`, `lore_fragments/`, `raw_roots_chant.txt`, `prophecies.txt` og — þegar valfrjáls tilfinningagreining er virk — `emotional_undertow.txt`), öll að fullu staðfærð fyrir níu studdu tungumálin.
- `shamanic_ai.py` *(valfrjálst, byggt á LLM)* — kallar í LLM (sjálfgefið OpenAI; OpenRouter eða hvaða OpenAI-samhæfða slóð sem er gegnum `llm_provider`) til að búa til fjórar frásagnarraddir (`Katla`, `Vieno`, `Lumi`, `Sami`) ofan á sömu útflutninga. Þegar valfrjálsa `sentiment.csv` er til staðar byggir Vieno söng sinn á tilfinningabogadrætti textans í stað hráu setninganna. Krefst lykils valinnar þjónustu í `golden_key.env`.
- `shamanic_voice.py` *(valfrjálst, krefst ElevenLabs)* — sjálfstæður afgreiðari sem keyrir einu sinni og myndgerir frásagnargripina fjóra sem `shamanic_ai.py` bjó til í `.mp3`-hljóð gegnum ElevenLabs API-ið, skráir hvern árangur/villu í skelina og hættir svo (enginn botni, enginn þjónn). Þarf `ELEVENLABS_API_KEY` í `golden_key.env` og `voices`-vörpun í stillingunum.
- `shamanic_locale.py` — staðfærsluböggull fyrir bæði shamanísku forritin (sniðmát, hausa og fallback-strengi Lumi á öllum níu tungumálum).
- `ksiega_niedomowien.py` *(valfrjálst, aðeins finnska, með aðstoð gervigreindarþjóns)* — Bók hins ósagða (*Sanomattomien kirja*): breytir `raw_roots_chant.txt` í dulkóðaða dagbók sem vex smám saman, með eyðum sem blint líkan gat ekki giskað á. Þetta er ákveðinn (deterministic) hjálpari fyrir hæfnina í `skills/ksiega-niedomowien/SKILL.md`; skelúttakið fylgir `ui_lang`.
- `helsinki_reacts.py` *(valfrjálst, með LLM)* — háðskt handrit að streymi: Valtteri frá Helsinki bregst ásamt finnsku spjalli við upptöku (útflutningsmöppu eða textaskrá). Kerfisfyrirmælin eru utan kóðans (`helsinki_reacts.example.md`, eigið eintak í `helsinki_reacts.md`) og tungumál streymisins fylgir `ui_lang`. Krefst lykils valinnar þjónustu í `golden_key.env`.

## Hvað gerir leiðslan

1. Hleður texta úr skrá (`.pdf`, `.txt`, `.docx`, `.md`, `.html` eða myndum: `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`, `.webp`) eða úr URL — fjarlægir endurteknar haus-/fótlínur, hliðarspjöld, „Related articles"-kafla og álíka kjarna. Skannaðar PDF-skrár og myndainntak eru lesin með OCR: hvert tungumál í `corpus_languages` les síðuna með eigin vél (OCR sem er innbyggt í Windows 10/11, eða Tesseract fyrir tungumál sem Windows hefur ekki — nú íslensku), RapidOCR les hana einu sinni enn til vara, og orðasafn hvers tungumáls velur orðabókarmyndir úr öllum lestrum.
2. Ákveður tungumál hvers orðs út frá orðasöfnum tungumálanna í `corpus_languages` (sjá **Tungumál hvers orðs**): grunntungumálið stýrir spaCy-leiðslunni, og erlendar tilvitnanir og nöfn verða að tungumálabútum.
3. Keyrir spaCy einu sinni á hvern textahluta: líkan grunntungumálsins vinnur grunntextann ásamt erlendum innskotum, og hverja erlenda blokk vinnur líkan hennar eigin tungumáls, sem er hlaðið eftir þörfum gegnum `get_nlp()` (vafið í `functools.lru_cache(maxsize=2)`, svo að í skyndiminni eru í mesta lagi tvö líkön). Engin endurskipting í setningar og engin önnur fjöltyngd umferð.
4. Tókun → sía stop-orða → uppslátt → POS-merking → NER, hvert tákn greint með líkani síns eigin tungumáls.
5. Vektorframsetning: Bag of Words, TF-IDF + sjálfsfyrirspurnaleit með cosinus-röðun.
6. Bygging: setningar → málsgreinar (3–6 setningar hver) → meginsetningar (besta setning per málsgrein). Hver setning ber tungumál sitt og erlend innskot sín; hver málsgrein ber ríkjandi tungumál sitt.
7. Þemamódel með KMeans yfir málsgreinavektorum spaCy.
8. *(Valfrjálst, slökkt sjálfgefið)* Tilfinningamat per málsgrein með `cardiffnlp/twitter-xlm-roberta-base-sentiment`, skrifað í `sentiment.csv`. Niðurstaðan er aldrei sýnd notandanum — hún er aðeins til sem fóður fyrir shamaníska lagið. Sjá **Stillingar** (`enable_sentiment`).
9. CSV/JSON-útflutningur + textaleg samantektarskýrsla + aðgengilegt HTML og DOCX + heildar HTML-skýrsla (`analysis_report.html`).

## Studd tungumál

| Kóði | Tungumál   | spaCy-líkan            | NER / vektorar |
|------|------------|------------------------|----------------|
| pl   | pólska     | `pl_core_news_lg`      | spaCy          |
| ru   | rússneska  | `ru_core_news_lg`      | spaCy          |
| en   | enska      | `en_core_web_lg`       | spaCy          |
| it   | ítalska    | `it_core_news_lg`      | spaCy          |
| de   | þýska      | `de_core_news_lg`      | spaCy          |
| es   | spænska    | `es_core_news_lg`      | spaCy          |
| fr   | franska    | `fr_core_news_lg`      | spaCy          |
| fi   | finnska    | `fi_core_news_lg`      | spaCy          |
| is   | íslenska   | `spacy.blank("is")` + Hugging Face | `mideind/IceBERT` (vektorar), `grammatek/icelandic-ner-bert` (NER) |

Það er ekkert fullt spaCy-líkan fyrir íslensku, því eru tvö Hugging Face líkön tengd inn í auða leiðslu. Fyrsta niðurhal krefst ~1,3 GB á diski og nettenginga; síðari keyrslur nota HF-skyndiminni.

**Valfrjáls endurbót á finnskri beygingarfræði (omorfi).** Tölfræðilega lemmunarvélin í `fi_core_news_lg` ræður illa við finnska viðskeytabeygingarfræði — hún framleiðir reglulega ruslmyndir eins og *kytköknen* eða *pisttää*. Þegar hreini Python-pakkinn `omorfi` er uppsettur og FST-stýrivélar hans sóttar (sjá Uppsetningu, skref 5), bætir minnisbókin við íhlutnum `omorfi_lemmas`, sem skiptir út lemmum og UD-beygingareinkennum fyrir orðabókargreiningar alls staðar þar sem þær eru sammála orðflokki spaCy-taggarans (`kytköksistä` → `kytkös`, `Euroopassa` → `Eurooppa`, `pistät` → `pistää`). Án pakkans eða stýrivélanna heldur leiðslan hljóðlega venjulegri spaCy-hegðun.

## Tungumál hvers orðs

Þú telur upp tungumál textans í `corpus_languages` (`config.json`; gamla heitið `ocr_languages` er enn lesið). Út frá orðasöfnum þessara tungumála ákveður minnisbókin:

1. **Grunntungumál** (`LANG`) — tungumálið sem orðasafnið þekkir stærstan hluta orða safnsins hjá (hlutföllin eru prentuð). Það stýrir aðal-spaCy-leiðslunni.
2. **Tungumál hvers orðs** (`odcinki_jezykowe.py`). Orð sem grunnorðasafnið þekkir ekki en orðasafn annars upptalins tungumáls þekkir tilheyrir því tungumáli; orð sem fleiri þeirra þekkja fer í minnsta stafrófið sem rúmar alla stafi þess — þannig tekur pólska orðasafnið, sem þekkir margar enskar orðmyndir, ekki til sín ensk orð, en `Łódź` helst pólskt. Letrið er staðreynd: orð með kýrillísku letri í latneskum texta fær kýrillískt tungumál, jafnvel þótt ekkert slíkt sé talið upp.
3. **Erlendir bútar** — að minnsta kosti tvö samliggjandi erlend orð sama tungumáls innan setningar, eða eitt orð með stöfum sem grunnstafrófið vantar. Bútur sem nær yfir heilar setningar er **blokk** og eigið spaCy-líkan hans vinnur hann (setningar, NER, lemmur). Bútur inni í setningu á grunntungumálinu er **innskot**: setningin verður áfram hjá grunnlíkaninu, en innskotið fær lemmur sínar og POS-merki frá líkani síns eigin tungumáls.

Útflutningurinn ber niðurstöðuna: `<span lang="…">` í `accessible_text.html` og sérstakt `Run` með `<w:lang>` í `accessible_text.docx` fyrir hverja erlenda setningu og hvert innskot, svo að skjálesari skiptir um rödd nákvæmlega á tilvitnuninni eða nafninu, ekki á allri setningunni. Allir bútar eru líka taldir upp í `language_spans.csv`, og `sentences.csv` hefur dálkinn `lang`.

Orðasöfn: spaCy-vigrar (endanlegur listi orðmynda) fyrir pólsku, ensku, rússnesku, ítölsku, þýsku, spænsku og frönsku; `omorfi` fyrir finnsku; BÍN (`islenska`) fyrir íslensku — sömu orðasöfn og OCR-kosningin notar. Með eitt tungumál í `corpus_languages` er ekkert orðasafn hlaðið og aðeins orð með öðru letri eru merkt. Vanti orðasafn stöðvast keyrslan með skilaboðum sem segja hvernig á að laga það.

**Hvaða tungumál á að telja upp.** Mælt á 20 finnskum uppskriftum (55.000 orð) þar sem mörg pólsk nöfn koma fyrir: með `["fi", "en"]` finnur minnisbókin 34 enska búta (hugtök og tilvitnanir); með `["fi", "pl", "en"]` finnur hún að auki 57 pólska búta — pólsk nöfn og nokkur pólsk orðasambönd, sem nú les pólsk rödd í stað finnskrar — og ekkert enskt orð fer til pólsku. Þess vegna:

- teldu upp hvert tungumál sem **tilvitnanir** í textanum eru á;
- fyrir texta skrifaðan á einu tungumáli sem nefnir **nöfn** úr öðru (pólsk nöfn í finnskum texta), bættu við tungumáli nafnanna: nöfn í grunnmynd og nöfn með stöfum sem grunnstafrófið vantar (`ł`, `ś`) les þá rödd þeirra eigin tungumáls. Nafn sem er beygt eingöngu með stöfum grunnstafrófsins (`Kowalskille`) helst hvort eð er í grunntungumálinu;
- ekki telja upp tungumál sem kemur ekki fyrir í textanum: það bætir aðeins við fölskum kandídötum.

**Hvers vegna ekki tölfræðilegur greinir.** Fram að ATA 1.x flokkaði `lingua-language-detector` heilar setningar. Á sömu uppskriftum merkti hann 127 setningar sem erlendar, nær allar ranglega; varnarreglurnar sem þurfti til að bæla það niður skildu eftir 2 setningar og enga af ensku tilvitnununum. ATA 2.0 fjarlægði hann. Heildarskýrslan (`generate_report.py`) merkir erlend orð í rússnesku frásögninni með sömu orðasöfnum (tungumálin úr `corpus_languages` auk ensku).

## Kröfur

- Python 3.12 eða nýrri (pakkarnir eru prófaðir á Python 3.14).
- ~1,5 GB af lausu plássi fyrir spaCy `_lg`-líkön (eitt per tungumál). Bættu við ~1,3 GB ef þú vilt íslenskustuðning (Hugging Face `transformers` + `torch` + IceBERT + icelandic-ner-bert). Íslenska NER-greiningin les allt skjalið í gluggum sem skarast: um 4.000 stafir á sekúndu á CPU, svo bók (1 MB af íslenskum texta) tekur nokkrar mínútur.
- OCR-stuðningur (valfrjáls): `winrt-*`-pakkarnir (undir 1 MB) og, fyrir hvert tungumál í `corpus_languages`, tungumálapakki Windows með ljóslestri (Stillingar > Tími og tungumál > Tungumál og svæði); `rapidocr` með `onnxruntime` (líkönin, um 40 MB, sækjast við fyrsta OCR-kall); fyrir tungumál án Windows-vélar (nú íslensku) `tesserocr` og tessdata_best-líkan tungumálsins í `tessdata`-möppu geymslunnar (íslenska: https://github.com/tesseract-ocr/tessdata_best/raw/main/isl.traineddata, um 9,5 MB) ásamt orðasafninu `islenska` (~62 MB). OCR þarf ekki lengur `torch`. Ef vél eða orðasafn vantar stöðvast keyrslan með skilaboðum sem segja hvernig á að laga það. Íslenskt orðasafn: Beygingarlýsing íslensks nútímamáls (BÍN), Stofnun Árna Magnússonar í íslenskum fræðum, höfundur og ritstjóri Kristín Bjarnadóttir, CC BY-SA 4.0.
- Bættu við ~130 MB ef þú vilt endurbót á finnskri beygingarfræði (FST-stýrivélar `omorfi`, sóttar með `omorfi-download`).
- Nettenging við fyrstu keyrslu (niðurhal líkana).

## Uppsetning umhverfis

Veldu einn af þremur valkostum hér að neðan. Allir enda á sömu `pip install -r requirements.txt` og niðurhali spaCy-líkana.

### Valkostur A — staðbundið `venv` (mælt með í daglegri notkun)

```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
```

`.venv/` mappan er í `.gitignore`. Frá virkri venv haltu áfram í **Uppsetning** að neðan.

### Valkostur B — Anaconda / Miniconda

```bash
conda create -n accessible-text-analyst python=3.14
conda activate accessible-text-analyst
```

Síðan haltu áfram í **Uppsetning**. Sá `pip` sem fylgir Anaconda virkar vel — það er enginn sérstakur Conda-pakkalisti fyrir þetta verkefni.

### Valkostur C — Google Colab (engin staðbundin uppsetning)

Opnaðu nýja Colab-minnisbók og límdu eftirfarandi í fyrsta hólfið:

```python
!git clone https://github.com/<your-fork>/accessible_text_analyst.git
%cd accessible_text_analyst
!pip install -r requirements.txt
!python -m spacy download en_core_web_lg
# Bættu við línum að neðan aðeins fyrir tungumál sem þú þarft í raun:
# !python -m spacy download pl_core_news_lg
# !python -m spacy download ru_core_news_lg
# !python -m spacy download it_core_news_lg
# !python -m spacy download fi_core_news_lg
# !python -m spacy download de_core_news_lg
# !python -m spacy download es_core_news_lg
# !python -m spacy download fr_core_news_lg
```

Síðan halaðu upp `config.json` (eða `config.ini`) í gegnum Files-spjaldið, stilltu `source_file` og keyrðu minnisbókina. Athugið: Colab-lotur eru skammlífar — niðurhaluð líkön og `export_results/`-gripi hverfa þegar runtime er endurræst. Fyrir lengri greiningu skaltu tengja Google Drive og skrifa úttakið þangað.

## Uppsetning

```bash
# 1. Python-pakkar
pip install -r requirements.txt

# 2. spaCy-líkön — settu aðeins upp þau tungumál sem þú þarft í raun.
# *_lg-afbrigðin eru nauðsynleg því þemamódel byggir á orðavektorum.
python -m spacy download pl_core_news_lg
python -m spacy download ru_core_news_lg
python -m spacy download en_core_web_lg
python -m spacy download it_core_news_lg
python -m spacy download fi_core_news_lg
python -m spacy download de_core_news_lg
python -m spacy download es_core_news_lg
python -m spacy download fr_core_news_lg

# 3. (Valfrjálst) Íslenskustuðningur — afkommenta `transformers` og
# `torch` í requirements.txt og keyrðu aftur `pip install -r requirements.txt`.
# IceBERT og icelandic-ner-bert eru þá sótt frá Hugging Face við fyrstu keyrslu.

# 4. (Valfrjálst) Tilfinningagreining — afkommenta `transformers`, `torch`,
# `sentencepiece`, `protobuf` og `tiktoken` í requirements.txt, keyrðu aftur
# uppsetninguna og stilltu "enable_sentiment": true í config.json. Líkanið
# (~1.1 GB) er sótt frá Hugging Face við fyrstu keyrslu og geymt í skyndiminni eftir það.
# Alla fimm pakkana þarf saman til að byggja XLM-RoBERTa-tókarann.

# 5. (Valfrjálst) Endurbót á finnskri beygingarfræði — afkommenta `omorfi`
# í requirements.txt, keyrðu uppsetninguna aftur og sæktu síðan FST-stýrivélarnar
# (~130 MB af *.hfst-skrám sem pakkast upp í rót verkefnisins; þær eru í .gitignore).
# Keyrðu úr rót verkefnisins:
omorfi-download

# 6. (Valkvætt) Berðu uppsettar útgáfur saman við mörkin í
# requirements.txt og við PyPI. Skriftan varar aðeins við, hún stöðvar ekkert:
python audyt_zaleznosci.py
```

## Stillingar

Afritaðu sýnishornsstillingarnar í staðbundna skrá. Bæði `config.json` og `config.ini` eru samþykktar — **innihald skrárinnar er JSON í báðum tilvikum**; endingin `.ini` er hreinlega notagildisívilnun fyrir Windows-notendur án tæknibakgrunns, sem hafa engan sjálfgefinn meðhöndlara fyrir `.json`.

```bash
# Veldu eitt:
cp config.example.json config.json
cp config.example.ini  config.ini
```

`config.json` og `config.ini` eru bæði í `.gitignore`, þannig að hver notandi heldur sinni staðbundnu afriti.

Innihald:

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

| Lykill             | Tegund          | Tilgangur |
|--------------------|-----------------|-----------|
| `source_file`      | string          | Slóð á skrá (`.pdf`, `.txt`, `.docx`, `.md`, `.html` eða mynd) **eða** URL (`http://`, `https://`). Tómur strengur eða týnd skrá → innbyggður sýnishornssafn. |
| `custom_patterns`  | string[]        | Valfrjáls listi af reglulegum tjáningum sem eru fjarlægðar úr hráum texta (hlaupandi hausar, fætur, endurtekið kjarnamál). Dæmi: `["Editorial: .*", "Copyright \\d{4}"]`. |
| `remove_noise`     | boolean         | Skiptir `generate_report.py` á milli lesendaham (`true`, felur Hugging Face/torch hleðslulínur og uppsláttar/POS-töflur) og fullum greiningarham (`false`). |
| `corpus_languages` | string[]        | Tungumál TEXTANS (kóðar tungumálapakka: `de`, `en`, `es`, `fi`, `fr`, `is`, `it`, `pl`, `ru`); gamla heitið `ocr_languages` er enn lesið. Orðasöfn þeirra velja grunntungumálið og tungumál hvers orðs (sjá **Tungumál hvers orðs**), og í skönnuðum PDF-skrám og myndum les hvert þeirra síðuna með eigin OCR-vél. Teldu aðeins upp tungumál sem raunverulega koma fyrir í textanum: aukatungumál hægir á OCR og bætir við fölskum kandídötum. Blanda má latnesku og kýrillísku letri (`["fi", "ru"]`). |
| `enable_sentiment` | boolean         | Kveikir á valfrjálsri tilfinningagreiningu per málsgrein (`false` sjálfgefið). Krefst hinna afkommentuðu tilfinningapakka (sjá Uppsetning, skref 4). Skrifar `sentiment.csv`; niðurstaðan er aldrei sýnd notandanum, hún fóðrar aðeins shamaníska lagið (helgisiðinn `emotional_undertow.txt` og söng Vieno). Við hverja hleðsluvillu er einfaldlega sleppt — engin fallback. |
| `ui_lang`          | string          | Tungumál notendaviðmóts fyrir úttak í skel og `<html lang>` eigind í myndaðri skýrslu (`pl` / `en` / `ru` / `fi` / `is` / `it` / `de` / `es` / `fr`). Tómur strengur eða óþekktur kóði → fallback `en`. Óháð tungumáli greinda safnsins, sem orðasöfn `corpus_languages` ákveða. |
| `lumi_katla_lines` | heiltala eða null | Valfrjáls skrautmark fyrir lokaskýrslu Lumi úr `shamanic_ai.py`: hve margar ekki-tómar línur einræðu Kötlu Lumi sér. `null` eða vantandi lykill = allt innihald; heiltala N > 0 = fyrstu N línurnar. |
| `lumi_vieno_lines` | heiltala eða null | Það sama og `lumi_katla_lines`, en fyrir bergmálsöng Vieno. |
| `voices`           | hlutur          | Varpar hverri shamanískri rödd (`katla` / `vieno` / `lumi` / `sami`) yfir á ElevenLabs radd-auðkenni, notað af `shamanic_voice.py`. Rödd með tómu eða vantandi auðkenni er sleppt. Aðeins nauðsynlegt ef þú keyrir hljóðafgreiðarann. |
| `llm_provider` | strengur | LLM-þjónusta fyrir `shamanic_ai.py` og Bókina: `openai` (sjálfgefið), `openrouter` eða `openai_compat`. Hver þjónusta les aðeins sinn eigin lykil úr `golden_key.env` — sjá *LLM-þjónustur og lyklar* hér fyrir neðan. |
| `llm_model` | strengur | Líkan fyrir þá þjónustu. Tómt = sjálfgefið líkan þjónustunnar (`gpt-6.1-sol` / `openai/gpt-6.1-sol`); skylda fyrir `openai_compat`. |
| `llm_base_url` | strengur | Slóð sem **aðeins** `openai_compat` les (t.d. `http://localhost:1234/v1`). `openai` og `openrouter` hunsa hana, því slóðir þeirra eru fastar. |
| `kirja_llm_provider` | strengur | Valfrjáls yfirskrift þjónustu fyrir Bókina (`ksiega_niedomowien.py draft` / `fill`). Tómt = `llm_provider`. |
| `kirja_drafter_model` | strengur | Líkan fyrir `draft` (höfund draga Bókarinnar gegnum API). Tómt = sjálfgefið líkan þjónustunnar, eða `llm_model` þegar Bókin notar almennu þjónustuna. |
| `kirja_filler_model` | strengur | Líkan fyrir `fill` (blindan eyðufyllanda Bókarinnar). Sama varaleið og `kirja_drafter_model`. |
| `reacts_llm_provider` | string | Valfrjáls hnekking þjónustu fyrir `helsinki_reacts.py`. Tómt = `llm_provider`. |
| `reacts_model` | string | Líkan fyrir `helsinki_reacts.py`. Tómt = sjálfgefið líkan þjónustunnar, eða `llm_model` þegar Helsinki Reacts notar almennu þjónustuna. |
| `reacts_lang` | string | Tungumál streymis í `helsinki_reacts.py` (`ui_lang`-kóði). Tómt = `ui_lang`. `fi` = streymið á finnsku; hvert annað = þýðing þess með finnskum innskotsorðum. |

> **LLM-þjónustur og lyklar.** Lykill er bundinn einum hýsli og er aldrei sendur annað: `openai` → `OPENAI_API_KEY` → `api.openai.com`; `openrouter` → `OPENROUTER_API_KEY` → `openrouter.ai`; `openai_compat` → `LLM_COMPAT_API_KEY` → `llm_base_url`. Þjónustan er valin sérstaklega og aldrei ráðin af slóð, svo að það að beina einni skriftu að annarri þjónustu getur hvorki lekið lykli fyrri þjónustunnar né brotið hina skriftuna. Lykillinn `kirja_filler_base_url` frá því fyrir v1.7.0 (hann sendi `OPENAI_API_KEY` á hvaða slóð sem var) er hafnað með leiðbeiningum um flutning. Á OpenRouter bera auðkenni líkana forskeyti framleiðanda (`openai/gpt-4o`, `anthropic/claude-sonnet-5.5`), og persónuverndarstillingar aðgangsins leyfa að útiloka þjónustur sem kunna að þjálfa á fyrirmælum þínum.

> **Tilfinningagreining — álag á örgjörva.** Þegar `enable_sentiment: true` er virkt er greiningin per málsgrein reikniþung á CPU — nokkurn veginn sambærileg við að keyra staðbundna Whisper tal-í-texta á CPU. Á eldri eða hitatakmörkuðum vélum getur þetta viðvarandi álag verið raunverulegt erfiði fyrir örgjörvann; virkjaðu það meðvitað, helst á vél með GPU eða með svigrúm fyrir langvarandi vinnu á fullu álagi.

> **`ui_lang` — umfang staðfærslu.** Skel-úttak sjálfstæðu skriptanna (`generate_report.py`, `generate_md.py`, `generate_diagnostic.py`, `shamanic_pipeline.py`, `shamanic_ai.py`, `ksiega_niedomowien.py`, `helsinki_reacts.py`) er staðfært gegnum `ui_lang`. **Staðalúttak minnisbókarinnar er ekki** staðfært — það er harðkóðað á rússnesku (aðeins skráarnafn tesanna fylgir greinda tungumáli safnsins). Lesendaham-skýrslan `analysis_report.html` heldur rússnesku frásögn minnisbókarinnar (rót hennar er `<html lang="ru">`); að fullu `ui_lang`-staðfærði notendaskjár-artefaktinn er **`diagnostic_report.html`** sem `generate_diagnostic.py` býr til. Þýðingar í `fi` / `is` / `it` / `de` / `es` / `fr` eru drög og óyfirfarnar — vinsamlegast tilkynntu ónákvæmni á GitHub.

> **Windows-slóðir og regex — mikilvægt.** Innihald stillinganna er JSON og JSON hefur enga raw-strengja-málskipan. Ein bakskáslína sleppir næsta staf (`\U`, `\d`, `\n` eru sérstakir), þannig að Windows-slóð skrifuð sem `"C:\Users\marek\doc.pdf"` veldur villu við JSON-túlkun. Tvær réttar leiðir til að skrifa hana:
>
> - **Áframslínur** (einfaldast, virkar líka á Windows): `"C:/Users/marek/doc.pdf"`.
> - **Tvöfaldar bakskáslínur**: `"C:\\Users\\marek\\doc.pdf"`.
>
> Sama regla á við um sérhverja reglulega tjáningu í `custom_patterns`: skrifaðu `"\\d{4}"`, ekki `"\d{4}"`; skrifaðu `"Copyright \\d{4}"`, ekki `"Copyright \d{4}"`. Í JSON er engin `r"…"`-málskipan fyrir raw-strengi.

## Keyrsla

Skriftunum hér að neðan er ætlað að keyra **í röð**: hver tekur við gripum úr fyrra skrefi.

### Flýtileið: öll staðbundna keðjan (`run_all.py`)

```bash
# minnisbók -> generate_report.py -> shamanic_pipeline.py -> scan bókarinnar (aðeins finnska)
python run_all.py
# nota úttakið sem þegar er vistað í minnisbókinni
python run_all.py --skip-notebook
# full greining á viðvörunum safna, óháð config
python run_all.py --warnings-as-errors
```

Skref 1, 2 og 4 hér að neðan, auk `scan` fyrir Bók hins ósagða þegar textasafnið er finnskt, í einni skipun. Keyrðu hann með Python úr `.venv` geymslunnar: ef kjarnann `analyst_env` vantar er hann skráður fyrir þann túlk. Keðjan stöðvast við fyrsta skrefið sem mistekst; úttakskóði 3 þýðir að heimildarathugun skýrslunnar hafnaði (sjá skref 2). Minnisbókin þaggar viðvaranir safna viljandi svo þær berist ekki í greiningarskýrsluna. `--warnings-as-errors` er sérstakur hamur fullrar greiningar: hann hunsar `config.json` og keyrir afrit af minnisbókinni með tilbúnu textasafni gegnum hvern íhlut (PDF með letursviðgerð og skannaðri síðu fyrir OCR, öll inntakssnið og URL frá staðbundnum þjóni, tilfinningagreiningu, íslensku, omorfi). Hann skráir hverja viðvörun, líka þær sem koma upp í kóða sem grípur undantekningar, og prentar þær allar undir fyrirsögn hólfsins, orðaðar af safninu, ásamt staðnum þar sem þær komu upp. Þekktar, skaðlausar viðvaranir (`diagnostyka.ZNANE_OSTRZEZENIA`) fá sérstaka línu og teljast ekki með. Hamurinn krefst allra valfrjálsra pakka í `requirements.txt` og líkansins `fi_core_news_lg`, og íhlutur sem hleðst ekki stöðvar hann með skilaboðum. Minnisbókin og `export_results/` eru ósnert og skýrslan og síðari skref keyra ekki; úttakskóði 4 = nýjar viðvaranir, 0 = engin. Skráningin nær yfir `warnings`-eininguna í ferli minnisbókarinnar: skilaboð send gegnum `logging` (t.d. frá `transformers`) og viðvaranir undirferla eru utan hennar. Ef safn skiptir skráningunni út (t.d. `logging.captureWarnings`) endar hamurinn með kóða 1 í stað falskrar „hreinnar“ niðurstöðu; sama gildir um Ctrl+C, eftir að safnaðar viðvaranir hafa verið prentaðar. Keyrðu hann eftir uppfærslu safna.

### 1. Minnisbók (skyldug)

```bash
jupyter notebook accessible_text_analyst.ipynb
# (Cell → Run All)
# Án viðmóts (CI): hólf 0-39 með nbclient, án gagnvirka hólfsins cell_qa_rag
python -c "import nbformat as f; from nbclient import NotebookClient as C; nb=f.read('accessible_text_analyst.ipynb',4); c=C(nb,timeout=None); c.create_kernel_manager(); c.start_new_kernel(); c.start_new_kernel_client(); [c.execute_cell(x,i) for i,x in enumerate(nb.cells[:40])]; f.write(nb,'accessible_text_analyst.ipynb'); c.km.shutdown_kernel(now=True)"
```

Þetta er raðleiðsla með sameiginlegri hnattrænni stöðu. **Ekki endurraða hólfum og ekki keyra þau úr röð.** Minnisbókin skrifar `export_results/<project>/sentences.csv`, `paragraphs.csv`, `theses.csv`, `keywords_tfidf.csv`, `paragraphs_with_topics.csv`, `topic_keywords.json`, `entities.csv`, `accessible_text.html`, `accessible_text.docx` og `theses.txt`.

### 2. HTML-skýrslur (mælt með)

```bash
python generate_report.py
# → export_results/<project>/analysis_report.html
```

`generate_report.py` les úttak hólfa beint úr `.ipynb`-skránni, þannig að HTML-skýrslan verður að vera mynduð úr **nýkeyrðri** minnisbók. `requirements.txt` listar `nbstripout` — ef hann hefur verið virkjaður í staðbundinni git-stillingu eru úttök minnisbókarinnar fjarlægð við commit. Myndaðu skýrsluna _áður_ en þú commitar, eða slökktu á nbstripout fyrir vinnuflæði þitt.

**Heimildarathugun.** Áður en `generate_report.py` skrifar nokkuð athugar það hvort úttak minnisbókarinnar tilheyri `source_file` í stillingunum, og hafnar annars (úttakskóði 3, ekkert skrifað). Þrjár athuganir: slóð heimildarinnar og útflutningsmappan sem minnisbókin prentaði verða að passa við stillingarnar og vistaða keyrslan verður að hafa náð enda útflutningshólfsins; `paragraphs.csv` og `sentences.csv` mega ekki vera nýrri en `.ipynb` (annars var úttak síðustu keyrslu aldrei vistað — dæmigert þegar minnisbókin er keyrð í VS Code án þess að vista); og síðuupphöfin sem minnisbókin prentaði verða að koma fyrir í upprunaskránni (borið saman sem runa bókstafa eingöngu, svo sameinuð orðskipti, fjarlægð blaðsíðutöl og síðuhausar skipta ekki máli). Þegar ekki er hægt að bera innihaldið saman — skannar lesnir með OCR, myndir, vefslóðir, brenglað textalag í PDF — ráða fyrstu tvær athuganirnar og stjórnborðið segir frá því. Skýrslan skráir líka hvort omorfi tók þátt í keyrslunni (`<meta name="ata-omorfi">`); Bók hins ósagða les það.

Fyrir uppbyggða, heildstæða **greiningarsýn** sem byggð er beint á CSV/JSON-útflutningnum:

```bash
python generate_diagnostic.py
# → export_results/<project>/diagnostic_report.html
```

`generate_diagnostic.py` les aðeins útfluttu CSV/JSON-skrárnar, þannig að — ólíkt `generate_report.py` — þarf það ekki nýkeyrða minnisbók, aðeins útflutninginn sem minnisbókin skrifaði. Niðurstaðan er aðgengilegt skjal (efnisyfirlit, fyrirsagnir, listar) sem nær yfir þemu, tesur, nafnliði eftir tegund og helstu lykilorð.

### 3. Gemini Notebook-vænt Markdown (valfrjálst)

```bash
python generate_md.py
# → export_results/<project>/gemini_notebook_report.md
```

Þetta breytir HTML-skýrslunni í Markdown-skrá þar sem aðgengis-spans hafa verið afpökkuð (Gemini Notebook — áður NotebookLM — notar ekki `<span lang="…">`). Keyrðu þetta aðeins ef þú vilt mata skýrsluna inn í Gemini Notebook.

### 4. Shamanískt eftirvinnsluforrit án LLM (valfrjálst)

```bash
python shamanic_pipeline.py
# → export_results/<project>/audio_scripts/oracle_script.txt
#                                          /raw_roots_chant.txt
#                                          /prophecies.txt
#                                          /lore_fragments/intercepted_log_T*_P*.txt
#                                          /emotional_undertow.txt   # aðeins ef sentiment.csv er til
```

Býr til helgisiðatextagripi beint úr CSV/JSON-útflutningi minnisbókarinnar — engin LLM-köll, ekkert net. Allir strengir koma úr `shamanic_locale.py` og eru að fullu staðfærðir á öll níu studdu tungumálin. Þegar valfrjálsa `sentiment.csv` er til staðar býr það einnig til `emotional_undertow.txt` — „tilfinningaflóð" per málsgrein ásamt jafnvægissamantekt; án hennar er þeim eina helgisiða einfaldlega sleppt.

### 5. Shamanískt LLM eftirvinnsluforrit (valfrjálst, krefst LLM API-lykils)

```bash
python shamanic_ai.py
# → export_results/<project>/audio_scripts/katla_entity_monologue.txt
#                                          /vieno_echoes_chant.txt
#                                          /lumi_final_report.txt
#                                          /sami_energetic_spark.txt
```

Krefst lykils valinnar þjónustu (`llm_provider`, sjálfgefið `openai`). Búðu til `golden_key.env` í rót verkefnisins með lyklinum sem þú þarft:

```
OPENAI_API_KEY=sk-...          # llm_provider: openai (default)
OPENROUTER_API_KEY=sk-or-...   # llm_provider: openrouter
LLM_COMPAT_API_KEY=...         # llm_provider: openai_compat (llm_base_url)
```

`golden_key.env` passar við `*.env` í `.gitignore`, því verður það ekki committað. Raddirnar fjórar keyra í röð:

1. **Katla** breytir entítetalistanum (`entities.csv`) í einræðu frosinna norrænna anda.
2. **Vieno** syngur yfir lykilorða-/þemalistann. Sjálfgefið vefur hún inn fimm hráum setningum úr safninu sem bergmáli frá öðrum víddum; þegar valfrjálsa `sentiment.csv` er til staðar les hún í staðinn tilfinningabogadrátt textans (tilfinningar per málsgrein, niðurúrtaktar til að rúmast innan tákamarka líkansins á löngum söfnum) og lætur hann móta hreyfiafl söngsins.
3. **Lumi** les `prophecies.txt` (skylda) auk einræðu Katlu og söngs Vieno (valfrjálst skraut) og myndar lokaskýrslu. Staðfærðir fallback-strengir taka við þegar Katla eða Vieno vantar.
4. **Sami** les skýrslu Lumi og afhendir orkuríka samantekt með neista vonar eða ákalli til aðgerða.

### 6. Shamanískur hljóðafgreiðari (valfrjálst, krefst ElevenLabs)

```bash
python shamanic_voice.py
# → export_results/<project>/audio_scripts/katla_entity_monologue.mp3
#                                          /vieno_echoes_chant.mp3
#                                          /lumi_final_report.mp3
#                                          /sami_energetic_spark.mp3
```

Sjálfstætt skript sem keyrir einu sinni, les frásagnargripina fjóra sem `shamanic_ai.py` bjó til og myndgerir hvern þeirra í `.mp3` gegnum ElevenLabs-líkanið `eleven_multilingual_v2` (sem greinir sjálfkrafa talaða tungumálið, svo enginn tungumálastiki er sendur). Það skráir hvern árangur eða villu í skelina og hættir svo — enginn botni, enginn þjónn, engin gagnvirk lota. Það þarf tvennt:

- `ELEVENLABS_API_KEY` í `golden_key.env` (sömu skrá og geymir LLM-lyklana).
- `voices`-vörpun í `config.json` / `config.ini` sem úthlutar ElevenLabs radd-auðkenni á hvert af `katla`, `vieno`, `lumi`, `sami`. Rödd með tómu auðkenni eða þeirri sem vantar gripinn fyrir er sleppt (keyrðu `shamanic_ai.py` fyrst); ein rödd sem mistekst stöðvar ekki hinar.

> **Friðhelgi og kostnaður.** Eins og `shamanic_ai.py` með OpenAI sendir þetta skript texta gripanna til þriðja aðila (ElevenLabs) til myndgerðar, og ElevenLabs er **gjaldskyld** API. Innihaldið yfirgefur vél þína — ekki keyra það á efni sem þú mátt ekki deila út á við.

### 7. Bók hins ósagða (valfrjálst, aðeins finnska, með aðstoð gervigreindarþjóns)

```bash
python ksiega_niedomowien.py scan              # hvaða export_results/-möppur uppfylla skilyrðin
python ksiega_niedomowien.py scan --blocks     # einnig búnar / opnar / eftirstandandi blokkir (hægt; sjálfvirkt með --folder)
python ksiega_niedomowien.py status            # framvinda eftir möppum: færslur, augljósar blokkir, opnir pakkar
python ksiega_niedomowien.py tidy              # færslur sem nýrri færsla sömu blokkar leysir af (forskoðun; --apply tekur til)
python ksiega_niedomowien.py prepare --folder <name> --limit 3
#   → export_results/_kirja_tyotila/<id>/packet.json
python ksiega_niedomowien.py draft <id>        # valfrjálst: drög gegnum API + seal, allt að 2 endurtekningar
python ksiega_niedomowien.py seal <id>         # sannreynir draft.json, skrifar blind.json
python ksiega_niedomowien.py fill <id>         # valfrjálst: blindar ágiskanir gegnum API, síðan judge
python ksiega_niedomowien.py judge <id>        # → export_results/Sanomattomien_kirja.md
# <id> = auðkenni pakkans sem prepare prentar, upphaf möppunafns eða slóð að pakkamöppunni
```

Leikur sem byggir á `raw_roots_chant.txt`. Fyrir hverja blokk 3–6 samfelldra róta skrifar mállíkan þokukennda finnska dagbókarfærslu með eyðum; svörin eru orðrétt brot úr frumtextanum og verða að koma fyrir **bæði** í `accessible_text.html` og `accessible_text.docx`, þ.e. í báðum útgáfum sannleiksuppsprettunnar. Síðan reynir sérstakt, blint líkan að fylla eyðurnar út frá færslunni einni; hver eyða sem það giskar á telst augljós og brot hennar er fjarlægt. Það sem eftir stendur — KATLA (viðvörunarkerfið) sem les ræturnar og VIENO (shamaníski sögumaðurinn) með ósögðu eyðunum — er bætt aftan við `export_results/Sanomattomien_kirja.md`. Svarlykillinn fer í `Sanomattomien_kirja.avain.json` og staðan í `Sanomattomien_kirja.tila.json`; endurkeyrsla tvítekur aldrei færslur.

Skriftan er ákveðni helmingurinn (síur, blokkir, sannleiksuppspretta, sannprófun, mat, Bókin). Skapandi helminginn — að skrifa `draft.json` — vinnur annaðhvort gervigreindarþjónn eftir `skills/ksiega-niedomowien/SKILL.md` eða líkan gegnum API með `draft`.

**Inntakssíur.** Aðeins undirmöppur `export_results/` með finnsku heiti, `<html lang="fi">`, finnskum söng og engum málfræðileka koma til greina; öllu öðru er hafnað með ástæðu. Línan `roots.header` er fjarlægð ef hún er til staðar. Prófið á *málfræðileka* finnur málheildir sem voru unnar áður en omorfi var virkjað (v1.5.0): yfir alla `keywords_tfidf.csv` telur það beygðar myndir sem lifðu lemmun af ásamt ruslmyndum spaCy og hafnar möppunni yfir 1,0 á hver 100 hugtök. Krefst omorfi (5. skref uppsetningar). Þegar mappan hefur uppfærða `analysis_report.html` segir höfnun vegna málfræðileka hvað skýrslan veit: omorfi tók þátt í keyrslunni (þá gæti vélin sjálf — leiðrétting finnskra lemma í minnisbókinni — þurft lagfæringu; tilkynntu dæmin), omorfi vantaði (settu það upp og keyrðu minnisbókina aftur) eða keyrslan hafði ekkert omorfi-skref. Án uppfærðrar skýrslu segir hún að það sé óvitað.

**Hvers vegna aðeins finnska.** Leikurinn lifir á því sem lemmun lætur ósagt, svo hann er aðeins skynsamlegur þar sem það að færa orð í grunnmynd sviptir það raunverulegri merkingu. Finnska er viðskeytamál: það sem pólska eða rússneska tjá að hluta með sérstökum forsetningum, og enska aðallega með orðaröð og kerfisorðum, pakkar finnskan inn í orðið sjálft — fimmtán föll (`talossa` „í húsinu“, `talosta` „úr húsinu“, `taloon` „inn í húsið“, `talolle` „að húsinu“, `talotta` „án húss“), eignarviðskeyti (`taloni` „húsið mitt“, `talonsa` „húsið hans/hennar/þeirra“), smáorðsviðhengi (`-ko` spurning, `-kin` „líka“, `-han` áhersla) og sagnmyndir sem bera í senn persónu, tíð, hátt og þolmynd (`tehtäisiinkö` „yrði það gert?“). Söngurinn smættar allt þetta í `TALO` og `TEHDÄ`: hver, hvar, hvaðan, hvert, hvers og hvort hverfa — einmitt þær eyður sem hlustandinn þarf að fylla. Í pólsku og rússnesku missir grunnmyndin beygingarendinguna, en stór hluti venslanna býr í sérstöku orði (forsetningunni), svo grunnmyndin bar þau aldrei ein; enska tapar litlu umfram tölu og tíð. Íslenska (fjögur föll, sem forsetningar stýra að miklu leyti) og ítalska (forsetningar og greinar, lítil nafnorðabeyging) standa nær pólsk-rússneska og enska mynstrinu, hvort um sig. Tæknilega þarf tólið einnig orðabókargreini til að sanna að söngurinn sé laus við málfræði og til að tengja rætur aftur við beygðan texta; í þessari leiðslu er slíkur aðeins til fyrir finnsku (omorfi), og þröskuldarnir voru stilltir á raunverulegum finnskum málheildum.

**Höfundur draga gegnum API (`draft`).** Lækkar þröskuldinn: enginn þjónn er nauðsynlegur. Skriftan sendir pakkann (chant, rætur og setningar úr frumtextanum úr `truth.sentences`) til stilltrar þjónustu, skrifar `draft.json` og innsiglar það; þegar `seal` hafnar drögunum fær líkanið þau aftur ásamt áþreifanlegum athugasemdum sannprófandans, í mesta lagi 2 endurtekningar (3 tilraunir). Úttakskóðar eru þeir sömu og hjá `seal` (0 innsiglað, 4 enn hafnað — lagaðu síðasta `draft.json` handvirkt eða með skillinu). Fyrirliggjandi `draft.json` er aldrei skrifað yfir án `--force`. Skillið er áfram öflugri hátturinn: ótakmarkaðar endurtekningar, og þjónninn les athugasemdirnar jafnóðum. Eina reglu er ekki hægt að sannprófa með ákveðnum hætti í hvorugum hættinum: *eignaðu ekki raunverulegu fólki staðreyndir eða ásakanir sem ekki eru í setningum frumtextans*. Bæði fyrirmæli höfundar draga og skillið nefna hana, en ekkert athugar hana — lestu færslur um raunverulegt fólk áður en þú deilir þeim.

**Blindur fyllandi (`fill`).** Sendir aðeins `blind.json` — aldrei svörin né frumtextann — til stilltrar þjónustu, vistar `guesses.json` og keyrir `judge` strax. Þjónusta: `kirja_llm_provider` (tómt = `llm_provider`); líkan: `kirja_filler_model`; `--provider` / `--model` yfirskrifa hvort tveggja. `judge` eitt og sér er ætlað fyrir ágiskanir blinds undirþjóns. Bæði `draft` og `fill` biðja fyrst um JSON-skema (structured outputs); ef slóðin hafnar því fara þau í venjulegan JSON-hátt og svo í fyrirmælin ein. `fill` reynir tvisvar aftur þegar svarið er ónothæft eða vantar eyðu. Hvert ónothæft svar er vistað í pakkamöppunni (`draft_reply_N.txt` / `fill_reply_N.txt`, með `finish_reason` og hugsanlegri synjun), og stjórnborðið segir hvar.

**Hæfnin tengd.**

- *Claude Code:* afritaðu `skills/ksiega-niedomowien/` í `~/.claude/skills/` (persónulegt) eða í `.claude/skills/` í þínu eintaki af geymslunni. Þessi geymsla hunsar `.claude/` í git, þess vegna fylgir hæfnin í `skills/`.
- *Claude-forritin:* þjappaðu möppunni `ksiega-niedomowien/` í ZIP (mappan sjálf verður að vera rót safnsins) og bættu henni við undir **Customize → Skills**; kóðakeyrsla þarf að vera virk og lotan þarf aðgang að eintakinu þínu, því omorfi-sjálfvirkjarnir og `export_results/` eru á þínum diski. Notaðu **Code**-flipann með **staðbundinni** lotu: í venjulegum spjallham eða í skýjalotu eru skrárnar sem þjónninn les — brot úr frumtextanum meðtalin — afritaðar í skýjaumhverfi.
- *Aðrir gervigreindarþjónar:* `SKILL.md` er einfalt Markdown-ferli með YAML-haus; hver sá þjónn sem getur keyrt staðbundnar skipanir í geymslunni getur fylgt því. Ef hann getur ekki ræst óháðan undirþjón skaltu nota `fill` fyrir blinda skrefið.
- Hreinn spjallþjónn án staðbundinnar skipanakeyrslu (t.d. custom GPT) getur ekki keyrt þetta: omorfi og um 130 MB sjálfvirkjar þess verða að keyra við hliðina á gögnunum þínum.

> **Friðhelgi og kostnaður.** Þrjú stig, frá minnstu til mestu gagna: `fill` sendir aðeins þokukenndan texta færslunnar (ekki frumtextann); `draft` sendir orðréttar setningar úr frumtextanum (`truth.sentences`) og segir fyrir kallið hve margar þær eru; þjónn sem fylgir skillinu les brot úr frumtextanum og sendir þau til eigin líkanaþjónustu — og í skýjalotu vinnur hann á skýjaafriti skránna. Öll API-köll kosta. Notaðu þau aðeins á efni sem þú mátt deila með þessum þjónustum.

### 8. Helsinki Reacts (valfrjálst, krefst LLM API-lykils)

```bash
python helsinki_reacts.py <project> [<project> …]
# → export_results/_streams/<project>.md
python helsinki_reacts.py notes.txt             # hvaða textaskrá sem er dugar líka
python helsinki_reacts.py <project> --dry-run   # sýna hvað yrði sent, án þess að senda neitt
python helsinki_reacts.py <project> --lang en   # tungumál streymisins í þessari keyrslu
python helsinki_reacts.py <project> --kirja     # bæta við færslu möppunnar úr Bók hins ósagða
```

Háðskt handrit að streymi: Valtteri, streymari frá Helsinki, bregst ásamt spjallinu sínu við upptöku, og Lumi, köld talgervilsrödd, les upp framlögin. Inntakið er heiti möppu í `export_results/` (texti `accessible_text.html` hennar án merkja og fyrirsagna) eða hvaða textaskrá sem er; handritið er vistað í `export_results/_streams/<heiti>.md`, og ný keyrsla sama heitis bætir við `_2`, `_3`.

**Fyrirmælin eru þín.** Kerfisfyrirmælin eru ekki í kóðanum: sjálfgefna skráin `helsinki_reacts.example.md` er viljandi hófleg. Afritaðu hana í `helsinki_reacts.md` (hún er í `.gitignore` og er notuð sjálfkrafa þegar hún er til) og breyttu því sem þú vilt, eða bentu á hvaða skrá sem er með `--prompt`. Ein regla til eða frá breytir streyminu mikið, svo berðu saman nokkrar keyrslur áður en þú velur útgáfu. Skriftan bætir sjálf aðeins við því sem verður að virka óháð fyrirmælunum: upptökunni, úttakstungumálinu og — með `--kirja` — kafla Bókar hins ósagða.

**Tungumál.** `--lang`, svo `reacts_lang` úr stillingum, svo `ui_lang`. Finnska gefur streymið sjálft á venjulegri finnsku; hvert annað tungumál gefur þýðingu þess, þar sem stutt finnsk innskotsorð haldast óþýdd.

**Bók hins ósagða (`--kirja`).** Fyrir möppu með færslu í `Sanomattomien_kirja.md` fær spjallið þokukenndan texta færslunnar og misheppnaðar ágiskanir blinda útfyllandans sem kenningar til að rífast um. Svarlykillinn nær aldrei til líkansins, og föst regla bannar Valtteri að bera eyðu saman við upptökuna, því eyðurnar fela orð úr sömu upptöku. Án færslu verður streymið til án Bókarinnar.

Þjónusta og líkan: `reacts_llm_provider` / `reacts_model` (tómt = `llm_provider` / `llm_model`), sem `--provider` / `--model` ganga framar; hugsunarátak er sjálfgefið `low` (`--effort`). Svari styttra en `--min-chars` (1500) er hafnað sem neitun og það prentað í stjórnborðið.

> **Friðhelgi og kostnaður.** Allur texti hverrar upptöku fer til stilltrar þjónustu, sem er greidd; skriftan segir frá því fyrir fyrsta kall. Niðurstaðan er háð um efnið, skrifað af gervigreind: lestu það áður en þú deilir því, sérstaklega ef raunverulegt fólk er nefnt — ekkert kannar hvað líkanið eignar því.

## Úttak

Hver greint safn fær sína undirmöppu undir `export_results/`, nefnda eftir upprunaskránni (slóð og ending fjarlægð) eða eftir `domain_slug` fyrir URL. Innbyggða sýnishornssafnið notar `export_results/_default/`.

Hver undirmappa inniheldur:

| Skrá                            | Búin til af       | Lýsing                                            |
|---------------------------------|-------------------|---------------------------------------------------|
| `sentences.csv`                 | minnisbók         | hver setning með vísitölu og tungumáli (`lang`)   |
| `paragraphs.csv`                | minnisbók         | málsgreinar (3–6 setningar hver)                  |
| `theses.csv`, `theses.txt`      | minnisbók         | ein meginsetning per málsgrein (hæsta-TF-IDF setning); `.txt`-skráarnafnið fer eftir tungumáli safnsins (t.d. `tezy.txt` fyrir pólsku, `тезисы.txt` fyrir rússnesku) |
| `keywords_tfidf.csv`            | minnisbók         | lykilorð (uni/bi/trigröm) með TF-IDF-vægi         |
| `paragraphs_with_topics.csv`    | minnisbók         | málsgreinar með úthlutuðu KMeans-þema             |
| `topic_keywords.json`           | minnisbók         | lykilorð per þema                                 |
| `entities.csv`                  | minnisbók         | öll nefnd entítet og merkimiðar þeirra            |
| `language_spans.csv`            | minnisbók         | erlendir tungumálabútar: skjal, stafahliðranir, tungumál, `block` eða `inline`, texti |
| `sentiment.csv`                 | minnisbók *(valfrjálst)* | tilfinning per málsgrein (`para_id`, `label`, `score`, `lang`) — aðeins þegar `enable_sentiment` er `true`; fóður fyrir shamaníska lagið, aldrei sýnt notandanum |
| `accessible_text.html`          | minnisbók         | `lang` á hverri málsgrein auk `<span lang>` á hverri erlendri setningu og hverju innskoti (tilvitnun, nafn) — skjálesarar skipta um rödd sjálfkrafa per brot |
| `accessible_text.docx`          | minnisbók         | sama innihald með `<w:lang>` stilltu per `Run` (`pl-PL`, `ru-RU`, `en-US`, `it-IT`, `fi-FI`, `is-IS`, `de-DE`, `es-ES`, `fr-FR`) — Word og SAPI nota það án nets, án nettengs greinis |
| `analysis_report.html`           | `generate_report.py` | heildar aðgengileg HTML-skýrsla                |
| `diagnostic_report.html`         | `generate_diagnostic.py` | uppbyggð greiningarskýrsla (þemu, tesur, nafnliðir eftir tegund, lykilorð) úr CSV/JSON-útflutningi |
| `gemini_notebook_report.md` | `generate_md.py`     | Gemini Notebook-tilbúið Markdown (áður NotebookLM) |
| `audio_scripts/*.txt`           | `shamanic_pipeline.py`, `shamanic_ai.py` | helgisiða- / frásagnartextagripi |
| `audio_scripts/*.mp3`           | `shamanic_voice.py` *(valfrjálst)* | frásagnarraddirnar fjórar myndgerðar í hljóð gegnum ElevenLabs |

## Aðgengi

Þetta er kjarnagildi verkefnisins. Allt hér að neðan er ásetningsvert og verður að varðveita við breytingar á leiðslunni:

- **Engir ANSI-litir, tjáningartákn eða gervigrafík í stdout.** Skjálesari les hvern staf bókstaflega — `[OK]` í stað „🟢", `---` í stað „───━━━".
- **Þaggaðar framvinduslíkur** (`tqdm`, `transformers`, `torch`) — `cell_model._silence_hf_progress()` þaggar Hugging Face/torch hleðslulínur og viðvaranir áður en IceBERT og icelandic-ner-bert eru sótt fyrir íslensku; `cell_corpus._silence_ocr_progress()` gerir það sama fyrir OCR-vélarnar.
- **`lang`-merking per málsgrein, per setningu og per bút í útflutningi.** `accessible_text.html` og `accessible_text.docx` bera ISO 639-1 kóða á hverri málsgrein, á hverri erlendri setningu og á hverju erlendu innskoti (tilvitnun eða nafn inni í setningu). NVDA, JAWS, Narrator, VoiceOver, Word og SAPI virða þessi merki og skipta um rödd sjálfkrafa — jafnvel án nets.
- **Harðkóðuð enskumerking í HTML-skýrslunni.** `generate_report.py` vefur alltaf tæknileg ensk brot — POS-merki (`NOUN`, `VERB`, `ADJ`), NER-merki (`PER`, `ORG`, `[orgName]`), auðkenni spaCy / Hugging Face líkana, ASCII-slóðir, kóðablokkir — inn í `<span lang="en">`, þannig að þau eru ekki lengur lesin með sjálfgefnu rússnesku rödd skjalsins.
- **Per-brot merking erlends safns í HTML.** Þegar safnið er ekki rússneskt eru uppbyggð úttök (setningarútdrættir, lykilorðalistar, þemorðsorð, RAG-röðunarraðir, uppsláttartöflur) vafin í `<span lang="target_lang">`.
- **Línuleg HTML-bygging** (`<main>`, rétt fyrirsagnastigveldi).

### Lestur niðurstaðna sem ekki-rússneskumælandi notandi

Frásögn vinnubókarinnar og `print()`-úttak flestra hólfa er skrifað á rússnesku. Tveir eiginleikar Jupyter-viðmótsins gera þetta erfitt fyrir ekki-rússneskumælandi skjáleskara notendur, og pípan leggur til sértæka lausn fyrir hvora:

- **Jupyter í vafranum harðkóðar `lang="en"` á skjalið**, og „Þýða þessa síðu?" tilkynning birtist hvort sem er aldrei fyrir síður á `localhost`. Vinnubók með rússneskri frásögn er því lesin með enskri TTS-rödd — algjör ringulreið. Hagsýn lausn er **Jupyter-viðbótin fyrir VS Code**: listasýn hennar les aðeins `code cell` / `markdown cell` merki án ISO-merkinga, þú getur ýtt á Enter í kóðahólfum og ↓ farið framhjá markdown-hólfum án þess að hlusta á innihald þeirra, og harðkóðaða ensku-vandamálið takmarkast við úttakssýn (`Ctrl+Shift+↓`), sem þú getur einfaldlega ekki opnað.
- **`generate_report.py` er nánast skylda fyrir ekki-rússneskumælandi lesendur.** Það býr til `analysis_report.html` með `<html lang="ru">` og fullu setti af `<span lang="…">` merkjum fyrir hvert brot. Opnað í venjulegum vafra (ekki innan Jupyter), kveikir það á „Þýða þessa síðu?" tilkynningu vafrans fyrir rússnesku frásögnina, en heldur jafnframt TTS-raddaskiptum á brotum safnsins og á enskum tæknilegum hugtökum (POS, NER, líkana-nöfn).
- **Gagnvirk Q&A skrifar `qa_results.html` og opnar það fyrir þig.** `cell_qa_rag` prentar enn spurninguna og þrjár efstu niðurstöður í stdout — en það skrifar einnig sama efni í `export_results/<project>/qa_results.html` og kallar á `webbrowser.open()`, þannig að síðan lendir í kerfisvafranum, þar sem bæði þýðing og per-brot raddaskipti TTS virka. Úttakssýnin í Jupyter, þar sem harðkóðað `lang="en"` gerir rússnesku umbúðirnar ólesanlegar fyrir skjáleskara, er þannig ekki lengur eina leiðin að niðurstöðunni. Hver ný fyrirspurn skrifar yfir skrána.

## Þekktar takmarkanir

- **Uppruni tökuorða er ekki merktur.** Tungumálamerking (`lang`-eigindin, sjá *Tungumál hvers orðs*) nær til orða sem orðasafn annars upptalins tungumáls þekkir og til búta sem eru skrifaðir með erlendu letri: grískum stöfum, latnesku letri inni í kýrillískum texta. Skýr upprunamerking (`греч.`, `łac.`, `z niemieckiego`, `имеет греческое происхождение`) er ekki tengd tökuorðinu, og orð umritað með letri textans (`фразис` í rússneskum texta) heldur tungumáli safnsins. Slíkar merkingar hafa ekkert fast form (skammstöfun, lýsingarorð, heilt orðasamband), og ef kýrillíska `фразис` væri merkt sem gríska myndi skjálesarinn skipta yfir í gríska rödd, sem hljómar verr en sjálfgefna rússneska röddin.
- **Finnska: fyrsta orð setningar.** Í upphafi setningar byrjar hvert orð á hástaf, og spaCy-markarinn tekur stundum boðhátt eða upphrópun fyrir sérnafn: `Anna kuulua.` („láttu það heyrast“) verður nafnið *Anna*, `Oota, miten…` („bíddu, hvernig…“) nafnið *Oota*. omorfi-leiðréttingin skrifar aldrei yfir orð sem merkt er sem nafn, því annars yrðu raunveruleg nöfn að samnöfnum (*Tuskia* → *tuska*, „kvöl“). Slíkt orð heldur rituðu formi sínu sem lemmu og getur birst í lemmulistum, lykilorðum og rótasöngnum (`anna`, `oota`). Þegar markarinn telur orðið upphrópun setur omorfi inn sögnina (*Oota* → `oottaa`, frá v1.11.1). Málfræðilekaprófun Bókar hins ósagða telur ekki lykilorð sem heimildin notar líka sem nafn inni í setningu (*Anna Maria …*).
- **Nöfn skrifuð án stafmerkja.** Erlent nafn er aðeins merkt þegar ritháttur þess sjálfur er sönnun: stafir sem grunnstafrófið hefur ekki (`Kaczyński`), orðmynd sem aðeins orðasafn annars tilgreinds tungumáls þekkir, eða annað letur (`Качиньский` fær rússnesku). Margar ritstjórnir fella stafmerki brott úr erlendum nöfnum. Í RSS-fyrirsögnum sem safnað var 15. nóvember 2026 (Google News eftir löndum og eigin straumar vefmiðlanna) skrifuðu finnskir miðlar *Swiatek* í 8 fyrirsögnum af 8 og *Kaczynski* í 2 af 3, þó að *Wałęsa* héldi stöfum sínum í 6 af 7; í frönskum, ítölskum, spænskum og sænskum fyrirsögnum var stafmerkjalausa myndin í meirihluta fyrir að minnsta kosti tvö af þessum þremur nöfnum, þýskir og enskir miðlar héldu stöfunum að mestu og rússneskir umrita á kýrillískt letur. Nafn án stafmerkja, beygingarmyndir meðtaldar (*Kaczynskin*), er eingöngu úr stöfum grunnstafrófsins og er ekki í neinu orðasafni í þeirri mynd, svo það helst í grunnmálinu og rödd grunnmálsins les það, hvað sem `corpus_languages` telur upp. Textinn einn sker ekki úr um þetta og ATA giskar ekki á brottfelldu stafina: ef hvert óþekkt orð úr stöfum grunnstafrófsins væri borið saman við erlend orðasöfn án stafmerkja myndi röddin einnig skipta um á venjulegum orðum. Nafn úr tungumáli sem hér hefur engan pakka (*Erdoğan*) helst einnig í grunnmálinu.

## Bygging hugbúnaðarsafns

```
accessible_text_analyst/
├── accessible_text_analyst.ipynb   # aðalleiðsla (42 hólf)
├── generate_report.py              # HTML-skýrslu-myndari (lesendasýn)
├── generate_diagnostic.py          # greiningar-HTML-skýrsla úr CSV/JSON-útflutningi
├── generate_md.py                  # Gemini Notebook-Markdown-breytari
├── shamanic_pipeline.py            # valfrjálst: helgisiða-eftirvinnsluforrit án LLM
├── shamanic_ai.py                  # valfrjálst: LLM-drifnir helgisiðafrásagnamenn
├── llm_klient.py                   # val LLM-þjónustu og lykils (sameiginlegt)
├── shamanic_voice.py               # valfrjálst: ElevenLabs hljóðafgreiðari (keyrir einu sinni)
├── shamanic_locale.py              # staðfærsluböggull fyrir shamanístíska lagið
├── ksiega_niedomowien.py           # valfrjálst: Bók hins ósagða (aðeins finnska)
├── helsinki_reacts.py              # valfrjálst: handrit Helsinki Reacts-streyma (LLM)
├── helsinki_reacts.example.md      # sjálfgefin fyrirmæli Helsinki Reacts (í útgáfustýringu)
├── helsinki_reacts.md              # þitt eintak af fyrirmælunum (í .gitignore)
├── skills/ksiega-niedomowien/SKILL.md  # hæfni gervigreindarþjóns fyrir ksiega_niedomowien.py
├── config.example.json             # stillingarsniðmát, JSON-ending (versjónað)
├── config.example.ini              # stillingarsniðmát, INI-ending (versjónað)
├── config.json / config.ini        # þínar staðbundnu stillingar (gitignored)
├── golden_key.env                  # LLM- og ElevenLabs-lyklar (gitignored)
├── requirements.txt                # pip-pakkar
├── CLAUDE.md                       # leiðbeiningar fyrir Claude Code
├── README.md                       # kanónískt README (á ensku)
├── README_pl.md, README_ru.md, …   # þýðingar (afturhlekkur efst)
├── VERSION                         # útgáfulota í undirbúningi (`X.Y.Z-WIP` fram að útgáfu)
├── release_notes.md                # release notes í öfugri tímaröð
└── export_results/                 # greiningarútkomur (gitignored)
    ├── Sanomattomien_kirja.md      # Bók hins ósagða, bætt við smám saman
    ├── _streams/                   # handrit Helsinki Reacts
    └── <project_name>/
        ├── sentences.csv
        ├── paragraphs.csv
        ├── theses.csv
        ├── theses.txt              # nafn fer eftir tungumáli safnsins
        ├── accessible_text.html
        ├── accessible_text.docx
        ├── analysis_report.html
        ├── diagnostic_report.html
        ├── gemini_notebook_report.md
        └── audio_scripts/…
```

## Leyfi

Gefið út undir [MIT-leyfinu](LICENSE). Leiðslan er dreift aðeins sem frumkóði — engir tvíundir — og minnisbókin er í eðli sínu hægt að breyta hólf fyrir hólf í vafranum eða með Jupyter-viðbótinni fyrir VS Code. MIT-leyfið gerir einfaldlega skýrt það sem sniðið felur þegar í sér.
