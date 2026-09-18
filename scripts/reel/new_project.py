#!/usr/bin/env python3
"""scripts/reel/new_project.py — scaffold a new reel project.

    python3 ~/.claude/skills/reel/scripts/reel/new_project.py <dir> --name <slug>
        [--source <file>] [--copy] [--language en]

1. Creates <dir>/{raw,assets,lana,lana/jobs,lana-pkg,src,out}.
2. Copies template/src/* into <dir>/src/ and template/{package.json,
   package-lock.json,tsconfig.json,remotion.config.ts} into <dir>/.
3. Symlinks the shared node_modules (built once by setup.py) into
   <dir>/node_modules if it exists; otherwise warns and moves on (the agent
   can still work — `npm run check` just won't work until setup.py has run).
   NOTE: setup.py's node_modules lives at ~/.reel/template/node_modules (it
   copies template/package*.json there and runs `npm ci` once per machine);
   this script symlinks to that same path so `new_project.py` and `setup.py`
   agree on one shared location.
4. Writes a minimal project.json, copies/links
   --source into raw/ if given, copies examples/first-reel/videoconfig.py as
   a starting point with an empty script, and a project .gitignore.
5. Prints `export REEL_PROJECT=<dir>`.

Stdlib only.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import io as _io  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_NODE_MODULES = Path("~/.reel/template/node_modules").expanduser()
SLUG_RE = re.compile(r"^[a-z0-9-]{3,40}$")
PROJECT_DIRS = ("raw", "assets", "lana", "lana/jobs", "lana-pkg", "src", "out")

DEFAULT_VIDEOCONFIG = '''# -*- coding: utf-8 -*-
"""Edit plan for this reel. Fill in `sel` once you have
takes: run `takes.py --table` after transcribe/silence jobs, then reference
line indexes here (0-based)."""
CONFIG = {
    "style": {
        "captions": "bold",
        "hook_style": "banner",
        "hook_text": "first_line",
        "closing": "plate",
        "titles": "centered",
        "transitions": ["crosswarp"],
        "cards": "pop",
        "silence": "normal",
        "punch": "hooks",
        "font_group": "bold",
        "fonts_pair": "anton",
        "fonts_use": ["hook", "titles", "captions"],
        "sfx_kit": "full",
    },
    "sel": [],
    "hook_banner": "",
    "hook_tag": "",
    "titles": {},
    "punch": [],
    "bw": [],
    "glitch": [],
    "crosswarp": [],
    "closing": 0,
    "inserts": [],
    "boards": [],
    "lowerthirds": [],
    "gfx": {},
    "gfx_accents": {},
    "hold_f": 10,
}
'''


def make_project_json(name: str, language: str, source_file: str | None) -> dict:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "schema": 1,
        "name": name,
        "composition": "Reel",
        "fps": 30,
        "width": 1080,
        "height": 1920,
        "language": language,
        "requires": {"lana_mcp_render": ">=1.5.0"},
        "created_at": now,
        "assets": {},
        "fonts": {"pair": "anton", "uses": {"hook": "anton", "titles": "anton", "captions": "anton"}, "custom": {}},
        "library": {"release": None, "items": [], "rejected": []},
        "jobs": {"transcribe": None, "silence": None, "renders": []},
        "caps": {},
    }
    if source_file:
        payload["source"] = {
            "file": source_file,
            "probe": None,
            "mirror": False,
            "subject_side": "center",
            "script_mode": "full",
        }
        payload["assets"]["clip"] = {
            "file": source_file, "purpose": "episode", "content_type": None,
            "size_bytes": None, "sha256": None, "asset_id": None,
            "ingest_job_id": None, "ingest_status": None, "ext": "mp4",
        }
    return payload


def copy_template(dest: Path) -> None:
    template_src = REPO_ROOT / "template"
    if not template_src.is_dir():
        _io.eprint("!! template/ not found in the repo — skipping template copy")
        return
    src_dir = template_src / "src"
    if src_dir.is_dir():
        shutil.copytree(src_dir, dest / "src", dirs_exist_ok=True)
    for name in ("package.json", "package-lock.json", "tsconfig.json", "remotion.config.ts"):
        f = template_src / name
        if f.is_file():
            shutil.copy(f, dest / name)


def link_node_modules(dest: Path) -> None:
    target = dest / "node_modules"
    if target.exists() or target.is_symlink():
        return
    if SHARED_NODE_MODULES.is_dir():
        target.symlink_to(SHARED_NODE_MODULES, target_is_directory=True)
    else:
        _io.eprint(f"!! {SHARED_NODE_MODULES} not found — run setup.py first (`npm run check` won't work yet)")


def place_source(dest: Path, source: str, copy_source: bool) -> str:
    src_path = Path(source).expanduser()
    if not src_path.is_file():
        _io.fail(f"--source {source} does not exist", code=2)
    raw_dest = dest / "raw" / src_path.name
    if copy_source:
        shutil.copy(src_path, raw_dest)
    else:
        raw_dest.symlink_to(src_path.resolve())
    return f"raw/{src_path.name}"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Scaffold a new reel project.")
    parser.add_argument("dir", help="Project directory to create.")
    parser.add_argument("--name", required=True, help="Project slug [a-z0-9-]{3,40}.")
    parser.add_argument("--source", help="Raw footage file to place in raw/.")
    parser.add_argument("--copy", action="store_true", help="Copy --source instead of symlinking it.")
    parser.add_argument("--language", default="en", help="ISO 639-1 language code (default: en).")
    args = parser.parse_args(argv)

    if not SLUG_RE.match(args.name):
        _io.fail(f"--name {args.name!r} must match [a-z0-9-]{{3,40}}", code=1)

    dest = Path(args.dir).expanduser().resolve()
    if dest.exists() and any(dest.iterdir()):
        _io.fail(f"{dest} already exists and is not empty", code=1)
    dest.mkdir(parents=True, exist_ok=True)
    for d in PROJECT_DIRS:
        (dest / d).mkdir(parents=True, exist_ok=True)

    copy_template(dest)
    link_node_modules(dest)

    source_rel = None
    if args.source:
        source_rel = place_source(dest, args.source, args.copy)

    project = make_project_json(args.name, args.language, source_rel)
    _io.write_json(dest / "project.json", project)

    example_cfg = REPO_ROOT / "examples" / "first-reel" / "videoconfig.py"
    if example_cfg.is_file():
        shutil.copy(example_cfg, dest / "videoconfig.py")
    else:
        (dest / "videoconfig.py").write_text(DEFAULT_VIDEOCONFIG, encoding="utf-8")

    # lana/ MUST be ignored: it's where save_result.py writes lana/jobs/<id>.json,
    # and until every signed-URL field is redacted correctly, that file can
    # carry a live one (the class of bug this exact line used to make worse —
    # a project a user versions, as is normal, would commit it). lana-pkg/ is
    # entirely regenerable build output (bundle.zip, props.json, the copied
    # src/, *.args.json) — ignored whole, not just the zip. src/plan.json,
    # ritmo.json, graphics.json are NOT ignored: they're the only record of
    # exactly what was rendered, contain no secrets, and staying versioned is
    # what keeps a past render reproducible from what the user actually kept.
    (dest / ".gitignore").write_text("raw/\nout/\nlana/\nlana-pkg/\nnode_modules\n", encoding="utf-8")

    _io.eprint(f"project created at {dest}")
    print(f"export REEL_PROJECT={dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
