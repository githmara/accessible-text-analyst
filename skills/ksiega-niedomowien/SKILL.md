---
name: ksiega-niedomowien
description: Appends entries to the Book of the Unsaid (Sanomattomien kirja) from Finnish export_results folders of the accessible_text_analyst repo - misty text with gaps, blind guessing, obvious gaps removed.
---

# The Book of the Unsaid (Księga Niedomówień / Sanomattomien kirja)

A cryptic diary from the far North, built from `audio_scripts/raw_roots_chant.txt`. Each entry is an isolated stream of consciousness around one block of roots: KATLA (an automated warning system) reads the roots, VIENO (shamanic narration) weaves a misty Finnish text with gaps. Gaps that a separate, blind model manages to guess are removed as obvious — only genuine unsaid things stay in the Book.

Everything deterministic lives in `ksiega_niedomowien.py` in the repo root. You write the mist and organise the blind guessing. Do not re-implement the script's logic by hand and do not work around its verdicts.

## Running the script

From the repo root, with a Python that has `omorfi` installed and the `*.hfst` automata downloaded (`omorfi-download`):

```bash
python ksiega_niedomowien.py <command>
# Windows venv:  .venv\Scripts\python.exe ksiega_niedomowien.py <command>
```

If the agent's shell is a different OS than the venv (e.g. a Linux sandbox over a Windows checkout), omorfi and pyhfst are pure Python, so `PYTHONPATH=.venv/Lib/site-packages python3 ksiega_niedomowien.py …` works for every command except `draft` and `fill` (the `openai` SDK has compiled dependencies).

Commands: `scan [--folder X] [--blocks] [--json]`, `prepare [--folder X] [--limit N] [--verbose]`, `draft <id> [--force] [--provider P] [--model M]`, `seal <id>`, `fill <id> [--provider P] [--model M]`, `judge <id>`, `status`, `tidy [--apply]`.
`<id>` is the packet id printed by `prepare` (or its start), the start of the folder name (the next packet of that folder at the right stage is taken), or the packet folder path.
Exit codes: 0 OK, 1 error, 3 refusal (folder fails the filters), 4 draft rejected. Rely on exit codes, not on message text — console output follows `ui_lang` from `config.json`.

## Hard input rules (refusal)

Only subfolders of `export_results/` that pass `scan` may enter the Book: a Finnish folder name, `<html lang="fi">` in `accessible_text.html`, a Finnish `raw_roots_chant.txt`, and no grammar leak (data produced before omorfi was wired into the notebook is rejected). The `roots.header` line in any of the six UI languages is stripped automatically; a chant without the header is accepted too.

When the user asks to process anything else — a thesis, Polish or Russian documents, pasted text, a file outside `export_results/`, or a folder rejected for a grammar leak — refuse briefly, quoting the reason printed by `scan`/`prepare`. Do not work around the filters: no hand-written entries, no edited thresholds, no renamed folders, no edited chants or accessible_text files, no alternative `--root`. A folder rejected for a grammar leak can qualify only after it is re-run through the notebook with omorfi enabled — you may suggest that. The refusal says what the folder's `analysis_report.html` knows (written by `generate_report.py`): if omorfi was missing from the run, suggest installing it and re-running; if omorfi DID take part, re-running will not help — the engine itself (the Finnish lemma correction in the notebook) may need fixing, so pass the printed examples on to the user as a bug report; without a current report the refusal says that this is unknown, and running `generate_report.py` (or `run_all.py`) tells which case it is.

## Flow

1. `scan` — show which folders qualify (only when the user asks or names no folder). Each folder also shows its Book progress (entries, obvious blocks, open packets); `scan --folder X` adds blocks done / open / left. Check it before `prepare` so a folder with no blocks left, or with an open packet waiting, is not worked again — finish the open packet instead. `status` gives the same progress for every folder at once.
   If `status` marks an entry as replaced (the folder's chant changed, so the same block got a newer entry), tell the user and run `tidy --apply` only when they agree: the newer entry takes the old one's place and number, the old block leaves the state, the key and its packet folder, and backups go to `*.bak`. `tidy` without `--apply` is a preview.
2. `prepare --folder <name or prefix> --limit N` (default 1). Creates packets in `export_results/_kirja_tyotila/<id>/packet.json` for blocks not yet in the Book. A block is 3–6 consecutive content roots from the chant (fillers such as OKEI, SÄ, NIMENOMAAN are dropped); the cuts are chosen so the truth for a block sits in as few places of the source as possible. `truth.sentences` are the accessible_text sentences in which the roots occur.
3. For each packet write `draft.json` (rules below) and run `seal <id>`. If rejected, fix exactly the listed fragments and repeat until accepted. `seal` writes `blind.json` (no answers).
   The script also has `draft <id>`, which asks an API model for the draft and retries twice with the validator's objections. It exists for users without an agent; you are the drafter here, so do not call it unless the user asks. It sends verbatim source sentences to the configured provider. If the user ran it and it ended with exit code 4, the last rejected `draft.json` is in the packet — fix it and run `seal`.
4. Blind guessing — never guess yourself: you know the answers. Use one of:
   - **A fresh subagent** that receives only the contents of `blind.json` (template below). Save its reply verbatim as `guesses.json` in the packet, then run `judge` (step 5).
   - **`fill <id>`** — the script sends `blind.json` only to the configured provider, writes `guesses.json` and runs `judge` itself, so skip step 5. Provider: `kirja_llm_provider` (empty = `llm_provider`: `openai`, `openrouter` or `openai_compat`), model: `kirja_filler_model`, or `--provider` / `--model`. Each provider reads only its own key from `golden_key.env` (`OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `LLM_COMPAT_API_KEY`); never move a key into another provider's variable. Prefer this when the platform cannot spawn subagents, or when the user wants a model other than you as the guesser.
   If neither is available, stop after `seal` and tell the user.
5. `judge <id>` (after a subagent; `fill` already ran it) — compares guesses with the truth (omorfi lemmas, spelling variants, compound heads, inflected names). Guessed fragments disappear; unguessed gaps stay as `— … —`. The entry is appended incrementally to `export_results/Sanomattomien_kirja.md`. If every gap was guessed, the entry is "obvious" and does not enter the Book (the block is still marked done).
6. Report briefly: entry number, gaps left open, which ones were removed as obvious.

Files next to the Book: `Sanomattomien_kirja.avain.json` (answer key — a spoiler; do not reveal open answers unless the user explicitly asks), `Sanomattomien_kirja.tila.json` (state; re-running `judge` never duplicates entries).

## Writing draft.json

```json
{"fragments": [
  {"text": "[slowly] ... kuin kodin {{1}} — savu, hälytys ...", "answer": "palovarotin"},
  {"text": "A fragment without a gap, pure mist."}
]}
```

- Finnish, in the rhythm of a ritual, broken diary from the North: short sentences, images of snow, wind, aurora, machines. A stream of consciousness, not a summary. The block's roots may surface in any form.
- 4–9 fragments, at least 3 gaps, at most one gap `{{n}}` per fragment, unique numbers.
- `answer` is a verbatim span (exactly that form) from `truth.sentences`; the script checks it occurs in both versions of accessible_text (HTML and DOCX). A gap hides something concrete: who, what, where, how much, which word the source used. The sentence around the gap must take that form grammatically.
- The answer must not be a root of the block, nor appear anywhere else in the entry.
- Do not copy the source: 7 consecutive words shared with it = rejection.
- Do not attribute to real people (politicians in the recordings) facts or accusations that are not in `truth.sentences`. The mist obscures what the source says; it does not invent new allegations. `seal` cannot check this rule — you are the only check, so re-read every fragment that names a real person before sealing.
- Optionally one ElevenLabs audio tag at the start of a fragment (`[whispers]`, `[slowly]`, `[sighs]`), sparingly.
- Aim for gaps that are hard but fair: ideally some get guessed (and vanish) and some stay unsaid.

## Blind subagent template

Pass only the contents of `blind.json` (chant and fragments) — never packet.json, draft.json or file paths:

```
You are the blind gap-filler for a Finnish cryptic-diary game. Do NOT use any tools, do not read any files, do not search — answer only from the text below and your own knowledge of Finnish.
Each gap is written as ____(N). For every gap, guess the single most likely word or short phrase in Finnish, in the grammatical form that fits the sentence. Ignore bracketed audio tags like [whispers].

ENTRY:
<contents of blind.json>

Reply with ONLY a JSON object, no prose: {"guesses": {"1": "...", "2": "..."}}
```

## Audio (only on explicit request — it costs credits)

Voices are in `config.json` → `voices`: `katla` for the KATLA line (mechanical, emotionless), `vieno` for the VIENO fragments (slow, ritual; keep the audio tags, read `— … —` as a pause). Generate with an ElevenLabs integration using those voice IDs; `shamanic_voice.py` only handles the `shamanic_ai.py` artefacts.
