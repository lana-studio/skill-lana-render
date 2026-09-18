"""tests/test_register_asset.py — scripts/lana/register_asset.py."""
from __future__ import annotations

import json

from conftest import SCRIPTS, run

ASSET_ID = "00000000-0000-4000-8000-000000000042"
INGEST_ID = "00000000-0000-4000-8000-000000000043"


def run_register(proj, args):
    return run(SCRIPTS / "lana" / "register_asset.py", args, cwd=proj, env={"REEL_PROJECT": str(proj)})


def test_writes_ids_with_content_type_ext_before_ingest(project_dir):
    """D16/bug 9: no proxy exists yet at register time (ingest hasn't even
    started — ingest_status goes to PENDING right here), so ext must be
    content-type-derived, not a premature "mp4" purpose-based guess. The
    fixture's clip.content_type is "video/quicktime" -> "mov"; save_result.py
    job (INGEST) is what recalculates this to "mp4" once proxy_asset_id
    actually arrives (see test_save_result.py)."""
    result = run_register(project_dir, ["clip", "--asset-id", ASSET_ID, "--ingest-job", INGEST_ID])
    assert result.returncode == 0, result.stderr
    project = json.loads((project_dir / "project.json").read_text())
    entry = project["assets"]["clip"]
    assert entry["asset_id"] == ASSET_ID
    assert entry["ingest_job_id"] == INGEST_ID
    assert entry["ingest_status"] == "PENDING"
    assert entry["ext"] == "mov"
    assert f'wait: lana_wait_job("{INGEST_ID}")' in result.stdout


def test_font_purpose_writes_fonts_custom(project_dir):
    project = json.loads((project_dir / "project.json").read_text())
    project["assets"]["brand"] = {"file": "fonts/Brand-Bold.ttf", "purpose": "font"}
    (project_dir / "project.json").write_text(json.dumps(project), encoding="utf-8")

    result = run_register(project_dir, ["brand", "--asset-id", ASSET_ID])
    assert result.returncode == 0, result.stderr
    updated = json.loads((project_dir / "project.json").read_text())
    assert updated["fonts"]["custom"]["brand"]["asset_id"] == ASSET_ID
    assert updated["assets"]["brand"]["asset_id"] == ASSET_ID
    assert updated["assets"]["brand"]["ingest_status"] is None  # no ingest for fonts


def test_bundle_purpose_defaults_ext_zip(project_dir):
    project = json.loads((project_dir / "project.json").read_text())
    project["assets"]["bundle"] = {"file": "lana-pkg/bundle.zip", "purpose": "bundle"}
    (project_dir / "project.json").write_text(json.dumps(project), encoding="utf-8")

    result = run_register(project_dir, ["bundle", "--asset-id", ASSET_ID])
    assert result.returncode == 0, result.stderr
    updated = json.loads((project_dir / "project.json").read_text())
    assert updated["assets"]["bundle"]["ext"] == "zip"


def test_image_purpose_ext_from_content_type(project_dir):
    project = json.loads((project_dir / "project.json").read_text())
    project["assets"]["card1"] = {"file": "assets/card1.png", "purpose": "image", "content_type": "image/png"}
    (project_dir / "project.json").write_text(json.dumps(project), encoding="utf-8")

    result = run_register(project_dir, ["card1", "--asset-id", ASSET_ID])
    assert result.returncode == 0, result.stderr
    updated = json.loads((project_dir / "project.json").read_text())
    assert updated["assets"]["card1"]["ext"] == "png"
    assert updated["assets"]["card1"]["ingest_status"] is None  # no ingest for images


def test_explicit_ext_overrides_default(project_dir):
    result = run_register(project_dir, ["clip", "--asset-id", ASSET_ID, "--ext", "mov"])
    assert result.returncode == 0, result.stderr
    project = json.loads((project_dir / "project.json").read_text())
    assert project["assets"]["clip"]["ext"] == "mov"
