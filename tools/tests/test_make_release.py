"""tools/make_release.py — the zip users download holds the skill and the
user docs, and nothing a contributor left lying around."""
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_release_zip_contents(tmp_path):
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "make_release.py"), "--out", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    version = (REPO_ROOT / "lana-reel" / "VERSION").read_text(encoding="utf-8").strip()
    zip_path = Path(result.stdout.strip())
    assert zip_path == tmp_path / f"lana-reel-{version}.zip"

    names = set(zipfile.ZipFile(zip_path).namelist())
    for required in (
        "LEEME-PRIMERO.md", "INSTALAR.md", "DETALLES.md", "LICENSE", "NOTICE",
        "lana-reel/SKILL.md", "lana-reel/KNOWHOW.md", "lana-reel/prompt-reel.md",
        "lana-reel/references/mcp.md", "lana-reel/scripts/lana/transfer.py",
        "lana-reel/template/package-lock.json", "lana-reel/assets/fonts/OFL.txt",
    ):
        assert required in names, required
    assert not any(n.startswith(("tests/", "tools/")) for n in names)
    assert not any(part in ("node_modules", "__pycache__", ".DS_Store") for n in names for part in n.split("/"))
