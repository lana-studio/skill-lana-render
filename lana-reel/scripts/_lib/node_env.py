"""The Remotion template's node_modules, installed once per machine.

It lives at ~/.reel/template/node_modules — outside any synced folder, see
KNOWHOW.md — and every project symlinks it. The first script that needs it
(new_project.py, or make_pkg.py for a project scaffolded by hand) runs
`npm ci` there; after that it is reused. A changed package-lock.json in the
skill (a Remotion bump) triggers a fresh `npm ci`.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from . import io as _io

SKILL_TEMPLATE = Path(__file__).resolve().parents[2] / "template"
PACKAGE_FILES = ("package.json", "package-lock.json")


def shared_template_dir() -> Path:
    # Resolved on every call, not at import: tests point HOME elsewhere.
    return Path("~/.reel/template").expanduser()


def _up_to_date(shared: Path) -> bool:
    if not (shared / "node_modules").is_dir():
        return False
    for name in PACKAGE_FILES:
        src, dst = SKILL_TEMPLATE / name, shared / name
        if src.is_file() and (not dst.is_file() or dst.read_bytes() != src.read_bytes()):
            return False
    return True


def ensure_shared_node_modules() -> Path | None:
    """Return ~/.reel/template/node_modules, running `npm ci` first if it is
    missing or stale. None if npm is not on PATH or `npm ci` fails — the
    reason has already been printed to stderr."""
    shared = shared_template_dir()
    if _up_to_date(shared):
        return shared / "node_modules"
    npm = shutil.which("npm")
    if npm is None:
        _io.eprint("!! npm not found on PATH — install Node.js >= 20")
        return None
    shared.mkdir(parents=True, exist_ok=True)
    for name in PACKAGE_FILES:
        if (SKILL_TEMPLATE / name).is_file():
            shutil.copy(SKILL_TEMPLATE / name, shared / name)
    _io.eprint(f"installing the Remotion template once in {shared} (npm ci, about a minute)...")
    # npm's own output goes to stderr: stdout belongs to the calling script.
    result = subprocess.run([npm, "ci", "--no-audit", "--no-fund"], cwd=str(shared), stdout=sys.stderr)
    if result.returncode != 0 or not (shared / "node_modules").is_dir():
        _io.eprint(f"!! npm ci failed in {shared} (exit {result.returncode})")
        return None
    return shared / "node_modules"
