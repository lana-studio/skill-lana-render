#!/usr/bin/env python3
"""setup.py — verify the platform and prepare the shared Remotion node_modules.

    python3 setup.py [--home ~/.reel] [--skip-node]

Steps:
  1. python3 >= 3.10 (fails with a message otherwise).
  2. node >= 20 and npm (fails unless --skip-node).
  3. ffmpeg AND ffprobe on PATH — REQUIREMENT. If
     either is missing this FAILS (exit 1) with the install command for the
     detected OS. There is no --skip-ffmpeg: it is how the agent looks at the
     material (probe_source.py) and verifies the render (verify_output.py),
     not an optional convenience.
  4. Copies template/package.json + package-lock.json to <home>/template/ and
     runs `npm ci` there once per machine (Remotion does NOT download Chromium
     on `npm ci`; this skill never runs `remotion render|still`).
  5. Writes <home>/setup.json: {python, node, ffmpeg, node_modules, at}.
  6. Prints the next step (`claude mcp add …` if not configured, and the
     "hello render").

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
MIN_PYTHON = (3, 10)
MIN_NODE = 20

FFMPEG_INSTALL_HINTS = {
    "macos": "brew install ffmpeg",
    "debian": "sudo apt install ffmpeg",
    "fedora": "sudo dnf install ffmpeg",
    "arch": "sudo pacman -S ffmpeg",
}
FFMPEG_DOWNLOAD_URL = "https://ffmpeg.org/download.html"


def detect_os() -> str:
    system = platform.system()
    if system == "Darwin":
        return "macos"
    if system == "Linux":
        try:
            text = Path("/etc/os-release").read_text(encoding="utf-8")
        except OSError:
            return "linux"
        fields = dict(
            line.split("=", 1) for line in text.splitlines() if "=" in line
        )
        id_like = (fields.get("ID", "") + " " + fields.get("ID_LIKE", "")).strip('"').lower()
        if "debian" in id_like or "ubuntu" in id_like:
            return "debian"
        if "fedora" in id_like or "rhel" in id_like:
            return "fedora"
        if "arch" in id_like:
            return "arch"
        return "linux"
    return system.lower()


def ffmpeg_install_hint(os_name: str) -> str:
    cmd = FFMPEG_INSTALL_HINTS.get(os_name)
    if cmd:
        return f"{cmd}  (see also {FFMPEG_DOWNLOAD_URL})"
    return f"install ffmpeg from {FFMPEG_DOWNLOAD_URL}"


def check_python() -> None:
    if sys.version_info < MIN_PYTHON:
        got = ".".join(str(x) for x in sys.version_info[:3])
        want = ".".join(str(x) for x in MIN_PYTHON)
        sys.exit(f"!! python3 {got} found, need >= {want}")


def _run(cmd: list[str]) -> str | None:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return (result.stdout or result.stderr).strip()


def check_node(skip: bool) -> str | None:
    if skip:
        return None
    node_path = shutil.which("node")
    npm_path = shutil.which("npm")
    if not node_path or not npm_path:
        sys.exit("!! node >= 20 and npm are required (use --skip-node to skip this check)")
    version = _run([node_path, "--version"]) or ""
    digits = version.lstrip("v").split(".")[0]
    try:
        major = int(digits)
    except ValueError:
        major = 0
    if major < MIN_NODE:
        sys.exit(f"!! node {version} found, need >= {MIN_NODE}")
    return version


def check_ffmpeg() -> str:
    os_name = detect_os()
    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    if not ffmpeg_path or not ffprobe_path:
        missing = ", ".join(n for n, p in (("ffmpeg", ffmpeg_path), ("ffprobe", ffprobe_path)) if not p)
        sys.exit(
            f"!! {missing} not found on PATH — ffmpeg is REQUIRED, not optional\n"
            f"!! install it with: {ffmpeg_install_hint(os_name)}"
        )
    version_line = _run([ffmpeg_path, "-version"]) or ""
    version = version_line.splitlines()[0].split()[2] if version_line else "unknown"
    print(f"ffmpeg {version} ok", file=sys.stderr)
    return version


def prepare_node_modules(home: Path, skip_node: bool, dry_run: bool) -> str | None:
    if skip_node:
        return None
    template_src = REPO_ROOT / "template"
    package_json = template_src / "package.json"
    if not package_json.is_file():
        print("!! template/package.json not found — skipping npm ci", file=sys.stderr)
        return None
    template_dst = home / "template"
    if dry_run:
        print(f"[dry-run] copy {template_src}/package*.json -> {template_dst}, then npm ci")
        return str(template_dst / "node_modules")
    template_dst.mkdir(parents=True, exist_ok=True)
    for name in ("package.json", "package-lock.json"):
        src = template_src / name
        if src.is_file():
            shutil.copy(src, template_dst / name)
    subprocess.run(["npm", "ci"], cwd=template_dst, check=True)
    return str(template_dst / "node_modules")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Verify platform requirements and prepare node_modules.")
    parser.add_argument("--home", default="~/.reel", help="Where to keep the shared template/node_modules.")
    parser.add_argument("--skip-node", action="store_true", help="Skip node/npm checks and npm ci.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    home = Path(args.home).expanduser().resolve()

    check_python()
    node_version = check_node(args.skip_node)
    ffmpeg_version = check_ffmpeg()
    node_modules = prepare_node_modules(home, args.skip_node, args.dry_run)

    payload = {
        "python": ".".join(str(x) for x in sys.version_info[:3]),
        "node": node_version,
        "ffmpeg": ffmpeg_version,
        "node_modules": node_modules,
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    setup_json = home / "setup.json"
    if not args.dry_run:
        home.mkdir(parents=True, exist_ok=True)
        setup_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"setup ok -> {setup_json}", file=sys.stderr)
    print(
        "next: connect the Lana MCP if you haven't (`claude mcp add ...` — see "
        "the README's onboarding section), then the hello render.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
