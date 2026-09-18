"""tests/test_brand.py — scripts/lana/brand.py.

No test file existed for this script before the systematic schema sweep
(2026-09-17) — cmd_from_caps()'s bug (reading brand.fonts/brand.sfx instead
of brand.defaults.fonts/brand.defaults.sfx, the same class of bug found in
caps.py's show_brand()) shipped untested.
"""
from __future__ import annotations

import json
import shutil

from conftest import SCRIPTS, run


def run_brand(proj, args, env=None):
    full_env = {"REEL_PROJECT": str(proj)}
    if env:
        full_env.update(env)
    return run(SCRIPTS / "lana" / "brand.py", args, cwd=proj, env=full_env)


def test_emit_builds_fonts_and_sfx_args(project_dir, tmp_path):
    project = json.loads((project_dir / "project.json").read_text())
    project.setdefault("fonts", {})["custom"] = {
        "vogue": {"asset_id": "00000000-0000-4000-8000-000000000501", "family": "Vogue", "weight": 700},
    }
    (project_dir / "project.json").write_text(json.dumps(project), encoding="utf-8")

    style = tmp_path / "style.json"
    style.write_text(json.dumps({
        "fonts_pair": "vogue", "fonts_use": ["hook", "titles"],
        "sfx_kit": "punchy", "sfx_map": {"whoosh": "brand-whoosh"}, "sfx_levels": {},
    }), encoding="utf-8")

    result = run_brand(project_dir, ["--emit", str(style)])
    assert result.returncode == 0, result.stderr
    emitted = json.loads(result.stdout)
    assert emitted["fonts"]["pair"] == "vogue"
    assert emitted["fonts"]["uses"] == {"hook": "vogue", "titles": "vogue"}
    assert emitted["fonts"]["assets"] == {"vogue": "00000000-0000-4000-8000-000000000501"}
    assert emitted["sfx"]["kit"] == "punchy"


def test_from_caps_reads_defaults_not_the_tenant_asset_lists(project_dir, fixtures_dir, monkeypatch, tmp_path):
    """Bug found in the schema sweep: BrandCapabilities.fonts/sfx are lists
    of the tenant's own uploaded BrandAssetView objects, never {pair, kit} —
    those live under brand.defaults.fonts/.sfx. cmd_from_caps() used to read
    brand.fonts.get('pair')/brand.sfx.get('kit') directly, so against a real
    (list-shaped) brand.fonts/sfx this always silently no-op'd (dict.get on
    a list crashes; on the old code's `.get("fonts") or {}` fallback for a
    non-dict it would actually raise AttributeError, exactly like the
    caps.py show_brand mutation). Fixture is schema-derived (see its
    _fixture_note in caps.brand.json)."""
    shutil.copy(fixtures_dir / "gateway" / "caps.brand.json", project_dir / "lana" / "caps.brand.json")
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    result = run_brand(project_dir, ["--from-caps"], env={"HOME": str(fake_home)})
    assert result.returncode == 0, result.stderr
    last = json.loads((fake_home / ".reel" / "last-style.json").read_text())
    assert last["fonts_pair"] == "vogue"
    assert last["sfx_kit"] == "brand-kit-1"
