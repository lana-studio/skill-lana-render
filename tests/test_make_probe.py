"""tests/test_make_probe.py — scripts/lana/make_probe.py."""
from __future__ import annotations

import json

from conftest import SCRIPTS, run


def test_emit_has_2_files_and_hello_composition():
    result = run(SCRIPTS / "lana" / "make_probe.py", ["--emit"])
    assert result.returncode == 0, result.stderr
    args = json.loads(result.stdout)
    assert args["compositions"] == ["Hello"]
    assert set(args["files"].keys()) == {"src/index.tsx", "src/Root.tsx"}
    assert args["assets"] == {}
    assert args["idempotency_key"].startswith("hello-render-")


def test_custom_font_and_sfx_are_used():
    result = run(SCRIPTS / "lana" / "make_probe.py", ["--emit", "--font", "Oswald", "--sfx", "click"])
    assert result.returncode == 0, result.stderr
    args = json.loads(result.stdout)
    assert "Oswald" in args["files"]["src/Root.tsx"]
    assert "sfx/click.wav" in args["files"]["src/Root.tsx"]
