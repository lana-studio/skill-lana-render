"""tests/test_project_lib.py — scripts/_lib/project.py."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from _lib import project as _project  # noqa: E402


def test_find_project_via_env(tmp_path, monkeypatch):
    proj = tmp_path / "myproj"
    proj.mkdir()
    (proj / "project.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("REEL_PROJECT", str(proj))
    found = _project.find_project()
    assert found == proj.resolve()


def test_find_project_via_cwd(tmp_path, monkeypatch):
    monkeypatch.delenv("REEL_PROJECT", raising=False)
    proj = tmp_path / "myproj"
    proj.mkdir()
    (proj / "project.json").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(proj)
    found = _project.find_project()
    assert found == proj.resolve()


def test_find_project_ascends_up_to_3_levels(tmp_path, monkeypatch):
    monkeypatch.delenv("REEL_PROJECT", raising=False)
    proj = tmp_path / "myproj"
    deep = proj / "a" / "b" / "c"
    deep.mkdir(parents=True)
    (proj / "project.json").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(deep)
    found = _project.find_project()
    assert found == proj.resolve()


def test_find_project_not_found_exit_code_is_2_not_1(tmp_path, monkeypatch):
    """Regression: a bare `SystemExit("message")` has `.code` set to the
    STRING, which CPython treats as exit status 1 when it actually leaves
    the process — this family's convention (2 = missing project) needs
    an explicit integer exit code, not a message passed positionally."""
    monkeypatch.delenv("REEL_PROJECT", raising=False)
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.chdir(empty)
    try:
        _project.find_project()
        assert False, "expected SystemExit"
    except SystemExit as exc:
        assert exc.code == 2
        assert isinstance(exc.code, int)


def test_find_project_too_deep_fails(tmp_path, monkeypatch):
    monkeypatch.delenv("REEL_PROJECT", raising=False)
    proj = tmp_path / "myproj"
    deep = proj / "a" / "b" / "c" / "d"
    deep.mkdir(parents=True)
    (proj / "project.json").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(deep)
    try:
        _project.find_project()
        assert False, "expected SystemExit"
    except SystemExit as exc:
        assert exc.code == 2


def test_find_project_missing_fails(tmp_path, monkeypatch):
    monkeypatch.delenv("REEL_PROJECT", raising=False)
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.chdir(empty)
    try:
        _project.find_project()
        assert False, "expected SystemExit"
    except SystemExit as exc:
        assert exc.code == 2


def test_save_preserves_unknown_keys(tmp_path):
    proj = tmp_path / "myproj"
    proj.mkdir()
    data = {"schema": 1, "name": "x", "a_future_field_this_script_does_not_know": {"nested": True}}
    (proj / "project.json").write_text(json.dumps(data), encoding="utf-8")

    loaded = _project.load(proj)
    loaded["name"] = "y"  # a script only touches the field it cares about
    _project.save(proj, loaded)

    reloaded = json.loads((proj / "project.json").read_text(encoding="utf-8"))
    assert reloaded["name"] == "y"
    assert reloaded["a_future_field_this_script_does_not_know"] == {"nested": True}


def test_load_config_reads_CONFIG(tmp_path):
    proj = tmp_path / "myproj"
    proj.mkdir()
    (proj / "videoconfig.py").write_text("CONFIG = {'sel': [], 'hold_f': 10}\n", encoding="utf-8")
    cfg = _project.load_config(proj)
    assert cfg == {"sel": [], "hold_f": 10}


def test_load_config_missing_file_exits_2(tmp_path):
    proj = tmp_path / "myproj"
    proj.mkdir()
    try:
        _project.load_config(proj)
        assert False, "expected SystemExit"
    except SystemExit as exc:
        assert exc.code == 2


def test_load_config_two_projects_dont_collide(tmp_path):
    """Regression: importlib module caching by name must not let project A's
    CONFIG leak into project B when both are loaded in the same process."""
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "videoconfig.py").write_text("CONFIG = {'sel': [], 'marker': 'A'}\n", encoding="utf-8")
    (b / "videoconfig.py").write_text("CONFIG = {'sel': [], 'marker': 'B'}\n", encoding="utf-8")
    cfg_a = _project.load_config(a)
    cfg_b = _project.load_config(b)
    assert cfg_a["marker"] == "A"
    assert cfg_b["marker"] == "B"
