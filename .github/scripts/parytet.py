#!/usr/bin/env python
"""parytet.py — bramka parytetu tłumaczeń przed wydaniem (krok w release.yml).

Odpowiednik bramek rodziny `buduj_wielojezyczne` z Reżysera, bez tłumaczy:
w ATA tłumaczenia pisze się ręcznie (192 klucze × 6 języków, README ×6 bez
szablonów — inwentaryzacja 2026-10-15), więc pilnujemy tego, co mechanicznie
sprawdzalne:

  1. KLUCZE    — każdy `dictionaries/<język>/<plik>.yaml` ma ten sam zbiór kluczy
                 co `pl` (polski jest wzorcem, jak w Reżyserze);
  2. PLACEHOLDERY — dla każdego klucza ten sam multizbiór `{nazwa}` we wszystkich
                 językach (zgubiony placeholder = KeyError albo dziura w tekście);
  3. README    — każde `README_*.md` ma tyle samo nagłówków, bloków kodu i linków
                 co `README.md`, a bloki kodu są IDENTYCZNE po pominięciu linii
                 komentarzy (komentarze się tłumaczy, polecenia i JSON — nie).

Wynik: exit 0 = parytet, exit 1 = rozjazd (każdy wypisany jako ::error).
Uruchom lokalnie:  python .github/scripts/parytet.py   (z korzenia repo; wymaga PyYAML)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

KORZEN = Path(__file__).resolve().parents[2]
WZORZEC = "pl"
_PH = re.compile(r"\{[a-z_0-9]+\}")
_BLOK = re.compile(r"```.*?```", re.S)


def plaskie(wezel, prefiks=""):
    wynik = {}
    for k, v in (wezel or {}).items():
        klucz = f"{prefiks}{k}"
        wynik.update(plaskie(v, klucz + ".") if isinstance(v, dict) else {klucz: v})
    return wynik


def bledy_slownikow(katalog: Path) -> list[str]:
    jezyki = sorted(p.name for p in katalog.iterdir() if p.is_dir())
    if WZORZEC not in jezyki:
        return [f"no reference pack dictionaries/{WZORZEC}"]
    bledy = []
    for plik in sorted(p.name for p in (katalog / WZORZEC).glob("*.yaml")):
        wzor = plaskie(yaml.safe_load((katalog / WZORZEC / plik).read_text(encoding="utf-8")))
        for j in jezyki:
            sciezka = katalog / j / plik
            if not sciezka.exists():
                bledy.append(f"dictionaries/{j}/{plik}: file missing")
                continue
            inny = plaskie(yaml.safe_load(sciezka.read_text(encoding="utf-8")))
            for k in sorted(set(wzor) - set(inny)):
                bledy.append(f"dictionaries/{j}/{plik}: key missing: {k}")
            for k in sorted(set(inny) - set(wzor)):
                bledy.append(f"dictionaries/{j}/{plik}: key not in {WZORZEC}: {k}")
            for k in sorted(set(wzor) & set(inny)):
                a, b = sorted(_PH.findall(str(wzor[k]))), sorted(_PH.findall(str(inny[k])))
                if a != b:
                    bledy.append(f"dictionaries/{j}/{plik}: {k}: placeholders {b} != {WZORZEC} {a}")
    return bledy


def _bez_komentarzy(blok: str) -> list[str]:
    return [linia.split(" #")[0].rstrip() for linia in blok.splitlines()
            if not linia.strip().startswith(("#", "//"))]


def _struktura(tekst: str) -> dict:
    return {"headings": len(re.findall(r"^#+ ", tekst, re.M)),
            "code blocks": len(_BLOK.findall(tekst)),
            "links": len(re.findall(r"\]\(", tekst))}


def bledy_readme(katalog: Path) -> list[str]:
    en = (katalog / "README.md").read_text(encoding="utf-8")
    bledy = []
    for sciezka in sorted(katalog.glob("README_*.md")):
        t = sciezka.read_text(encoding="utf-8")
        for miara, ile in _struktura(t).items():
            if ile != _struktura(en)[miara]:
                bledy.append(f"{sciezka.name}: {miara} {ile} != README.md {_struktura(en)[miara]}")
        for i, (a, b) in enumerate(zip(_BLOK.findall(en), _BLOK.findall(t)), 1):
            if _bez_komentarzy(a) != _bez_komentarzy(b):
                bledy.append(f"{sciezka.name}: code block {i} differs from README.md outside comments")
    return bledy


def main() -> int:
    bledy = bledy_slownikow(KORZEN / "dictionaries") + bledy_readme(KORZEN)
    for b in bledy:
        print(f"::error::{b}")
    print(f"Translation parity: {'OK' if not bledy else f'{len(bledy)} problem(s)'}")
    return 1 if bledy else 0


if __name__ == "__main__":
    sys.exit(main())
