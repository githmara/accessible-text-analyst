#!/usr/bin/env python
"""cykl_wersji.py — czy bieżąca praca ma zadeklarowany cykl wydania.

Bliźniak `.github/scripts/cykl_wersji.py` w Reżyserze Audio GPT (ta sama
tabela stanów, inna granica „zmiany wydawniczej”). Tylko stdlib: woła go hak
startu sesji maintainera systemowym Pythonem i `audyt_zaleznosci.py`.

DLACZEGO (decyzja maintainera 2026-11-14, ATA 2.0). Do 1.13 wersję projektu
audyt brał z górnej sekcji `release_notes.md`, a tej sekcji nie da się dopisać
przed wydaniem — jej pojawienie się na `main` JEST wydaniem. Przez cały cykl
audyt liczył więc wstrzymania względem ostatniego WYDANEGO numeru: holdy
„z przyszłości” (`# hold: 1.14.0` przy wydaniu, które okazało się majorem)
świeciły na zielono, a wszystkie holdy 1.x przeterminowałyby się naraz
dopiero w chwili wydania. Cykl otwiera się więc JAWNIE plikiem `VERSION`:
`X.Y.0-WIP` (minor albo major) albo `X.Y.Z-WIP` (patch); commit wydania
zdejmuje `-WIP` i dopisuje sekcję notatek (`wydanie.py` pilnuje zgodności).

STANY:
  wip          `VERSION` ma `-WIP`, a tagu tej wersji jeszcze nie ma — dobrze;
  wydany       `VERSION` = istniejący tag, a od tagu zmieniły się najwyżej
               pliki CI (`.github/`) — spoczynek po wydaniu;
  zamykanie    `VERSION` bez `-WIP` i bez tagu — commit wydania w przygotowaniu;
  nieotwarty   `VERSION` = istniejący tag, a od tagu zmieniło się coś poza
               `.github/` — BŁĄD: zadeklaruj cykl;
  wip_wydanej  `VERSION` = `X.Y.Z-WIP`, a tag `vX.Y.Z` już istnieje — BŁĄD;
  nieznany     brak `VERSION`, gita albo tagów — nie da się orzec.

Granica różni się od Reżysera świadomie: ATA jest source-only, więc KAŻDA
zmiana poza CI trafia do użytkownika z następnym archiwum źródeł — nie ma tu
skróconej procedury dev-tools-only. Zmiany liczone są względem DRZEWA
ROBOCZEGO (`git diff <tag>`), żeby hak startu ostrzegł przed pierwszym
niezadeklarowanym commitem, nie po nim.

Uruchom:  python .github/scripts/cykl_wersji.py [--json]   (z roota repo)
Kod wyjścia: 1 dla `nieotwarty` / `wip_wydanej`, inaczej 0.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

PLIK_WERSJI = "VERSION"
_WERSJA = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?(-WIP)?$")
STANY_BLEDU = ("nieotwarty", "wip_wydanej")
# Zmiany, które nie trafiają do użytkownika (CI i jego narzędzia).
PREFIKSY_POZA_WYDANIEM = (".github/",)


def _git(*argumenty: str) -> tuple[int, str]:
    try:
        wynik = subprocess.run(["git", *argumenty], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return wynik.returncode, wynik.stdout.strip()


def parsuj_wersje(tekst: str) -> tuple[tuple[int, int, int], bool] | None:
    """((major, minor, patch), czy_wip) z treści `VERSION`; brak patcha = 0."""
    m = _WERSJA.match(tekst.strip())
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)), bool(m.group(4))


def czytaj_wersje(korzen: Path = Path(".")) -> tuple[tuple[int, int, int], bool] | None:
    try:
        return parsuj_wersje((korzen / PLIK_WERSJI).read_text(encoding="utf-8"))
    except OSError:
        return None


def _tag_istnieje(tag: str) -> bool:
    kod, _ = _git("rev-parse", "-q", "--verify", f"refs/tags/{tag}")
    return kod == 0


def _nazwa_tagu(wersja: tuple[int, int, int]) -> str | None:
    """Tag wersji: `vX.Y.Z`, a dla patcha 0 także historyczne `vX.Y`."""
    pelny = "v{}.{}.{}".format(*wersja)
    if _tag_istnieje(pelny):
        return pelny
    if wersja[2] == 0:
        krotki = "v{}.{}".format(*wersja[:2])
        if _tag_istnieje(krotki):
            return krotki
    return None


def winowajcy(tag: str) -> list[str]:
    """Pliki zmienione od ``tag`` do drzewa roboczego, które trafią do użytkownika."""
    kod, surowe = _git("diff", "--name-only", tag)
    if kod != 0:
        raise RuntimeError(f"git diff {tag} failed")
    return [w for w in surowe.splitlines()
            if w.strip() and not w.startswith(PREFIKSY_POZA_WYDANIEM)]


def stan_cyklu(korzen: Path = Path(".")) -> dict:
    wersja = czytaj_wersje(korzen)
    if wersja is None:
        return {"stan": "nieznany", "powod": "VERSION missing or not X.Y[.Z][-WIP]"}
    numer, wip = wersja
    tekst = "{}.{}.{}".format(*numer) + ("-WIP" if wip else "")
    kod, _ = _git("rev-parse", "--git-dir")
    if kod != 0:
        return {"stan": "nieznany", "wersja": tekst, "powod": "not a git repository"}
    tag = _nazwa_tagu(numer)
    if wip:
        stan = "wip_wydanej" if tag else "wip"
        return {"stan": stan, "wersja": tekst, "tag": tag,
                "typ": "patch" if numer[2] else "minor/major"}
    if tag is None:
        kod, tagi = _git("tag", "--list", "v*")
        if kod != 0 or not tagi:
            return {"stan": "nieznany", "wersja": tekst,
                    "powod": "no v* tags in this clone (fetch tags?)"}
        return {"stan": "zamykanie", "wersja": tekst}
    try:
        lista = winowajcy(tag)
    except RuntimeError as exc:
        return {"stan": "nieznany", "wersja": tekst, "tag": tag, "powod": str(exc)}
    return {"stan": "nieotwarty" if lista else "wydany", "wersja": tekst,
            "tag": tag, "winowajcy": lista}


def komunikat(stan: dict) -> str:
    s = stan["stan"]
    w = stan.get("wersja", "?")
    if s == "nieotwarty":
        pliki = stan.get("winowajcy", [])
        return (f"Release cycle not opened: VERSION={w} is already tagged ({stan['tag']}), "
                f"but {len(pliki)} release file(s) changed since ({', '.join(pliki[:3])}"
                f"{', ...' if len(pliki) > 3 else ''}). Set VERSION to X.Y.0-WIP for a "
                f"minor/major or X.Y.Z-WIP for a patch, so dependency holds expire now, "
                f"not at release.")
    if s == "wip_wydanej":
        return (f"VERSION={w} is WIP, but tag {stan['tag']} already exists — "
                f"the cycle must carry the NEXT version number.")
    if s == "wip":
        return f"Cycle open: VERSION={w} ({stan['typ']})."
    if s == "wydany":
        return f"At rest after release {stan['tag']} (only CI files changed since)."
    if s == "zamykanie":
        return f"Closing the cycle: VERSION={w} has no tag yet."
    return f"Cycle state unknown: {stan.get('powod', '?')}."


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    stan = stan_cyklu()
    if "--json" in argv:
        print(json.dumps(stan, ensure_ascii=False))
    else:
        print(komunikat(stan))
    return 1 if stan["stan"] in STANY_BLEDU else 0


if __name__ == "__main__":
    sys.exit(main())
