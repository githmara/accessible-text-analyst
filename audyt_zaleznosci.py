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
import subprocess
import sys
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import NamedTuple, Optional

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "requirements.txt"
NOTATKI_WYDAN = ROOT / "release_notes.md"
# Drugi zegar holdu (budzik, 2026-11-12, bliźniak Reżysera): hold starszy niż
# tyle dni od commitu, który ostatnio zmienił jego linię, wygasa także bez
# nowego minora — sam zegar wersji staje, gdy projekt nie wydaje.
WIEK_HOLDU_DNI = 60
# Znacznik budzika: wynik ostatniego pełnego audytu. Czyta go hak startu sesji
# maintainera; `export_results/` jest poza gitem.
ZNACZNIK_BUDZIKA = ROOT / "export_results" / "audyt_zaleznosci_ostatni.json"
URL_PYPI = "https://pypi.org/pypi/{}/json"
TIMEOUT = 15
# Modele Hugging Face, które notatnik pobiera po nazwie. Do 2026-11-13 oba modele
# islandzkie wskazywały repozytoria, których nie ma (HTTP 401) — loader łapał
# wyjątek, a islandzki od pierwszego commita działał bez wektorów i NER. Audyt
# pyta więc API Hubu o każdą nazwę, którą notatnik POBIERA: argument `model=`
# albo `from_pretrained(` — literał "org/model" wprost albo stała, której
# przypisanie (dowolny cudzysłów, z adnotacją typu lub bez) daje taki literał.
# Od użycia, nie od nazwy stałej (audyt 2026-11-13): sam wzorzec nazw `HF_*`/
# `*_MODEL` gubił literał w wywołaniu i apostrofy, a łapał `OPENROUTER_MODEL =
# "anthropic/…"`, którego Hub nie zna — fałszywe ostrzeżenie w audycie.
NOTATNIK = ROOT / "accessible_text_analyst.py"
URL_HF = "https://huggingface.co/api/models/{}"
_NAZWA_HF = r"[\w.-]+/[\w.-]+"
_RE_UZYCIE_HF = re.compile(
    r"""(?:\bmodel\s*=\s*|\bfrom_pretrained\(\s*)"""
    rf"""(?:(["'])({_NAZWA_HF})\1|([A-Za-z_]\w*)\b)""")


def _re_stala_hf(nazwa: str) -> re.Pattern:
    return re.compile(rf"""^\s*{re.escape(nazwa)}\s*(?::[^=\n]+)?=\s*(["'])({_NAZWA_HF})\1""", re.M)
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
        "pillow",
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


def modele_hf(sciezka: Path = NOTATNIK) -> list[str]:
    """Nazwy modeli Hubu, które notatnik pobiera, w kolejności, bez powtórzeń.
    Ścieżka istniejąca na dysku (model lokalny) nie jest nazwą Hubu."""
    tekst = sciezka.read_text(encoding="utf-8")
    wynik = []
    for m in _RE_UZYCIE_HF.finditer(tekst):
        if m.group(2):
            wynik.append(m.group(2))
        elif m.group(3):
            wynik += [s.group(2) for s in _re_stala_hf(m.group(3)).finditer(tekst)]
    return [n for n in dict.fromkeys(wynik) if not (sciezka.parent / n).exists()]


def model_hf_istnieje(model: str) -> bool | None:
    """True = repozytorium jest publiczne, False = Hub go nie zna (401/404),
    None = brak odpowiedzi (sieć) — wtedy nic nie wiadomo."""
    import urllib.error
    try:
        with urllib.request.urlopen(URL_HF.format(model), timeout=TIMEOUT) as odp:
            return odp.status == 200
    except urllib.error.HTTPError as e:
        return False if e.code in (401, 403, 404) else None
    except (OSError, ValueError):
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


def _klon_plytki(katalog: Path) -> bool:
    """True, gdy repo jest płytkim klonem — wiek z blame jest wtedy fałszywy.
    Bliźniak Reżysera (`audyt_zaleznosci._klon_plytki`)."""
    try:
        wynik = subprocess.run(["git", "rev-parse", "--is-shallow-repository"],
                               cwd=katalog, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return wynik.returncode == 0 and wynik.stdout.strip() == "true"


def wiek_linii_manifestu(sciezka: Path = MANIFEST, dzis: date | None = None) -> dict[str, int]:
    """{pakiet: dni od commitu, który ostatnio zmienił jego linię} z `git blame`.

    Linie opcjonalne (`# pakiet<…`) też się liczą. Bez gita: pusty słownik
    (wiek nieznany, nie zerowy). Płytki klon (`--depth 1`) też: blame
    przypisałby każdą linię commitowi granicznemu i odmłodził hold (bliźniak
    Reżysera, audyt 2026-11-13: 130 dni w pełnej historii, 10 w płytkim klonie).
    """
    dzis = dzis or date.today()
    if _klon_plytki(sciezka.parent):
        return {}
    try:
        wynik = subprocess.run(["git", "blame", "--line-porcelain", "--", sciezka.name],
                               cwd=sciezka.parent, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.SubprocessError):
        return {}
    if wynik.returncode != 0:
        return {}
    wieki: dict[str, int] = {}
    czas = None
    for linia in wynik.stdout.splitlines():
        if linia.startswith("committer-time "):
            czas = int(linia.split()[1])
        elif linia.startswith("\t") and czas is not None:
            # Tylko linie z `hold:` (twin Reżysera 19.18): komentarz nagłówka
            # „# fonttools 4.67.0: naprawa…" stał PRZED wpisem i `setdefault`
            # dawał fonttools wiek tego komentarza zamiast linii z granicą.
            surowa = linia[1:].strip()
            tekst = (surowa.lstrip("#").strip().partition("#")[0].strip()
                     if "hold:" in surowa else "")
            g = _WPIS.match(tekst)
            if g and g.group("spec"):
                dni = (dzis - datetime.fromtimestamp(czas).date()).days
                wieki.setdefault(g.group("nazwa").lower(), max(dni, 0))
            czas = None
    return wieki


def ocen_wstrzymanie(w: str, hold: Optional[str],
                     projekt: Optional[tuple[int, int, int]],
                     wiek_dni: Optional[int] = None) -> str:
    """`trzymana` → `niedatowana` / `przeterminowana` wg daty holdu; reszta bez zmian.

    Hold liczy się tylko wtedy, gdy granica naprawdę coś wyklucza: pakiet aktualny
    ze starą datą nie ma czego testować. Bez czytelnej wersji projektu nie da się
    orzec wygaśnięcia — hold zostaje wtedy `trzymana` (audyt i tak tylko ostrzega).
    """
    if w != "trzymana":
        return w
    if hold is None:
        return "niedatowana"
    major, minor = (int(x) for x in hold.split(".")[:2])
    if projekt is not None and (major, minor) < projekt[:2]:
        return "przeterminowana"
    if wiek_dni is not None and wiek_dni > WIEK_HOLDU_DNI:
        return "przeterminowana_wiek"
    return w


def zapisz_znacznik(do_decyzji: list[str], sciezka: Path | None = None,
                    dzis: date | None = None) -> bool:
    """Znacznik budzika po PEŁNYM audycie (format wspólny z Reżyserem: format/data/do_decyzji)."""
    cel = sciezka or ZNACZNIK_BUDZIKA
    try:
        cel.parent.mkdir(parents=True, exist_ok=True)
        cel.write_text(json.dumps({"format": 1, "data": (dzis or date.today()).isoformat(),
                                   "zrodlo": "audyt_zaleznosci", "do_decyzji": do_decyzji},
                                  ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        return False
    return True


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
    wieki = wiek_linii_manifestu()
    licznik: dict[str, int] = {}
    do_decyzji: list[str] = []
    manifest = wczytaj_manifest()
    # Hold bez znanego wieku (brak gita, paczka „Source code”, błąd blame):
    # 60-dniowy zegar stoi, więc audyt mówi to głośno i NIE cofa budzika.
    bez_wieku = sorted(w.nazwa for w in manifest if w.hold and w.nazwa.lower() not in wieki)
    if bez_wieku:
        print(t(ui, "deps.wiek_nieznany", ile=len(bez_wieku),
                nazwy=", ".join(bez_wieku[:5]), limit=WIEK_HOLDU_DNI))
    for wpis in manifest:
        grupa = GRUPY_RYZYKA.get(wpis.nazwa)
        if grupa is None:
            licznik["bez_grupy"] = licznik.get("bez_grupy", 0) + 1
            do_decyzji.append(t(ui, "deps.w_bez_grupy", nazwa=wpis.nazwa))
            print(do_decyzji[-1])
        inst = zainstalowana(wpis.nazwa)
        nowa = najnowsza(wpis.nazwa) if inst else None
        w = ocen_wstrzymanie(werdykt(wpis.spec, inst, nowa, wpis.opcja), wpis.hold,
                             projekt, wieki.get(wpis.nazwa))
        klucz = "przeterminowana" if w == "przeterminowana_wiek" else w
        licznik[klucz] = licznik.get(klucz, 0) + 1
        if w in ("ok", "pominieta"):
            continue
        linia = t(ui, f"deps.w_{w}", nazwa=wpis.nazwa, spec=wpis.spec or "-",
                  inst=inst or "-", nowa=nowa or "-", hold=wpis.hold or "-",
                  projekt=wersja_txt, wiek=wieki.get(wpis.nazwa, "?"),
                  limit=WIEK_HOLDU_DNI)
        print(linia)
        if w not in ("trzymana", "pypi"):
            do_decyzji.append(linia)
        if klucz in ("przeterminowana", "niedatowana", "dopuszczona") and grupa:
            print("    " + t(ui, f"deps.grupa_{grupa}"))
    for model in modele_hf():
        jest = model_hf_istnieje(model)
        if jest:
            continue
        # Brak sieci liczy się jak brak PyPI: audyt nie był pełny, budzik stoi.
        klucz = "model_hf" if jest is False else "pypi"
        licznik[klucz] = licznik.get(klucz, 0) + 1
        linia = t(ui, f"deps.w_{klucz}_model", model=model)
        print(linia)
        if jest is False:
            do_decyzji.append(linia)
    ostrzezenia = sum(licznik.get(k, 0) for k in
                      ("dopuszczona", "poza", "brak", "niedatowana", "bez_grupy", "model_hf"))
    print(t(ui, "deps.podsumowanie", ok=licznik.get("ok", 0),
            trzymane=licznik.get("trzymana", 0),
            przeterminowane=licznik.get("przeterminowana", 0),
            ostrzezenia=ostrzezenia, pominiete=licznik.get("pominieta", 0)))
    # Budzik cofa tylko audyt, który porównał wszystko z PyPI: przebieg bez
    # sieci nie wie, czy upgrade czeka, więc nie może uciszyć przypomnienia.
    if not licznik.get("pypi") and not bez_wieku and zapisz_znacznik(do_decyzji):
        print(t(ui, "deps.budzik", plik=ZNACZNIK_BUDZIKA.relative_to(ROOT).as_posix()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
