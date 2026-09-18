#!/usr/bin/env python3
"""scripts/lana/make_submit.py — the "emitir" step for lana_submit_render.

    python3 make_submit.py (--proof | --final) [--bitrate <s>] [--attempt <n>] --emit

Reads project.json (the bundle's asset_id, sha256, and the asset registry)
and prints the exact args for `lana_submit_render` in bundle mode (`files`
is only ever used by make_probe.py's hello render). Never emits `props` at
all — D17 (below): in bundle mode the harness drops `props` between prepare
and render regardless of what's sent, so the plan travels inside the bundle
itself (lana-pkg/src/plan.ts etc. — generated .ts modules, D17 v2, via
make_pkg.py) instead.

D16 (bug 9 — "every real reel rendered black"): the old contract derived
`assets` from `lana-pkg/used-assets.json`, a static-literal
scan of code that resolved everything by variable — the scan always found
nothing, `assets` came out `{}`, the harness had nothing to stage, and the
job still reported SUCCEEDED with four identical black outputs.

- `assets` = `_lib.project.ready_assets(project)` (asset_id set, ingest
  finished or N/A, purpose != "bundle") -> `{key: asset_id}`, PLUS
  `_lib.project.ready_custom_fonts(project)` -> `{key: asset_id}` — the
  EXACT same two functions make_pkg.py uses to build ASSET_FILES, so the two
  scripts cannot diverge again the way the literal scan diverged from the
  registry. Every registered-and-ready asset is sent, not "the ones the code
  happens to reference" — the harness stages the whole map regardless, there
  is no warning or cost for an unreferenced one, and the registry is the
  only reliable signal of intent. `!!` exit 1 if > RENDER_MAX_ASSETS (24),
  listing the keys so the agent can `register_asset.py --remove <key>`.
- Coherence check against `lana-pkg/manifest-summary.json.assets` (written
  by make_pkg.py from the same source a moment earlier): every key must
  appear on both sides or `!!` exit 1 ("make_pkg.py and make_submit.py
  disagree: re-run make_pkg.py") — this catches a stale lana-pkg/ from
  before an asset was registered/removed.
- `assets == {}` while the registry has ready, non-bundle assets is `!!`
  exit 1 on its own — the exact black-render regression, caught even if the
  coherence check above somehow doesn't (e.g. an empty manifest-summary.json
  from an old make_pkg.py run).
- `idempotency_key = f"{name}-{bundle_sha256[:8]}-{proof|final}[-{attempt}]"`
  (<= 64 chars, [a-z0-9-]) — the same bundle content + the same kind always
  produces the same key unless --attempt forces a new one.
- Library release guard: if project.library.items is non-empty and
  lana/caps.library.json's release differs from project.library.release,
  this refuses to emit (`!!`, exit 1) rather than silently render against a
  library that moved under the selection.
- `--emit` prints {"entry": "src/index.tsx", "bundle": <asset_id>,
  "compositions": [...], "assets": {...}, "idempotency_key": "..."} (+
  "video_bitrate" if --bitrate was given) and registers a stub in
  project.jobs.renders[]: {kind, idempotency_key, bundle_sha256, job_id:
  null} — save_result.py job later fills job_id/status/outputs into this
  same stub, matched by job_id or by --idempotency-key.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import io as _io  # noqa: E402
from _lib import limits as _limits  # noqa: E402
from _lib import project as _project  # noqa: E402

IDEMPOTENCY_KEY_MAX_LEN = 64
SLUG_SANITIZE_RE = re.compile(r"[^a-z0-9-]+")


def proof_compositions(proofs: list[dict]) -> list[str]:
    ids = sorted(
        (p["id"] for p in proofs if re.match(r"^Reel-proof-\d+$", p.get("id", ""))),
        key=lambda cid: int(cid.rsplit("-", 1)[1]),
    )
    return ids[:4]


def check_library_guard(project_dir: Path, project: dict) -> None:
    items = (project.get("library") or {}).get("items") or []
    if not items:
        return
    caps_path = project_dir / "lana" / "caps.library.json"
    if not caps_path.is_file():
        _io.fail("project.library.items is non-empty but lana/caps.library.json was never saved", code=1)
    caps = _io.read_json(caps_path)
    active_release = (caps.get("library") or caps).get("release")
    selected_release = (project.get("library") or {}).get("release")
    if active_release != selected_release:
        _io.fail(
            f"library release mismatch: active is {active_release!r}, selection was made with "
            f"{selected_release!r} — it will not be silently swapped. Re-check the "
            "selection or refresh lana/caps.library.json.",
            code=1,
        )


def build_assets_map(project_dir: Path, project: dict) -> dict[str, str]:
    assets_map = {
        key: entry["asset_id"] for key, entry in _project.ready_assets(project).items()
    }
    assets_map.update({
        key: entry["asset_id"] for key, entry in _project.ready_custom_fonts(project).items()
    })

    if len(assets_map) > _limits.RENDER_MAX_ASSETS:
        _io.fail(
            f"{len(assets_map)} assets exceeds RENDER_MAX_ASSETS ({_limits.RENDER_MAX_ASSETS}): "
            f"{sorted(assets_map)} — register_asset.py --remove <key> to trim",
            code=1,
        )

    # Coherence check: make_pkg.py's ASSET_FILES and this script's submit
    # map must come from the same registry snapshot. A stale lana-pkg/ from
    # before an asset was registered or removed is exactly the kind of
    # silent divergence D16 exists to prevent — INCLUDING the actual
    # black-render regression itself: assets_map is derived directly from
    # the live registry (_lib.project.ready_assets/ready_custom_fonts), so
    # it can only be empty while the registry has ready assets if
    # lana-pkg/manifest-summary.json is stale (e.g. from before those
    # assets were registered) — which this same check already catches.
    summary_path = project_dir / "lana-pkg" / "manifest-summary.json"
    if not summary_path.is_file():
        _io.fail(f"{summary_path} not found — run make_pkg.py first", code=2)
    summary = _io.read_json(summary_path)
    summary_keys = set(summary.get("assets") or [])
    submit_keys = set(assets_map)
    if summary_keys != submit_keys:
        _io.fail(
            "make_pkg.py and make_submit.py disagree: re-run make_pkg.py "
            f"(manifest-summary.json has {sorted(summary_keys)}, this submit "
            f"has {sorted(submit_keys)})",
            code=1,
        )

    return assets_map


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Build lana_submit_render args from a registered bundle.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--proof", action="store_true")
    mode.add_argument("--final", action="store_true")
    parser.add_argument("--bitrate")
    parser.add_argument("--attempt", type=int)
    parser.add_argument("--emit", action="store_true")
    args = parser.parse_args(argv)

    project_dir = _project.find_project()
    project = _project.load(project_dir)

    check_library_guard(project_dir, project)

    bundle = (project.get("assets") or {}).get("bundle") or {}
    bundle_asset_id = bundle.get("asset_id")
    bundle_sha256 = bundle.get("sha256")
    if not bundle_asset_id or not bundle_sha256:
        _io.fail("project.assets.bundle has no asset_id/sha256 — run make_bundle.py and confirm the upload first", code=1)

    assets_map = build_assets_map(project_dir, project)

    if args.proof:
        proofs_path = project_dir / "lana-pkg" / "proofs.json"
        if not proofs_path.is_file():
            _io.fail(f"{proofs_path} not found — run build.py first", code=2)
        proofs = _io.read_json(proofs_path)
        compositions = proof_compositions(proofs)
        if not compositions:
            _io.fail("no Reel-proof-N entries in lana-pkg/proofs.json — run build.py first", code=1)
        kind = "proof"
    else:
        compositions = [project.get("composition", "Reel")]
        kind = "final"

    slug = SLUG_SANITIZE_RE.sub("-", project.get("name", "reel").lower()).strip("-")
    key = f"{slug}-{bundle_sha256[:8]}-{kind}"
    if args.attempt:
        key = f"{key}-{args.attempt}"
    key = key[:IDEMPOTENCY_KEY_MAX_LEN]

    submit_args = {
        "entry": "src/index.tsx", "bundle": bundle_asset_id,
        "compositions": compositions, "assets": assets_map, "idempotency_key": key,
    }
    if args.bitrate:
        submit_args["video_bitrate"] = args.bitrate

    if args.emit:
        _io.emit(submit_args, "make_submit", project_dir)
    else:
        _io.eprint(str(submit_args))

    renders = project.setdefault("jobs", {}).setdefault("renders", [])
    if not any(r.get("idempotency_key") == key for r in renders):
        renders.append({"kind": kind, "idempotency_key": key, "bundle_sha256": bundle_sha256, "job_id": None})
        _project.save(project_dir, project)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
