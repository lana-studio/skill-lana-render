#!/usr/bin/env python3
"""tools/check.py — the repo's only check.

This repo has no CI (decision of Martín, 2026-09-17): it's a skill, not a library,
and GitHub Issues here are best-effort with no SLA. `tools/check.py` is what
replaced the five steps a GitHub Actions workflow used to run — one command,
chained in the same order, stopping at the first red:

    python3 tools/check.py

    1. check_clean.py --root . --allow tools/tests --json
    2. check_no_network.py --root . --allow tools/tests
    3. cd template && npm ci && npm run check
    4. pytest -q -rs tests tools/tests
    5. tools/generated_pkg_check.py

Order matters and is NOT incidental (hallazgo 17): step 4's pytest run depends on
step 3 having already left `template/node_modules` in place — bug 8's typecheck
guardian (`tests/test_make_pkg_typecheck.py`) self-skips into a false green
whenever `node_modules` doesn't exist yet. Running these five as one script with a
fixed list, instead of five ad-hoc commands typed by hand, is what makes that
ordering a property of the tool instead of something every future contributor has
to remember.

Prints `check: 5/5 ok` on a clean run, or names the step that failed (with its
exit code) and stops there — the remaining steps never run, same as the old
workflow's "para en el primer rojo". Exit 0 = clean, exit 1 = a step failed, exit 2
= couldn't even start a step (e.g. `npm`/`pytest` not on PATH).

Run this before opening a PR against this repo, and again before merging one —
there is no automation that will do either for you (see README.md "Support" and
the publication runbook's step 9). Only stdlib; every actual check still lives in
check_clean.py / check_no_network.py / the test suite, this just sequences them.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "lana-reel" / "template"


def _run(cmd: list[str], cwd: Path) -> int:
    """Run a step as a real subprocess, inheriting stdout/stderr so its own
    output (a findings table, a pytest summary, a tsc error) reaches the
    terminal directly — never captured and re-printed, never silenced."""
    try:
        return subprocess.run(cmd, cwd=str(cwd)).returncode
    except FileNotFoundError as exc:
        print(f"!! could not run {cmd[0]!r}: {exc}", file=sys.stderr)
        return 127


def step_check_clean() -> int:
    return _run(
        [sys.executable, "tools/check_clean.py", "--root", ".", "--allow", "tools/tests", "--json"],
        REPO_ROOT,
    )


def step_check_no_network() -> int:
    return _run(
        [sys.executable, "tools/check_no_network.py", "--root", ".", "--allow", "tools/tests"],
        REPO_ROOT,
    )


def step_template() -> int:
    code = _run(["npm", "ci"], TEMPLATE_DIR)
    if code != 0:
        return code
    return _run(["npm", "run", "check"], TEMPLATE_DIR)


def step_pytest() -> int:
    return _run([sys.executable, "-m", "pytest", "-q", "-rs", "tests", "tools/tests"], REPO_ROOT)


def step_generated_pkg_check() -> int:
    return _run([sys.executable, "tools/generated_pkg_check.py"], REPO_ROOT)


STEPS: list[tuple[str, Callable[[], int]]] = [
    ("check_clean", step_check_clean),
    ("check_no_network", step_check_no_network),
    ("template (npm ci + typecheck)", step_template),
    ("pytest", step_pytest),
    ("generated_pkg_check", step_generated_pkg_check),
]


def run_steps(steps: list[tuple[str, Callable[[], int]]], out=sys.stderr) -> int:
    """The actual sequencing logic, factored out from main() so it can be unit
    tested against fake steps (tools/tests/test_check.py) instead of only ever
    exercised by spawning real subprocesses — which from inside the test suite
    itself would mean pytest spawning tools/check.py spawning pytest, an
    unbounded self-recursion (the same hazard test_conftest_skip_policy.py's
    own docstring calls out)."""
    total = len(steps)
    for i, (name, step_fn) in enumerate(steps, start=1):
        print(f"-- [{i}/{total}] {name}", file=out)
        code = step_fn()
        if code != 0:
            print(f"check: {i - 1}/{total} ok — [{i}/{total}] {name} failed (exit {code})", file=out)
            return 1
    print(f"check: {total}/{total} ok", file=out)
    return 0


def main() -> int:
    return run_steps(STEPS)


if __name__ == "__main__":
    raise SystemExit(main())
