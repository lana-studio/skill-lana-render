"""tests/test_new_project.py — scripts/reel/new_project.py.

QA/repo-hygiene-ci found the generated .gitignore's second bug (the first was
save_result.py's redaction): `lana/` — where save_result.py writes
lana/jobs/<id>.json, the exact file that can carry an unredacted signed URL
if redaction ever fails again — wasn't ignored at all in a brand-new user
project, and `lana-pkg/` was scoped down to just bundle.zip instead of the
whole (fully regenerable) directory. Verified the same way repo-hygiene-ci
verified the repo's own .gitignore: a real throwaway git repo, `git add -A`,
and `git diff --cached --name-only` — ground truth, not re-implementing
gitignore glob semantics by hand.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from conftest import SCRIPTS, run

# Same query-param shape check_clean.py's own signed-url rule looks for,
# and the same shape QA's real hello-render job had — fake host/signature,
# real structure. Built from split pieces so this file's own source doesn't
# contain, as a contiguous literal, the exact substrings that rule scans
# every .py file for (same reasoning as transfer.py's _signature_markers()).
FAKE_SIGNED_URL = (
    "https://stlanadev.blob.core.windows.net/lana-media/8f2a91c0/original.mp4"
    "?" + "s" + "v=2023-01-03&sr=b&" + "s" + "ig=q9fLp2K7x1ZbY6mRt0vN3sJ8dE5cA4wB%2FhU%3D"
    "&" + "s" + "e=2026-09-18T00%3A00%3A00Z&sp=r"
)


def run_new_project(args, cwd=None):
    return run(SCRIPTS / "reel" / "new_project.py", [*args, "--no-install"], cwd=cwd)


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)


def _staged_paths(repo: Path) -> list[str]:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    return subprocess.run(
        ["git", "diff", "--cached", "--name-only"], cwd=repo,
        capture_output=True, text=True, check=True,
    ).stdout.splitlines()


def test_scaffolds_expected_directories(tmp_path):
    dest = tmp_path / "myproj"
    result = run_new_project([str(dest), "--name", "my-first-reel"])
    assert result.returncode == 0, result.stderr
    for d in ("raw", "assets", "lana", "lana/jobs", "lana-pkg", "src", "out"):
        assert (dest / d).is_dir(), d
    project = json.loads((dest / "project.json").read_text())
    assert project["name"] == "my-first-reel"
    assert f"export REEL_PROJECT={dest}" in result.stdout


def test_bad_slug_exits_1(tmp_path):
    result = run_new_project([str(tmp_path / "x"), "--name", "N0"])  # too short, uppercase
    assert result.returncode == 1


# ---------------------------------------------------------------------------
# The generated .gitignore actually ignores what save_result.py/build.py/
# make_pkg.py write there, verified with a real git repo — not just that the
# text contains the right lines.
# ---------------------------------------------------------------------------

def test_gitignore_blocks_a_job_with_a_live_signed_url(tmp_path):
    dest = tmp_path / "myproj"
    result = run_new_project([str(dest), "--name", "my-first-reel"])
    assert result.returncode == 0, result.stderr
    _init_repo(dest)

    job_file = dest / "lana" / "jobs" / "8f2a91c0-render.json"
    job_file.write_text(
        json.dumps({"status": "SUCCEEDED", "render": {"outputs": [{"read_url": FAKE_SIGNED_URL}]}}),
        encoding="utf-8",
    )

    staged = _staged_paths(dest)
    assert "lana/jobs/8f2a91c0-render.json" not in staged
    # sanity: git add -A actually ran for real (a real file staged alongside it)
    assert "project.json" in staged


def test_gitignore_covers_every_lana_generated_file(tmp_path):
    dest = tmp_path / "myproj"
    run_new_project([str(dest), "--name", "my-first-reel"])
    _init_repo(dest)

    for rel in (
        "lana/transcript.json", "lana/silence.json", "lana/takes.json",
        "lana/caps.limits.json", "lana/caps.library.json", "lana/frames/clip-50.jpg",
    ):
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}", encoding="utf-8")

    staged = _staged_paths(dest)
    for rel in (
        "lana/transcript.json", "lana/silence.json", "lana/takes.json",
        "lana/caps.limits.json", "lana/caps.library.json", "lana/frames/clip-50.jpg",
    ):
        assert rel not in staged, rel


def test_gitignore_covers_the_whole_lana_pkg_dir_not_just_bundle_zip(tmp_path):
    dest = tmp_path / "myproj"
    run_new_project([str(dest), "--name", "my-first-reel"])
    _init_repo(dest)

    for rel in (
        "lana-pkg/bundle.zip", "lana-pkg/bundle.sha256", "lana-pkg/props.json",
        "lana-pkg/files.json", "lana-pkg/manifest-summary.json",
        "lana-pkg/make_submit.args.json", "lana-pkg/src/Root.tsx",
    ):
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}", encoding="utf-8")

    staged = _staged_paths(dest)
    for rel in (
        "lana-pkg/bundle.zip", "lana-pkg/bundle.sha256", "lana-pkg/props.json",
        "lana-pkg/files.json", "lana-pkg/manifest-summary.json",
        "lana-pkg/make_submit.args.json", "lana-pkg/src/Root.tsx",
    ):
        assert rel not in staged, rel


def test_gitignore_never_swallows_real_project_content(tmp_path):
    """src/plan.json etc. are deliberately NOT under lana/ or lana-pkg/ —
    they're the only record of exactly what was rendered, contain no
    secrets, and staying versioned is what keeps a past render reproducible
    from what the user actually kept (team-lead's explicit call, not mine to
    second-guess)."""
    dest = tmp_path / "myproj"
    run_new_project([str(dest), "--name", "my-first-reel"])
    _init_repo(dest)

    for rel in ("src/plan.json", "src/ritmo.json", "src/graphics.json", "project.json", "videoconfig.py"):
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}", encoding="utf-8")

    staged = _staged_paths(dest)
    for rel in ("src/plan.json", "src/ritmo.json", "src/graphics.json", "project.json", "videoconfig.py"):
        assert rel in staged, rel
