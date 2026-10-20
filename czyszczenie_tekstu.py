"""
czyszczenie_tekstu.py — wspólne czyszczenie tekstu źródłowego (Reżyser Audio GPT ⟷ ATA).

BLIŹNIAK BAJT W BAJT: ten sam plik leży w accessible_text_analyst i jest
edytowany WYŁĄCZNIE parami (zmiana tu = ta sama zmiana tam, w tym samym cyklu;
klasa bliźniaków „czyszczenie_tekstu”). Dlatego moduł:
  * importuje tylko bibliotekę standardową, nic z żadnego projektu;
  * nie czyta plików, nie drukuje, nie tłumaczy komunikatów — każda funkcja
    zwraca (wynik, liczniki), a co z nimi zrobić, decyduje wołający;
  * litery paczek językowych (alfabety) dostaje w PARAMETRZE.
Wektory testowe: `czyszczenie_tekstu_wektory.json` (UTF-8, LF) i runner
`czyszczenie_tekstu_wektory.py` (unittest) — oba też bajt w bajt.

Zawartość, w kolejności stosowania w `oczysc_akapity_docx`:
  1. spacja z fontu Symbol U+F020 → zwykła spacja;
  2. mojibake: litery z jednobajtowej strony kodowej odczytane jako
     Latin-1/cp1252 („Áèáëèîòåêà” → „Библиотека”);
  3. tekst rozstrzelony („С о ц и а л ь н о е”) → słowo, gdy dokument je zna;
  4. przeniesienia wyrazów w akapicie („по- священного”) — reguły 1–4.
Geometria PDF-a (gdzie w rozstrzeleniu kończy się słowo) zostaje w loaderach
obu projektów; tu jest tylko DECYZJA, na tokenach ze znacznikami granic.

Rozstrzyga wyłącznie tekst tego samego dokumentu i podane alfabety — bez list
języków, spójników ani pism w kodzie. Liczba akapitów nigdy się nie zmienia.
"""

from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------------------
# 1. Spacja z fontu Symbol
# ---------------------------------------------------------------------------

#: Spacja z fontu Symbol (prywatny obszar Unicode), którą Word wstawia przy
#: wypunktowaniach konwersji PDF→Word: 253× w słowniku koronawirusowym.
SPACJA_SYMBOL = chr(0xF020)


def zamien_spacje_symbol(akapity: list[str]) -> tuple[list[str], int]:
    """U+F020 → spacja; (akapity, liczba zamienionych znaków)."""
    ile = sum(a.count(SPACJA_SYMBOL) for a in akapity)
    return [a.replace(SPACJA_SYMBOL, " ") for a in akapity], ile


# ---------------------------------------------------------------------------
# Słownik dokumentu
# ---------------------------------------------------------------------------

# Słowo dokumentu: litery z łącznikami w środku („ковид-диссидентов”).
_RE_SLOWO = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*")
#: Apostrofy, którymi konwersja PDF→Word zapisuje akcent („КОВИ'ДНЫЙ”).
APOSTROFY = "'" + chr(0x2019) + chr(0x02BC)
_RE_APOSTROF_W_SLOWIE = re.compile(r"(?<=[^\W\d_])[" + APOSTROFY + r"](?=[^\W\d_])")


def bez_laczacych(tekst: str) -> str:
    """Tekst bez znaków łączących (akcent U+0301 i podobne)."""
    return "".join(z for z in tekst if not unicodedata.combining(z))


def klucz_slowa(tekst: str) -> str:
    """Postać porównawcza słowa: casefold, bez znaków łączących i apostrofów."""
    return bez_laczacych(tekst).casefold().translate({ord(a): None for a in APOSTROFY})


def slownik_dokumentu(akapity: list[str], *, scal_apostrofy: bool = False) -> dict[str, int]:
    """Słowa dokumentu (casefold) z liczbą wystąpień.

    `scal_apostrofy`: apostrof-akcent w środku słowa nie dzieli go
    („КОВИ'ДНЫЙ” liczy się jako „ковидный”, a nie jako urywki „кови”
    i „дный”, które zatwierdzały sklejenie rozstrzelonego „К о в и”).
    """
    slowa: dict[str, int] = {}
    for akapit in akapity:
        if scal_apostrofy:
            akapit = _RE_APOSTROF_W_SLOWIE.sub("", bez_laczacych(akapit))
        for m in _RE_SLOWO.finditer(akapit):
            k = m.group(0).casefold()
            slowa[k] = slowa.get(k, 0) + 1
    return slowa


# ---------------------------------------------------------------------------
# 4. Przeniesienia wyrazów w akapicie
# ---------------------------------------------------------------------------

# Interpunkcja dopuszczalna NA BRZEGU fragmentu (zdanie, cytat, nawias);
# wszystko inne przy słowie — kropka w środku, „/”, „@”, „:”, „_”, cyfra —
# robi z niego adres albo identyfikator i wyklucza kandydata.
OTWIERAJACE = "«„“\"'([{"
ZAMYKAJACE = ".,;:!?…»”\"')]}"


def _pismo(z: str) -> str:
    return unicodedata.name(z, "?").split(" ")[0]


#: Samogłoski, na które kończy się pierwszy człon złożenia z łącznikiem
#: („поисково-”, „научно-”) — dane pisma, nie lista języków.
_SAMOGLOSKI_ZLOZEN = frozenset("aeiouyаеёиоуыэюяіїє")
#: Najkrótszy pierwszy człon złożenia: przedrostek („по-”, „при-”, „пере-”)
#: to przeniesienie, a w krótkim dokumencie najdłuższe słowo bywa krótsze
#: od „посвященного” — bez tego bariera łapała zwykłe „по- священного”.
MIN_CZLON_ZLOZENIA = 5


def _rdzen_lewy(fragment: str) -> str | None:
    """Słowo przed „-” (z łącznikami w środku); `None` = kandydat wykluczony."""
    m = re.search(r"[^\W\d_]+(?:-[^\W\d_]+)*$", fragment)
    if m is None:
        return None
    return None if fragment[:m.start()].lstrip(OTWIERAJACE) else m.group(0)


def _rdzen_prawy(fragment: str) -> str | None:
    m = re.match(r"[^\W\d_]+", fragment)
    if m is None:
        return None
    return None if fragment[m.end():].rstrip(ZAMYKAJACE) else m.group(0)


def napraw_przeniesienia(akapity: list[str]) -> tuple[list[str], dict[str, int]]:
    """Zdejmuje przeniesienia wyrazów W ŚRODKU akapitu.

    Kandydat: słowo L kończące się literą, „-”, co najmniej jedna spacja, słowo
    R od małej litery, oba w tym samym piśmie. Wykluczone: cyfra, „.”, „/”,
    „@”, „:”, „_” przy którymkolwiek słowie (poza interpunkcją na brzegu:
    „священного,”), wielka litera na początku R. Rozstrzyga słownik CAŁEGO
    dokumentu (casefold) bez własnego wystąpienia R kandydata:
      1. „L+R” jest słowem dokumentu → sklejamy bez dywizu;
      2. inaczej „L-R” jest słowem → sklejamy z łącznikiem („ковид-диссидентов”);
      3. inaczej R NIE jest słowem → sklejamy bez dywizu („по- священного”),
         ALE tylko w dokumencie, w którym reguła 1 zadziałała choć raz:
         w notatkach pisanych ręcznie „- ” bywa myślnikiem („Плохой- хуже
         всех”), a reguła 1 nigdy tam nie trafia (zmierzone na 380 plikach
         `.docx`: ok. 15 zniszczonych, wszystkie z zerem trafień reguły 1);
         Złożenie z łącznikiem nie jest przeniesieniem: gdy L kończy się
         samogłoską (łącznik złożenia „-о-”, „-е-”), ma co najmniej
         `MIN_CZLON_ZLOZENIA` liter, a L+R jest dłuższe od
         najdłuższego słowa dokumentu w tym samym piśmie (bez łączników),
         reguła 3 nie działa — „поисково- информационную” (22 litery przy
         najdłuższym 18) traciło łącznik; na 380 plikach `.docx` to jedyny
         z 1540 kandydatów reguły 3, którego bariera dotyka (etap 6);
      4. inaczej bez zmian („бело- голубых” przy słowie „голубых”; wiszące
         „двух- и …”, bo „и” jest słowem).
    Przeniesienia PRZEZ granicę akapitu zostają (liczba akapitów stała).

    Returns:
        (akapity, liczniki) — `"1"`–`"4"`, `"wykluczone"` i `"3_bez_reguly_1"`
        (kandydaci reguły 3 zatrzymani bramką; zostali bez zmian).
    """
    slowa = slownik_dokumentu(akapity)
    najdluzsze: dict[str, int] = {}
    for slowo in slowa:
        if slowo and "-" not in slowo:
            pismo = _pismo(slowo[0])
            najdluzsze[pismo] = max(najdluzsze.get(pismo, 0), len(slowo))
    liczniki = {"1": 0, "2": 0, "3": 0, "4": 0, "wykluczone": 0, "3_bez_reguly_1": 0}
    # Przebieg 1: decyzje dla wszystkich kandydatów (bramka reguły 3 zależy
    # od całego dokumentu). Przebieg 2: zastosowanie.
    decyzje: list[list[tuple[int, str, str]]] = []
    for akapit in akapity:
        decyzje.append(_decyzje_akapitu(akapit, slowa, liczniki, najdluzsze)
                       if "- " in akapit else [])
    regula_1 = any(regula == "1" for lista in decyzje for _, regula, _ in lista)
    wynik: list[str] = []
    for akapit, lista in zip(akapity, decyzje):
        if not lista:
            wynik.append(akapit)
            continue
        czesci = re.split(r"(\s+)", akapit)
        for poz, regula, nowy in reversed(lista):
            if regula == "3" and not regula_1:
                liczniki["3_bez_reguly_1"] += 1
                continue
            liczniki[regula] += 1
            czesci[poz:poz + 3] = [nowy]
        wynik.append("".join(czesci))
    return wynik, liczniki


def _decyzje_akapitu(akapit: str, slowa: dict[str, int], liczniki: dict[str, int],
                     najdluzsze: dict[str, int] | None = None) -> list[tuple[int, str, str]]:
    """(pozycja w podziale na białe znaki, reguła, nowy fragment) — bez zmian w tekście.

    Liczy od razu `"4"` i `"wykluczone"`; reguły 1–3 liczy dopiero przebieg 2.
    Kandydaci nie zachodzą na siebie: po trafieniu skaczemy za prawy fragment.
    """
    czesci = re.split(r"(\s+)", akapit)
    lista: list[tuple[int, str, str]] = []
    i = 0
    while i + 2 < len(czesci):
        lewy_f, odstep, prawy_f = czesci[i], czesci[i + 1], czesci[i + 2]
        if not (lewy_f.endswith("-") and lewy_f[-2:-1].isalpha() and odstep
                and set(odstep) == {" "} and prawy_f[:1].isalpha()):
            i += 2
            continue
        lewy, prawy = _rdzen_lewy(lewy_f[:-1]), _rdzen_prawy(prawy_f)
        if lewy is None or prawy is None or not prawy[0].islower() \
                or len({_pismo(z) for z in lewy + prawy if z.isalpha()}) != 1:
            liczniki["wykluczone"] += 1
            i += 2
            continue
        wlasne_r = 1 + (lewy.casefold() == prawy.casefold())
        if slowa.get((lewy + prawy).casefold(), 0):
            lista.append((i, "1", lewy_f[:-1] + prawy_f))
        elif slowa.get(f"{lewy}-{prawy}".casefold(), 0):
            lista.append((i, "2", lewy_f + prawy_f))
        elif slowa.get(prawy.casefold(), 0) - wlasne_r <= 0 and not (
                len(lewy) >= MIN_CZLON_ZLOZENIA and lewy[-1].casefold() in _SAMOGLOSKI_ZLOZEN
                and len(lewy + prawy) > (najdluzsze or {}).get(_pismo(lewy[0]), len(lewy + prawy))):
            lista.append((i, "3", lewy_f[:-1] + prawy_f))
        else:
            liczniki["4"] += 1
        i += 4
    return lista


# ---------------------------------------------------------------------------
# 3. Tekst rozstrzelony
# ---------------------------------------------------------------------------

#: Najkrótszy ciąg pojedynczych liter, który bierzemy za rozstrzelenie.
MIN_ROZSTRZELENIE = 4


def litera_pojedyncza(token: str) -> bool:
    """Token z JEDNEJ litery plus ewentualne znaki łączące (akcent)."""
    return bool(token) and token[0].isalpha() and all(
        unicodedata.combining(z) for z in token[1:])


def _apostrof(token: str) -> bool:
    return len(token) == 1 and token in APOSTROFY


def scal_rozstrzelone(akapity: list[str], granica: str | None = None
                      ) -> tuple[list[str], dict[str, int]]:
    """„С о ц и а л ь н о е” → „Социальное”, tylko gdy dokument zna to słowo.

    Ciąg: ≥ `MIN_ROZSTRZELENIE` tokenów jednoliterowych (litera + znaki
    łączące) rozdzielonych POJEDYNCZĄ spacją; w środku ciągu może stać
    apostrof-akcent między dwiema literami („К о в и ' д н а я”), który
    zostaje w słowie. Granica słów: więcej spacji niż jedna albo znak
    `granica` (PDF: granica z geometrii linii, tu tylko decyzja). Sklejamy,
    gdy sklejona forma (`klucz_slowa`) jest słowem dokumentu. Dwa
    ograniczenia — oba wyłącznie ZMNIEJSZAJĄ liczbę sklejeń:
      * ciąg przyklejony pojedynczą spacją do innego tokenu to urwany kawałek
        („м а́ с к а.” — „а.” nie jest tokenem jednoliterowym — dawało
        „ма́ск а.”, bo „Маск” jest słowem) i zostaje;
      * słownik liczony z `scal_apostrofy=True`, więc urywki słów przy
        apostrofie-akcencie („КОВИ'ДНЫЙ” → „кови”) słowami nie są.
    Jednoliterowe słowa (в, к, с, о, и, а, у, я) sklejone przypadkiem nie
    dają słowa dokumentu, więc zostają.

    Returns:
        (akapity, liczniki) — `"sklejone"`, `"bez_zmian"` (słowa nie ma
        w dokumencie), `"przyklejone"`; liczba ciągów. Znaki `granica` są
        w wyniku zamienione na spacje.
    """
    zrodlo = [a.replace(granica, "  ") for a in akapity] if granica else list(akapity)
    slowa = slownik_dokumentu(zrodlo, scal_apostrofy=True)
    liczniki = {"sklejone": 0, "bez_zmian": 0, "przyklejone": 0}
    wynik: list[str] = []
    for akapit in akapity:
        if granica:
            # Separator z granicą (ze spacjami obok) to jeden znak `granica`:
            # dla reguły ciągu nie jest pojedynczą spacją, w wyniku nią jest.
            g = re.escape(granica)
            czesci = re.split(f"( *{g}[ {g}]*| +)", akapit)
            czesci = [(granica if granica in c else c) if i % 2 else c
                      for i, c in enumerate(czesci)]
            wynik.append(_scal_ciagi(czesci, slowa, liczniki).replace(granica, " "))
        else:
            wynik.append(_scal_ciagi(re.split(r"( +)", akapit), slowa, liczniki))
    return wynik, liczniki


def _scal_ciagi(czesci: list[str], slowa: dict[str, int], liczniki: dict[str, int]) -> str:
    """Podział na tekst (indeksy parzyste) i separatory (nieparzyste) → akapit."""

    def pojedyncza(k: int) -> bool:
        return k < len(czesci) and czesci[k] == " "
    nowe: list[str] = []
    i = 0
    while i < len(czesci):
        # Pierwszy token ciągu może nieść interpunkcję otwierającą, symetrycznie
        # do ogona: „(р а з б о р)” → „(разбор)” (etap 6, Земская).
        glowa = ""
        if not i % 2 and not litera_pojedyncza(czesci[i]):
            rdzen = czesci[i].lstrip(OTWIERAJACE)
            if rdzen != czesci[i] and litera_pojedyncza(rdzen):
                glowa = czesci[i][:len(czesci[i]) - len(rdzen)]
        if i % 2 or not (glowa or litera_pojedyncza(czesci[i])):
            nowe.append(czesci[i])
            i += 1
            continue
        j, liter = i, 1
        while j + 2 < len(czesci) and pojedyncza(j + 1):
            if litera_pojedyncza(czesci[j + 2]):
                j, liter = j + 2, liter + 1
            elif _apostrof(czesci[j + 2]) and j + 4 < len(czesci) and pojedyncza(j + 3) \
                    and litera_pojedyncza(czesci[j + 4]):
                j, liter = j + 4, liter + 1
            else:
                break
        # Ostatni token ciągu może nieść interpunkcję zamykającą: „в а к ц и́ н.”
        # → „вакци́н.” (etap 5; słownik PDF +19 sklejeń, Земская +12).
        ogon = ""
        if j + 2 < len(czesci) and pojedyncza(j + 1):
            rdzen = czesci[j + 2].rstrip(ZAMYKAJACE)
            if rdzen != czesci[j + 2] and litera_pojedyncza(rdzen):
                j, liter, ogon = j + 2, liter + 1, czesci[j + 2][len(rdzen):]
        if liter >= MIN_ROZSTRZELENIE:
            przyklejony = (i >= 2 and pojedyncza(i - 1) and czesci[i - 2]) or \
                (j + 2 < len(czesci) and pojedyncza(j + 1) and czesci[j + 2])
            litery = czesci[i:j + 1:2]
            litery[0] = litery[0][len(glowa):]
            if ogon:
                litery[-1] = litery[-1][:-len(ogon)]
            sklejone = "".join(litery)
            if przyklejony:
                liczniki["przyklejone"] += 1
                nowe.extend(czesci[i:j + 1])
            elif slowa.get(klucz_slowa(sklejone), 0):
                liczniki["sklejone"] += 1
                nowe.append(glowa + sklejone + ogon)
            else:
                liczniki["bez_zmian"] += 1
                nowe.extend(czesci[i:j + 1])
        else:
            nowe.extend(czesci[i:j + 1])
        i = j + 1
    return "".join(nowe)


# ---------------------------------------------------------------------------
# 2. Mojibake: jednobajtowa strona kodowa odczytana jako Latin-1 / cp1252
# ---------------------------------------------------------------------------

#: Jak tekst ZOSTAŁ źle odczytany (kodowanie, którym wracamy do bajtów).
ZRODLA_MOJIBAKE = ("latin-1", "cp1252")
#: W czym bajty były naprawdę zapisane — rejestr STRON KODOWYCH (dane
#: techniczne, nie lista języków): Windows, ISO 8859, KOI8, Mac, DOS.
CELE_MOJIBAKE = ("cp1250", "cp1251", "cp1253", "cp1254", "cp1257", "koi8-r",
                 "koi8-u", "iso8859-2", "iso8859-5", "mac-cyrillic", "cp866")
#: Najmniej słów (≥2 litery), żeby ocenić tekst.
MIN_SLOW_MOJIBAKE = 5
#: Mojibake ma WSZYSTKIE litery ze strony kodowej źródła — tak powstał.
#: Rosyjski z akcentem zapisanym łacińskimi samogłoskami („крылó”, „дéрево”,
#: zmierzone w .docx z dysku) ma litery poza Latin-1 i mojibake nie jest:
#: bez tego warunku wychodziło „крылу”, „дйрево”.
MIN_KODOWALNYCH_MOJIBAKE = 0.95
#: Przyjmujemy przekodowanie, gdy wejście ma co najwyżej taki udział słów
#: wiarygodnych, a wynik co najmniej taki (pomiar → nagłówek runnera).
PROG_WEJSCIA_MOJIBAKE = 0.5
PROG_WYNIKU_MOJIBAKE = 0.9

_RE_SLOWO_MOJIBAKE = re.compile(r"[^\W\d_]{2,}")


def przekoduj(tekst: str, zrodlo: str, cel: str) -> str:
    """Znak po znaku: `znak.encode(zrodlo).decode(cel)`; znak spoza → bez zmian."""
    wynik = []
    for z in tekst:
        try:
            b = z.encode(zrodlo)
            wynik.append(b.decode(cel) if len(b) == 1 else z)
        except (UnicodeEncodeError, UnicodeDecodeError):
            wynik.append(z)
    return "".join(wynik)


_JEDNOBAJTOWE: dict[str, frozenset[str]] = {}


def _jednobajtowe(zrodlo: str) -> frozenset[str]:
    """Znaki zapisywalne JEDNYM bajtem w `zrodlo` (raz na kodowanie)."""
    if zrodlo not in _JEDNOBAJTOWE:
        znaki = set()
        for b in range(256):
            try:
                znaki.add(bytes([b]).decode(zrodlo))
            except UnicodeDecodeError:
                pass
        _JEDNOBAJTOWE[zrodlo] = frozenset(z for z in znaki if len(z.encode(zrodlo)) == 1)
    return _JEDNOBAJTOWE[zrodlo]


def kodowalne(tekst: str, zrodlo: str) -> float:
    """Udział liter tekstu zapisywalnych JEDNYM bajtem w kodowaniu `zrodlo`.

    Zbiór znaków zamiast `encode` per znak: funkcja stoi na wejściu
    `napraw_mojibake` dla KAŻDEGO akapitu (etap 6, wyjście przed oceną).
    """
    litery = [z for z in tekst if z.isalpha()]
    if not litery:
        return 0.0
    zbior = _jednobajtowe(zrodlo)
    return sum(z in zbior for z in litery) / len(litery)


def _litery_zachowane(tekst: str, kandydat: str) -> bool:
    """Przekodowanie nie zamienia liter w symbole (mojibake: litera → litera).

    Bez tego cp866 robiło z niemieckiego „Hauptmenüleiste” „Hauptmen№leiste”:
    słowo z niewiarygodnym „ü” rozpadało się na dwa wiarygodne słowa ASCII
    i udział słów wiarygodnych ROSNĄŁ (339 linii paczek de/fr/es przy
    alfabetach sześciu paczek ATA, zmierzone w etapie 5).
    """
    return sum(z.isalpha() for z in kandydat) >= sum(z.isalpha() for z in tekst)


#: Znaki, które prawdziwy tekst pisze sam z siebie, choć przekodowanie robi
#: z nich litery: hiszpańskie „¿”, „¡” (cp1250: „ż”, „ˇ”).
_SYMBOLE_ZWYKLE = "¿¡"


def _przekodowanie_dopuszczalne(tekst: str, kandydat: str) -> bool:
    """Przekodowanie w obrębie JEDNEGO pisma (łacina → łacina) musi zamieniać
    w litery symbole, których zwykły tekst nie pisze („³” → „ł”, „¹” → „ą”,
    „£” → „Ł”). Samo „ñ” → „ń” to podmiana litery na literę: poprawny
    hiszpański („El año pasado el señor…”) wychodził jako „El ańo … seńor”
    przy alfabetach sześciu paczek ATA, bo „ń” jest w polskim (etap 6, audyt
    ATA M1). Zmiana pisma (łacina → cyrylica, „Повесть”) przechodzi zawsze.
    """
    symbol_w_litere = False
    for a, b in zip(tekst, kandydat):
        if a == b:
            continue
        if a.isalpha() and b.isalpha() and _pismo(a) != _pismo(b):
            return True
        if not a.isalpha() and b.isalpha() and a not in _SYMBOLE_ZWYKLE:
            symbol_w_litere = True
    return symbol_w_litere


def wiarygodnosc(tekst: str, alfabety) -> tuple[int, int]:
    """(słów, słów wiarygodnych): słowo jest wiarygodne, gdy jego litery są
    z JEDNEGO pisma i WSZYSTKIE mieszczą się w alfabecie JEDNEJ paczki.

    Sama suma alfabetów nie wystarcza: „Áèáëèîòåêà” ma litery z is, fr, it,
    fi — każdą znaną, ale żadna paczka nie ma ich wszystkich. Jedno pismo:
    paczka rosyjska zna też łacinę (z tekstów `ui.yaml`), więc bez tego
    francuskie „partîmes” po przekodowaniu na „partоmes” (łacina + cyrylica)
    liczyło się jako wiarygodne — zmierzone w ATA bez paczki fr. Pismo to
    pierwszy wyraz nazwy Unicode litery; znaki łączące i apostrofy są
    neutralne (słowo ich nie zawiera: łączące zdjęte, apostrof nie jest literą).
    """
    alfabety = list(alfabety)
    slowa = _RE_SLOWO_MOJIBAKE.findall(bez_laczacych(tekst))
    return len(slowa), sum(1 for s in slowa if len({_pismo(z) for z in s}) == 1
                           and any(set(s) <= a for a in alfabety))


def napraw_mojibake(tekst: str, alfabety, *, min_slow: int = MIN_SLOW_MOJIBAKE
                    ) -> tuple[str, dict]:
    """Przekodowuje tekst, gdy jest mojibake; inaczej zwraca go bez zmian.

    Args:
        alfabety: zbiory liter (obu wielkości) per paczka językowa.

    Returns:
        (tekst, info) — info: `slow`, `wejscie` i `wynik` (udziały słów
        wiarygodnych; `slow`/`wejscie` = `None`, gdy tekstu nie da się zapisać
        w żadnym kodowaniu źródła — cyrylica, polski: wyjście przed oceną),
        `kodowanie` („latin-1>cp1251”) albo `None`.
    """
    zrodla = [z for z in ZRODLA_MOJIBAKE if kodowalne(tekst, z) >= MIN_KODOWALNYCH_MOJIBAKE]
    if not zrodla:
        return tekst, {"slow": None, "wejscie": None, "wynik": None, "kodowanie": None}
    alfabety = [frozenset(a) for a in alfabety]
    n, ok = wiarygodnosc(tekst, alfabety)
    info = {"slow": n, "wejscie": ok / n if n else 1.0, "wynik": None, "kodowanie": None}
    if n < min_slow or info["wejscie"] > PROG_WEJSCIA_MOJIBAKE:
        return tekst, info
    najlepszy = (0.0, None, tekst)
    for zrodlo in zrodla:
        for cel in CELE_MOJIBAKE:
            kandydat = przekoduj(tekst, zrodlo, cel)
            if not _litery_zachowane(tekst, kandydat) or \
                    not _przekodowanie_dopuszczalne(tekst, kandydat):
                continue
            n2, ok2 = wiarygodnosc(kandydat, alfabety)
            if n2 and ok2 / n2 > najlepszy[0]:
                najlepszy = (ok2 / n2, f"{zrodlo}>{cel}", kandydat)
    info["wynik"] = najlepszy[0]
    if najlepszy[0] >= PROG_WYNIKU_MOJIBAKE:
        info["kodowanie"] = najlepszy[1]
        return najlepszy[2], info
    return tekst, info


def napraw_mojibake_akapitow(akapity: list[str], alfabety) -> tuple[list[str], dict]:
    """Mojibake w jednostce (strona PDF albo cały `.docx`): JEDNO kodowanie.

    Przebieg 1: akapit z co najmniej `MIN_SLOW_MOJIBAKE` słowami ocenia
    `napraw_mojibake` samodzielnie (strona z akapitem mojibake i akapitem
    francuskim — ocena całej strony nie przechodziła progu w żadną stronę).
    Przebieg 2: mojibake jednostki powstał JEDNYM kodowaniem, więc stosujemy
    wyłącznie to, które wygrało najczęściej — do każdego akapitu (krótkiego,
    odrzuconego, a także „zdobytego” przez inne kodowanie), o ile podnosi
    jego udział słów wiarygodnych. Zmierzone na „Повесть о Горе-Злочастии”
    (pisze „ѣ” łacińskim „h”, „вhка”): po regule jednego pisma 42 ze 108
    akapitów nie dochodziło samodzielnie do progu 0,9, a jeden przypadkiem
    dochodził przez mac-cyrillic, które z „я” robi „€” („обратилис€”).

    Returns:
        (akapity, info) — `przekodowane` (liczba akapitów) i `kodowania`
        ({„latin-1>cp1251”: liczba akapitów}).
    """
    alfabety = [frozenset(a) for a in alfabety]
    glosy: dict[str, int] = {}
    for akapit in akapity:
        _, info = napraw_mojibake(akapit, alfabety)
        if info["kodowanie"] is not None:
            glosy[info["kodowanie"]] = glosy.get(info["kodowanie"], 0) + 1
    wynik = list(akapity)
    kodowania: dict[str, int] = {}
    if glosy:
        glowne = max(glosy, key=lambda k: glosy[k])
        zrodlo, cel = glowne.split(">")
        for i, akapit in enumerate(akapity):
            if kodowalne(akapit, zrodlo) < MIN_KODOWALNYCH_MOJIBAKE:
                continue
            kandydat = przekoduj(akapit, zrodlo, cel)
            if not _litery_zachowane(akapit, kandydat) or \
                    not _przekodowanie_dopuszczalne(akapit, kandydat):
                continue
            n, ok = wiarygodnosc(akapit, alfabety)
            n2, ok2 = wiarygodnosc(kandydat, alfabety)
            if n2 and n and ok2 / n2 > ok / n:
                wynik[i] = kandydat
                kodowania[glowne] = kodowania.get(glowne, 0) + 1
    return wynik, {"przekodowane": sum(kodowania.values()), "kodowania": kodowania}


# ---------------------------------------------------------------------------
# Całość dla `.docx`
# ---------------------------------------------------------------------------

def oczysc_akapity_docx(akapity: list[str], alfabety=None) -> tuple[list[str], dict[str, int]]:
    """Kolejność: U+F020, mojibake (per akapit, gdy podano alfabety),
    rozstrzelenia, przeniesienia. Liczba akapitów się nie zmienia."""
    akapity, spacje = zamien_spacje_symbol(akapity)
    przekodowane = 0
    if alfabety is not None:
        akapity, info = napraw_mojibake_akapitow(akapity, alfabety)
        przekodowane = info["przekodowane"]
    akapity, rozstrzelone = scal_rozstrzelone(akapity)
    akapity, przeniesienia = napraw_przeniesienia(akapity)
    return akapity, {"spacja_symbol": spacje, "mojibake_akapity": przekodowane,
                     **{f"rozstrzelone_{k}": v for k, v in rozstrzelone.items()},
                     **{f"przeniesienia_{k}": v for k, v in przeniesienia.items()}}
