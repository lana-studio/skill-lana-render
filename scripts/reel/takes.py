#!/usr/bin/env python3
"""scripts/reel/takes.py — turn measured speech regions into a table of takes.

    python3 takes.py [--table] [--words <ms>-<ms>] [--asset clip]

Reads lana/silence.json (`speech[]`, from `lana_measure_silence`) and
lana/transcript.json (`words[]`, from `lana_transcribe`) for --asset (default
"clip"; multi-asset projects use lana/<key>.silence.json and
lana/<key>.transcript.json — see save_result.py --asset).

Each `speech` region IS a take (the rule that governs everything: cuts come
from measured audio, text comes from the transcript, never the reverse).
For each region:
  - words = transcript words with `s >= region.start-30` and `e <=
    region.end+30`;
  - text = those words joined;
  - flag "hallucination" if the region has < 200 ms of voice, OR no words
    matched it, OR it is a single word whose duration exceeds the measured
    correction cap `300 + 80*len(word)` ms (build-lana.py's cap — a lone,
    unnaturally long "word" over a short region is faster-whisper stretching
    silence into the last word, not real speech);
  - flag "repeat" if the take's own words contain an internal repeated
    n-gram (n>=2, up to 4) — a false start folded into one region because
    the pause between "and if you are—" and "and if you are a developer" was
    too short to split into two `speech` regions on its own.

Writes lana/takes.json: [{i, asset, start_ms, end_ms, text, words: n,
flag: null|"hallucination"|"repeat"}] and, with --table, prints it in the
SEL-row shape: `("<asset>", <start>, <end>, "<text>", False),`. This one file
covers every asset, not one file per asset: re-running with a different
--asset replaces only that asset's rows in the file, keeping the others — a
multi-episode project runs this once per source and ends up with one
combined table.

--words <a>-<b> prints the transcript words between a and b ms (replaces the
private skill's words.py) instead of building the take table.
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

MIN_VOICE_MS = 200
MATCH_PAD_MS = 30
REPEAT_MIN_WORDS = 2
REPEAT_MAX_NGRAM = 4


def _norm(text: str) -> str:
    """Accent-stripped, lowercased, alnum-only token — duplicated in build.py
    and check_repeats.py on purpose: each script in this family is meant to
    be readable stand-alone, without hunting through a shared helper file."""
    s = unicodedata.normalize("NFD", text.lower())
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]", "", s)


def _word_cap_ms(word: str) -> int:
    return 300 + 80 * len(word)


def load_asset_data(project_dir: Path, asset: str) -> tuple[dict, dict]:
    lana_dir = project_dir / "lana"
    suffix = "" if asset == "clip" else f"{asset}."
    silence_path = lana_dir / f"{suffix}silence.json"
    transcript_path = lana_dir / f"{suffix}transcript.json"
    if not silence_path.is_file():
        _io.fail(f"{silence_path} not found — run save_result.py silence first", code=2)
    if not transcript_path.is_file():
        _io.fail(f"{transcript_path} not found — run save_result.py transcript first", code=2)
    return _io.read_json(silence_path), _io.read_json(transcript_path)


def words_between(words: list[dict], a: int, b: int) -> list[dict]:
    return [w for w in words if w["s"] >= a - MATCH_PAD_MS and w["e"] <= b + MATCH_PAD_MS]


def _common_run_len(tokens: list[str], i: int, j: int, cap: int) -> int:
    """Length of the longest common run starting at i and j, capped at `cap`
    — an LCP of the two token suffixes, NOT a fixed-width slice comparison
    (duplicated from check_repeats.py's _common_run_len on purpose; see that
    file's docstring)."""
    n = 0
    limit = min(len(tokens) - i, len(tokens) - j, cap)
    while n < limit and tokens[i + n] == tokens[j + n]:
        n += 1
    return n


def find_internal_repeat(words: list[dict]) -> int | None:
    tokens = [_norm(w["t"]) for w in words]
    for i in range(len(tokens)):
        for j in range(i + 1, len(tokens)):
            n = _common_run_len(tokens, i, j, REPEAT_MAX_NGRAM)
            if n >= REPEAT_MIN_WORDS:
                return words[j]["s"]
    return None


def flag_for(region_words: list[dict], start_ms: int, end_ms: int) -> str | None:
    duration = end_ms - start_ms
    if duration < MIN_VOICE_MS or not region_words:
        return "hallucination"
    if len(region_words) == 1:
        w = region_words[0]
        if (w["e"] - w["s"]) > _word_cap_ms(w["t"]):
            return "hallucination"
    if find_internal_repeat(region_words) is not None:
        return "repeat"
    return None


def build_takes(silence: dict, transcript: dict, asset: str) -> list[dict]:
    words = transcript.get("words") or []
    takes = []
    for i, region in enumerate(silence.get("speech") or []):
        start_ms, end_ms = int(region[0]), int(region[1])
        region_words = words_between(words, start_ms, end_ms)
        text = " ".join(w["t"] for w in region_words)
        takes.append({
            "i": i, "asset": asset, "start_ms": start_ms, "end_ms": end_ms,
            "text": text, "words": len(region_words),
            "flag": flag_for(region_words, start_ms, end_ms),
        })
    return takes


def print_table(takes: list[dict]) -> None:
    print(f"{'ASSET':<10} {'#':>4} {'START':>9} {'END':>9} {'DUR':>7} {'FLAG':<14} TEXT")
    print("-" * 110)
    for t in takes:
        dur_s = (t["end_ms"] - t["start_ms"]) / 1000
        print(
            f"{t['asset']:<10} {t['i']:>4} {t['start_ms']:>9} {t['end_ms']:>9} "
            f"{dur_s:>6.2f}s {t['flag'] or '':<14} {t['text'][:70]}"
        )
    print(f"\n{len(takes)} takes. Each row is a possible SEL entry:")
    print('  ("<ASSET>", <START>, <END>, "script text", False),')


def print_words_between(transcript: dict, a: int, b: int) -> None:
    for w in words_between(transcript.get("words") or [], a, b):
        print(f"{w['s']:>8} {w['e']:>8}  {w['t']}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Build the take table from measured silence + transcript.")
    parser.add_argument("--table", action="store_true")
    parser.add_argument("--words", metavar="A-B")
    parser.add_argument("--asset", default="clip")
    args = parser.parse_args(argv)

    project_dir = _project.find_project()
    silence, transcript = load_asset_data(project_dir, args.asset)

    if args.words:
        a_str, _, b_str = args.words.partition("-")
        print_words_between(transcript, int(a_str), int(b_str))
        return 0

    takes = build_takes(silence, transcript, args.asset)
    dest = project_dir / "lana" / "takes.json"
    existing = _io.read_json(dest) if dest.is_file() else []
    combined = [t for t in existing if t.get("asset") != args.asset] + takes
    _io.write_json(dest, combined)

    if args.table:
        print_table(takes)
    else:
        n_flagged = sum(1 for t in takes if t["flag"])
        _io.eprint(f"{len(takes)} takes, {n_flagged} flagged -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
