"""zrodlo_raportu.py — bramka generatora raportu: czy wyjścia notatnika
pochodzą ze źródła wskazanego w configu.

Dlaczego: `generate_report.py` czyta wyjścia komórek z `.ipynb`, a katalog
docelowy wylicza z `source_file` w configu. Bez tej bramki raport o źródle A
lądował w folderze źródła B — wystarczyło zmienić config po przebiegu albo
uruchomić notatnik rozszerzeniem Jupyter w VS Code bez zapisania wyjść do pliku.

Trzy warstwy, każda deterministyczna; odmowa wyłącznie na DOWÓD rozjazdu:

1. Ścieżka — notatnik drukuje dosłownie `Загрузка из файла: <source_file>`
   (albo `Загрузка URL: …`, albo komunikat o korpusie wbudowanym) oraz
   `Каталог проекта: …`. Porównujemy z configem i z folderem raportu.
2. Świeżość zapisu — `paragraphs.csv` / `sentences.csv` w folderze projektu
   powstają w każdym udanym przebiegu komórki eksportu. Jeśli są NOWSZE niż
   `.ipynb`, wyjścia z ostatniego przebiegu nie zostały zapisane do pliku.
3. Treść — `cell_corpus` drukuje dosłownie pierwsze 80 znaków pierwszych
   (do 5) stron po podziale. Każdy podgląd sprowadzamy do ciągu samych liter
   (casefold, bez spacji, cyfr, łączników, numerów stron) i szukamy go
   w takim samym ciągu z pliku źródłowego. Ciąg liter jest odporny na to, co
   loader robi z tekstem: sklejanie przeniesień, zwijanie spacji, usuwanie
   numerów stron i kolontytułów (kolontytuł stoi PRZED podglądem, więc podgląd
   nadal jest podciągiem). Odmowa tylko, gdy ŻADEN sprawdzalny podgląd nie
   występuje w źródle. Treść niesprawdzalna (obraz, URL bez sieci, PDF bez
   warstwy tekstu albo ze zniekształconą warstwą, brak biblioteki) nie blokuje —
   decydują wtedy warstwy 1–2, a raport mówi to wprost.

Bramka czyta tylko początek źródła (PDF: strony aż do podglądów + zapas,
pozostałe: kilka stron po 2000 znaków), więc nie kosztuje przebiegu loadera.
Napisy rosyjskie niżej to DANE: dosłowny stdout notatnika, który jest celowo
rosyjski (CLAUDE.md, „Notebook localization scope”).
"""
from __future__ import annotations

import ast
import os
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from shamanic_locale import PODSTAWY

# --- dosłowny stdout cell_corpus / cell_model (accessible_text_analyst.py) ---
_ZNACZNIK_KORPUSU = "Корпус готов:"
_RE_PLIK = re.compile(r"^Загрузка из файла: (.+?)\s*$", re.M)
_RE_URL = re.compile(r"^\s*Загрузка URL: (.+?)\s*$", re.M)
_RE_BRAK = re.compile(r"^\[ВНИМАНИЕ\] Источник не найден: (.+)\. Используется встроенный пример\.\s*$", re.M)
_ZNACZNIK_WBUDOWANY = "Используется встроенный корпус-пример"
_RE_KATALOG = re.compile(r"^Каталог проекта: (.+?)\s*$", re.M)
_RE_PODGLAD = re.compile(r"^  \[(\d+)\] (.*)\.\.\.$")
_ZNACZNIK_MODELU = "--- Загрузка языковой модели ---"
_ZNACZNIK_EKSPORTU = "--- Экспорт результатов ---"
_EKSPORT_GOTOWY = "Файлы сохранены в папку:"   # ostatni print cell_export
_OMORFI_AKTYWNY = "Подключён omorfi:"
_OMORFI_NIEAKTYWNY = ("Пакет omorfi не установлен", "Автоматы omorfi (*.hfst) не найдены")
_RE_OMORFI_BLAD = re.compile(r"^\[ВНИМАНИЕ\] Не удалось загрузить \S*omorfi\S*\.hfst", re.M)

PAGE_SIZE = 2000          # pseudostrony txt/docx/html/md w notatniku
MIN_LITER = 15            # krótszy podgląd nie rozróżnia dokumentów
ZAPAS_STRON = 5           # PDF: tyle niepustych stron ponad liczbę podglądów
PROG_ZNIEKSZTALCENIA = 0.30   # udział liter spoza alfabetów podstaw
OBRAZY = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}

# Litery wszystkich języków z podstaw (obie wielkości po casefold) — miara
# zniekształconej warstwy tekstu PDF; dane, nie lista pism.
_ALFABET = frozenset("".join(p["alfabet"] for p in PODSTAWY.values()).casefold())


def litery(tekst: str) -> str:
    """Ciąg samych liter, casefold, NFC."""
    return "".join(z for z in unicodedata.normalize("NFC", tekst).casefold() if z.isalpha())


# ============================================================
# Wyjścia notatnika
# ============================================================

def _stdout(cell) -> str:
    out = []
    for o in cell.get("outputs", []):
        if o.get("output_type") == "stream" and o.get("name") == "stdout":
            t = o.get("text", "")
            out.append("".join(t) if isinstance(t, list) else t)
    return "".join(out)


def _komorka(nb, tag, znacznik):
    """Stdout komórki po tagu jupytext, a dla starych notatników po treści."""
    kod = [c for c in nb.get("cells", []) if c.get("cell_type") == "code"]
    for c in kod:
        if tag in (c.get("metadata", {}).get("tags") or []):
            return _stdout(c)
    for c in kod:
        s = _stdout(c)
        if znacznik in s:
            return s
    return ""


@dataclass
class WyjsciaKorpusu:
    wykonano: bool = False
    rodzaj: str | None = None      # plik | url | wbudowany
    zrodlo: str | None = None      # dosłowny source_file z wydruku
    katalog: str | None = None     # „Каталог проекта: …”
    podglady: list = field(default_factory=list)


def wyjscia_korpusu(nb) -> WyjsciaKorpusu:
    s = _komorka(nb, "cell_corpus", _ZNACZNIK_KORPUSU)
    w = WyjsciaKorpusu()
    if _ZNACZNIK_KORPUSU not in s:
        return w
    w.wykonano = True
    if m := _RE_PLIK.search(s):
        w.rodzaj, w.zrodlo = "plik", m.group(1)
    elif m := _RE_URL.search(s):
        w.rodzaj, w.zrodlo = "url", m.group(1)
    elif m := _RE_BRAK.search(s):
        try:
            w.zrodlo = ast.literal_eval(m.group(1))
        except (ValueError, SyntaxError):
            w.zrodlo = m.group(1)
    if _ZNACZNIK_WBUDOWANY in s or w.rodzaj is None:
        # Źródła nie ma, loader nic nie zwrócił albo config pusty → korpus
        # wbudowany (PROJECT_NAME = _default). `zrodlo` = to, co próbowano.
        w.rodzaj = "wbudowany"
    if m := _RE_KATALOG.search(s):
        w.katalog = m.group(1)
    po = s.split(_ZNACZNIK_KORPUSU, 1)[1].splitlines()
    for linia in po[1:]:
        m = _RE_PODGLAD.match(linia)
        if m:
            w.podglady.append(m.group(2))
        elif linia.strip() and not linia.startswith("  ..."):
            break
    return w


def eksport_ukonczony(nb) -> bool:
    """Czy przebieg dotarł do końca komórki eksportu. Bez tego CSV w folderze
    są z WCZEŚNIEJSZEGO przebiegu, a raport (i jego znacznik omorfi) opisywałby
    inny przebieg niż eksporty, które czytają skrypty dalej w łańcuchu."""
    return _EKSPORT_GOTOWY in _komorka(nb, "cell_export", _ZNACZNIK_EKSPORTU)


def omorfi_status(nb) -> str:
    """'active' — omorfi poprawiał lematy; 'inactive' — fiński bez omorfi
    (brak pakietu, automatów albo błąd ładowania); 'absent' — brak śladu
    (korpus nie fiński albo notatnik sprzed omorfi)."""
    s = _komorka(nb, "cell_model", _ZNACZNIK_MODELU)
    if _OMORFI_AKTYWNY in s:
        return "active"
    if any(z in s for z in _OMORFI_NIEAKTYWNY) or _RE_OMORFI_BLAD.search(s):
        return "inactive"
    return "absent"


# ============================================================
# Źródło prawdy: początek pliku z configu jako ciąg liter
# ============================================================

def _kawalki_pdf(sciezka):
    import pdfplumber
    with pdfplumber.open(sciezka) as pdf:
        for strona in pdf.pages:
            yield strona.extract_text() or ""


def _kawalki_txt(sciezka):
    with open(sciezka, encoding="utf-8", errors="replace") as f:
        while True:
            k = f.read(PAGE_SIZE)
            if not k:
                return
            yield k


def _kawalki_docx(sciezka):
    from docx import Document
    for p in Document(sciezka).paragraphs:
        yield p.text


def _kawalki_html(sciezka):
    from bs4 import BeautifulSoup
    with open(sciezka, encoding="utf-8", errors="replace") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    yield soup.get_text(" ")


def _kawalki_md(sciezka):
    import markdown
    from bs4 import BeautifulSoup
    with open(sciezka, encoding="utf-8", errors="replace") as f:
        html = markdown.markdown(f.read(), extensions=["fenced_code", "tables"])
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["pre"]):
        tag.decompose()
    yield soup.get_text(" ")


_CZYTNIKI = {".pdf": _kawalki_pdf, ".txt": _kawalki_txt, ".text": _kawalki_txt,
             ".docx": _kawalki_docx, ".html": _kawalki_html, ".htm": _kawalki_html,
             ".md": _kawalki_md, ".markdown": _kawalki_md}


@dataclass
class Tresc:
    stan: str                      # zgodna | rozjazd | niesprawdzalna
    powod: str = ""                # dla niesprawdzalnej: image | url | missing_file | format | library | no_text | garbled | no_previews
    znalezione: int = 0
    sprawdzalne: int = 0


def sprawdz_tresc(zrodlo: str, podglady: list) -> Tresc:
    """Warstwa 3: podglądy stron z wydruku notatnika vs plik źródłowy."""
    if zrodlo.startswith(("http://", "https://")):
        return Tresc("niesprawdzalna", "url")
    ext = Path(zrodlo).suffix.lower()
    if ext in OBRAZY:
        return Tresc("niesprawdzalna", "image")
    if not os.path.isfile(zrodlo):
        return Tresc("niesprawdzalna", "missing_file")
    czytnik = _CZYTNIKI.get(ext)
    if czytnik is None:
        return Tresc("niesprawdzalna", "format")
    cele = [c for c in (litery(p) for p in podglady) if len(c) >= MIN_LITER]
    if not cele:
        return Tresc("niesprawdzalna", "no_previews")
    niezn = set(range(len(cele)))
    ciag, surowe, niepuste = "", "", 0
    budzet_liter = (len(cele) + 2) * PAGE_SIZE
    try:
        for kawalek in czytnik(zrodlo):
            surowe += kawalek if len(surowe) < 4 * budzet_liter else ""
            nowe = litery(kawalek)
            if nowe:
                niepuste += 1
            ciag += nowe
            niezn = {i for i in niezn if cele[i] not in ciag}
            if not niezn:
                break
            if ext == ".pdf":
                if niepuste >= len(cele) + ZAPAS_STRON:
                    break
            elif len(ciag) >= budzet_liter:
                break
    except ImportError:
        return Tresc("niesprawdzalna", "library")
    znalezione = len(cele) - len(niezn)
    if znalezione:
        return Tresc("zgodna", znalezione=znalezione, sprawdzalne=len(cele))
    if not ciag:
        return Tresc("niesprawdzalna", "no_text", sprawdzalne=len(cele))
    obce = sum(z not in _ALFABET for z in ciag) / len(ciag)
    if obce > PROG_ZNIEKSZTALCENIA or surowe.count("(cid:") >= 3:
        # Warstwa tekstu PDF bez mapy ToUnicode: loader mógł ją naprawić albo
        # przepuścić przez OCR — surowy tekst nie jest wtedy źródłem prawdy.
        return Tresc("niesprawdzalna", "garbled", sprawdzalne=len(cele))
    return Tresc("rozjazd", znalezione=0, sprawdzalne=len(cele))


# ============================================================
# Werdykt
# ============================================================

def _norm_sciezka(p: str) -> str:
    return os.path.normcase(os.path.abspath(unicodedata.normalize("NFC", p.strip())))


def _rowne(a: str, b: str) -> bool:
    if a.startswith(("http://", "https://")) or b.startswith(("http://", "https://")):
        return a.strip() == b.strip()
    return _norm_sciezka(a) == _norm_sciezka(b)


def _norm_katalog(p: str) -> tuple:
    return tuple(unicodedata.normalize("NFC", x).casefold() for x in Path(p.strip()).parts)


@dataclass
class Werdykt:
    ok: bool
    klucz: str                     # klucz generate_report.gate_* w reports.yaml
    argumenty: dict = field(default_factory=dict)
    tresc: Tresc | None = None


def sprawdz(nb, source_cfg: str, project_dir: Path, notebook_path: Path) -> Werdykt:
    """Pełny werdykt bramki. `source_cfg` = `source_file` z configu (może być "")."""
    w = wyjscia_korpusu(nb)
    source_cfg = (source_cfg or "").strip()
    if not w.wykonano:
        return Werdykt(False, "gate_no_outputs", {"notebook": str(notebook_path)})

    # --- 1. ścieżka ---
    if w.rodzaj == "wbudowany":
        if source_cfg:
            if w.zrodlo and _rowne(w.zrodlo, source_cfg):
                return Werdykt(False, "gate_source_not_loaded", {"source": source_cfg})
            return Werdykt(False, "gate_builtin_vs_config", {"source": source_cfg})
    else:
        if not source_cfg:
            return Werdykt(False, "gate_source_vs_empty", {"ran": w.zrodlo})
        if not _rowne(w.zrodlo, source_cfg):
            return Werdykt(False, "gate_source_mismatch", {"ran": w.zrodlo, "source": source_cfg})
    if w.katalog and _norm_katalog(w.katalog) != _norm_katalog(str(project_dir)):
        return Werdykt(False, "gate_dir_mismatch", {"ran": w.katalog, "folder": str(project_dir)})

    if not eksport_ukonczony(nb):
        return Werdykt(False, "gate_run_incomplete", {"notebook": str(notebook_path)})

    # --- 2. świeżość zapisu .ipynb ---
    try:
        nb_mtime = Path(notebook_path).stat().st_mtime
    except OSError:
        nb_mtime = None
    if nb_mtime is not None:
        for nazwa in ("paragraphs.csv", "sentences.csv"):
            p = Path(project_dir) / nazwa
            if p.is_file() and p.stat().st_mtime > nb_mtime:
                return Werdykt(False, "gate_outputs_not_saved",
                               {"export": str(p), "notebook": str(notebook_path)})

    # --- 3. treść ---
    if w.rodzaj == "wbudowany":
        return Werdykt(True, "gate_ok_builtin")
    tresc = sprawdz_tresc(w.zrodlo, w.podglady)
    if tresc.stan == "rozjazd":
        return Werdykt(False, "gate_content_mismatch",
                       {"source": source_cfg, "checked": tresc.sprawdzalne}, tresc)
    if tresc.stan == "zgodna":
        return Werdykt(True, "gate_ok_content",
                       {"found": tresc.znalezione, "checked": tresc.sprawdzalne}, tresc)
    return Werdykt(True, "gate_ok_path_only", {"reason": tresc.powod}, tresc)
