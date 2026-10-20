import csv
import json
import re
from functools import lru_cache
from pathlib import Path

import yaml

_DICT_ROOT = Path(__file__).resolve().parent / 'dictionaries'

# ── PODSTAWY JĘZYKÓW (od 2026-10-16) ─────────────────────────────
# Zbiór obsługiwanych języków = katalogi dictionaries/<kod>/ z plikiem
# podstawy.yaml; to JEDYNE miejsce, w którym język jest wyliczony. Notatnik,
# generate_report i ten moduł liczą swoje mapy z PODSTAWY — mapa języków
# wypisana ręcznie w kodzie to wzorzec defektu (siódmy język cicho spadał
# na angielskie fallbacki). Brak pliku albo pola = wyjątek przy imporcie,
# nie cichy fallback; `.github/scripts/audyt_podstaw.py` sprawdza resztę.
# Opis pól: dictionaries/pl/podstawy.yaml.
POLA_PODSTAW = {
    'jezyk': str, 'lingua': str, 'nazwa_ru': str, 'locale': str,
    'spacy': (str, type(None)), 'alfabet': str, 'diakrytyki': str,
    'skrotowce': list, 'skrotowce_kodu': list, 'naglowki_struktury': list,
    'stopfrazy_powiazane': list, 'nav_slowa': list, 'nav_rdzenie': list,
}
PLIK_PODSTAW = 'podstawy.yaml'


class BladPodstaw(ValueError):
    """Niekompletne albo niespójne podstawy języka."""


def _katalogi_jezykow(root):
    """Katalogi języków; `_szkice/`, `.cache/` itp. nie są językami."""
    return sorted(p for p in Path(root).iterdir()
                  if p.is_dir() and not p.name.startswith(('_', '.')))


def wczytaj_podstawy(root=_DICT_ROOT):
    """{kod: dane} dla każdego katalogu języka w `root`; brak pliku/pola = BladPodstaw.

    Przy imporcie modułu błąd kończy się stosem wywołań, a nie komunikatem
    przez t(): bez kompletnych podstaw nie ma listy języków, więc nie ma też
    języka interfejsu, w którym dałoby się go wypisać."""
    wynik = {}
    for katalog in _katalogi_jezykow(root):
        plik = katalog / PLIK_PODSTAW
        if not plik.is_file():
            raise BladPodstaw(f'{plik}: missing — every language needs its basics')
        with open(plik, 'r', encoding='utf-8') as f:
            dane = yaml.safe_load(f) or {}
        if not isinstance(dane, dict):
            raise BladPodstaw(f'{plik}: must be a mapping of fields, not {type(dane).__name__}')
        for pole, typ in POLA_PODSTAW.items():
            if pole not in dane:
                raise BladPodstaw(f'{plik}: field "{pole}" missing')
            if not isinstance(dane[pole], typ):
                wskazowka = (' — quote the value: YAML reads no/yes/on/off as booleans'
                             if isinstance(dane[pole], bool) else '')
                raise BladPodstaw(f'{plik}: field "{pole}" has type '
                                  f'{type(dane[pole]).__name__}{wskazowka}')
        wynik[katalog.name] = dane
    return wynik


PODSTAWY = wczytaj_podstawy()

# Nazwa języka w promptach rytuałów (shamanic_ai) = nazwa enuma lingua.
LANGUAGE_NAMES = {kod: p['lingua'].title() for kod, p in PODSTAWY.items()}


def lingua_jezyki():
    """Członkowie lingua.Language dla wszystkich języków z podstaw."""
    from lingua import Language
    return [getattr(Language, p['lingua']) for p in PODSTAWY.values()]


def kody_regex():
    """Alternatywa kodów języków do wnętrza grupy regexu („en|fi…”)."""
    return '|'.join(sorted(PODSTAWY))


def nazwy_regex():
    """Alternatywa angielskich nazw języków: „English|Finnish|…”."""
    return '|'.join(sorted(LANGUAGE_NAMES.values()))


def _klasa(litery):
    return ''.join(re.escape(z) for z in dict.fromkeys(litery))


# Token TF-IDF: ≥2 dowolne LITERY (nie tylko alfabetu korpusu — „tšekki”,
# „Müller”, „łódź” w tekście islandzkim to też słowa), łącznik i apostrof
# tylko MIĘDZY literami („itä-suome”, którą omorfi celowo trzyma razem,
# „dell'anno”). Bez cyfr i podkreślnika. Wzorzec z alfabetu (2026-10-16)
# gubił całe słowa — kanon: nadmierne czyszczenie jest gorsze niż śmieci.
_LITERA = r"[^\W\d_]"
WZORZEC_TOKENOW = rf"(?u)\b{_LITERA}(?:{_LITERA}|[-'’](?={_LITERA}))+\b"


def wielkie_litery():
    """Klasa wielkich liter wszystkich języków (do wnętrza [...] regexu)."""
    return _klasa(''.join(p['alfabet'] for p in PODSTAWY.values()))


@lru_cache(maxsize=1)
def alfabety_paczek():
    """Litery KAŻDEJ paczki osobno (obie wielkości) — parametr `alfabety`
    wspólnego modułu `czyszczenie_tekstu` (mojibake: słowo jest wiarygodne,
    gdy wszystkie jego litery mieszczą się w alfabecie jednej paczki).

    Odpowiednik Reżysera (`alfabet` + litery `gui/ui.yaml`): `alfabet` z
    `podstawy.yaml` plus litery natywnych tekstów paczki — pozostałych plików
    `dictionaries/<kod>/*.yaml` (wartości tekstowe). Sam `alfabet` ru to czysta cyrylica, a druk
    przedreformowy bywa zapisany z łacińskim „h” za „ѣ” („вhка”): z samym
    alfabetem 119 linii „Повести о Горе-Злочастии” nie przechodziło progu
    mojibake (zmierzone 2026-10-20). `podstawy.yaml` w całości odpada jak
    u Reżysera (opisy pól)."""
    def napisy(w):
        if isinstance(w, str):
            yield w
        elif isinstance(w, dict):
            for v in w.values():
                yield from napisy(v)
        elif isinstance(w, list):
            for v in w:
                yield from napisy(v)

    wynik = []
    for kod, p in PODSTAWY.items():
        tekst = p['alfabet']
        for plik in sorted((_DICT_ROOT / kod).glob('*.yaml')):
            if plik.name != 'podstawy.yaml':
                # Wartości, nie surowy plik: komentarze YAML są po polsku i
                # dawały każdej paczce „ĆĘŁŃŚ”.
                tekst += ''.join(napisy(yaml.safe_load(plik.read_text(encoding='utf-8'))))
        litery = set()
        for z in set(tekst):
            if z.isalpha():
                litery.add(z)
                litery.update(z.upper())
                litery.update(z.lower())
        wynik.append(frozenset(litery))
    return wynik


def diakrytyki(kod):
    d = PODSTAWY[kod]['diakrytyki']
    return d + d.upper()


_CZLONY = re.compile(r'[^\s.]+|\.|\s+')
# Odstęp wewnątrz skrótowca: spacje/tabulatory i NAJWYŻEJ jeden koniec linii
# — pusta linia to granica akapitu, nie rozstrzelony skrót.
_ODSTEP = r'[ \t]*(?:\r?\n)?[ \t]*'


def _czlony(skrot):
    return _CZLONY.findall(skrot)


def wzorzec_skrotowca(skrot):
    """Regex scalający rozstrzelony zapis skrótowca wieloczłonowego
    („m. in.” → „m.in.”, „и  т. д.” → „и т.д.”) albo None dla jednoczłonowego.
    Kropki są OBOWIĄZKOWE — luźniejszy wzorzec trafia w zwykłe słowa prozy."""
    czlony = _czlony(skrot)
    if sum(1 for c in czlony if c != '.' and not c.isspace()) < 2:
        return None
    wzor = r'\b'
    for i, c in enumerate(czlony):
        if c == '.':
            wzor += r'\.' if i == len(czlony) - 1 else r'\.' + _ODSTEP
        elif c.isspace():
            wzor += r'(?=\s)' + _ODSTEP
        else:
            wzor += re.escape(c)
    if not skrot.endswith('.'):
        wzor += r'\b'
    return wzor


def wzorce_skrotowcow(kod):
    """[(regex, forma kanoniczna)] dla języka, najdłuższe formy najpierw."""
    pary = [(wzorzec_skrotowca(s), s) for s in PODSTAWY[kod]['skrotowce']]
    return sorted(((w, s) for w, s in pary if w), key=lambda p: -len(p[1]))


def _warianty(skrot, bez_kropki):
    rozstrzelony = re.sub(r'\.(?=[^\s.])', '. ', skrot)
    warianty = {skrot, rozstrzelony}
    if bez_kropki:
        warianty |= {w.rstrip('.') for w in warianty}
    return warianty


def warianty_skrotowcow():
    """{kod: frozenset zapisów} rozpoznających język krótkiego fragmentu <code>.

    Wchodzą: skrótowce WIELOCZŁONOWE (m.in., т.е., u.þ.b. — typograficznie
    jednoznaczne) oraz jednoczłonowe wpisane do `skrotowce_kodu` (np., etc.),
    każdy także bez kropki końcowej. Pozostałe jednoczłonowe (os., str., n.,
    v.) wyglądają jak kod Pythona albo pojedyncza litera, więc nie wchodzą.
    Zapis wspólny dwóm językom wypada ze wszystkich — decyduje wtedy lingua."""
    per_jezyk = {}
    for kod, p in PODSTAWY.items():
        zbior = set()
        for s in p['skrotowce']:
            if wzorzec_skrotowca(s) or s in p['skrotowce_kodu']:
                zbior |= _warianty(s, bez_kropki=True)
        per_jezyk[kod] = zbior
    licznik = {}
    for zbior in per_jezyk.values():
        for w in zbior:
            licznik[w] = licznik.get(w, 0) + 1
    return {kod: frozenset(w for w in zbior if licznik[w] == 1)
            for kod, zbior in per_jezyk.items()}


def naglowki_struktury():
    """Suma słów-znaczników struktury ze wszystkich języków, najdłuższe najpierw."""
    slowa = {s for p in PODSTAWY.values() for s in p['naglowki_struktury']}
    return sorted(slowa, key=lambda s: (-len(s), s))


def stopfrazy_powiazane():
    return sorted({s for p in PODSTAWY.values() for s in p['stopfrazy_powiazane']})


def nav_slowa():
    return frozenset(s for p in PODSTAWY.values() for s in p['nav_slowa'])


def nav_rdzenie():
    return tuple(sorted({s for p in PODSTAWY.values() for s in p['nav_rdzenie']}))


# Katalog z YAML-owymi słownikami i18n. Struktura: dictionaries/{lang}/*.yaml.
# Każdy plik to gniazdowany mapping; klucze hierarchiczne (np. prophecy.fallback.loc)
# są spłaszczane przy ładowaniu — dzięki temu zachowujemy istniejące API t().
#
# Uwaga gramatyczna: dla fi/is encje z entities.csv są już w deklinacji
# (Euroopassa, Yhdysvaltoihin, staðnum...). Bez prawdziwej morfologii nie da się
# ich odmienić z powrotem do mianownika, więc szablony fi/is używają prefiksów
# nominalnych (paikan {loc}, staðnum {loc}, hahmon {per} kautta itp.) —
# brzmi to jak nagłówek mantry, ale jest gramatycznie bezpieczne.
# (_DICT_ROOT jest zdefiniowany wyżej, przy podstawach.) podstawy.yaml to dane
# o języku, nie napisy — nie trafiają do bundle'a t().


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
        if yaml_path.name == PLIK_PODSTAW:
            continue
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


def get_ui_lang(default='en'):
    """Wczytaj `ui_lang` z config.json / config.ini i znormalizuj do kodu ISO 639-1
    ze zbioru obsługiwanych języków. Pusty string, brak klucza lub nieznany
    kod -> zwracamy `default` ('en' wg konwencji v1.1).

    Konsumenci: shamanic_pipeline, shamanic_ai, generate_report, generate_md
    i notebook (cell_corpus) wczytują przez ten helper, żeby UI był spójny."""
    for name in ('config.json', 'config.ini'):
        p = Path(name)
        if not p.is_file():
            continue
        try:
            with open(p, 'r', encoding='utf-8-sig') as f:
                cfg = json.load(f)
        except (OSError, json.JSONDecodeError):
            break
        raw = (cfg.get('ui_lang') or '').strip().lower()
        return raw if raw in LANGUAGE_NAMES else default
    return default


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
            from lingua import LanguageDetectorBuilder
            detector = LanguageDetectorBuilder.from_languages(*lingua_jezyki()).build()
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
