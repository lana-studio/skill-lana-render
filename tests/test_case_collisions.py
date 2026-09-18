"""tests/test_case_collisions.py — no two files that land in a Remotion
bundle may share a lowercased STEM (filename without extension).

Amendment (2026-09-17): the D17 v2 contract's generated graphics module was
first named `graphics.ts`. On a case-insensitive filesystem (macOS APFS by
default, Windows NTFS) a real `tsc -p lana-pkg/tsconfig.json` failed:
`TS1261: Already included file name '.../Graphics.ts' differs from file
name '.../graphics.ts' only in casing` plus `TS2614: Module './Graphics'
has no exported member 'Gfx'`. The mechanism: `import type { Gfx } from
"./Graphics"` is EXTENSIONLESS, so TypeScript tries candidate extensions
(.ts before .tsx) appended to the bare specifier; the candidate
"Graphics.ts" case-insensitively matched the real "graphics.ts" file before
TS ever got to try ".tsx" — the actual `Graphics.tsx` component was never
even considered. So the collision is a STEM collision ("Graphics" vs
"graphics"), not a full-filename collision (the extensions differ: .tsx vs
.ts) — comparing full filenames would have missed it entirely.

Because make_pkg.py copies EVERY project src/*.ts(x) file into
lana-pkg/src/ (which, for a real project, started life as a copy of
template/src/ — see new_project.py), the collision reached the pre-submit
typecheck gate itself: `!! typecheck failed` for every user on Mac or
Windows, while Linux CI (case-sensitive, no extension-guessing ambiguity)
stayed green and never saw it. The fix (rename to `gfx.ts`) closes the one
known instance; this test file is the backstop for the general rule and for
`scripts/lana/make_pkg.py`'s own `validate_no_case_collisions` guard.

Three cases, all comparing names from a LISTING (lower-cased stems), never
by asking the filesystem whether two paths resolve to the same file — a
filesystem probe only tells the truth on a case-insensitive filesystem, so
it would stay blind on Linux CI exactly where this bug was invisible
before. None of the three needs template/node_modules (no tsc involved
here at all — that's test_make_pkg_typecheck.py's job): this file must run,
and must be able to fail, on every platform including case-sensitive Linux
CI, which is deliberately the platform where the underlying filesystem bug
can never reproduce on its own.

1. template/src/ — the static listing this repo ships.
2. lana-pkg/src/ generated from a real project seeded off template/src/ (the
   actual scenario: copies + this script's own generated names, together)
   — via a real make_pkg.py subprocess run, no injection.
3. The same scenario with a `graphics.ts` injected back into the project's
   own src/ — the mutation-proof case: without it, this test file could
   only ever pass, which is exactly the kind of coverage this whole feature
   has learned not to trust. Injected via a real make_pkg.py subprocess run
   too, asserting the exact contract literal and exit 1.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from conftest import FIXTURES, REPO_ROOT, SCRIPTS, run

# Hallazgo 17 (2026-09-17, final amendment — no marker anymore, see
# conftest.py's pytest_sessionfinish): these tests never call
# require_guard_node_modules or otherwise skip — they were written from
# the start to need nothing but a directory listing (see the module
# docstring above, "None of the three needs template/node_modules"), which
# is what makes them immune to the exact silent-skip failure mode this
# whole amendment exists to close everywhere else. Nothing to register in
# tests/deferred_skips.py because nothing here ever skips.

TEMPLATE_SRC = REPO_ROOT / "lana-reel" / "template" / "src"


def stem_collisions(names: list[str]) -> dict[str, list[str]]:
    """{lowercased stem: [distinct original filenames]} for every stem that
    has more than one distinct filename — the same grouping
    scripts/lana/make_pkg.py's validate_no_case_collisions does, duplicated
    here deliberately (not imported) so this test exercises the CONTRACT
    (what a listing of names must satisfy), not today's implementation."""
    by_stem: dict[str, list[str]] = {}
    for name in names:
        by_stem.setdefault(Path(name).stem.lower(), []).append(name)
    return {stem: sorted(set(v)) for stem, v in by_stem.items() if len(set(v)) > 1}


def test_template_src_has_no_case_collisions():
    names = [f.name for f in TEMPLATE_SRC.glob("*.ts")] + [f.name for f in TEMPLATE_SRC.glob("*.tsx")]
    assert names, f"{TEMPLATE_SRC} is empty or missing — nothing to check"
    collisions = stem_collisions(names)
    assert collisions == {}, (
        f"case collision(s) in template/src/: {collisions} — "
        "two files with the same stem, different case and/or extension, "
        "will resolve ambiguously through an extensionless import"
    )


def _seed_project_from_template(proj: Path) -> None:
    """A real project directory seeded off the actual template/src/ this
    repo ships (not a synthetic fixture stand-in) — the same shape
    new_project.py produces, plus build.py's own plan/ritmo/graphics
    output and one proof window, so make_pkg.py can run for real. No
    node_modules, no tsc: this only exercises make_pkg.py's own
    validate_no_case_collisions + file assembly, never the typecheck step
    (which self-skips cleanly without node_modules — see
    test_make_pkg.py::test_typecheck_skipped_without_node_modules)."""
    (proj / "src").mkdir(parents=True, exist_ok=True)
    for f in TEMPLATE_SRC.glob("*.ts*"):
        shutil.copy(f, proj / "src" / f.name)
    shutil.copy(FIXTURES / "project.json", proj / "project.json")
    (proj / "src" / "plan.json").write_text(
        json.dumps({"fps": 30, "total": 30, "src": "clip", "segments": [], "captions": [], "lines": []}),
        encoding="utf-8",
    )
    (proj / "src" / "ritmo.json").write_text(
        json.dumps({
            "titles": [], "punch": [], "bw": [], "glitch": [], "closingMs": 0,
            "hookBanner": "", "hookTag": "", "hookEndMs": 0,
        }),
        encoding="utf-8",
    )
    (proj / "src" / "graphics.json").write_text("[]", encoding="utf-8")
    (proj / "lana-pkg").mkdir(parents=True, exist_ok=True)
    (proj / "lana-pkg" / "proofs.json").write_text(
        json.dumps([{"id": "Reel-proof-1", "label": "hook", "window": [0, 90]}]), encoding="utf-8",
    )


def _run_make_pkg(proj: Path):
    return run(SCRIPTS / "lana" / "make_pkg.py", ["--no-check"], cwd=proj, env={"REEL_PROJECT": str(proj)})


def test_generated_lana_pkg_src_has_no_case_collisions(tmp_path):
    """Case 2: copies (from the real template/src/) + this script's own
    generated names, together — the exact combination the bug shipped in."""
    proj = tmp_path / "proj"
    proj.mkdir()
    _seed_project_from_template(proj)

    result = _run_make_pkg(proj)
    assert result.returncode == 0, result.stderr

    dest = proj / "lana-pkg" / "src"
    names = [f.name for f in dest.glob("*.ts")] + [f.name for f in dest.glob("*.tsx")]
    assert names
    collisions = stem_collisions(names)
    assert collisions == {}, f"case collision(s) in the generated lana-pkg/src/: {collisions}"


def test_injected_graphics_ts_exits_1(tmp_path):
    """Case 3, the mutation-proof case: inject the exact file that shipped
    the real bug (a `graphics.ts` data module sitting next to the
    template's `Graphics.tsx` component) back into a project's src/, and
    assert make_pkg.py refuses it — the literal contract message, exit 1,
    BEFORE anything is written to lana-pkg/src/. Without this case, the two
    tests above could only ever pass (a listing that happens to have no
    collisions proves nothing about whether the check would catch one)."""
    proj = tmp_path / "proj"
    proj.mkdir()
    _seed_project_from_template(proj)
    (proj / "src" / "graphics.ts").write_text("export const x = 1;\n", encoding="utf-8")

    result = _run_make_pkg(proj)
    assert result.returncode == 1
    assert "case collision: Graphics.tsx vs graphics.ts — rename the data module" in result.stderr
    # "before anything is written" — the guard runs first in main(), so a
    # rejected run must not have touched lana-pkg/src/ at all.
    assert not (proj / "lana-pkg" / "src").exists()


def test_stem_collisions_helper_catches_same_stem_different_extension():
    """Direct check on the grouping helper itself: two files whose full
    names differ (different extensions) but whose STEM is the same case-
    insensitively must be flagged — the exact shape that shipped (.tsx vs
    .ts), which a full-filename lowercase compare would silently miss."""
    collisions = stem_collisions(["Graphics.tsx", "graphics.ts", "Root.tsx", "assets.ts"])
    assert collisions == {"graphics": ["Graphics.tsx", "graphics.ts"]}
