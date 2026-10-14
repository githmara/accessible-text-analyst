"""llm_klient.py — wspólny wybór providera LLM dla shamanic_ai.py i ksiega_niedomowien.py.

Zasada: zmienna z kluczem jest przywiązana do JEDNEGO hosta. Klucz nigdy nie
trafia pod adres, dla którego nie został wydany — dlatego provider jest jawnym
identyfikatorem w configu, a nie skutkiem ubocznym ustawienia base URL.

    openai         OPENAI_API_KEY      -> https://api.openai.com/v1 (na sztywno)
    openrouter     OPENROUTER_API_KEY  -> https://openrouter.ai/api/v1 (na sztywno)
    openai_compat  LLM_COMPAT_API_KEY  -> llm_base_url z configu (wymagany)

Base URL jest czytany wyłącznie dla openai_compat. Dla openai podajemy adres
jawnie, bo SDK samo czyta OPENAI_BASE_URL ze środowiska — bez tego zmienna
środowiskowa mogłaby po cichu przekierować OPENAI_API_KEY na inny host.

Wszystkie trzy mówią Chat Completions, więc wystarcza SDK `openai`. chat_json()
daje odpowiedź JSON z drabiną json_schema -> json_object -> prompt (wzorzec reżysera).
Klucze: golden_key.env (python-dotenv). Komunikaty: t(ui_lang, "llm.*")
z dictionaries/{lang}/reports.yaml.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from shamanic_locale import t

ROOT = Path(__file__).resolve().parent

PROVIDERS = {
    "openai": {"key": "OPENAI_API_KEY", "base_url": "https://api.openai.com/v1", "model": "gpt-6.1-sol"},
    "openrouter": {"key": "OPENROUTER_API_KEY", "base_url": "https://openrouter.ai/api/v1",
                   "model": "openai/gpt-6.1-sol"},
    "openai_compat": {"key": "LLM_COMPAT_API_KEY", "base_url": None, "model": None},
}
DEFAULT_PROVIDER = "openai"

# Klucze configu, które przed v1.7.0 kierowały OPENAI_API_KEY pod dowolny adres.
LEGACY_KEYS = ("kirja_filler_base_url",)


class LLMConfigError(Exception):
    """Niekompletna lub niebezpieczna konfiguracja LLM (komunikat już zlokalizowany)."""


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    key_var: str
    base_url: str
    model: str

    @property
    def endpoint(self):
        return self.base_url.split("://", 1)[-1].rstrip("/")


def resolve(cfg, ui_lang, provider_key="llm_provider", provider=None, model=None, legacy_keys=()):
    """Ustala providera, host, zmienną klucza i model — bez dotykania sieci.

    provider: jawne nadpisanie (CLI) > cfg[provider_key] > cfg["llm_provider"] > openai.
    model:    jawne nadpisanie > cfg["llm_model"] (tylko gdy provider = globalny) >
              domyślny providera; openai_compat nie ma domyślnego modelu.
    legacy_keys: przestarzałe klucze, których obecność ma zatrzymać wołającego
    (Księga podaje LEGACY_KEYS; szaman ich nie czytał, więc ich nie sprawdza).
    """
    for k in legacy_keys:
        if (cfg.get(k) or "").strip():
            raise LLMConfigError(t(ui_lang, "llm.err_legacy_base_url", name=k))
    global_provider = (cfg.get("llm_provider") or "").strip().lower() or DEFAULT_PROVIDER
    name = (provider or (cfg.get(provider_key) or "").strip().lower() or global_provider).lower()
    if name not in PROVIDERS:
        raise LLMConfigError(t(ui_lang, "llm.err_unknown_provider", provider=name,
                               known=", ".join(PROVIDERS)))
    spec = PROVIDERS[name]
    base_url = spec["base_url"]
    if base_url is None:
        base_url = (cfg.get("llm_base_url") or "").strip()
        if not base_url:
            raise LLMConfigError(t(ui_lang, "llm.err_compat_no_base_url"))
    chosen = (model or "").strip()
    if not chosen and name == global_provider:
        chosen = (cfg.get("llm_model") or "").strip()
    chosen = chosen or spec["model"]
    if not chosen:
        raise LLMConfigError(t(ui_lang, "llm.err_compat_no_model"))
    return LLMSettings(name, spec["key"], base_url, chosen)


def build_client(settings, ui_lang):
    """Klient SDK `openai` dla ustalonego providera. Klucz czytany tylko z jego zmiennej."""
    try:
        from dotenv import load_dotenv
        from openai import OpenAI
    except ImportError:
        raise LLMConfigError(t(ui_lang, "llm.err_no_sdk")) from None
    load_dotenv(ROOT / "golden_key.env")
    key = (os.environ.get(settings.key_var) or "").strip()
    if not key:
        raise LLMConfigError(t(ui_lang, "llm.err_no_key", var=settings.key_var,
                               provider=settings.provider))
    return OpenAI(api_key=key, base_url=settings.base_url)


# ==========================================
# Odpowiedzi strukturalne (wzorzec z core_llm.py reżysera)
# ==========================================

# Klucze, których structured outputs nie przyjmuje. Schemat KANONICZNY (u
# wołającego) zostaje nietknięty i nadal służy do walidacji po naszej stronie;
# do API idzie kopia z limitami przeniesionymi do `description`.
_UNSUPPORTED_KEYS = frozenset({
    "minItems", "maxItems", "minLength", "maxLength",
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
    "multipleOf", "pattern", "minProperties", "maxProperties", "uniqueItems",
})

# Przepełnienie kontekstu przychodzi tym samym 400 co błąd struktury, ale żadna
# degradacja formatu go nie naprawi — rozpoznajemy je po treści albo 413.
_CONTEXT_PHRASES = (
    "prompt is too long", "context_length_exceeded", "maximum context length",
    "exceed context limit", "context window", "too many tokens",
    "reduce the length of the messages",
)

# Drabina: od najściślejszego wymuszenia do samego promptu.
MODES = ("json_schema", "json_object", "prompt")

# Szczebel, który zadziałał, per (provider, adres, model) — kolejne wywołania w
# tym samym uruchomieniu (retry, następne pakiety) nie płacą znowu za odrzucenia.
_WORKING_MODE = {}


def _constraint_note(node):
    """Zdejmowane limity jako zwięzła notka po angielsku (model czyta `description`)."""
    parts = []
    lo, hi = node.get("minItems"), node.get("maxItems")
    if lo is not None and hi is not None:
        parts.append(f"Provide exactly {lo} items." if lo == hi else f"Provide between {lo} and {hi} items.")
    elif lo is not None:
        parts.append(f"Provide at least {lo} item(s).")
    elif hi is not None:
        parts.append(f"Provide at most {hi} items.")
    if node.get("minLength"):
        parts.append("Must not be empty.")
    if node.get("maxLength") is not None:
        parts.append(f"Keep it under {node['maxLength']} characters.")
    return " ".join(parts)


def schema_for_api(schema):
    """KOPIA schematu w podzbiorze structured outputs: bez _UNSUPPORTED_KEYS,
    `additionalProperties: false` w każdym obiekcie, limity przeniesione do `description`."""
    if isinstance(schema, dict):
        out = {k: schema_for_api(v) for k, v in schema.items() if k not in _UNSUPPORTED_KEYS}
        if out.get("type") == "object":
            out["additionalProperties"] = False
        note = _constraint_note(schema)
        if note:
            out["description"] = f"{str(out.get('description', '')).strip()} {note}".strip()
        return out
    if isinstance(schema, list):
        return [schema_for_api(v) for v in schema]
    return schema


def _status(exc):
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    return status


def is_context_overflow(exc):
    if _status(exc) == 413:
        return True
    text = str(exc).lower()
    return any(p in text for p in _CONTEXT_PHRASES)


def is_structure_error(exc):
    """Czy endpoint odrzucił KSZTAŁT payloadu (400/422), a nie limit, sieć czy kontekst."""
    if is_context_overflow(exc):
        return False
    if type(exc).__name__ in ("BadRequestError", "UnprocessableEntityError"):
        return True
    return _status(exc) in (400, 422)


@dataclass(frozen=True)
class LLMReply:
    text: str
    mode: str
    finish_reason: str
    refusal: str


def chat_json(client, settings, prompt, schema, name, ui_lang):
    """Jedno wywołanie Chat Completions z możliwie najściślejszym formatem JSON.

    json_schema (strict) -> json_object -> sam prompt. Szczebel niżej tylko po
    błędzie struktury; 429, timeout, sieć i przepełnienie kontekstu lecą wyżej od
    razu. Bez `temperature`: część nowszych modeli odrzuca wartości niedomyślne.
    """
    formats = {
        "json_schema": {"type": "json_schema",
                        "json_schema": {"name": name, "strict": True, "schema": schema_for_api(schema)}},
        "json_object": {"type": "json_object"},
        "prompt": None,
    }
    cache_key = (settings.provider, settings.base_url, settings.model)
    start = MODES.index(_WORKING_MODE.get(cache_key, MODES[0]))
    for i in range(start, len(MODES)):
        mode = MODES[i]
        kwargs = {"model": settings.model, "messages": [{"role": "user", "content": prompt}]}
        if formats[mode] is not None:
            kwargs["response_format"] = formats[mode]
        try:
            resp = client.chat.completions.create(**kwargs)
        except Exception as e:
            if i == len(MODES) - 1 or not is_structure_error(e):
                raise
            print(t(ui_lang, "llm.info_degraded", endpoint=settings.endpoint, mode=mode,
                    next=MODES[i + 1], error=str(e)[:200]))
            continue
        _WORKING_MODE[cache_key] = mode
        choice = resp.choices[0] if getattr(resp, "choices", None) else None
        msg = getattr(choice, "message", None)
        return LLMReply(text=(getattr(msg, "content", None) or ""), mode=mode,
                        finish_reason=str(getattr(choice, "finish_reason", None) or "-"),
                        refusal=str(getattr(msg, "refusal", None) or ""))
    raise RuntimeError("unreachable")


# Modele, które odrzuciły niedomyślną `temperature` — per (provider, adres, model),
# żeby kolejne rytuały tego samego uruchomienia nie płaciły znowu za odrzucenie.
_NO_TEMPERATURE = set()


def is_temperature_error(exc):
    """Czy 400 dotyczy WYŁĄCZNIE parametru `temperature` (rodzina gpt-6 przyjmuje tylko 1)."""
    if not is_structure_error(exc):
        return False
    if getattr(exc, "param", None) == "temperature":
        return True
    return "temperature" in str(exc).lower()


def chat_text(client, settings, messages, temperature, ui_lang):
    """Chat Completions z `temperature` wołającego, a bez niej, gdy model ją odrzuca.

    Twórcze temperatury rytuałów zostają tam, gdzie model je przyjmuje; model,
    który zna tylko wartość domyślną (gpt-6.x: 400 „Only the default (1) value is
    supported"), dostaje jedno ponowienie bez parametru. Każdy inny błąd leci wyżej.
    """
    cache_key = (settings.provider, settings.base_url, settings.model)
    kwargs = {"model": settings.model, "messages": messages}
    if cache_key not in _NO_TEMPERATURE:
        try:
            return client.chat.completions.create(**kwargs, temperature=temperature)
        except Exception as e:
            if not is_temperature_error(e):
                raise
            _NO_TEMPERATURE.add(cache_key)
            print(t(ui_lang, "llm.info_no_temperature", model=settings.model,
                    temperature=temperature))
    return client.chat.completions.create(**kwargs)


def save_diagnostics(path, reply, ui_lang):
    """Zapisuje surową odpowiedź (z metadanymi) i wypisuje jednolinijkową diagnozę."""
    path.write_text(f"mode: {reply.mode}\nfinish_reason: {reply.finish_reason}\n"
                    f"refusal: {reply.refusal or '-'}\nchars: {len(reply.text)}\n\n{reply.text}",
                    encoding="utf-8")
    # jedna linia dla czytnika ekranu: bez złamań, cytat odmowy skrócony (całość jest w pliku)
    short = " ".join(reply.refusal.split())
    short = short if len(short) <= 120 else short[:117].rstrip() + "..."
    refusal = t(ui_lang, "llm.diag_refusal", text=short) if reply.refusal else ""
    print(t(ui_lang, "llm.diag_reply", mode=reply.mode, finish=reply.finish_reason,
            chars=len(reply.text), refusal=refusal, path=path))
