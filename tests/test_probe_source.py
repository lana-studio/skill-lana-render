"""tests/test_probe_source.py — scripts/reel/probe_source.py."""
from __future__ import annotations

import json

import pytest

from conftest import SCRIPTS, ffprobe_stream_dims, make_testsrc, run


def run_probe(proj, args, env=None):
    return run(SCRIPTS / "reel" / "probe_source.py", args, cwd=proj, env=env)


@pytest.mark.ffmpeg
def test_extracts_3_frames_under_720px(tmp_path):
    src = tmp_path / "clip.mp4"
    make_testsrc(src, duration_s=2.0, with_audio=True, size="1280x720")
    out_dir = tmp_path / "frames"
    result = run_probe(tmp_path, [str(src), "--frames", "3", "--out", str(out_dir)])
    assert result.returncode == 0, result.stderr

    frame_paths = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(frame_paths) == 3
    from pathlib import Path as _P

    for p in frame_paths:
        assert p.strip()
        w, h = ffprobe_stream_dims(_P(p.strip()))
        assert max(w, h) <= 720

    assert "duration" in result.stderr
    assert "has_audio: True" in result.stderr
    assert "look at these frames" in result.stderr


@pytest.mark.ffmpeg
def test_record_writes_project_probe_without_frame_paths(project_dir):
    src = project_dir / "raw" / "clip.mp4"
    make_testsrc(src, duration_s=1.0, with_audio=True)
    result = run_probe(project_dir, [str(src), "--frames", "1", "--record"], env={"REEL_PROJECT": str(project_dir)})
    assert result.returncode == 0, result.stderr

    project = json.loads((project_dir / "project.json").read_text())
    probe = project["source"]["probe"]
    assert probe["has_audio"] is True
    assert probe["duration_ms"] is not None
    assert "frame" not in json.dumps(probe).lower() or "frames" not in probe


def test_missing_ffprobe_exits_2(tmp_path, monkeypatch):
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"not a real video")
    empty_bin = tmp_path / "emptybin"
    empty_bin.mkdir()
    result = run_probe(tmp_path, [str(src)], env={"PATH": str(empty_bin)})
    assert result.returncode == 2
    assert "run setup.py" in result.stderr
