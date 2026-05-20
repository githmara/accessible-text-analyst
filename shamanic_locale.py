import csv
import re
from pathlib import Path

# Wsparcie dla języków zgodnie z notebookiem (cell_langdet -> SUPPORTED_LANGS).
LANGUAGE_NAMES = {
    'pl': 'Polish',
    'en': 'English',
    'ru': 'Russian',
    'fi': 'Finnish',
    'is': 'Icelandic',
    'it': 'Italian',
}

# Bundle stringów dla artefaktów wyjściowych. Klucze są płaskie ('ritual.element').
# Wartości:
#   - stringi z polami {placeholder} formatuje się przez t(lang, key, **kwargs).
#   - 'prophecy.templates' to lista 4 wzorców (round-robin po akapitach).
#
# Uwaga gramatyczna: dla fi/is encje z entities.csv są już w deklinacji
# (Euroopassa, Yhdysvaltoihin, staðnum...). Bez prawdziwej morfologii nie da się
# ich odmienić z powrotem do mianownika, więc szablony fi/is używają prefiksów
# nominalnych (paikan {loc}, staðnum {loc}, hahmon {per} kautta itp.) —
# brzmi to jak nagłówek mantry, ale jest gramatycznie bezpieczne.
STRINGS = {
    'pl': {
        'oracle.header': (
            '--- WYROCZNIA STRUMIENIA ŚWIADOMOŚCI ---\n'
            'Instrukcja TTS: czytać powoli, z narastającym echem.\n\n'
        ),
        'roots.header': (
            '--- RYTUAŁ SUROWYCH RDZENI ---\n'
            'Instrukcja TTS: odczyt mechaniczny, nieludzki, pozbawiony emocji.\n\n'
        ),
        'lore.header': (
            '// SYGNATURA ZNALEZISKA: TOPIC-{topic_id} / FRAGMENT-{para_id} //\n'
            '// STATUS: USZKODZONY ZAPIS RADIOWY //\n\n'
        ),
        'prophecy.header': (
            '--- KSIĘGA PRZEPOWIEDNI Z PYŁU ---\n'
            'Instrukcja TTS: czytać dostojnie, z pauzami przed dwukropkami.\n\n'
        ),
        'prophecy.section': '[PRZEPOWIEDNIA {n}]',
        'prophecy.templates': [
            'Z pyłu {loc} wstanie {per}, aby {sentence}',
            'Gdy księżyc krwi zawiśnie nad {loc}, {per} wyrzeknie: {sentence}',
            'Z trzewi {org} wyszepcze {per} ku {loc}: {sentence}',
            'Pradawny głos {loc} przemówi przez {per}: {sentence}',
        ],
        'prophecy.fallback.loc': 'bezimiennej krainy',
        'prophecy.fallback.per': 'Bezimienny',
        'prophecy.fallback.org': 'zapomnianego zakonu',
        'katla.header': '--- MONOLOG ZAMROŻONYCH BYTÓW (GŁOS: KATLA) ---\n\n',
        'vieno.header': '--- SZAMAŃSKA INWOKACJA ECH (GŁOS: VIENO) ---\n\n',
        'lumi.header': '--- MELDUNEK OSTATECZNY Z MROŹNEJ PÓŁNOCY (GŁOS: LUMI) ---\n\n',
    },
    'en': {
        'oracle.header': (
            '--- ORACLE OF THE STREAM OF CONSCIOUSNESS ---\n'
            'TTS instruction: read slowly, with a rising echo.\n\n'
        ),
        'roots.header': (
            '--- RITUAL OF THE RAW ROOTS ---\n'
            'TTS instruction: mechanical reading, inhuman, devoid of emotion.\n\n'
        ),
        'lore.header': (
            '// FIND SIGNATURE: TOPIC-{topic_id} / FRAGMENT-{para_id} //\n'
            '// STATUS: CORRUPTED RADIO LOG //\n\n'
        ),
        'prophecy.header': (
            '--- BOOK OF PROPHECIES FROM THE DUST ---\n'
            'TTS instruction: read solemnly, with pauses before the colons.\n\n'
        ),
        'prophecy.section': '[PROPHECY {n}]',
        'prophecy.templates': [
            'From the dust of {loc} shall rise {per}, to {sentence}',
            'When the blood moon hangs over {loc}, {per} shall utter: {sentence}',
            'From the entrails of {org} {per} shall whisper toward {loc}: {sentence}',
            'The ancient voice of {loc} shall speak through {per}: {sentence}',
        ],
        'prophecy.fallback.loc': 'a nameless land',
        'prophecy.fallback.per': 'the Nameless One',
        'prophecy.fallback.org': 'a forgotten order',
        'katla.header': '--- MONOLOGUE OF THE FROZEN BEINGS (VOICE: KATLA) ---\n\n',
        'vieno.header': '--- SHAMANIC INVOCATION OF ECHOES (VOICE: VIENO) ---\n\n',
        'lumi.header': '--- FINAL DISPATCH FROM THE FROZEN NORTH (VOICE: LUMI) ---\n\n',
    },
    'ru': {
        'oracle.header': (
            '--- ОРАКУЛ ПОТОКА СОЗНАНИЯ ---\n'
            'Инструкция TTS: читать медленно, с нарастающим эхом.\n\n'
        ),
        'roots.header': (
            '--- РИТУАЛ СЫРЫХ КОРНЕЙ ---\n'
            'Инструкция TTS: чтение механическое, нечеловеческое, лишённое эмоций.\n\n'
        ),
        'lore.header': (
            '// СИГНАТУРА НАХОДКИ: TOPIC-{topic_id} / FRAGMENT-{para_id} //\n'
            '// СТАТУС: ПОВРЕЖДЁННАЯ РАДИОЗАПИСЬ //\n\n'
        ),
        'prophecy.header': (
            '--- КНИГА ПРОРОЧЕСТВ ИЗ ПРАХА ---\n'
            'Инструкция TTS: читать торжественно, с паузами перед двоеточиями.\n\n'
        ),
        'prophecy.section': '[ПРОРОЧЕСТВО {n}]',
        'prophecy.templates': [
            'Из праха {loc} восстанет {per}, дабы {sentence}',
            'Когда кровавая луна повиснет над {loc}, {per} изречёт: {sentence}',
            'Из чрева {org} прошепчет {per} к {loc}: {sentence}',
            'Древний голос {loc} проговорит через {per}: {sentence}',
        ],
        'prophecy.fallback.loc': 'безымянной земли',
        'prophecy.fallback.per': 'Безымянный',
        'prophecy.fallback.org': 'забытого ордена',
        'katla.header': '--- МОНОЛОГ ЗАМЁРЗШИХ СУЩНОСТЕЙ (ГОЛОС: КАТЛА) ---\n\n',
        'vieno.header': '--- ШАМАНСКАЯ ИНВОКАЦИЯ ОТЗВУКОВ (ГОЛОС: ВИЕНО) ---\n\n',
        'lumi.header': '--- ПОСЛЕДНИЙ ОТЧЁТ С МОРОЗНОГО СЕВЕРА (ГОЛОС: ЛУМИ) ---\n\n',
    },
    'fi': {
        'oracle.header': (
            '--- TIETOISUUDEN VIRRAN ORAAKKELI ---\n'
            'TTS-ohje: lue hitaasti, kasvavalla kaiulla.\n\n'
        ),
        'roots.header': (
            '--- RAAKOJEN JUURTEN RITUAALI ---\n'
            'TTS-ohje: mekaaninen luku, epäinhimillinen, tunteeton.\n\n'
        ),
        'lore.header': (
            '// LÖYDÖN TUNNUS: TOPIC-{topic_id} / FRAGMENT-{para_id} //\n'
            '// TILA: VAURIOITUNUT RADIOTALLENNE //\n\n'
        ),
        'prophecy.header': (
            '--- TOMUSTA NOUSEVAN ENNUSTUKSEN KIRJA ---\n'
            'TTS-ohje: lue arvokkaasti, tauoilla ennen kaksoispisteitä.\n\n'
        ),
        'prophecy.section': '[ENNUSTUS {n}]',
        'prophecy.templates': [
            'Tomusta — {loc} — nousee {per}, joka: {sentence}',
            'Kun veren kuu riippuu paikan {loc} yllä, {per} lausuu: {sentence}',
            'Yhteisön {org} sisältä kuiskaa {per} kohti paikkaa {loc}: {sentence}',
            'Muinainen ääni — {loc} — puhuu hahmon {per} kautta: {sentence}',
        ],
        'prophecy.fallback.loc': 'nimetön maa',
        'prophecy.fallback.per': 'Nimetön',
        'prophecy.fallback.org': 'unohdettu veljeskunta',
        'katla.header': '--- JÄÄTYNEIDEN OLENTOJEN MONOLOGI (ÄÄNI: KATLA) ---\n\n',
        'vieno.header': '--- KAIKUJEN SAMAANIKUTSU (ÄÄNI: VIENO) ---\n\n',
        'lumi.header': '--- VIIMEINEN RAPORTTI KYLMÄSTÄ POHJOLASTA (ÄÄNI: LUMI) ---\n\n',
    },
    'is': {
        'oracle.header': (
            '--- ORAKEL VITUNDARSTREYMIS ---\n'
            'TTS-leiðbeining: lestu hægt, með vaxandi bergmáli.\n\n'
        ),
        'roots.header': (
            '--- RITÚAL HRÁU RÓTANNA ---\n'
            'TTS-leiðbeining: vélrænn lestur, ómannlegur, tilfinningalaus.\n\n'
        ),
        'lore.header': (
            '// FUNDARSKILRÍKI: TOPIC-{topic_id} / FRAGMENT-{para_id} //\n'
            '// STAÐA: SKEMMD ÚTVARPSSKRÁ //\n\n'
        ),
        'prophecy.header': (
            '--- BÓK SPÁDÓMA ÚR RYKINU ---\n'
            'TTS-leiðbeining: lestu með reisn, með pásu fyrir tvípunkta.\n\n'
        ),
        'prophecy.section': '[SPÁDÓMUR {n}]',
        'prophecy.templates': [
            'Úr ryki — {loc} — rís {per}, til þess að: {sentence}',
            'Þegar blóðtunglið hangir yfir staðnum {loc}, mun {per} mæla: {sentence}',
            'Úr innyflum reglunnar {org} hvíslar {per} til staðarins {loc}: {sentence}',
            'Forn rödd — {loc} — talar gegnum {per}: {sentence}',
        ],
        'prophecy.fallback.loc': 'ónefnt land',
        'prophecy.fallback.per': 'hinn nafnlausi',
        'prophecy.fallback.org': 'gleymd regla',
        'katla.header': '--- EINTAL FROSINNA VERA (RÖDD: KATLA) ---\n\n',
        'vieno.header': '--- SEIÐKALL BERGMÁLA (RÖDD: VIENO) ---\n\n',
        'lumi.header': '--- LOKASKÝRSLA FRÁ FROSNU NORÐRI (RÖDD: LUMI) ---\n\n',
    },
    'it': {
        'oracle.header': (
            '--- ORACOLO DEL FLUSSO DI COSCIENZA ---\n'
            'Istruzione TTS: leggere lentamente, con eco crescente.\n\n'
        ),
        'roots.header': (
            '--- RITO DELLE RADICI GREZZE ---\n'
            'Istruzione TTS: lettura meccanica, inumana, priva di emozioni.\n\n'
        ),
        'lore.header': (
            '// FIRMA DEL RITROVAMENTO: TOPIC-{topic_id} / FRAGMENT-{para_id} //\n'
            '// STATO: REGISTRAZIONE RADIO DANNEGGIATA //\n\n'
        ),
        'prophecy.header': (
            '--- LIBRO DELLE PROFEZIE DALLA POLVERE ---\n'
            'Istruzione TTS: leggere solennemente, con pause prima dei due punti.\n\n'
        ),
        'prophecy.section': '[PROFEZIA {n}]',
        'prophecy.templates': [
            'Dalla polvere di {loc} sorgerà {per}, per {sentence}',
            'Quando la luna di sangue penderà su {loc}, {per} pronuncerà: {sentence}',
            'Dalle viscere di {org} sussurrerà {per} verso {loc}: {sentence}',
            "L'antica voce di {loc} parlerà attraverso {per}: {sentence}",
        ],
        'prophecy.fallback.loc': 'una terra senza nome',
        'prophecy.fallback.per': 'il Senza Nome',
        'prophecy.fallback.org': 'un ordine dimenticato',
        'katla.header': '--- MONOLOGO DEGLI ESSERI GHIACCIATI (VOCE: KATLA) ---\n\n',
        'vieno.header': '--- INVOCAZIONE SCIAMANICA DEGLI ECHI (VOCE: VIENO) ---\n\n',
        'lumi.header': '--- DISPACCIO FINALE DAL NORD GHIACCIATO (VOCE: LUMI) ---\n\n',
    },
}


def t(lang, key, **kwargs):
    """Pobierz string z bundle'a. Fallback przez en jeśli klucza brak w lang."""
    bundle = STRINGS.get(lang) or STRINGS['en']
    value = bundle.get(key)
    if value is None:
        value = STRINGS['en'].get(key, '')
    if kwargs and isinstance(value, str):
        return value.format(**kwargs)
    return value


_HTML_LANG_RE = re.compile(r'<html\s+lang="([a-z]{2})"', re.IGNORECASE)


def detect_corpus_lang(export_dir, default='en'):
    """Wykryj język korpusu (ISO 639-1 ograniczone do LANGUAGE_NAMES).

    Kolejność źródeł:
    1. atrybut <html lang="..."> z accessible_text.html (zapisane przez notebook),
    2. lingua-language-detector na pierwszych ~30 zdaniach z sentences.csv,
    3. fallback `default` ('en').
    """
    export_dir = Path(export_dir)
    html_path = export_dir / 'accessible_text.html'
    if html_path.exists():
        try:
            head = html_path.read_text(encoding='utf-8', errors='ignore')[:512]
            m = _HTML_LANG_RE.search(head)
            if m:
                code = m.group(1).lower()
                if code in LANGUAGE_NAMES:
                    return code
        except OSError:
            pass

    sentences_path = export_dir / 'sentences.csv'
    if sentences_path.exists():
        try:
            from lingua import Language, LanguageDetectorBuilder
            detector = LanguageDetectorBuilder.from_languages(
                Language.ENGLISH, Language.POLISH, Language.RUSSIAN,
                Language.ITALIAN, Language.FINNISH, Language.ICELANDIC,
            ).build()
            sample_parts = []
            with open(sentences_path, 'r', encoding='utf-8-sig') as f:
                for i, row in enumerate(csv.DictReader(f)):
                    if i >= 30:
                        break
                    sample_parts.append(row.get('sentence', ''))
            lang_obj = detector.detect_language_of(' '.join(sample_parts))
            if lang_obj is not None:
                code = lang_obj.iso_code_639_1.name.lower()
                if code in LANGUAGE_NAMES:
                    return code
        except Exception:
            pass

    return default
