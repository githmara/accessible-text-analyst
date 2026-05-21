import html as _html
import json
import re
import sys
from functools import lru_cache

NOTEBOOK_PATH = "accessible_text_analyst.ipynb"
OUTPUT_HTML = "raport_analizy.html"
CONFIG_PATH = "config.json"

# REMOVE_NOISE czytany z config.json (gitignored), żeby przełączanie
# między widokiem czytelnika a pełnym widokiem diagnostycznym nie
# brudziło historii repo. Brak pliku lub klucza => domyślnie True
# (tryb czytelnika: bez tabel lematyzacji, POS i pasków ładowania).
def _load_remove_noise(path=CONFIG_PATH, default=True):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return bool(json.load(f).get("remove_noise", default))
    except (FileNotFoundError, json.JSONDecodeError):
        return default

REMOVE_NOISE = _load_remove_noise()

try:
    import markdown
except ImportError:
    print("[BŁĄD] Brak biblioteki markdown. Wykonaj: pip install markdown")
    sys.exit(1)

try:
    from lingua import Language, LanguageDetectorBuilder
except ImportError:
    print("[BŁĄD] Brak biblioteki lingua-language-detector.")
    print("       Wykonaj: pip install lingua-language-detector")
    sys.exit(1)


# ============================================================
# Detektor języka per-fragment dla treści, której nie obejmuje
# ani EN-hardkod (POS-tag, NER-label itp.), ani target-lang
# z notebooka. Najczęściej są to: dynamiczne ścieżki plików
# z polskimi/fińskimi nazwami własnymi, kod inline w markdownie
# (przykłady polskich/rosyjskich skrótowców) oraz tytuły dzieł.
# ============================================================
_SUPPORTED_LANGS = {"en", "pl", "ru", "it", "fi", "is"}
_LINGUA_DETECTOR = LanguageDetectorBuilder.from_languages(
    Language.ENGLISH, Language.POLISH, Language.RUSSIAN,
    Language.ITALIAN, Language.FINNISH, Language.ICELANDIC,
).build()


@lru_cache(maxsize=8192)
def _detect_lang(text):
    """Wykryj język fragmentu — zwraca ISO 639-1 lub None.
    Cache LRU — generator analizuje wielokrotnie te same nazwy własne
    (Sara, Joanna, ohjaaja itd.), więc cache uniknie tysięcy wywołań lingua.
    """
    if not text or len(text.strip()) < 3:
        return None
    try:
        lang_obj = _LINGUA_DETECTOR.detect_language_of(text)
    except Exception:
        return None
    if lang_obj is None:
        return None
    iso = lang_obj.iso_code_639_1.name.lower()
    return iso if iso in _SUPPORTED_LANGS else None


# ============================================================
# Hardkod lang="en" dla fragmentów technicznych, które są zawsze
# anglojęzyczne niezależnie od języka korpusu (POS-tagi, NER-label,
# nazwy modeli spaCy/Hugging Face, identyfikatory plików ASCII itp.).
#
# Bez tego NVDA/JAWS czytałyby je głosem domyślnym dokumentu (rosyjski),
# co psuje zarówno wymowę, jak i rozumienie technicznych skrótów.
# ============================================================
# Pełne nazwy POS-tagów (Universal Dependencies + Penn Treebank). Zawsze
# anglojęzyczne, taggujemy je gdziekolwiek się pojawią — w pipe-table,
# w rozkładzie częstości (NOUN: 50), oraz w nagłówkach narracji
# ("NOUN — сущ., VERB — гл."). Granica \b z obu stron broni przed
# matchowaniem wewnątrz słów.
_POS_TAGS_FULL = (
    r"NOUN|VERB|ADJ|ADV|AUX|CCONJ|DET|INTJ|NUM|PART|PRON|PROPN|PUNCT|SCONJ|SYM|"
    r"ADP|ADD|AFX|HYPH|NFP|PDT|"
    r"JJR|JJS|NNP|NNPS|NNS|PRP|RBR|RBS|VBD|VBG|VBN|VBP|VBZ|WDT|WRB|XX|SPACE|"
    # Penn Treebank krótkie: 2-literowe ale jednoznaczne w domenie NLP
    r"CC|CD|DT|EX|FW|IN|JJ|LS|MD|NN|RB|RP|SP|TO|UH|VB|WP|"
    # X — UD POS dla "other/unknown" (gdy spaCy nie potrafi sklasyfikować).
    r"X"
)

# Krótkie aliasy z trzeciej kolumny cell_pos (multi-letter Title Case
# Pron, Adv, Conj, Aux i 1-literowe N/V/A/J...). Tylko po "|" w pipe-table —
# standalone "Pron" lub "V" w innym kontekście nie powinno być POS-tagiem.
_POS_TAGS_FI_ALIASES = (
    # 1-literowe (fiński cell_pos: N=Noun, V=Verb, A=Adjective, ...)
    r"A|N|V|J|R|P|D|C|M|U|S|F|G|I|L|T|W|X|Y|Z|"
    # Wieloliterowe Title Case aliasy
    r"Pron|Adv|Conj|Det|Aux|Interj|Art|Punct|Sym|Adp|"
    r"Card|Ord|Comp|Sup|Dem|Neg|Poss"
)

_NER_LABELS = (
    r"PER|PERSON|persName|ORG|orgName|LOC|GPE|placeName|geogName|FAC|NORP|"
    r"PRODUCT|EVENT|WORK_OF_ART|LAW|LANGUAGE|DATE|TIME|PERCENT|MONEY|"
    r"QUANTITY|ORDINAL|CARDINAL|MISC|EVT|ROL|MEDIA"
)

_SPACY_PIPELINE_COMPONENTS = (
    r"tok2vec|tagger|parser|attribute_ruler|lemmatizer|ner|sentencizer|senter|"
    r"morphologizer|trainable_lemmatizer|tok2vec_listener|transformer|textcat|"
    r"entity_linker|entity_ruler|merge_entities|merge_noun_chunks|"
    r"icebert_vectors|icelandic_ner"
)

_HF_ORG_PREFIXES = (
    r"cardiffnlp|mideind|nlptown|sentence-transformers|google|microsoft|"
    r"openai|facebook|meta-llama|deepset|allenai|huggingface|spacy|"
    r"bert-base|distilbert-base|xlm-roberta-base"
)

_PROJECT_IDENTIFIERS = (
    r"export_results|FALLBACK_CORPUS|MODEL_BY_LANG|CUSTOM_PATTERNS|"
    r"SUPPORTED_LANGS|LANG_NAMES|LANG_DETECTOR|LANG_TO_LOCALE|PROJECT_DIR|"
    r"PROJECT_NAME|SOURCE_FILE|HF_IS_VECTORS|HF_IS_NER|RELATED_ARTICLES_STOPWORDS|"
    r"PARA_MIN|PARA_MAX|TOKEN_PAT|AUTO_QUERY|THESES_FILE|"
    # Krótkie identyfikatory pojawiające się w narracji rosyjskiej.
    # Bezpieczne przez \b — nie matchują w słowach ani inflexji.
    r"LANG|Run|lang|attr|lemma"
)

# Czytniki ekranu i pokrewne nazwy własne — zawsze anglojęzyczne.
# NVDA, JAWS, Narrator, VoiceOver, SAPI, TTS to terminy techniczne pisane
# wyłącznie po angielsku, niezależnie od języka narracji.
_SCREEN_READERS_AND_TTS = (
    r"NVDA|JAWS|Narrator|VoiceOver|SAPI|TTS"
)

# Akronimy techniczne — formaty plików, terminy NLP, jednostki pamięci
# itp. Zawsze pisane wielkimi literami (lub CamelCase dla DataFrame).
# Granica \b chroni przed matchowaniem w polskich/rosyjskich słowach
# zawierających te same litery małe (np. "informacja" nie zawiera "INFO").
_TECH_ACRONYMS = (
    # Formaty plików i protokoły
    r"PDF|HTML|DOCX|CSV|JSON|TXT|XML|YAML|TOML|"
    r"URL|HTTP|HTTPS|API|REST|CLI|GUI|"
    # Terminy NLP/ML
    r"NLP|NER|POS|TF|IDF|BoW|RAG|LRU|"
    # Pamięć/encoding
    r"RAM|ISO|UTF|BOM|"
    # DataFrame'y/Vectorizers (CamelCase i ASCII upper)
    r"DataFrame|UniGram|BiGram|TriGram|"
    # Office/edytory
    r"Excel|Word"
)

# Angielskie słowa domeny NLP/ML często pojawiające się w narracji
# rosyjskiej w cytatach lub w tabelach (np. "Term Frequency — Inverse
# Document Frequency"). Lingua na pojedynczym 7-9 literowym słowie typu
# "Inverse" / "Document" / "documents" zwraca it/pl losowo, więc
# tagujemy wprost.
_NLP_DOMAIN_WORDS = (
    # Angielskie nazwy języków — w tabelach markdown ("| Italian | it |")
    r"English|Polish|Russian|Italian|Finnish|Icelandic|"
    r"Dutch|German|French|Spanish|Portuguese|Chinese|Japanese|"
    # NLP/ML słowa rozwiązane (w opisach algorytmów)
    r"Term|Frequency|Inverse|"
    r"machine|learning|natural|language|languages|named|entity|entities|"
    r"document|documents|sentence|sentences|token|tokens|"
    # Hugging Face składa się z dwóch słów; Hugging matchuje przez lingua jako en,
    # ale Face (4 znaki) nie wpada do _PATH_SEGMENT_LATIN_RE (próg 5).
    r"Face|Hugging"
)

# Warianty modeli spaCy w narracji: "Large (lg)", "версии sm", "*_md".
# Standalone w nawiasach albo poza — w obu przypadkach en. Dłuższe
# warianty jak `*_lg` są obsługiwane osobnym patternem niżej.
_MODEL_SIZE_VARIANTS = r"sm|md|lg|trf"

EN_HARDCODE_PATTERNS = [
    # ============ KOMPOZYTOWE IDENTYFIKATORY (priorytet) ============
    # Patterny matchujące "wieloczęściowe" identyfikatory muszą iść jako
    # pierwsze, bo inaczej pojedyncze słowa-akronimy (np. "sentences"
    # z _NLP_DOMAIN_WORDS) zostaną zatagowane wcześniej i rozbiją
    # pełną nazwę pliku na osobne fragmenty (sentences  .csv).

    # Pliki ASCII z rozszerzeniem technicznym (pomija cyryliczne typu тезисы.txt)
    (r"\b([A-Za-z][A-Za-z0-9_-]*\.(?:csv|json|html|docx|py|md|txt|ipynb|yaml|yml|toml|cfg|ini|sh|bat|ps1))\b",
     r'<span lang="en">\1</span>'),

    # Nazwy modeli spaCy: pl_core_news_lg, en_core_web_lg, ...
    (r"\b([a-z]{2,3}_core_(?:news|web|dep)_(?:sm|md|lg|trf))\b",
     r'<span lang="en">\1</span>'),

    # Wzorce modeli z gwiazdką: *_md, *_lg, *_sm, *_trf
    (r"(\*_(?:sm|md|lg|trf))\b",
     r'<span lang="en">\1</span>'),

    # Identyfikatory modeli Hugging Face: org/model-name
    (r"\b((?:" + _HF_ORG_PREFIXES + r")\/[A-Za-z0-9_.-]+)\b",
     r'<span lang="en">\1</span>'),

    # ============ NER labels (priorytet — w wielu strukturach) ============
    # w nawiasach prostokątnych: [PER], [orgName], [GPE]
    (r"(\[)(" + _NER_LABELS + r")(\])",
     r'\1<span lang="en">\2</span>\3'),

    # samodzielny przed dwukropkiem (cell_summary): "  PER         : 45"
    # MULTILINE — ^ per linia, nie tylko na początku całego chunka.
    (r"^(\s+)(" + _NER_LABELS + r")(\s+:\s+\d)",
     r'\1<span lang="en">\2</span>\3'),

    # NER label w narracji (poza nawiasami i bez `:`) — np. "Типичные метки:
    # PERSON, ORG, GPE, DATE, MONEY, PRODUCT".
    (r"\b(" + _NER_LABELS + r")\b",
     r'<span lang="en">\1</span>'),

    # ============ POS-tagi i komponenty pipeline ============
    # POS-tag pełna nazwa, gdziekolwiek wystąpi.
    (r"\b(" + _POS_TAGS_FULL + r")\b",
     r'<span lang="en">\1</span>'),

    # Krótkie aliasy POS — tylko po "|" w pipe-table.
    (r"(\|\s*)(" + _POS_TAGS_FI_ALIASES + r")(?=\s*(?:\||$))",
     r'\1<span lang="en">\2</span>'),

    # Nazwy komponentów spaCy w cudzysłowie (lista pipe_names)
    (r"&#x27;(" + _SPACY_PIPELINE_COMPONENTS + r")&#x27;",
     r'&#x27;<span lang="en">\1</span>&#x27;'),

    # ============ Nazwy własne, akronimy, terminy domeny ============
    # Czytniki ekranu, TTS
    (r"\b(" + _SCREEN_READERS_AND_TTS + r")\b",
     r'<span lang="en">\1</span>'),

    # Akronimy techniczne (PDF, HTML, NER, BoW, RAM, ...)
    (r"\b(" + _TECH_ACRONYMS + r")\b",
     r'<span lang="en">\1</span>'),

    # Warianty rozmiaru modeli spaCy: standalone "lg", "(lg)", "sm" itp.
    # Krótkie 2-3 literowe — bez \b z lewej tylko spacja/nawias/myślnik.
    (r"(?<![A-Za-z])(" + _MODEL_SIZE_VARIANTS + r")(?![A-Za-z])",
     r'<span lang="en">\1</span>'),

    # Tagi HTML jako tekst escape'owany: &lt;p&gt;, &lt;span&gt;, &lt;html&gt; itp.
    # Matchuje też atrybuty wewnątrz: &lt;p lang="..."&gt;.
    (r"(&lt;\/?[a-z][a-z0-9]*(?:\s[^&]*)?&gt;)",
     r'<span lang="en">\1</span>'),

    # Nazwy pakietów/bibliotek pojawiające się w outputach
    (r"\b(spaCy|spacy|sklearn|scikit-learn|numpy|pandas|tqdm|transformers|torch|"
     r"BeautifulSoup|bs4|pdfplumber|python-docx|markdown|requests|lxml|"
     r"langdetect|lingua|lingua-language-detector|nbstripout|jupyter|"
     r"functools|lru_cache|CountVectorizer|TfidfVectorizer|KMeans)\b",
     r'<span lang="en">\1</span>'),

    # Identyfikatory projektowe (zmienne globalne, stałe w stdout)
    (r"\b(" + _PROJECT_IDENTIFIERS + r")\b",
     r'<span lang="en">\1</span>'),

    # Angielskie nazwy języków i słowa domeny NLP/ML.
    # Case-insensitive — Title Case ("Inverse Document") i lower
    # ("machine learning") obok siebie.
    (r"(?i)\b(" + _NLP_DOMAIN_WORDS + r")\b",
     r'<span lang="en">\1</span>'),

    # ISO 639-1 kody w nawiasach: (fi), (en), (pl)
    (r"(\()(en|pl|ru|it|fi|is)(\))",
     r'\1<span lang="en">\2</span>\3'),

    # ISO 639-1 kody wewnątrz pojedynczych cudzysłowów: 'fi', 'en'.
    # Łapie zarówno dict-output ({&#x27;pl&#x27;: 5}) jak i samodzielne
    # wystąpienia z cell_multilang_pass ("Язык &#x27;fi&#x27; (финский)").
    (r"(&#x27;)(en|pl|ru|it|fi|is)(&#x27;)",
     r'\1<span lang="en">\2</span>\3'),

    # ISO 639-1 na początku wciętej linii w sekcji [ИТОГ] z
    # cell_multilang_pass: "  fi: предложений — 23".
    (r"^(\s+)(en|pl|ru|it|fi|is)(:\s+предложений)",
     r'\1<span lang="en">\2</span>\3'),
]


_TAG_RE = re.compile(r'(<[^>]+>)')
_SKIP_REGIONS_RE = re.compile(
    r'(<span lang="[^"]*">.*?</span>|<code\b[^>]*>.*?</code>)',
    re.DOTALL,
)


def _sub_only_in_text_nodes(text, pattern, replacement, flags=0):
    """re.sub poza zawartością tagów HTML.
    Splituje tekst na (HTML-tag | text-node) i aplikuje regex tylko na
    text nodes. Zapobiega temu, by `\\blang\\b` matchowało atrybut
    `lang="en"` albo by lingua taggowała nazwę elementu (`<strong>`).
    """
    parts = _TAG_RE.split(text)
    out = []
    for p in parts:
        if p.startswith('<') and p.endswith('>'):
            out.append(p)
        else:
            out.append(re.sub(pattern, replacement, p, flags=flags))
    return ''.join(out)


def _apply_outside_spans(text, patterns):
    """Aplikuje listę (regex, replacement) do wszystkich text-nodes
    poza już-otagowanymi <span lang="..."> i <code...>. Re-split przed
    każdym patternem — substitucja patternu N tworzy nowe <span lang="...">,
    których zawartość nie może być widziana przez pattern N+1.
    """
    for pat, repl in patterns:
        parts = _SKIP_REGIONS_RE.split(text)
        rebuilt = []
        for part in parts:
            if part.startswith('<span') or part.startswith('<code'):
                rebuilt.append(part)
            else:
                rebuilt.append(_sub_only_in_text_nodes(
                    part, pat, repl, flags=re.MULTILINE,
                ))
        text = ''.join(rebuilt)
    return text


# Post-processing: scalanie spanów ten-sam-lang oraz rozszerzanie span en o
# trailing -[0-9]+ ("UTF-8"). NVDA i wiele TTS przy *przejściu* między spanami
# różnymi językami wymawia separator (myślnik, przecinek, kropkę, nawias),
# nawet gdy interpunkcja jest "cicha" w obrębie jednego języka. Stąd
# "TF тире IDF" lub "DOCX правая круглая скобка python-docx" zamiast
# "TF-IDF" / "DOCX (python-docx)". Coalescing eliminuje pauzy.
#
# UWAGA: separator BEZ nawiasów `()[]` — żeby uniknąć asymetrycznego scalenia
# typu `<span en>Large (lg</span>)`. Nawiasy są dołączane przez osobny
# pattern `_BRACKET_WRAP_RE`, który wymaga zbalansowanej pary `(...)`.
_COALESCE_SAME_LANG_RE = re.compile(
    r'<span lang="([^"]+)">([^<]*)</span>'
    r'([\s\-–—,;:./·…]+)'                         # whitespace + neutralna interpunkcja
    r'<span lang="\1">([^<]*)</span>'             # (z myślnikami pauzy: ‑ – —)
)
# Wciąga zewnętrzne, zbalansowane nawiasy w span: "(<span en>lg</span>)" →
# "<span en>(lg)</span>". Dzięki temu NVDA czyta "(lg)" w obrębie en,
# a nie zewnętrzne nawiasy głosem rosyjskim.
_BRACKET_WRAP_RE = re.compile(
    r'\((<span lang="([^"]+)">([^<]+)</span>)\)'
)
# Rozszerza <span lang="en">X</span>-NN o trailing -liczba ("UTF-8",
# "COVID-19"). Częsty artefakt: akronim_en + wersja/standard_numeryczny.
_EXTEND_EN_WITH_NUMBER_RE = re.compile(
    r'<span lang="(en)">([^<]*)</span>(-[0-9]+)\b'
)


def _coalesce_same_lang_spans(text):
    """Iteracyjnie scal/rozszerz spany same-lang aż do stabilizacji."""
    prev = None
    while text != prev:
        prev = text
        text = _COALESCE_SAME_LANG_RE.sub(
            r'<span lang="\1">\2\3\4</span>', text,
        )
        text = _BRACKET_WRAP_RE.sub(
            r'<span lang="\2">(\3)</span>', text,
        )
        text = _EXTEND_EN_WITH_NUMBER_RE.sub(
            r'<span lang="\1">\2\3</span>', text,
        )
    return text


# Segmenty "wyglądające jak nazwa/ścieżka". Tylko Latin (z diakrytykami),
# bo lingua-fallback tagujemy tylko gdy detect-uje język INNY niż
# document_lang (zwykle ru) — cyryliczne segmenty zawsze zwrócą ru, więc
# ich tagowanie nic by nie dało, a nadto zwiększa szum. Próg 5 znaków:
# poniżej lingua zwraca losowy wynik (testy: "LRU", "Run" → "is").
_PATH_SEGMENT_LATIN_RE = re.compile(
    r'[A-Za-zÀ-ÿĀ-ſ][A-Za-zÀ-ÿĀ-ſ0-9_-]{4,}',
    re.UNICODE,
)

_ASCII_ONLY_TOKEN_RE = re.compile(r'^[A-Za-z0-9_-]+$')
_CAMEL_CASE_RE = re.compile(r'[a-z][A-Z]')  # przejście lower→upper w środku


def _lingua_word_fallback(text, document_lang="ru"):
    """Lingua per-segment fallback dla treści w output-box, której nie
    obejmują predefiniowane wzorce: dynamiczne ścieżki plików, nazwy
    własne korpusu, fragmenty obcojęzyczne w rosyjskiej narracji.

    Heurystyki (kolejno) dla ASCII-only segmentów — zanim odpalimy lingui:
    1. `_` lub code-look (nawiasy, kropki) → Python identifier → en.
       (get_nlp, sent_langs, accessible_text...)
    2. CamelCase / PascalCase (lower→upper przejście) → identifier → en.
       (UniGram, IceBERT, BeautifulSoup, BiGram, TriGram).

    Dla nazw własnych z diakrytykami (Joanna_Kos-Krauzen_särkyneet_kulissit)
    nie trafiamy w żadną z heurystyk ASCII-only — lingui dostaje pełną nazwę
    i wykrywa fi/pl prawidłowo.

    Cyryliczne segmenty zostawiamy w spokoju — zawsze są w document_lang.
    """
    def repl(m):
        seg = m.group(0)
        is_ascii_only = _ASCII_ONLY_TOKEN_RE.fullmatch(seg) is not None
        if is_ascii_only:
            if '_' in seg or _CODE_LOOK_RE.search(seg):
                if document_lang != "en":
                    return f'<span lang="en">{seg}</span>'
                return seg
            if _CAMEL_CASE_RE.search(seg):
                if document_lang != "en":
                    return f'<span lang="en">{seg}</span>'
                return seg
            # Po cleanup z separatorów (- _ cyfra) zostają same litery.
            # Mniej niż 5 → lingua zwraca losowo (test: "lang"→is,
            # "lang-"→is). Fallback en.
            letters_only = re.sub(r'[^A-Za-z]', '', seg)
            if len(letters_only) < 5:
                if document_lang != "en":
                    return f'<span lang="en">{seg}</span>'
                return seg
        detected = _detect_lang(seg)
        if detected and detected != document_lang:
            return f'<span lang="{detected}">{seg}</span>'
        return seg

    parts = _SKIP_REGIONS_RE.split(text)
    out = []
    for part in parts:
        if part.startswith('<span') or part.startswith('<code'):
            out.append(part)
            continue
        # Pomijamy też zawartość tagów HTML (<strong>, <li>, <a href=...>),
        # żeby lingua nie próbowała tagować nazw elementów ani atrybutów.
        subparts = _TAG_RE.split(part)
        new_sub = []
        for sub in subparts:
            if sub.startswith('<') and sub.endswith('>'):
                new_sub.append(sub)
            else:
                new_sub.append(_PATH_SEGMENT_LATIN_RE.sub(repl, sub))
        out.append(''.join(new_sub))
    return ''.join(out)


_CODE_BLOCK_RE = re.compile(
    r'<code(?![^>]*\blang=)([^>]*)>(.*?)</code>',
    re.DOTALL,
)

# Hardkodowane skrótowce — krótsze niż próg lingua, ale jednoznaczne.
# Bez tej listy "m.in." / "т.е." / "np." są klasyfikowane heurystyką
# fallback na "en" (krótkie ASCII), co psuje wymowę przykładów w narracji.
# Wszystkie warianty bez końcowego przecinka — przecinek jest stripowany
# przed lookupem, żeby pokryć "m.in,", "np.,", "т.д.,", "и т.д." itp.
_ABBREV_BY_LANG = {
    "pl": frozenset({
        "m.in.", "m.in", "m. in.", "m. in", "np.", "np",
        "tzw.", "tzw", "tzn.", "tzn", "tj.", "tj",
        "itd.", "itd", "itp.", "itp", "ww.", "ww",
        "tzn", "tzn.",
    }),
    "ru": frozenset({
        "т.е.", "т. е.", "т.е", "т.д.", "т. д.", "т.д",
        "т. наз.", "т.наз.", "напр.", "и др.", "и пр.",
        "т. п.", "т.п.", "и т.д.", "и т. д.", "и т.п.", "и т. п.",
    }),
    "en": frozenset({
        "e.g.", "e. g.", "e.g", "i.e.", "i. e.", "i.e",
        "etc.", "etc", "vs.", "vs", "cf.", "cf",
        "a.k.a.", "a.k.a", "n.b.", "viz.",
    }),
}

# Wygląd "kodu Python/HTML/CSS": nawiasy, podkreślenia jako separator
# słów, kropki przed identyfikatorem (.method, module.attr), strzałki,
# znaki przypisania. Match → klasyfikujemy jako en bez angażowania lingui.
_CODE_LOOK_RE = re.compile(
    r'[(){}\[\]=<>;:&|/\\]'      # typowe znaki kodu
    r'|\.\w+'                    # kropka przed identifikatorem (spacy.blank)
    r'|\w_\w'                    # identyfikator z podkreśleniem
    r'|->'                       # strzałka funkcyjna
)


_HAS_CYRILLIC_RE = re.compile(r'[Ѐ-ӿ]')


def _classify_code_lang(plain):
    """Wybiera lang dla zawartości <code>. Kolejność heurystyk:
    1. Skrótowce ze sztywnej listy (m.in., т.е., e.g.) — jednoznaczne.
       Końcowy przecinek jest pomijany, żeby "m.in," / "np.,"  trafiały
       w listę warianów bez przecinka.
    2. Zawiera cyrylicę → lingua → ru (cyrylica jest jednoznaczna).
       Wczesna ścieżka, żeby krótkie "что что" / "т.д." nie spadało
       do fallbacku en przez krok 4.
    3. "Code-look" (nawiasy, podkreślenia, kropki przed identyfikatorem) → en.
    4. Po usunięciu znaków niealfabetycznych < 8 liter → en. Lingua na
       6-7 znakowych łacińskich nazwach typu "lingua" zwraca losowo
       (it/is/pl) — bezpieczniej zaakceptować en jako default dla
       krótkich identyfikatorów w <code>.
    5. Lingua na pełnej zawartości; fallback en.
    """
    plain = plain.strip()
    if not plain:
        return "en"
    # 1. Skrótowce — z normalizacją końcowego przecinka
    plain_norm = plain.rstrip(",").strip()
    for lang, abbrevs in _ABBREV_BY_LANG.items():
        if plain in abbrevs or plain_norm in abbrevs:
            return lang
    # 2. Cyrylica → lingua zawsze rozpozna ru
    if _HAS_CYRILLIC_RE.search(plain):
        return _detect_lang(plain) or "ru"
    # 3. Code-look
    if _CODE_LOOK_RE.search(plain):
        return "en"
    # 4. Cleanup — tylko Latin letters (cyrylica już obsłużona wyżej)
    letters_only = re.sub(r'[^A-Za-z]', '', plain)
    if len(letters_only) < 8:
        return "en"
    # 5. Lingua
    return _detect_lang(plain) or "en"


def _tag_code_blocks(html_str):
    """Wzbogaca elementy <code>/<pre><code> o atrybut lang.
    Pomija elementy, które już mają lang= w atrybutach.
    """
    def repl(match):
        attrs = match.group(1)
        content = match.group(2)
        plain = re.sub(r'<[^>]+>', '', _html.unescape(content))
        detected = _classify_code_lang(plain)
        return f'<code{attrs} lang="{detected}">{content}</code>'

    return _CODE_BLOCK_RE.sub(repl, html_str)

def build_accessible_html():
    with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
        nb = json.load(f)

    # 1. Znajdź język docelowy analizowanego tekstu
    target_lang = "ru" 
    for cell in nb.get("cells", []):
        if cell["cell_type"] == "code":
            for output in cell.get("outputs", []):
                text = "".join(output.get("text", []))
                match = re.search(r'Выбран язык: .*?\((.*?)\)', text)
                if match:
                    target_lang = match.group(1).strip()
                    break

    # 2. Inteligentne tagowanie
    def tag_target_language(text, lang):
        # Zawsze HTML-escape (nawet dla rosyjskiego korpusu — zabezpiecza
        # przed nieoczekiwanym < lub > w outpucie i pozwala traktować
        # &#x27;/&quot; uniformowo we wszystkich wzorcach).
        text = _html.escape(text)

        # === Krok 0: multilang sample (uruchamiany ZAWSZE) ===
        # cell_multilang_pass drukuje "  [fi] [PERSON] 'Joanna Kos'" — gdzie
        # ISO z nawiasu to język danego konkretnego cytatu. Tagujemy go tym
        # ISO, niezależnie od target_lang korpusu, bo nawet w korpusie ru/en
        # wtrącenia mogą być w dowolnym z {pl, fi, it, is}. Pattern bierze
        # ISO z grupy \2 i używa go DWA razy: raz jako wartość lang="en"
        # (sam kod jest anglojęzyczny), drugi raz jako lang="\2" dla tekstu.
        multilang_always_patterns = [
            (r'^(\s+\[)(en|pl|ru|it|fi|is)(\]\s+\[)([A-Za-z_]+)(\]\s+&#x27;)(.+?)(&#x27;)\s*$',
             r'\1<span lang="en">\2</span>\3<span lang="en">\4</span>\5<span lang="\2">\6</span>\7'),
            # cell_multilang_pass per-language лемма-сэмпл:
            # "      [fi] 'Oletko'                 → 'oletko'"
            # Tagujemy kod ISO jako en, a obie strony strzałki — jako ten
            # właśnie ISO (forma i lemma są w tym samym języku).
            (r'^(\s+\[)(en|pl|ru|it|fi|is)(\]\s+&#x27;)(.+?)(&#x27;\s+→\s+&#x27;)(.+?)(&#x27;)\s*$',
             r'\1<span lang="en">\2</span>\3<span lang="\2">\4</span>\5<span lang="\2">\6</span>\7'),
        ]
        lines0 = text.split('\n')
        tagged0 = []
        for line in lines0:
            for pat, repl in multilang_always_patterns:
                line = re.sub(pat, repl, line)
            tagged0.append(line)
        text = '\n'.join(tagged0)

        # === Krok 1: tagowanie języka korpusu (target_lang) ===
        # Wykonujemy najpierw, bo wzorce są zakotwiczone do nieprzetagowanych
        # prefiksów typu "[orgName] " czy "Абзац N:". Po EN-hardkodzie
        # te prefiksy zawierałyby już <span> i regex by nie zadziałał.
        # Dla korpusów rosyjskich i angielskich pomijamy — w ru reszta
        # i tak jest po rosyjsku (lang dziedziczone z <html lang="ru">),
        # a w en EN-hardkod sam zatagowuje treść i tak.
        if lang not in ("ru", "en"):
            patterns = [
                # Zdania bazowe: [1] Obcy tekst...
                (r'^(\s*\[\d+\]\s+)(.+)$', r'\1<span lang="{}">\2</span>'),
                # Słowa kluczowe (pierwsze 20): Первые 20: [&#x27;Word&#x27;, ...]
                (r'(Первые \d+:\s+)(\[.+\])', r'\1<span lang="{}">\2</span>'),
                # Filtrowanie i stop słowa: Выборка (первые 20 по алфавиту): [&#x27;Word&#x27;, ...]
                (r'(Выборка(?: \(первые \d+ по алфавиту\))?:\s+)(\[.+\])', r'\1<span lang="{}">\2</span>'),
                # Tezy: Абзац 1: Obcy tekst...
                (r'^(.*Абзац\s+\d+(?: \([^)]+\))?:\s+)(.+)$', r'\1<span lang="{}">\2</span>'),
                # Przykłady z tematów: Пример: Obcy tekst
                (r'^(.*Пример:\s+)(.+)$', r'\1<span lang="{}">\2</span>'),
                # Bigramy/Trigramy: 1. &#x27;word&#x27;: 5
                (r"^(\s*\d+\.\s+&#x27;)(.+?)(&#x27;\s*:\s*\d+)$", r'\1<span lang="{}">\2</span>\3'),
                # Entity: [orgName] &#x27;Name&#x27;
                (r"^(\s*\[\w+\]\s+&#x27;)(.+?)(&#x27;)$", r'\1<span lang="{}">\2</span>\3'),
                # Niespójne NER (cell_ner diagnostyka): "    'tekst': LABEL1, LABEL2".
                # Tekst trafia w jezyk target_lang; LABEL{1,2} sa lapane przez
                # EN-hardkod (_NER_LABELS) w nastepnym kroku. Wymagamy >= 1
                # przecinka, zeby nie nachodzic na inne wzorce z pojedyncza
                # etykieta.
                (r"^(\s+&#x27;)(.+?)(&#x27;:\s+[A-Za-z][A-Za-z_]*(?:,\s+[A-Za-z][A-Za-z_]*)+)\s*$",
                 r'\1<span lang="{}">\2</span>\3'),
                # Unigramy: &#x27;word&#x27; : 10
                (r"^(\s*&#x27;)(.+?)(&#x27;\s*:\s*\d+.*)$", r'\1<span lang="{}">\2</span>\3'),

                # Auto-wyszukiwanie RAG: Автозапрос: &quot;zapytanie&quot;
                (r'(Автозапрос:\s+&quot;)(.+?)(&quot;)', r'\1<span lang="{}">\2</span>\3'),
                # RAG Tytuł wyszukiwania: Ранжирование по запросу &quot;zapytanie&quot;:
                (r'(Ранжирование по запросу\s+&quot;)(.+?)(&quot;.*)', r'\1<span lang="{}">\2</span>\3'),
                # RAG Tabela z rankingiem: 1      Документ 5     0.2214           hallusinoi...
                (r'^(\s*\d+\s+Документ\s+\d+\s+0\.\d{4}\s+)(.+)$', r'\1<span lang="{}">\2</span>'),
                # Tabela TF-IDF:   słowo                 0.1940
                (r'^(\s+)([^\s\d\|]+(?: [^\s\d\|]+)*?)(\s+0\.\d{4})$', r'\1<span lang="{}">\2</span>\3'),
                # Tematyzacja (Słowa kluczowe w grupie): Ключевые слова: słowo, słowo
                (r'^(.*Ключевые слова:\s+)(.+)$', r'\1<span lang="{}">\2</span>'),
                # Tematyzacja z podsumowania: Тема 0: słowo, słowo
                (r'^(.*Тема \d+:\s+)(.+)$', r'\1<span lang="{}">\2</span>'),
                # Zapytanie w sprawozdaniu końcowym
                (r'(Запрос \(авто\)\s+:\s+&quot;)(.+?)(&quot;)', r'\1<span lang="{}">\2</span>\3'),

                # POS: &#x27;słowo&#x27; | VERB | V (tagujemy tylko słowo!)
                (r"^(\s*&#x27;)(.+?)(&#x27;\s*\|.*)$", r'\1<span lang="{}">\2</span>\3'),
                # Lematyzacja (tabela):   Słowo     słowo   &lt;-- изменено
                (r"^(\s+)(?!Исходное|-------)([^\s]+)(\s+)(?!Лемма|-----)([^\s]+)(\s*&lt;-- изменено)?$",
                 r'\1<span lang="{0}">\2</span>\3<span lang="{0}">\4</span>\5'),
            ]

            lines = text.split('\n')
            tagged_lines = []
            for line in lines:
                for pat, repl in patterns:
                    line = re.sub(pat, repl.format(lang), line)
                tagged_lines.append(line)
            text = '\n'.join(tagged_lines)

        # === Krok 2: hardkod lang="en" dla treści zawsze anglojęzycznej ===
        # Pracujemy tylko poza istniejącymi <span>, żeby nie zagnieżdżać
        # tagów ani nie nadpisywać już zatagowanego korpusu.
        text = _apply_outside_spans(text, EN_HARDCODE_PATTERNS)

        # === Krok 3: lingua per-segment fallback ===
        # Dla pozostałych nieotagowanych "słów" >= 5 znaków (typowo: ścieżki
        # plików, nazwy własne korpusu, fragmenty obcojęzyczne w narracji),
        # jeśli lingua wykryje język inny niż domyślny dokumentu (ru), otocz
        # spanem. Dzięki temu np. "Joanna_Kos-Krauzen_särkyneet_kulissit"
        # w ścieżce dostanie lang="fi", a "Whisper" — lang="en".
        text = _lingua_word_fallback(text, document_lang="ru")

        # === Krok 4: scalanie sąsiadujących spanów same-lang ===
        # "TF тире IDF" → "TF-IDF" (jedno wymówienie en zamiast dwóch).
        text = _coalesce_same_lang_spans(text)

        return text

    # 3. Mechanizm wycinania szumu (dostępnościowy filtr)
    def clean_noise(text_lines):
        if not REMOVE_NOISE:
            return text_lines
        
        clean_lines = []
        skip_mode = False
        
        for line in text_lines:
            # Wyciszanie pasków ładowania i brzydkich komunikatów
            if "Loading weights" in line or "Materializing param" in line:
                continue
            if "Warning: You are sending unauthenticated requests" in line:
                continue
            
            # Wycinanie gigantycznych tabel lematyzacji i POS
            if "--- Лемматизация ---" in line or "--- Разметка частей речи (POS) ---" in line:
                skip_mode = True
            elif skip_mode and line.startswith("--- "): # Kolejna sensowna sekcja
                skip_mode = False
                
            if not skip_mode:
                clean_lines.append(line)
                
        return clean_lines

    # 4. Budowanie struktury HTML
    html_content = [
        "<!DOCTYPE html>",
        '<html lang="ru">', 
        "<head>",
        '  <meta charset="utf-8">',
        "  <title>Отчёт: Анализ текста</title>",
        "  <style>",
        "    body { font-family: Arial, sans-serif; line-height: 1.6; max-width: 900px; margin: 2rem auto; padding: 0 1rem; color: #333; }",
        "    h1, h2, h3 { color: #2c3e50; margin-top: 2rem; }",
        "    .output-box { background: #f8f9fa; border-left: 4px solid #007bff; padding: 1rem; margin-bottom: 1.5rem; overflow-x: auto; font-family: Consolas, monospace; white-space: pre-wrap; }",
        "    .markdown-cell { margin-bottom: 1.5rem; }",
        "  </style>",
        "</head>",
        "<body>",
        '<main>'
    ]

    # 5. Przetwarzanie komórek
    for cell in nb.get("cells", []):
        cell_id = cell.get("id", "")
        
        if cell_id in ["md_qa_rag", "cell_qa_rag"]:
            continue

        if cell["cell_type"] == "markdown":
            source = "".join(cell.get("source", []))
            md_html = markdown.markdown(source)
            # 1. Per-<code> lingua: dla każdego elementu <code>/<pre><code>
            #    wykrywamy język (en/pl/ru/it/fi/is) z fallbackiem en.
            md_html = _tag_code_blocks(md_html)
            # 2. EN-hardkod dla narracji rosyjskiej: nazwy bibliotek, akronimy
            #    (PDF, HTML, NER, BoW, ...), czytniki ekranu (NVDA, JAWS),
            #    POS-tagi w tekście. Skipuje wnętrza <span lang="..."> i <code>.
            md_html = _apply_outside_spans(md_html, EN_HARDCODE_PATTERNS)
            # 3. Lingua-fallback dla pozostałych nazw własnych w narracji
            #    (np. polsko/fińskie segmenty w opisach), z heurystykami
            #    Python-identifier i CamelCase → en.
            md_html = _lingua_word_fallback(md_html, document_lang="ru")
            # 4. Scal sąsiadujące same-lang spany (TF-IDF, UTF-8 itp.).
            md_html = _coalesce_same_lang_spans(md_html)
            html_content.append(f'<div class="markdown-cell">\n{md_html}\n</div>')

        elif cell["cell_type"] == "code":
            outputs = cell.get("outputs", [])
            if not outputs:
                continue
            
            cell_text_output = ""
            for out in outputs:
                if out.get("output_type") == "stream" and out.get("name") == "stdout":
                    cell_text_output += "".join(out.get("text", []))
                elif out.get("output_type") == "execute_result":
                    cell_text_output += "".join(out.get("data", {}).get("text/plain", []))

            if cell_text_output.strip():
                # Oczyszczenie z szumu
                lines = cell_text_output.split('\n')
                cleaned_lines = clean_noise(lines)
                clean_text = '\n'.join(cleaned_lines)
                
                # Tagowanie
                tagged_output = tag_target_language(clean_text, target_lang)
                if tagged_output.strip():
                    html_content.append(f'<div class="output-box" aria-label="Вывод системы">\n{tagged_output}\n</div>')

    html_content.extend([
        "</main>",
        "</body>",
        "</html>"
    ])

    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write("\n".join(html_content))
    
    print(f"[OK] Pomyślnie wygenerowano dostępny raport HTML: {OUTPUT_HTML}")
    print(f"[INFO] Rozpoznany język docelowy tekstu do tagowania: {target_lang}")
    if REMOVE_NOISE:
        print("[INFO] Tryb usuwania technicznego szumu (lematyzacja, POS, logi) jest AKTYWNY.")

if __name__ == "__main__":
    build_accessible_html()