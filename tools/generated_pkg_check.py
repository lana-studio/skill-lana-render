#!/usr/bin/env python3
"""tools/generated_pkg_check.py — step 5 of tools/check.py (not pytest): does
the REAL generated bundle compile, on THIS machine, right now?

    python3 tools/generated_pkg_check.py

This is a long-promised deliverable that never got written until this
round: scaffold a real project, seed it with a known-good fixture, and
run it through build.py -> make_pkg.py for real, exiting with
make_pkg.py's own code. It exists separately from pytest because plain
`pytest -q -rs tests tools/tests` never runs `npm ci` on its own (only
`cd template && npm ci && npm run check` does, and only against the bare
placeholder — never a project with registered assets/fonts/library items
run through make_pkg.py for real) — this script runs AFTER that `npm ci`,
wired into `tools/check.py` as its own step (step 5), closing that gap
(see the rsp-scripts report). There is no CI (decision of Martín,
2026-09-17): `tools/check.py` is what runs these steps now, by hand.

Steps, each run as a real subprocess (matching every other script's test
convention — no internals imported):
1. `new_project.py <tmp>/proj --name ci-check` — the real scaffolding path
   a user's first command takes, not a hand-built fixture project.
2. Overwrite the scaffolded project.json with
   tests/fixtures/project.pkg-check.json (synthetic UUIDs, three
   registered assets: video/image/font, plus a custom font and a library
   item — so ASSET_FILES, FONT_FILES and LIB_FILES are all non-empty and
   the typecheck step below actually exercises them, not just an
   annotation on an empty object) and videoconfig.py + lana/transcript.json
   + lana/silence.json with the matching fixtures, so build.py has real
   input to align against.
3. If template/node_modules exists next to this repo (the `template` CI
   job's own `npm ci` leaves it there), symlink it into the project — so
   make_pkg.py's internal typecheck step actually RUNS instead of printing
   "typecheck skipped" and exiting 0 regardless. Without
   this, the script would "pass" without ever compiling anything, which is
   exactly the silent-pass failure mode this script exists to close.
4. `build.py` — turns the fixture CONFIG into src/plan.json/ritmo.json/
   graphics.json + lana-pkg/proofs.json.
5. `make_pkg.py` — the real gate: case-collision check, asset/library
   manifests, plan modules, code-budget breakdown, typecheck if
   node_modules is there.

Exit code: exactly make_pkg.py's own (0 ok, 1 a validation/typecheck
failure, 2 missing input) — build.py failing first exits with ITS code
instead (2 normally, since the fixtures are known-good; a nonzero here at
all means investigate, not "this script has its own opinion").
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "lana-reel" / "scripts"
FIXTURES = REPO_ROOT / "tests" / "fixtures"
TEMPLATE_NODE_MODULES = REPO_ROOT / "lana-reel" / "template" / "node_modules"


def run(script: Path, args: list[str], cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    import os

    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    result = subprocess.run(
        [sys.executable, str(script), *args], cwd=str(cwd), capture_output=True, text=True, env=full_env,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result


def main() -> int:
    # Line-buffer both streams: when this script's own output is redirected
    # to a file (as any CI runner does), stdout is fully block-buffered by
    # default while stderr typically isn't — the two streams then flush at
    # different times and a merged (2>&1) log shows this script's steps and
    # each subprocess's stdout/stderr out of true chronological order, which
    # is confusing to read even though the actual data is complete.
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)

    tmp = Path(tempfile.mkdtemp(prefix="generated-pkg-check-"))
    proj = tmp / "proj"

    print(f"== new_project.py {proj} --name ci-check", file=sys.stderr)
    result = run(SCRIPTS / "reel" / "new_project.py", [str(proj), "--name", "ci-check", "--no-install"], cwd=tmp)
    if result.returncode != 0:
        print("!! new_project.py failed", file=sys.stderr)
        return result.returncode

    print(
        "== seeding fixtures (project.json, videoconfig.py, transcript.json, silence.json, caps.sfx.json)",
        file=sys.stderr,
    )
    shutil.copy(FIXTURES / "project.pkg-check.json", proj / "project.json")
    shutil.copy(FIXTURES / "videoconfig.py", proj / "videoconfig.py")
    (proj / "lana").mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURES / "transcript.json", proj / "lana" / "transcript.json")
    shutil.copy(FIXTURES / "silence.json", proj / "lana" / "silence.json")
    # Bug 19 follow-up (2026-09-17): build.py now fails loud unless
    # style.sfx_kit="mute" or lana/caps.sfx.json exists — the fixture
    # CONFIG selects sfx_kit="full" (new_project.py's own default too), so
    # this script needs the pack present for build.py to get past its gate
    # at all.
    shutil.copy(FIXTURES / "gateway" / "caps.sfx.json", proj / "lana" / "caps.sfx.json")

    node_modules = proj / "node_modules"
    if TEMPLATE_NODE_MODULES.is_dir():
        # new_project.py ran with --no-install (no npm ci into the real
        # ~/.reel from a check). Point straight at the node_modules
        # tools/check.py's own step 3 left in the template so make_pkg.py's
        # typecheck step actually runs instead of installing its own.
        if node_modules.is_symlink() or node_modules.exists():
            if node_modules.is_symlink() or node_modules.is_file():
                node_modules.unlink()
            else:
                shutil.rmtree(node_modules)
        node_modules.symlink_to(TEMPLATE_NODE_MODULES)
        shutil.copy(REPO_ROOT / "lana-reel" / "template" / "tsconfig.json", proj / "tsconfig.json")
        print(f"== linked {TEMPLATE_NODE_MODULES} -> {node_modules}", file=sys.stderr)
    else:
        print(
            "!! template/node_modules not found — make_pkg.py's typecheck step will self-skip "
            "(run `npm ci` in template/ first for this script to actually compile anything)",
            file=sys.stderr,
        )

    print("== build.py", file=sys.stderr)
    result = run(SCRIPTS / "reel" / "build.py", [], cwd=proj, env={"REEL_PROJECT": str(proj)})
    if result.returncode != 0:
        print("!! build.py failed", file=sys.stderr)
        return result.returncode

    print("== make_pkg.py", file=sys.stderr)
    result = run(SCRIPTS / "lana" / "make_pkg.py", [], cwd=proj, env={"REEL_PROJECT": str(proj)})
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
