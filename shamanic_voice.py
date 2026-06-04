import os
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

from shamanic_locale import get_ui_lang, t

# Język UI (printy w konsoli) — niezależny od języka korpusu. Body głosów jest
# już wygenerowane przez shamanic_ai.py w języku korpusu; tu tylko czytamy
# gotowe artefakty i wysyłamy je do ElevenLabs (model eleven_multilingual_v2
# sam wykrywa język mowy), więc skrypt potrzebuje wyłącznie UI_LANG.
UI_LANG = get_ui_lang()

# Klucz z gitignorowanego golden_key.env (ten sam plik co OPENAI_API_KEY).
load_dotenv("golden_key.env")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")

# Te cztery pliki to dokładnie output shamanic_ai.py — nazwy są hardkodowane po
# angielsku w obu miejscach. Klucz głosu (katla/...) mapuje na config["voices"].
# Kolejność = kolejność rytuałów (Lumi czyta Katlę/Vieno, Sami czyta Lumi).
VOICE_SEQUENCE = (
    ('katla', 'katla_entity_monologue.txt'),
    ('vieno', 'vieno_echoes_chant.txt'),
    ('lumi', 'lumi_final_report.txt'),
    ('sami', 'sami_energetic_spark.txt'),
)

_ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
_ELEVENLABS_MODEL = "eleven_multilingual_v2"


def _locate_config():
    # Akceptujemy config.json i config.ini (treść zawsze JSON) — jak reszta repo.
    for name in ('config.json', 'config.ini'):
        if Path(name).is_file():
            return name
    return 'config.json'


def _load_config():
    try:
        with open(_locate_config(), 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _slugify(s, maxlen=80):
    # Mirror cell_corpus / shamanic_ai._slugify.
    s = re.sub(r"[^\w\-\.]+", "_", s, flags=re.UNICODE).strip("._")
    return s[:maxlen] or "_default"


def get_export_dir(config):
    source_path = (config.get('source_file') or '').strip()
    if not source_path:
        name = "_default"
    elif source_path.startswith(("http://", "https://")):
        u = urlparse(source_path)
        host = (u.netloc or "url").replace("www.", "")
        path = u.path.strip("/").replace("/", "_") or "index"
        name = _slugify(f"{host}_{path}")
    else:
        name = _slugify(Path(source_path).stem)
    return Path('export_results') / name


def _read_body(file_path):
    # Treść artefaktu bez nagłówka (pierwszy blok do podwójnego \n\n) — ten sam
    # podział, którego używa shamanic_ai._read_artifact_body przy splataniu głosów.
    text = file_path.read_text(encoding='utf-8')
    blocks = text.split('\n\n', 1)
    return blocks[1].strip() if len(blocks) == 2 else text.strip()


def _synthesize(text, voice_id, output_path):
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY,
    }
    data = {
        "text": text,
        "model_id": _ELEVENLABS_MODEL,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    response = requests.post(
        _ELEVENLABS_URL.format(voice_id=voice_id), json=data, headers=headers
    )
    response.raise_for_status()
    output_path.write_bytes(response.content)


def voice_artifact(voice_key, filename, audio_dir, voices):
    """Kontrakt trójwartościowy jak w rytuałach szamańskich:
    produced -> True; legitnie pominięty (brak pliku / brak ID / pusta treść)
    -> False; błąd syntezy -> wyjątek (łapany przez pętlę w __main__)."""
    source = audio_dir / filename
    if not source.exists():
        # Głos nie powstał (shamanic_ai.py nie odpalił tego rytuału) — legalny
        # częściowy stan, nie błąd.
        return False

    voice_id = voices.get(voice_key)
    if not voice_id:
        print(t(UI_LANG, 'dispatcher.warn_no_voice_id', voice=voice_key))
        return False

    body = _read_body(source)
    if not body:
        return False

    output_path = source.with_suffix('.mp3')
    _synthesize(body, voice_id, output_path)
    print(t(UI_LANG, 'dispatcher.ok_voice', voice=voice_key, filename=output_path.name))
    return True


if __name__ == "__main__":
    print(t(UI_LANG, 'dispatcher.starting'))
    try:
        if not ELEVENLABS_API_KEY:
            raise RuntimeError(t(UI_LANG, 'dispatcher.err_no_api_key'))

        config = _load_config()
        voices = config.get('voices') or {}
        if not voices:
            raise RuntimeError(t(UI_LANG, 'dispatcher.err_no_voices'))

        export_dir = get_export_dir(config)
        audio_dir = export_dir / 'audio_scripts'
        # Krytyczny strażnik: brak audio_scripts/ = potok szamański nie odpalił.
        if not audio_dir.is_dir():
            raise RuntimeError(t(UI_LANG, 'dispatcher.err_no_audio_scripts', path=audio_dir))

        produced = 0
        failures = []
        for voice_key, filename in VOICE_SEQUENCE:
            try:
                if voice_artifact(voice_key, filename, audio_dir, voices):
                    produced += 1
            except Exception as e:
                failures.append(voice_key)
                print(t(UI_LANG, 'dispatcher.warn_voice_failed', voice=voice_key, error=e))

        if failures:
            print("\n" + t(UI_LANG, 'dispatcher.done_with_errors',
                           failed=len(failures), total=len(VOICE_SEQUENCE)))
        elif produced == 0:
            print("\n" + t(UI_LANG, 'dispatcher.warn_nothing_produced', path=audio_dir))
        else:
            print("\n" + t(UI_LANG, 'dispatcher.done', count=produced))
    except Exception as e:
        print(t(UI_LANG, 'dispatcher.fatal_error', error=e))
