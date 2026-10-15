#!/usr/bin/env python
"""audyt_zaleznosci.py — czy któraś zależność ma nowsze wydanie albo nie trzyma granicy.

Lustro `audyt_zaleznosci.py` z Reżysera Audio GPT, z jedną świadomą różnicą:
TYLKO OSTRZEGA (kod wyjścia zawsze 0). Reżyser zamraża zależności w bundlu
PyInstallera, więc tam nieprzetestowana wersja blokuje build. ATA nie ma
bundla: użytkownik instaluje `requirements.txt` sam, a przepisanie notatnika na
czysty Python pod PyInstallera rozdęłoby paczkę (torch + modele) ponad limit
assetu GitHuba. Tu audyt jest informacją dla osoby, która instaluje.

Manifest ma granice od v1.8.0: górna granica = następny minor ponad wersją
przetestowaną. Zależności opcjonalne stoją w `requirements.txt` jako
zakomentowane linie `# pakiet<granica>` — audyt sprawdza je, gdy są
zainstalowane, a niezainstalowane pomija (to normalny stan).

Werdykty:
  ok          zainstalowana = najnowsza na PyPI;
  trzymana    jest nowsze wydanie, ale granica manifestu je wyklucza (świadomie);
  dopuszczona jest nowsze wydanie, które granica DOPUSZCZA — nieprzetestowane;
  poza        zainstalowana wersja nie spełnia granicy manifestu;
  brak        wymagany pakiet nie jest zainstalowany.

Uruchom:  python audyt_zaleznosci.py      (konsola w ui_lang z config.json)
"""

from __future__ import annotations

import importlib.metadata as metadata
import json
import platform
import re
import sys
import urllib.request
from pathlib import Path

from shamanic_locale import get_ui_lang, t

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "requirements.txt"
URL_PYPI = "https://pypi.org/pypi/{}/json"
TIMEOUT = 15
# Python, na którym zestaw z manifestu był ostatnio przetestowany (patrz nagłówek
# requirements.txt). Jedno miejsce — audyt porównuje z nim bieżący interpreter.
PYTHON_PRZETESTOWANY = "3.14.3"

_WPIS = re.compile(r"^(?P<opcja>#\s*)?(?P<nazwa>[A-Za-z0-9._-]+)\s*(?P<spec>[<>=!~][^#\s]*)?\s*$")


def wczytaj_manifest(sciezka: Path = MANIFEST) -> list[tuple[str, str, bool]]:
    """[(nazwa, specyfikator, opcjonalny)] — bez duplikatów (pierwsze wystąpienie)."""
    wynik, widziane = [], set()
    for linia in sciezka.read_text(encoding="utf-8").splitlines():
        g = _WPIS.match(linia.strip())
        if not g or not g.group("spec") and g.group("opcja"):
            # Linia komentarza z jednym słowem bez granicy to proza, nie wpis.
            continue
        nazwa = g.group("nazwa").lower()
        if nazwa in widziane:
            continue
        widziane.add(nazwa)
        wynik.append((nazwa, g.group("spec") or "", bool(g.group("opcja"))))
    return wynik


def zainstalowana(nazwa: str) -> str | None:
    try:
        return metadata.version(nazwa)
    except metadata.PackageNotFoundError:
        return None


def najnowsza(nazwa: str) -> str | None:
    try:
        with urllib.request.urlopen(URL_PYPI.format(nazwa), timeout=TIMEOUT) as odp:
            return json.load(odp)["info"]["version"]
    except Exception:  # noqa: BLE001 — sieć/PyPI: werdykt „nie sprawdzono”, nie wyjątek
        return None


def werdykt(spec: str, inst: str | None, nowa: str | None, opcja: bool) -> str:
    from packaging.specifiers import SpecifierSet
    from packaging.version import Version
    if inst is None:
        return "pominieta" if opcja else "brak"
    s = SpecifierSet(spec)
    if spec and Version(inst) not in s:
        return "poza"
    if nowa is None:
        return "pypi"
    if Version(nowa) <= Version(inst):
        return "ok"
    return "dopuszczona" if (not spec or Version(nowa) in s) else "trzymana"


def main() -> int:
    ui = get_ui_lang()
    print(t(ui, "deps.naglowek"))
    teraz = platform.python_version()
    if teraz != PYTHON_PRZETESTOWANY:
        print(t(ui, "deps.python_inny", teraz=teraz, przetestowany=PYTHON_PRZETESTOWANY))
    try:
        import packaging  # noqa: F401
    except ImportError:
        print(t(ui, "deps.brak_packaging"))
        return 0
    licznik: dict[str, int] = {}
    for nazwa, spec, opcja in wczytaj_manifest():
        inst = zainstalowana(nazwa)
        nowa = najnowsza(nazwa) if inst else None
        w = werdykt(spec, inst, nowa, opcja)
        licznik[w] = licznik.get(w, 0) + 1
        if w in ("ok", "pominieta"):
            continue
        print(t(ui, f"deps.w_{w}", nazwa=nazwa, spec=spec or "-",
                inst=inst or "-", nowa=nowa or "-"))
    ostrzezenia = sum(licznik.get(k, 0) for k in ("dopuszczona", "poza", "brak"))
    print(t(ui, "deps.podsumowanie", ok=licznik.get("ok", 0),
            trzymane=licznik.get("trzymana", 0), ostrzezenia=ostrzezenia,
            pominiete=licznik.get("pominieta", 0)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
