"""helsinki_reacts.py — satirical stream script: Valtteri from Helsinki reacts to a recording.

Input: an export folder (a bare name from `export_results/` or a path to the folder; the
text of its `accessible_text.html` without markup and without ATA's own heading) or any
text file. Output: `export_results/_streams/<name>.md`.

The system prompt lives OUTSIDE the code, because it is where the user decides what the
stream is like: `helsinki_reacts.md` (the user's copy, gitignored) wins over the shipped
`helsinki_reacts.example.md`; `--prompt` points at any other file. HTML comments in the
prompt file are not sent. The script adds only what has to work whatever the prompt says:
the input data, the output language and — with `--kirja` — the Book of the Unsaid bridge.

Stream language: `--lang` > config `reacts_lang` > `ui_lang`. Finnish = the stream itself,
in plain Finnish; any other language = its translation with Finnish interjections.

Provider: llm_klient, `reacts_llm_provider` / `reacts_model` (empty = the global ones);
`--provider` / `--model` override both. Thinking effort: `medium` where the thinking comes
back readable (Claude via OpenRouter), `low` elsewhere, unless `--effort` says otherwise.
Paid API: the text of every recording leaves the machine, and the script says so before
the first call. Everything is read and checked BEFORE that call, so a broken input costs
nothing.
"""

import argparse
import html.parser
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import llm_klient
from shamanic_locale import LANGUAGE_NAMES, t

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

EFFORTS = ("low", "medium", "high")
TEMPERATURE = 1.0
# A full stream is several thousand characters; a refusal is a few dozen.
DEFAULT_MIN_CHARS = 1500
# A theory sharing a word stem this long with a hidden answer is withheld (audit 2.1.0, #1).
STEM = 5

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
- The entry is material for the CHAT, not for Valtteri. Viewers bring it to the stream: they quote short fragments (the gaps stay "— … —"), link them to the recording and argue about what the images mean. Two or three fragments in the whole stream are enough. Fragments are quoted in the language of the script; a short Finnish original next to the translation is allowed.
- "Chat theories" are words someone once used to fill the gaps. Viewers present them as certainties and argue about them. They are only theories.
- Valtteri does not know the diary until the chat brings it. He may laugh at a theory or find it interesting, but he never says which word hides in a gap: the diary stays unsaid.
- The gaps hide words that really occur in the recording, so Valtteri does NOT compare a gap with the recording. Answering a theory, he gives no concrete detail from the recording (a name, number, date, place) as fitting the gap, does not list candidates and never says the recording answers it. He may judge only the mood and the image of a theory. He talks about facts of the recording when he discusses the recording, not in reply to a fragment of the diary.
- The same goes for the chat: a viewer may insist on a theory but never "solves" a gap with a fact from the recording.
- The diary attributes nothing to real people that the recording does not say, and the theories are guesses, not accusations."""


# ==========================================
# Configuration (one place: the repo root, like read_config of the Book)
# ==========================================

def _load_json(path, warn_lang=None):
    """Dict from a JSON file. Missing file -> {}. Unreadable or not a dict -> {} plus a
    warning (when warn_lang is given), so a broken file is never mistaken for an empty one."""
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        data = None
    if isinstance(data, dict):
        return data
    if warn_lang:
        print(t(warn_lang, "reacts.warn_json_invalid", path=path), file=sys.stderr)
    return {}


def _config_path():
    for name in ("config.json", "config.ini"):
        p = ROOT / name
        if p.is_file():
            return p
    return None


def read_config(warn_lang=None):
    path = _config_path()
    return _load_json(path, warn_lang) if path else {}


def _ui_lang_of(cfg):
    code = str(cfg.get("ui_lang") or "").strip().lower()
    return code if code in LANGUAGE_NAMES else "en"


# The console follows ui_lang from the SAME config the tool reads (audit 2.1.0, #8): reading
# it from the working directory made the console and the stream language differ.
UI_LANG = _ui_lang_of(read_config())


# ==========================================
# Prompt and language
# ==========================================

def prompt_path(explicit):
    """--prompt > helsinki_reacts.md (user copy) > helsinki_reacts.example.md."""
    if explicit:
        return Path(explicit)
    return PROMPT_LOCAL if PROMPT_LOCAL.is_file() else PROMPT_DEFAULT


def load_prompt(path):
    """(prompt text without HTML comments, error key or None)."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return None, "reacts.err_prompt_encoding"
    except OSError:
        return None, "reacts.err_prompt"
    text = _HTML_COMMENT.sub("", text).strip()
    return (text, None) if text else (None, "reacts.err_prompt")


def stream_language(cli_lang, cfg):
    """Language code of the stream: --lang > reacts_lang > ui_lang. None = unknown code."""
    code = (cli_lang or cfg.get("reacts_lang") or UI_LANG or "en").strip().lower()
    return code if code in LANGUAGE_NAMES else None


def language_block(code):
    if code == "fi":
        return LANGUAGE_FINNISH
    return LANGUAGE_TRANSLATED.format(language=LANGUAGE_NAMES[code])


def effort_for(settings, cli_effort):
    """--effort, otherwise medium where the thinking is readable and low elsewhere.

    A rule-heavy creative task needs some thinking; llm_klient forces anything above low
    down to low on models whose thinking cannot be read (paid and never seen), so the
    automatic choice asks for medium only where it is actually sent.
    """
    if cli_effort:
        return cli_effort
    return "medium" if llm_klient.reads_thinking(settings) else "low"


# ==========================================
# Input: export folder or file
# ==========================================

class _HtmlText(html.parser.HTMLParser):
    """Text of an HTML file, one paragraph per block element.

    `skip_heading=True` (ATA's own accessible_text.html) drops its <h1>, which is the
    export's title, not the recording; any other HTML keeps its headings (audit 2.1.0, #7).
    """

    SKIP = {"title", "script", "style"}
    BLOCKS = {"p", "li", "div", "br", "tr", "table", "ul", "ol", "section", "article",
              "blockquote", "header", "footer", "pre", "h1", "h2", "h3", "h4", "h5", "h6"}
    CELLS = {"td", "th"}

    def __init__(self, skip_heading):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0
        self.pre = 0
        if skip_heading:
            self.SKIP = self.SKIP | {"h1"}

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCKS:
            self.parts.append("\n\n")
            self.pre += tag == "pre"
        elif tag in self.CELLS:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in self.BLOCKS:
            self.parts.append("\n\n")
            if tag == "pre":
                self.pre = max(0, self.pre - 1)
        elif tag in self.CELLS:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data.replace("\n", "\n\n") if self.pre else data)


def html_to_text(path):
    parser = _HtmlText(skip_heading=path.name == HTML_NAME)
    parser.feed(path.read_text(encoding="utf-8-sig"))
    paragraphs = (" ".join(p.split()) for p in "".join(parser.parts).split("\n\n"))
    return "\n\n".join(p for p in paragraphs if p)


@dataclass
class Source:
    path: Path
    name: str
    folder: str | None
    shadows_folder: bool = False
    text: str = ""


def _nfc(s):
    return unicodedata.normalize("NFC", s)


def _export_folder(arg):
    """Real export folder for a bare name, matched without case (Windows paths are
    case-insensitive, but the Book is keyed by the real name — audit 2.1.0, #4)."""
    if not EXPORT_DIR.is_dir():
        return None
    wanted = _nfc(arg).casefold()
    for d in EXPORT_DIR.iterdir():
        if d.is_dir() and _nfc(d.name).casefold() == wanted and (d / HTML_NAME).is_file():
            return d
    return None


def resolve_source(arg):
    """Source or None. Order: an existing file, a folder path with accessible_text.html,
    a bare export folder name (audit 2.1.0, #6)."""
    path = Path(arg)
    if path.is_file():
        real = path.resolve()
        folder = real.parent.name if real.name == HTML_NAME else None
        shadows = folder is None and _export_folder(arg) is not None
        return Source(path, folder or path.stem, folder, shadows)
    if path.is_dir() and (path / HTML_NAME).is_file():
        real = path.resolve()
        return Source(real / HTML_NAME, real.name, real.name)
    folder_dir = _export_folder(arg)
    if folder_dir is not None:
        return Source(folder_dir / HTML_NAME, folder_dir.name, folder_dir.name)
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


def _stems(text):
    """Word stems (first STEM letters, casefolded) of the words with 3+ letters."""
    words = "".join(c if c.isalnum() else " " for c in str(text).casefold()).split()
    return {w[:STEM] for w in words if len(w) >= 3}


def kirja_bridge(folder):
    """(text for the model, entries, theories) for one export folder.

    Gaps in the Book text appear in the order of the OPEN gap numbers of the key (gaps
    removed as obvious are already written into the text). Missed blind guesses come from
    `_kirja_tyotila/<id>/guesses.json`. The answers of the key never leave this function:
    they are read only to withhold a theory that shares a word stem with any hidden answer
    of the entry — a near miss would point at the answer (audit 2.1.0, #1). Gap numbers
    run on across the entries of one folder, so every "(n)" is unique in the message.
    """
    if not folder or not KIRJA.is_file():
        return "", 0, 0
    avain = _load_json(KIRJA_AVAIN, UI_LANG)
    blocks, theories_total, k = [], 0, 0
    for entry in parse_kirja_entries(KIRJA.read_text(encoding="utf-8-sig")):
        if _nfc(entry["folder"]) != _nfc(folder):
            continue
        key = avain.get(entry["id"])
        open_map = key.get("open") if isinstance(key, dict) else None
        valid_key = isinstance(open_map, dict) and all(str(g).isdigit() for g in open_map)
        guesses_path = KIRJA_TYOTILA / entry["id"] / "guesses.json"
        guesses = _load_json(guesses_path, UI_LANG).get("guesses") or {}
        if not isinstance(guesses, dict):
            print(t(UI_LANG, "reacts.warn_json_invalid", path=guesses_path), file=sys.stderr)
            guesses = {}
        body = "\n".join(entry["fragments"])
        theories, withheld = [], 0
        if not valid_key:
            print(t(UI_LANG, "reacts.warn_kirja_key_invalid", id=entry["id"]), file=sys.stderr)
        elif body.count(GAP) != len(open_map):
            print(t(UI_LANG, "reacts.warn_kirja_mismatch", id=entry["id"],
                    gaps=body.count(GAP), keys=len(open_map)), file=sys.stderr)
        else:
            answer_stems = set().union(*(_stems(a) for a in open_map.values()))
            pieces = body.split(GAP)
            out = [pieces[0]]
            for gap_no, piece in zip(sorted(open_map, key=int), pieces[1:]):
                k += 1
                out += [f"{GAP}({k})", piece]
                guess = str(guesses.get(gap_no) or "").strip()
                if guess and _stems(guess) & answer_stems:
                    withheld += 1
                elif guess:
                    theories.append(f"({k}) {guess}")
            body = "".join(out)
        if withheld:
            print(t(UI_LANG, "reacts.warn_theories_withheld", id=entry["id"], count=withheld))
        block = [f"KATLA: {entry['katla']}", "VIENO:", body]
        if theories:
            block += ["Chat theories:"] + theories
        theories_total += len(theories)
        blocks.append("\n".join(block))
    return "\n\n---\n\n".join(blocks), len(blocks), theories_total


def build_user_message(source, lang_code, use_kirja):
    """(message, entries, theories). Data first, then the tool's own instructions."""
    parts = [f"Recording title: {title_from_name(source.name)}",
             f"Recording text:\n<<<\n{source.text}\n>>>"]
    entries = theories = 0
    if use_kirja:
        bridge, entries, theories = kirja_bridge(source.folder)
        if bridge:
            parts.append(f"Entry from Sanomattomien kirja:\n<<<\n{bridge}\n>>>")
            parts.append(KIRJA_RULES)
    parts.append(language_block(lang_code))
    return "\n\n".join(parts), entries, theories


# ==========================================
# Output and model call
# ==========================================

def write_unique(name, content, suffix=""):
    """Writes `_streams/<name><suffix>.md`, or `_2`, `_3`… when taken.

    The file is created exclusively, so two parallel runs never pick the same name and
    overwrite a paid result (audit 2.1.0, #9); CRLF from the model is normalised (#10).
    """
    STREAMS_DIR.mkdir(parents=True, exist_ok=True)
    content = content.replace("\r\n", "\n").rstrip("\n") + "\n"
    counter = 1
    while True:
        tail = f"_{counter}" if counter > 1 else ""
        path = STREAMS_DIR / f"{name}{tail}{suffix}.md"
        try:
            with open(path, "x", encoding="utf-8", newline="\n") as f:
                f.write(content)
            return path
        except FileExistsError:
            counter += 1


def _rel(path):
    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path


def process(source, system_prompt, llm, args, lang_code, effort):
    """True when the stream was saved."""
    settings, client = llm
    message, entries, theories = build_user_message(source, lang_code, args.kirja)
    kirja = t(UI_LANG, "reacts.kirja_info", entries=entries, theories=theories) if entries else ""
    print(t(UI_LANG, "reacts.processing", name=source.name, provider=settings.provider,
            model=settings.model, kirja=kirja))
    if args.kirja and not entries:
        print(t(UI_LANG, "reacts.info_no_kirja", name=source.name))
    resp = llm_klient.chat_text(
        client, settings,
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": message}],
        TEMPERATURE, UI_LANG, effort=effort)

    choice = resp.choices[0] if getattr(resp, "choices", None) else None
    msg = getattr(choice, "message", None)
    content = (getattr(msg, "content", None) or "").strip()
    finish = getattr(choice, "finish_reason", None)
    usage = getattr(resp, "usage", None)

    if len(content) < args.min_chars:
        # A rejected reply was paid for: keep it in a file instead of only on the console
        # (audit 2.1.0, #12) — copying a long reply out of a console is hard with a screen reader.
        kept = write_unique(source.name, content or t(UI_LANG, "reacts.empty_reply"), ".rejected")
        print(t(UI_LANG, "reacts.err_rejected", chars=len(content), min=args.min_chars,
                finish=finish, path=_rel(kept)), file=sys.stderr)
        return False
    if finish == "length":
        print(t(UI_LANG, "reacts.warn_truncated"), file=sys.stderr)

    out = write_unique(source.name, content)
    print(t(UI_LANG, "reacts.ok_saved", path=_rel(out), chars=len(content),
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None)))
    return True


def _read_all(sources):
    """Reads every source before any paid call; False when one of them is unusable."""
    ok = True
    for source in sources:
        if source.shadows_folder:
            print(t(UI_LANG, "reacts.info_file_shadows", name=source.name))
        try:
            source.text = read_source(source.path)
        except UnicodeDecodeError:
            print(t(UI_LANG, "reacts.err_source_encoding", name=source.path))
            ok = False
            continue
        except OSError as error:
            print(t(UI_LANG, "reacts.err_call", name=source.path, error=error))
            ok = False
            continue
        if not source.text.strip():
            print(t(UI_LANG, "reacts.err_empty_source", name=source.path))
            ok = False
    return ok


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
    parser.add_argument("--effort", choices=EFFORTS, help=t(UI_LANG, "reacts.help_effort"))
    parser.add_argument("--min-chars", type=int, default=DEFAULT_MIN_CHARS,
                        help=t(UI_LANG, "reacts.help_min_chars", default=DEFAULT_MIN_CHARS))
    parser.add_argument("--dry-run", action="store_true", help=t(UI_LANG, "reacts.help_dry_run"))
    args = parser.parse_args(argv)

    cfg = read_config(UI_LANG)
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
    system_prompt, error_key = load_prompt(path)
    if system_prompt is None:
        print(t(UI_LANG, error_key, path=path))
        return 1
    if not _read_all(resolved):
        return 1
    print(t(UI_LANG, "reacts.info_prompt", path=path))
    print(t(UI_LANG, "reacts.info_lang", language=LANGUAGE_NAMES[lang_code]))

    if args.dry_run:
        for source in resolved:
            message, entries, theories = build_user_message(source, lang_code, args.kirja)
            print(message)
            print(t(UI_LANG, "reacts.dry_summary", name=source.name, chars=len(message),
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
    effort = effort_for(settings, args.effort)
    print(t(UI_LANG, "llm.info_provider", provider=settings.provider, model=settings.model,
            endpoint=settings.endpoint))
    print(t(UI_LANG, "reacts.info_privacy", count=len(resolved), endpoint=settings.endpoint))

    saved = 0
    for source in resolved:
        try:
            if process(source, system_prompt, llm, args, lang_code, effort):
                saved += 1
        except Exception as error:  # one failed recording does not stop the others
            print(t(UI_LANG, "reacts.err_call", name=source.name, error=error), file=sys.stderr)
    print(t(UI_LANG, "reacts.done", ok=saved, total=len(resolved)))
    return 0 if saved == len(resolved) else 1


if __name__ == "__main__":
    sys.exit(main())
