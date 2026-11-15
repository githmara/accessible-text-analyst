"""odcinki_jezykowe.py – język tekstu na poziomie SŁÓW, ze słowników języków korpusu (ATA 2.0, bez Lingua).

Po co. Lingua klasyfikowała całe zdania i akapity. Zmierzone 2026-11-14 na 20 fińskich
transkryptach (6047 zdań): surowa dała 127 fałszywych zdań obcych, a heurystyki, które je
tłumiły, przepuszczały 2 zdania i żadnego z angielskich cytatów. Słowniki języków, które
użytkownik zadeklarował (`corpus_languages`), znajdują 38 odcinków angielskich i 8 polskich bez
przejęć — pod warunkiem reguły alfabetu (niżej).

Model:
- **język bazowy** = język, którego słownik zna najwięcej słów korpusu (`wybierz_baze`);
- **słowo** jest *wyłącznie L*, gdy zna je słownik obcego języka L, a nie zna słownik bazy;
  słowo znane kilku językom obcym idzie do NAJMNIEJSZEGO alfabetu, który mieści wszystkie
  jego litery (en ⊂ pl: „Against” → en, „Łódź” → pl). Bez tej reguły wektory pl, które znają
  angielskie formy, przejmowały angielskie cytaty;
- słowo, którego nie zna nikt, a jego litery nie mieszczą się w alfabecie bazy (polskie
  nazwisko w fińskim tekście), idzie do najmniejszego alfabetu z języków korpusu, który je
  mieści — głos bazy i tak nie umie przeczytać tych liter; nieznane słowo z liter bazy
  dziedziczy bazę (nazwy odmienione po fińsku zostają fińskie);
- pismo jest faktem: słowo cyrylickie w tekście łacińskim dostaje język cyrylicy
  (`detektor_pism`), także gdy żadnego języka cyrylickiego nie zadeklarowano;
- **odcinek obcy** = co najmniej 2 słowa wyłącznie L, albo 1 słowo spoza alfabetu bazy;
  odcinek nie przechodzi przez koniec zdania; MAKS_MOST słów znanych i bazie, i L (omorfi zna
  „and”, „Against”) może leżeć MIĘDZY słowami wyłącznie L, nie na brzegu odcinka;
- odcinek jest **blokiem**, gdy obejmuje całe zdania (od początku do końca zdania) — notatnik
  przetwarza blok modelem jego języka zamiast modelu bazy (zdania, NER, lematy); pozostałe
  odcinki to **wtrącenia** wewnątrz zdania bazy.

Moduł nie ładuje słowników sam: dostaje je w parametrze (`{kod: Slownik}` z
`slowniki_jezykow.slownik`), więc testy podają słowniki z listy form.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Optional

import detektor_pism

SLOWO = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*", re.UNICODE)
KONIEC_ZDANIA = re.compile(r"[.!?…]")
MIN_SLOW_ODCINKA = 2
MAKS_MOST = 1
PROBKA_BAZY = 20000  # słów na wybór bazy: wynik stabilny, a omorfi nie analizuje całej książki dwa razy


@dataclass(frozen=True)
class Odcinek:
    """Fragment tekstu w języku innym niż baza; `start`/`koniec` to indeksy znaków w tekście."""

    start: int
    koniec: int
    jezyk: str
    blok: bool = False


@dataclass(frozen=True)
class _Slowo:
    start: int
    koniec: int
    wylaczny: Optional[str]  # język obcy, do którego słowo należy; None = baza albo nieznane
    znaja: frozenset         # języki, których słownik zna formę (z bazą)
    obce_pismo: bool         # litery spoza alfabetu bazy — wystarcza jako odcinek jednowyrazowy


def _alfabet(slownik) -> frozenset:
    return slownik.alfabet


def wybierz_baze(teksty: list[str], slowniki: dict, probka: int = PROBKA_BAZY) -> tuple[str, dict[str, float]]:
    """(baza, {kod: udział znanych słów}) — baza = język o największym udziale; remis: kolejność `slowniki`."""
    slowa = []
    for t in teksty:
        for m in SLOWO.finditer(t):
            if len(m.group()) >= 2:
                slowa.append(m.group())
                if len(slowa) >= probka:
                    break
        if len(slowa) >= probka:
            break
    if not slowa:
        kod = next(iter(slowniki))
        return kod, {k: 0.0 for k in slowniki}
    udzialy = {k: sum(bool(s.ocen(w)) for w in slowa) / len(slowa) for k, s in slowniki.items()}
    kolejnosc = list(slowniki)
    baza = max(kolejnosc, key=lambda k: (udzialy[k], -kolejnosc.index(k)))
    return baza, udzialy


def najmniejszy_alfabet(litery: set, kandydaci: list[str], slowniki: dict) -> Optional[str]:
    mieszcza = [k for k in kandydaci if litery <= _alfabet(slowniki[k])]
    if not mieszcza:
        return None
    return min(mieszcza, key=lambda k: (len(_alfabet(slowniki[k])), kandydaci.index(k)))


def _klasyfikuj(slowo: str, baza: str, slowniki: dict, alfabety: dict[str, str]) -> tuple[Optional[str], frozenset, bool]:
    litery = set(slowo)
    pismo = detektor_pism.dominujace_pismo(slowo)
    pismo_bazy = detektor_pism.dominujace_pismo(alfabety[baza]) if baza in alfabety else None
    if pismo == detektor_pism.CYRYLICA and pismo_bazy != detektor_pism.CYRYLICA:
        return detektor_pism.jezyk_cyrylicy(slowo, alfabety), frozenset(), True
    obce = [k for k in slowniki if k != baza]
    znaja = frozenset(k for k, s in slowniki.items() if s.ocen(slowo))
    obce_pismo = not litery <= _alfabet(slowniki[baza])
    if baza in znaja:
        return None, znaja, obce_pismo
    znajace_obce = [k for k in obce if k in znaja]
    if len(znajace_obce) == 1:
        return znajace_obce[0], znaja, obce_pismo
    if znajace_obce:
        return najmniejszy_alfabet(litery, znajace_obce, slowniki) or znajace_obce[0], znaja, obce_pismo
    if obce_pismo and len(slowo) >= 2:
        return najmniejszy_alfabet(litery, obce, slowniki), znaja, obce_pismo
    return None, znaja, obce_pismo


def _slowa(tekst: str, baza: str, slowniki: dict, alfabety: dict[str, str]) -> list[_Slowo]:
    wynik = []
    cache: dict[str, tuple] = {}
    for m in SLOWO.finditer(tekst):
        w = m.group()
        if w not in cache:
            cache[w] = _klasyfikuj(w, baza, slowniki, alfabety)
        wyl, znaja, obce = cache[w]
        wynik.append(_Slowo(m.start(), m.end(), wyl, znaja, obce))
    return wynik


def _bez_liter(fragment: str) -> bool:
    return not any(z.isalpha() for z in fragment)


def _blok(tekst: str, start: int, koniec: int,
          konce: Optional[list[int]] = None) -> tuple[bool, int]:
    """(czy odcinek obejmuje całe zdania, koniec poszerzony o znak końca zdania).

    `konce` — pozycje znaków `KONIEC_ZDANIA` w `tekst`, policzone RAZ przez
    `odcinki` (audyt 2.0: skan `tekst[:start]` i kopia `tekst[koniec:]` przy
    każdym odcinku dawały czas kwadratowy — 29 s na 1,7 mln znaków).
    """
    import bisect
    if konce is None:
        konce = [m.start() for m in KONIEC_ZDANIA.finditer(tekst)]
    j = bisect.bisect_left(konce, start)            # konce[j-1] < start
    if not _bez_liter(tekst[konce[j - 1] + 1 if j else 0:start]):
        return False, koniec
    j = bisect.bisect_left(konce, koniec)           # pierwszy koniec zdania od `koniec`
    nast = konce[j] if j < len(konce) else None
    if not _bez_liter(tekst[koniec:nast if nast is not None else len(tekst)]):
        return False, koniec
    if nast is None:
        return True, koniec
    k = nast + 1
    while k < len(tekst) and KONIEC_ZDANIA.match(tekst[k]):
        k += 1
    return True, k


def odcinki(tekst: str, baza: str, slowniki: dict, alfabety: dict[str, str]) -> list[Odcinek]:
    """Obce odcinki tekstu w kolejności; reszta tekstu jest w języku `baza`.

    `slowniki`: {kod: Slownik} języków korpusu (z bazą); `alfabety`: {kod: alfabet} WSZYSTKICH
    paczek (pismo cyrylickie rozstrzyga się także poza językami korpusu).
    """
    slowa = _slowa(tekst, baza, slowniki, alfabety)
    konce = [m.start() for m in KONIEC_ZDANIA.finditer(tekst)]
    wynik: list[Odcinek] = []
    i, n = 0, len(slowa)
    while i < n:
        jezyk = slowa[i].wylaczny
        if jezyk is None:
            i += 1
            continue
        ostatni, wylacznych, most = i, 1, 0
        k = i + 1
        while k < n and not KONIEC_ZDANIA.search(tekst[slowa[k - 1].koniec:slowa[k].start]):
            s = slowa[k]
            if s.wylaczny == jezyk:
                ostatni, wylacznych, most = k, wylacznych + 1, 0
            elif s.koniec - s.start < 2:
                pass  # słowo jednoliterowe („a”, „I”, „e”) nie ma głosu słownika i nie rozcina cytatu
            elif s.wylaczny is None and jezyk in s.znaja and most < MAKS_MOST:
                most += 1
            else:
                break
            k += 1
        if wylacznych >= MIN_SLOW_ODCINKA or any(s.obce_pismo for s in slowa[i:ostatni + 1]):
            start, koniec = slowa[i].start, slowa[ostatni].koniec
            blok, koniec_bloku = _blok(tekst, start, koniec, konce)
            wynik.append(Odcinek(start, koniec_bloku if blok else koniec, jezyk, blok))
        i = ostatni + 1
    return _scal_bloki(tekst, wynik)


def _scal_bloki(tekst: str, odc: list[Odcinek]) -> list[Odcinek]:
    """Sąsiednie bloki jednego języka (kolejne zdania cytatu) → jeden blok."""
    wynik: list[Odcinek] = []
    for o in odc:
        p = wynik[-1] if wynik else None
        if p and p.blok and o.blok and p.jezyk == o.jezyk and _bez_liter(tekst[p.koniec:o.start]):
            wynik[-1] = Odcinek(p.start, o.koniec, o.jezyk, True)
        else:
            wynik.append(o)
    return wynik


def segmenty(tekst: str, baza: str, odc: list[Odcinek]) -> list[tuple[int, int, str]]:
    """Tekst pocięty na segmenty do przetworzenia modelem: bloki osobno, reszta w bazie.

    Segmenty pokrywają cały tekst bez przerw; wtrącenia zostają wewnątrz segmentów bazy
    (składnia zdania jest bazowa). Pusty tekst → [].
    """
    wynik: list[tuple[int, int, str]] = []
    kursor = 0
    for o in odc:
        if not o.blok:
            continue
        if o.start > kursor:
            wynik.append((kursor, o.start, baza))
        wynik.append((o.start, o.koniec, o.jezyk))
        kursor = o.koniec
    if kursor < len(tekst):
        wynik.append((kursor, len(tekst), baza))
    return wynik


def statystyka(odc: list[Odcinek]) -> dict[str, dict[str, int]]:
    """{jezyk: {"bloki": n, "wtracenia": n}} — do wydruku w notatniku."""
    licz: dict[str, Counter] = {}
    for o in odc:
        licz.setdefault(o.jezyk, Counter())["bloki" if o.blok else "wtracenia"] += 1
    return {k: {"bloki": v["bloki"], "wtracenia": v["wtracenia"]} for k, v in licz.items()}
