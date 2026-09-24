"""tests/test_verify_output.py — scripts/lana/verify_output.py."""
from __future__ import annotations

import json

import pytest

from conftest import SCRIPTS, make_silence_gap_video, run


def run_verify(proj, args):
    return run(SCRIPTS / "lana" / "verify_output.py", args, cwd=proj, env={"REEL_PROJECT": str(proj)})


def write_job(proj, job_id="j1", status="SUCCEEDED", duration_s=2.0, error=None, render=None):
    job = {"job_id": job_id, "status": status, "outputs": [{"composition_id": "Reel", "duration_s": duration_s, "size_bytes": 1000}]}
    if error:
        job["error"] = error
        job["outputs"] = []
    if render:
        job["render"] = render
    (proj / "lana" / "jobs" / f"{job_id}.json").write_text(json.dumps(job), encoding="utf-8")
    return proj / "lana" / "jobs" / f"{job_id}.json"


def write_plan(proj, total_frames, fps=30, lines=None):
    (proj / "src").mkdir(parents=True, exist_ok=True)
    (proj / "src" / "plan.json").write_text(json.dumps({
        "fps": fps, "total": total_frames, "src": "clip", "hold_f": 10,
        "segments": [], "captions": [], "lines": lines or [], "inserts": [], "boards": [],
    }), encoding="utf-8")


def test_asset_error_interpreted_as_premium_too_old(project_dir):
    job_path = write_job(project_dir, error={"code": "ASSET_ERROR", "field_path": "assets.brand"})
    result = run_verify(project_dir, ["--job", str(job_path)])
    assert result.returncode == 1
    assert "premium too old for purpose=font" in result.stderr


def test_sfx_404_interpreted_as_harness_too_old(project_dir):
    job_path = write_job(project_dir, error={"code": "RENDER_ERROR"}, render={"logs_tail": "GET public/sfx/whoosh-short.wav 404"})
    result = run_verify(project_dir, ["--job", str(job_path)])
    assert result.returncode == 1
    assert "harness too old" in result.stderr


def test_forbidden_scope_message(project_dir):
    # McpErrorDetail (services/mcp-gateway/app/schemas/errors.py) has no
    # "scope" field — the missing scope is named inside `message` itself,
    # the only field the FORBIDDEN_SCOPE catalog entry guarantees.
    job_path = write_job(project_dir, error={"code": "FORBIDDEN_SCOPE", "message": "missing scope render:create"})
    result = run_verify(project_dir, ["--job", str(job_path)])
    assert result.returncode == 1
    assert "re-authorize" in result.stderr
    assert "grant" in result.stderr
    assert "render:create" in result.stderr


def test_duration_matches_plan(project_dir):
    write_plan(project_dir, total_frames=60)  # 60/30fps = 2.0s
    job_path = write_job(project_dir, duration_s=2.0)
    result = run_verify(project_dir, ["--job", str(job_path)])
    assert result.returncode == 0, result.stderr


def test_duration_mismatch_flagged(project_dir):
    write_plan(project_dir, total_frames=60)  # expects 2.0s
    job_path = write_job(project_dir, duration_s=5.0)  # way off
    result = run_verify(project_dir, ["--job", str(job_path)])
    assert result.returncode == 1
    assert "differs from plan" in result.stderr


@pytest.mark.ffmpeg
def test_file_unjustified_silence_flagged(project_dir, tmp_path):
    write_plan(project_dir, total_frames=90, lines=[{"i": 0, "startMs": 0, "endMs": 3000, "keep": False}])
    job_path = write_job(project_dir, duration_s=3.0)

    out = tmp_path / "out.mp4"
    make_silence_gap_video(out)

    result = run_verify(project_dir, ["--job", str(job_path), "--file", str(out)])
    assert result.returncode == 1
    assert "unjustified silence" in result.stderr


@pytest.mark.ffmpeg
def test_file_silence_covered_by_keep_pauses_passes(project_dir, tmp_path):
    write_plan(project_dir, total_frames=90, lines=[{"i": 0, "startMs": 0, "endMs": 3000, "keep": True}])
    job_path = write_job(project_dir, duration_s=3.0)

    out = tmp_path / "out.mp4"
    make_silence_gap_video(out)

    result = run_verify(project_dir, ["--job", str(job_path), "--file", str(out)])
    assert result.returncode == 0, result.stderr
