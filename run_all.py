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
# Ten tryb wykonuje KOPIĘ notatnika z ostrzeżeniami zamienionymi w błędy
# (jak audyt z `-W error`) i eksportami skierowanymi do katalogu
# tymczasowego: notatnik w repo i export_results/ zostają nietknięte, więc
# bramka źródła raportu nie widzi eksportów nowszych niż zapisane wyjścia.
WARNINGS_TAG = "warnings_as_errors"
WARNINGS_ERROR = 'warnings.simplefilter("error")'
# Kotwice łaty: dokładnie jedno trafienie w podanej komórce, inaczej tryb
# odmawia (notatnik zmienił się pod łatą — test_run_all to wychwyci).
WARNINGS_ANCHORS = (
    ("cell_langdet", 'warnings.filterwarnings("ignore")'),
    ("cell_corpus", 'PROJECT_DIR = Path("export_results") / PROJECT_NAME'),
)


def patch_for_warnings(nb, export_root):
    """Kopia notatnika: pierwsza komórka zamienia ostrzeżenia w błędy,
    cell_langdet już ich nie wycisza, PROJECT_DIR leży w export_root.
    Zwraca nową kopię albo rzuca ValueError z tagiem i kotwicą, która nie trafiła."""
    import copy
    import nbformat

    kopia = copy.deepcopy(nb)
    zamiany = {
        WARNINGS_ANCHORS[0]: WARNINGS_ERROR,
        WARNINGS_ANCHORS[1]: f"PROJECT_DIR = Path({str(export_root)!r}) / PROJECT_NAME",
    }
    for (tag, kotwica), nowa in zamiany.items():
        komorki = [c for i, c in enumerate(kopia.cells) if _tag(c, i) == tag]
        if len(komorki) != 1 or komorki[0].source.count(kotwica) != 1:
            raise ValueError(f"{tag}: {kotwica}")
        komorki[0].source = komorki[0].source.replace(kotwica, nowa)
    pierwsza = nbformat.v4.new_code_cell("import warnings\n" + WARNINGS_ERROR)
    pierwsza.metadata["tags"] = [WARNINGS_TAG]
    kopia.cells.insert(0, pierwsza)
    return kopia


def _warning_location(traceback_lines):
    """Gdzie padło ostrzeżenie, z tracebacku IPythona: linia komórki
    (`Cell In[11], line 104`) i ostatnia ramka biblioteki (`File ~/…/x.py:12,
    in f`). Lista 0–2 linii — pusta, gdy żadnej ramki nie ma."""
    ramki = [ANSI_RE.sub("", linia).strip() for blok in traceback_lines or []
             for linia in str(blok).splitlines()]
    komorka = [r for r in ramki if r.startswith("Cell In")]
    biblioteka = [r for r in ramki if r.startswith("File ")]
    return komorka[-1:] + biblioteka[-1:]


def run_warnings_check():
    """Kody: 0 = żadnego ostrzeżenia, 4 = ostrzeżenie (wydrukowane pod
    nagłówkiem, surowe — tekst biblioteki nie ma tłumaczenia), 1 = inna awaria."""
    import tempfile
    import nbformat
    from nbclient import NotebookClient
    from nbclient.exceptions import CellExecutionError

    nb = nbformat.read(NOTEBOOK, as_version=4)
    name = nb.metadata.get("kernelspec", {}).get("name", "analyst_env")
    if not ensure_kernel(name):
        return 1
    with tempfile.TemporaryDirectory(prefix="ata_warnings_") as tmp:
        try:
            nb = patch_for_warnings(nb, Path(tmp) / "export_results")
        except ValueError as e:
            print(t(UI_LANG, "run_all.warnings_patch_failed", anchor=str(e)))
            return 1
        print(t(UI_LANG, "run_all.warnings_start", path=tmp))
        stop = next((i for i, c in enumerate(nb.cells) if _tag(c, i) in QA_TAGS), len(nb.cells))
        code = [i for i in range(stop) if nb.cells[i].cell_type == "code"]
        client = NotebookClient(nb, timeout=None, kernel_name=name,
                                resources={"metadata": {"path": str(ROOT)}})
        warnings.filterwarnings("ignore", message="Proactor event loop", category=RuntimeWarning)
        i = code[0]
        try:
            with client.setup_kernel(stderr=subprocess.DEVNULL):
                for n, i in enumerate(code, 1):
                    print(t(UI_LANG, "run_all.notebook_cell", i=n, total=len(code),
                            tag=_tag(nb.cells[i], i)), flush=True)
                    client.execute_cell(nb.cells[i], i)
        except CellExecutionError as e:
            ename = getattr(e, "ename", "") or ""
            evalue = ANSI_RE.sub("", str(getattr(e, "evalue", "") or "")).strip()
            if ename.endswith("Warning"):
                print(t(UI_LANG, "run_all.warnings_found", tag=_tag(nb.cells[i], i)))
                print(f"{ename}: {evalue}")
                for linia in _warning_location(nb.cells[i].outputs[-1].get("traceback")
                                               if nb.cells[i].outputs else None):
                    print(linia)
                return 4
            print(t(UI_LANG, "run_all.warnings_cell_failed", tag=_tag(nb.cells[i], i),
                    error=f"{ename}: {evalue}" if ename else type(e).__name__))
            return 1
        except Exception as e:  # noqa: BLE001 — DeadKernelError, jądro nie wstało
            last = ANSI_RE.sub("", str(e) or type(e).__name__).strip().splitlines()[-1:] or [type(e).__name__]
            print(t(UI_LANG, "run_all.warnings_cell_failed", tag=_tag(nb.cells[i], i), error=last[0]))
            return 1
    print(t(UI_LANG, "run_all.warnings_clean", n=len(code)))
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
