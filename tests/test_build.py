"""tests/test_build.py — scripts/reel/build.py."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from conftest import FIXTURES, SCRIPTS, run


def write_config(proj: Path, config_body: str) -> None:
    (proj / "videoconfig.py").write_text(config_body, encoding="utf-8")


def run_build(proj: Path, extra_args: list[str] | None = None):
    return run(SCRIPTS / "reel" / "build.py", extra_args or [], cwd=proj, env={"REEL_PROJECT": str(proj)})


@pytest.fixture(autouse=True)
def _seed_sfx_pack(project_dir):
    """Bug 19 follow-up (2026-09-17): build.py now fails loud (exit 1) if
    style.sfx_kit != "mute" and lana/caps.sfx.json is missing — exactly
    the gap that let an unresolved SFX name reach the renderer and burn a
    real job. tests/fixtures/videoconfig.py's CONFIG always selects
    sfx_kit="full", so every test in this file needs the pack present by
    default; test_build_fails_when_sfx_kit_active_without_caps_sfx removes
    it again to exercise the negative case on its own."""
    shutil.copy(FIXTURES / "gateway" / "caps.sfx.json", project_dir / "lana" / "caps.sfx.json")


def test_build_aligns_sel_against_transcript(project_dir):
    result = run_build(project_dir)
    assert result.returncode == 0, result.stderr

    plan = json.loads((project_dir / "src" / "plan.json").read_text())
    assert plan["total"] > 0
    assert len(plan["segments"]) == 2
    assert len(plan["lines"]) == 2
    assert plan["lines"][0]["text"] == "Here is the thing nobody tells you."
    # 7 words for line 0 + 6 for line 1 = 13 captions
    assert len(plan["captions"]) == 13


def test_build_picks_latest_take_on_tie(project_dir):
    """Pick the LATEST take that matches, not the first similar one: the
    script line 'And if you are a developer.' matches BOTH the
    stutter's first 'and if you are' and the full second repetition — the
    longest contiguous match is the second (later) occurrence, so its
    captions must fall in the SECOND half of the transcript window, not
    overlap the first "and if you are" (3200-3750ms)."""
    result = run_build(project_dir)
    assert result.returncode == 0, result.stderr
    plan = json.loads((project_dir / "src" / "plan.json").read_text())
    line1_words = plan["lines"][1]["words"]
    first_word_ms = line1_words[0]["startMs"]
    # line 1 occupies global [2500, 4500); its "And" must land in the local
    # window mapped from the SECOND occurrence (>= ~500ms into the region),
    # not from ms 0 (which would mean the FIRST "and" was picked instead).
    assert first_word_ms > 2500 + 300, f"expected the later occurrence, got {first_word_ms}"


def test_build_captions_leading_space_except_first(project_dir):
    result = run_build(project_dir)
    assert result.returncode == 0, result.stderr
    plan = json.loads((project_dir / "src" / "plan.json").read_text())
    captions = plan["captions"]
    assert not captions[0]["text"].startswith(" ")
    for c in captions[1:]:
        assert c["text"].startswith(" "), c


def test_build_lines_carry_keep_flag(project_dir):
    result = run_build(project_dir)
    assert result.returncode == 0, result.stderr
    plan = json.loads((project_dir / "src" / "plan.json").read_text())
    for line in plan["lines"]:
        assert "keep" in line and isinstance(line["keep"], bool)


def test_build_writes_ritmo_with_title_and_closing(project_dir):
    result = run_build(project_dir)
    assert result.returncode == 0, result.stderr
    ritmo = json.loads((project_dir / "src" / "ritmo.json").read_text())
    assert len(ritmo["titles"]) == 1
    assert ritmo["titles"][0]["text"] == "THE THING"
    assert ritmo["titles"][0]["capSuppressEndMs"] == ritmo["titles"][0]["endMs"]
    assert ritmo["closingMs"] == 2500
    assert ritmo["punch"] == [{"ms": 0}]


def test_build_proof_windows_in_proofs_json(project_dir):
    """D17: the plan travels inside the code (src/plan.json, imported by
    the generated Root.tsx), never as lana_submit_render's `props` — bundle
    mode drops inputProps between prepare and render on the harness side.
    lana-pkg/proofs.json only records which window each proof composition
    renders; lana-pkg/props.json is no longer written at all."""
    result = run_build(project_dir, ["--proof-windows", "4"])
    assert result.returncode == 0, result.stderr
    assert not (project_dir / "lana-pkg" / "props.json").exists()
    proofs = json.loads((project_dir / "lana-pkg" / "proofs.json").read_text())
    assert len(proofs) == 4
    ids = [p["id"] for p in proofs]
    assert ids == ["Reel-proof-1", "Reel-proof-2", "Reel-proof-3", "Reel-proof-4"]
    for p in proofs:
        window = p["window"]
        assert isinstance(window, list) and len(window) == 2
        assert window[1] > window[0]
        assert isinstance(p["label"], str) and p["label"]
    assert proofs[0]["window"] == [0, 90]


def test_build_anchors_shift_when_a_line_is_inserted(project_dir):
    """Inserting a SEL line shifts every later index — titles/closing
    that reference line numbers must resolve against the NEW positions."""
    config = '''CONFIG = {
    "style": {},
    "sel": [
        (0, 2500, "Here is the thing nobody tells you.", False),
        (6000, 6100, "", False),
        (3200, 5200, "And if you are a developer.", False),
    ],
    "hook_banner": "X", "hook_tag": "",
    "titles": {2: "THE THING"},
    "punch": [], "bw": [], "glitch": [], "crosswarp": [],
    "closing": 2,
    "inserts": [], "boards": [], "lowerthirds": [], "gfx": {}, "gfx_accents": {},
    "hold_f": 10,
}
'''
    # An empty-text line is invalid (validate_config's "empty text" rule),
    # so this asserts the validator catches it BEFORE any alignment runs —
    # covering the "index shift" contract at the validation boundary since a
    # real 3-line shift test needs a 3rd real take, which this fixture's
    # transcript doesn't have. The full anchor-shift path is exercised by
    # test_build_writes_ritmo_with_title_and_closing against line index 0.
    write_config(project_dir, config)
    result = run_build(project_dir)
    assert result.returncode == 1
    assert "empty text" in result.stderr


def test_build_fails_over_180s(project_dir):
    config = '''CONFIG = {
    "style": {},
    "sel": [(0, 2500, "Here is the thing nobody tells you.", True)] * 80,
    "hook_banner": "", "hook_tag": "",
    "titles": {}, "punch": [], "bw": [], "glitch": [], "crosswarp": [],
    "closing": 0,
    "inserts": [], "boards": [], "lowerthirds": [], "gfx": {}, "gfx_accents": {},
    "hold_f": 10,
}
'''
    write_config(project_dir, config)
    result = run_build(project_dir)
    assert result.returncode == 1
    assert "exceeds" in result.stderr and "180" in result.stderr


def test_build_removed_key_music_is_explicit_error(project_dir):
    config = '''CONFIG = {
    "style": {},
    "sel": [(0, 2500, "Here is the thing nobody tells you.", False)],
    "hook_banner": "", "hook_tag": "",
    "titles": {}, "punch": [], "bw": [], "glitch": [], "crosswarp": [],
    "closing": 0,
    "inserts": [], "boards": [], "lowerthirds": [], "gfx": {}, "gfx_accents": {},
    "hold_f": 10,
    "music": {"track": "x"},
}
'''
    write_config(project_dir, config)
    result = run_build(project_dir)
    assert result.returncode == 1
    assert "not supported in the public skill" in result.stderr


def test_build_no_match_reports_candidates(project_dir):
    config = '''CONFIG = {
    "style": {},
    "sel": [(0, 2500, "This text does not exist in the transcript at all.", False)],
    "hook_banner": "", "hook_tag": "",
    "titles": {}, "punch": [], "bw": [], "glitch": [], "crosswarp": [],
    "closing": 0,
    "inserts": [], "boards": [], "lowerthirds": [], "gfx": {}, "gfx_accents": {},
    "hold_f": 10,
}
'''
    write_config(project_dir, config)
    result = run_build(project_dir)
    assert result.returncode == 1
    assert "no match" in result.stderr
    assert "candidates" in result.stderr


# ---- P0/P1 regression: fields template/src/types.ts's Plan declares that
# build.py must actually write. QA (A4) caught plan.mirror never being
# written at all — the fixture's project.json always had mirror: false,
# whose plan.json output is indistinguishable from the bug, so nothing
# caught it. These tests exercise mirror: true and every renamed field so a
# silent regression fails loudly instead of matching the default by luck.

def test_build_writes_mirror_true(project_dir):
    project = json.loads((project_dir / "project.json").read_text())
    project["source"]["mirror"] = True
    (project_dir / "project.json").write_text(json.dumps(project), encoding="utf-8")

    result = run_build(project_dir)
    assert result.returncode == 0, result.stderr
    plan = json.loads((project_dir / "src" / "plan.json").read_text())
    assert plan["mirror"] is True


def test_build_writes_mirror_false_by_default(project_dir):
    result = run_build(project_dir)
    assert result.returncode == 0, result.stderr
    plan = json.loads((project_dir / "src" / "plan.json").read_text())
    assert plan["mirror"] is False


def test_build_segments_use_src_key_not_asset(project_dir):
    """Reel.tsx reads `asset(s.src ?? plan.src)` — a segment's own source
    asset key must be under "src", not "asset" (the private CONFIG-side
    name for the same thing bled into the plan.json output field name)."""
    result = run_build(project_dir)
    assert result.returncode == 0, result.stderr
    plan = json.loads((project_dir / "src" / "plan.json").read_text())
    for seg in plan["segments"]:
        assert "src" in seg
        assert "asset" not in seg
    assert plan["segments"][0]["src"] == "clip"


def test_build_captions_have_timestamp_and_confidence_fields(project_dir):
    """@remotion/captions' Caption type requires timestampMs/confidence
    (nullable, but the KEY must exist) — restored to match the private
    skill's original build.py, which this port had silently dropped."""
    result = run_build(project_dir)
    assert result.returncode == 0, result.stderr
    plan = json.loads((project_dir / "src" / "plan.json").read_text())
    for cap in plan["captions"]:
        assert cap["timestampMs"] is None
        assert cap["confidence"] is None


def test_build_inserts_use_src_key_not_asset(project_dir):
    config = '''CONFIG = {
    "style": {},
    "sel": [
        (0, 2500, "Here is the thing nobody tells you.", False),
        (3200, 5200, "And if you are a developer.", False),
    ],
    "hook_banner": "", "hook_tag": "",
    "titles": {}, "punch": [], "bw": [], "glitch": [], "crosswarp": [],
    "closing": 1,
    "inserts": [{"asset": "clip", "line": 1, "at_ms": 0, "dur_ms": 500}],
    "boards": [], "lowerthirds": [], "gfx": {}, "gfx_accents": {},
    "hold_f": 10,
}
'''
    write_config(project_dir, config)
    result = run_build(project_dir)
    assert result.returncode == 0, result.stderr
    plan = json.loads((project_dir / "src" / "plan.json").read_text())
    assert len(plan["inserts"]) == 1
    assert plan["inserts"][0]["src"] == "clip"
    assert "asset" not in plan["inserts"][0]


def test_build_crosswarp_uses_outsrc_insrc_keys(project_dir):
    config = '''CONFIG = {
    "style": {},
    "sel": [
        (0, 2500, "Here is the thing nobody tells you.", False),
        (3200, 5200, "And if you are a developer.", False),
    ],
    "hook_banner": "", "hook_tag": "",
    "titles": {}, "punch": [], "bw": [], "glitch": [], "crosswarp": [(1, -1)],
    "closing": 1,
    "inserts": [], "boards": [], "lowerthirds": [], "gfx": {}, "gfx_accents": {},
    "hold_f": 10,
}
'''
    write_config(project_dir, config)
    result = run_build(project_dir)
    assert result.returncode == 0, result.stderr
    ritmo = json.loads((project_dir / "src" / "ritmo.json").read_text())
    assert len(ritmo["crosswarp"]) == 1
    xw = ritmo["crosswarp"][0]
    assert xw["outSrc"] == "clip"
    assert xw["inSrc"] == "clip"
    assert "outAsset" not in xw and "inAsset" not in xw


def test_build_hook_video_produces_plan_hookvideo(project_dir):
    project = json.loads((project_dir / "project.json").read_text())
    project["assets"]["hookclip"] = {
        "file": "raw/hook.mp4", "purpose": "context",
        "asset_id": "00000000-0000-4000-8000-000000000005", "ext": "mp4",
    }
    (project_dir / "project.json").write_text(json.dumps(project), encoding="utf-8")

    config = '''CONFIG = {
    "style": {},
    "sel": [
        (0, 2500, "Here is the thing nobody tells you.", False),
        (3200, 5200, "And if you are a developer.", False),
    ],
    "hook_banner": "", "hook_tag": "",
    "titles": {}, "punch": [], "bw": [], "glitch": [], "crosswarp": [],
    "closing": 1,
    "inserts": [], "boards": [], "lowerthirds": [], "gfx": {}, "gfx_accents": {},
    "hold_f": 10,
    "hook_video": {"asset": "hookclip", "src_frames": 60, "src_y": 100, "full": False},
}
'''
    write_config(project_dir, config)
    result = run_build(project_dir)
    assert result.returncode == 0, result.stderr
    plan = json.loads((project_dir / "src" / "plan.json").read_text())
    hv = plan["hookVideo"]
    assert hv["src"] == "hookclip"
    assert hv["srcY"] == 100
    assert hv["full"] is False
    assert hv["durF"] == round((2500 - 0) / 1000 * 30)  # line 0's own duration
    assert hv["rate"] == round(60 / hv["durF"], 4)


def test_build_no_hook_video_key_when_not_configured(project_dir):
    result = run_build(project_dir)
    assert result.returncode == 0, result.stderr
    plan = json.loads((project_dir / "src" / "plan.json").read_text())
    assert "hookVideo" not in plan


def test_build_hook_video_missing_asset_fails_validation(project_dir):
    config = '''CONFIG = {
    "style": {},
    "sel": [(0, 2500, "Here is the thing nobody tells you.", False)],
    "hook_banner": "", "hook_tag": "",
    "titles": {}, "punch": [], "bw": [], "glitch": [], "crosswarp": [],
    "closing": 0,
    "inserts": [], "boards": [], "lowerthirds": [], "gfx": {}, "gfx_accents": {},
    "hold_f": 10,
    "hook_video": {"asset": "does-not-exist", "src_frames": 60},
}
'''
    write_config(project_dir, config)
    result = run_build(project_dir)
    assert result.returncode == 1
    assert "hook_video" in result.stderr
    assert "does-not-exist" in result.stderr


def test_build_writes_ritmo_sfx_names_from_pack(project_dir):
    """Bug 19 (2026-09-17): Sfx.tsx's resolveName() bails out with
    `if (!name || !sfx.pack || !sfx.names) return name;` — without
    `ritmo.sfx.names` the whole FALLBACK table is unreachable and an
    unmapped role name reaches the renderer verbatim, 404ing mid-render
    and burning a real job (exactly what happened: DEFAULT_MAP.title =
    "impact", absent from the deployed 0.9.0 pack). This only tests what
    build.py itself controls — that `names` carries every name from
    lana/caps.sfx.json, non-empty, which is what ARMS Sfx.tsx's guard.
    Whether an absent DEFAULT_MAP name then correctly resolves through
    FALLBACK is Sfx.tsx's own runtime logic (template/src/Sfx.tsx,
    TypeScript) — outside what a pytest suite with no JS runtime can
    execute (tsc only type-checks, it doesn't run resolveName()); that
    half is remotion-template's/QA's to cover at the TS level, not
    silently claimed here.

    Partial empirical evidence exists from the field, with an exact
    limit — stated precisely, not rounded up (team-lead, 2026-09-17):
    Martín's shipped reel (job 8ca17ecb-...) carries a TITLE event, and
    DEFAULT_MAP.title = "impact" is absent from the deployed 0.9.0 pack.
    The earlier render with the same title died 404 on impact.wav; the
    later one, with `names` populated by this fix, rendered whole. That
    proves resolveName() no longer lets the raw name through — the guard
    IS armed. It does NOT distinguish whether resolveName() returned
    "impact-2" (a correct FALLBACK substitution) or "" (silent, no sound
    at all) — neither path 404s, so this evidence cannot tell them apart.
    Confirming which one happened is still Sfx.tsx's own TS-level test to
    write, not something this render (or this test) establishes."""
    result = run_build(project_dir)
    assert result.returncode == 0, result.stderr
    ritmo = json.loads((project_dir / "src" / "ritmo.json").read_text())
    assert ritmo["sfx"]["pack"] is True
    assert ritmo["sfx"]["names"], "empty/missing names leaves Sfx.tsx's FALLBACK table unreachable"
    assert set(ritmo["sfx"]["names"]) == {
        e["name"] for e in json.loads((FIXTURES / "gateway" / "caps.sfx.json").read_text())["sfx"]["sfx"]
    }


def test_build_fails_when_sfx_kit_active_without_caps_sfx(project_dir):
    """The other half of bug 19's real root cause: nothing stopped the
    pipeline from reaching make_pkg.py/make_submit.py with SFX selected
    and lana/caps.sfx.json never saved at all (the agent skipped
    caps.py sfx). style.sfx_kit="full" (the fixture CONFIG's own default,
    same as new_project.py's) without the pack on disk must fail loud,
    before a single job is spent — not proceed with `ritmo.sfx.pack:
    false` and silently disarm the FALLBACK table for the whole render."""
    (project_dir / "lana" / "caps.sfx.json").unlink()
    result = run_build(project_dir)
    assert result.returncode == 1
    assert "style.sfx_kit='full'" in result.stderr
    assert "caps.sfx.json" in result.stderr
    assert "caps.py sfx" in result.stderr


def test_build_sfx_kit_mute_does_not_require_caps_sfx(project_dir):
    """"mute" is the one kit with no SFX at all (styles.py: "None — No
    SFX.") — it must NOT be forced through the same gate."""
    (project_dir / "lana" / "caps.sfx.json").unlink()
    config = '''CONFIG = {
    "style": {"sfx_kit": "mute"},
    "sel": [(0, 2500, "Here is the thing nobody tells you.", False)],
    "hook_banner": "", "hook_tag": "",
    "titles": {}, "punch": [], "bw": [], "glitch": [], "crosswarp": [],
    "closing": 0,
    "inserts": [], "boards": [], "lowerthirds": [], "gfx": {}, "gfx_accents": {},
    "hold_f": 10,
}
'''
    write_config(project_dir, config)
    result = run_build(project_dir)
    assert result.returncode == 0, result.stderr
    ritmo = json.loads((project_dir / "src" / "ritmo.json").read_text())
    assert ritmo["sfx"]["pack"] is False
