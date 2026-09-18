#!/usr/bin/env python3
"""scripts/reel/styles.py — the style questionnaire. Never assume "like last
time": every element is shown and confirmed on every run, even for a repeat
creator — a preference from months ago may not hold today.

    python3 styles.py questions [answers.json]
    python3 styles.py remember answers.json

`questions` prints a JSON list of rounds ready for `AskUserQuestion` (<= 4
options each): text (captions/hook text/hook style/closing), image
(titles position/transitions/cards/boards), rhythm & brand (silence
tightness/punch/SFX kit), and typography (font group, then the pairs in that
group — Google Fonts from `_lib.fonts.FONT_PAIRS`, PLUS every `kind="font"`
entry in lana/caps.library.json shown with its `license` right in the label,
e.g. "Sequel Sans Bold (library · license: unknown)" — no filtering: every
shared-library font gets offered like any other, license and all). There is
no music round (the private skill's music catalog file is not part of the
public skill). If `answers.json` (or `~/.reel/last-style.json`) exists, each
option that matches the previous answer is annotated "(last time)" in its
description — shown, never assumed: the agent still asks.

The answers this prints are meant to be copied into CONFIG["style"] in
videoconfig.py by the agent, together with whatever
line indices the agent decides for punch/bw/glitch/titles from the actual
SEL — this script only asks the QUESTIONS, it doesn't touch videoconfig.py.

`remember answers.json` merges those answers into ~/.reel/last-style.json so
a future run's "(last time)" hints reflect them.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import fonts as _fonts  # noqa: E402
from _lib import io as _io  # noqa: E402
from _lib import project as _project  # noqa: E402

LAST_STYLE_PATH = Path("~/.reel/last-style.json").expanduser()

# element key -> {question, header, opts: [(id, label, description)], multi: bool}
CATALOG = {
    "captions": {
        "q": "How should captions look?", "header": "Captions",
        "opts": [
            ("bold", "Bold word-by-word", "Uppercase, the spoken word highlighted, thick outline."),
            ("none", "No captions", "Only titles and cards; the audio carries it."),
        ],
    },
    "hook_text": {
        "q": "What does the hook text (the first ~4s) say?", "header": "Hook · text",
        "opts": [
            ("first_line", "The script's first line", "Uppercase, exactly as spoken."),
            ("custom", "I'll write it", "Pick 'Other' and give the exact text."),
        ],
    },
    "hook_style": {
        "q": "What style does that hook text enter with?", "header": "Hook · style",
        "opts": [
            ("banner", "Angled banner", "A colored block with a small tag underneath; snaps in on frame 0."),
            ("title", "Big word-by-word title", "Centered, each word lands on its own beat."),
            ("lower_third", "News lower third", "A colored block plus a dark headline wiping in from the left, ~3.6s."),
            ("none", "No hook text", "Just the camera."),
        ],
    },
    "closing": {
        "q": "How does the video close?", "header": "Closing",
        "opts": [
            ("plate", "Dark plate + CTA title", "The camera dims; the call-to-action title sits over it."),
            ("title_only", "Just the CTA title over camera", "No dimming."),
        ],
    },
    "titles": {
        "q": "Where do the big titles sit?", "header": "Titles",
        "opts": [
            ("centered", "Centered", "Over the chest/face; works if you're far from the camera."),
            ("top", "Top", "Shifted up so a close-up face isn't covered."),
        ],
    },
    "transitions": {
        "q": "Which transitions can be used? (pick any)", "header": "Transitions", "multi": True,
        "opts": [
            ("crosswarp", "Crosswarp", "The two shots stretch and blend — the cut disappears. For section changes."),
            ("swish", "Whip pan", "A horizontal blur pan hides the cut inside the motion."),
            ("glitch", "Glitch", "RGB split + a white flash — one strong hit, not more than two per video."),
            ("cuts", "Hard cuts only", "Clean jump cuts."),
        ],
    },
    "cards": {
        "q": "Cards when a keyword is said?", "header": "Cards",
        "opts": [
            ("pop", "Pop with a logo/icon", "Springs in on the word, ~2.4s, alternates top/bottom."),
            ("stack", "Stack (lists)", "Cards pile up and leave together when the list ends."),
            ("none", "No cards", ""),
        ],
    },
    "boards": {
        "q": "Which full-screen boards can appear? (pick any; the script marks where)", "header": "Boards", "multi": True,
        "opts": [
            ("chalk", "Chalk board", "Strokes and handwritten words that land on the word that names them."),
            ("image", "Screenshot with a marker", "A tweet/contract/diagram with a red box drawn on the named word."),
            ("band", "Split screen", "Material on top, you at the bottom; captions live in the top band."),
        ],
    },
    "silence": {
        "q": "How tight should the silences be?", "header": "Silences",
        "opts": [
            ("soft", "Soft", "Gaps > 350ms tighten to 200ms; a more reflective pace."),
            ("normal", "Normal", "Gaps > 220ms tighten to 120ms; reel pace."),
            ("aggressive", "Aggressive", "Gaps > 200ms tighten to 100ms; no air."),
        ],
    },
    "punch": {
        "q": "Punch zoom when a line starts?", "header": "Punch",
        "opts": [
            ("hooks", "Hooks only", "Hook, turns, and closing; the agent proposes which lines."),
            ("most", "Most lines", "Every line outside boards; aggressive."),
            ("never", "Never", ""),
        ],
    },
    "sfx_kit": {
        "q": "Which SFX kit?", "header": "SFX",
        "opts": [
            ("full", "Full", "Every SFX pack sound is available for the agent to use."),
            ("minimal", "Minimal", "Only whooshes on transitions and one hit on the hook."),
            ("mute", "None", "No SFX."),
        ],
    },
}

FONT_GROUP_LABELS = {
    "bold": "Bold", "editorial": "Editorial", "geometric": "Geometric",
    "rounded": "Rounded", "script": "Script",
}

# _lib.fonts.FONT_GROUPS has 5 real groups (matching Fonts.tsx's FONT_GROUPS
# exactly). Every AskUserQuestion round is capped at <= 4 options,
# so the font_group QUESTION combines these two into one honestly-labeled
# option ("Geometric & Rounded") rather than falsifying either group's real
# identity in _lib/fonts.py (that would just move the divergence from "the
# question" to "the data", which is worse — a reviewer diffing
# _lib/fonts.py against Fonts.tsx would see a lie, not a UI constraint).
# pairs_for_group_answer() below resolves the combined id back to real pairs
# from BOTH real groups; every other group is asked about on its own.
GROUP_QUESTION_MERGE = ("geometric", "rounded")


def font_group_question_options() -> list[dict]:
    merge_into, merge_from = GROUP_QUESTION_MERGE
    opts = []
    for g in _fonts.FONT_GROUPS:
        if g == merge_from:
            continue  # folded into merge_into's option, handled below
        pairs = list(_fonts.pairs_in_group(g))
        opt_id, label = g, FONT_GROUP_LABELS[g]
        if g == merge_into:
            pairs += _fonts.pairs_in_group(merge_from)
            opt_id = f"{merge_into}+{merge_from}"
            label = f"{FONT_GROUP_LABELS[merge_into]} & {FONT_GROUP_LABELS[merge_from]}"
        opts.append({"id": opt_id, "label": label, "description": ", ".join(pairs)})
    return opts


def pairs_for_group_answer(answer: str) -> list[str]:
    """Resolves a font_group answer — a real group id, or the merged
    "geometric+rounded" combo id from font_group_question_options() — back
    to real pair ids. Each pair's own `group` in _lib/fonts.py is never
    touched by the question-level merge."""
    pairs: list[str] = []
    for g in (answer or "bold").split("+"):
        pairs.extend(_fonts.pairs_in_group(g))
    return pairs


def load_answers(path: str | None) -> dict:
    if path and Path(path).is_file():
        return _io.read_json(path)
    if LAST_STYLE_PATH.is_file():
        return _io.read_json(LAST_STYLE_PATH)
    return {}


def annotate_last_time(opts: list[tuple[str, str, str]], last_value) -> list[dict]:
    out = []
    for opt_id, label, desc in opts:
        is_last = (opt_id == last_value) or (isinstance(last_value, list) and opt_id in last_value)
        out.append({
            "id": opt_id, "label": label,
            "description": f"{desc} (last time)".strip() if is_last and desc else (desc or ("(last time)" if is_last else "")),
        })
    return out


def library_font_options(project_dir: Path) -> list[dict]:
    caps_path = project_dir / "lana" / "caps.library.json"
    if not caps_path.is_file():
        return []
    data = _io.read_json(caps_path)
    library = data.get("library", data)
    entries = library.get("entries") or []
    opts = []
    for e in entries:
        if e.get("kind") != "font":
            continue
        license_ = e.get("license", "unknown")
        opts.append({
            "id": f"lib:{e['id']}",
            "label": f"{e.get('id')} (library · license: {license_})",
            "description": ", ".join(e.get("tags") or []),
        })
    return opts


def build_questions(project_dir: Path, answers: dict) -> list[dict]:
    rounds = []
    for key, spec in CATALOG.items():
        last_value = answers.get(key)
        opts = annotate_last_time(spec["opts"], last_value)
        rounds.append({
            "key": key, "header": spec["header"], "question": spec["q"],
            "multi": spec.get("multi", False), "options": opts[:4],
        })

    # font group, then the pairs within it (+ library fonts with license shown)
    rounds.append({
        "key": "font_group", "header": "Typography · group", "question": "Which font family group?",
        "multi": False, "options": font_group_question_options(),
    })

    last_group = answers.get("font_group", "bold")
    pair_opts = []
    for pid in pairs_for_group_answer(last_group):
        pair = _fonts.FONT_PAIRS[pid]
        label = f"{pair['primary']['family']} / {pair['secondary']['family']}"
        pair_opts.append({"id": pid, "label": label, "description": ""})
    pair_opts.extend(library_font_options(project_dir))
    rounds.append({
        "key": "fonts_pair", "header": "Typography · pair", "question": f"Which pair in '{last_group}'?",
        "multi": False, "options": pair_opts[:4],
    })

    return rounds


def cmd_questions(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("answers", nargs="?")
    args = parser.parse_args(argv)

    try:
        project_dir = _project.find_project()
    except SystemExit:
        project_dir = Path.cwd()

    answers = load_answers(args.answers)
    rounds = build_questions(project_dir, answers)
    print(json.dumps(rounds, indent=2, ensure_ascii=False))
    return 0


def cmd_remember(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("answers")
    args = parser.parse_args(argv)

    if not Path(args.answers).is_file():
        _io.fail(f"{args.answers} does not exist", code=2)
    new_answers = _io.read_json(args.answers)
    merged = _io.read_json(LAST_STYLE_PATH) if LAST_STYLE_PATH.is_file() else {}
    merged.update(new_answers)
    _io.write_json(LAST_STYLE_PATH, merged)
    _io.eprint(f"remembered -> {LAST_STYLE_PATH}")
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in ("questions", "remember"):
        _io.fail("usage: styles.py {questions [answers.json] | remember answers.json}", code=2)
    cmd, rest = argv[0], argv[1:]
    if cmd == "questions":
        return cmd_questions(rest)
    return cmd_remember(rest)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
