"""
detektor_pism.py — pismo tekstu i język cyrylicy z alfabetów paczek (Reżyser Audio GPT ⟷ ATA).

BLIŹNIAK BAJT W BAJT: ten sam plik leży w accessible_text_analyst i jest
edytowany WYŁĄCZNIE parami (klasa bliźniaków „detektor_pism”). Dlatego moduł:
  * importuje tylko bibliotekę standardową, nic z żadnego projektu;
  * nie czyta plików, nie drukuje, nie tłumaczy komunikatów;
  * alfabety paczek dostaje w PARAMETRZE (``{kod: alfabet}``).

Po co (decyzja maintainera 2026-11-09). Pismo litery jest FAKTEM, nie
zgadywaniem: detektor statystyczny potrzebuje ok. 20 znaków, a pismo widać po
jednej literze. Zmierzone tego dnia: krótki akapit rosyjski („Мы ждём вас
завтра.”) spadał pod próg detekcji i dostawał język dokumentu (``pl``), więc
Espeak czytał go polskim głosem, literując „cyrillic” przy każdej literze.

  * :func:`pismo_znaku` / :func:`dominujace_pismo` — pismo z nazwy Unicode
    (``LATIN``, ``CYRILLIC``, ``GREEK``…); znak mikro ``µ`` i znak omu ``Ω``
    liczą się jako greka, bo tak są czytane;
  * :func:`jezyk_cyrylicy` — który z WDROŻONYCH języków cyrylickich: ten, którego
    alfabet zawiera wszystkie cyrylickie litery tekstu; remis albo brak
    kandydata → ``domyslny`` (``ru``). Dziś paczka cyrylicka jest jedna, więc
    wynik jest jednoznaczny; litera, której ma tylko jeden alfabet (ukr. ``ї``),
    rozstrzygnie, gdy dojdzie druga paczka;
  * :func:`odcinki_pism` — tekst pocięty na odcinki jednego pisma (znaki
    neutralne między literami tego samego pisma należą do odcinka) — po to, by
    Naprawiacz Tagów dał obcemu pismu w akapicie własny ``lang``;
  * ``KOD_GREKI = "el"`` — greka bez paczki jest jednoznaczna: Naprawiacz nie
    zmienia treści, więc ``λόγος`` w polskim akapicie dostaje ``lang="el"``.
"""

from __future__ import annotations

import unicodedata
from collections import Counter

CYRYLICA = "CYRILLIC"
GREKA = "GREEK"
LACINKA = "LATIN"

#: Kod języka greckiego odcinka (BCP-47). Stały, bo pismo ma jeden język
#: (decyzja maintainera 2026-11-09).
KOD_GREKI = "el"

#: Znaki spoza bloków greki, czytane jako litery greckie.
_GREKA_SPOZA_BLOKU = {chr(0x00B5), chr(0x2126)}


def pismo_znaku(znak: str) -> str | None:
    """Pismo LITERY (pierwsze słowo nazwy Unicode); ``None`` dla nie-litery."""
    if znak in _GREKA_SPOZA_BLOKU:
        return GREKA
    if not znak.isalpha():
        return None
    # Litera modyfikująca (Lm) nie ma pisma: apostrof ukraiński U+02BC
    # („мʼясо"), grecki znak elizji, akcent IPA — nazwa Unicode zaczyna się od
    # MODIFIER, więc bez tego rozcinała słowo na dwa odcinki (audyt N1).
    if unicodedata.category(znak) == "Lm":
        return None
    try:
        return unicodedata.name(znak).split(" ", 1)[0]
    except ValueError:
        return None


def dominujace_pismo(tekst: str) -> str | None:
    """Pismo większości liter; remis rozstrzyga pierwsza litera; ``None`` bez liter."""
    licznik: Counter[str] = Counter()
    pierwsze: dict[str, int] = {}
    for i, znak in enumerate(tekst):
        pismo = pismo_znaku(znak)
        if pismo:
            licznik[pismo] += 1
            pierwsze.setdefault(pismo, i)
    if not licznik:
        return None
    return max(licznik, key=lambda p: (licznik[p], -pierwsze[p]))


def jezyki_cyrylickie(alfabety: dict[str, str]) -> list[str]:
    """Kody paczek, których alfabet jest pisany cyrylicą (posortowane)."""
    return sorted(kod for kod, alfabet in alfabety.items()
                  if dominujace_pismo(alfabet) == CYRYLICA)


def jezyk_cyrylicy(tekst: str, alfabety: dict[str, str],
                   domyslny: str = "ru") -> str:
    """Język cyrylickiego tekstu spośród paczek z ``alfabety``.

    Kandydatem jest paczka cyrylicka, której alfabet (obie wielkości) zawiera
    KAŻDĄ cyrylicką literę tekstu. Jeden kandydat → on. Kilku (tekst z liter
    wspólnych) albo żaden (litera spoza wszystkich alfabetów) → ``domyslny``,
    gdy jest wśród rozważanych; inaczej kandydat o największym pokryciu,
    a przy remisie pierwszy alfabetycznie. Bez paczek cyrylickich →
    ``domyslny``.
    """
    paczki = jezyki_cyrylickie(alfabety)
    if not paczki:
        return domyslny
    litery = {z.lower() for z in tekst if pismo_znaku(z) == CYRYLICA}
    zestawy = {kod: {z.lower() for z in alfabety[kod]} for kod in paczki}
    pelne = [kod for kod in paczki if litery <= zestawy[kod]]
    if len(pelne) == 1:
        return pelne[0]
    rozwazane = pelne or paczki
    if domyslny in rozwazane:
        return domyslny
    return max(rozwazane, key=lambda kod: (len(litery & zestawy[kod]),
                                           -paczki.index(kod)))


def odcinki_pism(tekst: str) -> list[tuple[int, int, str]]:
    """Odcinki ``(start, koniec, pismo)`` liter jednego pisma, w kolejności tekstu.

    Znaki neutralne (spacja, cyfra, interpunkcja, znak łączący) między dwiema
    literami TEGO SAMEGO pisma należą do odcinka („привет, мир” to jeden
    odcinek); między różnymi pismami — do żadnego. Odcinek zaczyna się
    pierwszą i kończy ostatnią literą, więc spacja wokół niego zostaje poza.
    Znak łączący tuż po ostatniej literze (akcent U+0301) należy do odcinka.
    """
    odcinki: list[tuple[int, int, str]] = []
    start = koniec = -1
    biezace: str | None = None
    for i, znak in enumerate(tekst):
        pismo = pismo_znaku(znak)
        if pismo is None:
            if biezace is not None and koniec == i and unicodedata.combining(znak):
                koniec = i + 1
            continue
        if pismo == biezace:
            koniec = i + 1
            continue
        if biezace is not None:
            odcinki.append((start, koniec, biezace))
        biezace, start, koniec = pismo, i, i + 1
    if biezace is not None:
        odcinki.append((start, koniec, biezace))
    return odcinki
