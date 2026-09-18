"""scripts/_lib/fonts.py — mirror of `template/src/Fonts.tsx`'s `FONT_PAIRS`.

The `group` here is the true semantic taxonomy and matches
`template/src/Fonts.tsx`'s `FONT_GROUPS` exactly: bold, editorial,
geometric, rounded, script — 5 groups, same as the template. It does NOT
bend to the <= 4-options-per-AskUserQuestion-round cap every questionnaire
round in this skill respects; that cap is a presentation constraint on
`styles.py`'s font_group question, not a
taxonomy fact, so it is resolved there (two groups combined into one
question OPTION, honestly labeled, with each pair's `group` here left
untouched) rather than by lying about which group a pair belongs to. See
`styles.py`'s `GROUP_QUESTION_MERGE` for that merge.

This file is the list `scripts/reel/styles.py` reads from — a plain Python
dict rather than parsing TypeScript at runtime, so this script has no node
dependency. `tests/test_styles.py` is what keeps the two in sync: it parses
`template/src/Fonts.tsx` by regex for the exported `FONT_PAIRS` ids AND each
pair's `group`, and asserts both match this file exactly. If a font pair is
added/removed/renamed/regrouped in Fonts.tsx and this file isn't updated to
match, that test fails — that's the point.

Every family here is Google Fonts (OFL), loaded by @remotion/google-fonts in
the render box — nothing is uploaded, nothing has a license to redistribute.
"""
from __future__ import annotations

# id -> {group, primary: {family, weight[, style]}, secondary: {family, weight[, style]}}
FONT_PAIRS = {
    "anton": {
        "group": "bold",
        "primary": {"family": "Anton", "weight": "400"},
        "secondary": {"family": "Anton", "weight": "400"},
    },
    "archivo": {
        "group": "bold",
        "primary": {"family": "Archivo Black", "weight": "400"},
        "secondary": {"family": "Open Sans", "weight": "600"},
    },
    "montserrat": {
        "group": "editorial",
        "primary": {"family": "Montserrat", "weight": "800"},
        "secondary": {"family": "EB Garamond", "weight": "400", "style": "italic"},
    },
    "playfair": {
        "group": "editorial",
        "primary": {"family": "Playfair Display", "weight": "800"},
        "secondary": {"family": "Raleway", "weight": "400"},
    },
    "poppins": {
        "group": "geometric",
        "primary": {"family": "Poppins", "weight": "700"},
        "secondary": {"family": "Playfair Display", "weight": "500", "style": "italic"},
    },
    "inter": {
        "group": "geometric",
        "primary": {"family": "Inter", "weight": "900"},
        "secondary": {"family": "Raleway", "weight": "300"},
    },
    "nunito": {
        "group": "rounded",
        "primary": {"family": "Nunito", "weight": "900"},
        "secondary": {"family": "Nunito", "weight": "400"},
    },
    "baloo": {
        "group": "rounded",
        "primary": {"family": "Baloo 2", "weight": "800"},
        "secondary": {"family": "Quicksand", "weight": "500"},
    },
    "elegant": {
        "group": "script",
        "primary": {"family": "Raleway", "weight": "800"},
        "secondary": {"family": "Great Vibes", "weight": "400"},
    },
    "garamond": {
        "group": "script",
        "primary": {"family": "EB Garamond", "weight": "500"},
        "secondary": {"family": "Great Vibes", "weight": "400"},
    },
}

FONT_GROUPS = ("bold", "editorial", "geometric", "rounded", "script")


def pairs_in_group(group: str) -> list[str]:
    return [pid for pid, p in FONT_PAIRS.items() if p["group"] == group]
