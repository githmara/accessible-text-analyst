# Accessible Text Analyst

Un pipeline de TAL multilingue conçu pour **l’accessibilité avec les lecteurs d’écran** (NVDA, JAWS, VoiceOver, Narrateur). Tout le code, la sortie console et les rapports sont pensés pour être interprétés proprement par les technologies d’assistance : pas de couleurs ANSI, pas d’emoji, pas de barres de progression, pas de caractères de dessin de cadres.

> **Autres langues :** [English](README.md) · [polski](README_pl.md) · [русский](README_ru.md) · [suomi](README_fi.md) · [íslenska](README_is.md) · [italiano](README_it.md) · [Deutsch](README_de.md) · [español](README_es.md)

> **État de la traduction (v1.0).** Seul le README a été traduit. La narration du notebook Jupyter, toute la sortie console, `CLAUDE.md` et les commentaires du code restent dans leurs langues d’origine (surtout le russe, avec du polonais dans les correctifs et dans la couche chamanique). Leur traduction est volontairement prévue pour la v1.1 — voir `release_notes.md`.

## Contenu du projet

- `accessible_text_analyst.ipynb` — un notebook Jupyter contenant tout le pipeline d’analyse (42 cellules : 21 de code + 21 de markdown ; la narration du notebook est en russe). Il écrit deux artefacts accessibles (`accessible_text.html`, `accessible_text.docx`) dans lesquels chaque paragraphe et chaque phrase en langue étrangère portent leur propre attribut `lang`, afin que les lecteurs d’écran et les moteurs TTS changent de voix automatiquement — même hors ligne.
- `generate_report.py` — un script de post-traitement qui transforme le notebook exécuté en un seul fichier HTML accessible (`analysis_report.html`). Il entoure les fragments d’un corpus en langue étrangère de `<span lang="target_lang">` et, quelle que soit la langue du corpus, place toujours `<span lang="en">` autour du contenu technique en anglais (étiquettes POS, étiquettes NER, identifiants de modèles spaCy/Hugging Face, noms de fichiers ASCII). Le code en ligne et les blocs de code de la narration sont balisés en bloc `lang="en"`. En mode lecture (`remove_noise: true`), il réduit les boucles de diagnostic par document du notebook aux premiers documents au lieu d’en déverser des centaines.
- `run_all.py` — un lanceur pour toute la chaîne locale gratuite : il enregistre le noyau Jupyter `analyst_env` s’il manque, exécute le notebook sans interface (sans la cellule interactive de questions) et enregistre ses sorties dans le `.ipynb`, puis lance `generate_report.py`, `shamanic_pipeline.py` et, pour un corpus finnois, le `scan` du Livre du Non-Dit. Il ne lance jamais d’étape payante (rituels LLM, voix ElevenLabs, `draft`/`fill` du Livre).
- `generate_diagnostic.py` — un générateur indépendant d’un **rapport de diagnostic** complet (`diagnostic_report.html`) construit directement à partir des exports CSV/JSON du notebook (et non à partir de la sortie de `generate_report.py`). Une structure navigable, pensée d’abord pour les lecteurs d’écran : une table des matières dans `<nav>` et des sections — chacune avec son propre titre et ses listes — pour une vue d’ensemble, les thèmes avec leurs paragraphes, les thèses, les entités nommées regroupées par type et les principaux mots-clés. Les libellés structurels suivent `ui_lang` ; les fragments du corpus reçoivent `<span lang="…">`, les étiquettes NER `<span lang="en">`.
- `generate_md.py` — convertit le `analysis_report.html` généré en `gemini_notebook_report.md` pour l’importer dans Gemini Notebook (anciennement NotebookLM). Les spans d’accessibilité sont retirés, car Gemini Notebook ne les exploite pas.
- `shamanic_pipeline.py` *(optionnel)* — un post-processeur sans LLM qui transforme les exports CSV/JSON du notebook en artefacts textuels rituels (`oracle_script.txt`, `lore_fragments/`, `raw_roots_chant.txt`, `prophecies.txt` et — quand l’analyse de sentiment optionnelle est activée — `emotional_undertow.txt`), entièrement localisés dans les neuf langues prises en charge.
- `shamanic_ai.py` *(optionnel, piloté par LLM)* — appelle un LLM (OpenAI par défaut ; OpenRouter ou tout point de terminaison compatible OpenAI via `llm_provider`) pour générer quatre voix narratives (`Katla`, `Vieno`, `Lumi`, `Sami`) à partir des mêmes exports. Quand le `sentiment.csv` optionnel est présent, Vieno construit son chant sur l’arc émotionnel du texte plutôt que sur des phrases brutes. Nécessite la clé du fournisseur choisi dans `golden_key.env`.
- `shamanic_voice.py` *(optionnel, nécessite ElevenLabs)* — un répartiteur autonome à exécution unique qui synthétise en audio `.mp3` les quatre artefacts narratifs produits par `shamanic_ai.py` via l’API ElevenLabs, consigne chaque réussite ou échec dans la console et se termine (pas de bot, pas de serveur). Il lui faut `ELEVENLABS_API_KEY` dans `golden_key.env` et une correspondance `voices` dans la configuration.
- `shamanic_locale.py` — le paquet de localisation des deux scripts chamaniques (modèles, en-têtes et textes de secours de Lumi dans les neuf langues prises en charge).
- `ksiega_niedomowien.py` *(optionnel, finnois uniquement, assisté par un agent)* — le Livre du Non-Dit (*Sanomattomien kirja*) : transforme `raw_roots_chant.txt` en un journal énigmatique qui s’enrichit peu à peu et dont un modèle aveugle n’a pas su deviner les trous. C’est l’assistant déterministe de la skill de `skills/ksiega-niedomowien/SKILL.md` ; sa sortie console suit `ui_lang`.
- `helsinki_reacts.py` *(optionnel, avec LLM)* — script satirique d’un live : Valtteri, d’Helsinki, réagit avec un chat finlandais à un enregistrement (un dossier d’export ou un fichier texte). Le prompt système est hors du code (`helsinki_reacts.example.md`, votre propre copie dans `helsinki_reacts.md`) et la langue du live suit `reacts_lang`, puis `ui_lang`. Nécessite la clé du fournisseur choisi dans `golden_key.env`.

## Ce que fait le pipeline

1. Charge le texte depuis un fichier (`.pdf`, `.txt`, `.docx`, `.md`, `.html` ou des images : `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`, `.webp`) ou depuis une URL — en retirant les en-têtes et pieds de page répétés, les barres latérales, les sections « Articles similaires » et autres textes répétitifs du même genre. Les PDF numérisés et les images passent par l’OCR : chaque langue de `corpus_languages` lit la page avec son propre moteur (l’OCR intégré à Windows 10/11, ou Tesseract pour une langue que Windows n’a pas — aujourd’hui l’islandais), RapidOCR la relit une fois de plus en secours, et un dictionnaire de chaque langue choisit les formes de dictionnaire parmi toutes les lectures.
2. Détermine la langue de chaque mot à partir des dictionnaires des langues listées dans `corpus_languages` (voir **La langue de chaque mot**) : la langue de base pilote le pipeline spaCy, les citations et les noms en langue étrangère deviennent des segments linguistiques.
3. Exécute spaCy une fois par segment de texte : le modèle de la langue de base traite le texte de base avec les segments étrangers insérés, et chaque bloc étranger est traité par le modèle de sa propre langue, chargé à la demande via `get_nlp()` (enveloppé dans `functools.lru_cache(maxsize=2)`, si bien qu’au plus deux modèles sont en cache). Il n’y a ni passe de resegmentation ni seconde passe multilingue.
4. Tokenisation → filtrage des mots vides → lemmatisation → étiquetage POS → NER, chaque token étant analysé par le modèle de sa propre langue.
5. Représentations vectorielles : Bag of Words, TF-IDF + recherche par requête automatique et classement par cosinus.
6. Structure : phrases → paragraphes (de 3 à 6 phrases chacun) → thèses (la meilleure phrase de chaque paragraphe). Chaque phrase porte sa langue et ses segments étrangers insérés ; chaque paragraphe porte sa langue dominante.
7. Modélisation des thèmes avec KMeans sur les vecteurs de paragraphe de spaCy.
8. *(Optionnel, désactivé par défaut)* Notation du sentiment par paragraphe avec `cardiffnlp/twitter-xlm-roberta-base-sentiment`, écrite dans `sentiment.csv`. Le résultat n’est jamais montré à l’utilisateur — il ne sert qu’à alimenter la couche chamanique. Voir **Configuration** (`enable_sentiment`).
9. Export CSV/JSON + un rapport de synthèse textuel + un export HTML et DOCX balisé pour l’accessibilité + un rapport HTML global (`analysis_report.html`).

## Langues prises en charge

| Code | Langue     | Modèle spaCy           | NER / vecteurs |
|------|------------|------------------------|----------------|
| pl   | polonais   | `pl_core_news_lg`      | spaCy          |
| ru   | russe      | `ru_core_news_lg`      | spaCy          |
| en   | anglais    | `en_core_web_lg`       | spaCy          |
| it   | italien    | `it_core_news_lg`      | spaCy          |
| de   | allemand   | `de_core_news_lg`      | spaCy          |
| es   | espagnol   | `es_core_news_lg`      | spaCy          |
| fr   | français   | `fr_core_news_lg`      | spaCy          |
| fi   | finnois    | `fi_core_news_lg`      | spaCy          |
| is   | islandais  | `spacy.blank("is")` + Hugging Face | `mideind/IceBERT` (vecteurs), `grammatek/icelandic-ner-bert` (NER) |

Il n’existe pas de modèle spaCy complet pour l’islandais : deux modèles Hugging Face sont donc branchés sur un pipeline vide. Le premier téléchargement demande ~1,3 Go d’espace disque et une connexion internet ; les exécutions suivantes réutilisent le cache HF.

**Amélioration optionnelle de la morphologie finnoise (omorfi).** Le lemmatiseur statistique de `fi_core_news_lg` peine avec la morphologie agglutinante du finnois — il produit régulièrement des lemmes aberrants comme *kytköknen* ou *pisttää*. Quand le paquet en Python pur `omorfi` est installé et ses automates FST téléchargés (voir l’étape 5 de l’installation), le notebook ajoute un composant `omorfi_lemmas` qui remplace les lemmes et les traits morphologiques UD par des analyses de dictionnaire partout où elles concordent avec la catégorie grammaticale de l’étiqueteur spaCy (`kytköksistä` → `kytkös`, `Euroopassa` → `Eurooppa`, `pistät` → `pistää`). Sans le paquet ou sans les automates, le pipeline garde silencieusement le comportement standard de spaCy.

## La langue de chaque mot

Vous listez les langues du texte dans `corpus_languages` (`config.json` ; l’ancien nom `ocr_languages` est toujours lu). À partir des dictionnaires de ces langues, le notebook détermine :

1. **La langue de base** (`LANG`) — la langue dont le dictionnaire connaît la plus grande part des mots du corpus (les parts sont affichées). Elle pilote le pipeline spaCy principal.
2. **La langue de chaque mot** (`odcinki_jezykowe.py`). Un mot que le dictionnaire de base ne connaît pas, mais qu’une autre langue listée connaît, appartient à cette langue ; un mot connu de plusieurs d’entre elles va à l’alphabet le plus petit qui contient toutes ses lettres — ainsi un mot anglais n’est pas accaparé par le dictionnaire polonais, qui connaît beaucoup de formes anglaises, tandis que `Łódź` reste polonais. L’écriture est un fait : un mot cyrillique dans un texte latin reçoit une langue cyrillique même si aucune n’est listée.
3. **Segments étrangers** — au moins deux mots étrangers consécutifs d’une même langue dans une phrase, ou un mot comportant des lettres absentes de l’alphabet de base. Un segment qui couvre des phrases entières est un **bloc** et il est traité par son propre modèle spaCy (phrases, NER, lemmes). Un segment à l’intérieur d’une phrase dans la langue de base est un **segment inséré** : la phrase reste au modèle de base, et le segment reçoit ses lemmes et ses étiquettes POS du modèle de sa propre langue.

L’export porte le résultat : `<span lang="…">` dans `accessible_text.html` et un `Run` séparé avec `<w:lang>` dans `accessible_text.docx` pour chaque phrase étrangère et chaque segment inséré, afin que le lecteur d’écran change de voix exactement sur la citation ou le nom, et non sur toute la phrase. Tous les segments sont aussi listés dans `language_spans.csv`, et `sentences.csv` comporte une colonne `lang`.

Dictionnaires : les vecteurs spaCy (une liste finie de formes) pour le polonais, l’anglais, le russe, l’italien, l’allemand, l’espagnol et le français ; `omorfi` pour le finnois ; BÍN (`islenska`) pour l’islandais — les mêmes dictionnaires que ceux du vote OCR. Avec une seule langue dans `corpus_languages`, aucun dictionnaire n’est chargé et seuls les mots d’une autre écriture sont balisés. Un dictionnaire manquant arrête l’exécution avec un message qui indique la solution.

**Quelles langues lister.** Mesuré sur 20 transcriptions finnoises (55 000 mots) qui citent beaucoup de noms polonais : avec `["fi", "en"]`, le notebook trouve 34 segments anglais (termes et citations) ; avec `["fi", "pl", "en"]`, il trouve en plus 57 segments polonais — des noms polonais et quelques expressions polonaises, désormais lus par une voix polonaise au lieu d’une voix finnoise — et aucun mot anglais ne passe au polonais. Donc :

- listez chaque langue dont des **citations** apparaissent dans le texte ;
- pour un texte écrit dans une langue qui cite des **noms** d’une autre (des noms polonais dans un texte finnois), ajoutez la langue des noms : les noms à leur forme de base, et les noms comportant des lettres absentes de l’alphabet de base (`ł`, `ś`), sont alors lus par la voix de leur propre langue. Un nom décliné uniquement avec des lettres de l’alphabet de base (`Kowalskille`) reste de toute façon dans la langue de base ;
- ne listez pas une langue absente du texte : elle n’ajoute que de faux candidats.

**Pourquoi pas un détecteur statistique.** Jusqu’à ATA 1.x, `lingua-language-detector` classait des phrases entières. Sur les mêmes transcriptions, il a marqué 127 phrases comme étrangères, presque toutes à tort ; les heuristiques de garde nécessaires pour l’en empêcher laissaient 2 phrases et aucune des citations anglaises. ATA 2.0 l’a supprimé. Le rapport global (`generate_report.py`) balise les mots étrangers de sa narration russe avec les mêmes dictionnaires (les langues de `corpus_languages` plus l’anglais).

## Prérequis

- Python 3.12 ou plus récent (l’ensemble des dépendances est testé avec Python 3.14).
- ~1,5 Go d’espace disque libre pour les modèles spaCy `_lg` (un par langue installée). Ajoutez ~1,3 Go si vous activez l’islandais (Hugging Face `transformers` + `torch` + IceBERT + icelandic-ner-bert). La NER islandaise lit tout le document par fenêtres qui se chevauchent : environ 4 000 caractères par seconde sur CPU, si bien qu’un livre (1 Mo de texte islandais) prend quelques minutes.
- Prise en charge de l’OCR (optionnelle) : les paquets `winrt-*` (moins de 1 Mo) et, pour chaque langue de `corpus_languages`, le module linguistique Windows avec reconnaissance optique de caractères (Paramètres > Heure et langue > Langue et région) ; `rapidocr` avec `onnxruntime` (ses modèles, environ 40 Mo, se téléchargent au premier appel de l’OCR) ; pour une langue sans moteur Windows (aujourd’hui l’islandais), `tesserocr` et le modèle tessdata_best de cette langue dans le dossier `tessdata` du dépôt (islandais : https://github.com/tesseract-ocr/tessdata_best/raw/main/isl.traineddata, environ 9,5 Mo) plus le dictionnaire `islenska` (~62 Mo). L’OCR n’a plus besoin de `torch`. Un moteur ou un dictionnaire manquant arrête l’exécution avec un message qui indique la solution. Dictionnaire islandais : The Database of Icelandic Morphology (BÍN), The Árni Magnússon Institute for Icelandic Studies, autrice et éditrice Kristín Bjarnadóttir, CC BY-SA 4.0.
- Ajoutez ~130 Mo si vous activez l’amélioration de la morphologie finnoise (les automates FST d’`omorfi` téléchargés par `omorfi-download`).
- Une connexion internet lors de la première exécution (téléchargement des modèles).

## Mise en place de l’environnement

Choisissez l’une des trois options ci-dessous. Toutes trois se terminent par le même `pip install -r requirements.txt` + téléchargement des modèles spaCy.

### Option A — `venv` local (recommandé pour l’usage quotidien)

```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Le répertoire `.venv/` figure dans `.gitignore`. Depuis le venv activé, passez à l’**Installation** ci-dessous.

### Option B — Anaconda / Miniconda

```bash
conda create -n accessible-text-analyst python=3.14
conda activate accessible-text-analyst
```

Passez ensuite à l’**Installation** ci-dessous. Le `pip` fourni avec Anaconda fonctionne sans problème — il n’existe pas de liste de paquets propre à Conda pour ce projet.

### Option C — Google Colab (sans installation locale)

Ouvrez un nouveau notebook Colab et collez ce qui suit dans la première cellule. Cela clone le dépôt, installe les dépendances et télécharge les modèles spaCy dont vous avez besoin.

```python
!git clone https://github.com/<your-fork>/accessible_text_analyst.git
%cd accessible_text_analyst
!pip install -r requirements.txt
!python -m spacy download en_core_web_lg
# N’ajoutez les lignes ci-dessous que pour les langues dont vous avez vraiment besoin :
# !python -m spacy download pl_core_news_lg
# !python -m spacy download ru_core_news_lg
# !python -m spacy download it_core_news_lg
# !python -m spacy download fi_core_news_lg
# !python -m spacy download de_core_news_lg
# !python -m spacy download es_core_news_lg
# !python -m spacy download fr_core_news_lg
```

Téléversez ensuite votre `config.json` (ou `config.ini`) depuis le panneau Fichiers, définissez `source_file` et exécutez le notebook. Remarque : les sessions Colab sont éphémères — les modèles téléchargés et les artefacts de `export_results/` disparaissent quand l’environnement d’exécution est recyclé. Pour les analyses longues, montez Google Drive et écrivez-y la sortie.

## Installation

```bash
# 1. Dépendances Python
pip install -r requirements.txt

# 2. Modèles spaCy — n’installez que les langues dont vous avez vraiment besoin.
# Les variantes *_lg sont nécessaires, car la modélisation des thèmes dépend des vecteurs de mots.
python -m spacy download pl_core_news_lg
python -m spacy download ru_core_news_lg
python -m spacy download en_core_web_lg
python -m spacy download it_core_news_lg
python -m spacy download fi_core_news_lg
python -m spacy download de_core_news_lg
python -m spacy download es_core_news_lg
python -m spacy download fr_core_news_lg

# 3. (Optionnel) Prise en charge de l’islandais — décommentez `transformers` et `torch`
# dans requirements.txt et relancez `pip install -r requirements.txt`.
# IceBERT et icelandic-ner-bert sont alors récupérés sur Hugging Face à la première exécution.

# 4. (Optionnel) Analyse de sentiment — décommentez `transformers`, `torch`,
# `sentencepiece`, `protobuf` et `tiktoken` dans requirements.txt, relancez
# l’installation et mettez "enable_sentiment": true dans config.json. Le modèle
# (~1,1 Go) est récupéré sur Hugging Face à la première exécution puis mis en cache.
# Les cinq paquets sont nécessaires ensemble pour construire le tokeniseur XLM-RoBERTa.

# 5. (Optionnel) Amélioration de la morphologie finnoise — décommentez `omorfi` dans
# requirements.txt, relancez l’installation, puis téléchargez les automates FST
# (~130 Mo de fichiers *.hfst décompressés à la racine du dépôt ; ils sont dans .gitignore).
# Lancez-le depuis la racine du dépôt :
omorfi-download

# 6. (Optionnel) Comparez les versions installées avec les bornes de
# requirements.txt et avec PyPI. Il ne fait qu’avertir, il ne bloque jamais :
python audyt_zaleznosci.py
```

## Configuration

Copiez la configuration d’exemple dans un fichier local. `config.json` et `config.ini` sont tous deux acceptés — **le contenu du fichier est du JSON dans les deux cas** ; l’extension `.ini` n’est qu’une concession pratique aux utilisateurs de Windows peu techniciens, pour qui `.json` n’a pas de programme associé par défaut.

```bash
# Choisissez-en un :
cp config.example.json config.json
cp config.example.ini  config.ini
```

`config.json` et `config.ini` figurent tous deux dans `.gitignore`, si bien que chaque utilisateur garde sa propre copie locale.

Contenu :

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

| Clé                | Type            | Rôle |
|--------------------|-----------------|---------|
| `source_file`      | string          | Chemin vers un fichier (`.pdf`, `.txt`, `.docx`, `.md`, `.html` ou une image) **ou** une URL (`http://`, `https://`). Une chaîne vide ou un fichier manquant renvoie au corpus d’exemple intégré. |
| `custom_patterns`  | string[]        | Expressions régulières optionnelles retirées du texte brut (titres courants, pieds de page, textes répétitifs). Exemple : `["Editorial: .*", "Copyright \\d{4}"]`. |
| `remove_noise`     | boolean         | Fait basculer `generate_report.py` entre le mode lecture (`true`, masque les barres de chargement Hugging Face/torch et les tableaux de lemmatisation/POS) et le mode diagnostic complet (`false`). |
| `corpus_languages` | string[]        | Langues du TEXTE (codes des paquets linguistiques : `de`, `en`, `es`, `fi`, `fr`, `is`, `it`, `pl`, `ru`) ; l’ancien nom `ocr_languages` est toujours lu. Leurs dictionnaires choisissent la langue de base et la langue de chaque mot (voir **La langue de chaque mot**), et pour les PDF numérisés et les images chacune lit la page avec son propre moteur OCR. Ne listez que les langues réellement présentes dans le texte : une langue de trop ralentit l’OCR et ajoute de faux candidats. Le latin et le cyrillique peuvent être mélangés (`["fi", "ru"]`). |
| `enable_sentiment` | boolean         | Active l’analyse de sentiment optionnelle par paragraphe (`false` par défaut). Nécessite les dépendances de sentiment commentées (voir l’étape 4 de l’installation). Écrit `sentiment.csv` ; le résultat n’est jamais montré à l’utilisateur, il n’alimente que la couche chamanique (le rituel `emotional_undertow.txt` et le chant de Vieno). En cas d’échec de chargement, elle est ignorée silencieusement — sans solution de repli. |
| `ui_lang`          | string          | Langue de l’interface pour la sortie console et l’attribut `<html lang>` du rapport généré (`pl` / `en` / `ru` / `fi` / `is` / `it` / `de` / `es` / `fr`). Chaîne vide ou code inconnu → repli sur `en`. Indépendante de la langue du corpus analysé, que décident les dictionnaires de `corpus_languages`. |
| `lumi_katla_lines` | integer or null | Plafond optionnel de l’ornement pour la dépêche de Lumi dans `shamanic_ai.py` : combien de lignes non vides du monologue de Katla Lumi voit. `null` ou clé absente = contenu complet ; entier N > 0 = les N premières lignes. |
| `lumi_vieno_lines` | integer or null | Comme `lumi_katla_lines`, mais pour le chant d’échos de Vieno. |
| `voices`           | object          | Associe à chaque voix chamanique (`katla` / `vieno` / `lumi` / `sami`) un identifiant de voix ElevenLabs, utilisé par `shamanic_voice.py`. Une voix dont l’identifiant est vide ou absent est ignorée. Nécessaire seulement si vous lancez le répartiteur audio. |
| `llm_provider` | string | Fournisseur LLM pour `shamanic_ai.py` et le Livre : `openai` (par défaut), `openrouter` ou `openai_compat`. Chaque fournisseur ne lit que sa propre clé dans `golden_key.env` — voir *Fournisseurs LLM et clés* ci-dessous. |
| `llm_model` | string | Modèle pour ce fournisseur. Vide = le modèle par défaut du fournisseur (`gpt-6.1-sol` / `openai/gpt-6.1-sol`) ; obligatoire pour `openai_compat`. |
| `llm_base_url` | string | Adresse du point de terminaison, lue **uniquement** par `openai_compat` (par ex. `http://localhost:1234/v1`). Ignorée par `openai` et `openrouter`, dont les adresses sont fixes. |
| `kirja_llm_provider` | string | Fournisseur de remplacement optionnel pour le Livre (`ksiega_niedomowien.py draft` / `fill`). Vide = `llm_provider`. |
| `kirja_drafter_model` | string | Modèle pour `draft` (le rédacteur par API du Livre). Vide = le modèle par défaut du fournisseur, ou `llm_model` quand le Livre utilise le fournisseur global. |
| `kirja_filler_model` | string | Modèle pour `fill` (le remplisseur aveugle de trous du Livre). Même repli que `kirja_drafter_model`. |
| `reacts_llm_provider` | string | Remplacement facultatif du fournisseur pour `helsinki_reacts.py`. Vide = `llm_provider`. |
| `reacts_model` | string | Modèle pour `helsinki_reacts.py`. Vide = celui du fournisseur par défaut, ou `llm_model` quand Helsinki Reacts utilise le fournisseur global. |
| `reacts_lang` | string | Langue du live de `helsinki_reacts.py` (un code `ui_lang`). Vide = `ui_lang`. `fi` = le live en finnois ; toute autre = sa traduction avec des interjections finnoises. |

> **Fournisseurs LLM et clés.** Une clé est liée à un seul hôte et n’est jamais envoyée ailleurs : `openai` → `OPENAI_API_KEY` → `api.openai.com` ; `openrouter` → `OPENROUTER_API_KEY` → `openrouter.ai` ; `openai_compat` → `LLM_COMPAT_API_KEY` → `llm_base_url`. Le fournisseur est choisi explicitement et jamais déduit d’une adresse, si bien que diriger un script vers un autre service ne peut ni divulguer la clé du premier service ni casser l’autre script. La clé `kirja_filler_base_url`, antérieure à la v1.7.0 (qui envoyait `OPENAI_API_KEY` à n’importe quelle adresse), est refusée avec un message de migration. Sur OpenRouter, les identifiants de modèle portent un préfixe de l’éditeur (`openai/gpt-4o`, `anthropic/claude-sonnet-5.5`), et les paramètres de confidentialité du compte permettent d’exclure les fournisseurs susceptibles de s’entraîner sur vos prompts.

> **Analyse de sentiment — coût CPU.** Avec `enable_sentiment: true`, la passe par paragraphe est lourde pour le CPU — à peu près comparable à la reconnaissance vocale locale Whisper sur CPU. Sur des machines anciennes ou limitées thermiquement, cette charge prolongée peut réellement éprouver le processeur ; activez-la en connaissance de cause, idéalement sur une machine dotée d’un GPU ou capable de tenir longtemps à pleine charge.

> **`ui_lang` — portée de la localisation.** La sortie console des scripts autonomes (`generate_report.py`, `generate_md.py`, `generate_diagnostic.py`, `shamanic_pipeline.py`, `shamanic_ai.py`, `ksiega_niedomowien.py`, `helsinki_reacts.py`) est localisée via `ui_lang`. La **sortie du notebook ne l’est pas** — elle est figée en russe (seul le nom du fichier de thèses suit la langue du corpus détectée). Le `analysis_report.html` en mode lecture garde la narration russe du notebook (sa racine est `<html lang="ru">`) ; l’artefact destiné à l’utilisateur et entièrement localisé selon `ui_lang` est **`diagnostic_report.html`**, produit par `generate_diagnostic.py`. Les traductions en `fi` / `is` / `it` / `de` / `es` / `fr` sont des ébauches non relues — signalez les maladresses sur GitHub, s’il vous plaît.

> **Chemins Windows et expressions régulières — important.** Le contenu de la configuration est du JSON, et le JSON n’a pas de syntaxe de chaîne brute. Une seule barre oblique inverse échappe le caractère suivant (`\U`, `\d`, `\n` sont spéciaux), donc un chemin Windows écrit `"C:\Users\marek\doc.pdf"` produit une erreur d’analyse JSON. Deux façons de l’écrire correctement :
>
> - **Barres obliques** (le plus simple, fonctionne aussi sous Windows) : `"C:/Users/marek/doc.pdf"`.
> - **Barres obliques inverses doublées** : `"C:\\Users\\marek\\doc.pdf"`.
>
> La même règle vaut pour chaque expression régulière de `custom_patterns` : écrivez `"\\d{4}"`, et non `"\d{4}"` ; écrivez `"Copyright \\d{4}"`, et non `"Copyright \d{4}"`. Il n’existe pas de chaîne brute de la forme `r"…"` en JSON.

## Exécution

Les scripts numérotés ci-dessous sont prévus pour être exécutés **dans l’ordre** : chacun consomme les artefacts produits par l’étape précédente.

### Raccourci : toute la chaîne locale (`run_all.py`)

```bash
# notebook -> generate_report.py -> shamanic_pipeline.py -> analyse pour le Livre (finnois uniquement)
python run_all.py
# réutiliser les sorties déjà enregistrées dans le notebook
python run_all.py --skip-notebook
# diagnostic complet des avertissements des bibliothèques, indépendant de la configuration
python run_all.py --warnings-as-errors
```

Les étapes 1, 2 et 4 ci-dessous, plus le `scan` du Livre du Non-Dit pour un corpus finnois, en une seule commande. Lancez-le avec le Python du `.venv` du dépôt : si le noyau `analyst_env` manque, il est enregistré pour cet interpréteur. La chaîne s’arrête à la première étape en échec ; le code de sortie 3 signifie que la vérification de la source du rapport a refusé (voir l’étape 2). Le notebook fait volontairement taire les avertissements des bibliothèques pour qu’ils n’arrivent pas dans le rapport d’analyse. `--warnings-as-errors` est un mode distinct de diagnostic complet : il ignore `config.json` et fait passer une copie du notebook avec un corpus synthétique par chaque composant (un PDF avec réparation de police et une page numérisée pour l’OCR, chaque format d’entrée et une URL servie par un serveur local, analyse de sentiment, islandais, omorfi). Il enregistre chaque avertissement, y compris ceux émis dans du code qui intercepte les exceptions, et les affiche tous sous le titre de la cellule, dans les termes de la bibliothèque, avec l’endroit où ils ont été émis. Les avertissements connus et inoffensifs (`diagnostyka.ZNANE_OSTRZEZENIA`) reçoivent une ligne à part et ne comptent pas. Le mode nécessite toutes les dépendances optionnelles de `requirements.txt` et le modèle `fi_core_news_lg`, et un composant qui ne se charge pas l’arrête avec un message. Le notebook et `export_results/` ne sont pas touchés, et le rapport et les étapes suivantes ne s’exécutent pas ; code de sortie 4 = nouveaux avertissements, 0 = aucun. L’enregistreur couvre le module `warnings` dans le processus du notebook : les messages passant par `logging` (par exemple ceux de `transformers`) et les avertissements des processus enfants en sont exclus. Quand une bibliothèque remplace l’enregistreur (par exemple `logging.captureWarnings`), le mode se termine avec le code 1 au lieu d’un faux « propre » ; de même pour Ctrl+C, après l’affichage des avertissements recueillis jusque-là. Lancez-le après chaque mise à jour des bibliothèques.

### 1. Notebook (obligatoire)

```bash
jupyter notebook accessible_text_analyst.ipynb
# (Cell → Run All)
# Sans interface (CI) : cellules 0-39 via nbclient, sans la cellule interactive cell_qa_rag
python -c "import nbformat as f; from nbclient import NotebookClient as C; nb=f.read('accessible_text_analyst.ipynb',4); c=C(nb,timeout=None); c.create_kernel_manager(); c.start_new_kernel(); c.start_new_kernel_client(); [c.execute_cell(x,i) for i,x in enumerate(nb.cells[:40])]; f.write(nb,'accessible_text_analyst.ipynb'); c.km.shutdown_kernel(now=True)"
```

C’est un pipeline séquentiel avec un état global partagé. **Ne réordonnez pas les cellules et ne les exécutez pas dans le désordre.** Le notebook écrit `export_results/<project>/sentences.csv`, `paragraphs.csv`, `theses.csv`, `keywords_tfidf.csv`, `paragraphs_with_topics.csv`, `topic_keywords.json`, `entities.csv`, `accessible_text.html`, `accessible_text.docx` et `theses.txt`.

### 2. Rapports HTML (recommandé)

```bash
python generate_report.py
# → export_results/<project>/analysis_report.html
```

`generate_report.py` lit les sorties des cellules directement dans le fichier `.ipynb` ; le rapport HTML doit donc être généré à partir d’un notebook **fraîchement exécuté**. `requirements.txt` inclut `nbstripout` — s’il est activé dans la configuration git locale, les sorties du notebook sont retirées au commit. Générez le rapport _avant_ le commit, ou désactivez nbstripout dans votre flux de travail.

**Vérification de la source.** Avant d’écrire quoi que ce soit, `generate_report.py` vérifie que les sorties du notebook appartiennent au `source_file` de la configuration, et refuse sinon (code de sortie 3, rien n’est écrit). Trois vérifications : le chemin de la source et le dossier d’export affichés par le notebook doivent correspondre à la configuration, et l’exécution enregistrée doit avoir atteint la fin de la cellule d’export ; `paragraphs.csv` et `sentences.csv` ne doivent pas être plus récents que le `.ipynb` (sinon les sorties de la dernière exécution n’ont jamais été enregistrées — typique d’un notebook exécuté dans VS Code sans être enregistré) ; et les débuts de page affichés par le notebook doivent figurer dans le fichier source (comparés comme un flux de lettres, si bien que les coupures de mots recollées, les numéros de page supprimés et les titres courants n’ont pas d’importance). Quand le contenu ne peut pas être comparé — numérisations lues par OCR, images, URL, couche texte PDF altérée —, les deux premières vérifications décident et la console le signale. Le rapport consigne aussi si omorfi a participé à l’exécution (`<meta name="ata-omorfi">`) ; le Livre du Non-Dit le lit.

Pour une vue de **diagnostic** complète et structurée, construite directement à partir des exports CSV/JSON :

```bash
python generate_diagnostic.py
# → export_results/<project>/diagnostic_report.html
```

`generate_diagnostic.py` ne lit que les CSV/JSON exportés ; contrairement à `generate_report.py`, il n’a donc pas besoin d’un notebook fraîchement exécuté, seulement des exports que le notebook a écrits. Le résultat est un document navigable (table des matières, titres, listes) qui couvre les thèmes, les thèses, les entités regroupées par type et les principaux mots-clés.

### 3. Markdown pour Gemini Notebook (optionnel)

```bash
python generate_md.py
# → export_results/<project>/gemini_notebook_report.md
```

Cela convertit le rapport HTML en un fichier Markdown sans les spans d’accessibilité (Gemini Notebook — anciennement NotebookLM — n’exploite pas `<span lang="…">`). Ne le lancez que si vous voulez importer le rapport dans Gemini Notebook.

### 4. Post-processeur chamanique sans LLM (optionnel)

```bash
python shamanic_pipeline.py
# → export_results/<project>/audio_scripts/oracle_script.txt
#                                          /raw_roots_chant.txt
#                                          /prophecies.txt
#                                          /lore_fragments/intercepted_log_T*_P*.txt
#                                          /emotional_undertow.txt   # seulement si sentiment.csv existe
```

Génère des artefacts textuels rituels directement à partir des exports CSV/JSON du notebook — sans appel LLM, sans réseau. Tous les textes proviennent de `shamanic_locale.py` et sont entièrement localisés dans les neuf langues prises en charge. Quand le `sentiment.csv` optionnel est présent, il produit aussi `emotional_undertow.txt` — une « marée des humeurs » par paragraphe et un bilan ; sans lui, ce seul rituel est simplement ignoré.

### 5. Post-processeur chamanique avec LLM (optionnel, nécessite une clé d’API LLM)

```bash
python shamanic_ai.py
# → export_results/<project>/audio_scripts/katla_entity_monologue.txt
#                                          /vieno_echoes_chant.txt
#                                          /lumi_final_report.txt
#                                          /sami_energetic_spark.txt
```

Il faut la clé du fournisseur choisi (`llm_provider`, par défaut `openai`). Créez `golden_key.env` à la racine du projet avec la clé nécessaire :

```
OPENAI_API_KEY=sk-...          # llm_provider : openai (par défaut)
OPENROUTER_API_KEY=sk-or-...   # llm_provider : openrouter
LLM_COMPAT_API_KEY=...         # llm_provider : openai_compat (llm_base_url)
```

`golden_key.env` correspond au motif `*.env` de `.gitignore` et ne sera donc pas commité. Les quatre voix s’exécutent à la suite :

1. **Katla** transmue la liste des entités (`entities.csv`) en un monologue d’esprits gelés du Nord.
2. **Vieno** chante sur la liste des mots-clés et des thèmes. Par défaut, elle tisse cinq phrases brutes du corpus comme des échos d’une autre dimension ; quand le `sentiment.csv` optionnel est présent, elle lit plutôt l’arc émotionnel du texte (les humeurs par paragraphe, condensées pour tenir dans la limite de tokens du modèle sur les corpus longs) et le laisse façonner la dynamique du chant.
3. **Lumi** lit `prophecies.txt` (obligatoire) ainsi que le monologue de Katla et le chant de Vieno (ornement optionnel) et rédige la dépêche finale. Des textes de secours localisés couvrent le cas où Katla ou Vieno manquent.
4. **Sami** lit le rapport de Lumi et livre une synthèse pleine d’énergie, avec l’étincelle de l’espoir ou un appel à l’action.

### 6. Répartiteur audio chamanique (optionnel, nécessite ElevenLabs)

```bash
python shamanic_voice.py
# → export_results/<project>/audio_scripts/katla_entity_monologue.mp3
#                                          /vieno_echoes_chant.mp3
#                                          /lumi_final_report.mp3
#                                          /sami_energetic_spark.mp3
```

Un script autonome à exécution unique qui lit les quatre artefacts narratifs produits par `shamanic_ai.py` et synthétise chacun en `.mp3` via le modèle ElevenLabs `eleven_multilingual_v2` (qui détecte lui-même la langue parlée, si bien qu’aucun paramètre de langue n’est passé). Il consigne chaque réussite ou échec dans la console et se termine — pas de bot, pas de serveur, pas de session interactive. Il lui faut deux choses :

- `ELEVENLABS_API_KEY` dans `golden_key.env` (le même fichier que celui des clés LLM).
- une correspondance `voices` dans `config.json` / `config.ini` qui attribue un identifiant de voix ElevenLabs à chacune de `katla`, `vieno`, `lumi`, `sami`. Une voix dont l’identifiant est vide ou dont l’artefact manque est ignorée (lancez d’abord `shamanic_ai.py`) ; l’échec d’une voix n’interrompt pas les autres.

> **Confidentialité et coût.** Comme `shamanic_ai.py` avec OpenAI, ce script envoie le texte des artefacts à un service tiers (ElevenLabs) pour la synthèse, et ElevenLabs est une API **payante**. Le contenu quitte votre machine — ne le lancez pas sur des contenus que vous ne pouvez pas partager à l’extérieur.

### 7. Le Livre du Non-Dit (optionnel, finnois uniquement, assisté par un agent)

```bash
python ksiega_niedomowien.py scan              # quels dossiers de export_results/ conviennent
python ksiega_niedomowien.py scan --blocks     # plus les blocs faits / ouverts / restants (lent ; automatique avec --folder)
python ksiega_niedomowien.py status            # progression par dossier : entrées, blocs évidents, paquets ouverts
python ksiega_niedomowien.py tidy              # entrées remplacées par une entrée plus récente du même bloc (aperçu ; --apply nettoie)
python ksiega_niedomowien.py prepare --folder <name> --limit 3
#   → export_results/_kirja_tyotila/<id>/packet.json
python ksiega_niedomowien.py draft <id>        # optionnel : brouillon via l’API + seal, jusqu’à 2 nouveaux essais
python ksiega_niedomowien.py seal <id>         # valide draft.json, écrit blind.json
python ksiega_niedomowien.py fill <id>         # optionnel : propositions à l’aveugle via l’API, puis judge
python ksiega_niedomowien.py judge <id>        # → export_results/Sanomattomien_kirja.md
# <id> = l’identifiant de paquet affiché par prepare, le début du nom du dossier ou le chemin du dossier du paquet
```

Un jeu construit sur `raw_roots_chant.txt`. Pour chaque bloc de 3 à 6 racines consécutives, un LLM écrit une entrée de journal brumeuse en finnois, avec des trous dont les réponses sont des passages littéraux du texte source — ils doivent figurer dans les **deux** fichiers `accessible_text.html` et `accessible_text.docx`, les deux versions de la source de vérité. Un modèle aveugle distinct essaie ensuite de remplir les trous à partir de la seule entrée ; chaque trou qu’il devine compte comme évident et son fragment est supprimé. Ce qui reste — KATLA (le système d’alerte) lisant les racines et VIENO (la narratrice chamanique) avec les trous non dits — est ajouté à `export_results/Sanomattomien_kirja.md`. La clé des réponses va dans `Sanomattomien_kirja.avain.json` et l’état dans `Sanomattomien_kirja.tila.json` ; une nouvelle exécution ne duplique jamais d’entrées.

Le script est la moitié déterministe (filtres, blocs, source de vérité, validation, évaluation, le Livre). La moitié créative — écrire `draft.json` — revient soit à un agent qui suit `skills/ksiega-niedomowien/SKILL.md`, soit à un modèle par API via `draft`.

**Filtres d’entrée.** Seuls conviennent les sous-dossiers de `export_results/` qui ont un nom finnois, `<html lang="fi">`, un chant finnois et aucune fuite grammaticale ; tout le reste est refusé avec un motif. La ligne `roots.header` est retirée quand elle est présente. La vérification de *fuite grammaticale* repère les corpus traités avant l’activation d’omorfi (v1.5.0) : sur tout `keywords_tfidf.csv`, elle compte les formes fléchies qui ont survécu à la lemmatisation plus les lemmes aberrants de spaCy, et refuse le dossier au-delà de 1,0 pour 100 termes. Nécessite omorfi (étape 5 de l’installation). Quand le dossier a un `analysis_report.html` à jour, un refus pour fuite grammaticale indique ce que sait le rapport : omorfi a participé à l’exécution (c’est alors peut-être le moteur lui-même — la correction des lemmes finnois dans le notebook — qu’il faut corriger ; signalez les exemples), omorfi manquait (installez-le et relancez le notebook), ou l’exécution n’a eu aucune étape omorfi. Sans rapport à jour, il indique que c’est inconnu.

**Pourquoi le finnois uniquement.** Le jeu vit de ce que la lemmatisation laisse non dit ; il n’a donc de sens que là où ramener un mot à son lemme lui enlève un sens réel. Le finnois est agglutinant : ce que le polonais ou le russe expriment en partie par des prépositions séparées, et l’anglais surtout par l’ordre des mots et les mots-outils, le finnois le met dans le mot lui-même — quinze cas (`talossa` « dans la maison », `talosta` « hors de la maison », `taloon` « dans la maison (mouvement) », `talolle` « vers la maison », `talotta` « sans maison »), des suffixes possessifs (`taloni` « ma maison », `talonsa` « sa maison, leur maison »), des clitiques (`-ko` question, `-kin` « aussi », `-han` insistance) et des formes verbales qui portent à la fois la personne, le temps, le mode et le passif (`tehtäisiinkö` « est-ce que cela serait fait ? »). Le chant réduit tout cela à `TALO` et `TEHDÄ` : qui, où, d’où, vers où, à qui et si — tout disparaît, exactement les trous que l’auditeur doit combler. En polonais et en russe, le lemme perd la désinence, mais une grande partie de la relation se trouve dans un mot séparé (la préposition), si bien que le lemme ne la portait jamais seul ; l’anglais ne perd guère que le nombre et le temps. L’islandais (quatre cas, largement régis par des prépositions) et l’italien (prépositions et articles, peu de flexion nominale) se rapprochent respectivement du modèle polonais/russe et du modèle anglais. Techniquement, l’outil a aussi besoin d’un analyseur de dictionnaire pour prouver qu’un chant est exempt de grammaire et pour rattacher les racines au texte fléchi ; dans ce pipeline, seul le finnois en a un (omorfi), et les seuils ont été calibrés sur de vrais corpus finnois.

**Rédacteur par API (`draft`).** Abaisse le seuil d’entrée : aucun agent n’est nécessaire. Le script envoie le paquet (le chant, les racines et les phrases sources de `truth.sentences`) au fournisseur configuré, écrit `draft.json` et le scelle ; quand `seal` rejette le brouillon, le modèle le reçoit en retour avec les objections concrètes du validateur, jusqu’à 2 nouveaux essais (3 tentatives). Les codes de sortie sont ceux de `seal` (0 scellé, 4 toujours rejeté — corrigez le dernier `draft.json` à la main ou avec la skill). Un `draft.json` existant n’est jamais écrasé sans `--force`. La skill reste le mode le plus puissant : nouveaux essais illimités, l’agent lisant les objections au fil de l’eau. Une règle ne peut être validée de manière déterministe dans aucun des deux modes : *n’attribuez pas à des personnes réelles des faits ou des accusations absents des phrases sources*. Le prompt du rédacteur et la skill l’énoncent tous deux, mais rien ne la vérifie — relisez les entrées qui concernent des personnes réelles avant de les partager.

**Remplisseur aveugle (`fill`).** N’envoie que `blind.json` — jamais les réponses ni la source — au fournisseur configuré, enregistre `guesses.json` et lance aussitôt `judge`. Fournisseur : `kirja_llm_provider` (vide = `llm_provider`) ; modèle : `kirja_filler_model` ; `--provider` / `--model` remplacent les deux. `judge` seul est destiné aux propositions d’un sous-agent aveugle. `draft` comme `fill` demandent d’abord un schéma JSON (sorties structurées) ; quand le point de terminaison le refuse, ils se replient sur le mode JSON simple, puis sur le prompt seul. `fill` refait deux essais quand la réponse est inutilisable ou qu’il y manque un trou. Chaque réponse inutilisable est enregistrée dans le dossier du paquet (`draft_reply_N.txt` / `fill_reply_N.txt`, avec `finish_reason` et l’éventuel refus), et la console indique où.

**Brancher la skill.**

- *Claude Code :* copiez `skills/ksiega-niedomowien/` dans `~/.claude/skills/` (personnel) ou dans `.claude/skills/` de votre copie du dépôt. Ce dépôt met `.claude/` dans .gitignore, c’est pourquoi la skill est livrée dans `skills/`.
- *Applications Claude :* compressez le dossier `ksiega-niedomowien/` en ZIP (le dossier lui-même doit être la racine de l’archive) et ajoutez-le sous **Customize → Skills** ; l’exécution de code doit être activée, et la session doit avoir accès à votre copie du dépôt, car les automates omorfi et `export_results/` se trouvent sur votre disque. Utilisez l’onglet **Code** avec une session **locale** : en mode chat simple ou dans une session cloud, les fichiers que lit l’agent — extraits de la source compris — sont copiés dans un environnement cloud.
- *Autres agents :* `SKILL.md` est une procédure en Markdown simple avec un front matter YAML ; tout agent capable d’exécuter des commandes locales dans le dépôt peut la suivre. S’il ne peut pas lancer un sous-agent indépendant, utilisez `fill` pour l’étape aveugle.
- Un assistant purement conversationnel sans exécution de commandes locales (par ex. un GPT personnalisé) ne peut pas le faire tourner : omorfi et ses ~130 Mo d’automates doivent fonctionner à côté de vos données.

> **Confidentialité et coût.** Trois niveaux, du moins au plus de données : `fill` n’envoie que le texte brumeux de l’entrée (pas la source) ; `draft` envoie des phrases sources littérales (`truth.sentences`) et affiche leur nombre avant l’appel ; un agent qui suit la skill lit des extraits de la source et les envoie à son propre fournisseur de modèles — et, dans une session cloud, travaille sur une copie cloud des fichiers. Tous les appels d’API sont payants. Ne les utilisez que sur des contenus que vous pouvez partager avec ces fournisseurs.

### 8. Helsinki Reacts (optionnel, nécessite une clé d’API LLM)

```bash
python helsinki_reacts.py <project> [<project> …]
# → export_results/_streams/<project>.md
python helsinki_reacts.py notes.txt             # n’importe quel fichier texte convient aussi
python helsinki_reacts.py <project> --dry-run   # montrer ce qui serait envoyé, sans rien envoyer
python helsinki_reacts.py <project> --lang en   # langue du live pour cette exécution
python helsinki_reacts.py <project> --kirja     # joindre l’entrée du dossier dans le Livre du Non-Dit
```

Script satirique d’un live : Valtteri, streamer d’Helsinki, réagit avec son chat à un enregistrement, et Lumi, une voix de synthèse glaciale, lit les dons. L’entrée est le nom d’un dossier de `export_results/` (le texte de son `accessible_text.html`, sans balisage ni titres) ou n’importe quel fichier texte ; le script est écrit dans `export_results/_streams/<nom>.md`, et une nouvelle exécution du même nom ajoute `_2`, `_3`.

**Le prompt vous appartient.** Le prompt système n’est pas dans le code : celui par défaut, `helsinki_reacts.example.md`, est volontairement sobre. Copiez-le en `helsinki_reacts.md` (il est dans `.gitignore` et utilisé automatiquement s’il existe) et changez ce que vous voulez, ou indiquez n’importe quel fichier avec `--prompt`. Une règle de plus ou de moins change beaucoup le live : comparez quelques exécutions avant de retenir une version. Le script n’ajoute lui-même que ce qui doit fonctionner quel que soit le prompt : l’enregistrement, la langue de sortie et — avec `--kirja` — le bloc du Livre du Non-Dit.

**Langue.** `--lang`, puis `reacts_lang` dans le config, puis `ui_lang`. Le finnois donne le live lui-même, en finnois courant ; toute autre langue en donne la traduction, où les courtes interjections finnoises restent non traduites.

**Le Livre du Non-Dit (`--kirja`).** Pour un dossier ayant une entrée dans `Sanomattomien_kirja.md`, le chat reçoit le texte brumeux de l’entrée et les essais manqués du remplisseur aveugle comme théories à débattre. La clé des réponses n’atteint jamais le modèle, et une règle fixe empêche Valtteri de rapprocher une lacune de l’enregistrement, car les lacunes cachent des mots de ce même enregistrement. Sans entrée, le live se fait sans le Livre.

Fournisseur et modèle : `reacts_llm_provider` / `reacts_model` (vides = `llm_provider` / `llm_model`), remplacés par `--provider` / `--model`. Effort de réflexion : `medium` là où la réflexion revient lisible (Claude via OpenRouter), `low` ailleurs ; `--effort low|medium|high` le remplace. Toutes les entrées sont lues avant le premier appel : un fichier vide ou hors UTF-8 arrête donc l’exécution sans frais. Une réponse plus courte que `--min-chars` (1500) est rejetée comme un refus et conservée dans `_streams/<nom>.rejected.md`.

> **Confidentialité et coût.** Tout le texte de chaque enregistrement part vers le fournisseur configuré, une API payante ; le script le signale avant le premier appel. Le résultat est une satire du matériau écrite par une IA : lisez-la avant de la partager, surtout si elle nomme des personnes réelles — rien ne vérifie ce que le modèle leur attribue.

## Sortie

Chaque corpus analysé reçoit son propre sous-répertoire dans `export_results/`, nommé d’après le fichier source (sans chemin ni extension) ou d’après un `domain_slug` pour les URL. Le corpus d’exemple intégré utilise `export_results/_default/`.

Chaque sous-répertoire contient :

| Fichier                         | Produit par | Description                                              |
|---------------------------------|-------------|----------------------------------------------------------|
| `sentences.csv`                 | notebook    | chaque phrase avec son index et sa langue (`lang`)       |
| `paragraphs.csv`                | notebook    | paragraphes (de 3 à 6 phrases chacun)                    |
| `theses.csv`, `theses.txt`      | notebook    | une thèse par paragraphe (la phrase au TF-IDF le plus élevé) ; le nom du fichier `.txt` suit la langue du corpus (par ex. `tezy.txt` pour le polonais, `тезисы.txt` pour le russe, `thèses.txt` pour le français) |
| `keywords_tfidf.csv`            | notebook    | mots-clés (uni/bi/trigrammes) avec leurs poids TF-IDF    |
| `paragraphs_with_topics.csv`    | notebook    | paragraphes avec le thème KMeans attribué                |
| `topic_keywords.json`           | notebook    | mots-clés par thème                                      |
| `entities.csv`                  | notebook    | toutes les entités nommées et leurs étiquettes           |
| `language_spans.csv`            | notebook    | segments en langue étrangère : document, positions des caractères, langue, `block` ou `inline`, texte |
| `sentiment.csv`                 | notebook *(optionnel)* | sentiment par paragraphe (`para_id`, `label`, `score`, `lang`) — seulement quand `enable_sentiment` vaut `true` ; alimente la couche chamanique, jamais montré à l’utilisateur |
| `accessible_text.html`          | notebook    | `lang` sur chaque paragraphe plus `<span lang>` sur chaque phrase étrangère et chaque segment étranger inséré (citation, nom) — les lecteurs d’écran changent de voix automatiquement à chaque fragment |
| `accessible_text.docx`          | notebook    | le même contenu avec `<w:lang>` défini pour chaque `Run` (`pl-PL`, `ru-RU`, `en-US`, `it-IT`, `fi-FI`, `is-IS`, `de-DE`, `es-ES`, `fr-FR`) — Word et SAPI l’utilisent hors ligne, sans détecteur en ligne |
| `analysis_report.html`           | `generate_report.py` | rapport HTML global accessible                 |
| `diagnostic_report.html`         | `generate_diagnostic.py` | rapport de diagnostic structuré (thèmes, thèses, entités par type, mots-clés) à partir des exports CSV/JSON |
| `gemini_notebook_report.md` | `generate_md.py`     | Markdown prêt pour Gemini Notebook (anciennement NotebookLM) |
| `audio_scripts/*.txt`           | `shamanic_pipeline.py`, `shamanic_ai.py` | artefacts textuels rituels / narratifs |
| `audio_scripts/*.mp3`           | `shamanic_voice.py` *(optionnel)* | les quatre voix narratives synthétisées en audio via ElevenLabs |

## Accessibilité

C’est la valeur centrale du projet. Tout ce qui suit est intentionnel et doit être préservé lors de toute modification du pipeline :

- **Pas de couleurs ANSI, d’emoji ni de pseudographie dans la sortie.** Un lecteur d’écran lit chaque caractère littéralement — `[OK]` au lieu de « 🟢 », `---` au lieu de « ───━━━ ».
- **Barres de progression réduites au silence** (`tqdm`, `transformers`, `torch`) — `cell_model._silence_hf_progress()` fait taire les barres de chargement et les avertissements de Hugging Face/torch avant de récupérer IceBERT et icelandic-ner-bert pour l’islandais ; `cell_corpus._silence_ocr_progress()` fait de même pour les moteurs OCR.
- **Balisage `lang` par paragraphe, par phrase et par segment dans l’export.** `accessible_text.html` et `accessible_text.docx` portent un code ISO 639-1 sur chaque paragraphe, sur chaque phrase étrangère et sur chaque segment étranger inséré (une citation ou un nom à l’intérieur d’une phrase). NVDA, JAWS, Narrateur, VoiceOver, Word et SAPI respectent tous ces balises et changent de voix automatiquement — même hors ligne.
- **Balisage anglais figé dans le rapport HTML.** `generate_report.py` entoure toujours les fragments techniques en anglais — étiquettes POS (`NOUN`, `VERB`, `ADJ`), étiquettes NER (`PER`, `ORG`, `[orgName]`), identifiants de modèles spaCy / Hugging Face, noms de fichiers ASCII, blocs de code — de `<span lang="en">`, afin qu’ils ne soient plus prononcés avec la voix russe par défaut du document.
- **Balisage par fragment du corpus étranger dans le HTML.** Quand le corpus n’est pas russe, les sorties structurées (extraits de phrases, listes de mots-clés, mots des thèmes, lignes de classement RAG, tableaux de lemmatisation) sont entourées de `<span lang="target_lang">`.
- **Structure HTML linéaire** (`<main>`, hiérarchie correcte des titres).

### Lire la sortie sans parler russe

La narration du notebook et la sortie `print()` de la plupart des cellules sont rédigées en russe. Deux caractéristiques de l’interface Jupyter rendent cela hostile aux utilisateurs de lecteurs d’écran qui ne parlent pas russe, et le pipeline fournit des solutions précises pour chacune :

- **Jupyter dans un navigateur fige `lang="en"` sur le document**, et la question « Traduire cette page ? » ne s’affiche de toute façon jamais sur les pages `localhost`. Un notebook narré en russe est donc annoncé avec une voix TTS anglaise — le chaos total. La parade pragmatique est l’**extension Jupyter de VS Code** : sa vue en liste n’annonce que les libellés `code cell` / `markdown cell` sans balisage ISO, vous pouvez parcourir les cellules de code avec Entrée et passer les cellules markdown avec ↓ sans écouter leur contenu, et le problème de l’anglais figé se limite à la vue de sortie (`Ctrl+Shift+↓`) — dans laquelle vous pouvez choisir de ne pas entrer.
- **`generate_report.py` est en pratique obligatoire pour qui ne lit pas le russe.** Il produit `analysis_report.html` avec `<html lang="ru">` et l’ensemble complet des balises `<span lang="…">` par fragment. Ouvert dans un vrai navigateur (et non depuis Jupyter), il déclenche la question « Traduire cette page ? » pour la narration russe tout en changeant la voix TTS à chaque fragment pour le contenu du corpus et pour les termes techniques anglais (POS, NER, noms de modèles).
- **Les questions interactives écrivent `qa_results.html` et l’ouvrent pour vous.** `cell_qa_rag` affiche toujours la requête et les 3 meilleures correspondances sur stdout — mais il écrit aussi le même contenu dans `export_results/<project>/qa_results.html` et appelle `webbrowser.open()` pour que la page s’ouvre dans le navigateur du système, où la traduction et le changement de voix par fragment fonctionnent tous deux. La vue de sortie de Jupyter, où le `lang="en"` figé rend les enveloppes russes illisibles pour un lecteur d’écran, n’est donc plus le seul chemin vers le résultat. Chaque nouvelle requête écrase le fichier.

## Limites connues

- **L’origine des emprunts n’est pas balisée.** Le balisage linguistique (les attributs `lang`, voir *La langue de chaque mot*) couvre les mots que connaît le dictionnaire d’une autre langue listée et les fragments écrits dans une écriture étrangère : lettres grecques, latin au sein d’un texte cyrillique. Une marque d’origine explicite (`греч.`, `łac.`, `z niemieckiego`, `имеет греческое происхождение`) n’est pas reliée au mot emprunté, et un mot translittéré dans l’écriture du texte (`фразис` dans un texte russe) garde la langue du corpus. Ces marques n’ont pas de forme fixe (abréviation, adjectif, une expression entière), et baliser comme grec un `фразис` cyrillique ferait passer le lecteur d’écran à une voix grecque, ce qui est pire que le russe par défaut.
- **Finnois : le premier mot de la phrase.** En début de phrase, chaque mot prend une majuscule, et l’étiqueteur spaCy prend parfois un impératif ou une interjection pour un nom propre : `Anna kuulua.` (« qu’on l’entende ») devient le nom *Anna*, `Oota, miten…` (« attends, comment… ») le nom *Oota*. La correction omorfi ne remplace jamais un mot étiqueté comme nom, sans quoi de vrais noms deviendraient des mots communs (*Tuskia* → *tuska*, « angoisse »). Un tel mot garde sa forme écrite comme lemme et peut apparaître dans les listes de lemmes, les mots-clés et le chant des racines (`anna`, `oota`). Quand l’étiqueteur y voit plutôt une interjection, omorfi fournit le verbe (*Oota* → `oottaa`, depuis la v1.11.1). La vérification de fuite grammaticale du Livre du Non-Dit ne compte pas un mot-clé que la source emploie aussi comme nom en milieu de phrase (*Anna Maria …*).
- **Noms écrits sans leurs signes diacritiques.** Un nom étranger n'est balisé que si sa graphie elle-même apporte la preuve : des lettres que l'alphabet de base n'a pas (`Kaczyński`), une forme que seul le lexique d'une autre langue listée connaît, ou une autre écriture (`Качиньский` est balisé en russe). Beaucoup de rédactions retirent les diacritiques des noms étrangers. Dans des titres RSS recueillis le 15 novembre 2026 (Google News par pays et les flux propres des portails), les médias finlandais ont écrit *Swiatek* dans 8 titres sur 8 et *Kaczynski* dans 2 sur 3, alors que *Wałęsa* a gardé ses lettres dans 6 sur 7 ; dans les titres français, italiens, espagnols et suédois, la forme sans signes l'emportait pour au moins deux de ces trois noms, tandis que les médias allemands et anglais gardaient le plus souvent les lettres et que les médias russes translittèrent en cyrillique. Un nom sans signes, formes fléchies comprises (*Kaczynskin*), ne contient que des lettres de l'alphabet de base et ne figure sous cette forme dans aucun lexique : il reste donc dans la langue de base et c'est la voix de base qui le lit, quoi que liste `corpus_languages`. Le texte seul ne permet pas de trancher, et ATA ne devine pas les lettres retirées : comparer chaque mot inconnu fait de lettres de base à des lexiques étrangers privés de leurs diacritiques ferait aussi changer de voix sur des mots ordinaires. Un nom d'une langue qui n'a pas de pack ici (*Erdoğan*) reste lui aussi dans la langue de base.

## Organisation du dépôt

```
accessible_text_analyst/
├── accessible_text_analyst.ipynb   # pipeline principal (42 cellules)
├── generate_report.py              # générateur du rapport HTML (vue lecture)
├── generate_diagnostic.py          # rapport HTML de diagnostic à partir des exports CSV/JSON
├── generate_md.py                  # convertisseur Markdown pour Gemini Notebook
├── shamanic_pipeline.py            # optionnel : post-processeur rituel sans LLM
├── shamanic_ai.py                  # optionnel : narratrices rituelles pilotées par LLM
├── llm_klient.py                   # choix du fournisseur LLM et de la clé (partagé)
├── shamanic_voice.py               # optionnel : répartiteur audio ElevenLabs (exécution unique)
├── shamanic_locale.py              # paquet de localisation de la couche chamanique
├── ksiega_niedomowien.py           # optionnel : le Livre du Non-Dit (finnois uniquement)
├── helsinki_reacts.py              # optionnel : scripts de live Helsinki Reacts (LLM)
├── helsinki_reacts.example.md      # prompt par défaut de Helsinki Reacts (versionné)
├── helsinki_reacts.md              # votre copie de ce prompt (dans .gitignore)
├── skills/ksiega-niedomowien/SKILL.md  # skill d’agent pour ksiega_niedomowien.py
├── config.example.json             # modèle de configuration, extension JSON (versionné)
├── config.example.ini              # modèle de configuration, extension INI (versionné)
├── config.json / config.ini        # votre configuration locale (dans .gitignore)
├── golden_key.env                  # clés LLM et ElevenLabs (dans .gitignore)
├── requirements.txt                # dépendances pip
├── CLAUDE.md                       # guide pour Claude Code
├── README.md                       # la version de référence (anglais)
├── README_pl.md, README_ru.md, …   # traductions (lien de retour en haut)
├── VERSION                         # cycle de version en préparation (`X.Y.Z-WIP` jusqu’à la publication)
├── release_notes.md                # notes de version dans l’ordre chronologique inverse
└── export_results/                 # sorties de l’analyse (dans .gitignore)
    ├── Sanomattomien_kirja.md      # le Livre du Non-Dit, complété au fil de l’eau
    ├── _streams/                   # scripts Helsinki Reacts
    └── <project_name>/
        ├── sentences.csv
        ├── paragraphs.csv
        ├── theses.csv
        ├── theses.txt              # le nom suit la langue du corpus
        ├── accessible_text.html
        ├── accessible_text.docx
        ├── analysis_report.html
        ├── diagnostic_report.html
        ├── gemini_notebook_report.md
        └── audio_scripts/…
```

## Licence

Publié sous la [MIT License](LICENSE). Le pipeline est distribué uniquement sous forme de code source — sans binaires —, et le notebook est, par nature, modifiable cellule par cellule dans le navigateur ou dans l’extension Jupyter de VS Code. La licence MIT ne fait qu’expliciter ce que le format implique déjà.
