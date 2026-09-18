"""Tests for tools/check.py's step-sequencing logic (`run_steps`).

Deliberately does NOT invoke tools/check.py as a subprocess against the real
repo: its own pytest step would spawn this very test suite again (unbounded
self-recursion — the same hazard test_conftest_skip_policy.py's docstring
already calls out for a different file). Instead this exercises `run_steps`
directly with fake, instant step functions — the "stops at the first red,
skips the rest, reports N/total" behavior is orchestration logic that has
nothing to do with what any real step actually does.
"""
from __future__ import annotations

import importlib.util
import io
from pathlib import Path
from typing import Callable

TOOLS_DIR = Path(__file__).resolve().parent.parent


def _load_check_module():
    spec = importlib.util.spec_from_file_location("tools_check", TOOLS_DIR / "check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check = _load_check_module()


def _calls_log() -> tuple[list[str], list[tuple[str, Callable[[], int]]]]:
    """A 3-step plan where each step records that it ran; returns (log, steps)."""
    log: list[str] = []

    def make(name: str, code: int):
        def _step() -> int:
            log.append(name)
            return code
        return _step

    steps = [("a", make("a", 0)), ("b", make("b", 0)), ("c", make("c", 0))]
    return log, steps


def test_all_steps_ok_reports_full_count_and_runs_every_step():
    log, steps = _calls_log()
    buf = io.StringIO()
    code = check.run_steps(steps, out=buf)
    assert code == 0
    assert log == ["a", "b", "c"]
    assert "check: 3/3 ok" in buf.getvalue()


def test_middle_step_fails_stops_before_the_next_one():
    log, steps = _calls_log()
    # Replace "b" with a failing step.
    name, _ = steps[1]
    steps[1] = (name, lambda: 1)
    buf = io.StringIO()
    code = check.run_steps(steps, out=buf)
    assert code == 1
    # "c" never ran — the whole point of "para en el primer rojo".
    assert log == ["a"]
    output = buf.getvalue()
    assert "check: 1/3 ok" in output
    assert "[2/3] b failed (exit 1)" in output


def test_first_step_fails_nothing_after_it_runs():
    log, steps = _calls_log()
    name, _ = steps[0]
    steps[0] = (name, lambda: 1)
    buf = io.StringIO()
    code = check.run_steps(steps, out=buf)
    assert code == 1
    assert log == []
    assert "check: 0/3 ok" in buf.getvalue()


def test_last_step_fails_every_earlier_step_still_ran():
    log, steps = _calls_log()
    name, _ = steps[2]
    steps[2] = (name, lambda: 5)
    buf = io.StringIO()
    code = check.run_steps(steps, out=buf)
    assert code == 1
    assert log == ["a", "b"]
    assert "check: 2/3 ok" in buf.getvalue()
    assert "[3/3] c failed (exit 5)" in buf.getvalue()


def test_real_steps_list_has_the_five_documented_steps_in_order():
    """Pins the actual STEPS wiring — not what each step does (that's covered
    elsewhere: check_clean/check_no_network have their own tests, and running
    the real chain is covered by hand per the runbook), just that check.py
    still runs the five documented steps, in the documented order, and
    nothing got silently dropped or reordered."""
    names = [name for name, _ in check.STEPS]
    assert names == [
        "check_clean",
        "check_no_network",
        "template (npm ci + typecheck)",
        "pytest",
        "generated_pkg_check",
    ]
