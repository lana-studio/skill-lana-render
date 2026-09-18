#!/usr/bin/env python3
"""scripts/lana/verify_output.py — final verification before calling a render done.

    python3 verify_output.py --job lana/jobs/<id>.json [--file out/final.mp4] [--expect-ms <n>]

From the job: compares `outputs[].duration_s` against --expect-ms (or
src/plan.json's `total/fps` if --expect-ms is not given); `!!` if they differ
by more than 100 ms. Interprets known error shapes (useful for the hello
render and any submit): `ASSET_ERROR` under `assets.<font>` -> "premium too
old for purpose=font"; a `logs_tail` mentioning `public/sfx/` with a 404 ->
"harness too old: SFX pack not mounted"; `RENDER_NOT_ENABLED` /
`PLAN_NOT_ELIGIBLE` -> "render gate: check your plan"; `FORBIDDEN_SCOPE` ->
"re-authorize with /mcp and grant <scope>".

With --file (REQUIRED for the final render — ffmpeg is used here only to
verify, never to render): `ffprobe` duration (`!!` if it differs from the
plan by > 100 ms) and `ffmpeg -af silencedetect=noise=-40dB:d=0.4` over the
output; every detected silence is compared against the SEL's
`keep_pauses=True` windows (read from src/plan.json's `lines[].keep`, ±150 ms)
and the final `hold_f` tail — anything else is `!!`.

Exit 1 if any `!!` finding. Exit 2 if --job/--file don't exist.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import io as _io  # noqa: E402
from _lib import project as _project  # noqa: E402

SILENCE_RE_START = re.compile(r"silence_start:\s*([-\d.]+)")
SILENCE_RE_END = re.compile(r"silence_end:\s*([-\d.]+)\s*\|\s*silence_duration:\s*([-\d.]+)")
DURATION_TOLERANCE_MS = 100
PAUSE_TOLERANCE_MS = 150


def interpret_error(job: dict) -> str | None:
    error = job.get("error") or {}
    code = error.get("code")
    field = error.get("field_path") or ""
    render = job.get("render") or {}
    logs_tail = render.get("logs_tail") or ""

    if code == "ASSET_ERROR" and "assets." in field:
        return f"premium too old for purpose=font ({field})"
    if "public/sfx/" in logs_tail and "404" in logs_tail:
        return "harness too old: SFX pack not mounted"
    if code in ("RENDER_NOT_ENABLED", "PLAN_NOT_ELIGIBLE"):
        return "render gate: check your plan"
    if code == "FORBIDDEN_SCOPE":
        # McpErrorDetail (services/mcp-gateway/app/schemas/errors.py) has no
        # separate "scope" field — FORBIDDEN_SCOPE names the missing scope
        # inside `message` itself ("el detalle lo nombra" per the error
        # catalog's own guidance), which is always present (required field).
        return f"re-authorize with /mcp and grant {error.get('message', '')}"
    if code:
        return f"{code}: {error.get('message', '')}"
    return None


def expected_ms(job: dict, expect_ms: int | None, project_dir: Path | None) -> int | None:
    if expect_ms is not None:
        return expect_ms
    if project_dir is not None:
        plan_path = project_dir / "src" / "plan.json"
        if plan_path.is_file():
            plan = _io.read_json(plan_path)
            total = plan.get("total")
            fps = plan.get("fps", 30)
            if total is not None and fps:
                return round(total / fps * 1000)
    return None


def check_duration(label: str, actual_ms: float, expected_ms_value: int | None) -> bool:
    if expected_ms_value is None:
        return True
    diff = abs(actual_ms - expected_ms_value)
    if diff > DURATION_TOLERANCE_MS:
        _io.eprint(f"!! {label} duration {actual_ms:.0f}ms differs from plan {expected_ms_value}ms by {diff:.0f}ms")
        return False
    return True


def keep_windows(project_dir: Path) -> list[tuple[int, int]]:
    plan_path = project_dir / "src" / "plan.json"
    if not plan_path.is_file():
        return []
    plan = _io.read_json(plan_path)
    windows = []
    for line in plan.get("lines") or []:
        if line.get("keep"):
            windows.append((line["startMs"], line["endMs"]))
    return windows


def hold_tail_window(project_dir: Path) -> tuple[int, int] | None:
    plan_path = project_dir / "src" / "plan.json"
    if not plan_path.is_file():
        return None
    plan = _io.read_json(plan_path)
    total = plan.get("total")
    fps = plan.get("fps", 30)
    hold_f = plan.get("hold_f", 0)
    if total is None:
        return None
    total_ms = total / fps * 1000
    hold_ms = hold_f / fps * 1000
    return (round(total_ms - hold_ms), round(total_ms + hold_ms + 500))


def run_silencedetect(ffmpeg: str, file: Path) -> list[tuple[float, float]]:
    # silencedetect logs silence_start/silence_end at INFO level — "-v error"
    # (used everywhere else in this family to keep stderr quiet) would
    # silently discard every finding this function exists to parse.
    cmd = [ffmpeg, "-v", "info", "-nostats", "-i", str(file), "-af", "silencedetect=noise=-40dB:d=0.4", "-f", "null", "-"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    silences = []
    start = None
    for line in result.stderr.splitlines():
        m_start = SILENCE_RE_START.search(line)
        if m_start:
            start = float(m_start.group(1))
            continue
        m_end = SILENCE_RE_END.search(line)
        if m_end and start is not None:
            end = float(m_end.group(1))
            silences.append((start, end))
            start = None
    return silences


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Verify a render job's output.")
    parser.add_argument("--job", required=True)
    parser.add_argument("--file")
    parser.add_argument("--expect-ms", type=int)
    args = parser.parse_args(argv)

    job_path = Path(args.job)
    if not job_path.is_file():
        _io.fail(f"{job_path} does not exist", code=2)
    job = json.loads(job_path.read_text(encoding="utf-8"))

    try:
        project_dir = _project.find_project()
    except SystemExit:
        project_dir = None

    ok = True
    status = job.get("status")
    print(f"status: {status}")

    err_msg = interpret_error(job)
    if err_msg:
        _io.eprint(f"!! {err_msg}")
        ok = False

    # McpJobView nests outputs[] under render (RenderStatus.outputs) for a
    # RENDER job, not at the top level; obj.get("outputs") is kept only as
    # a fallback for a shape this schema doesn't currently produce.
    outputs = (job.get("render") or {}).get("outputs") or job.get("outputs") or []
    exp_ms = expected_ms(job, args.expect_ms, project_dir)
    for out in outputs:
        duration_s = out.get("duration_s")
        if duration_s is not None:
            ok = check_duration(out.get("composition_id", "output"), duration_s * 1000, exp_ms) and ok

    if args.file:
        file = Path(args.file)
        if not file.is_file():
            _io.fail(f"{file} does not exist", code=2)
        ffprobe = shutil.which("ffprobe")
        ffmpeg = shutil.which("ffmpeg")
        if not ffprobe or not ffmpeg:
            _io.fail("ffmpeg/ffprobe not found on PATH — run setup.py", code=2)

        probe_cmd = [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(file)]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
        try:
            file_duration_ms = float(probe_result.stdout.strip()) * 1000
        except ValueError:
            file_duration_ms = None
        if file_duration_ms is not None:
            ok = check_duration(file.name, file_duration_ms, exp_ms) and ok

        silences = run_silencedetect(ffmpeg, file)
        windows = keep_windows(project_dir) if project_dir else []
        tail = hold_tail_window(project_dir) if project_dir else None

        def is_justified(s_ms: float, e_ms: float) -> bool:
            for w0, w1 in windows:
                if s_ms >= w0 - PAUSE_TOLERANCE_MS and e_ms <= w1 + PAUSE_TOLERANCE_MS:
                    return True
            if tail and s_ms >= tail[0] - PAUSE_TOLERANCE_MS:
                return True
            return False

        for s, e in silences:
            s_ms, e_ms = s * 1000, e * 1000
            if not is_justified(s_ms, e_ms):
                _io.eprint(f"!! unjustified silence {s_ms:.0f}-{e_ms:.0f}ms ({e_ms - s_ms:.0f}ms)")
                ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
