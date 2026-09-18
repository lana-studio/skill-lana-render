#!/usr/bin/env python3
"""install.py — install the reel-skill family into ~/.claude/skills/.

One script family shared by both skills, installed by copy (or by symlink
in --link mode, for local development).

    python3 install.py [--link] [--skills reel,lana-mcp-render] [--dest ~/.claude/skills] [--dry-run]

Behavior:
  1. Reads VERSION and `git rev-parse --short HEAD` (or "unknown" without git).
  2. For each requested skill (default: both `reel` and `lana-mcp-render`):
       - if <dest>/<name> already exists (dir or symlink), it is MOVED (never
         deleted) to ~/.claude/skill-backups/<name>-<YYYY-MM-DD-HHMM>/.
       - copy mode (default): copytree(skills/<name>) -> <dest>/<name>, then
         copy scripts/, template/, assets/ into it (excludes __pycache__,
         node_modules, .DS_Store, tests/).
       - --link mode: symlink(<repo>/skills/<name>, <dest>/<name>); creates
         <repo>/skills/<name>/{scripts,template,assets} as relative symlinks
         back to the repo root if they don't already exist (these three names
         are gitignored precisely so --link can create them without dirtying
         the tree).
       - writes <dest>/<name>/INSTALLED.json.
  3. Prints a summary and the next step (`python3 setup.py`).

Exit 0 only if every requested skill installed; 2 if skills/<name>/SKILL.md is
missing from the repo. Stdlib only. Never touches ~/.claude/settings.json or
~/.claude.json.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
ALL_SKILLS = ("reel", "lana-mcp-render")
SHARED_DIRS = ("scripts", "template", "assets")
COPY_EXCLUDES = {"__pycache__", "node_modules", ".DS_Store", "tests"}


def _ignore(_dir: str, names: list[str]) -> set[str]:
    return {n for n in names if n in COPY_EXCLUDES or n.endswith(".pyc")}


def read_version() -> str:
    path = REPO_ROOT / "VERSION"
    return path.read_text(encoding="utf-8").strip() if path.is_file() else "unknown"


def read_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


def backup_existing(dest_skill: Path, backups_root: Path, dry_run: bool) -> None:
    if not (dest_skill.is_dir() or dest_skill.is_symlink()):
        return
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    target = backups_root / f"{dest_skill.name}-{stamp}"
    print(f"backup: {dest_skill} -> {target}")
    if dry_run:
        return
    backups_root.mkdir(parents=True, exist_ok=True)
    shutil.move(str(dest_skill), str(target))


def install_copy(name: str, dest: Path, dry_run: bool) -> None:
    src_skill = REPO_ROOT / "skills" / name
    dst_skill = dest / name
    if dry_run:
        print(f"[dry-run] copytree {src_skill} -> {dst_skill}")
    else:
        shutil.copytree(src_skill, dst_skill, ignore=_ignore)
    for shared in SHARED_DIRS:
        src = REPO_ROOT / shared
        if not src.is_dir():
            continue
        dst = dst_skill / shared
        if dry_run:
            print(f"[dry-run] copytree {src} -> {dst}")
            continue
        shutil.copytree(src, dst, ignore=_ignore, dirs_exist_ok=True)


def install_link(name: str, dest: Path, dry_run: bool) -> None:
    src_skill = REPO_ROOT / "skills" / name
    dst_skill = dest / name
    if dry_run:
        print(f"[dry-run] symlink {dst_skill} -> {src_skill}")
    else:
        dest.mkdir(parents=True, exist_ok=True)
        dst_skill.symlink_to(src_skill, target_is_directory=True)
    for shared in SHARED_DIRS:
        link_path = src_skill / shared
        target = REPO_ROOT / shared
        if link_path.exists() or link_path.is_symlink() or not target.is_dir():
            continue
        rel = Path("..") / ".." / shared
        if dry_run:
            print(f"[dry-run] symlink {link_path} -> {rel}")
        else:
            link_path.symlink_to(rel, target_is_directory=True)


def write_installed_marker(dest_skill: Path, name: str, version: str, commit: str, mode: str, dry_run: bool) -> None:
    import json

    payload = {
        "name": name,
        "version": version,
        "commit": commit,
        "installed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": mode,
        "repo": str(REPO_ROOT),
    }
    marker = dest_skill / "INSTALLED.json"
    if dry_run:
        print(f"[dry-run] write {marker}: {payload}")
        return
    marker.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Install the reel-skill family into ~/.claude/skills/.")
    parser.add_argument("--link", action="store_true", help="Symlink instead of copying (for development).")
    parser.add_argument("--skills", default=",".join(ALL_SKILLS), help="Comma-separated skill names (default: both).")
    parser.add_argument("--dest", default="~/.claude/skills", help="Destination skills directory.")
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen without writing anything.")
    args = parser.parse_args(argv)

    names = [n.strip() for n in args.skills.split(",") if n.strip()]
    dest = Path(args.dest).expanduser().resolve()
    backups_root = Path("~/.claude/skill-backups").expanduser()
    version = read_version()
    commit = read_commit()
    mode = "link" if args.link else "copy"

    ok = True
    for name in names:
        src_skill_md = REPO_ROOT / "skills" / name / "SKILL.md"
        if not src_skill_md.is_file():
            print(f"!! skills/{name}/SKILL.md not found in the repo — nothing to install", file=sys.stderr)
            ok = False
            continue

        dest_skill = dest / name
        backup_existing(dest_skill, backups_root, args.dry_run)

        if args.link:
            install_link(name, dest, args.dry_run)
        else:
            install_copy(name, dest, args.dry_run)

        write_installed_marker(dest_skill, name, version, commit, mode, args.dry_run)
        print(f"installed {name} {version} ({commit}) -> {dest_skill} [{mode}]")

    if ok:
        print("\nnext: python3 setup.py")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
