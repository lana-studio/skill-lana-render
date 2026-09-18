"""Windows compatibility — the paths that only run on Windows, exercised here
by making the symlink fail the way Windows does without administrator rights
or Developer Mode, and by passing platform="win32" explicitly.

What this cannot prove: that a real Windows machine runs a reel end to end.
Windows stays "experimental" in the README until someone does that."""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lana-reel" / "scripts"))
import _lib  # noqa: E402
from _lib import io as _io  # noqa: E402


def _refuse_symlinks(monkeypatch):
    def refuse(self, *args, **kwargs):
        raise OSError(1314, "A required privilege is not held by the client")
    monkeypatch.setattr(Path, "symlink_to", refuse)


def _no_winapi(monkeypatch):
    # _winapi only exists on Windows; make sure the junction attempt fails
    # the same way on every machine that runs this test.
    monkeypatch.setitem(sys.modules, "_winapi", None)


@pytest.fixture
def shared_dir(tmp_path):
    d = tmp_path / "shared" / "node_modules"
    (d / "typescript" / "bin").mkdir(parents=True)
    (d / "typescript" / "bin" / "tsc").write_text("// tsc\n", encoding="utf-8")
    return d


def test_link_dir_is_a_symlink_where_allowed(tmp_path, shared_dir):
    link = tmp_path / "proj" / "node_modules"
    link.parent.mkdir()
    assert _io.link_dir(link, shared_dir) == "symlink"
    assert link.is_symlink() and (link / "typescript" / "bin" / "tsc").is_file()


def test_link_dir_still_fails_loudly_off_windows(tmp_path, shared_dir, monkeypatch):
    _refuse_symlinks(monkeypatch)
    link = tmp_path / "node_modules"
    with pytest.raises(OSError):
        _io.link_dir(link, shared_dir, platform="darwin")
    assert not link.exists()


def test_link_dir_on_windows_without_privilege_falls_back(tmp_path, shared_dir, monkeypatch):
    _refuse_symlinks(monkeypatch)
    _no_winapi(monkeypatch)
    link = tmp_path / "node_modules"
    assert _io.link_dir(link, shared_dir, platform="win32") == "copy"
    assert (link / "typescript" / "bin" / "tsc").read_text(encoding="utf-8") == "// tsc\n"


def test_link_file_on_windows_without_privilege_hardlinks(tmp_path, monkeypatch):
    _refuse_symlinks(monkeypatch)
    source = tmp_path / "take.MOV"
    source.write_bytes(b"\x00\x01video")
    raw = tmp_path / "raw"
    raw.mkdir()
    assert _io.link_file(raw / "take.MOV", source, platform="win32") == "hardlink"
    assert (raw / "take.MOV").read_bytes() == b"\x00\x01video"


def test_link_file_still_fails_loudly_off_windows(tmp_path, monkeypatch):
    _refuse_symlinks(monkeypatch)
    source = tmp_path / "take.MOV"
    source.write_bytes(b"x")
    with pytest.raises(OSError):
        _io.link_file(tmp_path / "copy.MOV", source, platform="linux")


def test_windows_output_is_forced_to_utf8():
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1252")
    _lib.force_utf8_output([stream], platform="win32")
    stream.write("→ vídeo · ok")
    stream.flush()
    assert raw.getvalue().decode("utf-8") == "→ vídeo · ok"


def test_output_encoding_untouched_off_windows():
    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    _lib.force_utf8_output([stream], platform="darwin")
    assert stream.encoding == "cp1252"


def test_force_utf8_skips_streams_that_cannot_be_reconfigured():
    _lib.force_utf8_output([io.StringIO()], platform="win32")  # no reconfigure(): must not raise


def test_new_project_survives_a_system_without_symlinks(tmp_path, monkeypatch, shared_dir):
    """new_project.py end to end with symlinks refused, as on Windows: the
    project is created, raw/ holds the take and node_modules resolves."""
    from reel import new_project  # noqa: E402  (scripts/ is on sys.path)
    from _lib import node_env

    _refuse_symlinks(monkeypatch)
    _no_winapi(monkeypatch)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(node_env, "ensure_shared_node_modules", lambda: shared_dir)

    take = tmp_path / "take.MOV"
    take.write_bytes(b"video")
    dest = tmp_path / "reels" / "first"
    assert new_project.main([str(dest), "--name", "first", "--source", str(take)]) == 0
    assert (dest / "raw" / "take.MOV").read_bytes() == b"video"
    assert (dest / "node_modules" / "typescript" / "bin" / "tsc").is_file()
