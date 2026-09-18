# Style questions — one question per element

`styles.py questions` emits the rounds ready to be passed, as they are, to `AskUserQuestion`.
This file documents what each round covers and where each answer lands in `CONFIG["style"]`.
**The script is the authority on the exact wording and the exact option ids**; this file exists
so you can tell whether an answer is missing.

Two rules govern the whole questionnaire:

- **Never assume "like the last video".** Every element is shown and confirmed on every video.
  The previous choice appears **first**, labelled "(last time)", so confirming is one click —
  showing it is not the same as assuming it (I8).
- **What is measured is not asked.** Where a headline lands, how long the hook lasts, where the
  face is: the code decides that (I16). If a question would need a measurement to answer, it
  does not belong here.

An explicit instruction from the user ("use font X", "no overlays") **overrides any suggestion
this skill makes**, in this questionnaire and everywhere else (I13).

## Round 1 — Text

| Question | `CONFIG["style"]` key | Options |
|---|---|---|
| Captions | `captions` | `bold` · `none` |
| Hook text | `hook_text` | `first_line` · `custom` (the text goes to `hook_text_value`) |
| Hook style | `hook_style` | `banner` · `title` · `lower_third` · `none` |
| Closing | `closing` | `plate` · `title_only` |

## Round 2 — Image

| Question | `CONFIG["style"]` key | Options |
|---|---|---|
| Headlines | `titles` | `centered` · `top` |
| Transitions (multi) | `transitions` | `crosswarp` · `whip` · `glitch` |
| Cards | `cards` | `pop` · `stack` · `none` |
| Full-frame plans (multi) | — (they become `boards`, `inserts`, `hookVideo` entries) | chalk board · screenshot board · split screen · hook video |

Headlines behind the person are **not offered in v1** — the capability is not available as an
MCP tool. Do not add the option back by hand.

## Round 3 — Rhythm and brand

| Question | `CONFIG["style"]` key | Options |
|---|---|---|
| Silences | `silence` | `soft` · `normal` · `aggressive` |
| Punch | `punch` | `hooks` · `most` · `never` |
| Typographic character | `font_group` | `bold` · `editorial` · `geometric` · `rounded` · `script` |
| Palette | `palette` | `{accent, bg}` — accent color and background |

## Round 4 — Typography and sound

Asked with the previous answers in hand (`styles.py questions answers.json`), because the pair
depends on the group chosen in round 3.

| Question | `CONFIG["style"]` key | Options |
|---|---|---|
| Font pair | `fonts_pair` | the pairs of the chosen group, **four at most** (`AskUserQuestion` takes four options) |
| Where it applies (multi) | `fonts_use` | `hook` · `titles` · `captions` — anything unticked stays on the default |
| Sound effects kit | `sfx_kit` | `full` · `minimal` · `mute` |

### Where the font pairs come from

- **Google Fonts (OFL), loaded by the renderer.** Nothing travels in the bundle, nothing is
  uploaded, there is no license to redistribute. This is the default path.
- **Your own font**, uploaded with `purpose="font"` (ttf/otf/woff2, 5 MiB at most, no ingest)
  and referenced as `assets/<key>.<ext>`.
- **A font from Lana's shared library** (`kind: "font"`), referenced as `lib/<id>.<ext>`. Library
  fonts appear as pair candidates **with their license visible in the option label** — for
  example `… (library · license: unknown)` — and they are never filtered out (I15). The library
  does not ship variable weights: pick the published weight closest to what you need.

## After the questionnaire

```bash
python3 ~/.claude/skills/lana-reel/scripts/reel/styles.py remember answers.json
python3 ~/.claude/skills/lana-reel/scripts/lana/brand.py --emit answers.json   # → lana_set_brand_defaults(**args)
```

`remember` stores the answers locally so they show up as "(last time)" next time; `brand.py`
emits the arguments that save them as the tenant's brand defaults, which is what
`lana_get_capabilities(topic="brand")` returns at the start of the next video.

`build.py` applies the answers on its own: gaps, headline lift, hook as banner / headline /
lower third, closing, captions, punch by policy. It **warns** (`!! style:`) when `CONFIG` uses a
glitch, a board or a hook video that was not chosen.
