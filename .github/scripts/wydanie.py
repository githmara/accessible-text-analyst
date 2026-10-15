#!/usr/bin/env python
"""wydanie.py — decyzja i treść wydania z `release_notes.md` + listy tagów.

Wołany przez `.github/workflows/release.yml`. Tylko stdlib, bez sieci: listę
tagów podaje workflow (`git ls-remote --tags origin`), więc całą logikę da się
sprawdzić lokalnie (`python .github/scripts/test_wydanie.py`).

Źródło prawdy o wersji jest JEDNO: pierwsza sekcja `## vX.Y.Z — tytuł`
w `release_notes.md`. Plik VERSION celowo nie istnieje — projekt jest
source-only, nie ma czego w nim numerować poza notatkami i tagiem.

Decyzja (wypisywana jako `decyzja=` do $GITHUB_OUTPUT):
  pomin    tag tej wersji już istnieje — wydanie było, nic do zrobienia;
  wydaj    tagu nie ma, a wersja jest WYŻSZA od każdego istniejącego tagu;
  (błąd)   wersja nie wyższa od najnowszego tagu, zły nagłówek, pusta treść.

Bezpieczeństwo: treść notatek jest DANYMI. Wersja przechodzi ścisły wzorzec,
zanim gdziekolwiek trafi; tytuł i treść idą do plików, nigdy do powłoki.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

PLIK_NOTATEK = "release_notes.md"
# Nagłówek sekcji: `## v1.8.0 — tytuł`. Myślnik może być długi albo zwykły.
_NAGLOWEK = re.compile(r"^## (v(\d+)\.(\d+)\.(\d+)) [—-] (\S.*)$", re.MULTILINE)
_TAG = re.compile(r"^refs/tags/v(\d+)\.(\d+)(?:\.(\d+))?$")


class BladWydania(Exception):
    """Workflow kończy się błędem z tym komunikatem (po angielsku)."""


def pierwsza_sekcja(notatki: str) -> tuple[str, tuple[int, int, int], str, str]:
    """(tag, wersja, tytuł, treść) pierwszej sekcji `## vX.Y.Z — …`."""
    m = _NAGLOWEK.search(notatki)
    if not m:
        raise BladWydania("no '## vX.Y.Z — title' section in release_notes.md")
    tag = m.group(1)
    wersja = (int(m.group(2)), int(m.group(3)), int(m.group(4)))
    tytul = f"{tag} — {m.group(5).strip()}"
    reszta = notatki[m.end():]
    nastepna = re.search(r"^## v\d", reszta, re.MULTILINE)
    tresc = reszta[:nastepna.start()] if nastepna else reszta
    # `---` należy MIĘDZY sekcje, nie do treści wydania (lekcja z Reżysera).
    tresc = re.sub(r"(?:^|\n)-{3,}\s*$", "", tresc.strip()).strip()
    if not tresc:
        raise BladWydania(f"section {tag} has no body")
    return tag, wersja, tytul, tresc


def wersje_tagow(ls_remote: str) -> set[tuple[int, int, int]]:
    """Wersje z wyjścia `git ls-remote --tags` (`v1.0` = 1.0.0; `^{}` pomijane)."""
    wynik = set()
    for linia in ls_remote.splitlines():
        czesci = linia.split()
        if len(czesci) != 2:
            continue
        m = _TAG.match(czesci[1])
        if m:
            wynik.add((int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)))
    return wynik


def decyzja(wersja: tuple[int, int, int], tagi: set[tuple[int, int, int]]) -> str:
    if wersja in tagi:
        return "pomin"
    if tagi and wersja <= max(tagi):
        najnowsza = ".".join(map(str, max(tagi)))
        raise BladWydania(
            f"v{'.'.join(map(str, wersja))} is not newer than the latest tag v{najnowsza}"
            " — refusing to release out of order")
    return "wydaj"


def main() -> int:
    katalog = Path(os.environ.get("RUNNER_TEMP", "."))
    ls_remote = Path(sys.argv[1]).read_text(encoding="utf-8")
    try:
        tag, wersja, tytul, tresc = pierwsza_sekcja(Path(PLIK_NOTATEK).read_text(encoding="utf-8"))
        wynik = decyzja(wersja, wersje_tagow(ls_remote))
    except BladWydania as exc:
        print(f"::error::{exc}")
        return 1
    (katalog / "tytul.txt").write_text(tytul, encoding="utf-8")
    (katalog / "tresc.md").write_text(tresc + "\n", encoding="utf-8")
    wyjscie = os.environ.get("GITHUB_OUTPUT")
    linie = f"decyzja={wynik}\ntag={tag}\n"
    if wyjscie:
        with open(wyjscie, "a", encoding="utf-8") as f:
            f.write(linie)
    print(linie.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
