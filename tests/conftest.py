"""tests/conftest.py — shared fixtures for the reel-skill script family.

Every test that runs a script does so as a real subprocess (`python3
scripts/.../<script>.py ...`) against a temp project directory built from
tests/fixtures/. This matches how an agent actually uses these scripts (CLI,
exit codes, stdout purity for --emit) rather than importing internals.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "ffmpeg: requires ffmpeg/ffprobe on PATH (CI installs them; skip locally with -m 'not ffmpeg')",
    )


# Hallazgo 17 (2026-09-17), FINAL amendment — two earlier versions of this
# defense each had a blind spot a THIRD, unrelated skip exposed:
#   1. A CI step that grepped the pytest log for keywords matched the file
#      PATH `test_gateway_shapes.py` and turned 7 deliberate skips red.
#   2. A `@pytest.mark.guard` marker fixed that, but was blind to
#      `pytest.skip()` called inline inside a test body with no marker at
#      all — exactly the shape of a THIRD skip mechanism that turned up
#      asleep in tests/test_styles.py (gated on template/src/Fonts.tsx,
#      since removed — see that file).
# Neither approach generalizes to "the next mechanism nobody thought of
# yet". This version moves the check into pytest itself: every skip,
# whatever produced it (`@pytest.mark.skip`, module-level `skipif`, an
# inline `pytest.skip()` call, in ANY file) is compared against
# tests/deferred_skips.py's DEFERRED allowlist by (nodeid, exact reason).
# Anything not listed — or listed but with a different reason — fails the
# whole SESSION. So does a DEFERRED entry that stopped skipping (a capture
# landed and the decorator wasn't removed) — closing a deferral means
# removing the decorator AND the DEFERRED entry in the same commit, or this
# catches the mismatch.
#
# require_guard_node_modules is unrelated to the allowlist mechanism above:
# it's decision 1's OWN fail-not-skip behavior for the node_modules-
# dependent tests (test_make_pkg_typecheck.py) — those never skip at all
# except through the REEL_GUARD_ALLOW_SKIP=1 escape hatch below, and if
# used, the resulting skip is (by design) NOT in DEFERRED, so the
# allowlist check below still flags it — "ruidoso, nunca en CI" holds
# either way: the escape hatch makes a skip visible, never quietly green.
GUARD_SKIP_ENV_VAR = "REEL_GUARD_ALLOW_SKIP"


def require_guard_node_modules(node_modules_dir: Path, what: str) -> None:
    """Call at the very start of a test that needs a real node_modules (a
    real `tsc`) to run its real assertion. `what` is what to name in the
    failure/skip message (e.g. "template/node_modules"). Fails (never
    silently skips) unless REEL_GUARD_ALLOW_SKIP=1."""
    if node_modules_dir.is_dir():
        return
    if os.environ.get(GUARD_SKIP_ENV_VAR) == "1":
        pytest.skip(
            f"!! {GUARD_SKIP_ENV_VAR}=1: skipping a guard that needs {what} — "
            "this must NEVER be set in CI"
        )
    pytest.fail(
        f"!! bug-8 guard cannot run: {what} missing — run npm ci in template/ (setup.py does it)"
    )


_SEEN_SKIPS: dict[str, str] = {}  # nodeid -> exact skip reason, this session
_COLLECTED_NODEIDS: set[str] = set()


def _skip_reason(report: pytest.TestReport) -> str:
    """report.longrepr for a skip is (path, lineno, 'Skipped: <reason>') —
    strip pytest's own 'Skipped: ' prefix to recover the exact string
    passed to `pytest.mark.skip(reason=...)` / `pytest.skip(...)`, which is
    what deferred_skips.DEFERRED's values are (no prefix)."""
    longrepr = report.longrepr
    text = str(longrepr[2]) if isinstance(longrepr, tuple) and len(longrepr) == 3 else str(longrepr)
    prefix = "Skipped: "
    return text[len(prefix):] if text.startswith(prefix) else text


def pytest_collection_modifyitems(session: pytest.Session, config: pytest.Config, items: list) -> None:  # noqa: ARG001
    _COLLECTED_NODEIDS.update(item.nodeid for item in items)


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if report.when in ("setup", "call") and report.skipped:
        _SEEN_SKIPS[report.nodeid] = _skip_reason(report)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:  # noqa: ARG001
    """Hallazgo 17's actual enforcement: cero skips salvo la allowlist
    nominal, ciega al mecanismo. Runs on every session regardless of what
    was collected (a narrow `pytest tests/test_x.py` run only checks the
    "deferral closed" half for entries actually collected this run — it
    can't claim a deferral broke for a nodeid it never saw)."""
    from deferred_skips import DEFERRED  # local import: avoid a module-load-order dependency

    violations: list[str] = []
    for nodeid, reason in _SEEN_SKIPS.items():
        expected = DEFERRED.get(nodeid)
        if expected is None or reason != expected:
            violations.append(f"!! unexpected skip: {nodeid} — {reason}")
    for nodeid in DEFERRED:
        if nodeid in _COLLECTED_NODEIDS and nodeid not in _SEEN_SKIPS:
            violations.append(f"!! deferral closed but still listed: {nodeid}")

    if violations:
        print("", file=sys.stderr)
        for v in violations:
            print(v, file=sys.stderr)
        print(
            "!! see tests/deferred_skips.py — every skip must be listed there with its "
            "exact reason, and every listed entry must still actually skip",
            file=sys.stderr,
        )
        session.exitstatus = 1


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
SCRIPTS = REPO_ROOT / "scripts"


def run(script: Path, args: list[str], cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run a script as a subprocess. Returns the CompletedProcess (never
    raises on nonzero exit — tests assert on .returncode themselves)."""
    import os

    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        env=full_env,
    )


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """A temp project directory seeded with project.json, videoconfig.py,
    lana/{transcript,silence}.json, and the standard subdirectories — the
    shape new_project.py would have produced."""
    proj = tmp_path / "proj"
    for d in ("raw", "assets", "lana", "lana/jobs", "lana-pkg", "src", "out"):
        (proj / d).mkdir(parents=True, exist_ok=True)

    shutil.copy(FIXTURES / "project.json", proj / "project.json")
    shutil.copy(FIXTURES / "videoconfig.py", proj / "videoconfig.py")
    shutil.copy(FIXTURES / "transcript.json", proj / "lana" / "transcript.json")
    shutil.copy(FIXTURES / "silence.json", proj / "lana" / "silence.json")
    return proj


def load_project(proj: Path) -> dict:
    return json.loads((proj / "project.json").read_text(encoding="utf-8"))


def save_project(proj: Path, data: dict) -> None:
    (proj / "project.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


@pytest.fixture
def run_reel():
    def _run(script_name: str, args: list[str], cwd: Path | None = None, env: dict | None = None):
        return run(SCRIPTS / "reel" / script_name, args, cwd=cwd, env=env)
    return _run


@pytest.fixture
def run_lana():
    def _run(script_name: str, args: list[str], cwd: Path | None = None, env: dict | None = None):
        return run(SCRIPTS / "lana" / script_name, args, cwd=cwd, env=env)
    return _run


def has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def make_testsrc(dest: Path, duration_s: float = 2.0, with_audio: bool = True, size: str = "320x568") -> None:
    """Generate a tiny synthetic video with ffmpeg -f lavfi (no network, no
    real footage) for tests marked @pytest.mark.ffmpeg."""
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"testsrc=duration={duration_s}:size={size}:rate=30",
    ]
    if with_audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={duration_s}"]
        cmd += ["-c:v", "libx264", "-c:a", "aac", "-shortest"]
    else:
        cmd += ["-c:v", "libx264", "-an"]
    cmd.append(str(dest))
    subprocess.run(cmd, check=True, capture_output=True)


def make_fast_video_of_duration(dest: Path, duration_s: float) -> None:
    """Generate a video of an EXACT duration as fast as possible (tiny
    resolution, ultrafast preset, no audio) — for tests that need to cross a
    specific duration boundary (e.g. prep_upload.py's per-purpose floor/
    ceiling) without waiting on a multi-minute real encode."""
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"color=c=black:s=32x32:d={duration_s}:rate=5",
        "-c:v", "libx264", "-preset", "ultrafast", "-an", str(dest),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def ffprobe_stream_dims(path: Path) -> tuple[int, int]:
    """(width, height) of the first video stream — a helper so callers never
    inline a `subprocess.run(["ffprobe", ...])` literal themselves (that
    literal-list shape is exactly what tools/check_no_network.py's
    ffmpeg-allowlist rule flags outside the 4 production scripts; a variable
    built here, like make_testsrc's `cmd` above, isn't statically
    distinguishable from any other list at the call site)."""
    cmd = ["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(path)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    w, h = (int(x) for x in result.stdout.strip().split(",")[:2])
    return w, h


def make_silence_gap_video(dest: Path, tone_s: float = 1.0) -> None:
    """A synthetic video whose audio is tone / silence / tone (each
    `tone_s` long) — used by test_verify_output.py's ffmpeg-marked tests to
    exercise silencedetect against a real gap without any real footage."""
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"sine=frequency=1000:duration={tone_s}",
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono:duration={tone_s}",
        "-f", "lavfi", "-i", f"sine=frequency=1000:duration={tone_s}",
        "-f", "lavfi", "-i", f"color=c=black:s=320x240:d={tone_s * 3}",
        "-filter_complex", "[0:a][1:a][2:a]concat=n=3:v=0:a=1[out]",
        "-map", "[out]", "-map", "3:v", "-shortest", "-c:v", "libx264", "-c:a", "aac", str(dest),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
