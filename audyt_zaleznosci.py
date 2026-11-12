#!/usr/bin/env python
"""audyt_zaleznosci.py — czy któraś zależność ma nowsze wydanie albo nie trzyma granicy.

Lustro `audyt_zaleznosci.py` z Reżysera Audio GPT, z jedną świadomą różnicą:
TYLKO OSTRZEGA (kod wyjścia zawsze 0). Reżyser zamraża zależności w bundlu
PyInstallera, więc tam nieprzetestowana wersja blokuje build. ATA nie ma
bundla: użytkownik instaluje `requirements.txt` sam, a przepisanie notatnika na
czysty Python pod PyInstallera rozdęłoby paczkę (torch + modele) ponad limit
assetu GitHuba. Tu audyt jest informacją dla osoby, która instaluje.

KANON ŚRODOWISKA (od 2026-11-12, bliźniak Reżysera 19.18). Granica bez daty
psuje się po cichu: „trzymana” wyglądała na stan dobry na zawsze i nikt nie
wracał do pakietu (pomiar 2026-11-12: 27 z 29 granic stało od v1.8.0, cztery
wydania minor wcześniej). Dlatego:
  1. każda granica nosi datę: `pakiet<X.Y  # hold: <wersja ATA>` — wersja, w której
     zestaw z tą granicą był ostatnio PRZETESTOWANY;
  2. hold wygasa z następnym minorem: gdy górna sekcja `release_notes.md` ma
     wyższy (major, minor) niż hold, a nowsze wydanie pakietu istnieje, audyt
     ostrzega PRZETERMINOWANA — przetestuj i podbij granicę albo odnów datę;
  3. każdy pakiet ma grupę ryzyka (`GRUPY_RYZYKA`), która mówi, CO testować.
     Pakiet z manifestu bez grupy to ostrzeżenie: nowa zależność musi dostać
     grupę w tym samym commicie.

Manifest ma granice od v1.8.0: górna granica = następny minor ponad wersją
przetestowaną. Zależności opcjonalne stoją w `requirements.txt` jako
zakomentowane linie `# pakiet<granica>  # hold: …` — audyt sprawdza je, gdy są
zainstalowane, a niezainstalowane pomija (to normalny stan).

Werdykty:
  ok               zainstalowana = najnowsza na PyPI;
  trzymana         jest nowsze wydanie, granica je wyklucza, hold jest ważny;
  przeterminowana  jak wyżej, ale hold pochodzi z wcześniejszego minora;
  niedatowana      jak wyżej, ale granica nie ma `# hold:` (nikt nie wie, od kiedy);
  dopuszczona      jest nowsze wydanie, które granica DOPUSZCZA — nieprzetestowane;
  poza             zainstalowana wersja nie spełnia granicy manifestu;
  brak             wymagany pakiet nie jest zainstalowany.

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
from typing import NamedTuple, Optional

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "requirements.txt"
NOTATKI_WYDAN = ROOT / "release_notes.md"
URL_PYPI = "https://pypi.org/pypi/{}/json"
TIMEOUT = 15
# Python, na którym zestaw z manifestu był ostatnio przetestowany (patrz nagłówek
# requirements.txt). Jedno miejsce — audyt porównuje z nim bieżący interpreter.
PYTHON_PRZETESTOWANY = "3.14.3"

# Grupa ryzyka = co testować przed podbiciem granicy (opis: deps.grupa_<X>).
#   A — zmienia to, co analiza znajduje, albo to, jak czyta się raport;
#   B — rozmawia z zewnętrznym API;
#   C — narzędzia obok wyniku (notatnik, postęp), bez wpływu na treść.
GRUPY_RYZYKA: dict[str, str] = {
    **dict.fromkeys((
        "lingua-language-detector", "spacy", "numpy", "pandas", "scikit-learn",
        "pdfplumber", "fonttools", "python-docx", "beautifulsoup4", "lxml",
        "markdown", "markdownify", "omorfi", "transformers", "torch",
        "sentencepiece", "protobuf", "tiktoken", "pypdfium2", "easyocr", "pyyaml",
    ), "A"),
    **dict.fromkeys(("openai", "requests", "python-dotenv"), "B"),
    **dict.fromkeys(("ipykernel", "nbstripout", "jupytext", "nbclient", "tqdm"), "C"),
}

_WPIS = re.compile(r"^(?P<nazwa>[A-Za-z0-9._-]+)\s*(?P<spec>[<>=!~][^\s]*)?\s*$")
_HOLD = re.compile(r"\bhold:\s*v?(?P<wersja>\d+\.\d+(?:\.\d+)?)")
_SEKCJA = re.compile(r"^##\s*v?(\d+)\.(\d+)\.(\d+)\b")


class Wpis(NamedTuple):
    nazwa: str
    spec: str
    opcja: bool
    hold: Optional[str]


def wczytaj_manifest(sciezka: Path = MANIFEST) -> list[Wpis]:
    """Wpisy manifestu bez duplikatów (pierwsze wystąpienie).

    Linia opcjonalna zaczyna się od `#`; komentarz za wpisem (po drugim `#`,
    np. `# hold: 1.12.0`) pip traktuje jako komentarz, audyt czyta z niego datę.
    """
    wynik, widziane = [], set()
    for linia in sciezka.read_text(encoding="utf-8").splitlines():
        tekst = linia.strip()
        opcja = tekst.startswith("#")
        if opcja:
            tekst = tekst.lstrip("#").strip()
        tresc, _, komentarz = tekst.partition("#")
        g = _WPIS.match(tresc.strip())
        if not g or not g.group("spec") and opcja:
            # Linia komentarza z jednym słowem bez granicy to proza, nie wpis.
            continue
        nazwa = g.group("nazwa").lower()
        if nazwa in widziane:
            continue
        widziane.add(nazwa)
        h = _HOLD.search(komentarz)
        wynik.append(Wpis(nazwa, g.group("spec") or "", opcja, h.group("wersja") if h else None))
    return wynik


def wersja_projektu(sciezka: Path = NOTATKI_WYDAN) -> Optional[tuple[int, int, int]]:
    """Wersja z górnej sekcji `## vX.Y.Z` notatek wydań (ATA nie ma pliku VERSION)."""
    try:
        for linia in sciezka.read_text(encoding="utf-8").splitlines():
            m = _SEKCJA.match(linia)
            if m:
                return tuple(int(x) for x in m.groups())  # type: ignore[return-value]
    except OSError:
        pass
    return None


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


def ocen_wstrzymanie(w: str, hold: Optional[str],
                     projekt: Optional[tuple[int, int, int]]) -> str:
    """`trzymana` → `niedatowana` / `przeterminowana` wg daty holdu; reszta bez zmian.

    Hold liczy się tylko wtedy, gdy granica naprawdę coś wyklucza: pakiet aktualny
    ze starą datą nie ma czego testować. Bez czytelnej wersji projektu nie da się
    orzec wygaśnięcia — hold zostaje wtedy `trzymana` (audyt i tak tylko ostrzega).
    """
    if w != "trzymana":
        return w
    if hold is None:
        return "niedatowana"
    if projekt is None:
        return w
    major, minor = (int(x) for x in hold.split(".")[:2])
    return "przeterminowana" if (major, minor) < projekt[:2] else w


def main() -> int:
    from shamanic_locale import get_ui_lang, t
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
    projekt = wersja_projektu()
    wersja_txt = ".".join(map(str, projekt)) if projekt else "?"
    licznik: dict[str, int] = {}
    for wpis in wczytaj_manifest():
        grupa = GRUPY_RYZYKA.get(wpis.nazwa)
        if grupa is None:
            licznik["bez_grupy"] = licznik.get("bez_grupy", 0) + 1
            print(t(ui, "deps.w_bez_grupy", nazwa=wpis.nazwa))
        inst = zainstalowana(wpis.nazwa)
        nowa = najnowsza(wpis.nazwa) if inst else None
        w = ocen_wstrzymanie(werdykt(wpis.spec, inst, nowa, wpis.opcja), wpis.hold, projekt)
        licznik[w] = licznik.get(w, 0) + 1
        if w in ("ok", "pominieta"):
            continue
        print(t(ui, f"deps.w_{w}", nazwa=wpis.nazwa, spec=wpis.spec or "-",
                inst=inst or "-", nowa=nowa or "-", hold=wpis.hold or "-",
                projekt=wersja_txt))
        if w in ("przeterminowana", "niedatowana", "dopuszczona") and grupa:
            print("    " + t(ui, f"deps.grupa_{grupa}"))
    ostrzezenia = sum(licznik.get(k, 0) for k in
                      ("dopuszczona", "poza", "brak", "niedatowana", "bez_grupy"))
    print(t(ui, "deps.podsumowanie", ok=licznik.get("ok", 0),
            trzymane=licznik.get("trzymana", 0),
            przeterminowane=licznik.get("przeterminowana", 0),
            ostrzezenia=ostrzezenia, pominiete=licznik.get("pominieta", 0)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
