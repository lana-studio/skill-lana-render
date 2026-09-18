# -*- coding: utf-8 -*-
"""Fixture CONFIG for tests — 2 SEL lines matching
tests/fixtures/transcript.json + silence.json."""
CONFIG = {
    "style": {
        "captions": "bold",
        "hook_style": "banner",
        "hook_text": "first_line",
        "closing": "plate",
        "titles": "centered",
        "transitions": ["crosswarp"],
        "cards": "pop",
        "silence": "normal",
        "punch": "hooks",
        "font_group": "bold",
        "fonts_pair": "anton",
        "fonts_use": ["hook", "titles", "captions"],
        "sfx_kit": "full",
    },
    "sel": [
        (0, 2500, "Here is the thing nobody tells you.", False),
        (3200, 5200, "And if you are a developer.", False),
    ],
    "hook_banner": "NOBODY TELLS YOU THIS",
    "hook_tag": "",
    "titles": {0: "THE THING"},
    "punch": [0],
    "bw": [],
    "glitch": [],
    "crosswarp": [],
    "closing": 1,
    "inserts": [],
    "boards": [],
    "lowerthirds": [],
    "gfx": {},
    "gfx_accents": {},
    "hold_f": 10,
}
