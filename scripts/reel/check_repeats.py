#!/usr/bin/env python3
"""scripts/reel/check_repeats.py — mandatory check before every render.

    python3 check_repeats.py [--asset clip]

Whisper-on-the-isolated-take (the private skill's approach) doesn't exist
here: Lana transcribes the whole file once. What it loses is per-take
isolation, so a false start folded into a single `speech` region ("and if
you are— and if you are a developer") won't show up as two different takes
the way it used to — it has to be caught by looking for a repeated n-gram
*inside* one region's own words.

For every region in lana/<asset->silence.json's `speech[]` (asset defaults to
"clip"; see save_result.py --asset), tokens are normalized (accent-stripped,
lowercased, alnum-only) and every n-gram (n >= 3) is compared against every
later position in the SAME region: if the same n-gram reappears with its
second start less than 4 s after the first, that's a false start.

Prints `!! REPEAT in take <i> at <ms>: "<tokens>" -> start the line at <ms>`
for each hit (nothing with `!!` goes to render, per the skill's rule) and
exits 1 if there is at least one. No cache, no ffmpeg, no whisper: this is a
pure re-read of already-transcribed data.
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import io as _io  # noqa: E402
from _lib import project as _project  # noqa: E402

MATCH_PAD_MS = 30
MIN_NGRAM = 3
MAX_GAP_MS = 4000


def _norm(text: str) -> str:
    """Duplicated from takes.py on purpose — see that file's docstring."""
    s = unicodedata.normalize("NFD", text.lower())
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]", "", s)


def words_in_region(words: list[dict], a: int, b: int) -> list[dict]:
    return [w for w in words if w["s"] >= a - MATCH_PAD_MS and w["e"] <= b + MATCH_PAD_MS]


def _common_run_len(tokens: list[str], i: int, j: int) -> int:
    """Length of the longest common run starting at i and j (an LCP of the
    two token suffixes) — NOT a fixed-width slice comparison: two repeats
    are rarely the exact same length as some arbitrary window, so this
    grows the match as far as it actually goes."""
    n = 0
    limit = min(len(tokens) - i, len(tokens) - j)
    while n < limit and tokens[i + n] == tokens[j + n]:
        n += 1
    return n


def find_repeats_in_region(region_words: list[dict]) -> list[tuple[int, int, str]]:
    """Returns a list of (first_start_ms, second_start_ms, ngram_text) for
    every repeated n-gram (n >= MIN_NGRAM) whose second occurrence starts
    less than MAX_GAP_MS after the first."""
    tokens = [_norm(w["t"]) for w in region_words]
    hits = []
    claimed = set()
    for i in range(len(tokens)):
        if i in claimed:
            continue
        for j in range(i + 1, len(tokens)):
            n = _common_run_len(tokens, i, j)
            if n < MIN_NGRAM:
                continue
            gap = region_words[j]["s"] - region_words[i]["s"]
            if gap < 0 or gap >= MAX_GAP_MS:
                continue
            ngram_text = " ".join(w["t"] for w in region_words[i:i + n])
            hits.append((region_words[i]["s"], region_words[j]["s"], ngram_text))
            claimed.update(range(i, i + n))
            break
    return hits


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Detect false-start repeats within measured speech regions.")
    parser.add_argument("--asset", default="clip")
    args = parser.parse_args(argv)

    project_dir = _project.find_project()
    lana_dir = project_dir / "lana"
    suffix = "" if args.asset == "clip" else f"{args.asset}."
    silence_path = lana_dir / f"{suffix}silence.json"
    transcript_path = lana_dir / f"{suffix}transcript.json"
    if not silence_path.is_file() or not transcript_path.is_file():
        _io.fail(f"missing {silence_path} or {transcript_path}", code=2)

    silence = _io.read_json(silence_path)
    transcript = _io.read_json(transcript_path)
    words = transcript.get("words") or []

    bad = 0
    regions = silence.get("speech") or []
    for i, region in enumerate(regions):
        region_words = words_in_region(words, int(region[0]), int(region[1]))
        for first_ms, second_ms, ngram_text in find_repeats_in_region(region_words):
            print(f'  !! REPEAT in take {i} at {second_ms}: "{ngram_text}" -> start the line at {second_ms}')
            bad += 1

    print(f"{args.asset}: {len(regions)} regions reviewed, {bad} repeats")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
