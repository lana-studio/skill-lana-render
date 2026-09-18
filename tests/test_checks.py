"""tests/test_checks.py — check_repeats.py, check_captions.py, check_retention.py."""
from __future__ import annotations

import json

from conftest import SCRIPTS, run


def run_check(name, proj, args=None):
    return run(SCRIPTS / "reel" / name, args or [], cwd=proj, env={"REEL_PROJECT": str(proj)})


# ---- check_repeats.py ----

def test_check_repeats_detects_stutter(project_dir):
    result = run_check("check_repeats.py", project_dir)
    assert result.returncode == 1
    assert "REPEAT" in result.stdout
    assert "take 1" in result.stdout


def test_check_repeats_clean_transcript_passes(tmp_path, fixtures_dir):
    proj = tmp_path / "proj"
    (proj / "lana").mkdir(parents=True)
    proj_json = json.loads((fixtures_dir / "project.json").read_text())
    (proj / "project.json").write_text(json.dumps(proj_json), encoding="utf-8")
    (proj / "lana" / "transcript.json").write_text(json.dumps({
        "language": "en", "duration_ms": 2000,
        "words": [{"t": "hello", "s": 0, "e": 300}, {"t": "world", "s": 300, "e": 600}],
    }), encoding="utf-8")
    (proj / "lana" / "silence.json").write_text(json.dumps({
        "duration_ms": 2000, "noise_db": -35, "min_silence_ms": 150,
        "speech": [[0, 600]], "silences": [],
    }), encoding="utf-8")
    result = run_check("check_repeats.py", proj)
    assert result.returncode == 0
    assert "0 repeats" in result.stdout


# ---- check_captions.py ----

def _write_plan(proj, captions, lines):
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "project.json").write_text('{"schema": 1, "name": "x"}', encoding="utf-8")
    (proj / "src").mkdir(parents=True, exist_ok=True)
    (proj / "src" / "plan.json").write_text(json.dumps({
        "fps": 30, "total": 100, "src": "clip", "segments": [],
        "captions": captions, "lines": lines, "inserts": [], "boards": [],
    }), encoding="utf-8")


def test_check_captions_passes_when_pages_cover_the_words(tmp_path):
    proj = tmp_path / "proj"
    captions = [
        {"text": "hello", "startMs": 0, "endMs": 300},
        {"text": " world", "startMs": 300, "endMs": 600},
    ]
    lines = [{"i": 0, "startMs": 0, "endMs": 600}]
    _write_plan(proj, captions, lines)
    result = run_check("check_captions.py", proj)
    assert result.returncode == 0, result.stdout + result.stderr


def test_check_captions_fails_on_line_boundary_cut(tmp_path):
    """A page must not survive across a SEL line boundary: line 0 ends at
    600ms and line 1's first word starts immediately, so a caption for line
    0's word starting near the end, if pushed past the line boundary by a
    naive time-only grouping, must be flagged. This constructs a page whose
    last token ends well after its line's next-page start, forcing a cut."""
    proj = tmp_path / "proj"
    captions = [
        {"text": "hello", "startMs": 0, "endMs": 300},
        {"text": " world", "startMs": 300, "endMs": 2000},  # unnaturally long word
    ]
    lines = [{"i": 0, "startMs": 0, "endMs": 2000}]
    _write_plan(proj, captions, lines)
    result = run_check("check_captions.py", proj, ["--old"])
    assert result.returncode == 1
    assert "cut mid-word" in result.stdout


# ---- check_retention.py ----

def test_check_retention_reports_biggest_gap(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "project.json").write_text('{"schema": 1, "name": "x"}', encoding="utf-8")
    (proj / "src").mkdir(parents=True)
    plan = {"fps": 30, "total": 300, "src": "clip", "segments": [], "captions": [], "lines": [], "inserts": [], "boards": []}
    ritmo = {"titles": [{"ms": 0, "endMs": 500}], "punch": [], "bw": [], "glitch": [], "crosswarp": [], "lowerthirds": [], "closingMs": 9000, "hookEndMs": 500}
    gfx = []
    (proj / "src" / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    (proj / "src" / "ritmo.json").write_text(json.dumps(ritmo), encoding="utf-8")
    (proj / "src" / "graphics.json").write_text(json.dumps(gfx), encoding="utf-8")
    result = run_check("check_retention.py", proj)
    assert result.returncode == 0
    assert "biggest gap" in result.stdout
