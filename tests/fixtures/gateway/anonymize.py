#!/usr/bin/env python3
"""tests/fixtures/gateway/anonymize.py — turn a real captured gateway
response into a committable test fixture.

    python3 anonymize.py <raw.json> <out.json> --tool <name> [--job-kind KIND]

Input: a real response saved from `tool-results/mcp-lana-<tool>-<ts>.txt`
(strip any non-JSON prefix Claude Code added — this script expects to parse
straight JSON, unlike save_result.py's own tolerant parser) or a real
`McpJobView` from `lana_wait_job`. Never write a gateway fixture by hand —
this is the only path a fixture under this directory is allowed to come
from (see the module docstring in the parity test, test_gateway_shapes.py,
and the contract this pair implements).

What it does, in order:
1. UUIDs -> synthetic UUIDs, `00000000-0000-4000-8000-<12-digit counter>`,
   stable within one file (the same real UUID always maps to the same
   synthetic one, so cross-references inside a single fixture — e.g. a
   render job's `outputs[].asset_id` matching an ingest's `proxy_asset_id`
   — still line up after anonymizing).
2. `read_url`/`upload_url`/`result_url` (any key ending in those three
   names, at any depth) -> "<redacted>". These are signed URLs; a fixture
   must never carry one, redacted or not — check_clean.py's signed-url rule
   would also catch a stray one, but this is the source of truth for why.
3. `filename` -> "sample.mp4" (or the same extension the original had, if
   it wasn't .mp4 — a font/image/audio capture keeps a recognizable kind).
4. Transcript text (`words[].word`, `segments[].text`) -> a synthetic
   English script, generated to have the SAME WORD COUNT and the SAME
   start_s/end_s TIMINGS as the original — the timings are what
   normalize_transcript()'s output validation actually exercises; the
   words themselves are never real speech.
5. `created_at`/`started_at`/`finished_at` -> a fixed date
   ("2026-09-17T12:00:00Z" plus a stable offset per field so ordering is
   preserved).

Writes the `_captured: {tool, gateway_version, date, job_kind}` header this
family's fixtures all carry, as the first key.

Exit codes: 0 ok, 1 input isn't a JSON object, 2 missing input file.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
SIGNED_URL_KEYS = {"read_url", "upload_url", "result_url"}
DATE_KEYS = {"created_at", "started_at", "finished_at"}
FIXED_DATE_BASE = "2026-09-17T12:00:00"

SYNTHETIC_WORDS = (
    "here is the thing nobody tells you about this before you actually start "
    "doing it yourself and the reason is simple once you notice the pattern "
    "everywhere you look you will never see it the same way again after this"
).split()


class UuidMap:
    def __init__(self) -> None:
        self._map: dict[str, str] = {}
        self._counter = 0

    def get(self, real: str) -> str:
        if real not in self._map:
            self._counter += 1
            self._map[real] = f"00000000-0000-4000-8000-{self._counter:012d}"
        return self._map[real]

    def sub(self, text: str) -> str:
        return UUID_RE.sub(lambda m: self.get(m.group(0)), text)


def _date_for(key: str, index: int) -> str:
    # Distinct-but-stable fake timestamps: created_at < started_at <
    # finished_at, same relative order the original had.
    order = {"created_at": 0, "started_at": 30, "finished_at": 90}
    return FIXED_DATE_BASE.replace("12:00:00", f"{12 + order.get(key, 0) // 60:02d}:{order.get(key, 0) % 60:02d}:00") + "Z"


def anonymize_value(value, uuids: UuidMap, key: str | None = None):
    if isinstance(value, dict):
        return {k: anonymize_value(v, uuids, k) for k, v in value.items()}
    if isinstance(value, list):
        return [anonymize_value(v, uuids, key) for v in value]
    if isinstance(value, str):
        if key in SIGNED_URL_KEYS:
            return "<redacted>" if value else value
        if key == "filename" and value:
            ext = Path(value).suffix or ".mp4"
            return f"sample{ext}"
        if key in DATE_KEYS:
            return _date_for(key, 0)
        return uuids.sub(value)
    return value


def synthesize_words(words: list[dict]) -> list[dict]:
    """Same count, same start_s/end_s per word — different (synthetic)
    text. Cycles SYNTHETIC_WORDS if the real transcript is longer."""
    out = []
    for i, w in enumerate(words):
        synthetic = dict(w)
        if "word" in synthetic:
            synthetic["word"] = SYNTHETIC_WORDS[i % len(SYNTHETIC_WORDS)]
        out.append(synthetic)
    return out


def synthesize_segments(segments: list[dict]) -> list[dict]:
    out = []
    for seg in segments:
        synthetic = dict(seg)
        if "text" in synthetic and isinstance(synthetic["text"], str):
            n_words = max(1, len(synthetic["text"].split()))
            synthetic["text"] = " ".join(
                SYNTHETIC_WORDS[i % len(SYNTHETIC_WORDS)] for i in range(n_words)
            ).capitalize()
        out.append(synthetic)
    return out


def anonymize(obj: dict, tool: str, gateway_version: str, date: str, job_kind: str | None) -> dict:
    uuids = UuidMap()
    result = anonymize_value(obj, uuids)

    transcription = result.get("transcription")
    if isinstance(transcription, dict):
        if isinstance(transcription.get("words"), list):
            transcription["words"] = synthesize_words(transcription["words"])
        if isinstance(transcription.get("segments"), list):
            transcription["segments"] = synthesize_segments(transcription["segments"])

    header = {"tool": tool, "gateway_version": gateway_version, "date": date}
    if job_kind:
        header["job_kind"] = job_kind
    out = {"_captured": header}
    out.update(result)
    return out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Anonymize a real captured gateway response into a fixture.")
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--tool", required=True, help="e.g. lana_wait_job, lana_get_capabilities(topic=sfx)")
    parser.add_argument("--job-kind", help="TRANSCRIBE|RENDER|INGEST|SILENCE|SEGMENT, for a job fixture")
    parser.add_argument("--gateway-version", default="1.5.0")
    parser.add_argument("--date", default="2026-09-17")
    args = parser.parse_args(argv)

    in_path = Path(args.input)
    if not in_path.is_file():
        print(f"{in_path} does not exist", file=sys.stderr)
        return 2
    try:
        obj = json.loads(in_path.read_text(encoding="utf-8"))
    except ValueError:
        print("input is not JSON", file=sys.stderr)
        return 1
    if not isinstance(obj, dict):
        print("input is not a JSON object", file=sys.stderr)
        return 1

    out = anonymize(obj, args.tool, args.gateway_version, args.date, args.job_kind)
    out_path = Path(args.output)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
