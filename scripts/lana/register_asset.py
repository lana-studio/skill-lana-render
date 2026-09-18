#!/usr/bin/env python3
"""scripts/lana/register_asset.py — the "guardar" step for lana_confirm_upload.

    python3 register_asset.py <key> --asset-id <uuid> [--ingest-job <uuid>]
        [--status ready] [--ext mp4]

Writes project.assets[key].{asset_id, ingest_job_id, ingest_status, ext}.
`ext` (mirrors server.py::_resolve_render_assets + common.py::
RENDER_ASSET_EXT_BY_CONTENT_TYPE, via _lib/limits.py resolve_asset_ext()):
derived from the existing project.assets[key].
content_type (set earlier by prep_upload.py). At THIS point in the flow
(right after lana_confirm_upload, before ingest has even started) no video
has a proxy yet, so this is content-type-based only — a .mov registers as
"mov", not "mp4". `save_result.py job` recalculates it to "mp4" once the
ingest job's proxy_asset_id actually arrives (a video WITH a proxy always
mounts as its h264/mp4 proxy, never the original container) — this script
must not guess that ahead of time. For a font asset (purpose="font"), also
writes project.fonts.custom[key].asset_id — a font key lives in two places
in project.json (the asset registry AND the fonts block `make_pkg.py`/
`Fonts.tsx` read from).

Prints the next step: `wait: lana_wait_job("<ingest_job_id>")` when there is
an ingest job to wait for (episode/context only).

Exit codes: 0 ok, 2 missing project or unknown asset key.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import io as _io  # noqa: E402
from _lib import limits as _limits  # noqa: E402
from _lib import project as _project  # noqa: E402


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Register a confirmed upload's asset_id.")
    parser.add_argument("key")
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--ingest-job")
    parser.add_argument("--status", default="ready")
    parser.add_argument("--ext")
    args = parser.parse_args(argv)

    project_dir = _project.find_project()
    project = _project.load(project_dir)
    entry = project.setdefault("assets", {}).setdefault(args.key, {})

    purpose = entry.get("purpose")
    ext = args.ext
    if not ext:
        # No proxy exists yet at register time (ingest hasn't run) — content
        # type only. resolve_asset_ext returns None for anything not in its
        # map (e.g. purpose="bundle"'s "application/zip"), so those fall
        # through to the uploaded file's own suffix below, same as before.
        ext = _limits.resolve_asset_ext(entry.get("content_type"), has_proxy=False)
        if not ext and entry.get("file"):
            ext = Path(entry["file"]).suffix.lstrip(".")

    entry["asset_id"] = args.asset_id
    entry["ingest_job_id"] = args.ingest_job
    entry["ingest_status"] = "PENDING" if args.ingest_job else None
    if ext:
        entry["ext"] = ext

    if purpose == "font":
        custom = project.setdefault("fonts", {}).setdefault("custom", {})
        font_entry = custom.setdefault(args.key, {})
        font_entry["asset_id"] = args.asset_id

    _project.save(project_dir, project)

    _io.eprint(f"assets.{args.key}: asset_id={args.asset_id} status={args.status} ext={ext}")
    if args.ingest_job:
        print(f'wait: lana_wait_job("{args.ingest_job}")')
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
