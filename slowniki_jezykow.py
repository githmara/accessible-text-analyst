"""slowniki_jezykow.py – słownik form dla każdego języka z podstaw (bez Lingua, bez spaCy-pipeline'u).

Wspólne źródło dla trzech konsumentów: głosowania OCR (`glosowanie_ocr`), tagowania odcinków
językowych w notatniku (`odcinki_jezykowe`) i tagowania obcych słów w raporcie
(`generate_report`). Wydzielone z `glosowanie_ocr` w ATA 2.0, żeby raport i notatnik nie
importowały silników OCR (pywinrt).

Słownik języka (forma jest „słownikowa”, gdy jej litery należą do alfabetu z
`podstawy.yaml` I leksykon ją zna — sam leksykon nie wystarcza, bo zna formy obce):
- wektory spaCy w trybie `default` = skończona lista form (pl, en, ru, it: 500–685 tys.,
  ~1,7 s i ~55 MB RAM na język, zmierzone; de, es, fr: po 500 tys., 1,3–4,5 s,
  zmierzone 2026-11-15);
- wektory `floret` (fi) znają KAŻDY napis — „intencjQ” przechodził jako fiński —
  więc słownikiem fińskim jest omorfi;
- brak modelu spaCy (is) — słownikiem jest BÍN z pakietu `islenska` (99,2% słów
  z literami islandzkimi; licencja danych CC BY-SA 4.0 wymaga uznania autorstwa
  w interfejsie — `UZNANIE_BIN`).
Gałęzie `kod == "fi"` / `kod == "is"` to logika dla jednego języka (jak w
`cell_model`), nie wyliczanie języków.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable, Optional

from shamanic_locale import PODSTAWY

KATALOG = Path(__file__).resolve().parent
AUTOMATY_OMORFI = ("omorfi_recased.describe.hfst", "omorfi.describe.hfst")
UZNANIE_BIN = ("The Database of Icelandic Morphology. The Árni Magnússon Institute for "
               "Icelandic Studies. Author and editor Kristín Bjarnadóttir. https://bin.arnastofnun.is")
_LITERY = re.compile(r"[^\W\d_]+", re.UNICODE)



def _rdzen(tekst: str) -> str:
    """Jedyny ciąg liter słowa („kuuluu?” → „kuuluu”); pusty, gdy liter brak albo jest ich kilka ciągów."""
    m = _LITERY.findall(tekst)
    return m[0] if len(m) == 1 else ""


@dataclass
class Slownik:
    kod: str
    alfabet: frozenset
    zna_forme: Callable[[str], bool]
    zrodlo: str
    uznanie: str = ""  # uznanie autorstwa wymagane licencją danych; notatnik drukuje je przy użyciu
    # Ranga częstości formy (0 = najczęstsza) albo None. Tylko wektory spaCy: ich
    # wiersze są posortowane po częstości (zmierzone 2026-11-15, pl: „się” 7,
    # „sią” 103 213). Rekonstrukcja znaku zastępczego ■ (naprawa_zrodel) rozstrzyga
    # nią formy, które leksykon zna obie, bo zna też śmieci („bezpieczećstwa”).
    ranga: Optional[Callable[[str], Optional[int]]] = None

    def ranga_formy(self, slowo: str, dokladna: bool = False) -> Optional[int]:
        """Ranga formy: lepsza z dokładnej i pisanej małymi literami (wersalikowe
        „WSTĘP” jest rzadkie, „wstęp” — nie); `dokladna` = tylko ta pisownia.
        None = brak rangi lub formy."""
        if self.ranga is None:
            return None
        rangi = [r for f in ({slowo} if dokladna else {slowo, slowo.lower()})
                 if (r := self.ranga(f)) is not None]
        return min(rangi) if rangi else None

    def ocen(self, slowo: str) -> Optional[bool]:
        """True = forma słownikowa; False = nie; None = brak głosu (mniej niż 2 litery, liczba, znak)."""
        r = _rdzen(slowo)
        if len(r) < 2:
            return None
        if not set(r) <= self.alfabet:
            return False
        return self.zna_forme(r) or (r.lower() != r and self.zna_forme(r.lower()))


def _alfabet(kod: str) -> frozenset:
    a = PODSTAWY[kod]["alfabet"]
    return frozenset(a) | frozenset(a.lower())


def _slownik_spacy(kod: str, model: str) -> Slownik:
    import gc

    import spacy

    nlp = spacy.load(model, exclude=["tok2vec", "tagger", "parser", "ner", "lemmatizer", "attribute_ruler",
                                     "morphologizer", "senter", "trainable_lemmatizer"])
    wek = nlp.vocab.vectors
    if wek.mode != "default":
        raise LookupError(f"{model} vectors are in mode {wek.mode}, not a finite word list")
    s = nlp.vocab.strings
    # Forma → wiersz wektora (= ranga częstości, patrz `Slownik.ranga`).
    formy = {s[k]: r for k, r in wek.key2row.items() if k in s}
    del nlp, wek, s
    gc.collect()
    return Slownik(kod, _alfabet(kod), formy.__contains__, f"spaCy {model} ({len(formy)} forms)",
                   ranga=formy.get)


def _slownik_omorfi(kod: str) -> Slownik:
    from omorfi.omorfi import Omorfi
    from omorfi.token import Token

    sciezka = next((p for n in AUTOMATY_OMORFI for p in (Path.cwd() / n, KATALOG / n) if p.exists()), None)
    if sciezka is None:
        raise LookupError("omorfi automata (*.hfst) missing: run omorfi-download in the repository folder")
    om = Omorfi()
    om.load_analyser(str(sciezka))

    @lru_cache(maxsize=65536)
    def zna(forma: str) -> bool:
        tok = Token.fromsurf(forma)
        om.analyse(tok)
        mala = forma.islower()
        for a in tok.analyses:
            lemat = "".join(a.get_lemmas() or [])
            # Te same dwa artefakty, co w cell_model._om_plausible: zgadywanie (waga inf)
            # i wielka litera w lemacie małej formy, wymyślona przez automat recased.
            if a.weight != float("inf") and lemat and not (mala and lemat != lemat.lower()):
                return True
        return False

    return Slownik(kod, _alfabet(kod), zna, f"omorfi ({sciezka.name})")


def _slownik_bin(kod: str) -> Slownik:
    from islenska import Bin

    b = Bin(add_compounds=True)
    return Slownik(kod, _alfabet(kod), lambda forma: bool(b.lookup(forma)[1]), "BÍN (islenska)", UZNANIE_BIN)


@lru_cache(maxsize=None)
def slownik(kod: str) -> Slownik:
    """Słownik języka; `LookupError` z instrukcją, gdy brakuje składnika."""
    model = PODSTAWY[kod]["spacy"]
    try:
        if kod == "fi":
            return _slownik_omorfi(kod)
        if kod == "is":
            return _slownik_bin(kod)
        if model:
            return _slownik_spacy(kod, model)
    except ImportError as e:
        raise LookupError(f"package {e.name} missing: uncomment it in requirements.txt and install") from e
    except OSError as e:  # spacy.load: model niezainstalowany
        raise LookupError(f"spaCy model {model} missing: python -m spacy download {model}") from e
    raise LookupError("no lexicon source for this language (neither spaCy vectors nor a lexicon)")


def slownik_pelny(kod: str) -> Slownik:
    """Słownik, który zna KAŻDĄ formę z liter alfabetu języka — dla korpusu jednego języka.

    Gdy użytkownik zadeklarował jeden język tekstu, baza jest znana i leksykonu nie trzeba
    ładować; tagowanie odcinków znajdzie wtedy tylko słowa innego pisma.
    """
    return Slownik(kod, _alfabet(kod), lambda forma: True, "-")
