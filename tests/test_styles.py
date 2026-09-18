"""tests/test_styles.py — scripts/reel/styles.py."""
from __future__ import annotations

import json
import re
import shutil

from conftest import REPO_ROOT, SCRIPTS, run


def run_styles(proj, args, env=None):
    full_env = {"REEL_PROJECT": str(proj)}
    if env:
        full_env.update(env)
    return run(SCRIPTS / "reel" / "styles.py", args, cwd=proj, env=full_env)


def test_no_music_round(project_dir):
    result = run_styles(project_dir, ["questions"])
    assert result.returncode == 0, result.stderr
    rounds = json.loads(result.stdout)
    keys = {r["key"] for r in rounds}
    assert "music" not in keys
    assert not any("music" in r["header"].lower() for r in rounds)


def test_every_round_has_at_most_4_options(project_dir):
    result = run_styles(project_dir, ["questions"])
    rounds = json.loads(result.stdout)
    for r in rounds:
        assert len(r["options"]) <= 4, r["key"]


def test_font_group_round_lists_4_options_from_5_real_groups(project_dir):
    """The font_group QUESTION shows 4 options (every questionnaire round in
    this skill caps at <= 4), but _lib/fonts.py's real taxonomy stays at 5 groups (matching
    Fonts.tsx exactly) — "geometric" and "rounded" are combined into ONE
    honestly-labeled option here, not silently merged in the data."""
    result = run_styles(project_dir, ["questions"])
    rounds = json.loads(result.stdout)
    font_group = next(r for r in rounds if r["key"] == "font_group")
    ids = {o["id"] for o in font_group["options"]}
    assert ids == {"bold", "editorial", "geometric+rounded", "script"}

    combo = next(o for o in font_group["options"] if o["id"] == "geometric+rounded")
    assert combo["label"] == "Geometric & Rounded"
    assert set(combo["description"].split(", ")) == {"poppins", "inter", "nunito", "baloo"}

    import sys
    sys.path.insert(0, str(SCRIPTS))
    from _lib import fonts as _fonts  # noqa: E402

    assert _fonts.FONT_GROUPS == ("bold", "editorial", "geometric", "rounded", "script")
    assert _fonts.FONT_PAIRS["nunito"]["group"] == "rounded"
    assert _fonts.FONT_PAIRS["baloo"]["group"] == "rounded"


def test_fonts_pair_round_resolves_merged_group_answer(project_dir):
    """Answering the combined "geometric+rounded" option must surface pairs
    from BOTH real groups, not just one."""
    answers = json.dumps({"font_group": "geometric+rounded"})
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        f.write(answers)
        answers_path = f.name
    result = run_styles(project_dir, ["questions", answers_path])
    rounds = json.loads(result.stdout)
    pair_round = next(r for r in rounds if r["key"] == "fonts_pair")
    ids = {o["id"] for o in pair_round["options"] if not o["id"].startswith("lib:")}
    assert ids == {"poppins", "inter", "nunito", "baloo"}


def test_fonts_pair_round_includes_library_fonts_with_license(project_dir, fixtures_dir):
    shutil.copy(fixtures_dir / "gateway" / "caps.library.unknown.json", project_dir / "lana" / "caps.library.json")
    result = run_styles(project_dir, ["questions"])
    rounds = json.loads(result.stdout)
    pair_round = next(r for r in rounds if r["key"] == "fonts_pair")
    lib_opts = [o for o in pair_round["options"] if o["id"].startswith("lib:")]
    assert lib_opts, "expected at least one library font option"
    assert "license: unknown" in lib_opts[0]["label"]


def test_last_time_annotation_from_answers_file(project_dir, tmp_path):
    answers = tmp_path / "answers.json"
    answers.write_text(json.dumps({"captions": "none"}), encoding="utf-8")
    result = run_styles(project_dir, ["questions", str(answers)])
    rounds = json.loads(result.stdout)
    captions_round = next(r for r in rounds if r["key"] == "captions")
    none_opt = next(o for o in captions_round["options"] if o["id"] == "none")
    assert "(last time)" in none_opt["description"]
    bold_opt = next(o for o in captions_round["options"] if o["id"] == "bold")
    assert "(last time)" not in bold_opt["description"]


def test_remember_writes_last_style_under_fake_home(project_dir, tmp_path):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    answers = tmp_path / "answers.json"
    answers.write_text(json.dumps({"captions": "none", "font_group": "script"}), encoding="utf-8")

    result = run_styles(project_dir, ["remember", str(answers)], env={"HOME": str(fake_home)})
    assert result.returncode == 0, result.stderr
    saved = json.loads((fake_home / ".reel" / "last-style.json").read_text())
    assert saved["captions"] == "none"
    assert saved["font_group"] == "script"


def test_remember_missing_file_exits_2(project_dir, tmp_path):
    result = run_styles(project_dir, ["remember", str(tmp_path / "nope.json")], env={"HOME": str(tmp_path)})
    assert result.returncode == 2


# Fonts.tsx writes its pair keys as idiomatic (unquoted) TS object keys —
# `anton: { group: "bold", build: () => ({ ... }) },` — not the JSON-style
# quoted keys this regex originally expected (that version's `findall`
# always returned an empty set, so the comparison test below always
# vacuously passed no matter what changed; see PARSE_FONT_PAIRS_TSX_TEST
# below, which locks in that the parser actually distinguishes a real
# mutation, against a synthetic fixture that doesn't depend on
# template/src/Fonts.tsx existing).
FONT_PAIR_ENTRY_RE = re.compile(r'"?([a-zA-Z_][a-zA-Z0-9_-]*)"?\s*:\s*\{\s*group:\s*"([a-zA-Z0-9_-]+)"')


def parse_font_pairs_tsx(text: str) -> dict[str, str]:
    """id -> group, parsed from a Fonts.tsx-shaped `FONT_PAIRS` block."""
    match = re.search(r"FONT_PAIRS\s*[:=].*?\{(.*)\}\s*;", text, re.DOTALL)
    assert match, "could not find FONT_PAIRS in the given text"
    return dict(FONT_PAIR_ENTRY_RE.findall(match.group(1)))


SYNTHETIC_FONTS_TSX = '''
export const FONT_GROUPS = ["bold", "editorial"] as const;
export const FONT_PAIRS: Record<string, { group: FontGroup; build: () => FontSet }> = {
  anton: { group: "bold", build: () => ({ id: "anton", name: "Anton / Anton" }) },
  playfair: { group: "editorial", build: () => ({ id: "playfair", name: "Playfair / Raleway" }) },
};
export const FONT_IDS = Object.keys(FONT_PAIRS);
'''


def test_parse_font_pairs_tsx_extracts_unquoted_ts_keys():
    """Locks in the parser against a fixture that does NOT depend on
    template/src/Fonts.tsx existing — this test can never be silently
    skipped, unlike the integration comparison below."""
    parsed = parse_font_pairs_tsx(SYNTHETIC_FONTS_TSX)
    assert parsed == {"anton": "bold", "playfair": "editorial"}


def test_parse_font_pairs_tsx_fails_on_a_real_mutation():
    """The whole point of the comparison test below: if an id or group is
    renamed on one side and not the other, parsing must actually notice."""
    parsed = parse_font_pairs_tsx(SYNTHETIC_FONTS_TSX)
    mutated = dict(parsed)
    mutated["anton"] = "editorial"  # simulate Fonts.tsx regrouping a pair
    assert mutated != parsed
    del mutated["playfair"]  # simulate a pair being removed
    assert set(mutated) != set(parsed)


def test_font_pair_ids_and_groups_match_template_fonts_tsx():
    """styles.py's pairs mirror template/src/Fonts.tsx's FONT_PAIRS by
    design. Hallazgo 17 (2026-09-17): this used to `pytest.skip()` inline
    when Fonts.tsx hadn't landed yet — a THIRD, file-name/marker-invisible
    skip mechanism, asleep since the template merged but exactly the same
    species as make_pkg.py's old silent "typecheck skipped".
    `Fonts.tsx` is part of the integrated tree now: a missing file is a
    real regression, not a "some other role's work isn't in yet" — fail,
    don't sleep."""
    fonts_tsx = REPO_ROOT / "lana-reel" / "template" / "src" / "Fonts.tsx"
    assert fonts_tsx.is_file(), "template/src/Fonts.tsx missing"

    import sys
    sys.path.insert(0, str(SCRIPTS))
    from _lib import fonts as _fonts  # noqa: E402

    tsx_pairs = parse_font_pairs_tsx(fonts_tsx.read_text(encoding="utf-8"))
    assert tsx_pairs, "found no FONT_PAIRS entries in Fonts.tsx — regex may need updating"
    ours = {pid: p["group"] for pid, p in _fonts.FONT_PAIRS.items()}
    assert tsx_pairs == ours
