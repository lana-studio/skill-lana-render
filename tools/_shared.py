"""Shared helpers for tools/check_clean.py and tools/check_no_network.py.

Internal to tools/ — not part of the public scripts/_lib/ family that ships
with the skills themselves (project.py, io.py, limits.py under scripts/_lib/);
this one ships only with the repo's own hygiene checks. Stdlib only.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

EXCLUDED_DIR_NAMES = {"node_modules", ".git", "__pycache__"}


def _is_excluded(rel: Path) -> bool:
    return any(part in EXCLUDED_DIR_NAMES for part in rel.parts)


def _has_git(root: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"
    except (OSError, subprocess.SubprocessError):
        return False


def list_files(root: Path) -> list[Path]:
    """Return every file under root, relative to root, that would ship.

    Uses `git ls-files` (cached + untracked-but-not-ignored) when root sits
    inside a git work tree — this covers both "already committed" and
    "about to be committed" (pre-first-push) scenarios. Falls back to a plain
    walk, excluding node_modules/.git/__pycache__, when there is no git.
    """
    root = root.resolve()
    if _has_git(root):
        try:
            result = subprocess.run(
                ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
            paths = [Path(p) for p in result.stdout.split("\0") if p]
            return sorted(p for p in paths if not _is_excluded(p) and (root / p).is_file())
        except (OSError, subprocess.SubprocessError):
            pass  # fall through to the walk-based listing below

    paths: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIR_NAMES]
        for name in filenames:
            rel = (Path(dirpath) / name).relative_to(root)
            if not _is_excluded(rel):
                paths.append(rel)
    return sorted(paths)


def is_allowed(rel: Path, allow_prefixes: list[str]) -> bool:
    """True if rel (posix-style relative path) sits under one of the --allow prefixes."""
    rel_posix = rel.as_posix()
    for prefix in allow_prefixes:
        prefix = prefix.strip("/")
        if not prefix:
            continue
        if rel_posix == prefix or rel_posix.startswith(prefix + "/"):
            return True
    return False


# Directories whose own tests already use clean fixtures (null UUID, no forbidden
# literals) and must therefore never be exempted from either checker via --allow —
# not the prefix itself, nor any path nested under it. Shared by check_clean.py and
# check_no_network.py so the two checkers can never drift on which dirs are off
# limits; see the pack's own --allow contract doc for the full rationale.
FORBIDDEN_ALLOW_PREFIXES = ("scripts", "template", "skills", "assets", "examples", "tests")


def forbidden_allow_prefix(allow_prefixes: list[str]) -> str | None:
    """Return the first --allow value that names (or sits under) a forbidden prefix,
    or None if every value is fine. `--allow scripts/lana` is just as forbidden as
    `--allow scripts` — a nested path still exempts part of a dir that must stay
    fully in scope."""
    for raw in allow_prefixes:
        prefix = raw.strip("/")
        if not prefix:
            continue
        for forbidden in FORBIDDEN_ALLOW_PREFIXES:
            if prefix == forbidden or prefix.startswith(forbidden + "/"):
                return raw
    return None


def allowed_skip_counts(files: list[Path], allow_prefixes: list[str]) -> list[tuple[str, int]]:
    """For every distinct --allow prefix (order preserved, de-duplicated, each file
    counted once under the first prefix it matches — same precedence as is_allowed),
    how many files from `files` it caused to be skipped. Both checkers must always
    report this, so a passed `--allow <dir>` can never hide what left scope."""
    order: list[str] = []
    counts: dict[str, int] = {}
    for raw in allow_prefixes:
        norm = raw.strip("/")
        if not norm or norm in counts:
            continue
        counts[norm] = 0
        order.append(norm)
    for rel in files:
        rel_posix = rel.as_posix()
        for norm in order:
            if rel_posix == norm or rel_posix.startswith(norm + "/"):
                counts[norm] += 1
                break
    return [(norm, counts[norm]) for norm in order]


def read_text(path: Path) -> str | None:
    """Best-effort text read; returns None for binary/undecodable files."""
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw[:8192]:
        return None  # treat as binary
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
