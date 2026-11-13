"""Bramka: każdy workflow instaluje DOKŁADNIE ten Python, na którym projekt przetestowano.

`setup-python` z `python-version: '3.14'` bierze najnowszy patch — 2026-10-21 runner
miał CPython 3.14.8, a lokalny interpreter (venv, kernel `analyst_env`) to 3.14.3.
Pięć patchy różnicy bywa nieszkodliwe, ale testy chodzą m.in. przez `ast`, a nowy
patch może zmienić zachowanie albo wprowadzić regresję: zielone CI nie mówiłoby
wtedy nic o tym, co działa u użytkownika. Jedno źródło prawdy to
`audyt_zaleznosci.PYTHON_PRZETESTOWANY`; bump interpretera = zmiana tej stałej,
a ta bramka wymusza przestawienie workflowów w tym samym commicie.

Uruchom:  .venv/Scripts/python .github/scripts/test_python_ci.py   (tylko stdlib)
"""
import ast
import re
import shlex
import sys
import unittest
from pathlib import Path

KORZEN = Path(__file__).resolve().parents[2]
CUDZYSLOWY = chr(39) + chr(34)


def python_przetestowany(plik: Path) -> str:
    """Wartość PYTHON_PRZETESTOWANY czytana AST-em (bez importu modułu i jego zależności)."""
    for wezel in ast.parse(plik.read_text(encoding="utf-8")).body:
        if isinstance(wezel, ast.Assign) and any(
                isinstance(c, ast.Name) and c.id == "PYTHON_PRZETESTOWANY" for c in wezel.targets):
            return ast.literal_eval(wezel.value)
    raise LookupError(f"PYTHON_PRZETESTOWANY not found in {plik}")


def wersje_w_workflow(tekst: str) -> list[str]:
    """Wszystkie wartości `python-version:` w treści workflowa."""
    wynik = []
    for linia in tekst.splitlines():
        s = linia.strip()
        if s.startswith("python-version:"):
            wynik.append(s.split(":", 1)[1].split("#", 1)[0].strip().strip(CUDZYSLOWY))
    return wynik


def rozjazdy(katalog: Path, oczekiwana: str) -> list[str]:
    bledy = []
    for nazwa, tekst in workflowy(katalog).items():
        for w in wersje_w_workflow(tekst):
            if w != oczekiwana:
                bledy.append(f"{nazwa}: python-version {w!r}, expected {oczekiwana!r} "
                             f"(audyt_zaleznosci.PYTHON_PRZETESTOWANY)")
    return bledy


def granice_manifestu(plik: Path) -> dict[str, str]:
    """{pakiet (lower): specyfikator} z requirements.txt, także z zakomentowanych wpisów."""
    wynik = {}
    for linia in plik.read_text(encoding="utf-8").splitlines():
        tekst = linia.strip().lstrip("#").strip().split("#", 1)[0].strip()
        for znak in "<>=!~":
            if znak in tekst:
                nazwa, _, reszta = tekst.partition(znak)
                if nazwa.strip() and " " not in nazwa.strip():
                    wynik.setdefault(nazwa.strip().lower(), znak + reszta)
                break
    return wynik


_RE_WYMAGANIE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*([^;]*)")
_OPCJE_Z_ARGUMENTEM = {"-r", "--requirement", "-c", "--constraint", "-e", "--editable",
                       "-i", "--index-url", "--extra-index-url"}


def kanoniczna(nazwa: str) -> str:
    """Nazwa wg PEP 503: `lingua_language_detector` == `lingua-language-detector`."""
    return re.sub(r"[-_.]+", "-", nazwa).lower()


def instalacje_w_workflow(tekst: str) -> list[tuple[str, str]]:
    """[(nazwa kanoniczna, specyfikator)] dla KAŻDEGO pakietu z `pip install`
    (też `pip3`, `python -m pip`, kontynuacje linii, apostrofy, extras, markery).
    Lista, nie dict: dwa kroki w jednym pliku nie nadpisują się. Bliźniak
    Reżysera (`test_bramka_zaleznosci._instalacje_w_workflow`); tu bez
    `packaging`, bo CI go nie instaluje. Audyt 2026-11-13: poprzedni parser
    dzielił tylko po cudzysłowie `"` i porównywał tekst, więc apostrofy, pin
    i drugi krok w pliku przechodziły po cichu."""
    wynik = []
    for linia in tekst.replace(chr(92) + chr(10), " ").splitlines():
        if linia.strip().startswith("#"):
            continue
        try:
            tokeny = shlex.split(linia)
        except ValueError:
            continue
        for i, tok in enumerate(tokeny):
            if tok != "install" or i == 0 or tokeny[i - 1] not in ("pip", "pip3"):
                continue
            pomin = False
            for arg in tokeny[i + 1:]:
                if arg in ("&&", "||", ";", "|"):
                    break
                if pomin or arg.startswith("-"):
                    pomin = not pomin and arg in _OPCJE_Z_ARGUMENTEM
                    continue
                m = _RE_WYMAGANIE.match(arg)
                if m:
                    wynik.append((kanoniczna(m.group(1)), m.group(2).replace(" ", "")))
    return wynik


def _wersja(tekst: str) -> tuple[int, ...]:
    czesci = [int(c) for c in re.findall(r"\d+", tekst.split("+")[0])]
    while len(czesci) > 1 and czesci[-1] == 0:      # 4.0 == 4
        czesci.pop()
    return tuple(czesci)


def gorna_granica(spec: str):
    """(wersja, czy_włącznie) — najciaśniejsza górna granica albo None.
    Pin `==` i `~=` też ją wyznaczają."""
    granice = []
    for czlon in filter(None, spec.replace(" ", "").split(",")):
        m = re.match(r"(<=|<|===|==|~=|>=|>|!=)(.+)", czlon)
        if not m:
            continue
        op, v = m.groups()
        if op == "<":
            granice.append((_wersja(v), False))
        elif op == "<=" or (op in ("==", "===") and "*" not in v):
            granice.append((_wersja(v), True))
        elif op == "==":                                  # X.Y.* -> < X.(Y+1)
            cz = list(_wersja(v.rstrip(".*")) or (0,))
            cz[-1] += 1
            granice.append((tuple(cz), False))
        elif op == "~=":                                  # ~=X.Y -> < X+1
            cz = [int(c) for c in re.findall(r"\d+", v)][:-1]
            cz[-1] += 1
            granice.append((_wersja(".".join(map(str, cz))), False))
    return min(granice) if granice else None


def rozjazdy_granic(workflowy: dict[str, str], manifest: dict[str, str]) -> list[str]:
    """Rozjazd = pakiet z manifestu, którego górna granica w workflowie jest INNA
    (semantycznie: `<4.0` == `<4`) albo jej brak — każdy plik i krok osobno."""
    manifest = {kanoniczna(n): s for n, s in manifest.items()}
    bledy = []
    for plik, tekst in sorted(workflowy.items()):
        for nazwa, spec in instalacje_w_workflow(tekst):
            if nazwa in manifest and gorna_granica(spec) != gorna_granica(manifest[nazwa]):
                bledy.append(f"{plik}: {nazwa}{spec or ' (no bound)'}, requirements.txt has "
                             f"{nazwa}{manifest[nazwa]}")
    return bledy


def workflowy(katalog: Path) -> dict[str, str]:
    return {wf.name: wf.read_text(encoding="utf-8")
            for wf in sorted(katalog.glob("*.yml")) + sorted(katalog.glob("*.yaml"))}


class TestPythonCI(unittest.TestCase):
    def test_granice_pakietow_w_workflow_zgodne_z_manifestem(self):
        """Audyt 2026-11-13: po podbiciu fonttools release.yml dalej instalował
        <4.68, więc bramka wydania testowała starszą wersję niż manifest."""
        manifest = granice_manifestu(KORZEN / "requirements.txt")
        self.assertIn("fonttools", manifest)
        wf = workflowy(KORZEN / ".github" / "workflows")
        widziane = {n for t in wf.values() for n, _s in instalacje_w_workflow(t)}
        self.assertIn("fonttools", widziane)
        self.assertEqual(rozjazdy_granic(wf, manifest), [])

    def test_bramka_granic_lapie_rozjazd(self):
        """Porównanie z manifestem widziane na czerwono — każda forma z audytu."""
        q = chr(34)
        przypadki = [
            (f"python -m pip install --quiet {q}fonttools<4.69{q}", False),
            (f"pip install {q}fonttools<4.69.0{q}", False),
            ("pip install 'fonttools >= 4.60, < 4.69'", False),
            (f"pip install {q}fonttools~=4.68.0{q}", False),       # = <4.69
            ("pip install -r requirements.txt", False),
            (f"python -m pip install --quiet {q}fonttools<4.68{q}", True),
            ("pip install 'fonttools<4.68'", True),
            (f"pip install {q}fonttools==4.68.1{q}", True),
            (f"pip install {q}fonttools[woff]<4.68{q}", True),
            (f"pip3 install {q}fonttools<4.68{q}", True),
            (f"pip install {chr(92)}{chr(10)}  {q}fonttools<4.68{q}", True),
            ("pip install fonttools", True),
            (f"pip install {q}FontTools<4.68{q}", True),
        ]
        for instalacja, rozjazd in przypadki:
            with self.subTest(instalacja=instalacja):
                wynik = rozjazdy_granic({"x.yml": "run: " + instalacja}, {"fonttools": "<4.69"})
                self.assertIs(bool(wynik), rozjazd, wynik)

    def test_bramka_granic_dwa_kroki_w_pliku(self):
        q = chr(34)
        tekst = f"run: pip install {q}fonttools<4.69{q}{chr(10)}run: pip install {q}fonttools<4.68{q}"
        wynik = rozjazdy_granic({"x.yml": tekst}, {"fonttools": "<4.69"})
        self.assertEqual(len(wynik), 1, wynik)

    def test_nazwa_wg_pep503(self):
        q = chr(34)
        tekst = f"run: pip install {q}lingua_language_detector<2.2{q}"
        self.assertTrue(rozjazdy_granic({"x.yml": tekst}, {"lingua-language-detector": "<2.3"}))

    def test_workflowy_zgodne_z_przetestowanym(self):
        oczekiwana = python_przetestowany(KORZEN / "audyt_zaleznosci.py")
        self.assertRegex(oczekiwana, "^[0-9]+[.][0-9]+[.][0-9]+$",
                         "PYTHON_PRZETESTOWANY must be an exact X.Y.Z patch")
        self.assertEqual(rozjazdy(KORZEN / ".github" / "workflows", oczekiwana), [])

    def test_bramka_lapie_wersje_bez_patcha(self):
        q = chr(39)
        tekst = f"    with:{chr(10)}      python-version: {q}3.14{q}{chr(10)}"
        self.assertEqual(wersje_w_workflow(tekst), ["3.14"])
        self.assertNotEqual(wersje_w_workflow(tekst), ["3.14.3"])

    def test_bramka_czyta_komentarz_i_cudzyslowy(self):
        tekst = f"python-version: {chr(34)}3.14.3{chr(34)}  # pinned"
        self.assertEqual(wersje_w_workflow(tekst), ["3.14.3"])


if __name__ == "__main__":
    sys.exit(unittest.main(verbosity=1, exit=False).result.wasSuccessful() is False)
