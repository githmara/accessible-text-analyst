# Accessible Text Analyst

Fjöltyngd NLP-leiðsla hönnuð með **aðgengi fyrir skjálesara** í huga (NVDA, JAWS, VoiceOver, Narrator). Allur kóði, úttak í skel og skýrslur eru sett upp þannig að hjálpartæknin geti lesið þau hreint: engir ANSI-litir, engin tjáningartákn (emoji), engar framvinduslíkur, engin gervigrafík.

> **Önnur tungumál:** [English](README.md) · [polski](README_pl.md) · [русский](README_ru.md) · [suomi](README_fi.md) · [italiano](README_it.md)

> **i18n staða (v1.0).** Aðeins README hefur verið þýtt. Frásögn í minnisbókinni, allt skel-úttak, `CLAUDE.md` og athugasemdir í kóða halda sínum upprunalegu tungumálum (aðallega rússnesku; í patchum og shamanísku lagi pólsku). Þýðing á öðru er meðvitað frestað til v1.1 — sjá `release_notes.md`.

## Innihald verkefnisins

- `accessible_text_analyst.ipynb` — Jupyter-minnisbók með heilli greiningarleiðslu (42 hólf: 21 kóða + 21 markdown; frásögnin innan minnisbókarinnar er á rússnesku). Hún skrifar tvö aðgengisgripi (`accessible_text.html`, `accessible_text.docx`), þar sem hver málsgrein og hver erlend setning ber sitt eigið `lang`-eiginleika — skjálesarar og TTS-vélar skipta um rödd sjálfkrafa, jafnvel án nets.
- `generate_report.py` — eftirvinnsluforrit sem breytir framkvæmdri minnisbók í eina aðgengilega HTML-skrá (`analysis_report.html`). Það vefur erlend brot inn í `<span lang="target_lang">` og — óháð tungumáli safnsins — þvingar `<span lang="en">` utan um tæknilegt enskt innihald (POS-merki, NER-merki, auðkenni spaCy/Hugging Face líkana, ASCII-skráarnöfn). Inline-kóði og kóðablokkir í frásögn fá öll `lang="en"` í einu lagi. Í lesendaham (`remove_noise: true`) styttir það skjalkvíslar greiningarlykkjur minnisbókarinnar niður í fyrstu fáu skjölin í stað þess að prenta hundruð.
- `generate_diagnostic.py` — sjálfstæður smiður á heildstæðri **greiningarskýrslu** (`diagnostic_report.html`) sem byggð er beint á CSV/JSON-útflutningi minnisbókarinnar (ekki á úttaki `generate_report.py`). Aðgengileg uppbygging fyrir skjálesara: efnisyfirlit `<nav>` ásamt köflum — hver með eigin fyrirsögn og listum — fyrir yfirlit, þemu með málsgreinum, tesur, nafngreinda nafnliði eftir tegund og helstu lykilorð. Byggingartextar fylgja `ui_lang`; brot úr safninu fá `<span lang="…">`, NER-merki `<span lang="en">`.
- `generate_md.py` — breytir `analysis_report.html` í `notebooklm_report.md` fyrir NotebookLM. Aðgengis-spans eru afpökkuð því NotebookLM notar þau ekki.
- `shamanic_pipeline.py` *(valfrjálst)* — eftirvinnsluforrit án LLM sem breytir CSV/JSON-útflutningi minnisbókarinnar í helgisiðatextagripi (`oracle_script.txt`, `lore_fragments/`, `raw_roots_chant.txt`, `prophecies.txt` og — þegar valfrjáls tilfinningagreining er virk — `emotional_undertow.txt`), öll að fullu staðfærð fyrir sex studdu tungumálin.
- `shamanic_ai.py` *(valfrjálst, byggt á LLM)* — kallar í OpenAI til að búa til fjórar frásagnarraddir (`Katla`, `Vieno`, `Lumi`, `Sami`) ofan á sömu útflutninga. Þegar valfrjálsa `sentiment.csv` er til staðar byggir Vieno söng sinn á tilfinningabogadrætti textans í stað hráu setninganna. Krefst `OPENAI_API_KEY` í `golden_key.env`.
- `shamanic_locale.py` — staðfærsluböggull fyrir bæði shamanísku forritin (sniðmát, hausa og fallback-strengi Lumi á öllum sex tungumálum).

## Hvað gerir leiðslan

1. Hleður texta úr skrá (`.pdf`, `.txt`, `.docx`, `.html` eða myndum: `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`, `.webp`) eða úr URL — fjarlægir endurteknar haus-/fótlínur, hliðarspjöld, „Related articles"-kafla og álíka kjarna. Skannaðar PDF-skrár og myndainntak fá OCR (`pypdfium2` + `easyocr`) til vara.
2. Greinir tungumál safnsins með [`lingua-language-detector`](https://github.com/pemistahl/lingua-py). Ríkjandi tungumál stýrir spaCy-leiðslunni; sami greinir er endurnýttur per málsgrein og per setningu fyrir tungumálamerktan útflutning.
3. Hleður spaCy-líkönum **í tveimur þrepum**. Fyrst vinnur líkan ríkjandi tungumáls allt safnið frá byrjun til enda (tókun → stop-orð → uppslátt → POS → NER). Síðan endurkeyrir `cell_multilang_pass` málkennslupörin (NLP) aðeins fyrir málsgreinar þar sem greint tungumál er annað en ríkjandi — hleður hvert ekki-ríkjandi líkan að ósk gegnum `get_nlp()`, sem er vafið inn í `functools.lru_cache(maxsize=2)`. LRU-skyndiminnið skiptir aðeins máli í þessu öðru þrepi; aldrei eru fleiri en tvö líkön í minni samtímis.
4. Tókun → sía stop-orða → uppslátt → POS-merking → NER (tveggja þrepa fjöltyngdur NER með per-setningar dispatcher).
5. Vektorframsetning: Bag of Words, TF-IDF + sjálfsfyrirspurnaleit með cosinus-röðun.
6. Bygging: setningar → málsgreinar (3–6 setningar hver) → meginsetningar (besta setning per málsgrein). Hver málsgrein og setning er merkt með sínu ISO 639-1 kóða.
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
| fi   | finnska    | `fi_core_news_lg`      | spaCy          |
| is   | íslenska   | `spacy.blank("is")` + Hugging Face | `mideind/IceBERT-base` (vektorar), `mideind/icelandic-ner-MIM-GOLD-22` (NER) |

Það er ekkert fullt spaCy-líkan fyrir íslensku, því eru tvö Hugging Face líkön tengd inn í auða leiðslu. Fyrsta niðurhal krefst ~700 MB á diski og nettenginga; síðari keyrslur nota HF-skyndiminni.

## Tungumálagreining

Greining vinnur á þremur stigum:

1. **Ríkjandi í safni** — `cell_langdet` kýs per skjal og velur ríkjandi tungumálið sem `LANG`. Stýrir spaCy-leiðslunni.
2. **Per málsgrein** (`para_langs`) — notað sem `<p lang="...">` eiginleiki í `accessible_text.html` og sem sjálfgefið `<w:lang>` fyrir hverja málsgrein í `accessible_text.docx`.
3. **Per setning** (`sent_langs`) — notað til að vefja einstaka setningar í `<span lang="...">` innan málsgreina með blönduðu tungumáli (HTML) eða setja `<w:lang>` á per-setningar runa (DOCX).

Per-málsgreina og per-setningar greining notar viljandi **íhaldssama `_safe_detect()`-vafningu** í `cell_para`. Að treysta hráu lingua-úttaki veldur heyranlegum gripum: lingua flokkar ranglega stutt latnesk brot sem ráðin eru af sérnöfnum („Igor de Lendorf" → it, „Mut se mies, Igor" → en), og skjálesari sem skiptir yfir í enska rödd fyrir „Igor de Lendorf" og aftur á finnsku fyrir næstu setningu hljómar verr en að lesa sérnafnið með finnskum hreim.

Vafningin beitir eftirfarandi reglum í röð:

1. **Kýrílskir stafir hvar sem er í broti → `ru`.** Ótvírætt; virkar jafnvel á 3-stafa brotum.
2. **Brot styttra en 30 stafir → fallback `LANG`.** Lingua er óáreiðanleg á stuttum latneskum brotum.
3. **Brot inniheldur diakritíska stafi `LANG`** (t.d. `ä`/`ö` fyrir `fi`, `ąęć` fyrir `pl`) → fallback `LANG`. Finnsk setning með enskri tilvitnun er enn finnsk setning.
4. **Lingua er sammála `LANG`** → samþykkt.
5. **Lingua er ósammála, en greint tungumál hefur SÍNA eigin einkennandi diakritísku stafi í brotinu** (`à` fyrir it, `ż` fyrir pl, `ð` fyrir is) → treyst er lingua.
6. **Lingua er ósammála og greint tungumál hefur enga einkennandi diakritíska stafi í brotinu** (yfirleitt `en`) → fallback `LANG`.

Hvati reglu 6 er hreint hljóðfræðilegur: ensk rödd sem les finnsk/pólsk/ítölsk brot framleiðir greinilega bjögun, en finnsk/pólsk/ítölsk rödd sem les enska tilvitnun með léttum hreim er skiljanleg og óáreitin. Málamiðlunin er sú að hreinar enskar setningar í safni án ensku eru lesnar með ríkjandi rödd í stað þess að skipta yfir á ensku. Við sættum okkur við þessa málamiðlun því í reynd hafa notendur skjálesara greint frá ósamhverfri kostnaðargæðum.

Útlagar sem lifa af leiðslunnar eru listaðir í úttaki `cell_para` til handvirkrar yfirferðar (`Оставшиеся outlier-предложения...`). Sama diakritísk rökfræði stýrir per-`<code>` leiðslu (`_classify_code_lang`) í `generate_report.py` og per-hluta lingua-fallback (`_lingua_word_fallback`) fyrir slóðarlík ASCII-auðkenni.

## Kröfur

- Python 3.10 eða nýrri.
- ~1,5 GB af lausu plássi fyrir spaCy `_lg`-líkön (eitt per tungumál). Bættu við ~700 MB ef þú vilt íslenskustuðning (Hugging Face `transformers` + `torch` + IceBERT + MIM-GOLD-22).
- Bættu við ~700 MB ef þú vilt OCR-stuðning (`easyocr` sækir `torch` ásamt sínum greiningar- og þekkingarlíkönum við fyrsta OCR-kall). Ef þú virkjaðir líka íslensku deilist kostnaður `torch` milli beggja.
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
conda create -n accessible-text-analyst python=3.11
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

# 3. (Valfrjálst) Íslenskustuðningur — afkommenta `transformers` og
# `torch` í requirements.txt og keyrðu aftur `pip install -r requirements.txt`.
# IceBERT og MIM-GOLD-22 eru þá sótt frá Hugging Face við fyrstu keyrslu.

# 4. (Valfrjálst) Tilfinningagreining — afkommenta `transformers`, `torch`,
# `sentencepiece`, `protobuf` og `tiktoken` í requirements.txt, keyrðu aftur
# uppsetninguna og stilltu "enable_sentiment": true í config.json. Líkanið
# (~1.1 GB) er sótt frá Hugging Face við fyrstu keyrslu og geymt í skyndiminni eftir það.
# Alla fimm pakkana þarf saman til að byggja XLM-RoBERTa-tókarann.
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
  "ocr_languages": ["en"],
  "enable_sentiment": false,
  "ui_lang": "",
  "lumi_katla_lines": null,
  "lumi_vieno_lines": null
}
```

| Lykill             | Tegund          | Tilgangur |
|--------------------|-----------------|-----------|
| `source_file`      | string          | Slóð á skrá (`.pdf`, `.txt`, `.docx`, `.html` eða mynd) **eða** URL (`http://`, `https://`). Tómur strengur eða týnd skrá → innbyggður sýnishornssafn. |
| `custom_patterns`  | string[]        | Valfrjáls listi af reglulegum tjáningum sem eru fjarlægðar úr hráum texta (hlaupandi hausar, fætur, endurtekið kjarnamál). Dæmi: `["Editorial: .*", "Copyright \\d{4}"]`. |
| `remove_noise`     | boolean         | Skiptir `generate_report.py` á milli lesendaham (`true`, felur Hugging Face/torch hleðslulínur og uppsláttar/POS-töflur) og fullum greiningarham (`false`). |
| `ocr_languages`    | string[]        | Tungumál fyrir `easyocr` (notuð aðeins þegar PDF er skann eða uppspretta er mynd). Innan eins `easyocr.Reader` má aðeins blanda tungumálum úr sama letri — t.d. `["ru", "en"]` fyrir kýrillíska eða `["en", "pl", "it", "fi", "is"]` fyrir latneska. |
| `enable_sentiment` | boolean         | Kveikir á valfrjálsri tilfinningagreiningu per málsgrein (`false` sjálfgefið). Krefst hinna afkommentuðu tilfinningapakka (sjá Uppsetning, skref 4). Skrifar `sentiment.csv`; niðurstaðan er aldrei sýnd notandanum, hún fóðrar aðeins shamaníska lagið (helgisiðinn `emotional_undertow.txt` og söng Vieno). Við hverja hleðsluvillu er einfaldlega sleppt — engin fallback. |
| `ui_lang`          | string          | Tungumál notendaviðmóts fyrir úttak í skel og `<html lang>` eigind í myndaðri skýrslu (`pl` / `en` / `ru` / `fi` / `is` / `it`). Tómur strengur eða óþekktur kóði → fallback `en`. Óháð tungumáli greinda safnsins, sem er greint sjálfvirkt. |
| `lumi_katla_lines` | heiltala eða null | Valfrjáls skrautmark fyrir lokaskýrslu Lumi úr `shamanic_ai.py`: hve margar ekki-tómar línur einræðu Kötlu Lumi sér. `null` eða vantandi lykill = allt innihald; heiltala N > 0 = fyrstu N línurnar. |
| `lumi_vieno_lines` | heiltala eða null | Það sama og `lumi_katla_lines`, en fyrir bergmálsöng Vieno. |

> **Tilfinningagreining — álag á örgjörva.** Þegar `enable_sentiment: true` er virkt er greiningin per málsgrein reikniþung á CPU — nokkurn veginn sambærileg við að keyra staðbundna Whisper tal-í-texta á CPU. Á eldri eða hitatakmörkuðum vélum getur þetta viðvarandi álag verið raunverulegt erfiði fyrir örgjörvann; virkjaðu það meðvitað, helst á vél með GPU eða með svigrúm fyrir langvarandi vinnu á fullu álagi.

> **`ui_lang` — umfang staðfærslu.** Skel-úttak fjögurra skripta í kringum leiðsluna (`generate_report.py`, `generate_md.py`, `shamanic_pipeline.py`, `shamanic_ai.py`) er að fullu staðfært. Sjálf minnisbókin er *að hluta* staðfærð — 16 kaflahausar (`--- Heiti ---`), öll lokaskýrslan `cell_summary` og kveðjan „Q&A tilbúið" í `cell_qa_rag` fylgja `ui_lang`, en greiningar-prentanir á hverju þrepi (smáatriði um hleðslu safnsins, OCR-framvinda, forskoðanir tákna/POS/NER, fjöltyngd greining) haldast rússneskar. Minnisbókin er tól fyrir þróunaraðila; **að fullu staðfærður notendaskjár-artefakt er `analysis_report.html`** sem `generate_report.py` býr til. Þýðingar í `fi` / `is` / `it` eru drög og óyfirfarnar — tilkynntu ónákvæmni á GitHub.

> **Windows-slóðir og regex — mikilvægt.** Innihald stillinganna er JSON og JSON hefur enga raw-strengja-málskipan. Ein bakskáslína sleppir næsta staf (`\U`, `\d`, `\n` eru sérstakir), þannig að Windows-slóð skrifuð sem `"C:\Users\marek\doc.pdf"` veldur villu við JSON-túlkun. Tvær réttar leiðir til að skrifa hana:
>
> - **Áframslínur** (einfaldast, virkar líka á Windows): `"C:/Users/marek/doc.pdf"`.
> - **Tvöfaldar bakskáslínur**: `"C:\\Users\\marek\\doc.pdf"`.
>
> Sama regla á við um sérhverja reglulega tjáningu í `custom_patterns`: skrifaðu `"\\d{4}"`, ekki `"\d{4}"`; skrifaðu `"Copyright \\d{4}"`, ekki `"Copyright \d{4}"`. Í JSON er engin `r"…"`-málskipan fyrir raw-strengi.

## Keyrsla

Skriftunum hér að neðan er ætlað að keyra **í röð**: hver tekur við gripum úr fyrra skrefi.

### 1. Minnisbók (skyldug)

```bash
jupyter notebook accessible_text_analyst.ipynb
# (Cell → Run All)
```

Þetta er raðleiðsla með sameiginlegri hnattrænni stöðu. **Ekki endurraða hólfum og ekki keyra þau úr röð.** Minnisbókin skrifar `export_results/<project>/sentences.csv`, `paragraphs.csv`, `theses.csv`, `keywords_tfidf.csv`, `paragraphs_with_topics.csv`, `topic_keywords.json`, `entities.csv`, `accessible_text.html`, `accessible_text.docx` og `theses.txt`.

### 2. HTML-skýrslur (mælt með)

```bash
python generate_report.py
# → export_results/<project>/analysis_report.html
```

`generate_report.py` les úttak hólfa beint úr `.ipynb`-skránni, þannig að HTML-skýrslan verður að vera mynduð úr **nýkeyrðri** minnisbók. `requirements.txt` listar `nbstripout` — ef hann hefur verið virkjaður í staðbundinni git-stillingu eru úttök minnisbókarinnar fjarlægð við commit. Myndaðu skýrsluna _áður_ en þú commitar, eða slökktu á nbstripout fyrir vinnuflæði þitt.

Fyrir uppbyggða, heildstæða **greiningarsýn** sem byggð er beint á CSV/JSON-útflutningnum:

```bash
python generate_diagnostic.py
# → export_results/<project>/diagnostic_report.html
```

`generate_diagnostic.py` les aðeins útfluttu CSV/JSON-skrárnar, þannig að — ólíkt `generate_report.py` — þarf það ekki nýkeyrða minnisbók, aðeins útflutninginn sem minnisbókin skrifaði. Niðurstaðan er aðgengilegt skjal (efnisyfirlit, fyrirsagnir, listar) sem nær yfir þemu, tesur, nafnliði eftir tegund og helstu lykilorð.

### 3. NotebookLM-vænt Markdown (valfrjálst)

```bash
python generate_md.py
# → export_results/<project>/notebooklm_report.md
```

Þetta breytir HTML-skýrslunni í Markdown-skrá þar sem aðgengis-spans hafa verið afpökkuð (NotebookLM notar ekki `<span lang="…">`). Keyrðu þetta aðeins ef þú vilt mata skýrsluna inn í NotebookLM.

### 4. Shamanískt eftirvinnsluforrit án LLM (valfrjálst)

```bash
python shamanic_pipeline.py
# → export_results/<project>/audio_scripts/oracle_script.txt
#                                          /raw_roots_chant.txt
#                                          /prophecies.txt
#                                          /lore_fragments/intercepted_log_T*_P*.txt
#                                          /emotional_undertow.txt   # aðeins ef sentiment.csv er til
```

Býr til helgisiðatextagripi beint úr CSV/JSON-útflutningi minnisbókarinnar — engin LLM-köll, ekkert net. Allir strengir koma úr `shamanic_locale.py` og eru að fullu staðfærðir á öll sex studdu tungumálin. Þegar valfrjálsa `sentiment.csv` er til staðar býr það einnig til `emotional_undertow.txt` — „tilfinningaflóð" per málsgrein ásamt jafnvægissamantekt; án hennar er þeim eina helgisiða einfaldlega sleppt.

### 5. Shamanískt LLM eftirvinnsluforrit (valfrjálst, krefst OpenAI lykils)

```bash
python shamanic_ai.py
# → export_results/<project>/audio_scripts/katla_entity_monologue.txt
#                                          /vieno_echoes_chant.txt
#                                          /lumi_final_report.txt
#                                          /sami_energetic_spark.txt
```

Krefst OpenAI API-lykils. Búðu til `golden_key.env` í rót verkefnisins:

```
OPENAI_API_KEY=sk-...
```

`golden_key.env` passar við `*.env` í `.gitignore`, því verður það ekki committað. Raddirnar fjórar keyra í röð:

1. **Katla** breytir entítetalistanum (`entities.csv`) í einræðu frosinna norrænna anda.
2. **Vieno** syngur yfir lykilorða-/þemalistann. Sjálfgefið vefur hún inn fimm hráum setningum úr safninu sem bergmáli frá öðrum víddum; þegar valfrjálsa `sentiment.csv` er til staðar les hún í staðinn tilfinningabogadrátt textans (tilfinningar per málsgrein, niðurúrtaktar til að rúmast innan tákamarka líkansins á löngum söfnum) og lætur hann móta hreyfiafl söngsins.
3. **Lumi** les `prophecies.txt` (skylda) auk einræðu Katlu og söngs Vieno (valfrjálst skraut) og myndar lokaskýrslu. Staðfærðir fallback-strengir taka við þegar Katla eða Vieno vantar.
4. **Sami** les skýrslu Lumi og afhendir orkuríka samantekt með neista vonar eða ákalli til aðgerða.

## Úttak

Hver greint safn fær sína undirmöppu undir `export_results/`, nefnda eftir upprunaskránni (slóð og ending fjarlægð) eða eftir `domain_slug` fyrir URL. Innbyggða sýnishornssafnið notar `export_results/_default/`.

Hver undirmappa inniheldur:

| Skrá                            | Búin til af       | Lýsing                                            |
|---------------------------------|-------------------|---------------------------------------------------|
| `sentences.csv`                 | minnisbók         | hver setning með vísitölu og málsgreinatengingu   |
| `paragraphs.csv`                | minnisbók         | málsgreinar (3–6 setningar hver)                  |
| `theses.csv`, `theses.txt`      | minnisbók         | ein meginsetning per málsgrein (hæsta-TF-IDF setning); `.txt`-skráarnafnið fer eftir tungumáli safnsins (t.d. `tezy.txt` fyrir pólsku, `тезисы.txt` fyrir rússnesku) |
| `keywords_tfidf.csv`            | minnisbók         | lykilorð (uni/bi/trigröm) með TF-IDF-vægi         |
| `paragraphs_with_topics.csv`    | minnisbók         | málsgreinar með úthlutuðu KMeans-þema             |
| `topic_keywords.json`           | minnisbók         | lykilorð per þema                                 |
| `entities.csv`                  | minnisbók         | öll nefnd entítet og merkimiðar þeirra            |
| `sentiment.csv`                 | minnisbók *(valfrjálst)* | tilfinning per málsgrein (`para_id`, `label`, `score`, `lang`) — aðeins þegar `enable_sentiment` er `true`; fóður fyrir shamaníska lagið, aldrei sýnt notandanum |
| `accessible_text.html`          | minnisbók         | `lang`-eiginleikar á málsgreinar- og setningarstigi — skjálesarar skipta um rödd sjálfkrafa per brot |
| `accessible_text.docx`          | minnisbók         | sama innihald með `<w:lang>` stilltu per `Run` (`pl-PL`, `ru-RU`, `en-US`, `it-IT`, `fi-FI`, `is-IS`) — Word og SAPI nota það án nets, án nettengs greinis |
| `analysis_report.html`           | `generate_report.py` | heildar aðgengileg HTML-skýrsla                |
| `diagnostic_report.html`         | `generate_diagnostic.py` | uppbyggð greiningarskýrsla (þemu, tesur, nafnliðir eftir tegund, lykilorð) úr CSV/JSON-útflutningi |
| `notebooklm_report.md`      | `generate_md.py`     | NotebookLM-tilbúið Markdown                    |
| `audio_scripts/*.txt`           | `shamanic_pipeline.py`, `shamanic_ai.py` | helgisiða- / frásagnartextagripi |

## Aðgengi

Þetta er kjarnagildi verkefnisins. Allt hér að neðan er ásetningsvert og verður að varðveita við breytingar á leiðslunni:

- **Engir ANSI-litir, tjáningartákn eða gervigrafík í stdout.** Skjálesari les hvern staf bókstaflega — `[OK]` í stað „🟢", `---` í stað „───━━━".
- **Þaggaðar framvinduslíkur** (`tqdm`, `transformers`, `torch`) — `cell_model._silence_hf_progress()` þaggar Hugging Face/torch hleðslulínur og viðvaranir áður en IceBERT og MIM-GOLD-22 eru sótt fyrir íslensku; `cell_corpus._silence_ocr_progress()` gerir það sama fyrir `easyocr`.
- **Per-málsgreinar og per-setningar `lang`-merking í útflutningi.** `accessible_text.html` og `accessible_text.docx` bera ISO 639-1 kóða á hverri málsgrein (og á hverri setningu innan málsgreina/runa með blönduðu tungumáli). NVDA, JAWS, Narrator, VoiceOver, Word og SAPI virða þessi merki og skipta um rödd sjálfkrafa — jafnvel án nets.
- **Harðkóðuð enskumerking í HTML-skýrslunni.** `generate_report.py` vefur alltaf tæknileg ensk brot — POS-merki (`NOUN`, `VERB`, `ADJ`), NER-merki (`PER`, `ORG`, `[orgName]`), auðkenni spaCy / Hugging Face líkana, ASCII-slóðir, kóðablokkir — inn í `<span lang="en">`, þannig að þau eru ekki lengur lesin með sjálfgefnu rússnesku rödd skjalsins.
- **Per-brot merking erlends safns í HTML.** Þegar safnið er ekki rússneskt eru uppbyggð úttök (setningarútdrættir, lykilorðalistar, þemorðsorð, RAG-röðunarraðir, uppsláttartöflur) vafin í `<span lang="target_lang">`.
- **Línuleg HTML-bygging** (`<main>`, rétt fyrirsagnastigveldi).

### Lestur niðurstaðna sem ekki-rússneskumælandi notandi

Frásögn vinnubókarinnar og `print()`-úttak flestra hólfa er skrifað á rússnesku. Tveir eiginleikar Jupyter-viðmótsins gera þetta erfitt fyrir ekki-rússneskumælandi skjáleskara notendur, og pípan leggur til sértæka lausn fyrir hvora:

- **Jupyter í vafranum harðkóðar `lang="en"` á skjalið**, og „Þýða þessa síðu?" tilkynning birtist hvort sem er aldrei fyrir síður á `localhost`. Vinnubók með rússneskri frásögn er því lesin með enskri TTS-rödd — algjör ringulreið. Hagsýn lausn er **Jupyter-viðbótin fyrir VS Code**: listasýn hennar les aðeins `code cell` / `markdown cell` merki án ISO-merkinga, þú getur ýtt á Enter í kóðahólfum og ↓ farið framhjá markdown-hólfum án þess að hlusta á innihald þeirra, og harðkóðaða ensku-vandamálið takmarkast við úttakssýn (`Ctrl+Shift+↓`), sem þú getur einfaldlega ekki opnað.
- **`generate_report.py` er nánast skylda fyrir ekki-rússneskumælandi lesendur.** Það býr til `analysis_report.html` með `<html lang="ru">` og fullu setti af `<span lang="…">` merkjum fyrir hvert brot. Opnað í venjulegum vafra (ekki innan Jupyter), kveikir það á „Þýða þessa síðu?" tilkynningu vafrans fyrir rússnesku frásögnina, en heldur jafnframt TTS-raddaskiptum á brotum safnsins og á enskum tæknilegum hugtökum (POS, NER, líkana-nöfn).
- **Gagnvirk Q&A skrifar `qa_results.html` og opnar það fyrir þig.** `cell_qa_rag` prentar enn spurninguna og þrjár efstu niðurstöður í stdout — en það skrifar einnig sama efni í `export_results/<project>/qa_results.html` og kallar á `webbrowser.open()`, þannig að síðan lendir í kerfisvafranum, þar sem bæði þýðing og per-brot raddaskipti TTS virka. Úttakssýnin í Jupyter, þar sem harðkóðað `lang="en"` gerir rússnesku umbúðirnar ólesanlegar fyrir skjáleskara, er þannig ekki lengur eina leiðin að niðurstöðunni. Hver ný fyrirspurn skrifar yfir skrána.

## Bygging hugbúnaðarsafns

```
accessible_text_analyst/
├── accessible_text_analyst.ipynb   # aðalleiðsla (42 hólf)
├── generate_report.py              # HTML-skýrslu-myndari (lesendasýn)
├── generate_diagnostic.py          # greiningar-HTML-skýrsla úr CSV/JSON-útflutningi
├── generate_md.py                  # NotebookLM-Markdown-breytari
├── shamanic_pipeline.py            # valfrjálst: helgisiða-eftirvinnsluforrit án LLM
├── shamanic_ai.py                  # valfrjálst: LLM-drifnir helgisiðafrásagnamenn
├── shamanic_locale.py              # staðfærsluböggull fyrir shamanístíska lagið
├── config.example.json             # stillingarsniðmát, JSON-ending (versjónað)
├── config.example.ini              # stillingarsniðmát, INI-ending (versjónað)
├── config.json / config.ini        # þínar staðbundnu stillingar (gitignored)
├── golden_key.env                  # OpenAI-lykill fyrir shamanic_ai.py (gitignored)
├── requirements.txt                # pip-pakkar
├── CLAUDE.md                       # leiðbeiningar fyrir Claude Code
├── README.md                       # kanónískt README (á ensku)
├── README_pl.md, README_ru.md, …   # þýðingar (afturhlekkur efst)
├── release_notes.md                # release notes í öfugri tímaröð
└── export_results/                 # greiningarútkomur (gitignored)
    └── <project_name>/
        ├── sentences.csv
        ├── paragraphs.csv
        ├── theses.csv
        ├── theses.txt              # nafn fer eftir tungumáli safnsins
        ├── accessible_text.html
        ├── accessible_text.docx
        ├── analysis_report.html
        ├── diagnostic_report.html
        ├── notebooklm_report.md
        └── audio_scripts/…
```

## Leyfi

Gefið út undir [MIT-leyfinu](LICENSE). Leiðslan er dreift aðeins sem frumkóði — engir tvíundir — og minnisbókin er í eðli sínu hægt að breyta hólf fyrir hólf í vafranum eða með Jupyter-viðbótinni fyrir VS Code. MIT-leyfið gerir einfaldlega skýrt það sem sniðið felur þegar í sér.
