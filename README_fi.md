# Accessible Text Analyst

Monikielinen NLP-putki, joka on suunniteltu **ruudunlukijoiden saavutettavuutta** silmällä pitäen (NVDA, JAWS, VoiceOver, Narrator). Kaikki koodi, konsolituloste ja raportit on rakennettu niin, että avustava teknologia jäsentää ne puhtaasti: ei ANSI-värejä, ei emojeita, ei edistymispalkkeja eikä pseudografiikkaa.

> **Muut kielet:** [English](README.md) · [polski](README_pl.md) · [русский](README_ru.md) · [íslenska](README_is.md) · [italiano](README_it.md)

> **i18n-tilanne (v1.0).** Vain README on käännetty. Notebookin kerronta, kaikki konsolituloste, `CLAUDE.md` ja koodin kommentit pysyvät alkuperäisillä kielillään (pääosin venäjä; patcheissä ja shamanistisessa kerroksessa puola). Loppujen kääntäminen on tietoisesti siirretty versioon v1.1 — yksityiskohdat tiedostossa `release_notes.md`.

## Projektin sisältö

- `accessible_text_analyst.ipynb` — Jupyter-notebook, joka sisältää koko analyysiputken (40 solua: 20 koodia + 20 markdown; sisäinen kerronta on venäjäksi). Kirjoittaa kaksi saavutettavuusartefaktia (`accessible_text.html`, `accessible_text.docx`), joissa jokainen kappale ja jokainen vieraskielinen lause sisältää oman `lang`-attribuuttinsa — ruudunlukijat ja TTS-moottorit vaihtavat ääntä automaattisesti, jopa offline-tilassa.
- `generate_report.py` — jälkikäsittelyskripti, joka muuntaa suoritetun notebookin yhdeksi saavutettavaksi HTML-tiedostoksi (`analysis_report.html`). Se kääräisee vieraskieliset katkelmat tagiin `<span lang="target_lang">` ja — korpuksen kielestä riippumatta — pakottaa `<span lang="en">` teknisen englannin sisältöön (POS-tagit, NER-tunnisteet, spaCyn/Hugging Facen mallien tunnisteet, ASCII-polut). Kerronnan inline-koodi ja koodilohkot saavat poikkeuksetta `lang="en"`. Lukutilassa (`remove_noise: true`) se lyhentää notebookin dokumenttikohtaiset diagnostiikkasilmukat ensimmäisiin muutamaan dokumenttiin satojen tulostamisen sijaan.
- `generate_diagnostic.py` — riippumaton täyden **diagnostiikkaraportin** (`diagnostic_report.html`) luoja, joka rakennetaan suoraan notebookin CSV/JSON-vienneistä (ei `generate_report.py`:n ulostulosta). Navigoitava, ruudunlukijoille suunniteltu rakenne: sisällysluettelo `<nav>` ja osiot — kullakin oma otsikko ja listat — yleiskatsaukselle, aiheille kappaleineen, teeseille, nimetyille entiteeteille tyypeittäin ja tärkeimmille avainsanoille. Rakenteelliset tekstit seuraavat `ui_lang`-asetusta; korpuksen katkelmat saavat `<span lang="…">`, NER-tunnisteet `<span lang="en">`.
- `generate_md.py` — muuntaa `analysis_report.html`-tiedoston Markdown-muotoon (`notebooklm_report.md`) NotebookLM:ää varten. Saavutettavuus-spanit puretaan, koska NotebookLM ei käytä niitä.
- `shamanic_pipeline.py` *(valinnainen)* — ei-LLM-jälkikäsittelijä, joka muuntaa notebookin CSV/JSON-viennit neljäksi rituaaliseksi tekstiartefaktiksi (`oracle_script.txt`, `lore_fragments/`, `raw_roots_chant.txt`, `prophecies.txt`) ja on täysin lokalisoitu kaikille kuudelle tuetulle kielelle.
- `shamanic_ai.py` *(valinnainen, LLM-pohjainen)* — kutsuu OpenAI:ta neljän kerronnallisen äänen (`Katla`, `Vieno`, `Lumi`, `Sami`) tuottamiseen samojen vientien päälle. Vaatii `OPENAI_API_KEY`:n tiedostossa `golden_key.env`.
- `shamanic_locale.py` — molempien shamanististen skriptien lokalisointipaketti (mallit, otsikot ja Lumin fallback-merkkijonot kaikilla kuudella kielellä).

## Mitä putki tekee

1. Lataa tekstin tiedostosta (`.pdf`, `.txt`, `.docx`, `.html` tai kuvista: `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`, `.webp`) tai URL-osoitteesta — poistaen toistuvat ylä- ja alatunnisteet, sivupalkit, "Related articles" -osiot ja vastaavan kalvotekstin. Skannatut PDF:t ja kuvasyötteet siirtyvät OCR:lle (`pypdfium2` + `easyocr`).
2. Tunnistaa korpuksen kielen [`lingua-language-detector`-kirjastolla](https://github.com/pemistahl/lingua-py). Hallitseva kieli ohjaa spaCy-putken; sama tunnistin käytetään uudelleen kappale- ja lausekohtaisesti kielitagitettua vientiä varten.
3. Lataa spaCy-mallit **kahdessa vaiheessa**. Ensin hallitsevan kielen malli käsittelee koko korpuksen alusta loppuun (tokenointi → stop-sanat → lemmatisointi → POS → NER). Sitten `cell_multilang_pass` toistaa kielikohtaiset NLP-läpiajot vain niille kappaleille, joiden tunnistettu kieli eroaa hallitsevasta — ladaten jokaisen ei-hallitsevan mallin tarpeen mukaan funktion `get_nlp()` kautta, joka on kääritty `functools.lru_cache(maxsize=2)`:een. LRU-välimuistilla on merkitystä vasta tässä toisessa vaiheessa; muistissa on milloin tahansa enintään kaksi mallia.
4. Tokenointi → stop-sanojen suodatus → lemmatisointi → POS-merkitseminen → NER (kaksivaiheinen monikielinen NER lausekohtaisella mallin dispatcherilla).
5. Vektoriedustukset: Bag of Words, TF-IDF + auto-kyselyhaku kosinilajittelulla.
6. Rakenne: lauseet → kappaleet (3–6 lausetta kukin) → teesit (paras lause per kappale). Jokainen kappale ja lause merkitään tunnistetulla ISO 639-1 -koodilla.
7. Aiheen mallinnus KMeansilla spaCyn kappalevektoreiden päällä.
8. CSV/JSON-vienti + tekstimuotoinen yhteenvetoraportti + saavutettava HTML- ja DOCX-vienti + globaali HTML-raportti (`analysis_report.html`).

## Tuetut kielet

| Koodi | Kieli      | spaCy-malli            | NER / vektorit |
|-------|------------|------------------------|----------------|
| pl    | puola      | `pl_core_news_lg`      | spaCy          |
| ru    | venäjä     | `ru_core_news_lg`      | spaCy          |
| en    | englanti   | `en_core_web_lg`       | spaCy          |
| it    | italia     | `it_core_news_lg`      | spaCy          |
| fi    | suomi      | `fi_core_news_lg`      | spaCy          |
| is    | islanti    | `spacy.blank("is")` + Hugging Face | `mideind/IceBERT-base` (vektorit), `mideind/icelandic-ner-MIM-GOLD-22` (NER) |

Islannille ei ole täyttä spaCy-mallia, joten tyhjään putkeen on liitetty kaksi Hugging Face -mallia. Ensimmäinen lataus vaatii ~700 MB levytilaa ja internetyhteyden; seuraavat ajot käyttävät HF-välimuistia.

## Kielentunnistus

Tunnistus toimii kolmella tasolla:

1. **Hallitseva korpuksessa** — `cell_langdet` äänestää dokumenteittain ja valitsee hallitsevan kielen `LANG`:ksi. Ohjaa spaCy-putkea.
2. **Kappaleittain** (`para_langs`) — käytetään attribuuttina `<p lang="...">` tiedostossa `accessible_text.html` ja oletuksena `<w:lang>` jokaiselle kappaleelle tiedostossa `accessible_text.docx`.
3. **Lauseittain** (`sent_langs`) — käytetään yksittäisten lauseiden käärimiseen tagiin `<span lang="...">` sekakielisten kappaleiden sisällä (HTML) tai `<w:lang>`:n asettamiseen lausekohtaisille runeille (DOCX).

Kappale- ja lausekohtainen tunnistus käyttää tarkoituksellisesti **konservatiivista `_safe_detect()`-kääre** soluss `cell_para`. Linguan raakaan ulostuloon luottaminen aiheuttaa kuultavia artefakteja: lingua luokittelee väärin lyhyitä latinalaisia katkelmia, joita hallitsevat erisnimet ("Igor de Lendorf" → it, "Mut se mies, Igor" → en), ja ruudunlukija, joka vaihtaa englannin ääneen kohtaan "Igor de Lendorf" ja palaa suomeen seuraavalla lauseella, kuulostaa huonommalta kuin että erisnimi luettaisiin suomalaisella aksentilla.

Kääre soveltaa seuraavia sääntöjä järjestyksessä:

1. **Kyrilliset merkit missä tahansa katkelmassa → `ru`.** Yksiselitteistä; toimii jopa 3 merkin katkelmilla.
2. **Katkelma lyhyempi kuin 30 merkkiä → fallback `LANG`.** Lingua on epävarma lyhyillä latinalaisilla katkelmilla.
3. **Katkelma sisältää `LANG`:n diakriittejä** (esim. `ä`/`ö` kielelle `fi`, `ąęć` kielelle `pl`) → fallback `LANG`. Suomalainen lause englanninkielisellä lainauksella on yhä suomalainen lause.
4. **Lingua on samaa mieltä `LANG`:n kanssa** → hyväksytään.
5. **Lingua on eri mieltä, mutta tunnistettu kieli sisältää OMIA tunnusomaisia diakriittejään katkelmassa** (`à` italialle, `ż` puolalle, `ð` islannille) → luotetaan linguaan.
6. **Lingua on eri mieltä eikä tunnistetulla kielellä ole tunnusomaisia diakriittejä katkelmassa** (tyypillisesti `en`) → fallback `LANG`.

Säännön 6 motivaatio on puhtaasti foneettinen: englanninkielinen ääni, joka lukee suomalaisia/puolalaisia/italialaisia katkelmia, tuottaa kuultavaa vääristymää, kun taas suomalainen/puolalainen/italialainen ääni, joka lukee englanninkielisen lainauksen kevyellä aksentilla, on ymmärrettävä ja vähemmän häiritsevä. Kompromissi on, että puhtaasti englanninkieliset lauseet upotettuna ei-englanninkieliseen korpukseen luetaan hallitsevalla äänellä sen sijaan, että vaihdettaisiin englantiin. Hyväksymme tämän kompromissin, koska käytännössä ruudunlukijoiden käyttäjät raportoivat epäsymmetrisestä laatuhinnasta.

Heuristiikasta selviytyneet poikkeamat listataan `cell_para`:n ulostulossa manuaalista tarkastelua varten (`Оставшиеся outlier-предложения...`). Sama diakriittilogiikka ohjaa pir-`<code>`-heuristiikkaa (`_classify_code_lang`) tiedostossa `generate_report.py` sekä pirsegmenttistä lingua-fallbackia (`_lingua_word_fallback`) polkumaisille ASCII-tunnisteille.

## Vaatimukset

- Python 3.10 tai uudempi.
- ~1,5 GB vapaata levytilaa spaCyn `_lg`-malleja varten (yksi per kieli). Lisää ~700 MB, jos otat käyttöön islanninkielisen tuen (Hugging Face `transformers` + `torch` + IceBERT + MIM-GOLD-22).
- Lisää ~700 MB, jos otat käyttöön OCR-tuen (`easyocr` lataa `torch`:n sekä omat tunnistus- ja luonnistusmallinsa ensimmäisellä OCR-kutsulla). Jos otit käyttöön myös islanninkielen, `torch`:n kustannus jaetaan näiden välillä.
- Internet-yhteys ensimmäisellä ajolla (mallien lataus).

## Ympäristön asennus

Valitse yksi alla olevista kolmesta vaihtoehdosta. Kaikki päättyvät samaan komentoon `pip install -r requirements.txt` ja spaCy-mallien lataukseen.

### Vaihtoehto A — paikallinen `venv` (suositeltu päivittäiseen käyttöön)

```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Hakemisto `.venv/` on `.gitignore`:ssa. Aktivoidusta venvistä siirry kohtaan **Asennus**.

### Vaihtoehto B — Anaconda / Miniconda

```bash
conda create -n accessible-text-analyst python=3.11
conda activate accessible-text-analyst
```

Siirry sitten **Asennukseen**. Anacondan mukana tuleva `pip` toimii hyvin — projektille ei ole erillistä Conda-pakettilistaa.

### Vaihtoehto C — Google Colab (ei paikallista asennusta)

Avaa uusi Colab-notebook ja liitä ensimmäiseen soluun:

```python
!git clone https://github.com/<your-fork>/accessible_text_analyst.git
%cd accessible_text_analyst
!pip install -r requirements.txt
!python -m spacy download en_core_web_lg
# Lisää alla olevat rivit vain niille kielille, joita todella tarvitset:
# !python -m spacy download pl_core_news_lg
# !python -m spacy download ru_core_news_lg
# !python -m spacy download it_core_news_lg
# !python -m spacy download fi_core_news_lg
```

Lataa sitten `config.json` (tai `config.ini`) Files-paneelin kautta, aseta `source_file` ja aja notebook. Huomio: Colab-istunnot ovat lyhytaikaisia — ladatut mallit ja `export_results/`-artefaktit häviävät, kun runtime kierrätetään. Pidempiin analyyseihin liitä Google Drive ja kirjoita ulostulo sinne.

## Asennus

```bash
# 1. Python-riippuvuudet
pip install -r requirements.txt

# 2. spaCy-mallit — asenna vain ne kielet, joita oikeasti tarvitset.
# *_lg-variantit ovat pakollisia, koska aiheen mallinnus riippuu sanavektoreista.
python -m spacy download pl_core_news_lg
python -m spacy download ru_core_news_lg
python -m spacy download en_core_web_lg
python -m spacy download it_core_news_lg
python -m spacy download fi_core_news_lg

# 3. (Valinnainen) Islanninkielinen tuki — poista kommenttimerkit `transformers`:in ja
# `torch`:in edestä tiedostossa requirements.txt ja aja uudelleen `pip install -r requirements.txt`.
# IceBERT ja MIM-GOLD-22 ladataan sitten Hugging Facelta ensimmäisellä ajolla.
```

## Asetukset

Kopioi esimerkkiasetukset paikalliseksi tiedostoksi. Sekä `config.json` että `config.ini` hyväksytään — **tiedoston sisältö on JSON molemmissa tapauksissa**; pääte `.ini` on puhtaasti käytettävyysmyönnytys Windowsin ei-teknisille käyttäjille, joille `.json`:lla ei ole oletuskäsittelijää.

```bash
# Valitse yksi:
cp config.example.json config.json
cp config.example.ini  config.ini
```

`config.json` ja `config.ini` ovat molemmat `.gitignore`:ssa, joten jokainen käyttäjä pitää oman paikallisen kopionsa.

Sisältö:

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

| Avain              | Tyyppi          | Tarkoitus |
|--------------------|-----------------|-----------|
| `source_file`      | string          | Polku tiedostoon (`.pdf`, `.txt`, `.docx`, `.html` tai kuva) **tai** URL (`http://`, `https://`). Tyhjä merkkijono tai puuttuva tiedosto → sisäänrakennettu esimerkkikorpus. |
| `custom_patterns`  | string[]        | Valinnainen lista säännöllisistä lausekkeista, jotka poistetaan raakatekstistä (juoksevat otsikot, alatunnisteet, toistuvat kalvotekstit). Esimerkki: `["Editorial: .*", "Copyright \\d{4}"]`. |
| `remove_noise`     | boolean         | Vaihtaa `generate_report.py`:n lukijaystävällisen tilan (`true`, piilottaa Hugging Face/torch -latauspalkit ja lemmatisointi/POS-taulukot) ja täyden diagnostisen tilan (`false`) välillä. |
| `ocr_languages`    | string[]        | `easyocr`:n kielet (käytetään vain skannatuissa PDF:issä tai kuvalähteissä). Yhdessä `easyocr.Reader`-instanssissa voi sekoittaa vain saman kirjaimiston kieliä — esim. `["ru", "en"]` kyrilliselle tai `["en", "pl", "it", "fi", "is"]` latinalaiselle. |
| `ui_lang`          | string          | Käyttöliittymän kieli konsolituloste ja luodun raportin `<html lang>` -attribuutti (`pl` / `en` / `ru` / `fi` / `is` / `it`). Tyhjä merkkijono tai tuntematon koodi → fallback `en`. Riippumaton analysoidun korpuksen kielestä, joka tunnistetaan automaattisesti. |
| `lumi_katla_lines` | integer tai null | Valinnainen koristerajoitus `shamanic_ai.py`:n Lumin loppuraportille: kuinka monta ei-tyhjää riviä Katlan monologista Lumi näkee. `null` tai puuttuva avain = koko sisältö; integer N > 0 = ensimmäiset N riviä. |
| `lumi_vieno_lines` | integer tai null | Sama kuin `lumi_katla_lines`, mutta Vienon kaikulaululle. |

> **`ui_lang` — lokalisoinnin laajuus.** Neljän putken ympärillä olevan skriptin (`generate_report.py`, `generate_md.py`, `shamanic_pipeline.py`, `shamanic_ai.py`) konsolituloste on täysin lokalisoitu. Itse notebook on lokalisoitu *osittain* — 16 osion otsikkoa (`--- Otsikko ---`), koko lopullinen `cell_summary`-raportti ja `cell_qa_rag`-solun "Q&A valmis"-tervehdys seuraavat `ui_lang`-asetusta, mutta vaihekohtaiset diagnostiset printit (korpuksen latauksen yksityiskohdat, OCR-edistys, tokenien/POS/NER-esikatselut, monikielisen vaiheen diagnostiikka) pysyvät venäjäksi. Notebook on kehittäjälle tarkoitettu työkalu; **täysin lokalisoitu käyttäjälle näkyvä artefakti on `analysis_report.html`**, jonka tuottaa `generate_report.py`. Käännökset `fi` / `is` / `it` ovat luonnoksia eivätkä tarkistettuja — ilmoita epätarkkuuksista GitHubissa.

> **Windows-polut ja regexit — tärkeää.** Asetussisältö on JSON, eikä JSONissa ole raw-string-syntaksia. Yksittäinen kenoviiva escapeaa seuraavan merkin (`\U`, `\d`, `\n` ovat erikoismerkkejä), joten Windows-polku kirjoitettuna `"C:\Users\marek\doc.pdf"` aiheuttaa JSON-jäsennysvirheen. Kaksi oikeaa tapaa kirjoittaa se:
>
> - **Etukenoviivat** (yksinkertaisin, toimii myös Windowsissa): `"C:/Users/marek/doc.pdf"`.
> - **Tuplakenoviivat**: `"C:\\Users\\marek\\doc.pdf"`.
>
> Sama sääntö koskee jokaista säännöllistä lauseketta avaimessa `custom_patterns`: kirjoita `"\\d{4}"`, älä `"\d{4}"`; kirjoita `"Copyright \\d{4}"`, älä `"Copyright \d{4}"`. JSONissa ei ole `r"…"`-syntaksia raw-merkkijonoille.

## Suoritus

Alla olevat skriptit on tarkoitettu ajettaviksi **järjestyksessä**: jokainen käyttää edellisen vaiheen tuottamia artefakteja.

### 1. Notebook (pakollinen)

```bash
jupyter notebook accessible_text_analyst.ipynb
# (Cell → Run All)
```

Tämä on peräkkäinen putki, jolla on jaettu globaali tila. **Älä järjestä soluja uudelleen äläkä aja niitä järjestyksen ulkopuolella.** Notebook kirjoittaa `export_results/<project>/sentences.csv`, `paragraphs.csv`, `theses.csv`, `keywords_tfidf.csv`, `paragraphs_with_topics.csv`, `topic_keywords.json`, `entities.csv`, `accessible_text.html`, `accessible_text.docx` ja `theses.txt`.

### 2. HTML-raportit (suositeltu)

```bash
python generate_report.py
# → export_results/<project>/analysis_report.html
```

`generate_report.py` lukee solujen ulostulot suoraan `.ipynb`-tiedostosta, joten HTML-raportti on luotava **juuri suoritetusta** notebookista. `requirements.txt` listaa `nbstripout`:n — jos se on aktivoitu paikallisessa git-konfiguraatiossa, notebookin ulostulot riisutaan commitilla. Luo raportti _ennen_ commitia tai poista nbstripout käytöstä työnkulustasi.

Jäsenneltyä, täyttä **diagnostista** näkymää varten, joka rakennetaan suoraan CSV/JSON-vienneistä:

```bash
python generate_diagnostic.py
# → export_results/<project>/diagnostic_report.html
```

`generate_diagnostic.py` lukee vain viedyt CSV/JSON-tiedostot, joten — toisin kuin `generate_report.py` — se ei tarvitse juuri suoritettua notebookia, vaan ainoastaan notebookin kirjoittamat viennit. Tuloksena on navigoitava asiakirja (sisällysluettelo, otsikot, listat), joka kattaa aiheet, teesit, entiteetit tyypeittäin ja tärkeimmät avainsanat.

### 3. NotebookLM-ystävällinen Markdown (valinnainen)

```bash
python generate_md.py
# → export_results/<project>/notebooklm_report.md
```

Tämä muuntaa HTML-raportin Markdown-tiedostoksi, jossa saavutettavuus-spanit on purettu (NotebookLM ei käytä `<span lang="…">`). Aja tämä vain, jos haluat syöttää raportin NotebookLM:ään.

### 4. Shamanistinen ei-LLM-jälkikäsittelijä (valinnainen)

```bash
python shamanic_pipeline.py
# → export_results/<project>/audio_scripts/oracle_script.txt
#                                          /raw_roots_chant.txt
#                                          /prophecies.txt
#                                          /lore_fragments/intercepted_log_T*_P*.txt
```

Luo neljä rituaalista tekstiartefaktia suoraan notebookin CSV/JSON-vientien pohjalta — ei LLM-kutsua, ei verkkoa. Kaikki merkkijonot tulevat tiedostosta `shamanic_locale.py` ja on lokalisoitu kaikille kuudelle tuetulle kielelle.

### 5. Shamanistinen LLM-jälkikäsittelijä (valinnainen, vaatii OpenAI-avaimen)

```bash
python shamanic_ai.py
# → export_results/<project>/audio_scripts/katla_entity_monologue.txt
#                                          /vieno_echoes_chant.txt
#                                          /lumi_final_report.txt
#                                          /sami_energetic_spark.txt
```

Vaatii OpenAI API-avaimen. Luo `golden_key.env` projektin juuressa:

```
OPENAI_API_KEY=sk-...
```

`golden_key.env` täsmää kuvioon `*.env` `.gitignore`:ssa, joten sitä ei commitata. Neljä ääntä ajetaan järjestyksessä:

1. **Katla** muuttaa entiteettilistan (`entities.csv`) jäätyneiden pohjoisten henkien monologiksi.
2. **Vieno** kanttaa avainsana-/aiheluettelon yli viidellä raakalauseella korpuksesta toisen ulottuvuuden kaikuna.
3. **Lumi** lukee `prophecies.txt`:n (pakollinen) sekä Katlan monologin ja Vienon laulun (valinnainen koriste) ja tuottaa loppuraportin. Lokalisoidut fallback-merkkijonot kattavat tapauksen, jossa Katla tai Vieno puuttuvat.
4. **Sami** lukee Lumin raportin ja toimittaa korkeaenergisen synteesin toivon kipinällä tai toimintakutsulla.

## Tuloste

Jokainen analysoitu korpus saa oman alihakemistonsa kohdassa `export_results/`, nimettynä lähdetiedoston mukaan (polku ja pääte poistettuna) tai `domain_slug`:n mukaan URL-osoitteille. Sisäänrakennettu esimerkkikorpus käyttää `export_results/_default/`.

Jokainen alihakemisto sisältää:

| Tiedosto                        | Tuottaja          | Kuvaus                                            |
|---------------------------------|-------------------|---------------------------------------------------|
| `sentences.csv`                 | notebook          | jokainen lause indeksinsä ja kappaleeseen kuulumisensa kanssa |
| `paragraphs.csv`                | notebook          | kappaleet (3–6 lausetta kukin)                    |
| `theses.csv`, `theses.txt`      | notebook          | yksi teesi per kappale (korkein-TF-IDF-lause); `.txt`-tiedoston nimi mukautuu korpuksen kieleen (esim. `tezy.txt` puolaksi, `тезисы.txt` venäjäksi) |
| `keywords_tfidf.csv`            | notebook          | avainsanat (uni/bi/trigrammit) TF-IDF-painoineen  |
| `paragraphs_with_topics.csv`    | notebook          | kappaleet määrätyllä KMeans-aiheellaan            |
| `topic_keywords.json`           | notebook          | avainsanat aiheittain                             |
| `entities.csv`                  | notebook          | kaikki nimennetyt entiteetit ja niiden tunnisteet |
| `accessible_text.html`          | notebook          | kappale- ja lausetason `lang`-attribuutit — ruudunlukijat vaihtavat ääntä automaattisesti per katkelma |
| `accessible_text.docx`          | notebook          | sama sisältö `<w:lang>`:lla asetettuna per `Run` (`pl-PL`, `ru-RU`, `en-US`, `it-IT`, `fi-FI`, `is-IS`) — Word ja SAPI käyttävät sitä offline-tilassa ilman online-tunnistinta |
| `analysis_report.html`           | `generate_report.py` | globaali saavutettava HTML-raportti            |
| `diagnostic_report.html`         | `generate_diagnostic.py` | jäsennelty diagnostiikkaraportti (aiheet, teesit, entiteetit tyypeittäin, avainsanat) CSV/JSON-vienneistä |
| `notebooklm_report.md`      | `generate_md.py`     | NotebookLM-valmis Markdown                     |
| `audio_scripts/*.txt`           | `shamanic_pipeline.py`, `shamanic_ai.py` | rituaaliset / kerronnalliset tekstiartefaktit |

## Saavutettavuus

Tämä on projektin keskeinen arvo. Kaikki alla oleva on tarkoituksellista ja on säilytettävä, kun putkea muokataan:

- **Ei ANSI-värejä, emojeita tai pseudografiikkaa stdoutissa.** Ruudunlukija lukee jokaisen merkin kirjaimellisesti — `[OK]` "🟢":n sijaan, `---` "───━━━":n sijaan.
- **Vaiennetut edistymispalkit** (`tqdm`, `transformers`, `torch`) — `cell_model._silence_hf_progress()` mykistää Hugging Face/torch -latauspalkit ja varoitukset ennen IceBERT:in ja MIM-GOLD-22:n lataamista islanninkieltä varten; `cell_corpus._silence_ocr_progress()` tekee saman `easyocr`:lle.
- **Kappale- ja lausekohtainen `lang`-merkintä viennissä.** `accessible_text.html` ja `accessible_text.docx` kantavat ISO 639-1 -koodin jokaisessa kappaleessa (ja jokaisessa lauseessa sekakielisten kappaleiden / runejen sisällä). NVDA, JAWS, Narrator, VoiceOver, Word ja SAPI kunnioittavat näitä tageja ja vaihtavat ääntä automaattisesti — jopa offline-tilassa.
- **Kovakoodattu englannin merkintä HTML-raportissa.** `generate_report.py` kääräisee aina teknisen englannin katkelmat — POS-tagit (`NOUN`, `VERB`, `ADJ`), NER-tunnisteet (`PER`, `ORG`, `[orgName]`), spaCy / Hugging Face -mallien tunnisteet, ASCII-polut, koodilohkot — tagiin `<span lang="en">`, jolloin niitä ei enää ääntää dokumentin oletusvenäläisellä äänellä.
- **Vieraskielisen korpuksen pir-katkelmamerkintä HTML:ssä.** Kun korpus ei ole venäläinen, jäsennellyt ulostulot (lauseotteet, avainsanaluettelot, aihesanat, RAG-järjestysrivit, lemmatisointitaulukot) käärätään tagiin `<span lang="target_lang">`.
- **Lineaarinen HTML-rakenne** (`<main>`, oikea otsikkohierarkia).

### Tulosten lukeminen ei-venäjänkielisenä käyttäjänä

Notebookin selostus ja useimpien solujen `print()`-tuloste on kirjoitettu venäjäksi. Kaksi Jupyterin käyttöliittymän ominaisuutta tekevät siitä vihamielisen ei-venäjänkielisille ruudunlukijakäyttäjille, ja putki toimittaa kullekin oman kiertotien:

- **Selaimessa toimiva Jupyter koodaa kovakoodatusti `lang="en"` dokumenttiin**, eikä "Käännä tämä sivu?" -kehote koskaan ilmesty `localhost`-sivuilla. Venäjäksi selostettu notebook luetaan siten englanninkielisellä TTS-äänellä — täydellistä kaaosta. Pragmaattinen ratkaisu on **VS Code:n Jupyter-laajennus**: sen lista-näkymä lausuu vain `code cell` / `markdown cell` -etiketit ilman ISO-merkintöjä, voit painaa Enter koodisolujen läpi ja ↓ ohittaa markdown-solut kuuntelematta niiden sisältöä, ja kovakoodatun englannin ongelma rajoittuu tuloste-näkymään (`Ctrl+Shift+↓`), johon voi yksinkertaisesti olla menemättä.
- **`generate_report.py` on käytännössä pakollinen ei-venäjänkielisille lukijoille.** Se tuottaa `analysis_report.html`-tiedoston, jossa on `<html lang="ru">` ja täysi joukko `<span lang="…">`-tageja jokaiselle katkelmalle. Tavallisessa selaimessa avattuna (ei Jupyterin sisältä) se laukaisee selaimen "Käännä tämä sivu?" -kehotteen venäjänkieliselle selostukselle, säilyttäen samalla TTS-äänen vaihdon korpuksen katkelmilla ja englanninkielisillä teknisillä termeillä (POS, NER, mallien nimet).
- **Interaktiivinen Q&A kirjoittaa `qa_results.html`-tiedoston ja avaa sen puolestasi.** `cell_qa_rag` tulostaa edelleen kysymyksen ja kolme parasta osumaa stdoutiin — mutta lisäksi se kirjoittaa saman sisällön tiedostoon `export_results/<project>/qa_results.html` ja kutsuu `webbrowser.open()`, jolloin sivu päätyy järjestelmäselaimeen, jossa sekä käännös että per-katkelmainen TTS-äänen vaihto toimivat. Jupyterin tuloste-näkymä, jossa kovakoodattu `lang="en"` tekee venäjänkieliset kääreet ruudunlukijalle lukukelvottomiksi, ei siis enää ole ainoa polku tulokseen. Jokainen uusi kysely ylikirjoittaa tiedoston.

## Repositorion rakenne

```
accessible_text_analyst/
├── accessible_text_analyst.ipynb   # pääputki (40 solua)
├── generate_report.py              # HTML-raportin generaattori (lukijanäkymä)
├── generate_diagnostic.py          # diagnostiikka-HTML-raportti CSV/JSON-vienneistä
├── generate_md.py                  # NotebookLM-Markdown-muunnin
├── shamanic_pipeline.py            # valinnainen: ei-LLM rituaalinen jälkikäsittelijä
├── shamanic_ai.py                  # valinnainen: LLM-vetoiset rituaaliset kertojat
├── shamanic_locale.py              # lokalisointipaketti shamanistiselle kerrokselle
├── config.example.json             # asetusmalli, JSON-pääte (versioidaan)
├── config.example.ini              # asetusmalli, INI-pääte (versioidaan)
├── config.json / config.ini        # paikalliset asetuksesi (gitignored)
├── golden_key.env                  # OpenAI-avain shamanic_ai.py:lle (gitignored)
├── requirements.txt                # pip-riippuvuudet
├── CLAUDE.md                       # opas Claude Codelle
├── README.md                       # kanoninen README (englanniksi)
├── README_pl.md, README_ru.md, …   # käännökset (paluulinkki ylhäällä)
├── release_notes.md                # release notes käänteisessä aikajärjestyksessä
└── export_results/                 # analyysin tulokset (gitignored)
    └── <project_name>/
        ├── sentences.csv
        ├── paragraphs.csv
        ├── theses.csv
        ├── theses.txt              # nimi mukautuu korpuksen kieleen
        ├── accessible_text.html
        ├── accessible_text.docx
        ├── analysis_report.html
        ├── diagnostic_report.html
        ├── notebooklm_report.md
        └── audio_scripts/…
```

## Lisenssi

Julkaistu [MIT-lisenssillä](LICENSE). Putki jaetaan vain lähdekoodina — ei binäärejä — ja notebook on luonteeltaan muokattavissa solu kerrallaan selaimessa tai VS Coden Jupyter-laajennuksessa. MIT-lisenssi vain tekee eksplisiittiseksi sen, mitä formaatti jo edellyttää.
