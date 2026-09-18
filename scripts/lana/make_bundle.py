#!/usr/bin/env python3
"""scripts/lana/make_bundle.py — zip lana-pkg/src/ + an empty props.json for lana_submit_render(bundle=...).

    python3 make_bundle.py

Inputs: lana-pkg/src/** (from make_pkg.py — plan.ts/ritmo.ts/gfx.ts
since D17 v2; NO .json under src/ at all). Output: lana-pkg/bundle.zip
(deterministic — every entry gets the fixed timestamp 1980-01-01 so
re-running with the same inputs produces the same sha256) +
lana-pkg/bundle.sha256.

D17 ("still black after the asset-registry fix"): in bundle mode the
harness drops `props` between prepare and render (the gateway re-sends
`props: {}` on the internal job.json it re-reads at render time, regardless
of what was zipped) — a real plan sent as `props` never reaches the render
at all. The plan now travels INSIDE lana-pkg/src/ (imported by the
generated Root.tsx, D16/D17 in make_pkg.py), so `props.json` in the bundle
is hardcoded to `{}` here — never read from disk, never anything but an
empty object (the gateway still requires SOME object at that path if it's
going to accept the entry at all).

D17 v2 (escalation 3, 2026-09-17): a first cut had the plan travel as
`plan.json`/`ritmo.json`/`graphics.json`, imported from Root.tsx — a real
`lana_submit_render` was rejected with VALIDATION_ERROR … unresolved_relative
because the gateway's `check_imports` only resolves `.ts/.tsx/.js/.jsx`
imports, never `.json` (`bundle_scan.py`/`server.py`, see make_pkg.py's
module docstring). make_pkg.py now generates `plan.ts`/`ritmo.ts`/
`gfx.ts` instead — which means the plan **now counts** against the
code budget below (it didn't as `.json`); a stray `.json` under `src/` is
rejected here too (defense in depth — make_pkg.py already wipes and
regenerates `lana-pkg/src/` from scratch every run, so this should never
actually fire).

Amendment (2026-09-17): the graphics module is `gfx.ts`, never
`graphics.ts` — `graphics.ts` collides case-insensitively with the
template's `Graphics.tsx` component on macOS/Windows, breaking the
pre-submit typecheck for every user there (see make_pkg.py's module
docstring and `validate_no_case_collisions`; also guarded by
`tests/test_case_collisions.py`).

Validates against the gateway's own bundle limits (mirrored in
_lib.limits, from mcp-gateway's BUNDLE_MAX_*/RENDER_MAX_*): every entry's
extension is in the 13-extension allowlist, at most 1000 entries, compressed
<= 20 MiB, uncompressed <= 100 MiB, no `.json` under `src/` (D17 v2), and —
counting ONLY code (.ts/.tsx/.js/.jsx, the plan modules included) — at most
RENDER_MAX_FILES (64) files and RENDER_MAX_CODE_BYTES (256 KiB). `!!` and
exit 1 on any violation — better to fail here than burn a render job on a
bundle the gateway would reject.

Registers project.assets["bundle"] = {file, purpose: "bundle", sha256,
asset_id: null} — a changed sha256 invalidates any previously registered
asset_id (a new bundle needs a new upload; make_submit.py's idempotency_key
is built from this sha8, so a content change naturally gets a fresh key too).
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import io as _io  # noqa: E402
from _lib import limits as _limits  # noqa: E402
from _lib import project as _project  # noqa: E402

FIXED_DATE_TIME = (1980, 1, 1, 0, 0, 0)


def collect_entries(src_dir: Path) -> list[Path]:
    return sorted(p for p in src_dir.rglob("*") if p.is_file())


EMPTY_PROPS_BYTES = b"{}"


def validate_entries(entries: list[Path], src_dir: Path) -> list[str]:
    errors = []
    if len(entries) > _limits.BUNDLE_MAX_ENTRIES:
        errors.append(f"{len(entries)} entries exceeds BUNDLE_MAX_ENTRIES ({_limits.BUNDLE_MAX_ENTRIES})")
    for p in entries:
        if p.suffix.lower() not in _limits.BUNDLE_ALLOWED_EXTENSIONS:
            errors.append(f"{p}: extension {p.suffix!r} not allowed (allowlist: {sorted(_limits.BUNDLE_ALLOWED_EXTENSIONS)})")
    # D17 v2: .json under src/ must never happen — make_pkg.py converts
    # plan/ritmo/graphics into .ts modules precisely because the gateway
    # can't resolve a .json *import*; a .json file sitting in the bundle
    # unused is harmless to the gateway itself, but it's a sign lana-pkg/src/
    # is stale (an older make_pkg.py run, or a hand-edit) — reject it rather
    # than ship a bundle nothing in Root.tsx actually reads.
    for p in entries:
        if p.suffix.lower() == ".json":
            errors.append(
                f"{p.relative_to(src_dir)}: .json under lana-pkg/src/ is stale (D17 v2 — the plan "
                "travels as generated .ts modules) — re-run make_pkg.py"
            )
    # D17 v2: only code counts against RENDER_MAX_FILES/RENDER_MAX_CODE_BYTES
    # — and since D17 v2, that now INCLUDES plan.ts/ritmo.ts/gfx.ts
    # (they didn't count as .json; the whole reason the gateway forced this
    # move to .ts is that check_imports never resolved .json in the first
    # place, so there was never a way to keep them uncounted).
    code_entries = [p for p in entries if p.suffix.lower() in _limits.BUNDLE_CODE_EXTENSIONS]
    code_bytes = sum(p.stat().st_size for p in code_entries)
    if len(code_entries) > _limits.RENDER_MAX_FILES:
        errors.append(f"{len(code_entries)} code files exceeds RENDER_MAX_FILES ({_limits.RENDER_MAX_FILES})")
    if code_bytes > _limits.RENDER_MAX_CODE_BYTES:
        errors.append(f"{code_bytes} bytes of code exceeds RENDER_MAX_CODE_BYTES ({_limits.RENDER_MAX_CODE_BYTES})")
    return errors


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Zip lana-pkg/src/ + an empty props.json into a deterministic bundle.")
    args = parser.parse_args(argv)

    project_dir = _project.find_project()
    project = _project.load(project_dir)

    src_dir = project_dir / "lana-pkg" / "src"
    if not src_dir.is_dir():
        _io.fail(f"{src_dir} not found — run make_pkg.py first", code=2)

    entries = collect_entries(src_dir)
    # D17: props.json in the bundle is always {} — the plan travels inside
    # lana-pkg/src/*.json instead (see the module docstring). Never read
    # from disk; there is nothing to read anymore.
    props_bytes = EMPTY_PROPS_BYTES

    errors = validate_entries(entries, src_dir)
    if errors:
        _io.fail("\n".join(errors), code=1)

    out_path = project_dir / "lana-pkg" / "bundle.zip"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    uncompressed_total = len(props_bytes)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in entries:
            data = p.read_bytes()
            uncompressed_total += len(data)
            arcname = f"src/{p.relative_to(src_dir).as_posix()}"
            info = zipfile.ZipInfo(arcname, date_time=FIXED_DATE_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data)
        info = zipfile.ZipInfo("props.json", date_time=FIXED_DATE_TIME)
        info.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(info, props_bytes)

    compressed_bytes = out_path.stat().st_size
    if compressed_bytes > _limits.BUNDLE_MAX_BYTES:
        out_path.unlink()
        _io.fail(f"bundle {compressed_bytes} bytes exceeds BUNDLE_MAX_BYTES ({_limits.BUNDLE_MAX_BYTES})", code=1)
    if uncompressed_total > _limits.BUNDLE_MAX_UNCOMPRESSED_BYTES:
        out_path.unlink()
        _io.fail(
            f"uncompressed {uncompressed_total} bytes exceeds BUNDLE_MAX_UNCOMPRESSED_BYTES "
            f"({_limits.BUNDLE_MAX_UNCOMPRESSED_BYTES})",
            code=1,
        )

    sha256 = _io.sha256_file(out_path)
    (project_dir / "lana-pkg" / "bundle.sha256").write_text(sha256 + "\n", encoding="utf-8")

    bundle_entry = project.setdefault("assets", {}).setdefault("bundle", {})
    if bundle_entry.get("sha256") != sha256:
        bundle_entry["asset_id"] = None
    bundle_entry.update({
        "file": "lana-pkg/bundle.zip", "purpose": "bundle",
        "content_type": "application/zip", "size_bytes": compressed_bytes, "sha256": sha256,
    })
    _project.save(project_dir, project)

    _io.eprint(
        f"{out_path}: {compressed_bytes/1024:.1f} KB compressed, {len(entries)+1} entries, "
        f"{uncompressed_total/1024:.1f} KB uncompressed, sha256={sha256}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
