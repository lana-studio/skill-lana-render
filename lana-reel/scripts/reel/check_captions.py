#!/usr/bin/env python3
"""scripts/reel/check_captions.py — mandatory check before every render.

    python3 check_captions.py [--page-ms 1100] [--tail-ms 150] [--old]

No caption page may disappear while one of its own words is still being
spoken. This simulates Captions.tsx's pagination
(`createTikTokStyleCaptions`, `combineTokensWithinMilliseconds=1100`) over
src/plan.json and measures, per page, how long the take keeps talking after
the page dies.

  --old  simulates the OLD fixed cap (end = start + page-ms) instead of the
         current "hold until the last word ends" rule — for measuring how
         much used to get cut, not something the public skill's pipeline
         still does.

A page never crosses a SEL line boundary on its own (there is 0 ms between
one line's last word and the next line's first): pages are grouped by (time
proximity AND same plan.lines[] index), the same thing Captions.tsx does via
`lineStarts`.

Exit 1 if any page is cut mid-word; nothing with `!!` goes to render.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import io as _io  # noqa: E402
from _lib import project as _project  # noqa: E402

PUNCT_ONLY_RE = re.compile(r"[.,;:¿?¡!…\"'()\-]+")
CUT_THRESHOLD_MS = 250


def merge_punctuation(captions: list[dict]) -> list[dict]:
    merged: list[dict] = []
    for w in captions:
        t = w["text"].strip()
        if merged and PUNCT_ONLY_RE.fullmatch(t):
            merged[-1]["text"] += t
            merged[-1]["endMs"] = w["endMs"]
        else:
            merged.append(dict(w))
    return merged


def line_index_of(ms: int, line_starts: list[int]) -> int:
    i = 0
    while i + 1 < len(line_starts) and ms >= line_starts[i + 1]:
        i += 1
    return i if line_starts else 0


def build_pages(captions: list[dict], line_starts: list[int], page_ms: int) -> list[dict]:
    pages: list[dict] = []
    for c in captions:
        line = line_index_of(c["startMs"], line_starts)
        if pages and c["startMs"] - pages[-1]["start"] < page_ms and line == pages[-1]["line"]:
            pages[-1]["tokens"].append(c)
            pages[-1]["last"] = c["endMs"]
        else:
            pages.append({"start": c["startMs"], "last": c["endMs"], "tokens": [c], "line": line})
    return pages


def find_cuts(pages: list[dict], page_ms: int, tail_ms: int, old: bool) -> tuple[list[tuple[int, float, str]], float]:
    bad = []
    lost_ms = 0.0
    for i, page in enumerate(pages):
        next_start = pages[i + 1]["start"] if i + 1 < len(pages) else page["last"] + tail_ms
        if old:
            end = min(next_start, page["start"] + page_ms)
        else:
            end = min(next_start, max(page["start"] + page_ms, page["last"] + tail_ms))
        cut = min(next_start, page["last"]) - end
        if cut > CUT_THRESHOLD_MS:
            text = " ".join(t["text"].strip() for t in page["tokens"])
            bad.append((page["start"], cut, text))
            lost_ms += cut
    return bad, lost_ms


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Verify no caption page cuts off a spoken word.")
    parser.add_argument("--page-ms", type=int, default=1100)
    parser.add_argument("--tail-ms", type=int, default=150)
    parser.add_argument("--old", action="store_true")
    args = parser.parse_args(argv)

    project_dir = _project.find_project()
    plan_path = project_dir / "src" / "plan.json"
    if not plan_path.is_file():
        _io.fail(f"{plan_path} not found — run build.py first", code=2)
    plan = _io.read_json(plan_path)

    captions = merge_punctuation(plan.get("captions") or [])
    line_starts = sorted(L["startMs"] for L in plan.get("lines") or [])
    pages = build_pages(captions, line_starts, args.page_ms)
    bad, lost_ms = find_cuts(pages, args.page_ms, args.tail_ms, args.old)

    for start, cut, text in bad:
        print(f"  !! caption cut mid-word: {start/1000:6.1f}s  still talking {cut/1000:.2f}s with no caption  '{text}'")

    suffix = " (simulating the old fixed cap)" if args.old else ""
    print(
        f"{len(pages)} pages, {len(bad)} cut mid-word, "
        f"{lost_ms/1000:.1f}s spoken without a caption{suffix}"
    )
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
