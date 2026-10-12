"""Księga Niedomówień (fiń. Sanomattomien kirja) — kryptograficzny dziennik z Północy.

Narzędzie pomocnicze dla skilla `ksiega-niedomowien`. Część deterministyczna
(filtry, podział na bloki, źródło prawdy, sędzia, księga) jest tutaj; część
twórcza (mglisty kontekst z lukami) i ślepe wypełnianie luk robi LLM.

Przepływ jednego bloku:
    scan     -> które foldery z export_results/ się kwalifikują (i dlaczego nie)
    prepare  -> pakiet roboczy: korzenie bloku + fragment źródła prawdy
    seal     -> walidacja szkicu LLM (draft.json) i zapis ślepej wersji (blind.json)
    fill     -> (opcjonalnie) ślepe zgadywanie przez API zgodne z OpenAI
                (guesses.json) — zamiast osobnego agenta platformy
    judge    -> porównanie zgadywań (guesses.json) z prawdą; odgadnięte fragmenty
                znikają, reszta trafia przyrostowo do księgi
    status   -> stan księgi i otwartych pakietów

Lokalizacja (konwencja repo): komunikaty konsoli = tr(UI_LANG, "kirja.*")
z dictionaries/{lang}/reports.yaml; treść Księgi = tr(BOOK_LANG, "book.*")
z dictionaries/{lang}/shamanic.yaml. BOOK_LANG to zawsze "fi", bo filtry
wpuszczają wyłącznie fińskie korpusy.

Wejście: wyłącznie podfoldery export_results/ z fińską nazwą, `<html lang="fi">`
w accessible_text.html, plikiem audio_scripts/raw_roots_chant.txt i bez
"przecieku gramatyki" (dane sprzed podłączenia omorfi są odrzucane).
Źródło prawdy: accessible_text.html ORAZ accessible_text.docx (odpowiedź do luki
musi występować w obu).

Zależności: omorfi (+ automaty *.hfst w katalogu repo) — wymagane, bo bez
analizatora nie da się sprawdzić, czy dane są pozbawione gramatyki. PyYAML
(twarda zależność repo od v1.1). HTML i DOCX czytane biblioteką standardową.
`fill` dodatkowo: openai + python-dotenv (już w requirements.txt).
"""

import argparse
import hashlib
import html as html_lib
import json
import os
import re
import sys
import unicodedata
import zipfile
from datetime import date
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path

# `t` jest tu często nazwą zmiennej pętli (tokeny), więc alias `tr`.
from shamanic_locale import get_ui_lang, t as tr

ROOT = Path(__file__).resolve().parent
UI_LANG = get_ui_lang()
BOOK_LANG = "fi"
BOOK_NAME = "Sanomattomien_kirja"
WORK_DIR_NAME = "_kirja_tyotila"

# Kolejność inna niż w notebooku: chant i tekst są tu sprowadzane do małych liter,
# a wariant "recased" daje wtedy fałszywe odczyty nazw własnych (onet -> One).
OMORFI_MODEL_CANDIDATES = [
    "omorfi.describe.hfst",
    "omorfi.analyse.hfst",
    "omorfi_recased.describe.hfst",
]

# --- progi (dobrane na realnych danych z export_results, patrz SKILL.md) ---
NAME_FI_MIN = 0.5          # odsetek tokenów nazwy folderu znanych omorfi
CHANT_FI_MIN = 0.6         # odsetek słów chantu rozpoznanych jako fińskie
GRAMMAR_LEAK_MAX = 1.0     # (B + 2*G) na 100 terminów TF-IDF; powyżej = dane sprzed omorfi
BLOCK_MIN, BLOCK_MAX = 3, 6
WINDOW_PARAS = 2           # korzenie bloku muszą współwystępować w ≤ 2 sąsiednich akapitach
TRUTH_MAX_CHARS = 1600
GAPS_MIN, FRAGMENTS_MIN, FRAGMENTS_MAX = 3, 4, 9
COPY_NGRAM = 7             # tyle kolejnych słów wspólnych ze źródłem = kopiowanie

CONTENT_UPOS = {"NOUN", "PROPN", "VERB", "ADJ", "NUM"}
GAP_RE = re.compile(r"\{\{(\d+)\}\}")
WORD_RE = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿĀ-žА-яЁё]+(?:-[0-9A-Za-zÀ-ÖØ-öø-ÿĀ-žА-яЁё]+)*")
SENT_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+(?=[\"“”'(]?[A-ZÄÖÅ0-9])")

HEADER_FALLBACK_RE = [
    re.compile(r"^-{2,}.*-{2,}$"),
    re.compile(r"^(TTS|Instrukcja TTS|Istruzione TTS|Инструкция TTS)\b", re.I),
]


class Refusal(Exception):
    """Twarda odmowa — folder nie spełnia filtrów Księgi."""


# ==========================================
# omorfi
# ==========================================

_OMORFI = None


def omorfi():
    global _OMORFI
    if _OMORFI is not None:
        return _OMORFI
    try:
        from omorfi.omorfi import Omorfi
    except ImportError:
        sys.exit(tr(UI_LANG, "kirja.err_no_omorfi"))
    model = next((ROOT / p for p in OMORFI_MODEL_CANDIDATES if (ROOT / p).exists()), None)
    if model is None:
        sys.exit(tr(UI_LANG, "kirja.err_no_automata"))
    om = Omorfi()
    om.load_analyser(str(model))
    _OMORFI = om
    return om


@lru_cache(maxsize=131072)
def analyses(surf):
    """Krotki (lemma, UPOS) ze skończoną wagą; pusta krotka = słowo nieznane omorfi."""
    from omorfi.token import Token
    tok = Token.fromsurf(surf)
    omorfi().analyse(tok)
    out = []
    for a in tok.analyses:
        raw = a.raw or ""
        if a.weight == float("inf") or "GUESS=UNKNOWN" in raw:
            continue
        # BLACKLIST=TOOSHORTFORCOMPOUND dotyczy członu złożenia: samodzielne "maa"
        # też go nosi i jest poprawne; odrzucamy tylko złożenia z takim członem
        # (śmieciowe "kapinsk" -> kappi+SK).
        if "BLACKLIST" in raw and "BOUNDARY=COMPOUND" in raw:
            continue
        lemma = "".join(a.get_lemmas() or [])
        if not lemma:
            continue
        if "-" in lemma and "-" not in surf:
            lemma = lemma.replace("-", "")
        out.append((lemma.lower(), a.get_upos()))
    return tuple(out)


def lemmas(surf):
    return {l for l, _ in analyses(surf.lower())}


def common_lemmas(surf):
    """Lematy bez odczytów wyłącznie jako nazwa własna.

    Słownik nazw omorfi jest najsłabszy (i w wariancie recased zgaduje nazwy dla
    małych liter), więc do oceny gramatyki słowo z samymi odczytami PROPN
    traktujemy jak nieznane — tak samo jak nazwiska z transkrypcji.
    """
    an = analyses(surf.lower())
    if an and all(u == "PROPN" for _, u in an):
        return set()
    return {l for l, _ in an}


def fold(s):
    """Usuwa diakrytyki obce dla fińskiego (ń→n, ł→l), zostawia ä/ö/å."""
    s = s.lower().replace("ł", "l")
    out = []
    for ch in s:
        if ch in "äöå":
            out.append(ch)
            continue
        out.append("".join(c for c in unicodedata.normalize("NFD", ch) if not unicodedata.combining(c)))
    return "".join(out)


# ==========================================
# Źródło prawdy: accessible_text.html + .docx
# ==========================================

class _ParaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.lang, self.paras, self._cur = None, [], None

    def handle_starttag(self, tag, attrs):
        if tag == "html":
            self.lang = (dict(attrs).get("lang") or "").lower() or None
        elif tag == "p":
            self._cur = []

    def handle_endtag(self, tag):
        if tag == "p" and self._cur is not None:
            text = re.sub(r"\s+", " ", "".join(self._cur)).strip()
            if text:
                self.paras.append(text)
            self._cur = None

    def handle_data(self, data):
        if self._cur is not None:
            self._cur.append(data)


def read_html(path):
    p = _ParaParser()
    p.feed(path.read_text(encoding="utf-8", errors="replace"))
    return p.lang, p.paras


def read_docx(path):
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    paras = []
    for para in re.findall(r"<w:p[ >].*?</w:p>", xml, flags=re.S):
        if re.search(r'<w:pStyle w:val="(Heading|Title)', para):
            continue  # nagłówek H1 dokładany przez notebook
        text = "".join(re.findall(r"<w:t(?: [^>]*)?>(.*?)</w:t>", para, flags=re.S))
        text = re.sub(r"\s+", " ", html_lib.unescape(text)).strip()
        if text:
            paras.append(text)
    return paras


def norm_space(s):
    return re.sub(r"\s+", " ", s).strip().lower()


class Truth:
    """Obie wersje accessible_text. Akapity z HTML; DOCX jako kontrola krzyżowa."""

    def __init__(self, folder):
        h, d = folder / "accessible_text.html", folder / "accessible_text.docx"
        self.lang, self.paras, docx_paras = None, [], []
        if h.exists():
            self.lang, self.paras = read_html(h)
        if d.exists():
            docx_paras = read_docx(d)
            if not self.paras:
                self.paras = docx_paras
        self.has_html, self.has_docx = h.exists(), d.exists()
        self.html_text = norm_space(" ".join(self.paras)) if self.has_html else ""
        self.docx_text = norm_space(" ".join(docx_paras))
        self.versions_agree = (not (self.has_html and self.has_docx)
                               or [norm_space(p) for p in self.paras] == [norm_space(p) for p in docx_paras]
                               or [norm_space(p) for p in self.paras] == [norm_space(p) for p in docx_paras[1:]])

    def contains(self, span):
        s = norm_space(span)
        texts = [t for t in (self.html_text, self.docx_text) if t]
        return bool(texts) and all(s in t for t in texts)


# ==========================================
# raw_roots_chant.txt
# ==========================================

@lru_cache(maxsize=1)
def known_header_lines():
    lines = set()
    try:
        import yaml
        for f in (ROOT / "dictionaries").glob("*/shamanic.yaml"):
            data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            hdr = ((data.get("roots") or {}).get("header")) or ""
            lines |= {ln.strip() for ln in hdr.splitlines() if ln.strip()}
    except Exception:
        pass
    return lines


def parse_chant(path):
    """Zwraca (lista korzeni w kolejności, usunięte linie nagłówka, linie nierozpoznane)."""
    roots, header, junk = [], [], []
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip().lstrip("﻿")
        if not line:
            continue
        if line in known_header_lines() or any(r.search(line) for r in HEADER_FALLBACK_RE):
            header.append(line)
            continue
        if line.endswith(" .") or line.endswith("."):
            parts = [p.strip() for p in line.rstrip(".").split(" . ")]
            parts = [p for p in parts if p]
            if parts and all(p == p.upper() for p in parts):
                roots.extend(parts)
                continue
        junk.append(line)
    return roots, header, junk


# ==========================================
# Filtry
# ==========================================

def classify_word(w):
    """'base' — forma słownikowa; 'inflected' — fińska forma odmieniona; 'unknown'."""
    parts = w.lower().split()
    res = []
    for p in parts:
        L = common_lemmas(p)
        res.append("unknown" if not L else ("base" if p in L else "inflected"))
    if "inflected" in res:
        return "inflected"
    return "base" if "base" in res else "unknown"


def is_content(w):
    for p in w.lower().split():
        an = analyses(p)
        if not an:
            continue  # nazwy własne i transkrypcje Whispera — treść
        if not any(l == p and u in CONTENT_UPOS for l, u in an):
            return False
    return True


def grammar_leak(folder, para_tokens):
    """Wskaźnik przecieku gramatyki liczony na pełnym keywords_tfidf.csv.

    B = znane fińskie formy odmienione (lemmatyzator nie uciął końcówki),
    G = śmieciowe lematy spaCy (np. *mietia* ← mieti, omorfi: miettiä).
    """
    import csv
    kw = folder / "keywords_tfidf.csv"
    terms = []
    if kw.exists():
        with kw.open(encoding="utf-8-sig") as f:
            terms = [r.get("term", "") for r in csv.DictReader(f)]
    if not terms:
        roots, _, _ = parse_chant(folder / "audio_scripts" / "raw_roots_chant.txt")
        terms = [r.lower() for r in roots]
    words = {p.lower() for t in terms for p in t.split()}
    toks = sorted(para_tokens)
    B = sorted(w for w in words if common_lemmas(w) and w not in common_lemmas(w))
    G = []
    for w in words:
        if common_lemmas(w) or len(w) < 4:
            continue
        stem = w[:max(3, len(w) - 2)]
        cands = [s for s in toks if s.startswith(stem)]
        if cands and all(common_lemmas(s) for s in cands):
            G.append(w)
    rate = (len(B) + 2 * len(G)) / max(1, len(terms)) * 100
    return rate, B, sorted(G)


def tokens_of(text):
    out = []
    for m in WORD_RE.finditer(text):
        w = m.group(0).lower()
        out.append(w)
        if "-" in w:
            out.extend(x for x in w.split("-") if x)
    return out


def evaluate_folder(folder):
    """Werdykt dla jednego folderu: dict z polami ok, reasons, ... (bez wyjątków)."""
    v = {"folder": folder.name, "ok": False, "reasons": []}
    if folder.name.startswith(("_", ".")) or folder.name == WORK_DIR_NAME:
        v["reasons"].append(tr(UI_LANG, "kirja.reason_technical"))
        return v
    chant = folder / "audio_scripts" / "raw_roots_chant.txt"
    if not chant.exists():
        v["reasons"].append(tr(UI_LANG, "kirja.reason_no_chant"))
        return v

    name_toks = [t for t in re.split(r"[_\s\-\.]+", folder.name) if t and not t.isdigit()]
    name_fi = sum(bool(lemmas(t)) for t in name_toks) / max(1, len(name_toks))
    v["name_fi"] = round(name_fi, 2)
    if name_fi < NAME_FI_MIN:
        v["reasons"].append(tr(UI_LANG, "kirja.reason_name_not_fi", ratio=f"{name_fi:.2f}", min=NAME_FI_MIN))

    truth = Truth(folder)
    v["lang"] = truth.lang
    if not (truth.has_html or truth.has_docx):
        v["reasons"].append(tr(UI_LANG, "kirja.reason_no_truth"))
    elif truth.lang not in (None, "fi"):
        v["reasons"].append(tr(UI_LANG, "kirja.reason_lang_not_fi", code=truth.lang))
    if truth.has_html and truth.has_docx and not truth.versions_agree:
        v["reasons"].append(tr(UI_LANG, "kirja.reason_versions_differ"))
    if not (truth.has_html and truth.has_docx):
        v["warning"] = tr(UI_LANG, "kirja.warn_single_version")

    roots, header, junk = parse_chant(chant)
    v["header_stripped"] = bool(header)
    v["n_roots"] = len(roots)
    if not roots:
        v["reasons"].append(tr(UI_LANG, "kirja.reason_empty_chant"))
        return v
    fi_ratio = sum(classify_word(r) != "unknown" for r in roots) / len(roots)
    v["chant_fi"] = round(fi_ratio, 2)
    if fi_ratio < CHANT_FI_MIN:
        v["reasons"].append(tr(UI_LANG, "kirja.reason_chant_not_fi", ratio=f"{fi_ratio:.2f}", min=CHANT_FI_MIN))

    if not v["reasons"]:
        para_tokens = {t for p in truth.paras for t in tokens_of(p)}
        rate, B, G = grammar_leak(folder, para_tokens)
        v["grammar_leak"] = round(rate, 2)
        v["leak_examples"] = (B + G)[:8]
        if rate > GRAMMAR_LEAK_MAX:
            v["reasons"].append(tr(UI_LANG, "kirja.reason_grammar_leak", rate=f"{rate:.2f}",
                                   max=GRAMMAR_LEAK_MAX, examples=", ".join((B + G)[:6])))
    v["ok"] = not v["reasons"]
    return v


# ==========================================
# Bloki
# ==========================================

def split_sentences(p):
    return [s.strip() for s in SENT_SPLIT_RE.split(p) if s.strip()]


class Index:
    def __init__(self, truth):
        self.paras = truth.paras
        self.sents = [split_sentences(p) for p in self.paras]
        self.sent_lemmas = []
        for sl in self.sents:
            row = []
            for s in sl:
                toks = tokens_of(s)
                row.append([(fold(t), {fold(l) for l in lemmas(t)}) for t in toks])
            self.sent_lemmas.append(row)

    @staticmethod
    def _part_hits(part, toks):
        p = fold(part)
        unknown = not lemmas(part)
        for t, L in toks:
            if p in L or t == p:
                return True
            if unknown and len(p) >= 4 and t.startswith(p) and len(t) - len(p) <= 4:
                if not L or any(l.startswith(p) for l in L):
                    return True
        return False

    def sentence_hits(self, root, pi, si):
        toks = self.sent_lemmas[pi][si]
        return all(self._part_hits(part, toks) for part in root.lower().split())

    def para_hits(self, root, pi):
        return any(self.sentence_hits(root, pi, si) for si in range(len(self.sents[pi])))

    def window_hits(self, roots, win):
        return {r for r in roots if any(self.para_hits(r, pi) for pi in win)}

    def cover(self, roots):
        """Zachłanne pokrycie korzeni oknami po WINDOW_PARAS akapitów.

        Zwraca listę (okno, trafione_korzenie). Mniej okien = bardziej zwarta prawda.
        """
        n = len(self.paras)
        windows = [list(range(s, min(n, s + WINDOW_PARAS))) for s in range(n)]
        hits = [self.window_hits(roots, w) for w in windows]
        left, out = set(roots), []
        while left:
            k = max(range(n), key=lambda i: (len(hits[i] & left), -i))
            got = hits[k] & left
            if not got:
                break
            out.append((windows[k], got))
            left -= got
        return out

    def attested(self, root):
        return any(self.para_hits(root, pi) for pi in range(len(self.paras)))


def _chunk(seq, idx):
    """Podział ciągu korzeni na ciągłe bloki BLOCK_MIN..BLOCK_MAX (DP).

    Koszt bloku = liczba okien źródła potrzebnych do pokrycia jego korzeni;
    przy remisie wygrywają bloki bliższe 5 korzeniom.
    """
    n = len(seq)
    if n < BLOCK_MIN:
        return []
    cache = {}

    def cost(i, j):
        if (i, j) not in cache:
            cache[(i, j)] = len(idx.cover(seq[i:j])) + abs((j - i) - 5) * 0.1
        return cache[(i, j)]

    INF = float("inf")
    best = [INF] * (n + 1)
    prev = [None] * (n + 1)
    best[0] = 0
    for j in range(1, n + 1):
        for size in range(BLOCK_MIN, BLOCK_MAX + 1):
            i = j - size
            if i >= 0 and best[i] < INF and best[i] + cost(i, j) < best[j]:
                best[j], prev[j] = best[i] + cost(i, j), i
    end = n
    while end > 0 and best[end] == INF:
        end -= 1  # resztę (< BLOCK_MIN) dokleja się do ostatniego bloku niżej
    cuts, j = [], end
    while j > 0:
        cuts.append((prev[j], j)); j = prev[j]
    cuts.reverse()
    if cuts and end < n:
        i0, _ = cuts[-1]
        cuts[-1] = (i0, n)
    return [seq[i:j] for i, j in cuts]


def build_blocks(folder):
    truth = Truth(folder)
    roots, _, _ = parse_chant(folder / "audio_scripts" / "raw_roots_chant.txt")
    idx = Index(truth)
    seq, dropped = [], {"grammar": [], "filler": [], "unattested": []}
    seen = set()
    for r in roots:
        if r in seen:
            continue
        seen.add(r)
        if classify_word(r) == "inflected":
            dropped["grammar"].append(r)
        elif not is_content(r):
            dropped["filler"].append(r)
        elif not idx.attested(r):
            dropped["unattested"].append(r)
        else:
            seq.append(r)

    blocks = []
    for n, block in enumerate(_chunk(seq, idx), 1):
        cover = idx.cover(block)
        budget = TRUTH_MAX_CHARS // max(1, len(cover))
        sents = []
        for win, got in cover:
            cand = [(pi, si) for pi in win for si in range(len(idx.sents[pi]))
                    if any(idx.sentence_hits(r, pi, si) for r in got)]
            scored = sorted(cand, key=lambda ps: (-sum(idx.sentence_hits(r, *ps) for r in got), ps))
            keep, total, need = [], 0, set(got)
            for ps in scored:  # najpierw zdania wnoszące brakujące korzenie
                adds = {r for r in need if idx.sentence_hits(r, *ps)}
                s = idx.sents[ps[0]][ps[1]]
                if (adds or total + len(s) <= budget) and not (total + len(s) > budget * 1.5 and keep):
                    keep.append(ps); total += len(s); need -= adds
            sents.extend(idx.sents[pi][si] for pi, si in sorted(keep))
        bid = hashlib.sha1(f"{folder.name}|{' . '.join(block)}".encode("utf-8")).hexdigest()[:10]
        blocks.append({"id": bid, "folder": folder.name, "block_no": n, "roots": block,
                       "chant": " . ".join(block) + " .",
                       "truth": {"paragraph_ids": sorted({p + 1 for w, _ in cover for p in w}),
                                 "places": len(cover), "sentences": sents}})
    return blocks, dropped


# ==========================================
# Księga i stan
# ==========================================

def export_dir(args):
    return Path(args.root).resolve() / "export_results" if args.root else ROOT / "export_results"


def book_paths(exp):
    return (exp / f"{BOOK_NAME}.md", exp / f"{BOOK_NAME}.tila.json",
            exp / f"{BOOK_NAME}.avain.json", exp / WORK_DIR_NAME)


def load_json(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def done_ids(exp):
    book, state_p, _, _ = book_paths(exp)
    ids = set(load_json(state_p, {}).get("blocks", {}).keys())
    if book.exists():
        ids |= set(re.findall(r"kirja:id=([0-9a-f]{10})", book.read_text(encoding="utf-8")))
    return ids


def resolve_folder(exp, name):
    cand = exp / name
    if not cand.is_dir():
        matches = [d for d in exp.iterdir() if d.is_dir() and d.name.lower().startswith(name.lower())]
        if len(matches) != 1:
            raise Refusal(tr(UI_LANG, "kirja.err_ambiguous_folder", name=name))
        cand = matches[0]
    v = evaluate_folder(cand)
    if not v["ok"]:
        raise Refusal(tr(UI_LANG, "kirja.refusal_folder", name=cand.name, reasons="; ".join(v["reasons"])))
    return cand, v


# ==========================================
# Komendy
# ==========================================

def cmd_scan(args):
    exp = export_dir(args)
    folders = [exp / args.folder] if args.folder else sorted(d for d in exp.iterdir() if d.is_dir())
    verdicts = [evaluate_folder(f) if f.is_dir() else
                {"folder": f.name, "ok": False, "reasons": [tr(UI_LANG, "kirja.reason_missing")]} for f in folders]
    if args.json:
        print(json.dumps(verdicts, ensure_ascii=False, indent=2))
        return 0 if all(v["ok"] for v in verdicts) or not args.folder else 2
    for v in verdicts:
        if v["ok"]:
            header = tr(UI_LANG, "kirja.header_stripped" if v.get("header_stripped") else "kirja.header_none")
            print(tr(UI_LANG, "kirja.scan_ok", folder=v["folder"], rate=v.get("grammar_leak"), header=header))
        else:
            print(tr(UI_LANG, "kirja.scan_rejected", folder=v["folder"]))
        for r in v["reasons"]:
            print(f"       - {r}")
        if v.get("warning"):
            print(f"       ! {v['warning']}")
    return 0 if all(v["ok"] for v in verdicts) or not args.folder else 2


def cmd_prepare(args):
    exp = export_dir(args)
    _, _, _, work = book_paths(exp)
    if args.folder:
        try:
            folders = [resolve_folder(exp, args.folder)[0]]
        except Refusal as e:
            print(tr(UI_LANG, "kirja.refusal", message=e))
            return 3
    else:
        folders = [d for d in sorted(exp.iterdir()) if d.is_dir() and evaluate_folder(d)["ok"]]
    done = done_ids(exp)
    created = []
    for folder in folders:
        blocks, dropped = build_blocks(folder)
        if args.verbose:
            print(tr(UI_LANG, "kirja.info_blocks", folder=folder.name, count=len(blocks),
                     dropped="; ".join(f"{tr(UI_LANG, 'kirja.drop_' + k)}={v}" for k, v in dropped.items() if v) or "-"))
        for b in blocks:
            if b["id"] in done:
                continue
            d = work / b["id"]
            if (d / "packet.json").exists():
                created.append(d)
                continue
            b["created"] = date.today().isoformat()
            save_json(d / "packet.json", b)
            created.append(d)
            if len(created) >= args.limit:
                break
        if len(created) >= args.limit:
            break
    if not created:
        print(tr(UI_LANG, "kirja.info_up_to_date"))
        return 0
    for d in created[: args.limit]:
        p = load_json(d / "packet.json", {})
        print(tr(UI_LANG, "kirja.packet_line", path=d, folder=p["folder"], block=p["block_no"], chant=p["chant"]))
    return 0


def _ngrams(words, n):
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


def cmd_seal(args):
    d = Path(args.packet)
    packet = load_json(d / "packet.json", None)
    draft = load_json(d / "draft.json", None)
    if not packet or not draft:
        print(tr(UI_LANG, "kirja.err_packet_missing"))
        return 1
    exp = export_dir(args)
    folder, _ = resolve_folder(exp, packet["folder"])
    truth = Truth(folder)
    errors = []
    frags = draft.get("fragments") or []
    if not (FRAGMENTS_MIN <= len(frags) <= FRAGMENTS_MAX):
        errors.append(tr(UI_LANG, "kirja.err_fragment_count", count=len(frags), min=FRAGMENTS_MIN, max=FRAGMENTS_MAX))
    root_lemmas = {fold(p) for r in packet["roots"] for p in r.lower().split()}
    all_text = " ".join(f.get("text", "") for f in frags).lower()
    src_words = tokens_of(" ".join(truth.paras))
    src_ngrams = _ngrams(src_words, COPY_NGRAM)
    gaps, seen_nums = 0, set()
    for k, f in enumerate(frags, 1):
        text, ans = f.get("text", ""), (f.get("answer") or "").strip()
        nums = GAP_RE.findall(text)
        if len(nums) > 1:
            errors.append(tr(UI_LANG, "kirja.err_multi_gap", k=k))
        if nums and not ans:
            errors.append(tr(UI_LANG, "kirja.err_gap_no_answer", k=k))
        if ans and not nums:
            errors.append(tr(UI_LANG, "kirja.err_answer_no_gap", k=k))
        if nums:
            gaps += 1
            if nums[0] in seen_nums:
                errors.append(tr(UI_LANG, "kirja.err_dup_gap", k=k, gap=nums[0]))
            seen_nums.add(nums[0])
            if not truth.contains(ans):
                errors.append(tr(UI_LANG, "kirja.err_answer_not_in_truth", k=k, answer=ans))
            ans_l = {fold(l) for w in tokens_of(ans) for l in (lemmas(w) or {w})}
            if ans_l and ans_l <= root_lemmas:
                errors.append(tr(UI_LANG, "kirja.err_answer_is_root", k=k, answer=ans))
            if ans.lower() in GAP_RE.sub("", all_text):
                errors.append(tr(UI_LANG, "kirja.err_answer_in_text", k=k, answer=ans))
        copied = _ngrams(tokens_of(GAP_RE.sub(" ", text)), COPY_NGRAM) & src_ngrams
        if copied:
            errors.append(tr(UI_LANG, "kirja.err_copied", k=k, ngram=sorted(copied)[0]))
    if gaps < GAPS_MIN:
        errors.append(tr(UI_LANG, "kirja.err_too_few_gaps", gaps=gaps, min=GAPS_MIN))
    if errors:
        print(tr(UI_LANG, "kirja.draft_rejected"))
        for e in errors:
            print(f"  - {e}")
        return 4
    blind = {"id": packet["id"], "chant": packet["chant"],
             "fragments": [{"text": GAP_RE.sub(lambda m: f"____({m.group(1)})", f["text"])} for f in frags]}
    save_json(d / "blind.json", blind)
    print(tr(UI_LANG, "kirja.ok_sealed", gaps=gaps, path=d / "blind.json"))
    print(json.dumps(blind, ensure_ascii=False, indent=2))
    return 0


def _norm_set(text):
    out = []
    for w in tokens_of(text):
        L = {fold(l) for l in lemmas(w)} | {fold(w)}
        if analyses(w) and not any(u in CONTENT_UPOS for _, u in analyses(w)) and not w.isdigit():
            continue  # pomijamy słowa funkcyjne
        out.append(L)
    return out


def _similar(a, b):
    """1 - znormalizowana odległość Levenshteina."""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return 1 - prev[-1] / max(len(a), len(b))


def guessed(answer, guess):
    """Czy zgadywanie trafia w prawdę? Porównanie po lematach omorfi (+ prefiksy nazw)."""
    if not guess:
        return False
    a, g = _norm_set(answer), _norm_set(guess)
    if not a:
        return norm_space(answer) == norm_space(guess)

    def close(x, y):
        if len(x) < 4 or len(y) < 4:
            return False
        # odmiana nazw własnych nieznanych omorfi (Kaczyński ~ Kaczyńskin)
        if (x.startswith(y) or y.startswith(x)) and abs(len(x) - len(y)) <= 3:
            return True
        # człon główny złożenia (pommiuhkaukset ~ uhkaukset)
        if min(len(x), len(y)) >= 5 and (x.endswith(y) or y.endswith(x)):
            return True
        # warianty pisowni / literówki (palovarotin ~ palovaroitin)
        return min(len(x), len(y)) >= 6 and _similar(x, y) >= 0.85

    def hit(aset):
        return any(aset & gset or any(close(x, y) for x in aset for y in gset) for gset in g)

    hits = sum(hit(s) for s in a)
    return hits / len(a) >= (1.0 if len(a) <= 2 else 2 / 3)


def _read_config():
    """config.json, potem config.ini (treść zawsze JSON) — konwencja repo."""
    for name in ("config.json", "config.ini"):
        p = ROOT / name
        if p.is_file():
            try:
                return json.loads(p.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                return {}
    return {}


FILLER_PROMPT = """You are the blind gap-filler for a Finnish cryptic-diary game. \
Answer only from the text below and your own knowledge of Finnish.
Below is a JSON entry: a chant of root words and fragments of a misty Finnish text. \
Each gap is written as ____(N). For every gap, guess the single most likely word or short \
phrase in Finnish, in the grammatical form that fits the sentence. Ignore bracketed audio \
tags like [whispers].

ENTRY:
{entry}

Reply with ONLY a JSON object, no prose, in exactly this shape:
{shape}"""


def _parse_guesses(text):
    """Wyciąga {"guesses": {...}} z odpowiedzi modelu (toleruje ```json i prozę wokół)."""
    m = re.search(r"\{.*\}", text or "", flags=re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    g = data.get("guesses", data) if isinstance(data, dict) else None
    if not isinstance(g, dict):
        return None
    return {str(k): str(v) for k, v in g.items()}


def cmd_fill(args):
    """Ślepe wypełnienie przez API zgodne z OpenAI. Czyta WYŁĄCZNIE blind.json.

    Klucz: zawsze OPENAI_API_KEY z golden_key.env (ten sam parametr co
    shamanic_ai.py). Po przekierowaniu base URL na innego dostawcę zgodnego z
    OpenAI (np. OpenRouter) ta sama zmienna ma zawierać klucz tego dostawcy.
    """
    d = Path(args.packet)
    blind = load_json(d / "blind.json", None)
    if not blind:
        print(tr(UI_LANG, "kirja.err_no_blind"))
        return 1
    try:
        from dotenv import load_dotenv
        from openai import OpenAI
    except ImportError:
        print(tr(UI_LANG, "kirja.err_no_openai"))
        return 1
    load_dotenv(ROOT / "golden_key.env")
    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not key:
        print(tr(UI_LANG, "kirja.err_no_key"))
        return 1
    cfg = _read_config()
    model = args.model or (cfg.get("kirja_filler_model") or "").strip() or "gpt-4o"
    base_url = args.base_url or (cfg.get("kirja_filler_base_url") or "").strip() or None

    nums = sorted({n for f in blind["fragments"] for n in re.findall(r"____\((\d+)\)", f["text"])}, key=int)
    entry = json.dumps({"chant": blind["chant"], "fragments": [f["text"] for f in blind["fragments"]]},
                       ensure_ascii=False, indent=1)
    shape = json.dumps({"guesses": {n: "..." for n in nums}}, ensure_ascii=False)
    print(tr(UI_LANG, "kirja.llm_filler", model=model,
             endpoint=base_url or tr(UI_LANG, "kirja.default_endpoint")))
    try:
        client = OpenAI(api_key=key, base_url=base_url)
        # bez temperature: część nowszych modeli odrzuca wartości niedomyślne
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": FILLER_PROMPT.format(entry=entry, shape=shape)}])
        reply = resp.choices[0].message.content or ""
    except Exception as e:  # sieć, klucz, model — jeden czytelny komunikat
        print(tr(UI_LANG, "kirja.err_call", error=e))
        return 1
    guesses = _parse_guesses(reply)
    if guesses is None:
        print(tr(UI_LANG, "kirja.err_bad_reply", reply=reply[:300]))
        return 1
    missing = [n for n in nums if not guesses.get(n, "").strip()]
    if missing:
        print(tr(UI_LANG, "kirja.warn_missing_guess", gaps=", ".join(missing)))
    save_json(d / "guesses.json", {"guesses": guesses, "filler": {"model": model, "base_url": base_url}})
    print(tr(UI_LANG, "kirja.ok_guesses", path=d / "guesses.json", count=len(nums)))
    return 0


def cmd_judge(args):
    d = Path(args.packet)
    packet, draft = load_json(d / "packet.json", None), load_json(d / "draft.json", None)
    blind, guesses = load_json(d / "blind.json", None), load_json(d / "guesses.json", None)
    if not all([packet, draft, blind, guesses]):
        print(tr(UI_LANG, "kirja.err_packet_incomplete"))
        return 1
    exp = export_dir(args)
    resolve_folder(exp, packet["folder"])  # filtr jeszcze raz — nie ma obejścia
    book, state_p, key_p, _ = book_paths(exp)
    if packet["id"] in done_ids(exp):
        print(tr(UI_LANG, "kirja.info_already_in_book", id=packet["id"]))
        return 0
    raw = guesses.get("guesses", guesses)
    g = {str(k): str(v) for k, v in raw.items() if isinstance(v, (str, int, float))}
    gap_marker = tr(BOOK_LANG, "book.gap_marker")
    kept, removed, open_key = [], [], {}
    for f in draft["fragments"]:
        nums = GAP_RE.findall(f["text"])
        if not nums:
            kept.append(f["text"])
            continue
        n = nums[0]
        if guessed(f["answer"], g.get(n, "")):
            removed.append({"gap": n, "answer": f["answer"], "guess": g.get(n, "")})
        else:
            open_key[n] = f["answer"]
            kept.append(GAP_RE.sub(gap_marker, f["text"]))
    state = load_json(state_p, {"blocks": {}, "entries": 0})
    record = {"folder": packet["folder"], "block_no": packet["block_no"], "chant": packet["chant"],
              "gaps": len(open_key) + len(removed), "guessed": len(removed),
              "date": date.today().isoformat()}
    if not open_key:
        record["status"] = "obvious"
        state["blocks"][packet["id"]] = record
        save_json(state_p, state)
        print(tr(UI_LANG, "kirja.obvious", count=len(removed)))
        return 0

    state["entries"] = state.get("entries", 0) + 1
    no = state["entries"]
    title = packet["folder"].replace("_", " ")
    if not book.exists():
        book.write_text(f"# {tr(BOOK_LANG, 'book.title')}\n\n*{tr(BOOK_LANG, 'book.intro', gap=gap_marker)}*\n",
                        encoding="utf-8")
    vieno = "\n>\n".join(f"> {line}" for line in kept)
    entry = (f"\n---\n\n## {tr(BOOK_LANG, 'book.entry_heading', no=no, title=title)}\n\n"
             f"<!-- kirja:id={packet['id']} | folder={packet['folder']} | block={packet['block_no']} "
             f"| gaps={len(open_key)}/{len(open_key) + len(removed)} | date={record['date']} -->\n\n"
             f"{tr(BOOK_LANG, 'book.katla_label')}: {packet['chant']}\n\n"
             f"{tr(BOOK_LANG, 'book.vieno_label')}\n\n{vieno}\n")
    with book.open("a", encoding="utf-8") as fh:
        fh.write(entry)
    key = load_json(key_p, {})
    key[packet["id"]] = {"entry": no, "folder": packet["folder"], "open": open_key,
                         "removed_obvious": removed}
    save_json(key_p, key)
    record.update(status="in_book", entry=no)
    state["blocks"][packet["id"]] = record
    save_json(state_p, state)
    print(tr(UI_LANG, "kirja.ok_entry", no=no, book=book.name, open=len(open_key), removed=len(removed)))
    for r in removed:
        print(tr(UI_LANG, "kirja.removed_line", gap=r["gap"], answer=r["answer"], guess=r["guess"]))
    return 0


def cmd_status(args):
    exp = export_dir(args)
    book, state_p, _, work = book_paths(exp)
    state = load_json(state_p, {"blocks": {}, "entries": 0})
    blocks = state.get("blocks", {})
    exists = tr(UI_LANG, "kirja.status_exists" if book.exists() else "kirja.status_missing")
    print(tr(UI_LANG, "kirja.status_book", path=book, state=exists))
    print(tr(UI_LANG, "kirja.status_counts", entries=state.get("entries", 0),
             obvious=sum(1 for b in blocks.values() if b.get("status") == "obvious")))
    if work.exists():
        for d in sorted(work.iterdir()):
            if d.is_dir() and d.name not in blocks:
                have = [n for n in ("draft.json", "blind.json", "guesses.json") if (d / n).exists()]
                print(tr(UI_LANG, "kirja.status_open", id=d.name,
                         files=", ".join(have) or tr(UI_LANG, "kirja.status_only_packet")))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Księga Niedomówień / Sanomattomien kirja")
    ap.add_argument("--root", help=argparse.SUPPRESS)  # testy: inny katalog z export_results/
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan"); s.add_argument("--folder"); s.add_argument("--json", action="store_true")
    s = sub.add_parser("prepare"); s.add_argument("--folder"); s.add_argument("--limit", type=int, default=1)
    s.add_argument("--verbose", action="store_true")
    s = sub.add_parser("seal"); s.add_argument("packet")
    s = sub.add_parser("fill"); s.add_argument("packet"); s.add_argument("--model"); s.add_argument("--base-url")
    s = sub.add_parser("judge"); s.add_argument("packet")
    sub.add_parser("status")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        return {"scan": cmd_scan, "prepare": cmd_prepare, "seal": cmd_seal, "fill": cmd_fill,
                "judge": cmd_judge, "status": cmd_status}[args.cmd](args)
    except Refusal as e:
        print(tr(UI_LANG, "kirja.refusal", message=e))
        return 3


if __name__ == "__main__":
    sys.exit(main())
