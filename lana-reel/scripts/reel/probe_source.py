#!/usr/bin/env python3
"""scripts/reel/probe_source.py — look at the raw material with ffmpeg.

    python3 probe_source.py <file> [--frames 3] [--at 10,50,90] [--out lana/frames/] [--record]

ffmpeg is a REQUIREMENT here, used for exactly two things: metadata
(`ffprobe`) and extracting a handful of still frames so the agent can *look*
at the material — never to transcode, measure silence, or render (that stays
on the MCP; see the "Don'ts" list this skill ships with). This is the only
way the agent gets vision of the source: a short clip rendered by the MCP
isn't something the client can see (Claude Code and Codex included; the
gateway's inline-image response
only exists for shared-library refs, and the ingest pipeline doesn't
currently produce a preview frame for a user's own uploaded footage), so
looking at a handful of extracted JPEGs is the only path there is.

1. `ffprobe -show_entries stream=codec_type,codec_name,width,height,
   r_frame_rate,color_transfer,side_data_list:format=duration -of json` ->
   duration, resolution, fps, rotation (side_data_list[].rotation, falling
   back to the legacy `tags.rotate`), color transfer (HLG/PQ -> a note that
   the ingest tone-maps it, nothing to do locally), and whether an audio
   stream exists.
2. Extracts --frames JPGs at the --at percentages of the duration (default
   10/50/90%) with `-ss` BEFORE `-i` (fast seek), scaled to a 720px max side,
   named <stem>-<pct>.jpg under --out.
3. Prints the frame paths and closes with the instruction to look at them
   before deciding mirror / subject side / color.

No network. Writes to project.json only with --record (duration, rotation,
fps, hdr, has_audio — never the frame paths themselves).
Exit codes: 0 ok, 2 missing file/ffmpeg/ffprobe.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import io as _io  # noqa: E402
from _lib import project as _project  # noqa: E402

HDR_TRANSFERS = {"arib-std-b67": "HLG", "smpte2084": "PQ"}


def require_tools() -> tuple[str, str]:
    ffprobe = shutil.which("ffprobe")
    ffmpeg = shutil.which("ffmpeg")
    if not ffprobe or not ffmpeg:
        _io.fail("ffmpeg/ffprobe not found on PATH — install ffmpeg (macOS: brew install ffmpeg)", code=2)
    return ffmpeg, ffprobe  # type: ignore[return-value]


def probe(ffprobe: str, file: Path) -> dict:
    cmd = [
        ffprobe, "-v", "error",
        "-show_entries",
        "stream=codec_type,codec_name,width,height,r_frame_rate,color_transfer,side_data_list:format=duration",
        "-of", "json", str(file),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        _io.fail(f"ffprobe failed on {file}: {result.stderr.strip()[:300]}", code=2)
    return json.loads(result.stdout or "{}")


def _rotation_of(stream: dict) -> int:
    for sd in stream.get("side_data_list") or []:
        if "rotation" in sd:
            try:
                return int(sd["rotation"])
            except (TypeError, ValueError):
                pass
    tags = stream.get("tags") or {}
    if "rotate" in tags:
        try:
            return int(tags["rotate"])
        except (TypeError, ValueError):
            pass
    return 0


def summarize(data: dict) -> dict:
    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    duration_s = None
    fmt = data.get("format") or {}
    if fmt.get("duration") is not None:
        try:
            duration_s = float(fmt["duration"])
        except (TypeError, ValueError):
            duration_s = None
    fps = None
    if video and video.get("r_frame_rate"):
        num, _, den = video["r_frame_rate"].partition("/")
        try:
            fps = round(int(num) / int(den or "1"), 3)
        except (ValueError, ZeroDivisionError):
            fps = None
    rotation = _rotation_of(video) if video else 0
    transfer = (video or {}).get("color_transfer")
    hdr = HDR_TRANSFERS.get(transfer)
    return {
        "duration_ms": round(duration_s * 1000) if duration_s is not None else None,
        "width": (video or {}).get("width"),
        "height": (video or {}).get("height"),
        "fps": fps,
        "rotation": rotation,
        "hdr": hdr,
        "has_audio": has_audio,
    }


def extract_frames(ffmpeg: str, file: Path, duration_ms: int | None, percentages: list[int], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = file.stem
    paths = []
    duration_s = (duration_ms or 0) / 1000
    for pct in percentages:
        t = max(0.0, duration_s * pct / 100)
        dest = out_dir / f"{stem}-{pct}.jpg"
        cmd = [
            ffmpeg, "-v", "error", "-ss", f"{t:.3f}", "-i", str(file),
            "-frames:v", "1", "-vf", "scale='min(720,iw)':-2",
            "-q:v", "3", "-y", str(dest),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            _io.eprint(f"!! could not extract frame at {pct}%: {result.stderr.strip()[:200]}")
            continue
        paths.append(dest)
    return paths


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Probe raw footage and extract look-at-it frames.")
    parser.add_argument("file")
    parser.add_argument("--frames", type=int, default=3)
    parser.add_argument("--at", default="10,50,90")
    parser.add_argument("--out", default="lana/frames")
    parser.add_argument("--record", action="store_true", help="Write source.probe into project.json.")
    args = parser.parse_args(argv)

    file = Path(args.file).expanduser().resolve()
    if not file.is_file():
        _io.fail(f"{file} does not exist", code=2)

    ffmpeg, ffprobe = require_tools()
    raw = probe(ffprobe, file)
    info = summarize(raw)

    percentages = [int(p) for p in args.at.split(",") if p.strip()][: max(0, args.frames)]

    if info["duration_ms"] is not None:
        _io.eprint(f"duration: {info['duration_ms'] / 1000:.1f}s  {info['width']}x{info['height']}  {info['fps']} fps")
    _io.eprint(f"rotation: {info['rotation']}°  has_audio: {info['has_audio']}")
    if info["hdr"]:
        _io.eprint(f"HDR: {info['hdr']} — Lana's ingest tone-maps this; nothing to do locally")

    out_dir = Path(args.out)
    frame_paths = extract_frames(ffmpeg, file, info["duration_ms"], percentages, out_dir)
    for p in frame_paths:
        print(str(p))

    if args.record:
        try:
            project_dir = _project.find_project()
            project = _project.load(project_dir)
            project.setdefault("source", {})["probe"] = {
                "duration_ms": info["duration_ms"], "rotation": info["rotation"],
                "fps": info["fps"], "hdr": info["hdr"], "has_audio": info["has_audio"],
            }
            _project.save(project_dir, project)
        except SystemExit:
            _io.eprint("!! --record given but no project found; probe not saved")

    _io.eprint("look at these frames before deciding: mirror? subject side? color?")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
