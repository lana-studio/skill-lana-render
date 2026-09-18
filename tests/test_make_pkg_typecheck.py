"""tests/test_make_pkg_typecheck.py — tsc --noEmit against a REAL generated
bundle, not just the bare template placeholder.

Bug 8 (2026-09-17): CI/A5 only ever typechecked template/src/ with its empty
placeholder manifests (assets-manifest.ts, fonts-manifest.ts,
library-manifest.ts all `{}`) — never what make_pkg.py actually generates
once a project has registered assets and fonts. The generator and the
placeholder silently diverged (the generator used `as const`; the consumer
was written against the placeholder's looser declared type) and nothing
caught it until QA ran `npm run check` on a real project by hand.

This test is the fix for THAT root cause, per team-lead's explicit
instruction: "Sin ese test, el punto 1 se vuelve a romper en el próximo
cambio — es la causa raíz del octavo bug, no el síntoma." It seeds a real
project directory with template/src/ (the actual template this repo ships,
not a fixture stand-in), registers real assets/fonts/library items, runs
make_pkg.py for real, and typechecks the real output with the real tsc the
template's own node_modules ships.

Hallazgo 17 (2026-09-17, final amendment — supersedes this file's own
earlier `pytestmark = pytest.mark.skipif(...)` AND its intermediate
`pytestmark = pytest.mark.guard` replacement): this file's own docstring
used to say "Skipped (not failed) when template/ or its node_modules
aren't present next to this repo" — that was written intention, not an
oversight, and it's reverted on purpose. Every test here MUST NOT silently
skip when template/node_modules is missing — that was the exact silent-skip
that let the graphics.ts/Graphics.tsx case collision ship unnoticed (see
tests/test_case_collisions.py). `require_guard_node_modules` (conftest.py)
FAILS instead, with the contract's literal message, unless
REEL_GUARD_ALLOW_SKIP=1 is set locally — and there is no marker anymore:
tests/conftest.py's pytest_sessionfinish checks every skip in the whole
suite against tests/deferred_skips.py's allowlist regardless of mechanism
or marker, which is what closed the blind spot a marker-based version of
this same idea had (a THIRD skip mechanism, asleep in test_styles.py,
would have been invisible to `-m guard` selection too).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

from conftest import REPO_ROOT, SCRIPTS, require_guard_node_modules

TEMPLATE_DIR = REPO_ROOT / "lana-reel" / "template"
TEMPLATE_NODE_MODULES = TEMPLATE_DIR / "node_modules"


def _seed_real_template_project(proj) -> None:
    (proj / "src").mkdir(parents=True, exist_ok=True)
    for f in (TEMPLATE_DIR / "src").glob("*.ts*"):
        shutil.copy(f, proj / "src" / f.name)
    # new_project.py symlinks node_modules rather than copying it (it can be
    # hundreds of MB) — same approach here.
    os.symlink(TEMPLATE_NODE_MODULES, proj / "node_modules")
    shutil.copy(TEMPLATE_DIR / "tsconfig.json", proj / "tsconfig.json")

    project = json.loads((proj / "project.json").read_text())
    project["assets"]["card1"] = {
        "file": "assets/card1.png", "purpose": "image", "content_type": "image/png",
        "asset_id": "00000000-0000-4000-8000-000000000701", "ingest_status": None, "ext": "png",
    }
    project["assets"]["brand"] = {
        "file": "fonts/Brand-Bold.ttf", "purpose": "font", "content_type": "font/ttf",
        "asset_id": "00000000-0000-4000-8000-000000000702", "ingest_status": None, "ext": "ttf",
    }
    project["fonts"]["custom"]["brand"] = {
        "family": "Brand", "weight": 700, "style": "normal",
        "asset_id": "00000000-0000-4000-8000-000000000702",
    }
    project["library"]["items"] = [{
        "id": "white-paper-elements-05", "kind": "overlay", "file": "lib/white-paper-elements-05.webm",
        "license": "unknown", "attribution_required": False, "reason": "texture behind the title",
    }]
    (proj / "project.json").write_text(json.dumps(project), encoding="utf-8")

    # D17 v2: build.py's own output format is unchanged (still src/*.json —
    # check_captions.py/check_retention.py read these directly); make_pkg.py
    # is what converts them into the lana-pkg/src/*.ts modules Root.tsx
    # actually imports, never `props` and never a `.json` import.
    (proj / "src" / "plan.json").write_text(
        json.dumps({"fps": 30, "total": 90, "src": "clip", "segments": [], "captions": [], "lines": []}),
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


def test_generated_bundle_with_real_assets_and_fonts_typechecks(tmp_path):
    """The exact regression: a project with registered assets, a custom
    font, and a library item, run through the REAL template + the REAL
    generator, must satisfy the REAL tsc — not the bare placeholder."""
    require_guard_node_modules(TEMPLATE_NODE_MODULES, "template/node_modules")

    proj = tmp_path / "proj"
    proj.mkdir()
    shutil.copy(REPO_ROOT / "tests" / "fixtures" / "project.json", proj / "project.json")
    _seed_real_template_project(proj)

    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "lana" / "make_pkg.py")],
        cwd=str(proj), capture_output=True, text=True,
        env={**os.environ, "REEL_PROJECT": str(proj)},
    )
    assert result.returncode == 0, f"make_pkg.py failed:\n{result.stdout}\n{result.stderr}"
    # make_pkg.py's own internal typecheck-at-generation-time step is what's
    # actually load-bearing here (it ran tsc because node_modules exists) —
    # assert it actually ran and passed, not just that make_pkg.py exited 0
    # for some unrelated reason.
    assert "typecheck: ok" in result.stderr, result.stderr
    assert "typecheck skipped" not in result.stderr  # hallazgo 17: this string no longer exists at all

    manifest = (proj / "lana-pkg" / "src" / "assets-manifest.ts").read_text()
    assert '"card1": staticFile("assets/card1.png")' in manifest
    assert '"brand": staticFile("assets/brand.ttf")' in manifest
    fonts_manifest = (proj / "lana-pkg" / "src" / "fonts-manifest.ts").read_text()
    assert '"brand"' in fonts_manifest
    library_manifest = (proj / "lana-pkg" / "src" / "library-manifest.ts").read_text()
    assert '"lib/white-paper-elements-05.webm"' in library_manifest


def test_generated_bundle_independently_passes_tsc(tmp_path):
    """Belt-and-suspenders over the test above: run tsc directly ourselves
    against lana-pkg/src (with --no-check so make_pkg.py's own internal run
    doesn't mask a difference between the two invocations), so this test
    doesn't only prove make_pkg.py's internal call works — it proves the
    OUTPUT is independently valid TypeScript, which is what a human running
    `<node_modules>/.bin/tsc -p lana-pkg/tsconfig.json` by hand would also
    see."""
    require_guard_node_modules(TEMPLATE_NODE_MODULES, "template/node_modules")

    proj = tmp_path / "proj"
    proj.mkdir()
    shutil.copy(REPO_ROOT / "tests" / "fixtures" / "project.json", proj / "project.json")
    _seed_real_template_project(proj)

    gen = subprocess.run(
        [sys.executable, str(SCRIPTS / "lana" / "make_pkg.py"), "--no-check"],
        cwd=str(proj), capture_output=True, text=True,
        env={**os.environ, "REEL_PROJECT": str(proj)},
    )
    assert gen.returncode == 0, f"make_pkg.py failed:\n{gen.stdout}\n{gen.stderr}"

    tsc = proj / "node_modules" / ".bin" / "tsc"
    result = subprocess.run(
        [str(tsc), "-p", "lana-pkg/tsconfig.json"],
        cwd=str(proj), capture_output=True, text=True,
    )
    assert result.returncode == 0, f"tsc failed:\n{result.stdout}\n{result.stderr}"


def test_sabotaged_as_const_manifest_fails_typecheck(tmp_path):
    """The regression this whole guard exists to prevent (bug 8): the
    generator once emitted `as const` on ASSET_FILES, which infers a
    narrow, literal-keyed type instead of the placeholder's declared
    `Record<string, string>` — assets.ts's `ASSET_FILES[name]` (a `string`
    variable) then fails to typecheck against that narrower type. This
    can't be tested by asking make_pkg.py to regenerate (it never emits
    `as const` itself — tests/test_make_pkg.py already asserts that
    passively, `assert "as const" not in manifest`); instead a real,
    otherwise-clean generated bundle is hand-sabotaged exactly the way that
    regression would look, and a real, INDEPENDENT tsc run (not
    make_pkg.py's own internal call, which would just regenerate and
    overwrite the sabotage) must fail on it. Without this case, the
    passive `assert "as const" not in manifest` checks only prove today's
    generator behaves — never that the type contract they're guarding
    actually matters."""
    require_guard_node_modules(TEMPLATE_NODE_MODULES, "template/node_modules")

    proj = tmp_path / "proj"
    proj.mkdir()
    shutil.copy(REPO_ROOT / "tests" / "fixtures" / "project.json", proj / "project.json")
    _seed_real_template_project(proj)

    gen = subprocess.run(
        [sys.executable, str(SCRIPTS / "lana" / "make_pkg.py"), "--no-check"],
        cwd=str(proj), capture_output=True, text=True,
        env={**os.environ, "REEL_PROJECT": str(proj)},
    )
    assert gen.returncode == 0, f"make_pkg.py failed:\n{gen.stdout}\n{gen.stderr}"

    manifest_path = proj / "lana-pkg" / "src" / "assets-manifest.ts"
    original = manifest_path.read_text()
    assert "export const ASSET_FILES: Record<string, string> = {" in original
    sabotaged = original.replace(
        "export const ASSET_FILES: Record<string, string> = {",
        "export const ASSET_FILES = {",
    ).rstrip("\n")
    assert sabotaged.endswith("};")
    sabotaged = sabotaged[:-1] + " as const;\n"  # the exact bug 8 shape
    manifest_path.write_text(sabotaged, encoding="utf-8")

    tsc = proj / "node_modules" / ".bin" / "tsc"
    result = subprocess.run(
        [str(tsc), "-p", "lana-pkg/tsconfig.json"],
        cwd=str(proj), capture_output=True, text=True,
    )
    assert result.returncode != 0, "a narrowed `as const` manifest must fail typecheck, not pass it"
    assert "error TS" in (result.stdout + result.stderr)


def test_no_check_prints_loud_warning_and_exits_0(tmp_path):
    """--no-check is the ONLY way the typecheck gate is ever skipped
    (hallazgo 17) — and it must say so unmistakably, not just quietly
    return 0. Doesn't need node_modules at all — that's the point of this
    flag — so no require_guard_node_modules call."""
    proj = tmp_path / "proj"
    proj.mkdir()
    shutil.copy(REPO_ROOT / "tests" / "fixtures" / "project.json", proj / "project.json")
    (proj / "src").mkdir(parents=True, exist_ok=True)
    (proj / "src" / "Reel.tsx").write_text(
        'import { staticFile } from "remotion";\nexport const x = staticFile("assets/clip.mp4");\n',
        encoding="utf-8",
    )
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
    (proj / "lana-pkg" / "proofs.json").write_text("[]", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "lana" / "make_pkg.py"), "--no-check"],
        cwd=str(proj), capture_output=True, text=True,
        env={**os.environ, "REEL_PROJECT": str(proj)},
    )
    assert result.returncode == 0, result.stderr
    assert "WARNING: typecheck skipped by --no-check — the bundle may fail on Lana" in result.stderr
    assert (proj / "lana-pkg" / "tsconfig.json").is_file()


def _seed_minimal_project(proj) -> None:
    shutil.copy(REPO_ROOT / "tests" / "fixtures" / "project.json", proj / "project.json")
    (proj / "src").mkdir(parents=True, exist_ok=True)
    (proj / "src" / "Reel.tsx").write_text("export const x = 1;\n", encoding="utf-8")
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
    (proj / "lana-pkg" / "proofs.json").write_text("[]", encoding="utf-8")


def test_provisions_node_modules_from_reel_home_and_typechecks(tmp_path):
    """Hallazgo 17's actual fix, case "en sitio": a project with no
    node_modules of its own (e.g. a copy of examples/first-reel/ never run
    through new_project.py) still typechecks for real, by symlinking the
    shared node_modules at a SIMULATED ~/.reel/template (HOME pointed at a
    tmp dir, already up to date so no npm ci runs), not the real one on
    this machine, so the test is deterministic regardless of what this
    developer's ~/.reel holds."""
    require_guard_node_modules(TEMPLATE_NODE_MODULES, "template/node_modules")

    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "src").mkdir(parents=True, exist_ok=True)
    for f in (TEMPLATE_DIR / "src").glob("*.ts*"):
        shutil.copy(f, proj / "src" / f.name)
    shutil.copy(TEMPLATE_DIR / "tsconfig.json", proj / "tsconfig.json")
    shutil.copy(REPO_ROOT / "tests" / "fixtures" / "project.json", proj / "project.json")
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
    # NOT symlinked here on purpose — no project-local node_modules.

    fake_home = tmp_path / "fake-home"
    shared = fake_home / ".reel" / "template"
    shared.mkdir(parents=True)
    for name in ("package.json", "package-lock.json"):
        shutil.copy(TEMPLATE_DIR / name, shared / name)
    (shared / "node_modules").symlink_to(TEMPLATE_NODE_MODULES, target_is_directory=True)

    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "lana" / "make_pkg.py")],
        cwd=str(proj), capture_output=True, text=True,
        env={**os.environ, "REEL_PROJECT": str(proj), "HOME": str(fake_home)},
    )
    assert result.returncode == 0, f"make_pkg.py failed:\n{result.stdout}\n{result.stderr}"
    assert "typecheck: ok" in result.stderr, result.stderr
    node_modules_link = proj / "node_modules"
    assert node_modules_link.is_symlink()
    assert node_modules_link.resolve() == TEMPLATE_NODE_MODULES.resolve()


def test_no_node_modules_and_no_npm_exits_2(tmp_path):
    """The hard-failure half of hallazgo 17: no project node_modules, no
    shared one in ~/.reel, and no npm to install it — exit 2 with the
    contract's exact literal, never a silent "skipped". Uses an isolated
    fake, EMPTY HOME and a PATH without npm so this is deterministic (and
    never hits the network) regardless of this machine — doesn't need
    template/node_modules either, so no require_guard_node_modules call."""
    proj = tmp_path / "proj"
    proj.mkdir()
    _seed_minimal_project(proj)

    empty_home = tmp_path / "empty-home"
    empty_home.mkdir()
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()

    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "lana" / "make_pkg.py")],
        cwd=str(proj), capture_output=True, text=True,
        env={**os.environ, "REEL_PROJECT": str(proj), "HOME": str(empty_home), "PATH": str(empty_bin)},
    )
    assert result.returncode == 2
    assert "!! npm not found on PATH" in result.stderr
    assert "!! node_modules not found — npm ci could not install the template (the typecheck gate cannot run without it)" in result.stderr
    assert not (proj / "node_modules").exists()
