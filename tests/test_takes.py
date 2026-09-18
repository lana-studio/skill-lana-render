"""tests/test_takes.py — scripts/reel/takes.py."""
from __future__ import annotations

import json

from conftest import SCRIPTS, run


def run_takes(proj, args):
    return run(SCRIPTS / "reel" / "takes.py", args, cwd=proj, env={"REEL_PROJECT": str(proj)})


def test_5_regions_yield_5_takes(project_dir):
    result = run_takes(project_dir, [])
    assert result.returncode == 0, result.stderr
    takes = json.loads((project_dir / "lana" / "takes.json").read_text())
    assert len(takes) == 4  # tests/fixtures/silence.json has 4 speech regions


def test_hallucination_flag_on_short_region(project_dir):
    run_takes(project_dir, [])
    takes = json.loads((project_dir / "lana" / "takes.json").read_text())
    short_region = next(t for t in takes if t["start_ms"] == 6000)
    assert short_region["flag"] == "hallucination"
    assert short_region["words"] == 0


def test_hallucination_flag_on_overlong_single_word(project_dir):
    run_takes(project_dir, [])
    takes = json.loads((project_dir / "lana" / "takes.json").read_text())
    overlong = next(t for t in takes if t["start_ms"] == 8670)
    assert overlong["flag"] == "hallucination"
    assert overlong["words"] == 1


def test_repeat_flag_on_stutter_region(project_dir):
    run_takes(project_dir, [])
    takes = json.loads((project_dir / "lana" / "takes.json").read_text())
    stutter = next(t for t in takes if t["start_ms"] == 3200)
    assert stutter["flag"] == "repeat"


def test_clean_region_has_no_flag(project_dir):
    run_takes(project_dir, [])
    takes = json.loads((project_dir / "lana" / "takes.json").read_text())
    clean = next(t for t in takes if t["start_ms"] == 0)
    assert clean["flag"] is None
    assert clean["text"] == "here is the thing nobody tells you"


def test_words_between_flag(project_dir):
    result = run_takes(project_dir, ["--words", "0-700"])
    assert result.returncode == 0, result.stderr
    lines = [l for l in result.stdout.splitlines() if l.strip()]
    assert any("here" in l for l in lines)
    assert any("the" in l for l in lines)
    # "thing" ends at 1100ms, outside the 0-700(+30 pad) window
    assert not any(l.strip().endswith("thing") for l in lines)


def test_rerun_with_different_asset_merges_not_overwrites(project_dir, fixtures_dir):
    """takes.json is ONE file across every asset, not one per asset."""
    (project_dir / "lana" / "other.transcript.json").write_text(
        (fixtures_dir / "transcript.json").read_text(), encoding="utf-8"
    )
    (project_dir / "lana" / "other.silence.json").write_text(
        (fixtures_dir / "silence.json").read_text(), encoding="utf-8"
    )
    run_takes(project_dir, [])
    run_takes(project_dir, ["--asset", "other"])
    takes = json.loads((project_dir / "lana" / "takes.json").read_text())
    assets_present = {t["asset"] for t in takes}
    assert assets_present == {"clip", "other"}
    assert len(takes) == 8


def test_missing_silence_file_exits_2(tmp_path):
    proj = tmp_path / "empty"
    for d in ("lana",):
        (proj / d).mkdir(parents=True)
    (proj / "project.json").write_text("{}", encoding="utf-8")
    result = run_takes(proj, [])
    assert result.returncode == 2
