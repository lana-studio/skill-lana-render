#!/usr/bin/env python3
"""scripts/lana/brand.py — the emit/save pair for lana_set_brand_defaults.

    python3 brand.py --emit <style.json>
    python3 brand.py --from-caps

`--emit <style.json>`: reads the questionnaire answers (styles.py's shape —
`fonts_pair`, `fonts_use`, `sfx_kit`) and prints the exact args for
`lana_set_brand_defaults`: {"fonts": {"pair", "uses", "assets"}, "sfx":
{"kit", "map", "levels"}}. `assets` only includes
project.fonts.custom[*].asset_id entries that are not null — a pair that
references a font the user hasn't uploaded yet just doesn't get an asset
entry (the tenant default still records which pair id was chosen).

`--from-caps`: reads lana/caps.brand.json (saved by `save_result.py
caps-brand`) and merges it into ~/.reel/last-style.json so styles.py
questions can show "(last time)" hints from the tenant's actual saved
defaults, not just the previous local run.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import io as _io  # noqa: E402
from _lib import project as _project  # noqa: E402

LAST_STYLE_PATH = Path("~/.reel/last-style.json").expanduser()


def cmd_emit(style_path: str) -> int:
    if not Path(style_path).is_file():
        _io.fail(f"{style_path} does not exist", code=2)
    style = _io.read_json(style_path)

    project_dir = _project.find_project()
    project = _project.load(project_dir)
    custom = (project.get("fonts") or {}).get("custom") or {}

    pair = style.get("fonts_pair", "anton")
    uses = style.get("fonts_use") or ["hook", "titles", "captions"]
    assets = {k: v["asset_id"] for k, v in custom.items() if v.get("asset_id")}

    fonts = {"pair": pair, "uses": {u: pair for u in uses}, "assets": assets}
    sfx = {
        "kit": style.get("sfx_kit", "full"),
        "map": style.get("sfx_map") or {},
        "levels": style.get("sfx_levels") or {},
    }
    args = {"fonts": fonts, "sfx": sfx}
    _io.emit(args, "brand", project_dir)
    return 0


def cmd_from_caps() -> int:
    project_dir = _project.find_project()
    caps_path = project_dir / "lana" / "caps.brand.json"
    if not caps_path.is_file():
        _io.fail(f"{caps_path} not found — call lana_get_capabilities(topic=\"brand\") and save_result.py caps-brand first", code=2)
    caps = _io.read_json(caps_path)
    brand = caps.get("brand", caps)

    merged = _io.read_json(LAST_STYLE_PATH) if LAST_STYLE_PATH.is_file() else {}
    # BrandCapabilities.fonts/sfx (services/mcp-gateway/app/schemas/tools.py)
    # are LISTS of the tenant's own uploaded BrandAssetView objects — they
    # never carry pair/kit. The pair/kit picked by lana_set_brand_defaults
    # live separately under `defaults.fonts`/`defaults.sfx` (opaque
    # BrandDefaultsView dicts), which is what "(last time)" actually needs.
    defaults = brand.get("defaults") or {}
    default_fonts = defaults.get("fonts") or {}
    default_sfx = defaults.get("sfx") or {}
    if default_fonts.get("pair"):
        merged["fonts_pair"] = default_fonts["pair"]
    if default_sfx.get("kit"):
        merged["sfx_kit"] = default_sfx["kit"]
    _io.write_json(LAST_STYLE_PATH, merged)
    _io.eprint(f"remembered tenant defaults -> {LAST_STYLE_PATH}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Emit/save lana_set_brand_defaults data.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--emit", metavar="style.json")
    group.add_argument("--from-caps", action="store_true")
    args = parser.parse_args(argv)

    if args.emit:
        return cmd_emit(args.emit)
    return cmd_from_caps()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
