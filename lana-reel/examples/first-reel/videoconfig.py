# Edit plan for the "first reel" walkthrough (README.md in this folder).
# Line indexes below refer to positions in `sel` (0-based).
#
# This is a synthetic 8-line script recorded on a phone, no brand, no names,
# no third-party material. It exists so `build.py` has something real to
# align against the first time you run it — replace `sel` with your own take
# once `lana/transcript.json` and `lana/silence.json` exist for your clip.

CONFIG = {
    "style": {
        "captions": "bold",
        "hook_style": "banner",
        "hook_text": "first_line",
        "closing": "plate",
        "titles": "centered",
        "transitions": ["crosswarp"],
        "cards": "none",
        "silence": "normal",
        "punch": "hooks",
        "font_group": "bold",
        "fonts_pair": "anton",
        "fonts_use": ["hook", "titles", "captions"],
        "sfx_kit": "minimal",
        "palette": {"accent": "#FFC400", "bg": "#0A0A0A"},
    },
    # (start_ms, end_ms, "text", keep_pauses) — times are placeholders; build.py
    # aligns each line against lana/transcript.json by text, not by these ms
    # values, then reports the real start/end it found.
    "sel": [
        (0, 2400, "Here is the thing nobody tells you about editing your own videos.", False),
        (2400, 5200, "You do not need a studio, and you do not need a strong computer.", False),
        (5200, 8600, "You need a phone, thirty seconds, and something worth saying.", False),
        (8600, 11800, "Record it once, straight to camera, and do not stop for mistakes.", True),
        (11800, 15100, "The cuts happen later, from the pauses you already made.", False),
        (15100, 18900, "The captions come from what you actually said, word for word.", False),
        (18900, 22500, "Everything heavy runs on a render farm, not on your laptop.", False),
        (22500, 26000, "That is the whole idea: your first reel, from a phone.", False),
    ],
    "hook_banner": "YOUR FIRST REEL, FROM A PHONE",
    "hook_tag": "",
    "titles": {2: "THIRTY SECONDS", 6: "NOT ON YOUR LAPTOP"},
    "punch": [0],
    "bw": [],
    "glitch": [],
    "crosswarp": [(4, 1)],
    "closing": 7,
    "inserts": [],
    "boards": [],
    "lowerthirds": [],
    "gfx": {},
    "gfx_accents": {},
    "hold_f": 10,
}
