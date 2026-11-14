"""ciecie_stron.py – podział bardzo wysokiej strony na pasy z zakładką.

Czysta geometria, bez zależności: jednostką może być piksel obrazu (OCR Windows
w ATA, limit `OcrEngine.MaxImageDimension` = 10000 px) albo punkt PDF (cropbox
strony wysyłanej do modelu z obrazem). Pisany jako przyszły bliźniak dla
`core_skany` Reżysera (decyzja maintainera 2026-11-13, D4: cięcie wysokich stron
robimy raz).

Dlaczego zakładka i „strefy własne”, zmierzone 2026-11-13 na stronie 5172×10441 pt
(odręczne notatki z OneNote wydrukowane przez Chrome do jednej strony): cięcie bez
zakładki przecina wiersz na pół i żaden pas go nie odczyta, a z zakładką ten sam
wiersz trafia do dwóch pasów i w wyniku się dubluje. Zakładka musi więc iść w parze
z regułą, KTÓRY pas jest właścicielem danego miejsca. Właścicielem jest pas, w którego
strefie własnej leży ŚRODEK elementu (słowa, wiersza); granica stref to połowa
zakładki. Element niższy niż połowa zakładki, którego środek leży w strefie
własnej pasa, mieści się w tym pasie w całości, więc nie jest ucięty.
"""

from __future__ import annotations

from typing import NamedTuple


class Pas(NamedTuple):
    """Pas strony: [poczatek, koniec) do wycięcia, [wlasny_od, wlasny_do) do rozstrzygania duplikatów."""

    poczatek: float
    koniec: float
    wlasny_od: float
    wlasny_do: float


def pasy(dlugosc: float, maks: float, zakladka: float) -> list[Pas]:
    """Dzieli odcinek [0, dlugosc) na pasy nie dłuższe niż `maks`, sąsiednie nachodzą o `zakladka`.

    Odcinek mieszczący się w limicie to jeden pas, bez cięcia. Strefy własne
    pokrywają cały odcinek bez przerw i bez nakładania się.
    """
    if dlugosc <= 0:
        raise ValueError("dlugosc musi być dodatnia")
    if not 0 <= zakladka < maks:
        raise ValueError("zakladka musi być nieujemna i mniejsza od maks")
    if dlugosc <= maks:
        return [Pas(0.0, float(dlugosc), 0.0, float(dlugosc))]
    krok = maks - zakladka
    liczba = 1
    while krok * (liczba - 1) + maks < dlugosc:
        liczba += 1
    # Równe pasy zamiast pełnych i jednego karłowatego na końcu: każdy pas ma ten
    # sam kontekst, a zakładka zostaje dokładnie taka, jak zamówiono.
    dl_pasa = (dlugosc + zakladka * (liczba - 1)) / liczba
    wynik = []
    for i in range(liczba):
        poczatek = i * (dl_pasa - zakladka)
        koniec = dlugosc if i == liczba - 1 else poczatek + dl_pasa
        wlasny_od = 0.0 if i == 0 else poczatek + zakladka / 2
        wlasny_do = float(dlugosc) if i == liczba - 1 else koniec - zakladka / 2
        wynik.append(Pas(poczatek, koniec, wlasny_od, wlasny_do))
    return wynik


def wlasciciel(pasy_strony: list[Pas], srodek: float) -> int:
    """Indeks pasa, do którego strefy własnej należy punkt `srodek` (współrzędna strony)."""
    for i, p in enumerate(pasy_strony):
        if p.wlasny_od <= srodek < p.wlasny_do:
            return i
    return len(pasy_strony) - 1 if srodek >= pasy_strony[-1].wlasny_do else 0
