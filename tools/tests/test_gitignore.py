"""Tests for the repo's own .gitignore — specifically the entries this role
owns and keeps accurate as new local-leak vectors turn up.

QA ran the real proof render and found `lana/jobs/<id>.json`
holding a live, unredacted Azure signed URL — save_result.py's redaction
doesn't cover the real shape of a RENDER job result (bug routed to
python-scripts). `lana/` (transcript, silence, caps snapshots, job results,
extracted frames) wasn't in .gitignore at all, so if redaction fails again a
secret lands straight in a commit. Two layers, not one: redaction stops the
secret from being written; .gitignore stops it from being committed if
redaction fails anyway. Same reasoning extends to `lana-pkg/`: every file
under it is generated from `src/` + `project.json` + `videoconfig.py`, so the
whole directory is now ignored, not just `bundle.zip`.

These tests don't touch save_result.py or any other script (all
owned by other roles) — they only prove the .gitignore *patterns* actually
ignore the paths those scripts write to, using a real throwaway git repo so
`git status`/`git check-ignore` give ground truth instead of re-implementing
gitignore glob semantics by hand. Each test builds and tears down its own
tmp_path repo in the same function, so there's no cross-test teardown-ordering
hazard like the one QA found.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

OSS_ROOT = Path(__file__).resolve().parent.parent.parent  # oss/reel-skill/
GITIGNORE = OSS_ROOT / ".gitignore"


def _init_repo_with_gitignore(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    shutil.copy(GITIGNORE, repo / ".gitignore")
    return repo


def _is_ignored(repo: Path, rel_path: str) -> bool:
    result = subprocess.run(["git", "check-ignore", "-q", rel_path], cwd=repo)
    return result.returncode == 0


def test_skill_scripts_under_lana_are_not_swallowed_by_the_lana_pattern(tmp_path):
    # `lana/` ignores any directory named lana — including the skill's own
    # lana-reel/scripts/lana/. The negation must follow the skill folder, or a
    # new script there would silently never be committed.
    repo = _init_repo_with_gitignore(tmp_path)
    target = repo / "lana-reel" / "scripts" / "lana" / "new_script.py"
    target.parent.mkdir(parents=True)
    target.write_text("x", encoding="utf-8")
    assert not _is_ignored(repo, "lana-reel/scripts/lana/new_script.py")


# ---------------------------------------------------------------------------
# lana/ — the real scenario QA hit: a job result with a live signed URL in it
# ---------------------------------------------------------------------------

# A synthetic but realistically-shaped Azure blob SAS URL — same query-param
# shape check_clean.py's own signed-url rule looks for (sig=/sv=/se=), so this
# fixture protects the actual leak, not just an abstract path pattern.
FAKE_SIGNED_URL = (
    "https://lanamediadev.blob.core.windows.net/renders/8f2a91c0.mp4"
    "?sv=2023-01-03&sr=b&sig=q9fLp2K7x1ZbY6mRt0vN3sJ8dE5cA4wB%2FhU%3D&se=2026-09-18T00%3A00%3A00Z&sp=r"
)


def test_lana_dir_is_gitignored_including_a_job_with_a_live_signed_url(tmp_path):
    # Defense in depth: this must be ignored even though — especially because —
    # save_result.py's redaction is exactly what QA found broken. The
    # .gitignore layer doesn't care whether redaction worked; it blocks the
    # commit either way.
    repo = _init_repo_with_gitignore(tmp_path)
    jobs_dir = repo / "lana" / "jobs"
    jobs_dir.mkdir(parents=True)
    job_file = jobs_dir / "8f2a91c0-render.json"
    job_file.write_text(
        f'{{"status": "SUCCEEDED", "outputs": [{{"read_url": "{FAKE_SIGNED_URL}"}}]}}\n',
        encoding="utf-8",
    )

    assert _is_ignored(repo, "lana/jobs/8f2a91c0-render.json")

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], cwd=repo,
        capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    assert "lana/jobs/8f2a91c0-render.json" not in staged


@pytest.mark.parametrize("rel", [
    "lana/transcript.json",
    "lana/silence.json",
    "lana/takes.json",
    "lana/caps.limits.json",
    "lana/caps.library.json",
    "lana/frames/clip-50.jpg",
])
def test_lana_dir_covers_every_generated_result_file(tmp_path, rel):
    # This is the full set of files save_result.py / probe_source.py /
    # takes.py write under lana/ — cover the class, not just the one file QA
    # happened to hit.
    repo = _init_repo_with_gitignore(tmp_path)
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{}", encoding="utf-8")
    assert _is_ignored(repo, rel)


# ---------------------------------------------------------------------------
# lana-pkg/ — broadened from bundle.zip alone to the whole directory
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rel", [
    "lana-pkg/bundle.zip",
    "lana-pkg/bundle.sha256",
    "lana-pkg/props.json",
    "lana-pkg/files.json",
    "lana-pkg/used-assets.json",
    "lana-pkg/make_submit.args.json",
    "lana-pkg/src/Root.tsx",
    "lana-pkg/src/assets-manifest.ts",
])
def test_lana_pkg_dir_covers_every_generated_output_file(tmp_path, rel):
    # Everything under lana-pkg/ is generated from src/ + project.json +
    # videoconfig.py by make_pkg.py / build.py / make_bundle.py / each
    # script's --emit — none of it is source to commit.
    repo = _init_repo_with_gitignore(tmp_path)
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{}", encoding="utf-8")
    assert _is_ignored(repo, rel)


# ---------------------------------------------------------------------------
# legitimate project content must NEVER be swallowed by lana/ or lana-pkg/
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rel", [
    "src/index.tsx",
    "src/Root.tsx",
    "project.json",
    "videoconfig.py",
    "assets/card1.png",
])
def test_user_project_content_is_never_gitignored(tmp_path, rel):
    # src/ is the code the agent writes with the user, not a lana-pkg/src/
    # copy; project.json and videoconfig.py are project state the contract
    # explicitly says never carries a secret; assets/ (project-level, not
    # this repo's own assets/fonts|sfx) is user-provided source material like
    # card1.png. None of these are generated artifacts — ignoring them would
    # break the whole "the repo manages the user's real project" idea.
    repo = _init_repo_with_gitignore(tmp_path)
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("x", encoding="utf-8")
    assert not _is_ignored(repo, rel)
