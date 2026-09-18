"""tests/test_make_pkg.py — scripts/lana/make_pkg.py."""
from __future__ import annotations

import json
import re
import shutil

from conftest import SCRIPTS, run


def run_make_pkg(proj):
    """--no-check by default: this file tests manifest/validation/budget
    content, not the typecheck gate itself (that needs a real node_modules
    — hallazgo 17 made the gate FAIL, never silently skip, without one —
    and the fixture projects here use a minimal synthetic Reel.tsx that
    wouldn't typecheck against the real Reel/types/Graphics modules
    anyway). The typecheck gate itself — provisioning, the sabotage case,
    --no-check's own literal warning — is tests/test_make_pkg_typecheck.py's
    job, against the real template."""
    return run(SCRIPTS / "lana" / "make_pkg.py", ["--no-check"], cwd=proj, env={"REEL_PROJECT": str(proj)})


DEFAULT_PLAN = {"fps": 30, "total": 90, "src": "clip", "segments": [], "captions": [], "lines": []}
DEFAULT_RITMO = {
    "titles": [], "punch": [], "bw": [], "glitch": [], "closingMs": 0,
    "hookBanner": "", "hookTag": "", "hookEndMs": 0,
}
TWO_PROOF_WINDOWS = [
    {"id": "Reel-proof-1", "label": "hook", "window": [0, 90]},
    {"id": "Reel-proof-2", "label": "mid", "window": [10, 100]},
]


def seed(project_dir, fixtures_dir, reel_tsx: str, proofs: list, sfx=True):
    """D17 v2: the plan still starts as src/plan.json (+ ritmo.json/
    graphics.json) — build.py's own output, unchanged — but make_pkg.py now
    converts each into a lana-pkg/src/<name>.ts module (never copies the
    .json) for the generated Root.tsx to import. Never in
    lana-pkg/props.json, which make_pkg.py no longer reads at all.
    lana-pkg/proofs.json only records which window each proof composition
    renders."""
    (project_dir / "src").mkdir(parents=True, exist_ok=True)
    (project_dir / "src" / "Reel.tsx").write_text(reel_tsx, encoding="utf-8")
    (project_dir / "src" / "plan.json").write_text(json.dumps(DEFAULT_PLAN), encoding="utf-8")
    (project_dir / "src" / "ritmo.json").write_text(json.dumps(DEFAULT_RITMO), encoding="utf-8")
    (project_dir / "src" / "graphics.json").write_text(json.dumps([]), encoding="utf-8")
    (project_dir / "lana-pkg").mkdir(parents=True, exist_ok=True)
    (project_dir / "lana-pkg" / "proofs.json").write_text(json.dumps(proofs), encoding="utf-8")
    if sfx:
        shutil.copy(fixtures_dir / "gateway" / "caps.sfx.json", project_dir / "lana" / "caps.sfx.json")


def test_root_tsx_has_n_compositions(project_dir, fixtures_dir):
    seed(
        project_dir, fixtures_dir,
        'import { staticFile } from "remotion";\nexport const x = staticFile("assets/clip.mp4");\n',
        TWO_PROOF_WINDOWS,
    )
    result = run_make_pkg(project_dir)
    assert result.returncode == 0, result.stderr
    root_tsx = (project_dir / "lana-pkg" / "src" / "Root.tsx").read_text()
    assert root_tsx.count("<Composition") == 3
    assert 'id="Reel"' in root_tsx
    assert 'id="Reel-proof-1"' in root_tsx
    assert 'id="Reel-proof-2"' in root_tsx
    # D17 v2: defaultProps comes from the IMPORTED plan .ts modules, never
    # from a `props` argument and never from a `.json` import (the gateway
    # rejected that with VALIDATION_ERROR ... unresolved_relative) — each
    # proof composition overrides render_window on its own copy of that same
    # imported plan.
    assert 'import plan from "./plan";' in root_tsx
    assert 'import ritmo from "./ritmo";' in root_tsx
    # amendment 2026-09-17: "./gfx", never "./graphics" — "graphics.ts"
    # collides case-insensitively with the template's Graphics.tsx on
    # macOS/Windows (verified with a real tsc; see tests/test_case_collisions.py).
    assert 'import gfx from "./gfx";' in root_tsx
    # no ACTUAL .json import statement — a mention inside an explanatory `//`
    # comment (this generated file's own docstring names the rejected .json
    # form as history) doesn't count, so this only scans non-comment lines.
    code_lines = "\n".join(l for l in root_tsx.splitlines() if not l.strip().startswith("//"))
    assert '"./plan.json"' not in code_lines
    assert '"./ritmo.json"' not in code_lines
    assert '"./graphics.json"' not in code_lines
    assert '"./graphics"' not in code_lines
    assert "defaultProps={{ plan, ritmo, gfx }}" in root_tsx
    assert "render_window: [0, 90] as [number, number]" in root_tsx
    assert "render_window: [10, 100] as [number, number]" in root_tsx
    for f in ("plan.ts", "ritmo.ts", "gfx.ts"):
        assert (project_dir / "lana-pkg" / "src" / f).is_file()
    for f in ("plan.json", "ritmo.json", "graphics.json", "graphics.ts"):
        assert not (project_dir / "lana-pkg" / "src" / f).exists()


def test_unregistered_literal_exits_1(project_dir, fixtures_dir):
    seed(
        project_dir, fixtures_dir,
        'import { staticFile } from "remotion";\nexport const bad = staticFile("logos/x.svg");\n',
        [],
    )
    result = run_make_pkg(project_dir)
    assert result.returncode == 1
    assert "logos/x.svg" in result.stderr


def test_lib_ref_not_selected_exits_1(project_dir, fixtures_dir):
    seed(
        project_dir, fixtures_dir,
        'import { staticFile } from "remotion";\nexport const f = staticFile("lib/some-font.otf");\n',
        [],
    )
    result = run_make_pkg(project_dir)
    assert result.returncode == 1
    assert "lib/some-font.otf" in result.stderr


def test_lib_ref_selected_passes(project_dir, fixtures_dir):
    project = json.loads((project_dir / "project.json").read_text())
    project["library"]["items"] = [{"id": "some-font", "kind": "font", "file": "lib/some-font.otf", "license": "unknown"}]
    (project_dir / "project.json").write_text(json.dumps(project), encoding="utf-8")
    seed(
        project_dir, fixtures_dir,
        'import { staticFile } from "remotion";\nexport const f = staticFile("lib/some-font.otf");\n',
        [],
    )
    result = run_make_pkg(project_dir)
    assert result.returncode == 0, result.stderr


def test_assets_manifest_from_project_assets(project_dir, fixtures_dir):
    seed(
        project_dir, fixtures_dir,
        'import { staticFile } from "remotion";\nexport const x = staticFile("assets/clip.mp4");\n',
        [],
    )
    result = run_make_pkg(project_dir)
    assert result.returncode == 0, result.stderr
    manifest = (project_dir / "lana-pkg" / "src" / "assets-manifest.ts").read_text()
    # D16/bug 9: the manifest value is now a literal staticFile(...) call
    # over "assets/<key>.<ext>", not a plain path string — the gateway
    # validates that literal directly.
    assert '"clip": staticFile("assets/clip.mp4")' in manifest
    assert "Record<string, string>" in manifest
    assert "as const" not in manifest
    # used-assets.json is gone (bug 9: "used" was the wrong question — the
    # harness stages every registered asset regardless of code references).
    assert not (project_dir / "lana-pkg" / "used-assets.json").exists()
    summary = json.loads((project_dir / "lana-pkg" / "manifest-summary.json").read_text())
    assert summary["assets"] == ["clip"]


def test_asset_files_never_contains_keys_outside_the_registry(project_dir, fixtures_dir):
    """Reversal of the old fixed-sfx-fallback test (2026-09-17): a prior
    version of ASSET_FILES always carried two fixed "sfx_glitch"/"sfx_plop"
    entries for a Sfx.tsx fallback that isn't reachable once
    service_version >= 1.5.0 is required (caps.py --check already enforces
    that floor). The gateway scans EVERY staticFile("assets/<key>.<ext>")
    literal in the submitted bundle and rejects the WHOLE submit with
    VALIDATION_ERROR if the key isn't in the registered assets map — those
    two always-present, never-registered literals blocked every single
    submit for every project, dead code or not. ASSET_FILES must now
    contain ONLY keys that are actually in project.assets (or
    project.fonts.custom, which mirrors into project.assets too)."""
    seed(
        project_dir, fixtures_dir,
        'import { staticFile } from "remotion";\nexport const x = staticFile("assets/clip.mp4");\n',
        [],
    )
    result = run_make_pkg(project_dir)
    assert result.returncode == 0, result.stderr
    manifest = (project_dir / "lana-pkg" / "src" / "assets-manifest.ts").read_text()
    assert "sfx_glitch" not in manifest
    assert "sfx_plop" not in manifest
    # the fixture project registers exactly one ready asset ("clip") — the
    # manifest must carry that one and nothing beyond it.
    assert '"clip": staticFile("assets/clip.mp4")' in manifest
    keys_in_manifest = re.findall(r'^\s*"([^"]+)":', manifest, re.MULTILINE)
    assert keys_in_manifest == ["clip"]


def test_empty_fonts_and_library_manifests_omit_unused_staticfile_import(project_dir, fixtures_dir):
    """QA's finding on a real project with zero custom fonts and zero
    library picks (the common default case): fonts-manifest.ts and
    library-manifest.ts unconditionally imported staticFile even when the
    generated object had nothing that used it — tsconfig.json's
    noUnusedLocals then fails the whole typecheck with TS6133 on both
    files. The import must only appear when there's at least one entry."""
    seed(
        project_dir, fixtures_dir,
        'import { staticFile } from "remotion";\nexport const x = staticFile("assets/clip.mp4");\n',
        [],
    )
    result = run_make_pkg(project_dir)
    assert result.returncode == 0, result.stderr
    fonts_manifest = (project_dir / "lana-pkg" / "src" / "fonts-manifest.ts").read_text()
    library_manifest = (project_dir / "lana-pkg" / "src" / "library-manifest.ts").read_text()
    assert "staticFile" not in fonts_manifest  # no custom fonts, no library fonts registered
    assert "staticFile" not in library_manifest  # no project.library.items
    assert "Record<string, FontFile>" in fonts_manifest
    assert "Record<string, string>" in library_manifest


def test_missing_proofs_json_exits_2(project_dir, fixtures_dir):
    (project_dir / "src").mkdir(parents=True, exist_ok=True)
    (project_dir / "src" / "Reel.tsx").write_text("export const x = 1;\n", encoding="utf-8")
    result = run_make_pkg(project_dir)
    assert result.returncode == 2


def test_library_manifest_from_project_library(project_dir, fixtures_dir):
    project = json.loads((project_dir / "project.json").read_text())
    project["library"]["items"] = [{"id": "white-paper-elements-05", "kind": "overlay", "file": "lib/white-paper-elements-05.webm", "license": "unknown"}]
    (project_dir / "project.json").write_text(json.dumps(project), encoding="utf-8")
    seed(
        project_dir, fixtures_dir,
        'import { staticFile } from "remotion";\nexport const f = staticFile("lib/white-paper-elements-05.webm");\n',
        [],
    )
    result = run_make_pkg(project_dir)
    assert result.returncode == 0, result.stderr
    manifest = (project_dir / "lana-pkg" / "src" / "library-manifest.ts").read_text()
    assert '"lib/white-paper-elements-05.webm": staticFile("lib/white-paper-elements-05.webm")' in manifest
    assert "Record<string, string>" in manifest
    assert "as const" not in manifest
    summary = json.loads((project_dir / "lana-pkg" / "manifest-summary.json").read_text())
    assert summary["lib"] == ["lib/white-paper-elements-05.webm"]


def test_fonts_manifest_custom_font(project_dir, fixtures_dir):
    project = json.loads((project_dir / "project.json").read_text())
    project["fonts"]["custom"]["brand"] = {
        "file": "fonts/Brand-Bold.ttf", "family": "Brand", "weight": 700, "style": "normal",
        "asset_id": "00000000-0000-4000-8000-000000000501",
    }
    project["assets"]["brand"] = {
        "file": "fonts/Brand-Bold.ttf", "purpose": "font", "content_type": "font/ttf",
        "asset_id": "00000000-0000-4000-8000-000000000501", "ingest_status": None, "ext": "ttf",
    }
    (project_dir / "project.json").write_text(json.dumps(project), encoding="utf-8")
    seed(
        project_dir, fixtures_dir,
        'import { staticFile } from "remotion";\nexport const x = staticFile("assets/clip.mp4");\n',
        [],
    )
    result = run_make_pkg(project_dir)
    assert result.returncode == 0, result.stderr
    manifest = (project_dir / "lana-pkg" / "src" / "fonts-manifest.ts").read_text()
    assert '"brand": { family: "Brand", weight: 700, style: "normal", file: staticFile("assets/brand.ttf") }' in manifest
    assert "Record<string, FontFile>" in manifest
    assert "as const" not in manifest
    assert 'import type { FontFile } from "./types";' in manifest
    # a custom font is ALSO a registered asset (project.assets["brand"]), so
    # it must appear in ASSET_FILES too — that's the SAME literal path the
    # harness stages it under, just consulted by Fonts.tsx via a different
    # manifest.
    assets_manifest = (project_dir / "lana-pkg" / "src" / "assets-manifest.ts").read_text()
    assert '"brand": staticFile("assets/brand.ttf")' in assets_manifest


def test_invalid_asset_key_exits_1(project_dir, fixtures_dir):
    project = json.loads((project_dir / "project.json").read_text())
    project["assets"]["Not Valid!"] = {
        "purpose": "image", "content_type": "image/png", "ext": "png",
        "asset_id": "00000000-0000-4000-8000-000000000601", "ingest_status": None,
    }
    (project_dir / "project.json").write_text(json.dumps(project), encoding="utf-8")
    seed(
        project_dir, fixtures_dir,
        'import { staticFile } from "remotion";\nexport const x = staticFile("assets/clip.mp4");\n',
        [],
    )
    result = run_make_pkg(project_dir)
    assert result.returncode == 1
    assert "Not Valid!" in result.stderr


def test_variable_staticfile_outside_allowed_files_exits_1(project_dir, fixtures_dir):
    """The exact escalation-2 bug: staticFile(variable) for assets/ or lib/
    never gets staged by the harness, so make_pkg.py must reject it wherever
    it appears outside src/assets.ts and src/Sfx.tsx — this is the guard
    that keeps a 9th instance of the same bug from shipping again."""
    seed(
        project_dir, fixtures_dir,
        'import { staticFile } from "remotion";\nconst name = "assets/clip.mp4";\nexport const x = staticFile(name);\n',
        [],
    )
    result = run_make_pkg(project_dir)
    assert result.returncode == 1
    assert "non-literal argument" in result.stderr
    assert "src/Reel.tsx" in result.stderr


def test_variable_staticfile_allowed_in_assets_ts(project_dir, fixtures_dir):
    (project_dir / "src").mkdir(parents=True, exist_ok=True)
    (project_dir / "src" / "Reel.tsx").write_text("export const x = 1;\n", encoding="utf-8")
    (project_dir / "src" / "assets.ts").write_text(
        'import { staticFile } from "remotion";\n'
        "export const asset = (name: string) => name.startsWith(\"sfx/\") ? staticFile(name) : name;\n",
        encoding="utf-8",
    )
    (project_dir / "src" / "plan.json").write_text(json.dumps(DEFAULT_PLAN), encoding="utf-8")
    (project_dir / "src" / "ritmo.json").write_text(json.dumps(DEFAULT_RITMO), encoding="utf-8")
    (project_dir / "src" / "graphics.json").write_text(json.dumps([]), encoding="utf-8")
    (project_dir / "lana-pkg").mkdir(parents=True, exist_ok=True)
    (project_dir / "lana-pkg" / "proofs.json").write_text(json.dumps([]), encoding="utf-8")
    result = run_make_pkg(project_dir)
    assert result.returncode == 0, result.stderr


def test_no_check_writes_tsconfig_even_with_the_gate_off(project_dir, fixtures_dir):
    """The typecheck gate's own behavior (--no-check's literal warning,
    node_modules provisioning, the sabotage case) moved to
    tests/test_make_pkg_typecheck.py (hallazgo 17) — this only checks that
    --no-check still leaves lana-pkg/tsconfig.json behind (a real project
    can hand that to `npx tsc` by itself even when this script's own gate
    was skipped)."""
    seed(
        project_dir, fixtures_dir,
        'import { staticFile } from "remotion";\nexport const x = staticFile("assets/clip.mp4");\n',
        [],
    )
    result = run_make_pkg(project_dir)
    assert result.returncode == 0, result.stderr
    assert (project_dir / "lana-pkg" / "tsconfig.json").is_file()


def test_plan_modules_match_frozen_contract_shape(project_dir, fixtures_dir):
    """D17 v2's frozen contract: each generated plan module is
    `<type import>\\nexport default (<compact JSON>) as unknown as
    <Type>;\\n` — the same shape template/src/<name>.ts's own placeholder
    uses. remotion-template is rewriting that placeholder in parallel
    against this same frozen text; this is the signature-equality test meant
    to catch a divergence between the two sides — it must not be weakened to
    pass."""
    seed(
        project_dir, fixtures_dir,
        'import { staticFile } from "remotion";\nexport const x = staticFile("assets/clip.mp4");\n',
        [],
    )
    result = run_make_pkg(project_dir)
    assert result.returncode == 0, result.stderr

    plan_ts = (project_dir / "lana-pkg" / "src" / "plan.ts").read_text()
    lines = plan_ts.splitlines()
    assert lines[0] == 'import type { Plan } from "./types";'
    assert lines[1].startswith("export default (")
    assert lines[1].endswith(") as unknown as Plan;")
    payload = lines[1][len("export default ("):-len(") as unknown as Plan;")]
    assert json.loads(payload) == DEFAULT_PLAN
    assert ", " not in lines[1] and ": " not in lines[1]  # compact JSON, no spaces

    ritmo_ts = (project_dir / "lana-pkg" / "src" / "ritmo.ts").read_text()
    lines = ritmo_ts.splitlines()
    assert lines[0] == 'import type { Ritmo } from "./types";'
    assert lines[1].startswith("export default (")
    assert lines[1].endswith(") as unknown as Ritmo;")

    # amendment 2026-09-17: gfx.ts, never graphics.ts — see
    # tests/test_case_collisions.py and make_pkg.py's module docstring.
    gfx_ts = (project_dir / "lana-pkg" / "src" / "gfx.ts").read_text()
    assert not (project_dir / "lana-pkg" / "src" / "graphics.ts").exists()
    lines = gfx_ts.splitlines()
    assert lines[0] == 'import type { Gfx } from "./Graphics";'
    assert lines[1].startswith("export default (")
    assert lines[1].endswith(") as unknown as Gfx[];")


def test_json_import_injected_exits_1(project_dir, fixtures_dir):
    """The exact gateway rejection this generator now avoids by construction
    (D17 v2): `import … from "./x.json"` fails a real submit with
    VALIDATION_ERROR … unresolved_relative because check_imports only
    resolves .ts/.tsx/.js/.jsx — caught here instead, for free."""
    seed(
        project_dir, fixtures_dir,
        'import bad from "./something.json";\nexport const x = 1;\n',
        [],
    )
    result = run_make_pkg(project_dir)
    assert result.returncode == 1
    assert "json imports are not resolvable by the Lana gateway" in result.stderr
    assert "./something.json" in result.stderr


def test_code_budget_breakdown_printed(project_dir, fixtures_dir):
    seed(
        project_dir, fixtures_dir,
        'import { staticFile } from "remotion";\nexport const x = staticFile("assets/clip.mp4");\n',
        [],
    )
    result = run_make_pkg(project_dir)
    assert result.returncode == 0, result.stderr
    assert "template" in result.stderr
    assert "plan.ts" in result.stderr
    assert "ritmo.ts" in result.stderr
    assert "gfx.ts" in result.stderr
    assert "total" in result.stderr
    assert "of 256 KiB" in result.stderr


def _seed_plan_of_size(project_dir, fixtures_dir, pad_bytes: int):
    padded_plan = dict(DEFAULT_PLAN, pad="x" * pad_bytes)
    (project_dir / "src").mkdir(parents=True, exist_ok=True)
    (project_dir / "src" / "Reel.tsx").write_text(
        'import { staticFile } from "remotion";\nexport const x = staticFile("assets/clip.mp4");\n',
        encoding="utf-8",
    )
    (project_dir / "src" / "plan.json").write_text(json.dumps(padded_plan), encoding="utf-8")
    (project_dir / "src" / "ritmo.json").write_text(json.dumps(DEFAULT_RITMO), encoding="utf-8")
    (project_dir / "src" / "graphics.json").write_text(json.dumps([]), encoding="utf-8")
    (project_dir / "lana-pkg").mkdir(parents=True, exist_ok=True)
    (project_dir / "lana-pkg" / "proofs.json").write_text(json.dumps([]), encoding="utf-8")


def test_code_budget_over_256kib_exits_1(project_dir, fixtures_dir):
    """D17 v2: the plan now counts against RENDER_MAX_CODE_BYTES (it never
    did as .json) — make_pkg.py must fail BEFORE a submit the gateway would
    reject with SPEC_TOO_LARGE."""
    _seed_plan_of_size(project_dir, fixtures_dir, 257 * 1024)
    result = run_make_pkg(project_dir)
    assert result.returncode == 1
    assert "mitigations" in result.stderr
    assert "of 256 KiB" in result.stderr


def test_code_budget_under_256kib_passes(project_dir, fixtures_dir):
    """Mutation check for the test above: a plan comfortably under the cap
    must not trip the same gate."""
    _seed_plan_of_size(project_dir, fixtures_dir, 1024)
    result = run_make_pkg(project_dir)
    assert result.returncode == 0, result.stderr


def test_code_budget_over_200kib_warns_but_succeeds(project_dir, fixtures_dir):
    _seed_plan_of_size(project_dir, fixtures_dir, 201 * 1024)
    result = run_make_pkg(project_dir)
    assert result.returncode == 0, result.stderr
    assert "!! warning" in result.stderr
    assert "approaching RENDER_MAX_CODE_BYTES" in result.stderr


def test_stale_files_wiped_from_lana_pkg_src(project_dir, fixtures_dir):
    """D17 v2: lana-pkg/src/ is wiped before every regeneration — a leftover
    .json from an older run of this script (or any other stale file) must
    not survive a fresh make_pkg.py run."""
    seed(
        project_dir, fixtures_dir,
        'import { staticFile } from "remotion";\nexport const x = staticFile("assets/clip.mp4");\n',
        [],
    )
    dest = project_dir / "lana-pkg" / "src"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "plan.json").write_text("{}", encoding="utf-8")
    (dest / "stale.tsx").write_text("export const gone = 1;\n", encoding="utf-8")
    result = run_make_pkg(project_dir)
    assert result.returncode == 0, result.stderr
    assert not (dest / "plan.json").exists()
    assert not (dest / "stale.tsx").exists()
