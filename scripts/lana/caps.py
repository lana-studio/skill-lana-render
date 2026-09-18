#!/usr/bin/env python3
"""scripts/lana/caps.py — read a saved capabilities snapshot.

    python3 caps.py <topic> [--check] [--kind <k>] [--tag <t>] [--remember]

topic in: limits | sfx | brand | library | render

Reads lana/caps.<topic>.json (written by `save_result.py caps-<topic> ...`)
and prints a human summary to stdout. Never calls
`lana_get_capabilities()` without a topic itself — the untopiced response
runs to tens of KB, too much to put in the agent's context for one lookup;
it only reads what was already saved a topic at a time.

- limits: service_version, render_enabled, quotas,
  allowed_upload_content_types; writes project.caps.{service_version,
  max_assets, fetched_at}. --check exits 1 if service_version < 1.5.0
  (semantic compare, not string) or render_enabled is false, naming which
  gate/plan is missing.
- sfx: pack_version, count, and a name/duration_ms/hit_ms/default_volume/
  variant_of table; writes project.caps.sfx_pack_version.
- brand: defaults.fonts.{pair,uses}, defaults.sfx.kit (from
  lana_set_brand_defaults), and the tenant's own uploaded font/music/sfx
  asset count; --remember merges the defaults into ~/.reel/last-style.json.
- library: release, count, harness_compatible, and the FULL entry table
  (id/kind/ext/license/attribution_required/size/tags) with `license` shown
  AS-IS (`unknown` included) — never filtered, hidden, or reordered by
  license: every shared-library resource gets proposed like any other, and
  the user decides after seeing its license, not before. --kind/--tag filter
  only by kind/tag. Prints one footer line: "N of M entries have license
  'unknown' — verify before commercial use". There is no --all and no
  "hidden" state.
  Writes project.library.release. Exits 0 whenever the file exists.
- render: render limits (max_library_refs, max_library_bytes, etc.) and the
  quickstart text.

Exit codes: 0 ok, 1 --check failed, 2 missing lana/caps.<topic>.json or project.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import io as _io  # noqa: E402
from _lib import limits as _limits  # noqa: E402
from _lib import project as _project  # noqa: E402


def load_topic(project_dir: Path, topic: str) -> dict:
    path = project_dir / "lana" / f"caps.{topic}.json"
    if not path.is_file():
        _io.fail(
            f"{path} not found — call lana_get_capabilities(topic=\"{topic}\") "
            f"and save_result.py caps-{topic} first",
            code=2,
        )
    return _io.read_json(path)


def show_limits(project_dir: Path, data: dict, check: bool) -> int:
    service_version = data.get("service_version")
    render_enabled = data.get("render_enabled")
    limits_info = data.get("limits") or {}
    content_types = data.get("allowed_upload_content_types") or limits_info.get("allowed_upload_content_types") or []

    print(f"service_version: {service_version}")
    print(f"render_enabled: {render_enabled}")
    for k, v in _limits.OBSERVED_QUOTAS.items():
        print(f"quota {k}: {v}")
    print(f"allowed_upload_content_types: {', '.join(content_types)}")

    project = _project.load(project_dir)
    caps = project.setdefault("caps", {})
    caps["service_version"] = service_version
    # LimitsInfo (services/mcp-gateway/app/schemas/tools.py) has no
    # max_assets field — only RenderLimitsInfo does, under topic="render"'s
    # render.limits.max_assets, which this topic never sees. Nothing reads
    # caps.max_assets downstream (enforcement uses the hardcoded
    # _limits.RENDER_MAX_ASSETS constant), so it is not persisted here.
    import time

    caps["fetched_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _project.save(project_dir, project)

    if check:
        problems = []
        if service_version and not _limits.version_at_least(service_version):
            problems.append(
                f"service_version {service_version} < required {_limits.REQUIRED_SERVICE_VERSION}"
            )
        if render_enabled is False:
            problems.append("render_enabled is false — check your plan/gate")
        if problems:
            _io.fail("; ".join(problems), code=1)
    return 0


def show_sfx(project_dir: Path, data: dict) -> int:
    sfx = data.get("sfx") or data
    pack_version = sfx.get("pack_version")
    entries = sfx.get("sfx") or []
    print(f"pack_version: {pack_version}")
    print(f"count: {len(entries)}")
    print(f"{'name':<24}{'duration_ms':>12}{'hit_ms':>10}{'default_volume':>16}{'variant_of':>16}")
    for e in entries:
        print(
            f"{e.get('name', ''):<24}{e.get('duration_ms', ''):>12}{e.get('hit_ms', ''):>10}"
            f"{e.get('default_volume', ''):>16}{e.get('variant_of') or '':>16}"
        )
    project = _project.load(project_dir)
    project.setdefault("caps", {})["sfx_pack_version"] = pack_version
    _project.save(project_dir, project)
    return 0


def show_brand(project_dir: Path, data: dict, remember: bool) -> int:
    # BrandCapabilities (services/mcp-gateway/app/schemas/tools.py): fonts/
    # music/sfx are LISTS of the tenant's own uploaded BrandAssetView
    # objects (purpose=font/music/sfx) — they do NOT carry pair/uses/kit.
    # The pair/uses/kit picked by lana_set_brand_defaults live separately
    # under `defaults` (BrandDefaultsView.fonts/.sfx, opaque dicts). There
    # is no top-level "assets" field at all.
    brand = data.get("brand") or data
    tenant_fonts = brand.get("fonts") or []
    tenant_music = brand.get("music") or []
    tenant_sfx = brand.get("sfx") or []
    defaults = brand.get("defaults") or {}
    default_fonts = defaults.get("fonts") or {}
    default_sfx = defaults.get("sfx") or {}
    print(f"fonts.pair: {default_fonts.get('pair')}")
    print(f"fonts.uses: {default_fonts.get('uses')}")
    print(f"sfx.kit: {default_sfx.get('kit')}")
    print(f"tenant assets: {len(tenant_fonts) + len(tenant_music) + len(tenant_sfx)}")
    if remember:
        import json

        last = Path("~/.reel/last-style.json").expanduser()
        merged = {}
        if last.is_file():
            merged = _io.read_json(last)
        merged.update({"fonts": default_fonts, "sfx": default_sfx})
        _io.write_json(last, merged)
        print(f"remembered -> {last}", file=sys.stderr)
    return 0


def show_library(project_dir: Path, data: dict, kind: str | None, tag: str | None) -> int:
    library = data.get("library") or data
    release = library.get("release")
    entries = library.get("entries") or []
    harness_compatible = library.get("harness_compatible")

    print(f"release: {release}")
    print(f"count: {len(entries)}")
    print(f"harness_compatible: {harness_compatible}")

    filtered = entries
    if kind:
        filtered = [e for e in filtered if e.get("kind") == kind]
    if tag:
        filtered = [e for e in filtered if tag in (e.get("tags") or [])]

    print(f"{'id':<24}{'kind':<10}{'ext':<6}{'license':<12}{'attribution':<12}{'size':>10}  tags")
    for e in filtered:
        print(
            f"{e.get('id', ''):<24}{e.get('kind', ''):<10}{e.get('ext', ''):<6}"
            f"{e.get('license', 'unknown'):<12}{str(e.get('attribution_required', False)):<12}"
            # LibraryEntryView's real field is size_bytes, not size
            # (services/mcp-gateway/app/schemas/tools.py).
            f"{e.get('size_bytes', ''):>10}  {','.join(e.get('tags') or [])}"
        )

    unknown = sum(1 for e in entries if e.get("license", "unknown") == "unknown")
    print(
        f"{unknown} of {len(entries)} entries have license \"unknown\" — verify before "
        "commercial use (README §Shared library & licenses)"
    )

    project = _project.load(project_dir)
    project.setdefault("library", {})["release"] = release
    _project.save(project_dir, project)
    return 0


def show_render(data: dict) -> int:
    render = data.get("render") or data
    limits_info = render.get("limits") or {}
    for k, v in limits_info.items():
        print(f"{k}: {v}")
    quickstart = render.get("quickstart")
    if quickstart:
        print(quickstart)
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Read a saved lana_get_capabilities snapshot.")
    parser.add_argument("topic", choices=["limits", "sfx", "brand", "library", "render"])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--kind")
    parser.add_argument("--tag")
    parser.add_argument("--remember", action="store_true")
    args = parser.parse_args(argv)

    project_dir = _project.find_project()
    data = load_topic(project_dir, args.topic)

    if args.topic == "limits":
        return show_limits(project_dir, data, args.check)
    if args.topic == "sfx":
        return show_sfx(project_dir, data)
    if args.topic == "brand":
        return show_brand(project_dir, data, args.remember)
    if args.topic == "library":
        return show_library(project_dir, data, args.kind, args.tag)
    if args.topic == "render":
        return show_render(data)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
