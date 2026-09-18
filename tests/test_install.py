"""tests/test_install.py — install.py (repo root).

`skills/<name>/SKILL.md` and `template/` are other roles' deliverables
(skill-docs-en, remotion-template) and may not exist yet in this tree when
this suite runs — these tests create a throwaway `skills/<fixture>/SKILL.md`
under the REAL repo root (install.py hardcodes REPO_ROOT to its own
location, so there's no way to point it at a fake repo) and clean it up
afterward, rather than depending on those roles having landed first.
"""
from __future__ import annotations

import json
import shutil

import pytest

from conftest import REPO_ROOT, run

FIXTURE_SKILL = "pytest-fixture-skill"


def run_install(args, env=None):
    return run(REPO_ROOT / "install.py", args, cwd=REPO_ROOT, env=env)


@pytest.fixture
def fixture_skill():
    skill_dir = REPO_ROOT / "skills" / FIXTURE_SKILL
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("---\nname: fixture\n---\nFixture skill for install.py tests.\n", encoding="utf-8")
    try:
        yield FIXTURE_SKILL
    finally:
        # Only ever remove OUR OWN fixture subdirectory — skills/ itself is
        # shared with skill-docs-en's real deliverable (skills/reel/,
        # skills/lana-mcp-render/) and must never be rmtree'd wholesale.
        shutil.rmtree(skill_dir, ignore_errors=True)


def test_copy_mode_writes_installed_json(fixture_skill, tmp_path):
    dest = tmp_path / "skills"
    result = run_install(["--skills", fixture_skill, "--dest", str(dest)])
    assert result.returncode == 0, result.stderr
    marker = json.loads((dest / fixture_skill / "INSTALLED.json").read_text())
    assert marker["name"] == fixture_skill
    assert marker["mode"] == "copy"
    assert (dest / fixture_skill / "SKILL.md").is_file()
    assert (dest / fixture_skill / "scripts" / "_lib" / "io.py").is_file()


def test_backup_before_overwrite_never_inside_dest(fixture_skill, tmp_path):
    dest = tmp_path / "skills"
    dest.mkdir()
    existing = dest / fixture_skill
    existing.mkdir()
    (existing / "OLD_MARKER.txt").write_text("old", encoding="utf-8")

    backups_root = tmp_path / ".claude" / "skill-backups"
    result = run_install(["--skills", fixture_skill, "--dest", str(dest)], env={"HOME": str(tmp_path)})
    assert result.returncode == 0, result.stderr

    backups = list(backups_root.glob(f"{fixture_skill}-*"))
    assert len(backups) == 1
    assert (backups[0] / "OLD_MARKER.txt").is_file()
    assert not str(backups[0]).startswith(str(dest))
    # the fresh install replaced dest/<skill>, and OLD_MARKER.txt is NOT in it
    assert not (existing / "OLD_MARKER.txt").is_file()


def test_link_mode_creates_symlinks(fixture_skill, tmp_path):
    dest = tmp_path / "skills"
    result = run_install(["--skills", fixture_skill, "--dest", str(dest), "--link"])
    assert result.returncode == 0, result.stderr
    link = dest / fixture_skill
    assert link.is_symlink()
    marker = json.loads((link / "INSTALLED.json").read_text())
    assert marker["mode"] == "link"


def test_missing_skill_md_exits_2(tmp_path):
    dest = tmp_path / "skills"
    result = run_install(["--skills", "not-a-real-skill-xyz", "--dest", str(dest)])
    assert result.returncode == 2
