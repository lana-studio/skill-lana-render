#!/usr/bin/env python3
"""tools/make_release.py — build the zip users download.

    python3 tools/make_release.py [--out dist/]

Writes dist/lana-reel-<version>.zip with exactly what a user needs:

    lana-reel/          the skill (version from lana-reel/VERSION)
    LEEME-PRIMERO.md
    INSTALAR.md
    DETALLES.md
    LICENSE
    NOTICE

Leaves out node_modules, __pycache__, *.pyc and .DS_Store. Prints the path of
the zip. Stdlib only.
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = "lana-reel"
DOCS = ("LEEME-PRIMERO.md", "INSTALAR.md", "DETALLES.md", "LICENSE", "NOTICE")
EXCLUDED_NAMES = {"node_modules", "__pycache__", ".DS_Store"}


def skill_files(skill: Path) -> list[Path]:
    out = []
    for path in sorted(skill.rglob("*")):
        rel = path.relative_to(skill)
        if any(part in EXCLUDED_NAMES for part in rel.parts) or path.suffix == ".pyc":
            continue
        if path.is_file():
            out.append(path)
    return out


def build(out_dir: Path) -> Path:
    skill = REPO_ROOT / SKILL_DIR
    version = (skill / "VERSION").read_text(encoding="utf-8").strip()
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"{SKILL_DIR}-{version}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in skill_files(skill):
            zf.write(path, (Path(SKILL_DIR) / path.relative_to(skill)).as_posix())
        for name in DOCS:
            zf.write(REPO_ROOT / name, name)
    return zip_path


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Build the user-facing release zip.")
    parser.add_argument("--out", default=str(REPO_ROOT / "dist"), help="Output directory (default: dist/).")
    args = parser.parse_args(argv)
    print(build(Path(args.out)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
