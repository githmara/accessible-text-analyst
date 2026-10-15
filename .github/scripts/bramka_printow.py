#!/usr/bin/env python
"""bramka_printow.py — bramka hard-kodów w konsoli skryptów (krok w release.yml).

Kanon (CLAUDE.md, „Two languages, one module”): w skryptach samodzielnych
`print()` ≡ `t(UI_LANG, …)` — operator czyta konsolę w języku interfejsu
z configu, nie w języku, w którym ktoś akurat pisał kod. Reguła żyła dotąd
wyłącznie w dokumentacji; ta bramka robi z niej warunek wydania.

Co sprawdza (AST, bez uruchamiania kodu): każdy argument pozycyjny `print()`
w każdym `*.py` z korzenia repo. Naruszeniem jest literał tekstowy zawierający
LITERĘ (dowolnego alfabetu), także jako stała część f-stringa albo składnik
konkatenacji — o ile nie leży wewnątrz wywołania `t(…)` / `tr(…)` (klucz
tłumaczenia to też literał z literami, ale on jest właśnie drogą przez `t`).
Literały bez liter (wcięcia, „ - ”, dwukropki, puste `print()`) przechodzą.

Zakres jest wyprowadzany, nie wyliczany: NOWY skrypt w korzeniu trafia pod
bramkę sam. Wyłączony jest wyłącznie notatnik (`accessible_text_analyst.py`,
para jupytext) — jego stdout jest CELOWO rosyjski (CLAUDE.md, „Notebook
localization scope”). Skrypty w `.github/scripts/` to narzędzia CI, nie konsola
operatora.

Wyjątek punktowy: komentarz `# bramka-printow: ok — <powód>` na linii z
`print(`. Powód jest obowiązkowy — bez niego wyjątek się nie liczy.

Wynik: exit 0 = czysto, exit 1 = naruszenia (każde jako ::error), exit 2 = plik
nie parsuje się. Uruchom lokalnie:  python .github/scripts/bramka_printow.py
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

KORZEN = Path(__file__).resolve().parents[2]
WYLACZONE = {"accessible_text_analyst.py"}
FUNKCJE_TLUMACZACE = {"t", "tr"}
_WYJATEK = re.compile(r"#\s*bramka-printow:\s*ok\s*[—–-]+\s*\S")


def _ma_litere(tekst: str) -> bool:
    return any(z.isalpha() for z in tekst)


def _literaly(wezel: ast.AST):
    """Stałe tekstowe w wyrażeniu, z pominięciem poddrzew `t(…)` / `tr(…)`."""
    if isinstance(wezel, ast.Call):
        f = wezel.func
        nazwa = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)
        if nazwa in FUNKCJE_TLUMACZACE:
            return
    if isinstance(wezel, ast.Constant) and isinstance(wezel.value, str):
        yield wezel.value
        return
    if isinstance(wezel, ast.FormattedValue):
        # Wnętrze `{…}` to wyrażenie, nie tekst dla operatora: `{v['warning']}`
        # (zmierzone w ksiega_niedomowien.py) i specyfikator `{x:>10}`.
        return
    if isinstance(wezel, ast.Subscript):
        # Klucz indeksu (`d["status"]`) też nie jest tekstem dla operatora.
        yield from _literaly(wezel.value)
        return
    for dziecko in ast.iter_child_nodes(wezel):
        yield from _literaly(dziecko)


def naruszenia(sciezka: Path) -> list[tuple[int, str]]:
    zrodlo = sciezka.read_text(encoding="utf-8")
    linie = zrodlo.splitlines()
    wynik = []
    for wezel in ast.walk(ast.parse(zrodlo, filename=str(sciezka))):
        if not (isinstance(wezel, ast.Call) and isinstance(wezel.func, ast.Name)
                and wezel.func.id == "print"):
            continue
        if _WYJATEK.search(linie[wezel.lineno - 1]):
            continue
        teksty = [s for arg in wezel.args for s in _literaly(arg) if _ma_litere(s)]
        if teksty:
            wynik.append((wezel.lineno, teksty[0]))
    return wynik


def skrypty(korzen: Path = KORZEN) -> list[Path]:
    return sorted(p for p in korzen.glob("*.py") if p.name not in WYLACZONE)


def main(korzen: Path = KORZEN) -> int:
    bledy = 0
    for p in skrypty(korzen):
        try:
            lista = naruszenia(p)
        except SyntaxError as exc:
            print(f"::error file={p.name}::cannot parse: {exc}")
            return 2
        for nr, tekst in lista:
            bledy += 1
            print(f"::error file={p.name},line={nr}::print() with a hard-coded "
                  f"literal {tekst[:60]!r} — route it through t(UI_LANG, …) "
                  f"(dictionaries/<lang>/reports.yaml) or mark the line "
                  f"`# bramka-printow: ok — <reason>`")
    if bledy:
        print(f"Console hard-code gate: {bledy} violation(s).")
        return 1
    print(f"Console hard-code gate: clean ({len(skrypty(korzen))} scripts).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
