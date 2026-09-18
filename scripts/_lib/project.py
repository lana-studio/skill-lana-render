"""scripts/_lib/project.py — locate and load the current reel project.

  1. $REEL_PROJECT if set.
  2. Otherwise the current working directory.
  3. If project.json is not there, ascend up to 3 parent directories.
  4. If still not found: fail with "no project.json found: run new_project.py
     or export REEL_PROJECT".

Every script that touches a project calls `find_project()` once at the top,
then `load()`/`save()`. Nothing here does `os.chdir()` — every script reads
and writes with paths built from the project directory, so two scripts can
run against two different projects in the same shell without stepping on
each other (unlike the private skill's `cfg.py`, which chdir'd once at import
time; that was fine for a single project per process, but this family is a
public library other tools may import more than once).
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

from . import io as _io

PROJECT_FILENAME = "project.json"
MAX_ASCEND = 3
NOT_FOUND_MESSAGE = "no project.json found: run new_project.py or export REEL_PROJECT"


def find_project(start: Path | None = None) -> Path:
    """Return the directory containing project.json, or exit 2 with
    NOT_FOUND_MESSAGE (this family's exit code convention: 2 = missing
    input file/project). Raises SystemExit(2) via `_io.fail` — NOT a bare
    `SystemExit(str)`, whose `.code` would be the message string itself and
    which CPython turns into process exit status 1, not 2 (a real
    regression this file used to have: catch it with a test that asserts
    `.code == 2`, not just "raises")."""
    env = os.environ.get("REEL_PROJECT")
    if env:
        candidate = Path(env).expanduser().resolve()
        if (candidate / PROJECT_FILENAME).is_file():
            return candidate
        _io.fail(NOT_FOUND_MESSAGE, code=2)

    here = (start or Path.cwd()).resolve()
    for _ in range(MAX_ASCEND + 1):
        if (here / PROJECT_FILENAME).is_file():
            return here
        if here.parent == here:
            break
        here = here.parent
    _io.fail(NOT_FOUND_MESSAGE, code=2)


def load(project_dir: Path) -> dict[str, Any]:
    """Load project.json as-is. Callers that mutate it and call save() will
    naturally preserve any key they didn't touch, since they mutate the same
    dict they loaded (no allowlist of known keys anywhere in this path)."""
    return _io.read_json(Path(project_dir) / PROJECT_FILENAME)


def save(project_dir: Path, data: dict[str, Any]) -> None:
    """Write project.json. Never drops unknown keys: callers pass back the
    same dict `load()` gave them, mutated in place."""
    _io.write_json(Path(project_dir) / PROJECT_FILENAME, data)


def ready_assets(project: dict[str, Any]) -> dict[str, Any]:
    """Registered assets the render harness can actually stage: `asset_id`
    set, `purpose != "bundle"` (a bundle is the code package itself, never a
    render asset), and either no ingest applies (`ingest_status` is `None` —
    image/font/bundle-less uploads) or ingest finished
    (`ingest_status == "SUCCEEDED"`). Anything mid-ingest (`"PENDING"`) or
    failed is excluded, not hard-failed — the agent may still be waiting on
    one asset while others are ready.

    This is THE single definition of "ready" for both `make_pkg.py`'s
    `ASSET_FILES` and `make_submit.py`'s submit `assets` map (D16 / bug 9,
    "every real reel rendered black"): both call this exact function so they
    cannot silently diverge again the way the old `used-assets.json`
    static-literal scan diverged from the registry."""
    out: dict[str, Any] = {}
    for key, entry in (project.get("assets") or {}).items():
        if key == "bundle" or entry.get("purpose") == "bundle":
            continue
        if not entry.get("asset_id"):
            continue
        if entry.get("ingest_status") not in (None, "SUCCEEDED"):
            continue
        out[key] = entry
    return out


def ready_custom_fonts(project: dict[str, Any]) -> dict[str, Any]:
    """`project.fonts.custom[*]` entries with an `asset_id` — the font
    counterpart to `ready_assets()`, used the same way by both scripts."""
    custom = (project.get("fonts") or {}).get("custom") or {}
    return {key: entry for key, entry in custom.items() if entry.get("asset_id")}


def load_config(project_dir: Path):
    """Import <project>/videoconfig.py and return its CONFIG dict.

    Uses importlib with an explicit spec (not sys.path manipulation) so two
    projects' videoconfig.py — same module name, different content — never
    collide in sys.modules across a single process (a test suite imports many
    fixture projects in one pytest run).
    """
    path = Path(project_dir) / "videoconfig.py"
    if not path.is_file():
        _io.fail(
            f"missing {path} — copy examples/first-reel/videoconfig.py into your project",
            code=2,
        )
    # A fresh, unique module name per call avoids sys.modules collisions.
    mod_name = f"_reel_videoconfig_{abs(hash(str(path)))}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        _io.fail(f"could not load {path} as a Python module", code=2)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    try:
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    finally:
        sys.modules.pop(mod_name, None)
    if not hasattr(module, "CONFIG"):
        _io.fail(f"{path} does not define a CONFIG dict", code=2)
    return module.CONFIG
