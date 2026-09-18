"""tests/test_conftest_skip_policy.py — the recursive test: proves
tests/conftest.py's skip-allowlist policy (pytest_runtest_logreport +
pytest_sessionfinish, tests/deferred_skips.py) actually enforces what it
claims, against REAL `pytest` runs — never a fabricated log.

This is the recursive corollary D18 names explicitly:
"toda defensa nueva se prueba contra el artefacto real, incluida la
defensa contra usar sustitutos." The first version of this whole defense
(a CI step grepping a pytest log for keywords) passed two hand-written test
logs and then broke against the real one — it matched the file PATH
`tests/test_gateway_shapes.py` and turned 7 deliberate skips red. Testing
this version against anything OTHER than a real `pytest` subprocess run
would repeat that exact mistake one level up: "the guard against fixtures
invented from memory, verified with a fixture invented from memory."

Four cases, each a REAL subprocess `pytest` invocation against this real
tree (temp files injected directly into tests/, never a `pytester`
sandbox or an isolated fixture tree):

1. The actual, full test suite (tests/ + tools/tests/, matching CI's own
   invocation) — exit 0, with exactly the real DEFERRED-CAPTURE skips
   (tests/deferred_skips.py.DEFERRED, count not re-stated here on purpose)
   and no violation markers.
2. An unlisted `pytest.skip()` call INSIDE a test body — the shape this
   whole amendment exists for (invisible to a filename grep or a marker
   selection alike).
3. An unlisted module-level `pytestmark = pytest.mark.skipif(True, ...)` —
   a DIFFERENT mechanism (this file's own earlier form, before hallazgo
   17), proving the policy is blind to HOW a test skips, not just to one
   specific shape of it.
4. A `tests/deferred_skips.py` entry that no longer actually skips (the
   fixture landed, the decorator was removed, but the entry wasn't) — the
   exact scenario that will happen for real the moment one of team-lead's
   captures closes a deferral.

Every injected temp file is removed, and deferred_skips.py restored to its
original content, in a `finally` block — these tests must never leave the
real tree in a broken state even if an assertion fails mid-way.
"""
from __future__ import annotations

import subprocess
import sys

from conftest import REPO_ROOT

TESTS_DIR = REPO_ROOT / "tests"
DEFERRED_SKIPS_PATH = TESTS_DIR / "deferred_skips.py"


def _run_pytest(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-rs", *args],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )


def test_real_suite_has_exactly_the_deferred_skips():
    """Case 1: the actual, full suite, run for real — not a captured log.
    Excludes THIS file: CI's own invocation (`pytest tests tools/tests`,
    no --ignore) includes it normally, but a self-recursive subprocess call
    from inside one of its own tests would otherwise spawn the whole suite
    — itself included — inside itself, without bound."""
    result = _run_pytest("--ignore=tests/test_conftest_skip_policy.py", "tests", "tools/tests")
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "!! unexpected skip" not in output
    assert "!! deferral closed but still listed" not in output


def test_injected_inline_skip_fails_the_session():
    """Case 2: an unlisted pytest.skip() call inside a test body."""
    injected = TESTS_DIR / "_tmp_policy_check_inline_skip.py"
    injected.write_text(
        'import pytest\n\n\ndef test_x():\n    pytest.skip("unregistered reason")\n',
        encoding="utf-8",
    )
    try:
        result = _run_pytest(f"tests/{injected.name}")
    finally:
        injected.unlink()
    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert f"!! unexpected skip: tests/{injected.name}::test_x — unregistered reason" in output


def test_injected_module_skipif_fails_the_session():
    """Case 3: an unlisted module-level skipif — a DIFFERENT mechanism
    from case 2 (this is the exact shape test_make_pkg_typecheck.py used
    before hallazgo 17), proving the policy doesn't just catch one form."""
    injected = TESTS_DIR / "_tmp_policy_check_module_skipif.py"
    injected.write_text(
        'import pytest\n\n'
        'pytestmark = pytest.mark.skipif(True, reason="unregistered module skip")\n\n\n'
        'def test_x():\n    pass\n',
        encoding="utf-8",
    )
    try:
        result = _run_pytest(f"tests/{injected.name}")
    finally:
        injected.unlink()
    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert f"!! unexpected skip: tests/{injected.name}::test_x — unregistered module skip" in output


def test_closed_deferral_still_listed_fails_the_session():
    """Case 4: a DEFERRED entry whose test no longer skips — the fixture
    arrived, the decorator came off, but the dict entry didn't. Patches
    deferred_skips.py's real content (never a copy) and restores it in
    `finally`, so this proves the policy against the actual file the real
    suite reads, not a stand-in."""
    injected = TESTS_DIR / "_tmp_policy_check_closed_deferral.py"
    injected.write_text("def test_x():\n    assert True\n", encoding="utf-8")
    nodeid = f"tests/{injected.name}::test_x"

    original = DEFERRED_SKIPS_PATH.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    # The DEFERRED dict's closing brace is the first line that's exactly
    # "}" AFTER the dict's opening — found by line content, not by
    # assuming the file ends there (deferred_skips.py may carry trailing
    # prose/comments after the dict, as it does today).
    close_idx = next(i for i, line in enumerate(lines) if line.rstrip("\n") == "}")
    injected_line = f'    {nodeid!r}: "DEFERRED-CAPTURE: fake — nobody",\n'
    patched_lines = lines[:close_idx] + [injected_line] + lines[close_idx:]
    patched = "".join(patched_lines)

    try:
        DEFERRED_SKIPS_PATH.write_text(patched, encoding="utf-8")
        result = _run_pytest(f"tests/{injected.name}")
    finally:
        DEFERRED_SKIPS_PATH.write_text(original, encoding="utf-8")
        injected.unlink()

    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert f"!! deferral closed but still listed: {nodeid}" in output
