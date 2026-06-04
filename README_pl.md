# Accessible Text Analyst

Wielojęzyczny potok NLP zaprojektowany z myślą o **dostępności dla czytników ekranu** (NVDA, JAWS, VoiceOver, Narrator). Cały kod, wyjścia konsolowe i raporty są przygotowane tak, aby technologia asystująca odczytywała je czysto: bez kolorów ANSI, bez emoji, bez pasków postępu i bez pseudografiki.

> **Inne języki:** [English](README.md) · [русский](README_ru.md) · [suomi](README_fi.md) · [íslenska](README_is.md) · [italiano](README_it.md)

> **Status i18n (v1.0).** Przetłumaczone jest tylko README. Narracja w notebooku, całe wyjście konsolowe, `CLAUDE.md` i komentarze w kodzie pozostają w językach oryginalnych (głównie rosyjski, w patchach i warstwie szamańskiej — polski). Tłumaczenie reszty jest świadomie odłożone na v1.1 — szczegóły w `release_notes.md`.

## Zawartość projektu

- `accessible_text_analyst.ipynb` — notatnik Jupyter z kompletnym potokiem analizy (42 komórki: 21 kodu + 21 markdown; narracja w środku notatnika jest po rosyjsku). Zapisuje dwa artefakty dostępnościowe (`accessible_text.html`, `accessible_text.docx`), w których każdy akapit i każde zdanie obcojęzyczne ma własny atrybut `lang` — czytniki ekranu i syntezatory TTS przełączają głos automatycznie, nawet offline.
- `generate_report.py` — skrypt post-procesujący, który zamienia wykonany notatnik w jeden dostępny plik HTML (`analysis_report.html`). Fragmenty obcojęzyczne owija w `<span lang="target_lang">`, a — niezależnie od języka korpusu — twardo oznacza `<span lang="en">` przy treściach technicznie angielskich (tagi POS, etykiety NER, identyfikatory modeli spaCy/Hugging Face, ścieżki ASCII). Kod inline i bloki kodu w narracji dostają hurtem `lang="en"`. W trybie czytelnika (`remove_noise: true`) skraca diagnostyczne pętle „per dokument" do pierwszych kilku dokumentów, zamiast wypisywać setki.
- `generate_diagnostic.py` — niezależny generator pełnego raportu **diagnostycznego** (`diagnostic_report.html`) budowanego wprost z eksportów CSV/JSON notatnika (nie z wyjścia `generate_report.py`). Nawigowalna, dostępna dla czytników ekranu struktura: spis treści `<nav>` plus sekcje — każda z własnym nagłówkiem i listami — dla przeglądu, tematów z akapitami, tez, nazwanych encji wg typu i najważniejszych słów kluczowych. Etykiety strukturalne podążają za `ui_lang`; fragmenty korpusu dostają `<span lang="…">`, etykiety NER — `<span lang="en">`.
- `generate_md.py` — konwertuje `analysis_report.html` na `notebooklm_report.md` do NotebookLM. Spany dostępnościowe są rozpakowywane, bo NotebookLM ich nie konsumuje.
- `shamanic_pipeline.py` *(opcjonalny)* — post-procesor bez LLM, który zamienia eksportowane przez notatnik pliki CSV/JSON w rytualne artefakty tekstowe (`oracle_script.txt`, `lore_fragments/`, `raw_roots_chant.txt`, `prophecies.txt`, a — gdy włączona jest opcjonalna analiza sentymentu — także `emotional_undertow.txt`), w pełni zlokalizowane we wszystkich sześciu wspieranych językach.
- `shamanic_ai.py` *(opcjonalny, oparty na LLM)* — wywołuje OpenAI, by wygenerować cztery głosy narracyjne (`Katla`, `Vieno`, `Lumi`, `Sami`) na tych samych eksportach. Gdy obecny jest opcjonalny `sentiment.csv`, Vieno buduje swoją pieśń na łuku emocjonalnym tekstu zamiast na surowych zdaniach. Wymaga `OPENAI_API_KEY` w pliku `golden_key.env`.
- `shamanic_voice.py` *(opcjonalny, wymaga ElevenLabs)* — samodzielny skrypt jednorazowy, który syntetyzuje cztery artefakty narracyjne wytworzone przez `shamanic_ai.py` do plików audio `.mp3` przez API ElevenLabs, loguje każdy sukces/błąd do konsoli i kończy działanie (bez bota, bez serwera). Wymaga `ELEVENLABS_API_KEY` w `golden_key.env` oraz mapowania `voices` w konfiguracji.
- `shamanic_locale.py` — pakiet lokalizacyjny dla obu skryptów szamańskich (szablony, nagłówki i fallbacki Lumi we wszystkich sześciu językach).

## Co robi potok

1. Wczytuje tekst z pliku (`.pdf`, `.txt`, `.docx`, `.html` lub obrazów: `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`, `.webp`) lub z URL — usuwając powtarzające się nagłówki/stopki, panele boczne, sekcje „Powiązane artykuły” i podobne szablony. Skanowane PDF-y i obrazy są obsługiwane przez OCR (`pypdfium2` + `easyocr`).
2. Wykrywa język korpusu przez [`lingua-language-detector`](https://github.com/pemistahl/lingua-py). Dominujący język steruje potokiem spaCy; ten sam detektor jest używany ponownie per akapit i per zdanie do eksportu z tagami językowymi.
3. Ładuje modele spaCy **dwuetapowo**. Najpierw model dominującego języka przetwarza cały korpus od początku do końca (tokenizacja → stop-słowa → lematyzacja → POS → NER). Następnie `cell_multilang_pass` powtarza per-językowe przebiegi NLP tylko dla akapitów, których wykryty język różni się od dominującego — ładując każdy niedominujący model na żądanie przez `get_nlp()` opakowane w `functools.lru_cache(maxsize=2)`. Cache LRU ma znaczenie dopiero na tym drugim etapie; w żadnym momencie nie ma w RAM więcej niż dwóch modeli.
4. Tokenizacja → filtrowanie stop-słów → lematyzacja → tagowanie POS → NER (dwuetapowy wielojęzyczny NER z per-zdaniowym dispatcherem modeli).
5. Reprezentacje wektorowe: Bag of Words, TF-IDF + wyszukiwanie auto-zapytaniem z rankingiem kosinusowym.
6. Struktura: zdania → akapity (po 3–6 zdań) → tezy (najlepsze zdanie na akapit). Każdy akapit i każde zdanie dostaje wykryty kod ISO 639-1.
7. Modelowanie tematów przez KMeans na wektorach akapitowych spaCy.
8. *(Opcjonalnie, domyślnie wyłączone)* Per-akapitowa ocena sentymentu modelem `cardiffnlp/twitter-xlm-roberta-base-sentiment`, zapisywana do `sentiment.csv`. Wynik nigdy nie jest pokazywany użytkownikowi — istnieje wyłącznie jako pożywka dla warstwy szamańskiej. Zobacz **Konfiguracja** (`enable_sentiment`).
9. Eksport CSV/JSON + tekstowy raport podsumowujący + dostępny HTML i DOCX + globalny raport HTML (`analysis_report.html`).

## Wspierane języki

| Kod  | Język      | Model spaCy            | NER / wektory  |
|------|------------|------------------------|----------------|
| pl   | polski     | `pl_core_news_lg`      | spaCy          |
| ru   | rosyjski   | `ru_core_news_lg`      | spaCy          |
| en   | angielski  | `en_core_web_lg`       | spaCy          |
| it   | włoski     | `it_core_news_lg`      | spaCy          |
| fi   | fiński     | `fi_core_news_lg`      | spaCy          |
| is   | islandzki  | `spacy.blank("is")` + Hugging Face | `mideind/IceBERT-base` (wektory), `mideind/icelandic-ner-MIM-GOLD-22` (NER) |

Dla islandzkiego nie ma pełnego modelu spaCy, więc do pustego potoku wpięte są dwa modele Hugging Face. Pierwsze pobranie zajmuje ~700 MB na dysku i wymaga połączenia z Internetem; kolejne uruchomienia korzystają z cache HF.

## Detekcja języka

Detekcja działa na trzech poziomach:

1. **Dominujący w korpusie** — `cell_langdet` głosuje per dokument i wybiera dominujący język jako `LANG`. Steruje potokiem spaCy.
2. **Per akapit** (`para_langs`) — używany jako atrybut `<p lang="...">` w `accessible_text.html` i jako domyślny `<w:lang>` dla każdego akapitu w `accessible_text.docx`.
3. **Per zdanie** (`sent_langs`) — używany do owijania pojedynczych zdań w `<span lang="...">` w akapitach mieszanych językowo (HTML) lub do ustawiania `<w:lang>` na per-zdaniowych runach (DOCX).

Wykrywanie per akapit i per zdanie używa świadomie **konserwatywnego wrappera `_safe_detect()`** w `cell_para`. Zaufanie surowemu wyjściu lingua skutkuje słyszalnymi artefaktami: lingua myli krótkie łacińskie fragmenty zdominowane przez nazwy własne („Igor de Lendorf” → it, „Mut se mies, Igor” → en), a czytnik ekranu przełączający się na głos angielski dla „Igor de Lendorf” i z powrotem na fiński dla kolejnego zdania brzmi gorzej, niż gdyby przeczytał tę nazwę z fińskim akcentem.

Wrapper stosuje kolejno następujące reguły:

1. **Cyrylica w jakimkolwiek miejscu fragmentu → `ru`.** Jednoznaczne; działa nawet dla 3-znakowych fragmentów.
2. **Fragment krótszy niż 30 znaków → fallback `LANG`.** Lingua jest niepewna dla krótkich łacińskich fragmentów.
3. **Fragment zawiera diakrytyki języka `LANG`** (np. `ä`/`ö` dla `fi`, `ąęć` dla `pl`) → fallback `LANG`. Fińskie zdanie z angielskim cytatem to dalej fińskie zdanie.
4. **Lingua zgadza się z `LANG`** → akceptujemy.
5. **Lingua się nie zgadza, ale wykryty język ma WŁASNE charakterystyczne diakrytyki we fragmencie** (`à` dla it, `ż` dla pl, `ð` dla is) → ufamy lingui.
6. **Lingua się nie zgadza, a wykryty język nie ma charakterystycznych diakrytyk we fragmencie** (typowo `en`) → fallback `LANG`.

Motywacja reguły 6 jest czysto fonetyczna: angielski głos czytający fragmenty fińskie/polskie/włoskie produkuje wyraźną dystorsję („bełkot fonemów”), podczas gdy głos fiński/polski/włoski czytający angielski cytat z lekkim akcentem jest zrozumiały i nieuciążliwy. Kompromisem jest to, że czysto angielskie zdania zaszyte w korpusie nieangielskim są czytane głosem dominującym zamiast być przełączone na angielski. Akceptujemy ten kompromis, bo w praktyce użytkownicy czytników ekranu zgłaszają asymetryczny koszt jakości.

Outliery, które przetrwały heurystykę, są wypisywane w wyjściu `cell_para` do ręcznego przeglądu (`Оставшиеся outlier-предложения...`). Ta sama logika diakrytyk rządzi heurystyką per-`<code>` (`_classify_code_lang`) w `generate_report.py` i per-segmentowym fallbackiem lingua (`_lingua_word_fallback`) dla identyfikatorów ASCII przypominających ścieżki.

## Wymagania

- Python 3.10 lub nowszy.
- ~1,5 GB wolnego miejsca na dysku na modele `_lg` spaCy (po jednym na język). Dodaj ~700 MB, jeśli włączasz wsparcie dla islandzkiego (Hugging Face `transformers` + `torch` + IceBERT + MIM-GOLD-22).
- Dodaj ~700 MB, jeśli włączasz wsparcie OCR (`easyocr` pobiera `torch` oraz własne modele detekcji i rozpoznawania przy pierwszym wywołaniu OCR). Jeśli włączyłeś też islandzki, koszt `torch` jest dzielony między oba.
- Połączenie z Internetem przy pierwszym uruchomieniu (pobieranie modeli).

## Konfiguracja środowiska

Wybierz jedną z trzech opcji poniżej. Wszystkie kończą się tym samym `pip install -r requirements.txt` i pobraniem modeli spaCy.

### Opcja A — lokalny `venv` (zalecana do codziennego użytku)

```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Katalog `.venv/` jest w `.gitignore`. Z poziomu aktywnego venv przejdź do sekcji **Instalacja**.

### Opcja B — Anaconda / Miniconda

```bash
conda create -n accessible-text-analyst python=3.11
conda activate accessible-text-analyst
```

Następnie przejdź do **Instalacji**. `pip` dołączony do Anacondy działa bez problemu — projekt nie ma osobnej listy pakietów Conda.

### Opcja C — Google Colab (bez instalacji lokalnej)

Otwórz nowy notatnik w Colab i wklej do pierwszej komórki:

```python
!git clone https://github.com/<your-fork>/accessible_text_analyst.git
%cd accessible_text_analyst
!pip install -r requirements.txt
!python -m spacy download en_core_web_lg
# Dodaj linie poniżej tylko dla języków, których faktycznie potrzebujesz:
# !python -m spacy download pl_core_news_lg
# !python -m spacy download ru_core_news_lg
# !python -m spacy download it_core_news_lg
# !python -m spacy download fi_core_news_lg
```

Następnie wgraj `config.json` (lub `config.ini`) przez panel Files, ustaw `source_file` i uruchom notatnik. Uwaga: sesje Colab są ulotne — pobrane modele i artefakty `export_results/` znikają, gdy runtime się skończy. Do dłuższej pracy zamontuj Google Drive i zapisuj wyjście tam.

## Instalacja

```bash
# 1. Zależności Pythona
pip install -r requirements.txt

# 2. Modele spaCy — pobierz tylko te języki, których naprawdę potrzebujesz.
# Warianty *_lg są wymagane, bo modelowanie tematów potrzebuje wektorów słów.
python -m spacy download pl_core_news_lg
python -m spacy download ru_core_news_lg
python -m spacy download en_core_web_lg
python -m spacy download it_core_news_lg
python -m spacy download fi_core_news_lg

# 3. (Opcjonalnie) Wsparcie dla islandzkiego — odkomentuj `transformers` i
# `torch` w requirements.txt i ponownie uruchom `pip install -r requirements.txt`.
# IceBERT i MIM-GOLD-22 są wtedy pobierane z Hugging Face przy pierwszym uruchomieniu.

# 4. (Opcjonalnie) Analiza sentymentu — odkomentuj `transformers`, `torch`,
# `sentencepiece`, `protobuf` i `tiktoken` w requirements.txt, ponownie uruchom
# instalację i ustaw "enable_sentiment": true w config.json. Model
# (~1,1 GB) jest pobierany z Hugging Face przy pierwszym uruchomieniu i potem cache'owany.
# Wszystkie pięć pakietów jest potrzebnych razem do zbudowania tokenizatora XLM-RoBERTa.
```

## Konfiguracja

Skopiuj przykładowy plik konfiguracyjny do lokalnej kopii. Akceptowane są zarówno `config.json`, jak i `config.ini` — **zawartość jest w obu przypadkach JSON-em**; rozszerzenie `.ini` jest czysto ergonomicznym ustępstwem wobec nietechnicznych użytkowników Windows, dla których `.json` nie ma żadnego skojarzonego programu.

```bash
# Wybierz jedno:
cp config.example.json config.json
cp config.example.ini  config.ini
```

`config.json` i `config.ini` oba są w `.gitignore`, więc każdy użytkownik trzyma własną lokalną kopię.

Zawartość:

```json
{
  "source_file": "C:/path/to/document.pdf",
  "custom_patterns": [],
  "remove_noise": true,
  "ocr_languages": ["en"],
  "enable_sentiment": false,
  "ui_lang": "",
  "lumi_katla_lines": null,
  "lumi_vieno_lines": null,
  "voices": {
    "katla": "",
    "vieno": "",
    "lumi": "",
    "sami": ""
  }
}
```

| Klucz              | Typ              | Cel |
|--------------------|------------------|-----|
| `source_file`      | string           | Ścieżka do pliku (`.pdf`, `.txt`, `.docx`, `.html` lub obraz) **albo** URL (`http://`, `https://`). Pusty string lub brak pliku → wbudowany przykładowy korpus. |
| `custom_patterns`  | string[]         | Opcjonalna lista wyrażeń regularnych usuwanych z surowego tekstu (żywe nagłówki, stopki, powtarzające się szablony). Przykład: `["Editorial: .*", "Copyright \\d{4}"]`. |
| `remove_noise`     | boolean          | Przełącza `generate_report.py` między trybem czytelnika (`true`, ukrywa paski ładowania Hugging Face/torch i tabele lematyzacji/POS) a pełnym trybem diagnostycznym (`false`). |
| `ocr_languages`    | string[]         | Języki dla `easyocr` (używane tylko przy skanowanych PDF-ach lub źródłach-obrazach). W ramach jednej instancji `easyocr.Reader` można łączyć tylko języki tego samego skryptu — np. `["ru", "en"]` dla cyrylicy lub `["en", "pl", "it", "fi", "is"]` dla łaciny. |
| `enable_sentiment` | boolean          | Włącza opcjonalną per-akapitową analizę sentymentu (domyślnie `false`). Wymaga zakomentowanych zależności sentymentu (zobacz Instalacja krok 4). Zapisuje `sentiment.csv`; wynik nigdy nie jest pokazywany użytkownikowi, służy wyłącznie jako pożywka dla warstwy szamańskiej (rytuał `emotional_undertow.txt` i pieśń Vieno). Przy jakimkolwiek błędzie ładowania jest po cichu pomijana — bez fallbacku. |
| `ui_lang`          | string           | Język UI dla wyjścia konsoli i atrybutu `<html lang>` generowanego raportu (`pl` / `en` / `ru` / `fi` / `is` / `it`). Pusty string lub nieznany kod → fallback `en`. Niezależny od języka analizowanego korpusu — ten wykrywany jest automatycznie. |
| `lumi_katla_lines` | integer lub null | Opcjonalny limit ornamentu dla raportu Lumi z `shamanic_ai.py`: ile niepustych linii monologu Katli widzi Lumi. `null` lub brak klucza = cała treść; integer N > 0 = pierwsze N linii. |
| `lumi_vieno_lines` | integer lub null | To samo co `lumi_katla_lines`, dla pieśni ech Vieno. |
| `voices`           | obiekt          | Mapuje każdy głos szamański (`katla` / `vieno` / `lumi` / `sami`) na identyfikator głosu ElevenLabs, używany przez `shamanic_voice.py`. Głos z pustym lub brakującym ID jest pomijany. Potrzebne tylko, jeśli uruchamiasz dyspozytor audio. |

> **Analiza sentymentu — koszt CPU.** Przy `enable_sentiment: true` przebieg per akapit jest obliczeniowo kosztowny na CPU — z grubsza porównywalny z uruchomieniem lokalnego Whisper (mowa na tekst) na CPU. Na starszych lub ograniczonych termicznie maszynach to utrzymujące się obciążenie może być realnym obciążeniem dla procesora; włączaj je świadomie, najlepiej na maszynie z GPU lub z zapasem mocy na długotrwałą pracę pod pełnym obciążeniem.

> **`ui_lang` — zakres lokalizacji.** Wyjście konsolowe samodzielnych skryptów (`generate_report.py`, `generate_md.py`, `generate_diagnostic.py`, `shamanic_pipeline.py`, `shamanic_ai.py`) jest lokalizowane przez `ui_lang`. Wyjście stdout **notatnika nie jest** lokalizowane — jest zahardkodowane po rosyjsku (tylko nazwa pliku z tezami podąża za wykrytym językiem korpusu). Raport w trybie czytnika `analysis_report.html` zachowuje rosyjską narrację notatnika (jego korzeniem jest `<html lang="ru">`); w pełni zlokalizowanym przez `ui_lang`, skierowanym do użytkownika artefaktem jest **`diagnostic_report.html`** produkowany przez `generate_diagnostic.py`. Tłumaczenia w `fi` / `is` / `it` są w wersji draft i nie zweryfikowane — zgłaszaj nieścisłości na GitHubie.

> **Ścieżki Windows i regexy — ważne.** Treść configu jest JSON-em, a JSON nie ma składni raw-string. Pojedynczy backslash escapeuje kolejny znak (`\U`, `\d`, `\n` są specjalne), więc ścieżka windowsowa zapisana jako `"C:\Users\marek\doc.pdf"` da błąd parsowania JSON. Są dwa poprawne sposoby:
>
> - **Forward slashe** (najprostsze, działają też na Windows): `"C:/Users/marek/doc.pdf"`.
> - **Podwójne backslashe**: `"C:\\Users\\marek\\doc.pdf"`.
>
> Ta sama reguła obowiązuje dla każdego wyrażenia regularnego w `custom_patterns`: pisz `"\\d{4}"`, nie `"\d{4}"`; pisz `"Copyright \\d{4}"`, nie `"Copyright \d{4}"`. W JSON nie ma składni `r"…"` dla raw-stringów.

## Uruchamianie

Skrypty numerowane poniżej są uruchamiane **po kolei**: każdy konsumuje artefakty wyprodukowane przez poprzedni.

### 1. Notatnik (obowiązkowy)

```bash
jupyter notebook accessible_text_analyst.ipynb
# (Cell → Run All)
```

To jest sekwencyjny potok ze współdzielonym stanem globalnym. **Nie zmieniaj kolejności komórek i nie uruchamiaj ich poza kolejnością.** Notatnik zapisuje `export_results/<project>/sentences.csv`, `paragraphs.csv`, `theses.csv`, `keywords_tfidf.csv`, `paragraphs_with_topics.csv`, `topic_keywords.json`, `entities.csv`, `accessible_text.html`, `accessible_text.docx` i `theses.txt`.

### 2. Raporty HTML (zalecane)

```bash
python generate_report.py
# → export_results/<project>/analysis_report.html
```

`generate_report.py` czyta wyjścia komórek bezpośrednio z pliku `.ipynb`, więc raport HTML musi być generowany ze **świeżo wykonanego** notatnika. `requirements.txt` listuje `nbstripout` — jeśli został aktywowany w lokalnej konfiguracji git, wyjścia notatnika są usuwane przy commicie. Generuj raport _przed_ commitem albo wyłącz nbstripout dla swojego workflow.

Dla ustrukturyzowanego, pełnego widoku **diagnostycznego** budowanego wprost z eksportów CSV/JSON:

```bash
python generate_diagnostic.py
# → export_results/<project>/diagnostic_report.html
```

`generate_diagnostic.py` czyta wyłącznie wyeksportowane CSV/JSON, więc — w odróżnieniu od `generate_report.py` — nie potrzebuje świeżo wykonanego notatnika, a jedynie eksportów, które notatnik zapisał. Wynik to nawigowalny dokument (spis treści, nagłówki, listy) obejmujący tematy, tezy, encje wg typu i najważniejsze słowa kluczowe.

### 3. Markdown dla NotebookLM (opcjonalnie)

```bash
python generate_md.py
# → export_results/<project>/notebooklm_report.md
```

Konwertuje raport HTML na Markdown z rozpakowanymi spanami dostępnościowymi (NotebookLM nie konsumuje `<span lang="…">`). Uruchom tylko jeśli chcesz wczytać raport do NotebookLM.

### 4. Szamański post-procesor bez LLM (opcjonalnie)

```bash
python shamanic_pipeline.py
# → export_results/<project>/audio_scripts/oracle_script.txt
#                                          /raw_roots_chant.txt
#                                          /prophecies.txt
#                                          /lore_fragments/intercepted_log_T*_P*.txt
#                                          /emotional_undertow.txt   # tylko jeśli istnieje sentiment.csv
```

Generuje rytualne artefakty tekstowe wprost z eksportów CSV/JSON notatnika — bez wywołania LLM, bez sieci. Wszystkie stringi pochodzą z `shamanic_locale.py` i są w pełni zlokalizowane we wszystkich sześciu wspieranych językach. Gdy obecny jest opcjonalny `sentiment.csv`, generuje dodatkowo `emotional_undertow.txt` — per-akapitowy „przypływ nastroju" plus podsumowanie bilansu; bez niego ten jeden rytuał jest po prostu pomijany.

### 5. Szamański post-procesor LLM (opcjonalnie, wymaga klucza OpenAI)

```bash
python shamanic_ai.py
# → export_results/<project>/audio_scripts/katla_entity_monologue.txt
#                                          /vieno_echoes_chant.txt
#                                          /lumi_final_report.txt
#                                          /sami_energetic_spark.txt
```

Wymaga klucza API OpenAI. Stwórz `golden_key.env` w katalogu głównym projektu:

```
OPENAI_API_KEY=sk-...
```

`golden_key.env` pasuje do `*.env` w `.gitignore`, więc nie zostanie zacommitowany. Cztery głosy odpalają się po kolei:

1. **Katla** przemienia listę encji (`entities.csv`) w monolog zamrożonych północnych duchów.
2. **Vieno** intonuje pieśń wokół listy słów kluczowych/tematów. Domyślnie wplata pięć surowych zdań z korpusu jako echa z innego wymiaru; gdy obecny jest opcjonalny `sentiment.csv`, zamiast tego czyta łuk emocjonalny tekstu (per-akapitowe nastroje, zredukowane (downsampled), by zmieścić się w limicie tokenów modelu na długich korpusach) i pozwala mu kształtować dynamikę pieśni.
3. **Lumi** czyta `prophecies.txt` (obowiązkowo) plus monolog Katli i pieśń Vieno (opcjonalny ornament) i produkuje końcowy meldunek. Zlokalizowane stringi fallbacku obsługują przypadek, gdy Katli lub Vieno brakuje.
4. **Sami** czyta meldunek Lumi i dostarcza energetyczną syntezę z iskrą nadziei lub wezwaniem do działania.

### 6. Szamański dyspozytor audio (opcjonalny, wymaga ElevenLabs)

```bash
python shamanic_voice.py
# → export_results/<projekt>/audio_scripts/katla_entity_monologue.mp3
#                                          /vieno_echoes_chant.mp3
#                                          /lumi_final_report.mp3
#                                          /sami_energetic_spark.mp3
```

Samodzielny skrypt jednorazowy, który czyta cztery artefakty narracyjne wytworzone przez `shamanic_ai.py` i syntetyzuje każdy do `.mp3` przez model ElevenLabs `eleven_multilingual_v2` (sam wykrywa język mowy, więc nie przekazujemy parametru języka). Loguje każdy sukces lub błąd do konsoli i kończy działanie — nie ma bota, serwera ani sesji interaktywnej. Potrzebuje dwóch rzeczy:

- `ELEVENLABS_API_KEY` w `golden_key.env` (ten sam plik, który zawiera `OPENAI_API_KEY`).
- mapowania `voices` w `config.json` / `config.ini`, które przypisuje identyfikator głosu ElevenLabs każdemu z `katla`, `vieno`, `lumi`, `sami`. Głos z pustym ID lub bez artefaktu jest pomijany (najpierw uruchom `shamanic_ai.py`); awaria jednego głosu nie przerywa pozostałych.

> **Prywatność i koszt.** Tak jak `shamanic_ai.py` z OpenAI, ten skrypt wysyła treść artefaktów do usługi zewnętrznej (ElevenLabs) w celu syntezy, a ElevenLabs to **płatne** API. Treść opuszcza twój komputer — nie uruchamiaj go na materiałach, których nie możesz udostępnić na zewnątrz.

## Wyjście

Każdy analizowany korpus dostaje własny podkatalog w `export_results/`, nazwany po pliku źródłowym (z usuniętą ścieżką i rozszerzeniem) albo po `domain_slug` dla URL-i. Wbudowany przykładowy korpus używa `export_results/_default/`.

Każdy podkatalog zawiera:

| Plik                            | Produkowany przez | Opis                                              |
|---------------------------------|-------------------|---------------------------------------------------|
| `sentences.csv`                 | notatnik          | każde zdanie z jego indeksem i przypisaniem do akapitu |
| `paragraphs.csv`                | notatnik          | akapity (po 3–6 zdań)                             |
| `theses.csv`, `theses.txt`      | notatnik          | jedna teza na akapit (zdanie o najwyższym TF-IDF); nazwa pliku `.txt` zależy od języka korpusu (np. `tezy.txt` dla polskiego, `тезисы.txt` dla rosyjskiego) |
| `keywords_tfidf.csv`            | notatnik          | słowa kluczowe (uni/bi/trigramy) z wagami TF-IDF  |
| `paragraphs_with_topics.csv`    | notatnik          | akapity z przypisanym tematem KMeans              |
| `topic_keywords.json`           | notatnik          | słowa kluczowe per temat                          |
| `entities.csv`                  | notatnik          | wszystkie nazwane encje i ich etykiety            |
| `sentiment.csv`                 | notatnik *(opcjonalnie)* | per-akapitowy sentyment (`para_id`, `label`, `score`, `lang`) — tylko gdy `enable_sentiment` jest `true`; pożywka dla warstwy szamańskiej, nigdy nie pokazywana użytkownikowi |
| `accessible_text.html`          | notatnik          | atrybuty `lang` na poziomie akapitu i zdania — czytniki ekranu automatycznie przełączają głos per fragment |
| `accessible_text.docx`          | notatnik          | ta sama treść z `<w:lang>` ustawionym per `Run` (`pl-PL`, `ru-RU`, `en-US`, `it-IT`, `fi-FI`, `is-IS`) — Word i SAPI używają tego offline, bez detektora online |
| `analysis_report.html`           | `generate_report.py` | globalny dostępny raport HTML                  |
| `diagnostic_report.html`         | `generate_diagnostic.py` | ustrukturyzowany raport diagnostyczny (tematy, tezy, encje wg typu, słowa kluczowe) z eksportów CSV/JSON |
| `notebooklm_report.md`      | `generate_md.py`     | Markdown gotowy dla NotebookLM                 |
| `audio_scripts/*.txt`           | `shamanic_pipeline.py`, `shamanic_ai.py` | rytualne / narracyjne artefakty tekstowe |
| `audio_scripts/*.mp3`           | `shamanic_voice.py` *(opcjonalnie)* | cztery głosy narracyjne zsyntetyzowane do audio przez ElevenLabs |

## Dostępność

To jest centralna wartość projektu. Wszystko poniżej jest celowe i musi być zachowane przy modyfikacjach potoku:

- **Bez kolorów ANSI, emoji i pseudografiki w stdout.** Czytnik ekranu czyta dosłownie każdy znak — `[OK]` zamiast „🟢”, `---` zamiast „───━━━”.
- **Wyciszone paski postępu** (`tqdm`, `transformers`, `torch`) — `cell_model._silence_hf_progress()` wycisza paski ładowania Hugging Face/torch i ostrzeżenia przed pobraniem IceBERT i MIM-GOLD-22 dla islandzkiego; `cell_corpus._silence_ocr_progress()` robi to samo dla `easyocr`.
- **Tagi `lang` per akapit i per zdanie w eksporcie.** `accessible_text.html` i `accessible_text.docx` mają kod ISO 639-1 na każdym akapicie (i na każdym zdaniu w akapitach mieszanych językowo / runach). NVDA, JAWS, Narrator, VoiceOver, Word i SAPI respektują te tagi i przełączają głos automatycznie — nawet offline.
- **Twardo wpisane oznaczanie angielskiego w raporcie HTML.** `generate_report.py` zawsze owija technicznie angielskie fragmenty — tagi POS (`NOUN`, `VERB`, `ADJ`), etykiety NER (`PER`, `ORG`, `[orgName]`), identyfikatory modeli spaCy / Hugging Face, ścieżki ASCII, bloki kodu — w `<span lang="en">`, więc nie są już wymawiane domyślnym rosyjskim głosem dokumentu.
- **Per-fragmentowe oznaczanie obcego korpusu w HTML.** Gdy korpus nie jest rosyjski, ustrukturyzowane wyjścia (cytaty zdań, listy słów kluczowych, słowa tematów, wiersze rankingu RAG, tabele lematyzacji) są owinięte w `<span lang="target_lang">`.
- **Liniowa struktura HTML** (`<main>`, poprawna hierarchia nagłówków).

### Odczytywanie wyników jako użytkownik nierosyjskojęzyczny

Narracja notatnika i wyjście `print()` większości komórek są w języku rosyjskim. Dwie cechy interfejsu Jupytera czynią to wrogim dla użytkowników nierosyjskojęzycznych korzystających z czytników ekranu — pipeline dostarcza dla każdej z nich konkretne obejście:

- **Jupyter w przeglądarce ma na sztywno wpisane `lang="en"` na dokumencie**, a podpowiedź „Przetłumaczyć tę stronę?" i tak nigdy nie pojawia się dla stron na `localhost`. Notatnik z rosyjską narracją jest więc czytany angielskim głosem TTS — totalny chaos. Pragmatyczne rozwiązanie to **rozszerzenie Jupyter w VS Code**: jego widok listy komórek wypowiada tylko etykiety `code cell` / `markdown cell` bez tagów ISO, można Enter-em przechodzić przez komórki kodu i ↓ pomijać komórki markdown bez słuchania ich treści, a problem twardego angielskiego ogranicza się do widoku outputów (`Ctrl+Shift+↓`), którego można po prostu nie otwierać.
- **`generate_report.py` jest praktycznie obowiązkowy dla użytkowników nierosyjskojęzycznych.** Generuje `analysis_report.html` z `<html lang="ru">` i pełnym zestawem tagów `<span lang="…">` per fragment. Otwarty w normalnej przeglądarce (nie wewnątrz Jupytera) wyzwala podpowiedź „Przetłumaczyć tę stronę?" dla rosyjskiej narracji, jednocześnie zachowując przełączanie głosu TTS na fragmentach korpusu i na terminach technicznych po angielsku (POS, NER, nazwy modeli).
- **Interaktywne Q&A zapisuje `qa_results.html` i otwiera plik za Ciebie.** `cell_qa_rag` nadal wypisuje pytanie i top-3 trafienia do stdout — ale dodatkowo zapisuje tę samą treść do `export_results/<project>/qa_results.html` i wywołuje `webbrowser.open()`, więc strona ląduje w systemowej przeglądarce, gdzie tłumaczenie i per-fragmentowe przełączanie głosu TTS działają. Widok outputów w Jupyterze, gdzie twarde `lang="en"` czyni rosyjskie obwoluty nieczytelne dla czytnika ekranu, nie jest więc już jedyną drogą do wyniku. Każde nowe pytanie nadpisuje plik.

## Układ repozytorium

```
accessible_text_analyst/
├── accessible_text_analyst.ipynb   # główny potok (42 komórki)
├── generate_report.py              # generator raportu HTML (widok czytelnika)
├── generate_diagnostic.py          # diagnostyczny raport HTML z eksportów CSV/JSON
├── generate_md.py                  # konwerter na Markdown dla NotebookLM
├── shamanic_pipeline.py            # opcjonalnie: rytualny post-procesor bez LLM
├── shamanic_ai.py                  # opcjonalnie: rytualni narratorzy LLM
├── shamanic_voice.py               # opcjonalnie: dyspozytor audio ElevenLabs (jednorazowy)
├── shamanic_locale.py              # pakiet lokalizacyjny dla warstwy szamańskiej
├── config.example.json             # szablon konfiguracji, rozszerzenie JSON (wersjonowane)
├── config.example.ini              # szablon konfiguracji, rozszerzenie INI (wersjonowane)
├── config.json / config.ini        # twoja lokalna konfiguracja (gitignored)
├── golden_key.env                  # klucz OpenAI dla shamanic_ai.py (gitignored)
├── requirements.txt                # zależności pip
├── CLAUDE.md                       # przewodnik dla Claude Code
├── README.md                       # kanoniczne README (po angielsku)
├── README_pl.md, README_ru.md, …   # tłumaczenia (link zwrotny na górze)
├── release_notes.md                # release notes w odwrotnej kolejności chronologicznej
└── export_results/                 # wyniki analizy (gitignored)
    └── <project_name>/
        ├── sentences.csv
        ├── paragraphs.csv
        ├── theses.csv
        ├── theses.txt              # nazwa zależna od języka korpusu
        ├── accessible_text.html
        ├── accessible_text.docx
        ├── analysis_report.html
        ├── diagnostic_report.html
        ├── notebooklm_report.md
        └── audio_scripts/…
```

## Licencja

Wydane na [licencji MIT](LICENSE). Potok jest dystrybuowany wyłącznie jako kod źródłowy — bez binarek — a notatnik ze swojej natury jest edytowalny komórka po komórce w przeglądarce albo w rozszerzeniu Jupyter dla VS Code. Licencja MIT po prostu czyni wprost to, co i tak wynika z formatu.
