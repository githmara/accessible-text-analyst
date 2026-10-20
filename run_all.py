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
odmówiła raportu (jak w generate_report.py).
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
    if name in KernelSpecManager().find_kernel_specs():
        print(t(UI_LANG, "run_all.kernel_ok", name=name))
        return True
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
    # Stare wyjścia precz PRZED startem: po awarii komórki dalsze komórki nie
    # mogą zostać z wyjściami poprzedniego przebiegu (mieszanka dwóch przebiegów
    # w .ipynb przeszłaby przez bramkę źródła raportu).
    for i in code:
        nb.cells[i].outputs = []
        nb.cells[i].execution_count = None
    # timeout=None: cell_sentiment na CPU potrafi liczyć wiele minut.
    client = NotebookClient(nb, timeout=None, kernel_name=name,
                            resources={"metadata": {"path": str(ROOT)}})
    # Szum bibliotek (zmq o pętli Proactor, ostrzeżenia IPKernelApp ze stderr
    # jądra) nie ma nic dla operatora i psuje odczyt czytnikiem ekranu. Błędy
    # komórek przychodzą komunikatami jądra, nie jego stderr — nic nie ginie.
    warnings.filterwarnings("ignore", message="Proactor event loop", category=RuntimeWarning)
    ok, i = True, 0
    try:
        with client.setup_kernel(stderr=subprocess.DEVNULL):
            for n, i in enumerate(code, 1):
                print(t(UI_LANG, "run_all.notebook_cell", i=n, total=len(code), tag=_tag(nb.cells[i], i)),
                      flush=True)
                client.execute_cell(nb.cells[i], i)
    except CellExecutionError as e:
        ok = False
        last = ANSI_RE.sub("", str(e)).strip().splitlines()[-1:] or [""]
        print(t(UI_LANG, "run_all.notebook_failed", tag=_tag(nb.cells[i], i), path=NOTEBOOK.name,
                error=last[0]))
    finally:
        nbformat.write(nb, NOTEBOOK)
    if ok:
        print(t(UI_LANG, "run_all.notebook_saved", path=NOTEBOOK.name, n=len(code)))
    return ok


def run_script(args):
    r = subprocess.run([sys.executable, *args], cwd=ROOT)
    return r.returncode


def main(argv=None):
    ap = argparse.ArgumentParser(description=t(UI_LANG, "run_all.description"))
    ap.add_argument("--skip-notebook", action="store_true", help=t(UI_LANG, "run_all.help_skip_notebook"))
    ap.add_argument("--no-shamanic", action="store_true", help=t(UI_LANG, "run_all.help_no_shamanic"))
    ap.add_argument("--no-book", action="store_true", help=t(UI_LANG, "run_all.help_no_book"))
    args = ap.parse_args(argv)
    os.chdir(ROOT)

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
