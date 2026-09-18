#!/usr/bin/env python3
"""scripts/lana/make_pkg.py — assemble lana-pkg/src/ for the bundle.

    python3 make_pkg.py [--no-check]

Inputs: src/**, project.json, lana/caps.sfx.json (optional),
lana-pkg/proofs.json, src/plan.json + src/ritmo.json + src/graphics.json.

- Copies every src/*.ts|*.tsx as-is into lana-pkg/src/ (no regex patching —
  the private skill's make-lana-pkg.py did this; the public template is
  written to need none). lana-pkg/src/ is wiped and rebuilt from scratch on
  every run (D17 v2) — the plan modules below replaced plain .json copies,
  and a stale file from an older run of this script must never survive into
  a bundle.
- Converts src/plan.json/ritmo.json/graphics.json into lana-pkg/src/
  plan.ts/ritmo.ts/gfx.ts (D17 v2 amendment — see below): each is
  `export default (<compact JSON>) as unknown as <Type>;` behind the same
  type import as its template/src/ placeholder. The graphics module is
  named `gfx.ts`, never `graphics.ts` — see the case-collision note below.
- Generates lana-pkg/src/Root.tsx: one `<Composition id="...">` for
  project.composition plus one per lana-pkg/proofs.json entry, all using the
  template's `ReelWindow` component. Every composition's `defaultProps`
  comes from the IMPORTED plan/ritmo/graphics .ts modules, never from
  lana_submit_render's `props` argument (D17 v2).

D16 (bug 9 — "every real reel rendered black"): the
gateway derives what it stages ONLY from what it can see. `assets/` is
staged from the submit's registered-asset map but VALIDATED against literal
`staticFile("assets/<key>.<ext>")` calls; `lib/` is staged ONLY from those
literals (a variable reference never gets staged at all). The old contract
had `assets.ts` resolve everything by variable and derived the submit's
`assets` map from a static-literal scan of that same variable-driven code —
the map came out empty, nothing got staged, `<Video>` broke, and the job
still reported SUCCEEDED. Fixed shape, mirrored 1:1 by the template's
placeholders (`assets-manifest.ts`, `library-manifest.ts`, `fonts-manifest.ts`
in `template/src/`):

- `_lib.project.ready_assets(project)`/`ready_custom_fonts(project)` are THE
  single definition of "ready" — make_submit.py's submit `assets` map uses
  the exact same functions, so the two cannot diverge again.
- `lana-pkg/src/assets-manifest.ts`: `export const ASSET_FILES:
  Record<string, string> = { "clip": staticFile("assets/clip.mp4"), ... }`
  — ONLY one literal per ready asset (`asset_id` set, ingest finished or
  N/A, `purpose != "bundle"`), nothing else. A prior version also always
  added two fixed `sfx_glitch`/`sfx_plop` entries for a Sfx.tsx fallback
  that calls `asset("sfx_glitch")`/`asset("sfx_plop")` directly when the
  harness's SFX pack isn't available — removed (2026-09-17): the gateway
  scans EVERY literal `staticFile("assets/<key>.<ext>")` in the submitted
  bundle and rejects the whole submit with VALIDATION_ERROR if the key
  isn't in the registered `assets` map, dead code or not, so these two
  always-present literals blocked every single submit. The fallback they
  served can't run anyway — `caps.py --check` already hard-requires
  `service_version >= 1.5.0`, the exact harness version the fallback exists
  for versions BELOW; a branch that can only ever not execute isn't a
  degrade path, it's dead surface. The corresponding Sfx.tsx branch is
  removed from the template separately.
- `lana-pkg/src/library-manifest.ts`: `export const LIB_FILES:
  Record<string, string> = { "lib/<id>.<ext>": staticFile("lib/<id>.<ext>"),
  ... }` — one literal per `project.library.items[]` entry, keyed by the
  FULL "lib/<id>.<ext>" path (this is the only way `lib/` ever gets staged).
- `lana-pkg/src/fonts-manifest.ts`: `export const FONT_FILES:
  Record<string, FontFile> = { ... }` — `file` is already a `staticFile(...)`
  result, over "assets/<key>.ttf" (a user's own upload, `ext` from
  `project.assets[key].ext`) or "lib/<id>.<ext>" (a shared-library font).
- `<ext>` = `project.assets[key].ext` ("mp4" if the asset has a proxy; else
  `RENDER_ASSET_EXT_BY_CONTENT_TYPE[content_type]`, see
  `_lib.limits.resolve_asset_ext`). Keys validated with `^[a-z0-9_-]{1,32}$`
  (the gateway's own key regex); exit 1 if a registered key doesn't match.
- Type contract (bug 8): every generated file declares EXACTLY the same
  annotation as its `template/src/` placeholder — never `as const`, never
  inferred (`assets-manifest.ts`/`library-manifest.ts`:
  `Record<string, string>`; `fonts-manifest.ts`: `Record<string, FontFile>`)
  — so a real project typechecks against the same shape `npm run check` gives
  the bare placeholder. `tests/test_make_pkg.py` asserts the exported
  declaration lines match byte-for-byte.
- Typecheck AT GENERATION TIME, not just informationally: after writing
  `lana-pkg/src/**`, writes `lana-pkg/tsconfig.json` (`extends:
  "../tsconfig.json"`, `include: ["src"]`, `compilerOptions.noEmit: true`)
  and runs `<node_modules>/.bin/tsc -p lana-pkg/tsconfig.json`. `typecheck:
  ok (N files)` or `!! typecheck failed:` + the errors verbatim and exit 1
  — there is no bundle without a green typecheck. `--no-check` skips it
  with an explicit, LOUD warning (`WARNING: typecheck skipped by
  --no-check — the bundle may fail on Lana`) — the only way this gate is
  ever skipped, and it says so unmistakably. **The gate never silently
  skips otherwise (hallazgo 17, 2026-09-17):** no `node_modules/` in the
  project used to print `typecheck skipped: run setup.py` and continue —
  this let the pre-submit gate quietly do nothing on a fresh clone (or any
  project not scaffolded by `new_project.py`, e.g. `examples/first-reel/`
  used in place). Now `provision_node_modules` symlinks
  `<project>/node_modules` from the shared one `setup.py` built (its path
  read from `~/.reel/setup.json`, never hardcoded) if the project doesn't
  have its own; if neither exists, exit 2 `!! node_modules not found — run
  setup.py (the typecheck gate cannot run without it)`. This is the
  pre-render gate — it compiles what actually gets sent, not the bare
  placeholder, and it always either runs for real or fails loudly.
- The literal scan across `lana-pkg/src/**` is validation only, never the
  source of any map (the source is always the registry via
  `_lib.project.ready_assets`/`ready_custom_fonts`): `assets/<key>.<ext>`
  must be a value in ASSET_FILES; `sfx/<name>.wav` must be a name in
  `lana/caps.sfx.json`; `lib/<id>.<ext>` must be a `project.library.items[]`
  file. Any other literal is `!!` (exit 1). A `staticFile(` call whose
  argument ISN'T a simple string literal (a variable or a template literal)
  is allowed only in `src/assets.ts`/`src/Sfx.tsx` — anywhere else is `!!`
  exit 1 (that's exactly the escalation-2 bug: a variable reference to
  `assets/`/`lib/` never gets staged).
- Writes `lana-pkg/files.json` ({path: content}, informative — the transfer
  is by bundle, not `files`) and `lana-pkg/manifest-summary.json`
  (`{assets: [keys], lib: [files], sfx: [names]}` — informative,
  cross-checked by make_submit.py for coherence, never itself the source of
  a map). `lana-pkg/used-assets.json` no longer exists (bug 9: "used" was
  the wrong question — the harness stages every registered asset whether or
  not the code happens to reference it).

D17 (bug 10, "still black after the asset-registry fix"): QA measured every
output at exactly 1.365 s = 40 frames = the placeholder's own
`total(30) + holdFrames(10)`, regardless of the real plan — proof the
composition was rendering with ITS DEFAULT PROPS, not the real one. Verified
chain: in bundle mode the gateway sends `props: {}` to the harness; the
harness's prepare step keeps the real bundle props in memory only; the
render step re-reads job.json from disk, where the gateway already wrote
`props: {}` — so `inputProps` is always empty by the time a bundle-mode
render actually runs, no matter what was zipped as `props.json`. This is a
harness bug (a hotfix is tracked separately); the fix works against prod as
it is TODAY: the plan travels inside the CODE instead, imported and passed
as `defaultProps`, with each proof composition overriding `render_window` on
its own copy of the imported plan. `lana-pkg/props.json` is no longer
written by build.py at all; make_bundle.py bundles a hardcoded
`props.json = {}` instead (the gateway still requires SOME object there if
the file exists).

D17 v2 (escalation 3, 2026-09-17 — "the gateway rejected the first cut"):
the first version of the fix above had `Root.tsx` do
`import planJson from "./plan.json"` and pass `planJson as unknown as Plan`.
A real `lana_submit_render` came back `VALIDATION_ERROR … unresolved_relative`
on `files['src/Root.tsx']`. Two facts, each independently verified, turned
out to cancel each other out: `.json` IS in the gateway's own
`_LOCAL_RESOLUTION_EXTENSIONS` (`render_imports.py:100`) — but
`check_imports` only resolves against `scan.code_files`
(`server.py:2424`), and that dict is populated ONLY from
`.ts/.tsx/.js/.jsx` (`bundle_scan.py:245-246`) — the exact same exclusion
that keeps `.json` out of the 256 KiB code budget also keeps it out of
import resolution. Fix: the plan now travels as GENERATED `.ts` MODULES,
never `.json`:

- `src/plan.json`/`ritmo.json`/`graphics.json` still exist (build.py keeps
  writing them — `check_captions.py`/`check_retention.py` read them
  directly) but this script converts each into a lana-pkg/src/<name>.ts
  module: `import type { Plan } from "./types";\nexport default (<compact
  JSON, separators=(",",":")>) as unknown as Plan;` (idem `ritmo.ts` ->
  `Ritmo`, `gfx.ts` -> `Gfx[]` imported from `./Graphics`, matching Root.tsx's
  own import of `Gfx`). Same shape as its `template/src/<name>.ts`
  placeholder — see the "generated ≡ placeholder" type contract below.
- `Root.tsx` imports these directly (`import plan from "./plan"`, never
  `"./plan.json"`) — `.ts` needs no `resolveJsonModule` and resolves cleanly
  against `scan.code_files`.
- Consequence: the plan NOW COUNTS against `RENDER_MAX_CODE_BYTES` (256 KiB)
  — it didn't as `.json`. This script sums and breaks down the code budget
  (template vs. each plan module) and fails BEFORE the submit if it would
  exceed it — see the code-budget section below.
- A stray `import x from "./x.json"` anywhere under `lana-pkg/src/` is
  rejected outright (`validate_no_json_imports` below) — the same failure
  the gateway would produce, caught for free instead of on a real submit.
- `lana-pkg/src/` is wiped before every regeneration so a `.json` written by
  an older version of this script can never linger into a bundle.

Amendment (2026-09-17, macOS/Windows-only regression): the graphics module
is `gfx.ts`, never `graphics.ts`. A real `tsc -p lana-pkg/tsconfig.json` on
a case-insensitive filesystem (macOS APFS by default, also Windows NTFS)
failed with `TS2614`/`TS1149`/`TS1261` — TypeScript's extensionless module
resolution for `import type { Gfx } from "./Graphics"` tries a `.ts`
candidate before `.tsx` and the OS matches `graphics.ts` case-insensitively,
so `"./Graphics"` resolved to the WRONG file (this script's own generated
data module, which has no named `Gfx` export). This script also copies
every `template/src/*.ts(x)` file into `lana-pkg/src/` (`copy_src` below),
so `Graphics.tsx` always lands right next to whatever this script names its
generated graphics module — the collision travels into the pre-submit
typecheck gate itself, breaking packaging for every Mac/Windows user while
Linux CI (case-sensitive) stayed green. `gfx.ts` (type `Gfx`, variable
`gfx`) doesn't collide with anything in `template/src/`. As a second,
general layer (not specific to this one pair): `validate_no_case_collisions`
below rejects ANY two files that would land in `lana-pkg/src/` differing
only by case, covering a future name clash this script's author didn't
anticipate the same way this one wasn't.

Exit codes: 0 ok, 1 a validation/typecheck failure, 2 missing template/project.
"""
from __future__ import annotations

import argparse
import json as _json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import io as _io  # noqa: E402
from _lib import limits as _limits  # noqa: E402
from _lib import project as _project  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSET_KEY_RE = re.compile(r"^[a-z0-9_-]{1,32}$")

# D17 v2: the code budget's warn threshold (contract: "> 200 KiB ->
# warning", "> 256 KiB (RENDER_MAX_CODE_BYTES) -> !! exit 1"). Not a gateway
# constant like _limits.RENDER_MAX_CODE_BYTES (the gateway has no "warn"
# concept) — this is this script's own early-heads-up margin, so it lives
# here rather than in the mirror file.
CODE_BUDGET_WARN_BYTES = 200 * 1024

# Any staticFile(...) call, argument captured raw (not yet classified as a
# string literal / template literal / variable — that happens in
# validate_static_files, which needs to tell the three apart).
STATIC_FILE_CALL_RE = re.compile(r"staticFile\(\s*([^)]*?)\s*\)")


def strip_comments(source: str) -> str:
    """Remove `//…` and `/*…*/` comments outside strings/template literals,
    preserving newlines (so nothing downstream needs line numbers to shift).
    Mirror of the gateway's own `_strip_comments`
    (`app/mcp/render_imports.py`) — without this, a comment that mentions
    `staticFile("assets/<key>.<ext>")` as documentation (this very file's
    own module docstring does) gets scanned as if it were code."""
    result: list[str] = []
    i = 0
    n = len(source)
    in_string: str | None = None
    while i < n:
        ch = source[i]
        if in_string:
            result.append(ch)
            if ch == "\\" and i + 1 < n:
                result.append(source[i + 1])
                i += 2
                continue
            if ch == in_string:
                in_string = None
            i += 1
            continue
        if ch in ("'", '"', "`"):
            in_string = ch
            result.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "/":
            j = source.find("\n", i)
            if j == -1:
                break
            i = j
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "*":
            j = source.find("*/", i + 2)
            if j == -1:
                break
            result.append("\n" * source.count("\n", i, j + 2))
            i = j + 2
            continue
        result.append(ch)
        i += 1
    return "".join(result)

# Files allowed to call staticFile() with a non-literal (variable/template)
# argument — the two sanctioned exemptions from the escalation-2 rule.
# "src/Sfx.tsx" for sfx/ (the harness stages the whole pack every job, so a
# variable reference is safe); "src/assets.ts" itself for its own internal
# `if (name.startsWith("sfx/")) return staticFile(name);` branch — it never
# touches assets/ or lib/ by variable, only sfx/, but the file-level
# exemption is simpler than parsing which branch a call sits in.
STATIC_FILE_VARIABLE_ALLOWED_FILES = frozenset({"src/assets.ts", "src/Sfx.tsx"})

ROOT_TSX_TEMPLATE = '''import {{ Composition, Sequence }} from "remotion";
import {{ Reel, holdFrames }} from "./Reel";
import type {{ Plan, Ritmo }} from "./types";
import type {{ Gfx }} from "./Graphics";
import plan from "./plan";
import ritmo from "./ritmo";
import gfx from "./gfx";

// Generated by make_pkg.py from project.json + lana-pkg/proofs.json — do not
// edit by hand. D17 v2: the plan travels INSIDE the code as generated .ts
// modules (plan.ts/ritmo.ts/gfx.ts — named gfx.ts, never graphics.ts, to
// avoid colliding with Graphics.tsx on a case-insensitive filesystem; each
// already cast `as unknown as <Type>` — see make_pkg.py), imported here and
// passed as defaultProps —
// never as lana_submit_render's `props` argument, and never as a `.json`
// import (a first cut of this file did `import planJson from "./plan.json"`
// and the gateway rejected the submit with VALIDATION_ERROR …
// unresolved_relative: check_imports only resolves .ts/.tsx/.js/.jsx). In
// bundle mode the harness also drops inputProps between prepare and render
// (job.json is re-read with the gateway's props: {{}}), so a plan sent as
// `props` never reaches calculateMetadata/render at all — this is why a
// prior version of this file rendered every composition at its placeholder's
// 30 + holdFrames(30) = 40 frames, regardless of what build.py computed.

export const ReelWindow: React.FC<{{ plan: Plan; ritmo: Ritmo; gfx: Gfx[] }}> = (p) => {{
  const [from] = p.plan.render_window ?? [0, 0];
  return <Sequence from={{-from}} layout="none"><Reel {{...p}} /></Sequence>;
}};

const meta = ({{ props }}: {{ props: {{ plan: Plan }} }}) => {{
  const w = props.plan.render_window;
  return {{ durationInFrames: w ? w[1] - w[0] : props.plan.total + holdFrames(props.plan) }};
}};

export const RemotionRoot: React.FC = () => (
  <>
{compositions}
  </>
);
'''

FINAL_COMPOSITION_TEMPLATE = '''    <Composition id="{comp_id}" component={{ReelWindow}} fps={{{fps}}} width={{{width}}} height={{{height}}}
      durationInFrames={{plan.total + holdFrames(plan)}}
      defaultProps={{{{ plan, ritmo, gfx }}}} calculateMetadata={{meta}} />'''

PROOF_COMPOSITION_TEMPLATE = '''    <Composition id="{comp_id}" component={{ReelWindow}} fps={{{fps}}} width={{{width}}} height={{{height}}}
      durationInFrames={{{duration}}}
      defaultProps={{{{ plan: {{ ...plan, render_window: [{window0}, {window1}] as [number, number] }}, ritmo, gfx }}}}
      calculateMetadata={{meta}} />'''


def generate_root_tsx(final_id: str, proofs: list[dict], project: dict) -> str:
    fps = project.get("fps", 30)
    width = project.get("width", 1080)
    height = project.get("height", 1920)
    parts = [FINAL_COMPOSITION_TEMPLATE.format(comp_id=final_id, fps=fps, width=width, height=height)]
    for p in proofs:
        w0, w1 = p["window"]
        parts.append(PROOF_COMPOSITION_TEMPLATE.format(
            comp_id=p["id"], fps=fps, width=width, height=height,
            duration=w1 - w0, window0=w0, window1=w1,
        ))
    return ROOT_TSX_TEMPLATE.format(compositions="\n".join(parts))


def asset_files_map(project: dict) -> dict[str, str]:
    """{key: "assets/<key>.<ext>"} for every ready registered asset —
    NOTHING else. This used to also seed two fixed sfx_glitch/sfx_plop
    entries for a dead Sfx.tsx fallback branch; removed (2026-09-17) because
    the gateway scans every staticFile("assets/<key>.<ext>") literal in the
    submitted bundle and rejects the WHOLE submit with VALIDATION_ERROR if
    the key isn't in the registered assets map — those two always-present
    literals blocked every single submit, dead code or not. The single
    source both generate_assets_manifest() and validate_static_files() use,
    so they can't disagree with each other inside this same script."""
    files: dict[str, str] = {}
    for key, entry in _project.ready_assets(project).items():
        if not ASSET_KEY_RE.match(key):
            _io.fail(f"assets.{key}: key does not match {ASSET_KEY_RE.pattern!r}", code=1)
        ext = entry.get("ext") or "mp4"
        files[key] = f"assets/{key}.{ext}"
    return files


def library_files_map(project: dict) -> dict[str, str]:
    """{"lib/<id>.<ext>": "lib/<id>.<ext>"} — LIB_FILES is keyed by the FULL
    literal path (asset.ts does `LIB_FILES[name]` with the whole "lib/..."
    string), unlike ASSET_FILES which is keyed by the bare asset key."""
    return {
        item["file"]: item["file"]
        for item in (project.get("library") or {}).get("items") or []
        if item.get("file")
    }


def _staticfile_import(has_entries: bool) -> str:
    # noUnusedLocals is on (tsconfig.json) — an unconditional `import {
    # staticFile }` fails TS6133 the moment a project has nothing to put in
    # the manifest (no custom fonts, no library picks — the common default
    # case). Only emit the import when at least one entry actually uses it.
    return 'import { staticFile } from "remotion";\n' if has_entries else ""


def generate_assets_manifest(asset_files: dict[str, str]) -> str:
    lines = "\n".join(f'  "{key}": staticFile("{path}"),' for key, path in asset_files.items())
    return (
        "// Generated by make_pkg.py from project.json — do not edit by hand.\n"
        f"{_staticfile_import(bool(asset_files))}\n"
        f"export const ASSET_FILES: Record<string, string> = {{\n{lines}\n}};\n"
    )


def generate_library_manifest(lib_files: dict[str, str]) -> str:
    lines = "\n".join(f'  "{key}": staticFile("{path}"),' for key, path in lib_files.items())
    return (
        "// Generated by make_pkg.py from project.json — do not edit by hand.\n"
        f"{_staticfile_import(bool(lib_files))}\n"
        f"export const LIB_FILES: Record<string, string> = {{\n{lines}\n}};\n"
    )


def generate_fonts_manifest(project: dict) -> str:
    assets = project.get("assets") or {}
    entries: dict[str, dict] = {}
    for key, font in _project.ready_custom_fonts(project).items():
        if not ASSET_KEY_RE.match(key):
            _io.fail(f"fonts.custom.{key}: key does not match {ASSET_KEY_RE.pattern!r}", code=1)
        ext = (assets.get(key) or {}).get("ext") or "ttf"
        entries[key] = {
            "family": font.get("family", key), "weight": font.get("weight", 400),
            "style": font.get("style", "normal"), "literal_path": f"assets/{key}.{ext}",
        }
    for item in (project.get("library") or {}).get("items") or []:
        if item.get("kind") == "font" and item.get("file"):
            entries[item["id"]] = {
                "family": item.get("family", item["id"]), "weight": item.get("weight", 400),
                "style": item.get("style", "normal"), "literal_path": item["file"],
            }
    lines = []
    for key, e in entries.items():
        lines.append(
            f'  "{key}": {{ family: {_json.dumps(e["family"])}, weight: {e["weight"]}, '
            f'style: {_json.dumps(e["style"])}, file: staticFile({_json.dumps(e["literal_path"])}) }},'
        )
    body = "\n".join(lines)
    return (
        "// Generated by make_pkg.py from project.json — do not edit by hand.\n"
        f"{_staticfile_import(bool(entries))}"
        'import type { FontFile } from "./types";\n\n'
        f"export const FONT_FILES: Record<string, FontFile> = {{\n{body}\n}};\n"
    )


# D17 v2: (json filename in project src/, generated .ts filename, its type
# import line, the `as unknown as <cast>` type). The graphics module is
# named "gfx.ts", NEVER "graphics.ts" (amendment, 2026-09-17): it imports
# `Gfx` from "./Graphics" (the component file), not "./types" — matching
# Root.tsx's own `import type { Gfx } from "./Graphics";`, unlike Plan/Ritmo
# which do live in types.ts — and "graphics.ts" collides with "Graphics.tsx"
# on a case-insensitive filesystem (see the module docstring). Each
# generated file's shape is frozen byte-for-byte against its
# template/src/<name>.ts placeholder — tests/test_make_pkg.py asserts it.
PLAN_MODULE_SPECS = (
    ("plan.json", "plan.ts", 'import type { Plan } from "./types";', "Plan"),
    ("ritmo.json", "ritmo.ts", 'import type { Ritmo } from "./types";', "Ritmo"),
    ("graphics.json", "gfx.ts", 'import type { Gfx } from "./Graphics";', "Gfx[]"),
)

# Every filename this script itself puts in lana-pkg/src/, independent of
# any project state — the three manifests, Root.tsx, and each generated
# plan module's own output name from PLAN_MODULE_SPECS (currently
# plan.ts/ritmo.ts/gfx.ts). Known statically, so the case-collision check
# below can run BEFORE touching disk at all.
GENERATED_FILENAMES = ("assets-manifest.ts", "library-manifest.ts", "fonts-manifest.ts", "Root.tsx") + tuple(
    ts_name for _, ts_name, _, _ in PLAN_MODULE_SPECS
)


def validate_no_case_collisions(src_dir: Path) -> list[str]:
    """Amendment (2026-09-17): everything that will land in lana-pkg/src/ —
    every project src/*.ts|*.tsx this script copies, PLUS its own generated
    filenames (GENERATED_FILENAMES) — checked together for a STEM (filename
    without extension) that collides case-insensitively with another one,
    before anything is written. Compares STEMS, not full filenames: the
    real tsc failure that shipped once already was `Graphics.tsx` vs
    `graphics.ts` — different extensions (.tsx vs .ts), so a full-filename
    compare would miss it entirely. The mechanism is TS's own extensionless
    module resolution: `import … from "./Graphics"` tries appending
    candidate extensions (.ts before .tsx) to the bare specifier, and on a
    case-insensitive filesystem (macOS APFS by default, Windows NTFS) the
    candidate "Graphics.ts" case-insensitively MATCHES the real file
    "graphics.ts" before TS ever gets to try ".tsx" — the actual reported
    error was `TS1261: … 'Graphics.ts' differs from … 'graphics.ts' only in
    casing`, `Graphics.tsx` itself never entered into it. So ANY two files
    under lana-pkg/src/ that share a lowercased stem are equally dangerous
    regardless of their extensions — every module here is only ever
    imported by its bare, extensionless specifier (Root.tsx does
    `"./plan"`, `"./ritmo"`, `"./gfx"`; the template's own Reel.tsx/Root.tsx
    do `"./Graphics"`), so extension-guessing is exactly what every import
    in this bundle goes through. And because this script copies EVERY
    template/src/*.ts(x) file into lana-pkg/src/ (copy_src below), the
    collision reached the pre-submit typecheck gate itself —
    `!! typecheck failed` for every user on Mac or Windows, while Linux CI
    (case-sensitive, no extension-guessing ambiguity) stayed green and never
    saw it. Renaming that one pair (-> gfx.ts) fixes the known instance;
    this function is the backstop against the next one, whatever it turns
    out to be. Compares stems from a LISTING (lower-cased, deduplicated),
    never by asking the filesystem whether two paths resolve to the same
    file — a filesystem probe only tells the truth on a case-insensitive
    filesystem, so it would stay blind on Linux CI exactly where this bug
    was invisible before; a listing-based check catches it everywhere,
    deterministically (see tests/test_case_collisions.py)."""
    names = [f.name for f in sorted(src_dir.glob("*.ts")) + sorted(src_dir.glob("*.tsx"))]
    names += list(GENERATED_FILENAMES)
    by_stem: dict[str, list[str]] = {}
    for name in names:
        by_stem.setdefault(Path(name).stem.lower(), []).append(name)
    errors = []
    for variants in by_stem.values():
        distinct = sorted(set(variants))
        if len(distinct) > 1:
            errors.append(f"case collision: {' vs '.join(distinct)} — rename the data module")
    return errors


def copy_src(src_dir: Path, dest_dir: Path) -> dict[str, str]:
    """Copies every src/*.ts|*.tsx as-is. D17 v2: lana-pkg/src/ is wiped by
    the caller right before this runs, so this never leaves a stale file
    (a .json from an older version of this script included) behind — every
    run reflects exactly the current src/ + the plan modules generated
    below, nothing else."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    for f in sorted(src_dir.glob("*.ts")) + sorted(src_dir.glob("*.tsx")):
        content = f.read_text(encoding="utf-8")
        (dest_dir / f.name).write_text(content, encoding="utf-8")
        files[f"src/{f.name}"] = content
    return files


def generate_plan_modules(src_dir: Path, dest_dir: Path) -> dict[str, str]:
    """Converts src/plan.json/ritmo.json/graphics.json (still written by
    build.py for check_captions.py/check_retention.py to read) into
    lana-pkg/src/plan.ts/ritmo.ts/gfx.ts — the shape Root.tsx imports
    directly (`import plan from "./plan"`). Never `.json`: the gateway's
    check_imports only resolves .ts/.tsx/.js/.jsx (D17 v2, see module
    docstring) — a `.json` import is rejected with VALIDATION_ERROR …
    unresolved_relative on a real submit, verified. JSON is compacted
    (separators=(",",":")) — this also directly reduces the code budget
    below, the whole plan now counting against it."""
    out: dict[str, str] = {}
    for json_name, ts_name, type_import, cast in PLAN_MODULE_SPECS:
        src_file = src_dir / json_name
        if not src_file.is_file():
            _io.fail(f"{src_file} not found — run build.py first", code=2)
        data = _io.read_json(src_file)
        compact = _json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        content = f"{type_import}\nexport default ({compact}) as unknown as {cast};\n"
        (dest_dir / ts_name).write_text(content, encoding="utf-8")
        out[f"src/{ts_name}"] = content
    return out


# D17 v2: a `.json` import anywhere under lana-pkg/src/ is exactly the bug
# the gateway rejected a real submit for (VALIDATION_ERROR …
# unresolved_relative) — catch it locally instead of on a real submit.
# Matches ESM `import … from "…json"` / `export … from "…json"` forms.
JSON_IMPORT_RE = re.compile(r'''from\s+["']([^"']+\.json)["']''')


def validate_no_json_imports(files: dict[str, str]) -> list[str]:
    errors = []
    for path, content in files.items():
        stripped = strip_comments(content)
        for match in JSON_IMPORT_RE.finditer(stripped):
            errors.append(
                f"{path}: import from {match.group(1)!r} — json imports are not "
                "resolvable by the Lana gateway (check_imports only resolves "
                ".ts/.tsx/.js/.jsx — use a generated .ts module instead)"
            )
    return errors


def validate_static_files(
    files: dict[str, str], asset_files: dict[str, str], sfx_names: set[str], library_paths: set[str],
) -> list[str]:
    errors = []
    asset_values = set(asset_files.values())
    for path, content in files.items():
        stripped = strip_comments(content)
        for match in STATIC_FILE_CALL_RE.finditer(stripped):
            arg = match.group(1)
            if len(arg) >= 2 and arg[0] in "\"'" and arg[-1] == arg[0]:
                literal = arg[1:-1]
                if literal.startswith("assets/"):
                    if literal not in asset_values:
                        errors.append(f"{path}: staticFile({literal!r}) not registered in ASSET_FILES")
                elif literal.startswith("sfx/"):
                    name = literal[len("sfx/"):].rsplit(".", 1)[0]
                    if sfx_names and name not in sfx_names:
                        errors.append(f"{path}: staticFile({literal!r}) not a name in lana/caps.sfx.json")
                elif literal.startswith("lib/"):
                    if literal not in library_paths:
                        errors.append(f"{path}: staticFile({literal!r}) not in project.library.items")
                else:
                    errors.append(f"{path}: unrecognized staticFile({literal!r})")
            elif path not in STATIC_FILE_VARIABLE_ALLOWED_FILES:
                # A variable or template-literal argument to staticFile()
                # outside the two sanctioned files is exactly the
                # escalation-2 bug: assets/ or lib/ resolved by variable
                # never gets staged by the harness.
                errors.append(
                    f"{path}: staticFile({arg}) has a non-literal argument — only "
                    f"{sorted(STATIC_FILE_VARIABLE_ALLOWED_FILES)} may do this (sfx/ only)"
                )
    return errors


# D17 v2: (breakdown label, lana-pkg/src/ path) for the three plan modules —
# these now count against RENDER_MAX_CODE_BYTES (they didn't as .json).
# Order matches the contract's example breakdown line: template first, then
# plan.ts, ritmo.ts, gfx.ts.
PLAN_MODULE_BUDGET_PATHS = tuple(f"src/{ts_name}" for _, ts_name, _, _ in PLAN_MODULE_SPECS)


def code_budget(files: dict[str, str]) -> tuple[list[tuple[str, int]], int]:
    """UTF-8 byte count per lana-pkg/src/ file, split into "template"
    (everything except the three generated plan modules) and each plan
    module by name — mirrors the gateway's own bundle_scan.py byte-counting
    rule (UTF-8 length) and file set (.ts/.tsx/.js/.jsx only, the same four
    extensions RENDER_MAX_CODE_BYTES applies to)."""
    per_module = {p: 0 for p in PLAN_MODULE_BUDGET_PATHS}
    template_bytes = 0
    for path, content in files.items():
        if Path(path).suffix not in _limits.BUNDLE_CODE_EXTENSIONS:
            continue
        size = len(content.encode("utf-8"))
        if path in per_module:
            per_module[path] = size
        else:
            template_bytes += size
    breakdown = [("template", template_bytes)] + [
        (Path(p).name, per_module[p]) for p in PLAN_MODULE_BUDGET_PATHS
    ]
    total = template_bytes + sum(per_module.values())
    return breakdown, total


def provision_node_modules(project_dir: Path) -> Path | None:
    """Hallazgo 17 (2026-09-17): the typecheck gate must never silently
    skip. If <project_dir>/node_modules already exists, use it. Otherwise
    symlink it from the shared node_modules setup.py built — the path is
    READ from ~/.reel/setup.json's own "node_modules" field (never
    hardcoded: setup.py's --home can move where it lives, and its
    setup.json always records where it actually put things; new_project.py
    predates this and hardcodes ~/.reel/template/node_modules directly,
    which is more fragile — not changed here, out of scope). Returns the
    node_modules dir to typecheck against, or None if nothing usable could
    be found or provisioned (the caller fails exit 2 — there is no
    "skipped" outcome)."""
    node_modules = project_dir / "node_modules"
    if node_modules.is_dir():
        return node_modules

    setup_json = Path("~/.reel/setup.json").expanduser()
    if not setup_json.is_file():
        return None
    try:
        setup_data = _io.read_json(setup_json)
    except (OSError, ValueError):
        return None
    shared = setup_data.get("node_modules")
    if not shared:
        return None
    shared_path = Path(shared).expanduser()
    if not shared_path.is_dir():
        return None

    node_modules.symlink_to(shared_path, target_is_directory=True)
    return node_modules


def run_typecheck(project_dir: Path, dest_dir: Path, no_check: bool) -> int:
    tsconfig = {
        "extends": "../tsconfig.json",
        "include": ["src"],
        "compilerOptions": {"noEmit": True},
    }
    _io.write_json(project_dir / "lana-pkg" / "tsconfig.json", tsconfig)

    if no_check:
        # Explicit and LOUD (hallazgo 17): never a silent "typecheck
        # skipped" — this exact wording is the one place it can happen,
        # deliberately findable by grepping for the literal string.
        _io.eprint("WARNING: typecheck skipped by --no-check — the bundle may fail on Lana")
        return 0

    node_modules = provision_node_modules(project_dir)
    if node_modules is None:
        _io.fail("node_modules not found — run setup.py (the typecheck gate cannot run without it)", code=2)

    tsc_bin = node_modules / ".bin" / "tsc"
    if not tsc_bin.is_file():
        _io.fail(f"{tsc_bin} not found — corrupt node_modules, re-run setup.py", code=2)

    result = subprocess.run(
        [str(tsc_bin), "-p", str((project_dir / "lana-pkg" / "tsconfig.json").relative_to(project_dir))],
        cwd=str(project_dir), capture_output=True, text=True,
    )
    if result.returncode != 0:
        output = (result.stdout + result.stderr).strip()
        _io.fail(f"typecheck failed:\n{output}", code=1)
    n_files = sum(1 for f in dest_dir.glob("*.ts")) + sum(1 for f in dest_dir.glob("*.tsx"))
    _io.eprint(f"typecheck: ok ({n_files} files)")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Assemble lana-pkg/src/ for the bundle.")
    parser.add_argument(
        "--no-check", action="store_true",
        help="Skip the tsc --noEmit typecheck gate (explicit opt-out; a warning is printed).",
    )
    args = parser.parse_args(argv)

    project_dir = _project.find_project()
    project = _project.load(project_dir)

    src_dir = project_dir / "src"
    if not src_dir.is_dir():
        _io.fail(f"{src_dir} not found", code=2)

    # Amendment (2026-09-17): before anything is written, reject any file
    # this run would put in lana-pkg/src/ (copied + generated) that
    # collides in case with another one — see validate_no_case_collisions.
    case_errors = validate_no_case_collisions(src_dir)
    if case_errors:
        _io.fail("\n".join(case_errors), code=1)

    proofs_path = project_dir / "lana-pkg" / "proofs.json"
    if not proofs_path.is_file():
        _io.fail(f"{proofs_path} not found — run build.py first", code=2)
    proofs = _io.read_json(proofs_path)

    dest_dir = project_dir / "lana-pkg" / "src"
    if dest_dir.exists():
        # D17 v2: wipe before rebuilding — a leftover file from an older run
        # of this script (a .json plan module, a manifest for an asset since
        # removed) must never silently survive into a bundle.
        shutil.rmtree(dest_dir)
    files = copy_src(src_dir, dest_dir)
    files.update(generate_plan_modules(src_dir, dest_dir))

    asset_files = asset_files_map(project)
    assets_manifest = generate_assets_manifest(asset_files)
    (dest_dir / "assets-manifest.ts").write_text(assets_manifest, encoding="utf-8")
    files["src/assets-manifest.ts"] = assets_manifest

    lib_files = library_files_map(project)
    library_manifest = generate_library_manifest(lib_files)
    (dest_dir / "library-manifest.ts").write_text(library_manifest, encoding="utf-8")
    files["src/library-manifest.ts"] = library_manifest

    fonts_manifest = generate_fonts_manifest(project)
    (dest_dir / "fonts-manifest.ts").write_text(fonts_manifest, encoding="utf-8")
    files["src/fonts-manifest.ts"] = fonts_manifest

    root_tsx = generate_root_tsx(project.get("composition", "Reel"), proofs, project)
    (dest_dir / "Root.tsx").write_text(root_tsx, encoding="utf-8")
    files["src/Root.tsx"] = root_tsx

    caps_sfx_path = project_dir / "lana" / "caps.sfx.json"
    sfx_names: set[str] = set()
    if caps_sfx_path.is_file():
        sfx_data = _io.read_json(caps_sfx_path)
        sfx_topic = sfx_data.get("sfx") or sfx_data  # unwrap the topic="sfx" envelope
        sfx_list = sfx_topic.get("sfx") or []
        sfx_names = {e["name"] for e in sfx_list}
    library_paths = set(lib_files.keys())

    errors = validate_static_files(files, asset_files, sfx_names, library_paths)
    errors += validate_no_json_imports(files)
    if errors:
        _io.fail("\n".join(errors), code=1)

    _io.write_json(project_dir / "lana-pkg" / "files.json", files)
    _io.write_json(
        project_dir / "lana-pkg" / "manifest-summary.json",
        {
            "assets": sorted(_project.ready_assets(project).keys()),
            "lib": sorted(library_paths),
            "sfx": sorted(sfx_names),
        },
    )

    total_kb = sum(len(v.encode("utf-8")) for v in files.values()) / 1024
    _io.eprint(f"files: {len(files)}, {total_kb:.1f} KB total, {len(asset_files)} assets in ASSET_FILES")

    # D17 v2: the plan now counts against RENDER_MAX_CODE_BYTES (256 KiB) —
    # print the breakdown every run, warn past 200 KiB, fail past 256 KiB
    # BEFORE the submit (the gateway would reject it with SPEC_TOO_LARGE;
    # this failure is free, a render job is not).
    breakdown, total_code_bytes = code_budget(files)
    budget_line = " · ".join(f"{name} {size / 1024:.1f} KB" for name, size in breakdown)
    budget_line += f" · total {total_code_bytes / 1024:.1f} KB of {_limits.RENDER_MAX_CODE_BYTES // 1024} KiB"
    if total_code_bytes > _limits.RENDER_MAX_CODE_BYTES:
        _io.fail(
            budget_line + "\n"
            "mitigations, in order: 1) compact JSON (already the default) "
            "2) drop unused fields such as captions[].confidence "
            "3) trim the SEL (the 180s duration cap already bounds the plan to "
            "~60-70 KB) 4) last resort: split into two reels\n"
            "the gateway would reject this with SPEC_TOO_LARGE",
            code=1,
        )
    if total_code_bytes > CODE_BUDGET_WARN_BYTES:
        _io.eprint(f"!! warning: {budget_line} — approaching RENDER_MAX_CODE_BYTES")
    else:
        _io.eprint(budget_line)

    return run_typecheck(project_dir, dest_dir, args.no_check)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
