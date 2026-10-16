#!/usr/bin/env python
"""audyt_podstaw.py — audyt PODSTAW języków przed wydaniem (krok w release.yml).

Kanon (z Reżysera): dwie strony tej samej umowy liczą jedną enumeracją, a lista
języków wypisana ręcznie w Pythonie jest wzorcem defektu. Od 2026-10-16 język
w ATA jest wyliczony w JEDNYM miejscu: `dictionaries/<kod>/podstawy.yaml`
(loader i pochodne: `shamanic_locale.PODSTAWY`). Ten audyt pilnuje, żeby tak
zostało i żeby podstawy mówiły prawdę.

  1. KOMPLET   — każdy katalog `dictionaries/<kod>/` ma podstawy ze wszystkimi
                 polami `shamanic_locale.POLA_PODSTAW` (pusta wartość to
                 deklaracja, brak klucza to błąd).
  2. TREŚĆ     — `jezyk` == katalog; `lingua` to członek `lingua.Language` o tym
                 samym kodzie ISO (lingua MUSI być zainstalowana); `locale`
                 zaczyna się od `<kod>-`; alfabet wielkimi literami bez
                 powtórzeń; diakrytyki ⊂ alfabet; skrótowce z kropką, a wzorzec
                 wieloczłonowego scala jego rozstrzelony zapis; znaczniki
                 struktury wielkimi literami.
  3. README    — `README_<kod>.md` dla każdego kodu poza `en` i żadnego innego.
  4. SONDA spaCy — dla `spacy: null` szuka `<kod>_core_(news|web)_(sm|md|lg|trf)`
                 w indeksie modeli spaCy (`compatibility.json` z
                 explosion/spacy-models, ten sam co `spacy download`) i na
                 dysku; znaleziony = błąd z poleceniem, co dopisać. Model
                 zadeklarowany musi w indeksie istnieć. Niczego nie instaluje.
  5. NAWRÓT    — w żadnym `*.py` z korzenia nie wraca `Language.<NAZWA>` ani
                 literał wyliczający języki (słownik z ≥2 kluczami-kodami,
                 kolekcja z ≥3 kodami). Wyjątek punktowy: komentarz
                 `# audyt-podstaw: ok — <powód>` na linii literału.

Wynik: exit 0 = OK, exit 1 = błędy (każdy jako ::error), exit 2 = plik się nie
parsuje, exit 3 = indeksu spaCy nie da się pobrać — „cannot verify”, które
BLOKUJE wydanie (decyzja maintainera 2026-10-16: nigdy fałszywe zielone).
Uruchom:  .venv/Scripts/python .github/scripts/audyt_podstaw.py
Wymaga PyYAML i lingua-language-detector.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import re
import sys
import urllib.request
from pathlib import Path

KORZEN = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KORZEN))
try:
    import shamanic_locale as sl  # noqa: E402  (wczytuje podstawy już przy imporcie)
except ValueError as _e:  # BladPodstaw z importu — zgłoś jak każdy inny błąd audytu
    print(f"::error::{_e}")
    sys.exit(1)

README_WZORCA = "en"   # README.md bez sufiksu jest po angielsku
INDEKS_SPACY = "https://raw.githubusercontent.com/explosion/spacy-models/master/compatibility.json"
_WYJATEK = re.compile(r"#\s*audyt-podstaw:\s*ok\s*[—–-]+\s*\S")


class BladParsowania(Exception):
    pass


class BladSondy(Exception):
    pass


# ── 1–2. komplet i treść ──────────────────────────────────────────

def _lingua_kod(nazwa: str) -> str | None:
    from lingua import Language
    czlonek = getattr(Language, nazwa, None)
    return czlonek.iso_code_639_1.name.lower() if czlonek is not None else None


def bledy_podstaw(katalog: Path) -> tuple[dict, list[str]]:
    try:
        podstawy = sl.wczytaj_podstawy(katalog)
    except sl.BladPodstaw as e:
        return {}, [str(e)]
    bledy = []
    for kod, p in podstawy.items():
        gdzie = f"dictionaries/{kod}/{sl.PLIK_PODSTAW}"
        if p["jezyk"] != kod:
            bledy.append(f"{gdzie}: jezyk '{p['jezyk']}' != folder '{kod}'")
        iso = _lingua_kod(p["lingua"])
        if iso is None:
            bledy.append(f"{gdzie}: lingua '{p['lingua']}' is not a lingua.Language member")
        elif iso != kod:
            bledy.append(f"{gdzie}: lingua '{p['lingua']}' is ISO '{iso}', not '{kod}'")
        if not p["locale"].startswith(f"{kod}-"):
            bledy.append(f"{gdzie}: locale '{p['locale']}' does not start with '{kod}-'")
        a = p["alfabet"]
        if not a or a != a.upper() or not a.isalpha() or len(set(a)) != len(a):
            bledy.append(f"{gdzie}: alfabet must be unique UPPERCASE letters")
        d = p["diakrytyki"]
        if d != d.lower() or not set(d) <= set(a.lower()):
            bledy.append(f"{gdzie}: diakrytyki must be lowercase letters of alfabet")
        for s in p["skrotowce"]:
            if not isinstance(s, str) or "." not in s or not all(
                    c.isalpha() for c in re.split(r"[\s.]+", s) if c):
                bledy.append(f"{gdzie}: skrotowiec {s!r} must be letters with at least one dot")
                continue
            wzor = sl.wzorzec_skrotowca(s)
            if wzor:
                rozstrzelony = re.sub(r"\.(?=[^\s.])", ". ", s)
                if re.sub(wzor, s, rozstrzelony) != s:
                    bledy.append(f"{gdzie}: pattern for {s!r} does not join {rozstrzelony!r}")
        for s in p["naglowki_struktury"]:
            if not isinstance(s, str) or s != s.upper() or not s.isalpha():
                bledy.append(f"{gdzie}: naglowki_struktury entry {s!r} must be one UPPERCASE word")
        for pole in ("stopfrazy_powiazane", "nav_slowa", "nav_rdzenie"):
            for s in p[pole]:
                if not isinstance(s, str) or not s.strip() or s != s.lower():
                    bledy.append(f"{gdzie}: {pole} entry {s!r} must be non-empty lowercase text")
    return podstawy, bledy


# ── 3. README ─────────────────────────────────────────────────────

def bledy_readme(korzen: Path, kody: set[str]) -> list[str]:
    bledy = [f"README_{k}.md missing" for k in sorted(kody - {README_WZORCA})
             if not (korzen / f"README_{k}.md").exists()]
    for p in sorted(korzen.glob("README_*.md")):
        kod = p.stem.removeprefix("README_")
        if kod not in kody or kod == README_WZORCA:
            bledy.append(f"{p.name}: '{kod}' is not a translated language in dictionaries/")
    return bledy


# ── 4. sonda spaCy ────────────────────────────────────────────────

def pobierz_indeks(url: str = INDEKS_SPACY) -> dict[str, set[str]]:
    """{model: {wersje spaCy}}; każdy problem z siecią/formatem = BladSondy."""
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            dane = json.load(r)
        wynik: dict[str, set[str]] = {}
        for wersja, modele in dane["spacy"].items():
            for m in modele:
                wynik.setdefault(m, set()).add(wersja)
    except Exception as e:  # sieć, HTTP, JSON, nieoczekiwany kształt
        raise BladSondy(f"cannot verify spaCy models: {INDEKS_SPACY}: {e}") from e
    if not wynik:
        raise BladSondy(f"cannot verify spaCy models: {INDEKS_SPACY} lists no models")
    return wynik


def _zainstalowany(nazwa: str) -> bool:
    return importlib.util.find_spec(nazwa) is not None


def bledy_spacy(podstawy: dict, indeks: dict[str, set[str]], zainstalowany=_zainstalowany) -> list[str]:
    bledy = []
    for kod, p in sorted(podstawy.items()):
        gdzie = f"dictionaries/{kod}/{sl.PLIK_PODSTAW}"
        model = p["spacy"]
        if model is not None:
            if not model.startswith(f"{kod}_"):
                bledy.append(f"{gdzie}: spacy model '{model}' is not a '{kod}_' model")
            elif model not in indeks:
                bledy.append(f"{gdzie}: spacy model '{model}' is not in the spaCy model index")
            continue
        wzor = re.compile(rf"^{re.escape(kod)}_core_(news|web)_(sm|md|lg|trf)$")
        for m in sorted(m for m in indeks if wzor.match(m)):
            wersje = ", ".join(sorted(indeks[m]))
            bledy.append(f"{gdzie}: spaCy now publishes '{m}' (spaCy {wersje}) — set "
                         f"`spacy: {m}` here; the fallback branch for this language may be obsolete")
        for rozmiar in ("lg", "md", "sm", "trf"):
            for rodzaj in ("news", "web"):
                m = f"{kod}_core_{rodzaj}_{rozmiar}"
                if zainstalowany(m):
                    bledy.append(f"{gdzie}: '{m}' is installed on this machine but `spacy:` is "
                                 f"still null — set `spacy: {m}`")
    return bledy


# ── 5. nawrót wyliczeń ────────────────────────────────────────────

def bledy_wyliczen(korzen: Path, kody: set[str]) -> list[str]:
    bledy = []
    for plik in sorted(korzen.glob("*.py")):
        tekst = plik.read_text(encoding="utf-8")
        try:
            drzewo = ast.parse(tekst, plik.name)
        except SyntaxError as e:
            raise BladParsowania(f"{plik.name}: {e}") from e
        linie = tekst.splitlines()

        def zwolniony(wezel) -> bool:
            return any(_WYJATEK.search(linie[i - 1])
                       for i in range(wezel.lineno, (wezel.end_lineno or wezel.lineno) + 1))

        for n in ast.walk(drzewo):
            if (isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                    and n.value.id == "Language" and n.attr.isupper()):
                if not zwolniony(n):
                    bledy.append(f"{plik.name}:{n.lineno}: Language.{n.attr} — derive it from "
                                 f"podstawy (shamanic_locale.lingua_jezyki())")
                continue
            if isinstance(n, ast.Dict):
                elementy, prog, co = n.keys, 2, "dict keyed by"
            elif isinstance(n, (ast.Set, ast.List, ast.Tuple)):
                elementy, prog, co = n.elts, 3, "collection of"
            else:
                continue
            trafione = sorted({e.value for e in elementy if isinstance(e, ast.Constant)
                               and isinstance(e.value, str) and e.value in kody})
            if len(trafione) >= prog and not zwolniony(n):
                bledy.append(f"{plik.name}:{n.lineno}: {co} language codes {trafione} — "
                             f"move the data to dictionaries/<code>/podstawy.yaml")
    return bledy


def main() -> int:
    katalog = KORZEN / "dictionaries"
    try:
        podstawy, bledy = bledy_podstaw(katalog)
        kody = set(podstawy) or {p.name for p in katalog.iterdir() if p.is_dir()}
        bledy += bledy_readme(KORZEN, kody) + bledy_wyliczen(KORZEN, kody)
        if podstawy:
            bledy += bledy_spacy(podstawy, pobierz_indeks())
    except BladParsowania as e:
        print(f"::error::{e}")
        return 2
    except BladSondy as e:
        print(f"::error::{e} — the release stays blocked until the index can be read")
        return 3
    for b in bledy:
        print(f"::error::{b}")
    print(f"Language basics ({', '.join(sorted(kody))}): "
          f"{'OK' if not bledy else f'{len(bledy)} problem(s)'}")
    return 1 if bledy else 0


if __name__ == "__main__":
    sys.exit(main())
