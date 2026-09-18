#!/usr/bin/env python3
"""scripts/lana/prep_upload.py — the "emitir" step for lana_create_upload.

    python3 prep_upload.py <file> --purpose {episode,take,context,image,bundle,font}
        [--key <k>] [--title <t>] [--no-fix] --emit

Validates the file and registers it in project.assets[key], then prints the
exact args for `lana_create_upload` (the "emit" step of the emit -> call ->
save handshake). ffmpeg/ffprobe are used here for two things: (1) checking
duration against the gateway's real per-purpose floor/ceiling BEFORE
uploading, and (2) adding a silent audio track to an mp4/mov/mkv that has
none — Lana's ingest requires an audio stream. Neither is a transcode of the
raw take.

- Validates: file exists, size <= 2 GiB, extension<->content-type mapping,
  purpose coherent with the file type (font <= 5 MiB; bundle <= 20 MiB and
  only .zip; episode|take|context only video/audio; image only image);
  episode|take|context also get a local duration check against
  `_lib.limits.UPLOAD_DURATION_BOUNDS_S` (episode >= 60s — it means a full
  podcast episode; take = 1s-600s, the purpose that actually fits a reel's
  main source clip; context <= 600s, no floor). This is the check that used
  to only happen server-side, AFTER the file had already traveled, leaving
  the asset permanently REJECTED with no way to retry it under a different
  purpose — see `_lib.limits.UPLOAD_DURATION_BOUNDS_S`'s docstring for where
  these numbers come from and why they can't be read from the gateway today.
- --key is required except for `bundle` (fixed key "bundle"); `episode` and
  `take` both default to "clip" (either is the main source; ext deciding
  which one applies is left to the agent, not guessed by this script).
- For .mp4/.mov/.mkv: `ffprobe` checks for an audio stream; if missing, adds
  a silent one with `ffmpeg ... anullsrc=r=48000:cl=stereo -shortest -c:v
  copy -c:a aac -b:a 64k -movflags +faststart <stem>-a.mp4` (inherited from
  upload-clips.py) and registers THAT file instead, printing
  "<file>: no audio track — silent track added as <stem>-a.mp4 (Lana ingest
  requires audio)". --no-fix makes this a hard failure (exit 1) instead.
  Missing ffprobe -> exit 2.
- Warns (does not fail) for .jpg: "JPEG rendered broken in past runs; prefer
  PNG".
- Registers project.assets[key] = {file, purpose, content_type, size_bytes,
  sha256, asset_id: null}.
- --emit prints exactly {"filename","content_type","size_bytes","purpose",
  "title"} — the args of `lana_create_upload`.

Exit codes: 0 ok, 1 validation failed, 2 missing file/project/ffprobe, 3 n/a.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import io as _io  # noqa: E402
from _lib import limits as _limits  # noqa: E402
from _lib import project as _project  # noqa: E402

EXT_CONTENT_TYPE = {
    ".mov": "video/quicktime", ".mp4": "video/mp4", ".mkv": "video/x-matroska",
    ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".wav": "audio/wav",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".svg": "image/svg+xml", ".zip": "application/zip",
    ".ttf": "font/ttf", ".otf": "font/otf", ".woff2": "font/woff2",
}
VIDEO_AUDIO_EXTS = {".mov", ".mp4", ".mkv", ".mp3", ".m4a", ".wav"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
FONT_EXTS = {".ttf", ".otf", ".woff2"}
AUDIO_FIXABLE_EXTS = {".mp4", ".mov", ".mkv"}
DEFAULT_KEYS = {"bundle": "bundle", "episode": "clip", "take": "clip"}


def content_type_for(path: Path) -> str:
    ext = path.suffix.lower()
    ct = EXT_CONTENT_TYPE.get(ext)
    if ct is None:
        _io.fail(f"unrecognized extension {ext!r} for {path}", code=1)
    return ct


def check_purpose(path: Path, purpose: str, content_type: str, size_bytes: int) -> None:
    ext = path.suffix.lower()
    if purpose == "font":
        if ext not in FONT_EXTS:
            _io.fail(f"purpose=font requires ttf/otf/woff2, got {ext}", code=1)
        if size_bytes > _limits.FONT_MAX_BYTES:
            _io.fail(f"font file {size_bytes} bytes exceeds {_limits.FONT_MAX_BYTES} (5 MiB)", code=1)
    elif purpose == "bundle":
        if ext != ".zip":
            _io.fail("purpose=bundle requires a .zip file", code=1)
        if size_bytes > _limits.BUNDLE_MAX_BYTES:
            _io.fail(f"bundle {size_bytes} bytes exceeds {_limits.BUNDLE_MAX_BYTES} (20 MiB)", code=1)
    elif purpose in ("episode", "take", "context"):
        if not content_type.startswith("video/") and not content_type.startswith("audio/"):
            _io.fail(f"purpose={purpose} requires video or audio, got {content_type}", code=1)
    elif purpose == "image":
        if not content_type.startswith("image/"):
            _io.fail(f"purpose=image requires an image, got {content_type}", code=1)
    else:
        _io.fail(f"unknown purpose {purpose!r}", code=1)


def probe_duration_s(ffprobe: str, path: Path) -> float | None:
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def check_duration(purpose: str, duration_s: float | None) -> None:
    """Enforces _lib.limits.UPLOAD_DURATION_BOUNDS_S locally, before the file
    ever leaves this machine. Without this, a too-short episode upload
    travels all the way to the gateway, gets REJECTED there permanently, and
    the only way to find out is losing that upload.

    This does NOT just mirror services/media/app/services/probe.py's gate —
    it's deliberately STRICTER on the two ceilings the service can waive
    (context > 600s, episode > 4h), which probe.validate_probe() treats as
    DURATION_REQUIRES_CONFIRM (pass confirm_long_duration=True and it's
    allowed through) rather than a hard rejection. No MCP tool argument
    exposes confirm_long_duration, so a script here has no way to ask the
    server to waive it — hard-failing locally on those two ceilings is the
    correct behavior, not an approximation of the service's rule. The take
    ceiling (600s) IS a hard reject on both sides already, so it's not
    stricter there."""
    bounds = _limits.UPLOAD_DURATION_BOUNDS_S.get(purpose)
    if bounds is None or duration_s is None:
        return
    lo, hi = bounds
    if duration_s < lo:
        message = f"{duration_s:.1f}s with --purpose {purpose} is below the {lo:.0f}s floor"
        if purpose == "episode":
            message += "; use --purpose take instead (1-600s)"
        _io.fail(message, code=1)
    if duration_s > hi:
        _io.fail(
            f"{duration_s:.1f}s with --purpose {purpose} exceeds the {hi:.0f}s "
            f"({hi / 60:.0f} min) ceiling",
            code=1,
        )


def has_audio_stream(ffprobe: str, path: Path) -> bool:
    result = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return bool(result.stdout.strip())


def add_silent_track(ffmpeg: str, path: Path) -> Path:
    dest = path.with_name(f"{path.stem}-a{path.suffix}")
    cmd = [
        ffmpeg, "-y", "-v", "error", "-i", str(path),
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", str(dest),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        _io.fail(f"could not add a silent track to {path}: {result.stderr.strip()[:300]}", code=1)
    return dest


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Validate and register a file for lana_create_upload.")
    parser.add_argument("file")
    parser.add_argument("--purpose", required=True, choices=["episode", "take", "context", "image", "bundle", "font"])
    parser.add_argument("--key")
    parser.add_argument("--title")
    parser.add_argument("--no-fix", action="store_true", help="Fail instead of adding a silent audio track.")
    parser.add_argument("--emit", action="store_true")
    args = parser.parse_args(argv)

    path = Path(args.file).expanduser().resolve()
    if not path.is_file():
        _io.fail(f"{path} does not exist", code=2)

    size_bytes = path.stat().st_size
    if size_bytes > _limits.UPLOAD_MAX_BYTES:
        _io.fail(f"{path} is {size_bytes} bytes, exceeds the 2 GiB upload limit", code=1)

    content_type = content_type_for(path)
    check_purpose(path, args.purpose, content_type, size_bytes)

    ext = path.suffix.lower()
    if ext == ".jpg" or ext == ".jpeg":
        _io.eprint(f"!! {path}: JPEG rendered broken in past runs; prefer PNG")

    ffprobe = None
    if ext in VIDEO_AUDIO_EXTS and args.purpose in ("episode", "take", "context"):
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            _io.fail("ffprobe not found on PATH — run setup.py", code=2)
        check_duration(args.purpose, probe_duration_s(ffprobe, path))

    if ext in AUDIO_FIXABLE_EXTS and args.purpose in ("episode", "take", "context"):
        if ffprobe is None:
            ffprobe = shutil.which("ffprobe")
            if not ffprobe:
                _io.fail("ffprobe not found on PATH — run setup.py", code=2)
        if not has_audio_stream(ffprobe, path):
            if args.no_fix:
                _io.fail(f"{path} has no audio track (Lana ingest requires audio); rerun without --no-fix", code=1)
            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                _io.fail("ffmpeg not found on PATH — run setup.py", code=2)
            new_path = add_silent_track(ffmpeg, path)
            _io.eprint(f"{path}: no audio track — silent track added as {new_path.name} (Lana ingest requires audio)")
            path = new_path
            size_bytes = path.stat().st_size

    key = args.key or DEFAULT_KEYS.get(args.purpose)
    if not key:
        _io.fail("--key is required for this purpose", code=1)

    title = args.title or path.stem

    project_dir = _project.find_project()
    project = _project.load(project_dir)
    entry = project.setdefault("assets", {}).setdefault(key, {})
    entry.update({
        "file": str(path.relative_to(project_dir)) if path.is_relative_to(project_dir) else str(path),
        "purpose": args.purpose,
        "content_type": content_type,
        "size_bytes": size_bytes,
        "sha256": _io.sha256_file(path),
        "asset_id": entry.get("asset_id"),
    })
    _project.save(project_dir, project)

    emit_args = {
        "filename": path.name,
        "content_type": content_type,
        "size_bytes": size_bytes,
        "purpose": args.purpose,
        "title": title,
    }
    if args.emit:
        _io.emit(emit_args, "prep_upload", project_dir)
    else:
        _io.eprint(f"registered assets.{key}: {emit_args}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
