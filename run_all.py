"""run_all.py — cały łańcuch lokalny jednym poleceniem.

    notatnik (nbclient, bez interaktywnej komórki pytań, wyjścia zapisane do .ipynb)
    -> generate_report.py (z bramką źródła)
    -> shamanic_pipeline.py (rytuały lokalne, bez LLM)
    -> ksiega_niedomowien.py scan --folder <folder>   (tylko korpus fiński)

Wyłącznie kroki darmowe i nieinteraktywne. Rytuały LLM (shamanic_ai.py), głosy
ElevenLabs (shamanic_voice.py) i `draft`/`fill` Księgi kosztują i mają własne
zgody (klucz w golden_key.env, provider w configu) — launcher ich nie woła,
tylko przypomina na końcu.

Jądro Jupytera: nazwa z metadanych notatnika (`analyst_env`). Gdy go nie ma,
launcher rejestruje je dla interpretera, którym sam działa (`ipykernel install
--user`), więc uruchamiaj go Pythonem z .venv repo.

Kody wyjścia: 0 = łańcuch przeszedł, 1 = krok się wywrócił, 3 = bramka źródła
odmówiła raportu (jak w generate_report.py), 4 = `--warnings-as-errors`
znalazł ostrzeżenie (osobny tryb: sam notatnik, na kopii, bez reszty łańcucha).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import warnings
from pathlib import Path

from shamanic_locale import detect_corpus_lang, get_ui_lang, t
import zrodlo_raportu

ROOT = Path(__file__).resolve().parent
NOTEBOOK = ROOT / "accessible_text_analyst.ipynb"
UI_LANG = get_ui_lang()
BOOK_LANG = "fi"            # Księga wpuszcza wyłącznie korpusy fińskie
QA_TAGS = ("md_qa_rag", "cell_qa_rag")
# Sekwencje ANSI (kolorowy traceback IPythona) — budowane w czasie wykonania.
ANSI_RE = re.compile(chr(27) + r"\[[0-9;]*[A-Za-z]")


def ensure_kernel(name):
    from jupyter_client.kernelspec import KernelSpecManager
    ksm = KernelSpecManager()
    if name in ksm.find_kernel_specs():
        # Sama nazwa nie wystarcza: po odtworzeniu .venv kernelspec wskazuje
        # interpreter, którego już nie ma, a jądro nie wstaje (audyt 2026-10-20).
        try:
            python = ksm.get_kernel_spec(name).argv[0]
        except Exception:  # noqa: BLE001 — uszkodzony kernel.json = rejestrujemy od nowa
            python = ""
        if python and (not os.path.isabs(python) or os.path.isfile(python)):
            print(t(UI_LANG, "run_all.kernel_ok", name=name))
            return True
        print(t(UI_LANG, "run_all.kernel_stale", name=name, old=python or "?", python=sys.executable))
    else:
        print(t(UI_LANG, "run_all.kernel_registering", name=name, python=sys.executable))
    r = subprocess.run([sys.executable, "-m", "ipykernel", "install", "--user",
                        "--name", name, "--display-name", name],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        tail = (r.stderr or r.stdout).strip().splitlines()
        print(t(UI_LANG, "run_all.kernel_failed", name=name, error=tail[-1] if tail else r.returncode))
        return False
    return True


def _tag(cell, i):
    tags = cell.get("metadata", {}).get("tags") or []
    return tags[0] if tags else str(i)


def run_notebook():
    """Komórki do pierwszej z QA_TAGS (pętla input() umiera w trybie wsadowym).
    Wyjścia trafiają do .ipynb także po błędzie — do miejsca awarii."""
    import nbformat
    from nbclient import NotebookClient
    from nbclient.exceptions import CellExecutionError

    nb = nbformat.read(NOTEBOOK, as_version=4)
    name = nb.metadata.get("kernelspec", {}).get("name", "analyst_env")
    if not ensure_kernel(name):
        return False
    stop = next((i for i, c in enumerate(nb.cells) if _tag(c, i) in QA_TAGS), len(nb.cells))
    code = [i for i in range(stop) if nb.cells[i].cell_type == "code"]
    # timeout=None: cell_sentiment na CPU potrafi liczyć wiele minut.
    client = NotebookClient(nb, timeout=None, kernel_name=name,
                            resources={"metadata": {"path": str(ROOT)}})
    # Szum bibliotek (zmq o pętli Proactor, ostrzeżenia IPKernelApp ze stderr
    # jądra) nie ma nic dla operatora i psuje odczyt czytnikiem ekranu. Błędy
    # komórek przychodzą komunikatami jądra, nie jego stderr — nic nie ginie.
    warnings.filterwarnings("ignore", message="Proactor event loop", category=RuntimeWarning)
    ok, i, ruszone = True, 0, 0
    try:
        with client.setup_kernel(stderr=subprocess.DEVNULL):
            # Stare wyjścia precz dopiero, gdy jądro WSTAŁO, ale przed pierwszą
            # komórką: po awarii komórki dalsze komórki nie mogą zostać
            # z wyjściami poprzedniego przebiegu (mieszanka dwóch przebiegów
            # w .ipynb przeszłaby przez bramkę źródła raportu). Jądro, które nie
            # wstaje, nie kasuje już zapisanych wyjść (audyt 2026-10-20).
            for j in code:
                nb.cells[j].outputs = []
                nb.cells[j].execution_count = None
            for n, i in enumerate(code, 1):
                print(t(UI_LANG, "run_all.notebook_cell", i=n, total=len(code), tag=_tag(nb.cells[i], i)),
                      flush=True)
                ruszone += 1
                client.execute_cell(nb.cells[i], i)
    except Exception as e:  # noqa: BLE001 — CellExecutionError, DeadKernelError, jądro nie wstało
        ok = False
        last = ANSI_RE.sub("", str(e) or type(e).__name__).strip().splitlines()[-1:] or [type(e).__name__]
        if ruszone:
            print(t(UI_LANG, "run_all.notebook_failed", tag=_tag(nb.cells[i], i), path=NOTEBOOK.name,
                    error=last[0]))
        else:
            print(t(UI_LANG, "run_all.kernel_start_failed", name=name, path=NOTEBOOK.name, error=last[0]))
    finally:
        if ruszone:
            nbformat.write(nb, NOTEBOOK)
    if ok:
        print(t(UI_LANG, "run_all.notebook_saved", path=NOTEBOOK.name, n=len(code)))
    return ok


# Tryb --warnings-as-errors. Notatnik celowo wycisza ostrzeżenia
# (cell_langdet), żeby nie wyciekały do raportu z czystą analizą — przez to
# deprecjacja albo ostrzeżenie o niespójnych danych nie dociera do nikogo.
# Ten tryb wykonuje KOPIĘ notatnika, w której każde ostrzeżenie jest
# REJESTROWANE (`simplefilter("always")` + własny `showwarning`), a eksporty
# idą do katalogu tymczasowego: notatnik w repo i export_results/ zostają
# nietknięte, więc bramka źródła raportu nie widzi eksportów nowszych niż
# zapisane wyjścia. Każde zarejestrowane ostrzeżenie to błąd PRZEBIEGU (kod 4),
# ale nie wyjątek w komórce: pierwsza wersja (2026-11-13) robiła
# `simplefilter("error")` jak audyt z `-W error` i to zmieniało zachowanie
# notatnika — UserWarning torcha w easyocr stał się wyjątkiem, który
# `_ocr_image_array` połknął (`except Exception` -> pusty tekst), więc zamiast
# ostrzeżenia wyszedł „niedziałający OCR”. Rejestr widzi też ostrzeżenia
# z kodu, który łapie wyjątki, i zbiera wszystkie, nie tylko pierwsze.
# Config użytkownika NIE decyduje, co się wykona: kopia dostaje syntetyczny
# korpus z diagnostyka.py (PDF z naprawą fontu i skanem, islandzki, wszystkie
# loadery, adres URL z lokalnego serwera) i włączony sentyment — ostrzeżenie
# w komponencie, którego config akurat nie używa, też musi wyjść.
WARNINGS_TAG = "warnings_as_errors"
WARNINGS_ALWAYS = 'warnings.simplefilter("always")'
# Pierwsza komórka kopii: rejestr ostrzeżeń w jądrze. `catch_warnings` bibliotek
# przywraca nasz `showwarning`, więc rejestr przeżywa ich lokalne filtry.
WARNINGS_RECORDER = "\n".join([
    "import warnings",
    "_ATA_OSTRZEZENIA = []",
    "def _ata_rejestruj(message, category, filename, lineno, file=None, line=None):",
    "    _ATA_OSTRZEZENIA.append([category.__name__, str(message), f'{filename}:{lineno}'])",
    "warnings.showwarning = _ata_rejestruj",
    WARNINGS_ALWAYS,
])
# Po każdej komórce run_all wykonuje tę sondę: wypisuje i czyści rejestr oraz
# mówi, czy rejestr nadal jest podpięty (`logging.captureWarnings(True)` albo
# biblioteka podmieniająca `showwarning` na stałe dałyby ciche „czysto”).
WARNINGS_PROBE_MARK = "ATA_WARNINGS_JSON:"
WARNINGS_PROBE = ("import json as _ata_json\n"
                  f"print({WARNINGS_PROBE_MARK!r} + _ata_json.dumps({{"
                  "'w': _ATA_OSTRZEZENIA, 'ok': warnings.showwarning is _ata_rejestruj}))\n"
                  "_ATA_OSTRZEZENIA.clear()")
# Limit na komórkę w kopii: cały przebieg na korpusie syntetycznym trwa
# dziesiątki sekund (plus jednorazowe pobranie modeli), a zawieszone pobieranie
# z HF bez limitu blokowałoby tryb na zawsze.
WARNINGS_CELL_TIMEOUT = 1800
LOADERS_TAG = "diag_loaders"
COMPONENTS_TAG = "diag_components"
# Komórki kontrolne rzucają RuntimeError z tym prefiksem, gdy komponent jest
# zainstalowany, ale w notatniku nie zadziałał (np. model się nie pobrał).
DIAG_MARKER = "ATA_DIAG_MISSING: "
# Kotwice łaty: dokładnie jedno trafienie w podanej komórce, inaczej tryb
# odmawia (notatnik zmienił się pod łatą — test_run_all to wychwyci).
WARNINGS_ANCHORS = (
    ("cell_langdet", 'warnings.filterwarnings("ignore")'),
    ("cell_corpus", 'PROJECT_DIR = Path("export_results") / PROJECT_NAME'),
    ("cell_corpus", "from shamanic_locale import wielkie_litery"),
    ("cell_corpus", 'for _name in ("config.json", "config.ini"):'),
)
# Kopia z korpusem syntetycznym nie czyta configa wcale: klucz configa dodany
# kiedyś do notatnika, a nieobjęty nadpisaniem, nie przecieknie do diagnostyki.
WARNINGS_NO_CONFIG = "for _name in ():  # run_all --warnings-as-errors: config nie jest czytany"


def _code_cell(tag, source):
    import nbformat
    komorka = nbformat.v4.new_code_cell(source)
    komorka.metadata["tags"] = [tag]
    return komorka


def _loaders_source(fixtures, url):
    """Komórka po cell_corpus: każdy loader na swojej próbce + custom_patterns."""
    import diagnostyka as dg
    wywolania = [(k, f"load_{'image' if k == 'png' else k}({str(fixtures[k])!r})")
                 for k in ("txt", "md", "html", "docx", "png")]
    wywolania.append(("url", f"load_url({url!r})"))
    linie = ["_DIAG_WYNIK = {}"]
    linie += [f"_DIAG_WYNIK[{k!r}] = ' '.join({w})" for k, w in wywolania]
    linie += [
        f"_DIAG_BRAKI = [k for k, s in {dg.SLOWA_LOADEROW!r}.items()",
        "               if s.lower() not in _DIAG_WYNIK[k].lower()]",
        f"if {dg.ROSKA!r} in _DIAG_WYNIK['txt']:",
        "    _DIAG_BRAKI.append('custom_patterns')",
        "if _DIAG_BRAKI:",
        f"    raise RuntimeError({DIAG_MARKER!r} + 'loader ' + ', '.join(_DIAG_BRAKI))",
    ]
    return "\n".join(linie)


def _components_source():
    """Komórka na końcu: czy każdy komponent opcjonalny naprawdę pracował."""
    import diagnostyka as dg
    return "\n".join([
        "_DIAG_BRAKI = []",
        "if 'omorfi_lemmas' not in get_nlp('fi').pipe_names:",
        "    _DIAG_BRAKI.append('omorfi')",
        # get_nlp('is') poniżej sam ładuje model, więc bez tego warunku kontrola
        # przeszłaby, nawet gdyby korpus nigdy nie poszedł ścieżką islandzką.
        "if 'is' not in para_langs:",
        "    _DIAG_BRAKI.append('icelandic path (no paragraph detected as is)')",
        "_DIAG_IS = get_nlp('is')",
        "for _k in ('icebert_vectors', 'icelandic_ner'):",
        "    if _k not in _DIAG_IS.pipe_names:",
        "        _DIAG_BRAKI.append(_k)",
        "if 'icelandic_ner' in _DIAG_IS.pipe_names and not _DIAG_IS("
        + repr(dg.IS_STRONA[0]) + ").ents:",
        "    _DIAG_BRAKI.append('icelandic_ner (0 entities)')",
        "if IS_NER_FAILURES:",
        "    _DIAG_BRAKI.append('icelandic_ner failures: ' + ', '.join(sorted(set(IS_NER_FAILURES))))",
        "if _OCR_READER is None:",
        "    _DIAG_BRAKI.append('easyocr')",
        "if not (PROJECT_DIR / 'sentiment.csv').is_file():",
        "    _DIAG_BRAKI.append('sentiment')",
        "_DIAG_TXT = ' '.join(corpus)",
        f"if {dg.SLOWO_NAPRAWY!r} not in _DIAG_TXT or '(cid:' in _DIAG_TXT:",
        "    _DIAG_BRAKI.append('naprawa_zrodel (fontTools)')",
        "if 'SKANNATTU' not in _DIAG_TXT.upper():",
        "    _DIAG_BRAKI.append('pdf ocr (pypdfium2)')",
        "if _DIAG_BRAKI:",
        f"    raise RuntimeError({DIAG_MARKER!r} + ', '.join(_DIAG_BRAKI))",
    ])


def patch_for_warnings(nb, export_root, fixtures=None, url=""):
    """Kopia notatnika: pierwsza komórka rejestruje każde ostrzeżenie,
    cell_langdet już ich nie wycisza, PROJECT_DIR leży w export_root.
    Z `fixtures` (diagnostyka.zbuduj) config zostaje zastąpiony korpusem
    syntetycznym, a dochodzą komórki loaderów i kontroli komponentów.
    Zwraca nową kopię albo rzuca ValueError z tagiem i kotwicą, która nie trafiła."""
    import copy
    import diagnostyka as dg

    kopia = copy.deepcopy(nb)
    zamiany = [
        (WARNINGS_ANCHORS[0], WARNINGS_ALWAYS),
        (WARNINGS_ANCHORS[1], f"PROJECT_DIR = Path({str(export_root)!r}) / PROJECT_NAME"),
    ]
    if fixtures:
        nadpisanie = "\n".join([
            "# --- run_all --warnings-as-errors: config zastąpiony korpusem syntetycznym ---",
            f"SOURCE_FILE = {str(fixtures['pdf'])!r}",
            f"CUSTOM_PATTERNS = [{dg.WZORZEC_ROSKI!r}]",
            f"OCR_LANGS = {dg.OCR_JEZYKI!r}",
            "ENABLE_SENTIMENT = True",
            "",
        ])
        zamiany.append((WARNINGS_ANCHORS[2], nadpisanie + WARNINGS_ANCHORS[2][1]))
        zamiany.append((WARNINGS_ANCHORS[3], WARNINGS_NO_CONFIG))
    for (tag, kotwica), nowa in zamiany:
        komorki = [c for i, c in enumerate(kopia.cells) if _tag(c, i) == tag]
        if len(komorki) != 1 or komorki[0].source.count(kotwica) != 1:
            raise ValueError(f"{tag}: {kotwica}")
        komorki[0].source = komorki[0].source.replace(kotwica, nowa)
    if fixtures:
        po_korpusie = next(i for i, c in enumerate(kopia.cells) if _tag(c, i) == "cell_corpus") + 1
        kopia.cells.insert(po_korpusie, _code_cell(LOADERS_TAG, _loaders_source(fixtures, url)))
        stop = next((i for i, c in enumerate(kopia.cells) if _tag(c, i) in QA_TAGS), len(kopia.cells))
        kopia.cells.insert(stop, _code_cell(COMPONENTS_TAG, _components_source()))
    kopia.cells.insert(0, _code_cell(WARNINGS_TAG, WARNINGS_RECORDER))
    return kopia


def _local_server(katalog):
    """Serwer HTTP na 127.0.0.1 (losowy port) dla `load_url` — bez sieci."""
    import functools
    import http.server
    import threading

    class _Cichy(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    serwer = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(_Cichy, directory=str(katalog)))
    threading.Thread(target=serwer.serve_forever, daemon=True).start()
    return serwer


def _probe_warnings(client, probe):
    """Wykonuje sondę rejestru. Zwraca (lista [kategoria, treść, miejsce],
    czy rejestr nadal podpięty). Brak linii sondy = rejestru nie ma."""
    import json
    probe.outputs = []
    client.execute_cell(probe, 0)
    for wyjscie in probe.outputs:
        for linia in str(wyjscie.get("text", "")).splitlines():
            if linia.startswith(WARNINGS_PROBE_MARK):
                dane = json.loads(linia[len(WARNINGS_PROBE_MARK):])
                return dane["w"], bool(dane["ok"])
    return [], False


def _print_warnings(per_cell):
    """Raport: nagłówek per komórka (zlokalizowany), pod nim ostrzeżenia
    w brzmieniu biblioteki — bez powtórzeń, z miejscem wywołania. Znane,
    nieszkodliwe (diagnostyka.ZNANE_OSTRZEZENIA) idą jedną linią [INFO].
    Zwraca (liczba ostrzeżeń spoza tej listy, liczba znanych)."""
    import diagnostyka

    nowe_razem = znane_razem = 0
    for tag, lista in per_cell:
        unikalne = list(dict.fromkeys(tuple(w) for w in lista))
        nowe = [w for w in unikalne if not diagnostyka.znane(w[0], w[1])]
        znane = [w for w in unikalne if diagnostyka.znane(w[0], w[1])]
        if nowe:
            print(t(UI_LANG, "run_all.warnings_found", tag=tag, n=len(nowe)))
            for kategoria, tresc, miejsce in nowe:
                print(f"{kategoria}: {tresc}")
                print(f"  {miejsce}")
        if znane:
            print(t(UI_LANG, "run_all.warnings_known", tag=tag, n=len(znane),
                    names=", ".join(sorted({w[0] for w in znane}))))
        nowe_razem += len(nowe)
        znane_razem += len(znane)
    return nowe_razem, znane_razem


def run_warnings_check():
    """Kody: 0 = żadnego ostrzeżenia, 4 = ostrzeżenie (wydrukowane pod
    nagłówkiem, surowe — tekst biblioteki nie ma tłumaczenia), 1 = inna awaria
    albo niepełna diagnostyka (brak komponentu przed startem lub w notatniku)."""
    import tempfile
    import nbformat

    import diagnostyka

    # Najpierw komplet: bez któregoś komponentu jego ostrzeżenia by nie wyszły,
    # a „czysto” znaczyłoby tylko „nie sprawdzono”.
    braki = diagnostyka.brakujace()
    if braki:
        print(t(UI_LANG, "run_all.warnings_missing", missing=", ".join(braki)))
        return 1
    nb = nbformat.read(NOTEBOOK, as_version=4)
    name = nb.metadata.get("kernelspec", {}).get("name", "analyst_env")
    if not ensure_kernel(name):
        return 1
    with tempfile.TemporaryDirectory(prefix="ata_warnings_") as tmp:
        fixtures = diagnostyka.zbuduj(Path(tmp) / "diag")
        serwer = _local_server(fixtures["html"].parent)
        url = f"http://127.0.0.1:{serwer.server_address[1]}/{fixtures['html'].name}"
        try:
            try:
                nb = patch_for_warnings(nb, Path(tmp) / "export_results", fixtures, url)
            except ValueError as e:
                print(t(UI_LANG, "run_all.warnings_patch_failed", anchor=str(e)))
                return 1
            print(t(UI_LANG, "run_all.warnings_start", path=tmp))
            return _execute_warnings_copy(nb, name)
        finally:
            serwer.shutdown()
            serwer.server_close()


def _execute_warnings_copy(nb, name):
    import nbformat
    from nbclient import NotebookClient
    from nbclient.exceptions import CellExecutionError

    stop = next((i for i, c in enumerate(nb.cells) if _tag(c, i) in QA_TAGS), len(nb.cells))
    code = [i for i in range(stop) if nb.cells[i].cell_type == "code"]
    # Komórki notatnika — bez trzech wstrzykniętych przez sam tryb.
    wlasne = sum(1 for i in code if _tag(nb.cells[i], i) not in
                 (WARNINGS_TAG, LOADERS_TAG, COMPONENTS_TAG))
    client = NotebookClient(nb, timeout=WARNINGS_CELL_TIMEOUT, kernel_name=name,
                            resources={"metadata": {"path": str(ROOT)}})
    warnings.filterwarnings("ignore", message="Proactor event loop", category=RuntimeWarning)
    probe = nbformat.v4.new_code_cell(WARNINGS_PROBE)
    per_cell = []
    i = code[0]
    rejestr_utracony = None
    try:
        with client.setup_kernel(stderr=subprocess.DEVNULL):
            for n, i in enumerate(code, 1):
                print(t(UI_LANG, "run_all.notebook_cell", i=n, total=len(code),
                        tag=_tag(nb.cells[i], i)), flush=True)
                try:
                    client.execute_cell(nb.cells[i], i)
                finally:
                    zlapane, podpiety = _probe_warnings(client, probe)
                    if zlapane:
                        per_cell.append((_tag(nb.cells[i], i), zlapane))
                if not podpiety:
                    rejestr_utracony = _tag(nb.cells[i], i)
                    break
    except KeyboardInterrupt:
        # Sprzątanie (jądro, temp, serwer) robią menedżery kontekstu; tu
        # tylko nie gubimy tego, co już zebrane, i trzymamy kontrakt kodów.
        _print_warnings(per_cell)
        print(t(UI_LANG, "run_all.warnings_interrupted", tag=_tag(nb.cells[i], i)))
        return 1
    except CellExecutionError as e:
        ename = getattr(e, "ename", "") or ""
        evalue = ANSI_RE.sub("", str(getattr(e, "evalue", "") or "")).strip()
        _print_warnings(per_cell)
        if evalue.startswith(DIAG_MARKER):
            print(t(UI_LANG, "run_all.warnings_components", tag=_tag(nb.cells[i], i),
                    missing=evalue[len(DIAG_MARKER):]))
            return 1
        print(t(UI_LANG, "run_all.warnings_cell_failed", tag=_tag(nb.cells[i], i),
                error=f"{ename}: {evalue}" if ename else type(e).__name__))
        return 1
    except Exception as e:  # noqa: BLE001 — DeadKernelError, jądro nie wstało
        _print_warnings(per_cell)
        last = ANSI_RE.sub("", str(e) or type(e).__name__).strip().splitlines()[-1:] or [type(e).__name__]
        print(t(UI_LANG, "run_all.warnings_cell_failed", tag=_tag(nb.cells[i], i), error=last[0]))
        return 1
    nowe, znane = _print_warnings(per_cell)
    if rejestr_utracony:
        print(t(UI_LANG, "run_all.warnings_recorder_lost", tag=rejestr_utracony))
        return 1
    if nowe:
        return 4
    if znane:
        print(t(UI_LANG, "run_all.warnings_clean_known", n=wlasne, k=znane))
    else:
        print(t(UI_LANG, "run_all.warnings_clean", n=wlasne))
    return 0


def run_script(args):
    r = subprocess.run([sys.executable, *args], cwd=ROOT)
    return r.returncode


def main(argv=None):
    # Konsola Windows bywa cp1250, a przekierowane wyjście nie dziedziczy
    # PYTHONIOENCODING z ustawień agenta: rosyjski komunikat albo cyrylica
    # w ścieżce źródła rzucały UnicodeEncodeError (exit 1 zamiast kodu bramki;
    # audyt 2026-10-20). Jak w ksiega_niedomowien.py.
    for _strumien in (sys.stdout, sys.stderr):
        if hasattr(_strumien, "reconfigure"):
            _strumien.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=t(UI_LANG, "run_all.description"))
    ap.add_argument("--skip-notebook", action="store_true", help=t(UI_LANG, "run_all.help_skip_notebook"))
    ap.add_argument("--no-shamanic", action="store_true", help=t(UI_LANG, "run_all.help_no_shamanic"))
    ap.add_argument("--no-book", action="store_true", help=t(UI_LANG, "run_all.help_no_book"))
    ap.add_argument("--warnings-as-errors", action="store_true",
                    help=t(UI_LANG, "run_all.help_warnings_as_errors"))
    args = ap.parse_args(argv)
    os.chdir(ROOT)

    if args.warnings_as_errors:
        return run_warnings_check()

    total = 4 - args.no_shamanic - args.no_book
    n = 0

    def step(label):
        nonlocal n
        n += 1
        print(t(UI_LANG, "run_all.step", n=n, total=total, name=label), flush=True)

    step(NOTEBOOK.name)
    if args.skip_notebook:
        print(t(UI_LANG, "run_all.skip_notebook", path=NOTEBOOK.name))
    elif not run_notebook():
        return 1

    step("generate_report.py")
    code = run_script(["generate_report.py"])
    if code:
        print(t(UI_LANG, "run_all.step_failed", name="generate_report.py", code=code))
        return 3 if code == 3 else 1

    # Folder projektu dokładnie taki, jaki wydrukował notatnik — bramka już
    # potwierdziła, że to folder ze źródła w configu.
    with open(NOTEBOOK, encoding="utf-8") as f:
        katalog = zrodlo_raportu.wyjscia_korpusu(json.load(f)).katalog
    folder = ROOT / katalog if katalog else None

    if not args.no_shamanic:
        step("shamanic_pipeline.py")
        code = run_script(["shamanic_pipeline.py"])
        if code:
            print(t(UI_LANG, "run_all.step_failed", name="shamanic_pipeline.py", code=code))
            return 1

    if not args.no_book:
        step("ksiega_niedomowien.py scan")
        lang = detect_corpus_lang(folder) if folder else None
        if lang != BOOK_LANG:
            print(t(UI_LANG, "run_all.book_skipped_lang", language=lang))
        else:
            # Kod 2 = folder odrzucony przez filtry Księgi: to wynik, nie awaria.
            code = run_script(["ksiega_niedomowien.py", "scan", "--folder", folder.name])
            if code not in (0, 2):
                print(t(UI_LANG, "run_all.step_failed", name="ksiega_niedomowien.py scan", code=code))
                return 1

    print(t(UI_LANG, "run_all.done", folder=katalog))
    print(t(UI_LANG, "run_all.paid_hint"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
