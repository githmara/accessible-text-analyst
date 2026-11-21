# Accessible Text Analyst

Monikielinen NLP-putki, joka on suunniteltu **ruudunlukijoiden saavutettavuutta** silmällä pitäen (NVDA, JAWS, VoiceOver, Narrator). Kaikki koodi, konsolituloste ja raportit on rakennettu niin, että avustava teknologia jäsentää ne puhtaasti: ei ANSI-värejä, ei emojeita, ei edistymispalkkeja eikä pseudografiikkaa.

> **Muut kielet:** [English](README.md) · [polski](README_pl.md) · [русский](README_ru.md) · [íslenska](README_is.md) · [italiano](README_it.md) · [Deutsch](README_de.md) · [español](README_es.md) · [français](README_fr.md)

> **i18n-tilanne (v1.0).** Vain README on käännetty. Notebookin kerronta, kaikki konsolituloste, `CLAUDE.md` ja koodin kommentit pysyvät alkuperäisillä kielillään (pääosin venäjä; patcheissä ja shamanistisessa kerroksessa puola). Loppujen kääntäminen on tietoisesti siirretty versioon v1.1 — yksityiskohdat tiedostossa `release_notes.md`.

## Projektin sisältö

- `accessible_text_analyst.ipynb` — Jupyter-notebook, joka sisältää koko analyysiputken (42 solua: 21 koodia + 21 markdown; sisäinen kerronta on venäjäksi). Kirjoittaa kaksi saavutettavuusartefaktia (`accessible_text.html`, `accessible_text.docx`), joissa jokainen kappale ja jokainen vieraskielinen lause sisältää oman `lang`-attribuuttinsa — ruudunlukijat ja TTS-moottorit vaihtavat ääntä automaattisesti, jopa offline-tilassa.
- `generate_report.py` — jälkikäsittelyskripti, joka muuntaa suoritetun notebookin yhdeksi saavutettavaksi HTML-tiedostoksi (`analysis_report.html`). Se kääräisee vieraskieliset katkelmat tagiin `<span lang="target_lang">` ja — korpuksen kielestä riippumatta — pakottaa `<span lang="en">` teknisen englannin sisältöön (POS-tagit, NER-tunnisteet, spaCyn/Hugging Facen mallien tunnisteet, ASCII-polut). Kerronnan inline-koodi ja koodilohkot saavat poikkeuksetta `lang="en"`. Lukutilassa (`remove_noise: true`) se lyhentää notebookin dokumenttikohtaiset diagnostiikkasilmukat ensimmäisiin muutamaan dokumenttiin satojen tulostamisen sijaan.
- `run_all.py` — koko maksuttoman paikallisen ketjun käynnistin: rekisteröi Jupyter-ytimen `analyst_env`, jos se puuttuu, ajaa notebookin ilman käyttöliittymää (ilman interaktiivista kysymyssolua) ja tallentaa sen tulosteet `.ipynb`-tiedostoon, sitten ajaa `generate_report.py`:n, `shamanic_pipeline.py`:n ja suomenkieliselle korpukselle Sanomattomien kirjan `scan`-komennon. Maksullisia vaiheita (LLM-rituaalit, ElevenLabs-äänet, kirjan `draft`/`fill`) se ei koskaan käynnistä.
- `generate_diagnostic.py` — riippumaton täyden **diagnostiikkaraportin** (`diagnostic_report.html`) luoja, joka rakennetaan suoraan notebookin CSV/JSON-vienneistä (ei `generate_report.py`:n ulostulosta). Navigoitava, ruudunlukijoille suunniteltu rakenne: sisällysluettelo `<nav>` ja osiot — kullakin oma otsikko ja listat — yleiskatsaukselle, aiheille kappaleineen, teeseille, nimetyille entiteeteille tyypeittäin ja tärkeimmille avainsanoille. Rakenteelliset tekstit seuraavat `ui_lang`-asetusta; korpuksen katkelmat saavat `<span lang="…">`, NER-tunnisteet `<span lang="en">`.
- `generate_md.py` — muuntaa `analysis_report.html`-tiedoston Markdown-muotoon (`gemini_notebook_report.md`) Gemini Notebookia (entinen NotebookLM) varten. Saavutettavuus-spanit puretaan, koska Gemini Notebook ei käytä niitä.
- `shamanic_pipeline.py` *(valinnainen)* — ei-LLM-jälkikäsittelijä, joka muuntaa notebookin CSV/JSON-viennit rituaalisiksi tekstiartefakteiksi (`oracle_script.txt`, `lore_fragments/`, `raw_roots_chant.txt`, `prophecies.txt` ja — kun valinnainen sentimenttianalyysi on käytössä — `emotional_undertow.txt`) ja on täysin lokalisoitu kaikille yhdeksälle tuetulle kielelle.
- `shamanic_ai.py` *(valinnainen, LLM-pohjainen)* — kutsuu LLM:ää (oletuksena OpenAI; OpenRouter tai mikä tahansa OpenAI-yhteensopiva osoite asetuksella `llm_provider`) neljän kerronnallisen äänen (`Katla`, `Vieno`, `Lumi`, `Sami`) tuottamiseen samojen vientien päälle. Kun valinnainen `sentiment.csv` on saatavilla, Vieno rakentaa laulunsa tekstin tunnekaaren varaan raakalauseiden sijaan. Vaatii valitun palveluntarjoajan avaimen tiedostossa `golden_key.env`.
- `shamanic_voice.py` *(valinnainen, vaatii ElevenLabsin)* — itsenäinen, kertasuoritteinen dispatcher, joka syntetisoi `shamanic_ai.py`:n tuottamat neljä kerronnallista artefaktia `.mp3`-äänitiedostoiksi ElevenLabs-API:n kautta, kirjaa kunkin onnistumisen/epäonnistumisen konsoliin ja päättyy (ei bottia, ei palvelinta). Tarvitsee `ELEVENLABS_API_KEY`:n tiedostossa `golden_key.env` sekä `voices`-määrityksen asetuksissa.
- `shamanic_locale.py` — molempien shamanististen skriptien lokalisointipaketti (mallit, otsikot ja Lumin fallback-merkkijonot kaikilla yhdeksällä kielellä).
- `ksiega_niedomowien.py` *(valinnainen, vain suomi, agentin avulla)* — Sanomattomien kirja (*Księga Niedomówień*): muuttaa `raw_roots_chant.txt`-tiedoston vähitellen kasvavaksi salakirjoitetuksi päiväkirjaksi, jonka aukkoja sokea malli ei pystynyt arvaamaan. Se on deterministinen apuri tiedoston `skills/ksiega-niedomowien/SKILL.md` skillille; konsolitulosteet noudattavat `ui_lang`-asetusta.
- `helsinki_reacts.py` *(valinnainen, LLM)* — satiirinen striimikäsikirjoitus: helsinkiläinen Valtteri reagoi suomalaisen chatin kanssa tallenteeseen (vientikansioon tai tekstitiedostoon). Järjestelmäkehote on koodin ulkopuolella (`helsinki_reacts.example.md`, oma kopio tiedostossa `helsinki_reacts.md`), ja striimin kieli seuraa asetusta `reacts_lang`, sitten `ui_lang`. Vaatii valitun palveluntarjoajan avaimen tiedostossa `golden_key.env`.

## Mitä putki tekee

1. Lataa tekstin tiedostosta (`.pdf`, `.txt`, `.docx`, `.md`, `.html` tai kuvista: `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`, `.webp`) tai URL-osoitteesta — poistaen toistuvat ylä- ja alatunnisteet, sivupalkit, "Related articles" -osiot ja vastaavan kalvotekstin. Skannatut PDF:t ja kuvasyötteet luetaan OCR:llä: jokainen `corpus_languages`-luettelon kieli lukee sivun omalla moottorillaan (Windows 10/11:n sisäänrakennettu OCR tai Tesseract kielelle, jota Windowsissa ei ole — nykyään islanti), RapidOCR lukee sivun vielä kerran varalla, ja kunkin kielen sanasto poimii kaikista lukutuloksista sanakirjamuodot.
2. Päättää jokaisen sanan kielen `corpus_languages`-luettelon kielten sanastoista (ks. **Jokaisen sanan kieli**): peruskieli ohjaa spaCy-putkea, ja vieraskieliset lainaukset ja nimet muuttuvat kielijaksoiksi.
3. Ajaa spaCyn kerran jokaiselle tekstin segmentille: peruskielen malli käsittelee perustekstin yhdessä lauseen sisäisten vieraskielisten jaksojen kanssa, ja jokaisen vieraskielisen lohkon käsittelee sen oman kielen malli, joka ladataan tarvittaessa `get_nlp()`:n kautta (kääritty `functools.lru_cache(maxsize=2)`:een, joten välimuistissa on enintään kaksi mallia). Uudelleensegmentointia tai toista monikielistä ajoa ei ole.
4. Tokenointi → stop-sanojen suodatus → lemmatisointi → POS-merkitseminen → NER, jokainen token oman kielensä mallilla analysoituna.
5. Vektoriedustukset: Bag of Words, TF-IDF + auto-kyselyhaku kosinilajittelulla.
6. Rakenne: lauseet → kappaleet (3–6 lausetta kukin) → teesit (paras lause per kappale). Jokainen lause kantaa kielensä ja lauseen sisäiset vieraskieliset jaksonsa; jokainen kappale vallitsevan kielensä.
7. Aiheen mallinnus KMeansilla spaCyn kappalevektoreiden päällä.
8. *(Valinnainen, oletuksena pois päältä)* Kappalekohtainen sentimenttipisteytys mallilla `cardiffnlp/twitter-xlm-roberta-base-sentiment`, kirjoitettuna tiedostoon `sentiment.csv`. Tulosta ei koskaan näytetä käyttäjälle — se on olemassa vain syötteenä shamanistiselle kerrokselle. Katso **Asetukset** (`enable_sentiment`).
9. CSV/JSON-vienti + tekstimuotoinen yhteenvetoraportti + saavutettava HTML- ja DOCX-vienti + globaali HTML-raportti (`analysis_report.html`).

## Tuetut kielet

| Koodi | Kieli      | spaCy-malli            | NER / vektorit |
|-------|------------|------------------------|----------------|
| pl    | puola      | `pl_core_news_lg`      | spaCy          |
| ru    | venäjä     | `ru_core_news_lg`      | spaCy          |
| en    | englanti   | `en_core_web_lg`       | spaCy          |
| it    | italia     | `it_core_news_lg`      | spaCy          |
| de    | saksa      | `de_core_news_lg`      | spaCy          |
| es    | espanja    | `es_core_news_lg`      | spaCy          |
| fr    | ranska     | `fr_core_news_lg`      | spaCy          |
| fi    | suomi      | `fi_core_news_lg`      | spaCy          |
| is    | islanti    | `spacy.blank("is")` + Hugging Face | `mideind/IceBERT` (vektorit), `grammatek/icelandic-ner-bert` (NER) |

Islannille ei ole täyttä spaCy-mallia, joten tyhjään putkeen on liitetty kaksi Hugging Face -mallia. Ensimmäinen lataus vaatii ~1,3 GB levytilaa ja internetyhteyden; seuraavat ajot käyttävät HF-välimuistia.

**Valinnainen suomen morfologian parannus (omorfi).** `fi_core_news_lg`:n tilastollinen lemmatisoija pärjää huonosti suomen agglutinatiiviselle morfologialle — se tuottaa säännöllisesti roskalemmoja kuten *kytköknen* tai *pisttää*. Kun puhtaasti pythonilainen `omorfi`-paketti on asennettu ja sen FST-automaatit ladattu (ks. Asennus, vaihe 5), notebook lisää komponentin `omorfi_lemmas`, joka korvaa lemmat ja UD-morfologiset piirteet sanakirja-analyyseilla aina, kun ne ovat yhtä mieltä spaCy-taggerin sanaluokan kanssa (`kytköksistä` → `kytkös`, `Euroopassa` → `Eurooppa`, `pistät` → `pistää`). Ilman pakettia tai automaatteja putki jatkaa hiljaa spaCyn vakiokäyttäytymisellä.

## Jokaisen sanan kieli

Tekstin kielet luetellaan avaimessa `corpus_languages` (`config.json`; vanhaa nimeä `ocr_languages` luetaan yhä). Näiden kielten sanastoista muistio päättää:

1. **Peruskieli** (`LANG`) — kieli, jonka sanasto tuntee suurimman osan korpuksen sanoista (osuudet tulostetaan). Se ohjaa pääasiallista spaCy-putkea.
2. **Jokaisen sanan kieli** (`odcinki_jezykowe.py`). Sana, jota perussanasto ei tunne mutta jonkin toisen luetellun kielen sanasto tuntee, kuuluu tuohon kieleen; usean kielen tuntema sana menee pienimpään aakkostoon, johon kaikki sen kirjaimet mahtuvat — näin englanninkielistä sanaa ei vie puolan sanasto, joka tuntee paljon englannin muotoja, ja `Łódź` pysyy puolana. Kirjoitusjärjestelmä on tosiasia: kyrillinen sana latinalaisessa tekstissä saa kyrillisen kielen, vaikka sellaista ei olisi lueteltu.
3. **Vieraskieliset jaksot** — vähintään kaksi peräkkäistä saman vieraan kielen sanaa lauseen sisällä tai yksi sana, jossa on peruskielen aakkostosta puuttuvia kirjaimia. Kokonaiset lauseet kattava jakso on **lohko**, ja sen käsittelee oma spaCy-malli (lauseet, NER, lemmat). Peruskielisen lauseen sisällä oleva jakso on **lauseen sisäinen jakso**: lause jää perusmallille, ja jakso saa lemmansa ja POS-tagiensa oman kielensä mallilta.

Tulos näkyy viennissä: `<span lang="…">` tiedostossa `accessible_text.html` ja erillinen `Run` `<w:lang>`-ominaisuudella tiedostossa `accessible_text.docx` jokaiselle vieraskieliselle lauseelle ja jokaiselle lauseen sisäiselle jaksolle, joten ruudunlukija vaihtaa ääntä täsmälleen lainauksen tai nimen kohdalla eikä koko lauseen ajaksi. Kaikki jaksot luetellaan myös tiedostossa `language_spans.csv`, ja `sentences.csv`:ssä on sarake `lang`.

Sanastot: spaCyn vektorit (äärellinen sanamuotojen luettelo) puolalle, englannille, venäjälle, italialle, saksalle, espanjalle ja ranskalle; `omorfi` suomelle; BÍN (`islenska`) islannille — samat sanastot, joita OCR-äänestys käyttää. Kun `corpus_languages` sisältää vain yhden kielen, sanastoja ei ladata ja merkitään vain toisella kirjoitusjärjestelmällä kirjoitetut sanat. Puuttuva sanasto pysäyttää ajon viestiin, joka kertoo korjauksen.

**Mitkä kielet luetella.** Mitattu 20 suomenkielisellä litteroinnilla (55 000 sanaa), joissa mainitaan paljon puolalaisia nimiä: asetuksella `["fi", "en"]` muistio löytää 34 englanninkielistä jaksoa (termejä ja lainauksia); asetuksella `["fi", "pl", "en"]` lisäksi 57 puolankielistä jaksoa — puolalaisia nimiä ja muutaman puolankielisen ilmauksen, jotka nyt lukee puolalainen ääni suomalaisen sijaan — eikä yksikään englanninkielinen sana mene puolalle. Siksi:

- luettele jokainen kieli, jolla tekstissä on **lainauksia**;
- kun teksti on kirjoitettu yhdellä kielellä mutta mainitsee toisen kielen **nimiä** (puolalaisia nimiä suomenkielisessä tekstissä), lisää nimien kieli: perusmuotoiset nimet ja nimet, joissa on peruskielen aakkostosta puuttuvia kirjaimia (`ł`, `ś`), lukee silloin niiden oman kielen ääni. Pelkillä peruskielen kirjaimilla taivutettu nimi (`Kowalskille`) jää joka tapauksessa peruskieleen;
- älä luettele kieltä, jota tekstissä ei ole: se tuo vain vääriä ehdokkaita.

**Miksi ei tilastollista tunnistinta.** ATA 1.x:ään asti `lingua-language-detector` luokitteli kokonaisia lauseita. Samoissa litteroinneissa se merkitsi 127 lausetta vieraskielisiksi, lähes kaikki väärin; sen hillitsemiseen tarvitut suojaheuristiikat jättivät jäljelle 2 lausetta eikä yhtään englanninkielistä lainausta. ATA 2.0 poisti sen. Kokonaisraportti (`generate_report.py`) merkitsee venäjänkielisen kerronnan vieraat sanat samoilla sanastoilla (`corpus_languages`-kielet sekä englanti).

## Vaatimukset

- Python 3.12 tai uudempi (riippuvuudet on testattu Pythonilla 3.14).
- ~1,5 GB vapaata levytilaa spaCyn `_lg`-malleja varten (yksi per kieli). Lisää ~1,3 GB, jos otat käyttöön islanninkielisen tuen (Hugging Face `transformers` + `torch` + IceBERT + icelandic-ner-bert). Islannin NER lukee koko dokumentin limittäisissä ikkunoissa: CPU:lla noin 4 000 merkkiä sekunnissa, joten kirja (1 Mt islanninkielistä tekstiä) vie muutaman minuutin.
- OCR-tuki (valinnainen): `winrt-*`-paketit (alle 1 MB) sekä jokaiselle `corpus_languages`-kielelle Windowsin kielipaketti, jossa on optinen tekstintunnistus (Asetukset > Aika ja kieli > Kieli ja alue); `rapidocr` ja `onnxruntime` (mallit, noin 40 MB, latautuvat ensimmäisellä OCR-kutsulla); kielelle, jolle Windowsissa ei ole moottoria (nykyään islanti), `tesserocr` ja kielen tessdata_best-malli repositorion `tessdata`-kansiossa (islanti: https://github.com/tesseract-ocr/tessdata_best/raw/main/isl.traineddata, noin 9,5 MB) sekä `islenska`-sanasto (~62 MB). OCR ei enää tarvitse `torch`:ia. Puuttuva moottori tai sanasto pysäyttää ajon viestillä, joka kertoo korjauksen. Islannin sanasto: The Database of Icelandic Morphology (BÍN), The Árni Magnússon Institute for Icelandic Studies, tekijä ja toimittaja Kristín Bjarnadóttir, CC BY-SA 4.0.
- Lisää ~130 MB, jos otat käyttöön suomen morfologian parannuksen (`omorfi`:n FST-automaatit, jotka ladataan komennolla `omorfi-download`).
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
conda create -n accessible-text-analyst python=3.14
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
# !python -m spacy download de_core_news_lg
# !python -m spacy download es_core_news_lg
# !python -m spacy download fr_core_news_lg
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
python -m spacy download de_core_news_lg
python -m spacy download es_core_news_lg
python -m spacy download fr_core_news_lg

# 3. (Valinnainen) Islanninkielinen tuki — poista kommenttimerkit `transformers`:in ja
# `torch`:in edestä tiedostossa requirements.txt ja aja uudelleen `pip install -r requirements.txt`.
# IceBERT ja icelandic-ner-bert ladataan sitten Hugging Facelta ensimmäisellä ajolla.

# 4. (Valinnainen) Sentimenttianalyysi — poista kommenttimerkit `transformers`:in, `torch`:in,
# `sentencepiece`:n, `protobuf`:in ja `tiktoken`:in edestä tiedostossa requirements.txt, aja
# `pip install` uudelleen ja aseta "enable_sentiment": true tiedostossa config.json. Malli
# (~1,1 GB) ladataan Hugging Facelta ensimmäisellä ajolla ja tallennetaan välimuistiin sen jälkeen.
# Kaikki viisi pakettia tarvitaan yhdessä XLM-RoBERTa-tokenisaattorin rakentamiseen.

# 5. (Valinnainen) Suomen morfologian parannus — poista kommenttimerkki `omorfi`:n
# edestä tiedostossa requirements.txt, aja asennus uudelleen ja lataa sitten
# FST-automaatit (~130 MB *.hfst-tiedostoja, jotka puretaan repon juureen;
# ne ovat .gitignore:ssa). Aja repon juuresta:
omorfi-download

# 6. (Valinnainen) Vertaa asennettuja versioita requirements.txt-tiedoston
# rajoihin ja PyPI:hin. Komento vain varoittaa, se ei estä mitään:
python audyt_zaleznosci.py
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

| Avain              | Tyyppi          | Tarkoitus |
|--------------------|-----------------|-----------|
| `source_file`      | string          | Polku tiedostoon (`.pdf`, `.txt`, `.docx`, `.md`, `.html` tai kuva) **tai** URL (`http://`, `https://`). Tyhjä merkkijono tai puuttuva tiedosto → sisäänrakennettu esimerkkikorpus. |
| `custom_patterns`  | string[]        | Valinnainen lista säännöllisistä lausekkeista, jotka poistetaan raakatekstistä (juoksevat otsikot, alatunnisteet, toistuvat kalvotekstit). Esimerkki: `["Editorial: .*", "Copyright \\d{4}"]`. |
| `remove_noise`     | boolean         | Vaihtaa `generate_report.py`:n lukijaystävällisen tilan (`true`, piilottaa Hugging Face/torch -latauspalkit ja lemmatisointi/POS-taulukot) ja täyden diagnostisen tilan (`false`) välillä. |
| `corpus_languages` | string[]        | TEKSTIN kielet (kielipakettien koodit: `de`, `en`, `es`, `fi`, `fr`, `is`, `it`, `pl`, `ru`); vanhaa nimeä `ocr_languages` luetaan yhä. Niiden sanastot valitsevat peruskielen ja jokaisen sanan kielen (ks. **Jokaisen sanan kieli**), ja skannatuissa PDF:issä ja kuvissa kukin niistä lukee sivun omalla OCR-moottorillaan. Luettele vain kielet, joita tekstissä todella esiintyy: ylimääräinen kieli hidastaa OCR:ää ja tuo vääriä ehdokkaita. Latinalaisia ja kyrillisiä kirjaimia voi sekoittaa (`["fi", "ru"]`). |
| `enable_sentiment` | boolean         | Ottaa käyttöön valinnaisen kappalekohtaisen sentimenttianalyysin (oletuksena `false`). Vaatii kommentoidut sentimenttiriippuvuudet (katso asennusvaihe 4). Kirjoittaa `sentiment.csv`-tiedoston; tulosta ei koskaan näytetä käyttäjälle, se vain syöttää shamanistista kerrosta (`emotional_undertow.txt`-rituaali ja Vienon laulu). Minkä tahansa latausvirheen sattuessa se ohitetaan hiljaisesti — ei fallbackia. |
| `ui_lang`          | string          | Käyttöliittymän kieli konsolituloste ja luodun raportin `<html lang>` -attribuutti (`pl` / `en` / `ru` / `fi` / `is` / `it` / `de` / `es` / `fr`). Tyhjä merkkijono tai tuntematon koodi → fallback `en`. Riippumaton analysoidun korpuksen kielestä, jonka `corpus_languages`-kielten sanastot päättävät. |
| `lumi_katla_lines` | integer tai null | Valinnainen koristerajoitus `shamanic_ai.py`:n Lumin loppuraportille: kuinka monta ei-tyhjää riviä Katlan monologista Lumi näkee. `null` tai puuttuva avain = koko sisältö; integer N > 0 = ensimmäiset N riviä. |
| `lumi_vieno_lines` | integer tai null | Sama kuin `lumi_katla_lines`, mutta Vienon kaikulaululle. |
| `voices`           | object          | Yhdistää jokaisen shamanistisen äänen (`katla` / `vieno` / `lumi` / `sami`) ElevenLabs-äänen tunnisteeseen; käyttää `shamanic_voice.py`. Ääni, jonka tunniste on tyhjä tai puuttuu, ohitetaan. Tarvitaan vain, jos ajat äänidispatcherin. |
| `llm_provider` | string | LLM-palveluntarjoaja skriptille `shamanic_ai.py` ja Kirjalle: `openai` (oletus), `openrouter` tai `openai_compat`. Jokainen palveluntarjoaja lukee tiedostosta `golden_key.env` vain oman avaimensa — ks. *LLM-palveluntarjoajat ja avaimet* alla. |
| `llm_model` | string | Malli tälle palveluntarjoajalle. Tyhjä = palveluntarjoajan oletus (`gpt-6.1-sol` / `openai/gpt-6.1-sol`); pakollinen `openai_compat`-tilassa. |
| `llm_base_url` | string | Osoite, jonka lukee **vain** `openai_compat` (esim. `http://localhost:1234/v1`). `openai` ja `openrouter` ohittavat sen, koska niiden osoitteet ovat kiinteät. |
| `kirja_llm_provider` | string | Valinnainen palveluntarjoajan ohitus Kirjalle (`ksiega_niedomowien.py draft` / `fill`). Tyhjä = `llm_provider`. |
| `kirja_drafter_model` | string | Malli komennolle `draft` (Kirjan luonnosten kirjoittaja API:n kautta). Tyhjä = palveluntarjoajan oletus tai `llm_model`, kun Kirja käyttää yleistä palveluntarjoajaa. |
| `kirja_filler_model` | string | Malli komennolle `fill` (Kirjan sokea aukkojen täyttäjä). Sama varavaihtoehto kuin `kirja_drafter_model`. |
| `reacts_llm_provider` | string | Valinnainen palveluntarjoajan ohitus `helsinki_reacts.py`:lle. Tyhjä = `llm_provider`. |
| `reacts_model` | string | Malli `helsinki_reacts.py`:lle. Tyhjä = palveluntarjoajan oletus tai `llm_model`, kun Helsinki Reacts käyttää yleistä palveluntarjoajaa. |
| `reacts_lang` | string | `helsinki_reacts.py`:n striimin kieli (`ui_lang`-koodi). Tyhjä = `ui_lang`. `fi` = striimi suomeksi; mikä tahansa muu = sen käännös suomenkielisin välihuudahduksin. |

> **LLM-palveluntarjoajat ja avaimet.** Avain on sidottu yhteen palvelimeen, eikä sitä koskaan lähetetä muualle: `openai` → `OPENAI_API_KEY` → `api.openai.com`; `openrouter` → `OPENROUTER_API_KEY` → `openrouter.ai`; `openai_compat` → `LLM_COMPAT_API_KEY` → `llm_base_url`. Palveluntarjoaja valitaan erikseen eikä sitä koskaan päätellä osoitteesta, joten yhden skriptin ohjaaminen toiseen palveluun ei voi vuotaa ensimmäisen palvelun avainta eikä rikkoa toista skriptiä. Ennen v1.7.0:aa käytetty avain `kirja_filler_base_url` (se lähetti `OPENAI_API_KEY`-avaimen mihin tahansa osoitteeseen) hylätään siirto-ohjeen kanssa. OpenRouterissa mallitunnuksissa on toimittajan etuliite (`openai/gpt-4o`, `anthropic/claude-sonnet-5.5`), ja tilin yksityisyysasetuksilla voi sulkea pois toimittajat, jotka saattavat kouluttaa malleja kehotteillasi.

> **Sentimenttianalyysi — CPU-kuorma.** Kun `enable_sentiment: true`, kappalekohtainen ajo on laskennallisesti raskas CPU:lla — suunnilleen verrattavissa paikallisen Whisper-puheentunnistuksen ajamiseen CPU:lla. Vanhemmilla tai lämmöllisesti rajoitetuilla koneilla tämä jatkuva kuorma voi todella rasittaa prosessoria; ota se käyttöön harkiten, mieluiten koneella jossa on GPU tai pelivaraa pitkäkestoiseen täyskuormatyöhön.

> **`ui_lang` — lokalisoinnin laajuus.** Itsenäisten skriptien (`generate_report.py`, `generate_md.py`, `generate_diagnostic.py`, `shamanic_pipeline.py`, `shamanic_ai.py`, `ksiega_niedomowien.py`, `helsinki_reacts.py`) konsolituloste lokalisoidaan `ui_lang`-asetuksen kautta. Itse **notebookin stdout ei ole** lokalisoitu — se on kovakoodattu venäjäksi (vain teesien tiedostonimi seuraa tunnistettua korpuksen kieltä). Lukutila-artefakti `analysis_report.html` säilyttää notebookin venäjänkielisen kerronnan (sen juuri on `<html lang="ru">`); täysin `ui_lang`-lokalisoitu, käyttäjälle näkyvä artefakti on **`diagnostic_report.html`**, jonka tuottaa `generate_diagnostic.py`. Käännökset `fi` / `is` / `it` / `de` / `es` / `fr` ovat luonnoksia eivätkä tarkistettuja — ilmoita epätarkkuuksista GitHubissa.

> **Windows-polut ja regexit — tärkeää.** Asetussisältö on JSON, eikä JSONissa ole raw-string-syntaksia. Yksittäinen kenoviiva escapeaa seuraavan merkin (`\U`, `\d`, `\n` ovat erikoismerkkejä), joten Windows-polku kirjoitettuna `"C:\Users\marek\doc.pdf"` aiheuttaa JSON-jäsennysvirheen. Kaksi oikeaa tapaa kirjoittaa se:
>
> - **Etukenoviivat** (yksinkertaisin, toimii myös Windowsissa): `"C:/Users/marek/doc.pdf"`.
> - **Tuplakenoviivat**: `"C:\\Users\\marek\\doc.pdf"`.
>
> Sama sääntö koskee jokaista säännöllistä lauseketta avaimessa `custom_patterns`: kirjoita `"\\d{4}"`, älä `"\d{4}"`; kirjoita `"Copyright \\d{4}"`, älä `"Copyright \d{4}"`. JSONissa ei ole `r"…"`-syntaksia raw-merkkijonoille.

## Suoritus

Alla olevat skriptit on tarkoitettu ajettaviksi **järjestyksessä**: jokainen käyttää edellisen vaiheen tuottamia artefakteja.

### Oikotie: koko paikallinen ketju (`run_all.py`)

```bash
# notebook -> generate_report.py -> shamanic_pipeline.py -> kirjan scan (vain suomi)
python run_all.py
# käytä notebookiin jo tallennettuja tulosteita
python run_all.py --skip-notebook
# kirjastojen varoitusten täysi diagnostiikka configista riippumatta
python run_all.py --warnings-as-errors
```

Alla olevat vaiheet 1, 2 ja 4 sekä suomenkieliselle korpukselle Sanomattomien kirjan `scan` yhdellä komennolla. Aja se repon `.venv`-ympäristön Pythonilla: jos ydin `analyst_env` puuttuu, se rekisteröidään tälle tulkille. Ketju pysähtyy ensimmäiseen epäonnistuvaan vaiheeseen; paluukoodi 3 tarkoittaa, että raportin lähdetarkistus hylkäsi ajon (ks. vaihe 2). Notebook vaimentaa kirjastojen varoitukset tarkoituksella, jotta ne eivät päädy analyysiraporttiin. `--warnings-as-errors` on erillinen täyden diagnostiikan tila: se ohittaa `config.json`-tiedoston ja ajaa notebookin kopion synteettisellä korpuksella jokaisen komponentin läpi (PDF fontin korjauksella ja OCR:ää varten skannatulla sivulla, kaikki syötemuodot ja URL paikalliselta palvelimelta, sävyanalyysi, islanti, omorfi). Se kirjaa jokaisen varoituksen, myös poikkeuksia sieppaavassa koodissa syntyneet, ja tulostaa ne kaikki solun otsikon alle kirjaston omin sanoin ja syntypaikan kanssa. Tunnetut, harmittomat varoitukset (`diagnostyka.ZNANE_OSTRZEZENIA`) saavat oman rivinsä eivätkä vaikuta tulokseen. Tila vaatii kaikki `requirements.txt`-tiedoston valinnaiset riippuvuudet ja mallin `fi_core_news_lg`, ja komponentti, joka ei lataudu, pysäyttää sen ilmoituksella. Notebook ja `export_results/` jäävät koskematta, eikä raporttia tai myöhempiä vaiheita ajeta; paluukoodi 4 = uusia varoituksia, 0 = ei yhtään. Kirjaaja kattaa notebookin prosessin `warnings`-moduulin: `logging`-kanavan kautta lähetetyt viestit (esim. `transformers`) ja lapsiprosessien varoitukset jäävät sen ulkopuolelle. Kun kirjasto korvaa kirjaajan (esim. `logging.captureWarnings`), tila päättyy koodiin 1 väärän ”puhdas”-tuloksen sijaan; samoin Ctrl+C, kun kerätyt varoitukset on ensin tulostettu. Aja se kirjastojen päivittämisen jälkeen.

### 1. Notebook (pakollinen)

```bash
jupyter notebook accessible_text_analyst.ipynb
# (Cell → Run All)
# Ilman käyttöliittymää (CI): solut 0-39 nbclientillä, ilman interaktiivista cell_qa_rag-solua
python -c "import nbformat as f; from nbclient import NotebookClient as C; nb=f.read('accessible_text_analyst.ipynb',4); c=C(nb,timeout=None); c.create_kernel_manager(); c.start_new_kernel(); c.start_new_kernel_client(); [c.execute_cell(x,i) for i,x in enumerate(nb.cells[:40])]; f.write(nb,'accessible_text_analyst.ipynb'); c.km.shutdown_kernel(now=True)"
```

Tämä on peräkkäinen putki, jolla on jaettu globaali tila. **Älä järjestä soluja uudelleen äläkä aja niitä järjestyksen ulkopuolella.** Notebook kirjoittaa `export_results/<project>/sentences.csv`, `paragraphs.csv`, `theses.csv`, `keywords_tfidf.csv`, `paragraphs_with_topics.csv`, `topic_keywords.json`, `entities.csv`, `accessible_text.html`, `accessible_text.docx` ja `theses.txt`.

### 2. HTML-raportit (suositeltu)

```bash
python generate_report.py
# → export_results/<project>/analysis_report.html
```

`generate_report.py` lukee solujen ulostulot suoraan `.ipynb`-tiedostosta, joten HTML-raportti on luotava **juuri suoritetusta** notebookista. `requirements.txt` listaa `nbstripout`:n — jos se on aktivoitu paikallisessa git-konfiguraatiossa, notebookin ulostulot riisutaan commitilla. Luo raportti _ennen_ commitia tai poista nbstripout käytöstä työnkulustasi.

**Lähteen tarkistus.** Ennen kuin `generate_report.py` kirjoittaa mitään, se tarkistaa, että notebookin tulosteet kuuluvat asetusten `source_file`-lähteeseen, ja muuten kieltäytyy (paluukoodi 3, mitään ei kirjoiteta). Kolme tarkistusta: notebookin tulostaman lähdepolun ja vientikansion on vastattava asetuksia, ja tallennetun ajon on täytynyt päästä vientisolun loppuun; `paragraphs.csv` ja `sentences.csv` eivät saa olla `.ipynb`-tiedostoa uudempia (muuten viimeisimmän ajon tulosteita ei tallennettu — tyypillistä, kun notebook ajetaan VS Codessa tallentamatta); ja notebookin tulostamien sivujen alkujen on esiinnyttävä lähdetiedostossa (verrataan pelkkien kirjainten jonona, joten yhdistetyt tavutukset, poistetut sivunumerot ja ylä- ja alatunnisteet eivät haittaa). Kun sisältöä ei voi verrata — OCR:llä luetut skannaukset, kuvat, URL-osoitteet, vääristynyt PDF-tekstikerros — ratkaisevat kaksi ensimmäistä tarkistusta, ja konsoli kertoo sen. Raportti kirjaa myös, oliko omorfi mukana ajossa (`<meta name="ata-omorfi">`); Sanomattomien kirja lukee sen.

Jäsenneltyä, täyttä **diagnostista** näkymää varten, joka rakennetaan suoraan CSV/JSON-vienneistä:

```bash
python generate_diagnostic.py
# → export_results/<project>/diagnostic_report.html
```

`generate_diagnostic.py` lukee vain viedyt CSV/JSON-tiedostot, joten — toisin kuin `generate_report.py` — se ei tarvitse juuri suoritettua notebookia, vaan ainoastaan notebookin kirjoittamat viennit. Tuloksena on navigoitava asiakirja (sisällysluettelo, otsikot, listat), joka kattaa aiheet, teesit, entiteetit tyypeittäin ja tärkeimmät avainsanat.

### 3. Gemini Notebook -ystävällinen Markdown (valinnainen)

```bash
python generate_md.py
# → export_results/<project>/gemini_notebook_report.md
```

Tämä muuntaa HTML-raportin Markdown-tiedostoksi, jossa saavutettavuus-spanit on purettu (Gemini Notebook — entinen NotebookLM — ei käytä `<span lang="…">`). Aja tämä vain, jos haluat syöttää raportin Gemini Notebookiin.

### 4. Shamanistinen ei-LLM-jälkikäsittelijä (valinnainen)

```bash
python shamanic_pipeline.py
# → export_results/<project>/audio_scripts/oracle_script.txt
#                                          /raw_roots_chant.txt
#                                          /prophecies.txt
#                                          /lore_fragments/intercepted_log_T*_P*.txt
#                                          /emotional_undertow.txt   # vain jos sentiment.csv on olemassa
```

Luo rituaalisia tekstiartefakteja suoraan notebookin CSV/JSON-vientien pohjalta — ei LLM-kutsua, ei verkkoa. Kaikki merkkijonot tulevat tiedostosta `shamanic_locale.py` ja on lokalisoitu kaikille yhdeksälle tuetulle kielelle. Kun valinnainen `sentiment.csv` on saatavilla, se tuottaa lisäksi `emotional_undertow.txt`-tiedoston — kappalekohtaisen "tunnevuoroveden" sekä tasapainoyhteenvedon; ilman sitä tämä yksi rituaali yksinkertaisesti ohitetaan.

### 5. Shamanistinen LLM-jälkikäsittelijä (valinnainen, vaatii LLM-API-avaimen)

```bash
python shamanic_ai.py
# → export_results/<project>/audio_scripts/katla_entity_monologue.txt
#                                          /vieno_echoes_chant.txt
#                                          /lumi_final_report.txt
#                                          /sami_energetic_spark.txt
```

Vaatii valitun palveluntarjoajan avaimen (`llm_provider`, oletus `openai`). Luo `golden_key.env` projektin juureen tarvitsemallasi avaimella:

```
OPENAI_API_KEY=sk-...          # llm_provider: openai (default)
OPENROUTER_API_KEY=sk-or-...   # llm_provider: openrouter
LLM_COMPAT_API_KEY=...         # llm_provider: openai_compat (llm_base_url)
```

`golden_key.env` täsmää kuvioon `*.env` `.gitignore`:ssa, joten sitä ei commitata. Neljä ääntä ajetaan järjestyksessä:

1. **Katla** muuttaa entiteettilistan (`entities.csv`) jäätyneiden pohjoisten henkien monologiksi.
2. **Vieno** kanttaa avainsana-/aiheluettelon yli. Oletuksena hän kutoo mukaan viisi raakalausetta korpuksesta toisen ulottuvuuden kaikuina; kun valinnainen `sentiment.csv` on saatavilla, hän sen sijaan lukee tekstin tunnekaaren (kappalekohtaiset tunnelmat, alasnäytteistettyinä mahtumaan mallin token-rajaan pitkillä korpuksilla) ja antaa sen muovata laulun dynamiikkaa.
3. **Lumi** lukee `prophecies.txt`:n (pakollinen) sekä Katlan monologin ja Vienon laulun (valinnainen koriste) ja tuottaa loppuraportin. Lokalisoidut fallback-merkkijonot kattavat tapauksen, jossa Katla tai Vieno puuttuvat.
4. **Sami** lukee Lumin raportin ja toimittaa korkeaenergisen synteesin toivon kipinällä tai toimintakutsulla.

### 6. Shamanistinen äänidispatcher (valinnainen, vaatii ElevenLabsin)

```bash
python shamanic_voice.py
# → export_results/<project>/audio_scripts/katla_entity_monologue.mp3
#                                          /vieno_echoes_chant.mp3
#                                          /lumi_final_report.mp3
#                                          /sami_energetic_spark.mp3
```

Itsenäinen, kertasuoritteinen skripti, joka lukee `shamanic_ai.py`:n tuottamat neljä kerronnallista artefaktia ja syntetisoi kunkin `.mp3`-tiedostoksi ElevenLabsin `eleven_multilingual_v2`-mallilla (joka tunnistaa puhutun kielen automaattisesti, joten kieliparametria ei välitetä). Se kirjaa kunkin onnistumisen tai epäonnistumisen konsoliin ja päättyy — ei bottia, ei palvelinta, ei interaktiivista istuntoa. Se tarvitsee kaksi asiaa:

- `ELEVENLABS_API_KEY`:n tiedostossa `golden_key.env` (sama tiedosto, joka sisältää LLM-avaimet).
- `voices`-määrityksen tiedostossa `config.json` / `config.ini`, joka liittää ElevenLabs-äänen tunnisteen kuhunkin äänistä `katla`, `vieno`, `lumi`, `sami`. Ääni, jonka tunniste on tyhjä tai jonka artefakti puuttuu, ohitetaan (aja `shamanic_ai.py` ensin); yhden äänen epäonnistuminen ei keskeytä muita.

> **Yksityisyys ja kustannukset.** Kuten `shamanic_ai.py` OpenAI:n kanssa, tämä skripti lähettää artefaktitekstin kolmannen osapuolen palveluun (ElevenLabs) syntetisoitavaksi, ja ElevenLabs on **maksullinen** API. Sisältö poistuu koneeltasi — älä aja sitä materiaalilla, jota et voi jakaa ulkopuolelle.

### 7. Sanomattomien kirja (valinnainen, vain suomi, agentin avulla)

```bash
python ksiega_niedomowien.py scan              # mitkä export_results/-kansiot kelpaavat
python ksiega_niedomowien.py scan --blocks     # lisäksi tehdyt / avoimet / jäljellä olevat lohkot (hidas; --folder-valitsimella automaattisesti)
python ksiega_niedomowien.py status            # edistyminen kansioittain: merkinnät, ilmeiset lohkot, avoimet paketit
python ksiega_niedomowien.py tidy              # saman lohkon uudemmalla merkinnällä korvatut merkinnät (esikatselu; --apply siivoaa)
python ksiega_niedomowien.py prepare --folder <name> --limit 3
#   → export_results/_kirja_tyotila/<id>/packet.json
python ksiega_niedomowien.py draft <id>        # valinnainen: luonnos API:n kautta + seal, enintään 2 uusintaa
python ksiega_niedomowien.py seal <id>         # tarkistaa draft.json-tiedoston, kirjoittaa blind.json-tiedoston
python ksiega_niedomowien.py fill <id>         # valinnainen: sokeat arvaukset API:n kautta, sitten judge
python ksiega_niedomowien.py judge <id>        # → export_results/Sanomattomien_kirja.md
# <id> = prepare-komennon tulostama paketin tunnus, kansion nimen alku tai polku pakettikansioon
```

Peli, joka rakentuu `raw_roots_chant.txt`-tiedoston päälle. Jokaisesta 3–6 peräkkäisen juuren lohkosta LLM kirjoittaa sumuisen suomenkielisen päiväkirjamerkinnän, jossa on aukkoja; aukkojen vastaukset ovat sanatarkkoja katkelmia lähdetekstistä, ja niiden on löydyttävä **sekä** `accessible_text.html`- että `accessible_text.docx`-tiedostosta eli totuuden lähteen kummastakin versiosta. Sen jälkeen erillinen, sokea malli yrittää täyttää aukot pelkän merkinnän perusteella; jokainen arvattu aukko katsotaan ilmeiseksi, ja sen katkelma poistetaan. Jäljelle jäävä — juuret lukeva KATLA (varoitusjärjestelmä) ja sanomattomat aukot sisältävä VIENO (shamaanikertoja) — lisätään tiedostoon `export_results/Sanomattomien_kirja.md`. Vastausavain menee tiedostoon `Sanomattomien_kirja.avain.json` ja tila tiedostoon `Sanomattomien_kirja.tila.json`; uudelleenajo ei koskaan monista merkintöjä.

Skripti on deterministinen puolikas (suodattimet, lohkot, totuuden lähde, tarkistus, arviointi, Kirja). Luovan puolikkaan — `draft.json`-tiedoston kirjoittamisen — tekee joko agentti ohjeen `skills/ksiega-niedomowien/SKILL.md` mukaan tai API:n malli komennolla `draft`.

**Syötteen suodattimet.** Kelpaavat vain ne `export_results/`-alikansiot, joilla on suomenkielinen nimi, `<html lang="fi">`, suomenkielinen loitsu eikä kielioppivuotoa; kaikki muu hylätään syyn kera. Rivi `roots.header` poistetaan, jos se on mukana. *Kielioppivuodon* tarkistus havaitsee korpukset, jotka on käsitelty ennen omorfin käyttöönottoa (v1.5.0): se laskee koko `keywords_tfidf.csv`-tiedostosta lemmatisoinnista selvinneet taivutusmuodot sekä spaCyn roskalemmat ja hylkää kansion, jos niitä on yli 1,0 sataa termiä kohden. Vaatii omorfin (asennuksen vaihe 5). Kun kansiossa on ajantasainen `analysis_report.html`, kielioppivuodon vuoksi annettu hylkäys kertoo, mitä raportti tietää: omorfi oli mukana ajossa (silloin korjattavaa voi olla itse moottorissa — notebookin suomen lemmojen korjauksessa; ilmoita esimerkit), omorfi puuttui (asenna se ja aja notebook uudelleen) tai ajossa ei ollut omorfi-vaihetta lainkaan. Ilman ajantasaista raporttia se kertoo, ettei tätä tiedetä.

**Miksi vain suomi.** Peli elää siitä, mitä lemmatisointi jättää sanomatta, joten se on mielekäs vain siellä, missä sanan palauttaminen perusmuotoon vie siltä todellista merkitystä. Suomi on agglutinoiva kieli: sen, minkä puola tai venäjä ilmaisevat osin erillisillä prepositioilla ja englanti enimmäkseen sanajärjestyksellä ja funktiosanoilla, suomi pakkaa itse sanaan — viisitoista sijamuotoa (`talossa`, `talosta`, `taloon`, `talolle`, `talotta`), possessiivisuffiksit (`taloni`, `talonsa`), liitepartikkelit (`-ko` kysymys, `-kin` ”myös”, `-han` korostus) ja verbimuodot, jotka kantavat yhtä aikaa persoonaa, aikamuotoa, tapaluokkaa ja passiivia (`tehtäisiinkö`). Loitsu supistaa kaiken tämän muotoihin `TALO` ja `TEHDÄ`: kuka, missä, mistä, mihin, kenen ja onko katoavat — juuri ne aukot, jotka kuulijan on täytettävä. Puolassa ja venäjässä perusmuoto menettää taivutuspäätteen, mutta suuri osa suhteesta on erillisessä sanassa (prepositiossa), joten perusmuoto ei koskaan kantanut sitä yksin; englanti menettää vain vähän luvun ja aikamuodon lisäksi. Islanti (neljä sijaa, joita prepositiot pitkälti hallitsevat) ja italia (prepositiot ja artikkelit, niukka nominitaivutus) ovat lähempänä vastaavasti puolan ja venäjän sekä englannin mallia. Teknisesti työkalu tarvitsee myös sanakirjapohjaisen analysaattorin todistaakseen, että loitsu on kieliopiton, ja yhdistääkseen juuret takaisin taivutettuun tekstiin; tässä putkessa sellainen on vain suomelle (omorfi), ja kynnysarvot on kalibroitu oikeilla suomenkielisillä korpuksilla.

**Luonnosten kirjoittaja API:n kautta (`draft`).** Madaltaa kynnystä: agenttia ei tarvita. Skripti lähettää paketin (chant, juuret ja lähdelauseet kohdasta `truth.sentences`) määritetylle palveluntarjoajalle, kirjoittaa `draft.json`-tiedoston ja sinetöi sen; jos `seal` hylkää luonnoksen, malli saa sen takaisin tarkistimen konkreettisten huomautusten kanssa, enintään 2 uusintaa (3 yritystä). Paluukoodit ovat samat kuin `seal`-komennolla (0 sinetöity, 4 yhä hylätty — korjaa viimeisin `draft.json` käsin tai skillillä). Olemassa olevaa `draft.json`-tiedostoa ei koskaan korvata ilman `--force`-valitsinta. Skill on edelleen vahvempi tila: rajattomasti uusintoja, ja agentti lukee huomautukset sitä mukaa. Yhtä sääntöä ei voi tarkistaa deterministisesti kummassakaan tilassa: *älä liitä todellisiin henkilöihin tosiasioita tai syytöksiä, joita lähdelauseissa ei ole*. Sekä luonnoksen kirjoittajan kehote että skill mainitsevat sen, mutta mikään ei tarkista sitä — lue todellisia henkilöitä koskevat merkinnät ennen kuin jaat ne.

**Sokea täyttäjä (`fill`).** Lähettää määritetylle palveluntarjoajalle vain `blind.json`-tiedoston — ei koskaan vastauksia eikä lähdettä —, tallentaa `guesses.json`-tiedoston ja ajaa heti `judge`-komennon. Palveluntarjoaja: `kirja_llm_provider` (tyhjä = `llm_provider`); malli: `kirja_filler_model`; `--provider` / `--model` ohittavat molemmat. Erillinen `judge` on tarkoitettu sokean aliagentin arvauksille. Sekä `draft` että `fill` pyytävät ensin JSON-skeemaa (structured outputs); jos osoite hylkää sen, ne siirtyvät tavalliseen JSON-tilaan ja sitten pelkkään kehotteeseen. `fill` yrittää kahdesti uudelleen, jos vastaus on käyttökelvoton tai siitä puuttuu aukko. Jokainen käyttökelvoton vastaus tallennetaan pakettikansioon (`draft_reply_N.txt` / `fill_reply_N.txt`, mukana `finish_reason` ja mahdollinen kieltäytyminen), ja konsoli kertoo minne.

**Skillin kytkeminen.**

- *Claude Code:* kopioi `skills/ksiega-niedomowien/` kansioon `~/.claude/skills/` (henkilökohtainen) tai omaan repokopioosi kansioon `.claude/skills/`. Tämä repo jättää `.claude/`-kansion gitin ulkopuolelle, siksi skill toimitetaan kansiossa `skills/`.
- *Claude-sovellukset:* pakkaa kansio `ksiega-niedomowien/` ZIP-tiedostoksi (kansion itsensä on oltava arkiston juuressa) ja lisää se kohdassa **Customize → Skills**; koodin suorituksen on oltava päällä, ja istunto tarvitsee pääsyn repokopioosi, koska omorfin automaatit ja `export_results/` ovat omalla levylläsi. Käytä **Code**-välilehteä **paikallisen** istunnon kanssa: tavallisessa keskustelutilassa tai pilvi-istunnossa agentin lukemat tiedostot — lähdeotteet mukaan lukien — kopioidaan pilviympäristöön.
- *Muut agentit:* `SKILL.md` on tavallinen Markdown-ohje YAML-otsakkeella; sitä voi noudattaa mikä tahansa agentti, joka pystyy ajamaan paikallisia komentoja repossa. Jos agentti ei pysty käynnistämään itsenäistä aliagenttia, käytä sokeaan vaiheeseen komentoa `fill`.
- Pelkkä keskusteluavustaja ilman paikallista komentojen suoritusta (esim. custom GPT) ei pysty ajamaan tätä: omorfin ja sen noin 130 Mt:n automaattien on toimittava datasi vieressä.

> **Yksityisyys ja kustannukset.** Kolme tasoa vähiten dataa lähettävästä eniten lähettävään: `fill` lähettää vain merkinnän sumuisen tekstin (ei lähdettä); `draft` lähettää lähdelauseet sanatarkasti (`truth.sentences`) ja kertoo ennen kutsua, kuinka monta niitä on; skillin mukaan toimiva agentti lukee otteita lähteestä ja lähettää ne oman mallinsa palveluntarjoajalle — ja pilvi-istunnossa työskentelee tiedostojen pilvikopion päällä. Kaikki API-kutsut ovat maksullisia. Käytä niitä vain aineistoon, jonka voit jakaa näille palveluntarjoajille.

### 8. Helsinki Reacts (valinnainen, vaatii LLM-API-avaimen)

```bash
python helsinki_reacts.py <project> [<project> …]
# → export_results/_streams/<project>.md
python helsinki_reacts.py notes.txt             # myös mikä tahansa tekstitiedosto käy
python helsinki_reacts.py <project> --dry-run   # näytä, mitä lähetettäisiin, lähettämättä mitään
python helsinki_reacts.py <project> --lang en   # striimin kieli tälle ajolle
python helsinki_reacts.py <project> --kirja     # liitä kansion merkintä Sanomattomien kirjasta
```

Satiirinen striimikäsikirjoitus: helsinkiläinen striimaaja Valtteri reagoi chattinsa kanssa tallenteeseen, ja Lumi, kylmä puhesyntetisaattori, lukee lahjoitukset. Syötteenä on `export_results/`-kansion pelkkä nimi (sen `accessible_text.html`-tiedoston teksti ilman merkintäkieltä ja otsikoita) tai mikä tahansa tekstitiedosto; käsikirjoitus tallentuu tiedostoon `export_results/_streams/<nimi>.md`, ja saman nimen uusi ajo saa päätteen `_2`, `_3`.

**Kehote on sinun.** Järjestelmäkehote ei ole koodissa: oletus `helsinki_reacts.example.md` on tarkoituksella niukka. Kopioi se tiedostoksi `helsinki_reacts.md` (se on `.gitignore`-tiedostossa ja otetaan käyttöön automaattisesti, kun se on olemassa) ja muuta mitä haluat, tai osoita mikä tahansa tiedosto valitsimella `--prompt`. Yksi sääntö enemmän tai vähemmän muuttaa striimiä paljon, joten vertaa muutamaa ajoa ennen kuin valitset version. Skripti lisää itse vain sen, minkä täytyy toimia kehotteesta riippumatta: tallenteen, tulostekielen ja — valitsimella `--kirja` — Sanomattomien kirjan lohkon.

**Kieli.** `--lang`, sitten configin `reacts_lang`, sitten `ui_lang`. Suomi antaa itse striimin tavallisella suomella; mikä tahansa muu kieli antaa sen käännöksen, jossa lyhyet suomenkieliset välihuudahdukset jäävät kääntämättä.

**Sanomattomien kirja (`--kirja`).** Kansiolle, jolla on merkintä tiedostossa `Sanomattomien_kirja.md`, chat saa merkinnän usvaisen tekstin ja sokean täyttäjän ohilaukaukset teorioiksi, joista kiistellä. Vastausavain ei koskaan päädy mallille, ja kiinteä sääntö estää Valtteria vertaamasta aukkoa tallenteeseen, koska aukot kätkevät saman tallenteen sanoja. Ilman merkintää striimi tehdään ilman kirjaa.

Palveluntarjoaja ja malli: `reacts_llm_provider` / `reacts_model` (tyhjä = `llm_provider` / `llm_model`), jotka valitsimet `--provider` / `--model` ohittavat. Ajattelun taso: `medium`, kun ajattelu palaa luettavana (Claude OpenRouterin kautta), muuten `low`; valitsin `--effort low|medium|high` ohittaa sen. Jokainen syöte luetaan ennen ensimmäistä kutsua, joten tyhjä tai muu kuin UTF-8-tiedosto pysäyttää ajon maksutta. Valitsimen `--min-chars` (1500) arvoa lyhyempi vastaus hylätään kieltäytymisenä ja säilytetään tiedostossa `_streams/<nimi>.rejected.md`.

> **Yksityisyys ja kustannukset.** Jokaisen tallenteen koko teksti lähetetään määritetylle palveluntarjoajalle, ja se on maksullinen rajapinta; skripti kertoo tästä ennen ensimmäistä kutsua. Tulos on tekoälyn kirjoittamaa satiiria aineistosta: lue se ennen jakamista, varsinkin jos siinä mainitaan oikeita ihmisiä — mikään ei tarkista, mitä malli heistä väittää.

## Tuloste

Jokainen analysoitu korpus saa oman alihakemistonsa kohdassa `export_results/`, nimettynä lähdetiedoston mukaan (polku ja pääte poistettuna) tai `domain_slug`:n mukaan URL-osoitteille. Sisäänrakennettu esimerkkikorpus käyttää `export_results/_default/`.

Jokainen alihakemisto sisältää:

| Tiedosto                        | Tuottaja          | Kuvaus                                            |
|---------------------------------|-------------------|---------------------------------------------------|
| `sentences.csv`                 | notebook          | jokainen lause indeksinsä ja kielensä (`lang`) kanssa |
| `paragraphs.csv`                | notebook          | kappaleet (3–6 lausetta kukin)                    |
| `theses.csv`, `theses.txt`      | notebook          | yksi teesi per kappale (korkein-TF-IDF-lause); `.txt`-tiedoston nimi mukautuu korpuksen kieleen (esim. `tezy.txt` puolaksi, `тезисы.txt` venäjäksi) |
| `keywords_tfidf.csv`            | notebook          | avainsanat (uni/bi/trigrammit) TF-IDF-painoineen  |
| `paragraphs_with_topics.csv`    | notebook          | kappaleet määrätyllä KMeans-aiheellaan            |
| `topic_keywords.json`           | notebook          | avainsanat aiheittain                             |
| `entities.csv`                  | notebook          | kaikki nimennetyt entiteetit ja niiden tunnisteet |
| `language_spans.csv`            | notebook          | vieraskieliset jaksot: dokumentti, merkkisiirtymät, kieli, `block` tai `inline`, teksti |
| `sentiment.csv`                 | notebook *(valinnainen)* | kappalekohtainen sentimentti (`para_id`, `label`, `score`, `lang`) — vain kun `enable_sentiment` on `true`; syöte shamanistiselle kerrokselle, ei koskaan näytetä käyttäjälle |
| `accessible_text.html`          | notebook          | `lang` jokaisessa kappaleessa sekä `<span lang>` jokaisessa vieraskielisessä lauseessa ja lauseen sisäisessä jaksossa (lainaus, nimi) — ruudunlukijat vaihtavat ääntä automaattisesti per katkelma |
| `accessible_text.docx`          | notebook          | sama sisältö `<w:lang>`:lla asetettuna per `Run` (`pl-PL`, `ru-RU`, `en-US`, `it-IT`, `fi-FI`, `is-IS`, `de-DE`, `es-ES`, `fr-FR`) — Word ja SAPI käyttävät sitä offline-tilassa ilman online-tunnistinta |
| `analysis_report.html`           | `generate_report.py` | globaali saavutettava HTML-raportti            |
| `diagnostic_report.html`         | `generate_diagnostic.py` | jäsennelty diagnostiikkaraportti (aiheet, teesit, entiteetit tyypeittäin, avainsanat) CSV/JSON-vienneistä |
| `gemini_notebook_report.md` | `generate_md.py`     | Gemini Notebook -valmis Markdown (entinen NotebookLM) |
| `audio_scripts/*.txt`           | `shamanic_pipeline.py`, `shamanic_ai.py` | rituaaliset / kerronnalliset tekstiartefaktit |
| `audio_scripts/*.mp3`           | `shamanic_voice.py` *(valinnainen)* | neljä kerronnallista ääntä syntetisoituna äänitiedostoiksi ElevenLabsin kautta |

## Saavutettavuus

Tämä on projektin keskeinen arvo. Kaikki alla oleva on tarkoituksellista ja on säilytettävä, kun putkea muokataan:

- **Ei ANSI-värejä, emojeita tai pseudografiikkaa stdoutissa.** Ruudunlukija lukee jokaisen merkin kirjaimellisesti — `[OK]` "🟢":n sijaan, `---` "───━━━":n sijaan.
- **Vaiennetut edistymispalkit** (`tqdm`, `transformers`, `torch`) — `cell_model._silence_hf_progress()` mykistää Hugging Face/torch -latauspalkit ja varoitukset ennen IceBERT:in ja icelandic-ner-bert:n lataamista islanninkieltä varten; `cell_corpus._silence_ocr_progress()` tekee saman OCR-moottoreille.
- **Kappale-, lause- ja jaksokohtainen `lang`-merkintä viennissä.** `accessible_text.html` ja `accessible_text.docx` kantavat ISO 639-1 -koodin jokaisessa kappaleessa, jokaisessa vieraskielisessä lauseessa ja jokaisessa lauseen sisäisessä vieraskielisessä jaksossa (lainaus tai nimi lauseen sisällä). NVDA, JAWS, Narrator, VoiceOver, Word ja SAPI kunnioittavat näitä tageja ja vaihtavat ääntä automaattisesti — jopa offline-tilassa.
- **Kovakoodattu englannin merkintä HTML-raportissa.** `generate_report.py` kääräisee aina teknisen englannin katkelmat — POS-tagit (`NOUN`, `VERB`, `ADJ`), NER-tunnisteet (`PER`, `ORG`, `[orgName]`), spaCy / Hugging Face -mallien tunnisteet, ASCII-polut, koodilohkot — tagiin `<span lang="en">`, jolloin niitä ei enää ääntää dokumentin oletusvenäläisellä äänellä.
- **Vieraskielisen korpuksen pir-katkelmamerkintä HTML:ssä.** Kun korpus ei ole venäläinen, jäsennellyt ulostulot (lauseotteet, avainsanaluettelot, aihesanat, RAG-järjestysrivit, lemmatisointitaulukot) käärätään tagiin `<span lang="target_lang">`.
- **Lineaarinen HTML-rakenne** (`<main>`, oikea otsikkohierarkia).

### Tulosten lukeminen ei-venäjänkielisenä käyttäjänä

Notebookin selostus ja useimpien solujen `print()`-tuloste on kirjoitettu venäjäksi. Kaksi Jupyterin käyttöliittymän ominaisuutta tekevät siitä vihamielisen ei-venäjänkielisille ruudunlukijakäyttäjille, ja putki toimittaa kullekin oman kiertotien:

- **Selaimessa toimiva Jupyter koodaa kovakoodatusti `lang="en"` dokumenttiin**, eikä "Käännä tämä sivu?" -kehote koskaan ilmesty `localhost`-sivuilla. Venäjäksi selostettu notebook luetaan siten englanninkielisellä TTS-äänellä — täydellistä kaaosta. Pragmaattinen ratkaisu on **VS Code:n Jupyter-laajennus**: sen lista-näkymä lausuu vain `code cell` / `markdown cell` -etiketit ilman ISO-merkintöjä, voit painaa Enter koodisolujen läpi ja ↓ ohittaa markdown-solut kuuntelematta niiden sisältöä, ja kovakoodatun englannin ongelma rajoittuu tuloste-näkymään (`Ctrl+Shift+↓`), johon voi yksinkertaisesti olla menemättä.
- **`generate_report.py` on käytännössä pakollinen ei-venäjänkielisille lukijoille.** Se tuottaa `analysis_report.html`-tiedoston, jossa on `<html lang="ru">` ja täysi joukko `<span lang="…">`-tageja jokaiselle katkelmalle. Tavallisessa selaimessa avattuna (ei Jupyterin sisältä) se laukaisee selaimen "Käännä tämä sivu?" -kehotteen venäjänkieliselle selostukselle, säilyttäen samalla TTS-äänen vaihdon korpuksen katkelmilla ja englanninkielisillä teknisillä termeillä (POS, NER, mallien nimet).
- **Interaktiivinen Q&A kirjoittaa `qa_results.html`-tiedoston ja avaa sen puolestasi.** `cell_qa_rag` tulostaa edelleen kysymyksen ja kolme parasta osumaa stdoutiin — mutta lisäksi se kirjoittaa saman sisällön tiedostoon `export_results/<project>/qa_results.html` ja kutsuu `webbrowser.open()`, jolloin sivu päätyy järjestelmäselaimeen, jossa sekä käännös että per-katkelmainen TTS-äänen vaihto toimivat. Jupyterin tuloste-näkymä, jossa kovakoodattu `lang="en"` tekee venäjänkieliset kääreet ruudunlukijalle lukukelvottomiksi, ei siis enää ole ainoa polku tulokseen. Jokainen uusi kysely ylikirjoittaa tiedoston.

## Tunnetut rajoitukset

- **Lainasanojen alkuperää ei merkitä.** Kielimerkintä (`lang`-attribuutit, ks. *Jokaisen sanan kieli*) kattaa sanat, jotka jonkin toisen luetellun kielen sanasto tuntee, sekä vieraalla kirjoitusjärjestelmällä kirjoitetut katkelmat: kreikkalaiset kirjaimet, latinalaiset kirjaimet kyrillisessä tekstissä. Selvää alkuperämerkintää (`греч.`, `łac.`, `z niemieckiego`, `имеет греческое происхождение`) ei yhdistetä lainattuun sanaan, ja tekstin omalla kirjaimistolla kirjoitettu sana (`фразис` venäläisessä tekstissä) säilyttää korpuksen kielen. Merkinnöillä ei ole vakiomuotoa (lyhenne, adjektiivi, kokonainen ilmaus), ja kyrillisen `фразис`-sanan merkitseminen kreikaksi vaihtaisi ruudunlukijan kreikkalaiseen ääneen, mikä kuulostaa huonommalta kuin venäläinen oletusääni.
- **Suomi: virkkeen ensimmäinen sana.** Virkkeen alussa jokainen sana alkaa isolla kirjaimella, ja spaCyn jäsennin pitää joskus imperatiivia tai interjektiota erisnimenä: `Anna kuulua.` muuttuu nimeksi *Anna* ja `Oota, miten…` nimeksi *Oota*. omorfi-korjaus ei koskaan kirjoita nimeksi merkittyä sanaa yli, koska muuten oikeat nimet muuttuisivat yleissanoiksi (*Tuskia* → *tuska*). Tällainen sana säilyttää kirjoitetun muotonsa lemmana ja voi päätyä lemmaluetteloihin, avainsanoihin ja juurten loitsuun (`anna`, `oota`). Kun jäsennin pitää sanaa interjektiona, omorfi antaa verbin (*Oota* → `oottaa`, versiosta v1.11.1 alkaen). Sanomattomien kirjan kieliopin vuodon tarkistus ei laske avainsanaa, jota lähde käyttää myös nimenä keskellä virkettä (*Anna Maria …*).
- **Ilman tarkkeita kirjoitetut nimet.** Vieraskielinen nimi merkitään vain, jos kirjoitusasu itse antaa näytön: kirjaimia, joita perusaakkostossa ei ole (`Kaczyński`), muoto, jonka tuntee vain toisen luetellun kielen sanasto, tai toinen kirjoitusjärjestelmä (`Качиньский` merkitään venäjäksi). Monet toimitukset jättävät vieraiden nimien tarkkeet pois. Marraskuun 15. päivänä 2026 kerätyissä RSS-otsikoissa (Google News maittain ja portaalien omat syötteet) suomalaiset toimitukset kirjoittivat *Swiatek* 8 otsikossa kahdeksasta ja *Kaczynski* 2 otsikossa kolmesta, vaikka *Wałęsa* säilytti kirjaimensa 6 otsikossa seitsemästä; ranskalaisissa, italialaisissa, espanjalaisissa ja ruotsalaisissa otsikoissa tarkkeeton muoto oli enemmistönä ainakin kahdella näistä kolmesta nimestä, saksalaiset ja englantilaiset toimitukset säilyttivät kirjaimet useimmiten ja venäläiset translitteroivat kyrillisiksi. Tarkkeeton nimi taivutusmuotoineen (*Kaczynskin*) koostuu pelkästään perusaakkoston kirjaimista eikä sitä ole siinä muodossa missään sanastossa, joten se jää peruskieleen ja sen lukee peruskielen ääni, luettelipa `corpus_languages` mitä tahansa. Pelkkä teksti ei ratkaise asiaa, eikä ATA arvaa poistettuja kirjaimia takaisin: jokaisen perusaakkoston kirjaimista koostuvan tuntemattoman sanan vertaaminen tarkkeettomiksi riisuttuihin vieraisiin sanastoihin vaihtaisi äänen myös tavallisissa sanoissa. Myös nimi kielestä, jolle täällä ei ole pakettia (*Erdoğan*), jää peruskieleen.

## Repositorion rakenne

```
accessible_text_analyst/
├── accessible_text_analyst.ipynb   # pääputki (42 solua)
├── generate_report.py              # HTML-raportin generaattori (lukijanäkymä)
├── generate_diagnostic.py          # diagnostiikka-HTML-raportti CSV/JSON-vienneistä
├── generate_md.py                  # Gemini Notebook -Markdown-muunnin
├── shamanic_pipeline.py            # valinnainen: ei-LLM rituaalinen jälkikäsittelijä
├── shamanic_ai.py                  # valinnainen: LLM-vetoiset rituaaliset kertojat
├── llm_klient.py                   # LLM-palveluntarjoajan ja avaimen valinta (yhteinen)
├── shamanic_voice.py               # valinnainen: ElevenLabs-äänidispatcher (kertasuoritteinen)
├── shamanic_locale.py              # lokalisointipaketti shamanistiselle kerrokselle
├── ksiega_niedomowien.py           # valinnainen: Sanomattomien kirja (vain suomi)
├── helsinki_reacts.py              # valinnainen: Helsinki Reacts -striimikäsikirjoitukset (LLM)
├── helsinki_reacts.example.md      # Helsinki Reactsin oletuskehote (versionhallinnassa)
├── helsinki_reacts.md              # oma kopiosi kehotteesta (gitignore)
├── skills/ksiega-niedomowien/SKILL.md  # agentin skill ksiega_niedomowien.py:lle
├── config.example.json             # asetusmalli, JSON-pääte (versioidaan)
├── config.example.ini              # asetusmalli, INI-pääte (versioidaan)
├── config.json / config.ini        # paikalliset asetuksesi (gitignored)
├── golden_key.env                  # LLM- ja ElevenLabs-avaimet (gitignored)
├── requirements.txt                # pip-riippuvuudet
├── CLAUDE.md                       # opas Claude Codelle
├── README.md                       # kanoninen README (englanniksi)
├── README_pl.md, README_ru.md, …   # käännökset (paluulinkki ylhäällä)
├── VERSION                         # valmisteltava julkaisusykli (`X.Y.Z-WIP` julkaisuun asti)
├── release_notes.md                # release notes käänteisessä aikajärjestyksessä
└── export_results/                 # analyysin tulokset (gitignored)
    ├── Sanomattomien_kirja.md      # Sanomattomien kirja, kasvaa merkintä kerrallaan
    ├── _streams/                   # Helsinki Reacts -käsikirjoitukset
    └── <project_name>/
        ├── sentences.csv
        ├── paragraphs.csv
        ├── theses.csv
        ├── theses.txt              # nimi mukautuu korpuksen kieleen
        ├── accessible_text.html
        ├── accessible_text.docx
        ├── analysis_report.html
        ├── diagnostic_report.html
        ├── gemini_notebook_report.md
        └── audio_scripts/…
```

## Lisenssi

Julkaistu [MIT-lisenssillä](LICENSE). Putki jaetaan vain lähdekoodina — ei binäärejä — ja notebook on luonteeltaan muokattavissa solu kerrallaan selaimessa tai VS Coden Jupyter-laajennuksessa. MIT-lisenssi vain tekee eksplisiittiseksi sen, mitä formaatti jo edellyttää.
