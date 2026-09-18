"""tests/test_prep_upload.py — scripts/lana/prep_upload.py."""
from __future__ import annotations

import json

import pytest

from conftest import SCRIPTS, make_fast_video_of_duration, make_testsrc, run


def run_prep(proj, args):
    return run(SCRIPTS / "lana" / "prep_upload.py", args, cwd=proj, env={"REEL_PROJECT": str(proj)})


def test_content_type_by_extension(project_dir):
    png = project_dir / "assets" / "card1.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 100)
    result = run_prep(project_dir, [str(png), "--purpose", "image", "--key", "card1", "--emit"])
    assert result.returncode == 0, result.stderr
    args = json.loads(result.stdout)
    assert args["content_type"] == "image/png"
    assert set(args.keys()) == {"filename", "content_type", "size_bytes", "purpose", "title"}


def test_bundle_wrong_extension_exits_1(project_dir):
    fake = project_dir / "lana-pkg" / "bundle.tar"
    fake.write_bytes(b"0" * 10)
    result = run_prep(project_dir, [str(fake), "--purpose", "bundle"])
    assert result.returncode == 1
    assert "bundle" in result.stderr


def test_font_over_5mib_exits_1(project_dir):
    font = project_dir / "assets" / "big.ttf"
    font.write_bytes(b"0" * (6 * 1024 * 1024))
    result = run_prep(project_dir, [str(font), "--purpose", "font", "--key", "bigfont"])
    assert result.returncode == 1
    assert "5 MiB" in result.stderr or "exceeds" in result.stderr


def test_registers_in_project_assets(project_dir):
    png = project_dir / "assets" / "card1.png"
    png.write_bytes(b"0" * 500)
    result = run_prep(project_dir, [str(png), "--purpose", "image", "--key", "card1"])
    assert result.returncode == 0, result.stderr
    project = json.loads((project_dir / "project.json").read_text())
    entry = project["assets"]["card1"]
    assert entry["purpose"] == "image"
    assert entry["content_type"] == "image/png"
    assert entry["asset_id"] is None
    assert "sha256" in entry


def test_jpg_warns_but_does_not_fail(project_dir):
    jpg = project_dir / "assets" / "card1.jpg"
    jpg.write_bytes(b"\xff\xd8\xff" + b"0" * 100)
    result = run_prep(project_dir, [str(jpg), "--purpose", "image", "--key", "card1"])
    assert result.returncode == 0, result.stderr
    assert "prefer PNG" in result.stderr


@pytest.mark.ffmpeg
def test_mp4_without_audio_gets_silent_track_added(project_dir):
    src = project_dir / "raw" / "noaudio.mp4"
    make_testsrc(src, duration_s=1.0, with_audio=False)
    result = run_prep(project_dir, [str(src), "--purpose", "context", "--key", "clip2"])
    assert result.returncode == 0, result.stderr
    assert "silent track added" in result.stderr
    fixed = project_dir / "raw" / "noaudio-a.mp4"
    assert fixed.is_file()
    project = json.loads((project_dir / "project.json").read_text())
    assert project["assets"]["clip2"]["file"] == "raw/noaudio-a.mp4"


@pytest.mark.ffmpeg
def test_mp4_without_audio_and_no_fix_exits_1(project_dir):
    src = project_dir / "raw" / "noaudio2.mp4"
    make_testsrc(src, duration_s=1.0, with_audio=False)
    result = run_prep(project_dir, [str(src), "--purpose", "context", "--key", "clip3", "--no-fix"])
    assert result.returncode == 1
    assert "no audio track" in result.stderr
    assert not (project_dir / "raw" / "noaudio2-a.mp4").is_file()


@pytest.mark.ffmpeg
def test_mp4_with_audio_is_untouched(project_dir):
    src = project_dir / "raw" / "hasaudio.mp4"
    make_testsrc(src, duration_s=1.0, with_audio=True)
    result = run_prep(project_dir, [str(src), "--purpose", "context", "--key", "clip4"])
    assert result.returncode == 0, result.stderr
    assert "silent track" not in result.stderr
    project = json.loads((project_dir / "project.json").read_text())
    assert project["assets"]["clip4"]["file"] == "raw/hasaudio.mp4"


# ---------------------------------------------------------------------------
# Duration floors/ceilings per purpose (QA P0: a 34.3s clip uploaded with
# --purpose episode was REJECTED permanently server-side — no local check
# caught it before the file traveled). Mirrors
# services/media/app/services/probe.py's real gate, checked locally first.
# ---------------------------------------------------------------------------

@pytest.mark.ffmpeg
def test_episode_below_60s_floor_fails_with_take_suggestion(project_dir):
    """The exact scenario QA hit: a 34.3s reel take uploaded as episode."""
    src = project_dir / "raw" / "clip34.mp4"
    make_fast_video_of_duration(src, 34.3)
    result = run_prep(project_dir, [str(src), "--purpose", "episode", "--key", "clip"])
    assert result.returncode == 1
    assert "34." in result.stderr  # frame-quantized duration, ~34.3-34.4s
    assert "60s floor" in result.stderr
    assert "--purpose take" in result.stderr


@pytest.mark.ffmpeg
def test_same_34s_clip_succeeds_as_take(project_dir):
    src = project_dir / "raw" / "clip34.mp4"
    make_fast_video_of_duration(src, 34.3)
    result = run_prep(project_dir, [str(src), "--purpose", "take", "--key", "clip", "--emit"])
    assert result.returncode == 0, result.stderr
    args = json.loads(result.stdout)
    assert args["purpose"] == "take"


@pytest.mark.ffmpeg
def test_take_below_1s_floor_fails(project_dir):
    src = project_dir / "raw" / "tiny.mp4"
    make_fast_video_of_duration(src, 0.5)
    result = run_prep(project_dir, [str(src), "--purpose", "take", "--key", "clip"])
    assert result.returncode == 1
    assert "1s floor" in result.stderr


@pytest.mark.ffmpeg
def test_take_over_600s_ceiling_fails(project_dir):
    src = project_dir / "raw" / "toolong.mp4"
    make_fast_video_of_duration(src, 605.0)
    result = run_prep(project_dir, [str(src), "--purpose", "take", "--key", "clip"])
    assert result.returncode == 1
    assert "600s" in result.stderr
    assert "ceiling" in result.stderr


@pytest.mark.ffmpeg
def test_context_over_600s_ceiling_fails(project_dir):
    src = project_dir / "raw" / "toolong.mp4"
    make_fast_video_of_duration(src, 605.0)
    result = run_prep(project_dir, [str(src), "--purpose", "context", "--key", "clip2"])
    assert result.returncode == 1
    assert "600s" in result.stderr


@pytest.mark.ffmpeg
def test_context_has_no_floor(project_dir):
    """A still image probes as 0s and must remain valid context material."""
    src = project_dir / "raw" / "verysh.mp4"
    make_fast_video_of_duration(src, 0.2)
    result = run_prep(project_dir, [str(src), "--purpose", "context", "--key", "clip2"])
    assert result.returncode == 0, result.stderr


def test_take_is_a_valid_purpose_choice(project_dir):
    """--purpose take must be accepted by argparse — QA's report was that it
    wasn't even offered as an option."""
    result = run_prep(project_dir, ["--help"])
    assert "take" in result.stdout
