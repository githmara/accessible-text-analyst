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
    for wf in sorted(katalog.glob("*.yml")):
        for w in wersje_w_workflow(wf.read_text(encoding="utf-8")):
            if w != oczekiwana:
                bledy.append(f"{wf.name}: python-version {w!r}, expected {oczekiwana!r} "
                             f"(audyt_zaleznosci.PYTHON_PRZETESTOWANY)")
    return bledy


class TestPythonCI(unittest.TestCase):
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
