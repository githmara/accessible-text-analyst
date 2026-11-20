"""helsinki_reacts.py — satirical stream script: Valtteri from Helsinki reacts to a recording.

Input: an export folder name (`export_results/<name>/accessible_text.html`, text without
markup and headings) or any text file. Output: `export_results/_streams/<name>.md`.

The system prompt lives OUTSIDE the code, because it is where the user decides what the
stream is like: `helsinki_reacts.md` (the user's copy, gitignored) wins over the shipped
`helsinki_reacts.example.md`; `--prompt` points at any other file. HTML comments in the
prompt file are not sent. The script adds only what has to work whatever the prompt says:
the input data, the output language and — with `--kirja` — the Book of the Unsaid bridge.

Stream language: `--lang` > config `reacts_lang` > `ui_lang`. Finnish = the stream itself,
in plain Finnish; any other language = its translation with Finnish interjections.

Provider: llm_klient, `reacts_llm_provider` / `reacts_model` (empty = the global ones);
`--provider` / `--model` override both. Paid API: the text of every recording leaves the
machine, and the script says so before the first call.
"""

import argparse
import html.parser
import json
import re
import sys
from pathlib import Path

import llm_klient
from shamanic_locale import LANGUAGE_NAMES, get_ui_lang, t

ROOT = Path(__file__).resolve().parent
EXPORT_DIR = ROOT / "export_results"
STREAMS_DIR = EXPORT_DIR / "_streams"
PROMPT_LOCAL = ROOT / "helsinki_reacts.md"
PROMPT_DEFAULT = ROOT / "helsinki_reacts.example.md"
KIRJA = EXPORT_DIR / "Sanomattomien_kirja.md"
KIRJA_AVAIN = EXPORT_DIR / "Sanomattomien_kirja.avain.json"
KIRJA_TYOTILA = EXPORT_DIR / "_kirja_tyotila"
HTML_NAME = "accessible_text.html"
GAP = "— … —"

UI_LANG = get_ui_lang()
DEFAULT_EFFORT = "low"
TEMPERATURE = 1.0
# A full stream is several thousand characters; a refusal is a few dozen.
DEFAULT_MIN_CHARS = 1500

_HTML_COMMENT = re.compile("<!--.*?-->", re.S)

LANGUAGE_FINNISH = (
    "OUTPUT LANGUAGE: Finnish. The script IS the stream, in natural, colloquial Finnish — "
    "not a translation. Speaker tags stay **Valtteri:** and **Lumi:**. Fixed formulas the "
    "prompt quotes in another language (the on-screen title line, Lumi's donation line) are "
    "written in Finnish too."
)
LANGUAGE_TRANSLATED = (
    "OUTPUT LANGUAGE: {language}. The stream happens in Finnish and you write its {language} "
    "translation: every line in {language}, but keep short Finnish interjections (such as "
    "\"Moi\", \"Kiitos\", \"Perkele\") untranslated — they are the stream's flavour. Speaker "
    "tags stay **Valtteri:** and **Lumi:**. Fixed formulas the prompt quotes in another "
    "language (the on-screen title line, Lumi's donation line) are written in {language} too."
)

# Added only with --kirja and only when the folder has an entry. It is in the code, not in
# the editable prompt, because it protects the Book: the gaps hide words that really occur
# in the recording, so comparing a gap with the recording would give the answer away
# (measured 2026-11-20: without this rule Valtteri filled gaps from the recording).
KIRJA_RULES = """THE BOOK OF THE UNSAID
Below the recording there is an entry from "Sanomattomien kirja" (The Book of the Unsaid). In the stream it is an anonymous diary "from the far North" circulating on the Finnish internet: KATLA, an automated warning system, reads root words, and VIENO weaves a misty text around them. The places marked "— … —(n)" are unsaid on purpose. The entry is about the same drama as the recording, and part of the chat knows it.
- The entry is material for the CHAT, not for Valtteri. Viewers bring it to the stream: they quote short fragments (the gaps stay "— … —"), link them to the recording and argue about what the images mean. Two or three fragments in the whole stream are enough.
- "Chat theories" are words someone once used to fill the gaps. Viewers present them as certainties and argue about them. They are only theories.
- Valtteri does not know the diary until the chat brings it. He may laugh at a theory or find it interesting, but he never says which word hides in a gap: the diary stays unsaid.
- The gaps hide words that really occur in the recording, so Valtteri does NOT compare a gap with the recording. Answering a theory, he gives no concrete detail from the recording (a name, number, date, place) as fitting the gap, does not list candidates and never says the recording answers it. He may judge only the mood and the image of a theory. He talks about facts of the recording when he discusses the recording, not in reply to a fragment of the diary.
- The same goes for the chat: a viewer may insist on a theory but never "solves" a gap with a fact from the recording.
- The diary attributes nothing to real people that the recording does not say, and the theories are guesses, not accusations."""


# ==========================================
# Prompt
# ==========================================

def prompt_path(explicit):
    """--prompt > helsinki_reacts.md (user copy) > helsinki_reacts.example.md."""
    if explicit:
        return Path(explicit)
    return PROMPT_LOCAL if PROMPT_LOCAL.is_file() else PROMPT_DEFAULT


def load_prompt(path):
    """Prompt text without HTML comments; None when the file is missing or empty."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return None
    text = _HTML_COMMENT.sub("", text).strip()
    return text or None


def stream_language(cli_lang, cfg):
    """Language code of the stream: --lang > reacts_lang > ui_lang. None = unknown code."""
    code = (cli_lang or cfg.get("reacts_lang") or UI_LANG or "en").strip().lower()
    return code if code in LANGUAGE_NAMES else None


def language_block(code):
    if code == "fi":
        return LANGUAGE_FINNISH
    return LANGUAGE_TRANSLATED.format(language=LANGUAGE_NAMES[code])


# ==========================================
# Input: export folder or file
# ==========================================

class _HtmlText(html.parser.HTMLParser):
    """Paragraph text of accessible_text.html, without <title> and headings."""

    SKIP = {"title", "h1", "h2", "h3", "h4", "h5", "h6", "script", "style"}
    BLOCKS = {"p", "li", "div", "br"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCKS:
            self.parts.append("\n\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in self.BLOCKS:
            self.parts.append("\n\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_to_text(path):
    parser = _HtmlText()
    parser.feed(path.read_text(encoding="utf-8-sig"))
    paragraphs = (" ".join(p.split()) for p in "".join(parser.parts).split("\n\n"))
    return "\n\n".join(p for p in paragraphs if p)


def resolve_source(arg):
    """(source path, name, export folder name or None), or None when nothing matches.

    An existing file wins, so a plain .txt keeps working. Otherwise a bare folder name
    in export_results/ with accessible_text.html.
    """
    path = Path(arg)
    if path.is_file():
        folder = path.parent.name if path.name == HTML_NAME else None
        return path, folder or path.stem, folder
    folder_dir = EXPORT_DIR / arg
    if folder_dir.is_dir() and (folder_dir / HTML_NAME).is_file():
        return folder_dir / HTML_NAME, folder_dir.name, folder_dir.name
    return None


def read_source(path):
    if path.suffix.lower() in (".html", ".htm"):
        return html_to_text(path)
    return path.read_text(encoding="utf-8-sig").strip()


def title_from_name(name):
    """Underscores to spaces; hyphens stay, they belong to the title."""
    return " ".join(name.replace("_", " ").split())


# ==========================================
# Book of the Unsaid bridge (--kirja)
# ==========================================

def _load_json(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _strip_audio_tags(line):
    """Drops ElevenLabs audio tags ([whispers] etc.) from the start of a fragment."""
    line = line.strip()
    while line.startswith("[") and "]" in line:
        line = line[line.index("]") + 1:].strip()
    return line


def parse_kirja_entries(text):
    """Entries of the Book: {id, folder, katla, fragments} from the `<!-- kirja:... -->` line."""
    entries = []
    for section in text.split("\n## ")[1:]:
        lines = section.splitlines()
        meta = {}
        for line in lines:
            s = line.strip()
            if s.startswith("<!-- kirja:"):
                for part in s[len("<!-- kirja:"):].rstrip("->").strip().split(" | "):
                    key, _, value = part.partition("=")
                    meta[key.strip()] = value.strip()
                break
        if not meta.get("id"):
            continue
        katla, fragments = "", []
        for line in lines:
            s = line.strip()
            if s.startswith("**KATLA**"):
                katla = s.split(":", 1)[-1].strip()
            elif s.startswith(">"):
                fragment = _strip_audio_tags(s.lstrip(">").strip())
                if fragment:
                    fragments.append(fragment)
        entries.append({"id": meta["id"], "folder": meta.get("folder", ""),
                        "katla": katla, "fragments": fragments})
    return entries


def kirja_bridge(folder):
    """(text for the model, entries, theories) for one export folder.

    Gaps in the Book text appear in the order of the OPEN gap numbers of the key
    (gaps removed as obvious are already written into the text). Missed blind guesses
    come from `_kirja_tyotila/<id>/guesses.json`. The answers of the key never leave
    this function: only the gap NUMBERS are read from it.
    """
    if not folder or not KIRJA.is_file():
        return "", 0, 0
    avain = _load_json(KIRJA_AVAIN)
    blocks, theories_total = [], 0
    for entry in parse_kirja_entries(KIRJA.read_text(encoding="utf-8-sig")):
        if entry["folder"] != folder:
            continue
        open_gaps = sorted((avain.get(entry["id"], {}).get("open") or {}), key=int)
        guesses = _load_json(KIRJA_TYOTILA / entry["id"] / "guesses.json").get("guesses") or {}
        body = "\n".join(entry["fragments"])
        theories = []
        if body.count(GAP) == len(open_gaps):
            pieces = body.split(GAP)
            out = [pieces[0]]
            for k, (gap_no, piece) in enumerate(zip(open_gaps, pieces[1:]), start=1):
                out += [f"{GAP}({k})", piece]
                guess = str(guesses.get(gap_no) or "").strip()
                if guess:
                    theories.append(f"({k}) {guess}")
            body = "".join(out)
        else:
            print(t(UI_LANG, "reacts.warn_kirja_mismatch", id=entry["id"],
                    gaps=body.count(GAP), keys=len(open_gaps)), file=sys.stderr)
        block = [f"KATLA: {entry['katla']}", "VIENO:", body]
        if theories:
            block += ["Chat theories:"] + theories
        theories_total += len(theories)
        blocks.append("\n".join(block))
    return "\n\n---\n\n".join(blocks), len(blocks), theories_total


def build_user_message(source, lang_code, use_kirja):
    """(message, entries, theories). Data first, then the tool's own instructions."""
    path, name, folder = source
    parts = [f"Recording title: {title_from_name(name)}",
             f"Recording text:\n<<<\n{read_source(path)}\n>>>"]
    entries = theories = 0
    if use_kirja:
        bridge, entries, theories = kirja_bridge(folder)
        if bridge:
            parts.append(f"Entry from Sanomattomien kirja:\n<<<\n{bridge}\n>>>")
            parts.append(KIRJA_RULES)
    parts.append(language_block(lang_code))
    return "\n\n".join(parts), entries, theories


# ==========================================
# Model call
# ==========================================

def read_config():
    for name in ("config.json", "config.ini"):
        p = ROOT / name
        if p.is_file():
            return _load_json(p)
    return {}


def unique_output_path(name):
    path = STREAMS_DIR / f"{name}.md"
    counter = 2
    while path.exists():
        path = STREAMS_DIR / f"{name}_{counter}.md"
        counter += 1
    return path


def process(source, system_prompt, llm, args, lang_code):
    """True when the stream was saved."""
    settings, client = llm
    message, entries, theories = build_user_message(source, lang_code, args.kirja)
    name = source[1]
    kirja = t(UI_LANG, "reacts.kirja_info", entries=entries, theories=theories) if entries else ""
    print(t(UI_LANG, "reacts.processing", name=name, provider=settings.provider,
            model=settings.model, kirja=kirja))
    if args.kirja and not entries:
        print(t(UI_LANG, "reacts.info_no_kirja", name=name))
    resp = llm_klient.chat_text(
        client, settings,
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": message}],
        TEMPERATURE, UI_LANG, effort=args.effort)

    choice = resp.choices[0] if getattr(resp, "choices", None) else None
    msg = getattr(choice, "message", None)
    content = (getattr(msg, "content", None) or "").strip()
    finish = getattr(choice, "finish_reason", None)
    usage = getattr(resp, "usage", None)

    if len(content) < args.min_chars:
        print(t(UI_LANG, "reacts.err_rejected", chars=len(content), min=args.min_chars,
                finish=finish), file=sys.stderr)
        print(content or t(UI_LANG, "reacts.empty_reply"), file=sys.stderr)
        return False
    if finish == "length":
        print(t(UI_LANG, "reacts.warn_truncated"), file=sys.stderr)

    STREAMS_DIR.mkdir(parents=True, exist_ok=True)
    out = unique_output_path(name)
    out.write_text(content + "\n", encoding="utf-8")
    print(t(UI_LANG, "reacts.ok_saved", path=out.relative_to(ROOT), chars=len(content),
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None)))
    return True


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):  # a redirected stream (tests, pipes) may lack it
            stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=t(UI_LANG, "reacts.help_desc"))
    parser.add_argument("sources", nargs="+", help=t(UI_LANG, "reacts.help_sources"))
    parser.add_argument("--prompt", help=t(UI_LANG, "reacts.help_prompt"))
    parser.add_argument("--lang", help=t(UI_LANG, "reacts.help_lang"))
    parser.add_argument("--kirja", action="store_true", help=t(UI_LANG, "reacts.help_kirja"))
    parser.add_argument("--provider", help=t(UI_LANG, "reacts.help_provider"))
    parser.add_argument("--model", help=t(UI_LANG, "reacts.help_model"))
    parser.add_argument("--effort", default=DEFAULT_EFFORT,
                        help=t(UI_LANG, "reacts.help_effort", default=DEFAULT_EFFORT))
    parser.add_argument("--min-chars", type=int, default=DEFAULT_MIN_CHARS,
                        help=t(UI_LANG, "reacts.help_min_chars", default=DEFAULT_MIN_CHARS))
    parser.add_argument("--dry-run", action="store_true", help=t(UI_LANG, "reacts.help_dry_run"))
    args = parser.parse_args(argv)

    cfg = read_config()
    lang_code = stream_language(args.lang, cfg)
    if lang_code is None:
        print(t(UI_LANG, "reacts.err_lang", code=args.lang or cfg.get("reacts_lang"),
                known=", ".join(LANGUAGE_NAMES)))
        return 1

    resolved, missing = [], []
    for arg in args.sources:
        found = resolve_source(arg)
        if found:
            resolved.append(found)
        else:
            missing.append(arg)
    if missing:
        print(t(UI_LANG, "reacts.err_not_found", names=", ".join(missing), html=HTML_NAME))
        return 1

    path = prompt_path(args.prompt)
    system_prompt = load_prompt(path)
    if system_prompt is None:
        print(t(UI_LANG, "reacts.err_prompt", path=path))
        return 1
    print(t(UI_LANG, "reacts.info_prompt", path=path))
    print(t(UI_LANG, "reacts.info_lang", language=LANGUAGE_NAMES[lang_code]))

    if args.dry_run:
        for source in resolved:
            message, entries, theories = build_user_message(source, lang_code, args.kirja)
            print(message)
            print(t(UI_LANG, "reacts.dry_summary", name=source[1], chars=len(message),
                    entries=entries, theories=theories))
        return 0

    try:
        settings = llm_klient.resolve(cfg, UI_LANG, provider_key="reacts_llm_provider",
                                      provider=args.provider,
                                      model=args.model or cfg.get("reacts_model"))
        llm = (settings, llm_klient.build_client(settings, UI_LANG))
    except llm_klient.LLMConfigError as error:
        print(error)
        return 1
    print(t(UI_LANG, "llm.info_provider", provider=settings.provider, model=settings.model,
            endpoint=settings.endpoint))
    print(t(UI_LANG, "reacts.info_privacy", count=len(resolved), endpoint=settings.endpoint))

    saved = 0
    for source in resolved:
        try:
            if process(source, system_prompt, llm, args, lang_code):
                saved += 1
        except Exception as error:  # one failed recording does not stop the others
            print(t(UI_LANG, "reacts.err_call", name=source[1], error=error), file=sys.stderr)
    print(t(UI_LANG, "reacts.done", ok=saved, total=len(resolved)))
    return 0 if saved == len(resolved) else 1


if __name__ == "__main__":
    sys.exit(main())
