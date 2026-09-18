"""tests/test_setup.py — setup.py (repo root)."""
from __future__ import annotations

import json
from pathlib import Path

from conftest import REPO_ROOT, run


def run_setup(args, env=None):
    return run(REPO_ROOT / "setup.py", args, cwd=REPO_ROOT, env=env)


def test_missing_ffmpeg_exits_1_with_os_install_command(tmp_path):
    empty_bin = tmp_path / "emptybin"
    empty_bin.mkdir()
    result = run_setup(["--skip-node", "--dry-run"], env={"PATH": str(empty_bin)})
    assert result.returncode == 1
    assert "ffmpeg" in result.stderr
    assert "install" in result.stderr.lower()


def test_all_present_writes_setup_json_with_ffmpeg_version(tmp_path):
    home = tmp_path / ".reel"
    result = run_setup(["--home", str(home), "--skip-node"])
    assert result.returncode == 0, result.stderr
    setup_json = json.loads((home / "setup.json").read_text())
    assert setup_json["ffmpeg"] and setup_json["ffmpeg"] != "unknown"
    assert setup_json["python"]


def test_no_skip_ffmpeg_flag_exists():
    """ffmpeg is a REQUIREMENT, there is no opt-out flag."""
    result = run_setup(["--help"])
    assert "--skip-ffmpeg" not in result.stdout
