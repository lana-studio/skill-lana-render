"""tests/test_caps.py — scripts/lana/caps.py."""
from __future__ import annotations

import json
import shutil

from conftest import SCRIPTS, run


def run_caps(proj, args):
    return run(SCRIPTS / "lana" / "caps.py", args, cwd=proj, env={"REEL_PROJECT": str(proj)})


def test_library_shows_all_7_with_license_unknown_visible(project_dir, fixtures_dir):
    shutil.copy(fixtures_dir / "gateway" / "caps.library.unknown.json", project_dir / "lana" / "caps.library.json")
    result = run_caps(project_dir, ["library"])
    assert result.returncode == 0, result.stderr
    assert "count: 7" in result.stdout
    assert "7 of 7 entries have license \"unknown\"" in result.stdout
    for entry_id in (
        "sequel-sans-bold-disp", "white-paper-elements-05", "letra-animada-b",
        "degradado-negro-subtitulos", "super-8-frame", "broll-c309", "swoosh-original",
    ):
        assert entry_id in result.stdout
    # LibraryEntryView's real field is size_bytes, not size (services/
    # mcp-gateway/app/schemas/tools.py) — assert the actual byte count
    # shows up in the row, not just that a row exists for the id.
    assert "86436" in result.stdout


def test_library_mixed_licenses_hides_nothing(project_dir, fixtures_dir):
    """2 CC0 + 5 unknown -> all 7 rows shown, none hidden or reordered by license."""
    shutil.copy(fixtures_dir / "gateway" / "caps.library.mixed.json", project_dir / "lana" / "caps.library.json")
    result = run_caps(project_dir, ["library"])
    assert result.returncode == 0, result.stderr
    assert "count: 7" in result.stdout
    rows = [l for l in result.stdout.splitlines() if l.strip().startswith(("sequel-sans", "white-paper", "letra-", "degradado-", "super-8", "broll-", "swoosh-"))]
    assert len(rows) == 7
    assert "5 of 7 entries have license \"unknown\"" in result.stdout


def test_library_kind_filter(project_dir, fixtures_dir):
    shutil.copy(fixtures_dir / "gateway" / "caps.library.unknown.json", project_dir / "lana" / "caps.library.json")
    result = run_caps(project_dir, ["library", "--kind", "font"])
    assert result.returncode == 0, result.stderr
    assert "sequel-sans-bold-disp" in result.stdout
    assert "white-paper-elements-05" not in result.stdout
    # the footer count is still over ALL entries, not the filtered view
    assert "7 of 7 entries" in result.stdout


# The "limits" dict below is schema-DERIVED (LimitsInfo, services/
# mcp-gateway/app/schemas/tools.py), not a real captured lana_get_capabilities
# result — QA has not supplied one for topic="limits" yet. It previously
# carried a "max_assets" key that doesn't exist on LimitsInfo at all (that
# field only exists on RenderLimitsInfo, topic="render"); none of these
# tests assert on any "limits" sub-field, so the real field names are here
# only so the fixture cannot be mistaken for a schema that has max_assets.


def test_limits_check_fails_below_required_version(project_dir, tmp_path):
    (project_dir / "lana" / "caps.limits.json").write_text(json.dumps({
        "service_version": "1.4.0", "render_enabled": True, "limits": {"max_render_duration_s": 600, "max_render_width": 1920, "max_render_height": 1080, "max_render_fps": 30, "max_render_spec_bytes": 65536, "allowed_upload_content_types": ["video/mp4"], "upload_sas_ttl_s": 3600, "read_sas_ttl_s": 3600, "quota": {}},
    }), encoding="utf-8")
    result = run_caps(project_dir, ["limits", "--check"])
    assert result.returncode == 1
    assert "1.4.0" in result.stderr and "1.5.0" in result.stderr


def test_limits_check_passes_at_required_version(project_dir):
    (project_dir / "lana" / "caps.limits.json").write_text(json.dumps({
        "service_version": "1.5.0", "render_enabled": True, "limits": {"max_render_duration_s": 600, "max_render_width": 1920, "max_render_height": 1080, "max_render_fps": 30, "max_render_spec_bytes": 65536, "allowed_upload_content_types": ["video/mp4"], "upload_sas_ttl_s": 3600, "read_sas_ttl_s": 3600, "quota": {}},
    }), encoding="utf-8")
    result = run_caps(project_dir, ["limits", "--check"])
    assert result.returncode == 0, result.stderr
    project = json.loads((project_dir / "project.json").read_text())
    assert project["caps"]["service_version"] == "1.5.0"
    # LimitsInfo (services/mcp-gateway/app/schemas/tools.py) has no
    # max_assets field at all — only RenderLimitsInfo (topic="render") does.
    # Bug found in the schema sweep: this used to write caps["max_assets"]
    # from a field that can never be present on a real topic="limits"
    # snapshot (a prior fixture invented the field to match the bug).
    assert "max_assets" not in project["caps"]


def test_limits_check_semantic_not_string_compare(project_dir):
    """'1.10.0' must not compare less than '1.5.0' as a STRING would."""
    (project_dir / "lana" / "caps.limits.json").write_text(json.dumps({
        "service_version": "1.10.0", "render_enabled": True, "limits": {"max_render_duration_s": 600, "max_render_width": 1920, "max_render_height": 1080, "max_render_fps": 30, "max_render_spec_bytes": 65536, "allowed_upload_content_types": ["video/mp4"], "upload_sas_ttl_s": 3600, "read_sas_ttl_s": 3600, "quota": {}},
    }), encoding="utf-8")
    result = run_caps(project_dir, ["limits", "--check"])
    assert result.returncode == 0, result.stderr


def test_brand_reads_defaults_not_the_tenant_asset_lists(project_dir, fixtures_dir, tmp_path):
    """Bug found in the schema sweep: BrandCapabilities.fonts/music/sfx are
    LISTS of the tenant's own uploaded BrandAssetView objects — they never
    carry pair/uses/kit. Those live under `defaults.fonts`/`defaults.sfx`
    (BrandDefaultsView, opaque dicts written by lana_set_brand_defaults).
    There is also no top-level "assets" field; the tenant asset count is
    len(fonts)+len(music)+len(sfx). Fixture is schema-derived (see its
    _fixture_note), not yet QA-captured."""
    shutil.copy(fixtures_dir / "gateway" / "caps.brand.json", project_dir / "lana" / "caps.brand.json")
    result = run_caps(project_dir, ["brand"])
    assert result.returncode == 0, result.stderr
    assert "fonts.pair: vogue" in result.stdout
    assert "fonts.uses: {'headline': 'vogue-bold', 'body': 'vogue-regular'}" in result.stdout
    assert "sfx.kit: brand-kit-1" in result.stdout
    assert "tenant assets: 3" in result.stdout  # 2 fonts + 0 music + 1 sfx


def test_brand_remember_merges_defaults_into_last_style(project_dir, fixtures_dir, monkeypatch, tmp_path):
    shutil.copy(fixtures_dir / "gateway" / "caps.brand.json", project_dir / "lana" / "caps.brand.json")
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    result = run_caps(project_dir, ["brand", "--remember"])
    assert result.returncode == 0, result.stderr
    last = json.loads((fake_home / ".reel" / "last-style.json").read_text())
    assert last["fonts"]["pair"] == "vogue"
    assert last["sfx"]["kit"] == "brand-kit-1"


def test_no_topic_is_a_usage_error(project_dir):
    result = run_caps(project_dir, [])
    assert result.returncode != 0


def test_missing_snapshot_exits_2(project_dir):
    result = run_caps(project_dir, ["sfx"])
    assert result.returncode == 2
