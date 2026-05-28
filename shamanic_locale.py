import csv
import re
from functools import lru_cache
from pathlib import Path

import yaml

# Wsparcie dla języków zgodnie z notebookiem (cell_langdet -> SUPPORTED_LANGS).
LANGUAGE_NAMES = {
    'pl': 'Polish',
    'en': 'English',
    'ru': 'Russian',
    'fi': 'Finnish',
    'is': 'Icelandic',
    'it': 'Italian',
}

# Katalog z YAML-owymi słownikami i18n. Struktura: dictionaries/{lang}/*.yaml.
# Każdy plik to gniazdowany mapping; klucze hierarchiczne (np. prophecy.fallback.loc)
# są spłaszczane przy ładowaniu — dzięki temu zachowujemy istniejące API t().
#
# Uwaga gramatyczna: dla fi/is encje z entities.csv są już w deklinacji
# (Euroopassa, Yhdysvaltoihin, staðnum...). Bez prawdziwej morfologii nie da się
# ich odmienić z powrotem do mianownika, więc szablony fi/is używają prefiksów
# nominalnych (paikan {loc}, staðnum {loc}, hahmon {per} kautta itp.) —
# brzmi to jak nagłówek mantry, ale jest gramatycznie bezpieczne.
_DICT_ROOT = Path(__file__).resolve().parent / 'dictionaries'


def _flatten(node, prefix=''):
    """Spłaszcz zagnieżdżone mappingi do kluczy 'a.b.c'.
    Listy i skalary pozostają jako wartości — nie schodzimy w głąb list."""
    if not isinstance(node, dict):
        return {prefix: node}
    out = {}
    for k, v in node.items():
        key = f'{prefix}.{k}' if prefix else str(k)
        if isinstance(v, dict):
            out.update(_flatten(v, key))
        else:
            out[key] = v
    return out


@lru_cache(maxsize=8)
def _load_bundle(lang):
    """Załaduj wszystkie YAML-e z dictionaries/{lang}/ i zwróć spłaszczony bundle.
    Brak katalogu = pusty bundle (t() spróbuje fallbacku na 'en')."""
    lang_dir = _DICT_ROOT / lang
    if not lang_dir.is_dir():
        return {}
    bundle = {}
    for yaml_path in sorted(lang_dir.glob('*.yaml')):
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError):
            continue
        bundle.update(_flatten(data))
    return bundle


def t(lang, key, **kwargs):
    """Pobierz string z bundle'a. Fallback przez en jeśli klucza brak w lang."""
    bundle = _load_bundle(lang)
    value = bundle.get(key) if bundle else None
    if value is None:
        value = _load_bundle('en').get(key, '')
    if kwargs and isinstance(value, str):
        return value.format(**kwargs)
    return value


_HTML_LANG_RE = re.compile(r'<html\s+lang="([a-z]{2})"', re.IGNORECASE)


def detect_corpus_lang(export_dir, default='en'):
    """Wykryj język korpusu (ISO 639-1 ograniczone do LANGUAGE_NAMES).

    Kolejność źródeł:
    1. atrybut <html lang="..."> z accessible_text.html (zapisane przez notebook),
    2. lingua-language-detector na pierwszych ~30 zdaniach z sentences.csv,
    3. fallback `default` ('en').
    """
    export_dir = Path(export_dir)
    html_path = export_dir / 'accessible_text.html'
    if html_path.exists():
        try:
            head = html_path.read_text(encoding='utf-8', errors='ignore')[:512]
            m = _HTML_LANG_RE.search(head)
            if m:
                code = m.group(1).lower()
                if code in LANGUAGE_NAMES:
                    return code
        except OSError:
            pass

    sentences_path = export_dir / 'sentences.csv'
    if sentences_path.exists():
        try:
            from lingua import Language, LanguageDetectorBuilder
            detector = LanguageDetectorBuilder.from_languages(
                Language.ENGLISH, Language.POLISH, Language.RUSSIAN,
                Language.ITALIAN, Language.FINNISH, Language.ICELANDIC,
            ).build()
            sample_parts = []
            with open(sentences_path, 'r', encoding='utf-8-sig') as f:
                for i, row in enumerate(csv.DictReader(f)):
                    if i >= 30:
                        break
                    sample_parts.append(row.get('sentence', ''))
            lang_obj = detector.detect_language_of(' '.join(sample_parts))
            if lang_obj is not None:
                code = lang_obj.iso_code_639_1.name.lower()
                if code in LANGUAGE_NAMES:
                    return code
        except Exception:
            pass

    return default
