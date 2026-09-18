---
name: reel
description: >
  Builds vertical 1080x1920 talking-head reels with Remotion, rendered on Lana's GPU through
  the `lana` MCP: cuts silences from measured audio, aligns captions to the script, adds
  headlines, transitions, cards and sound effects, and measures retention before spending a
  render. Your machine only needs python3, node and ffmpeg. Use it when someone asks to
  "make a reel", "edit this vertical video", "cut the silences", "add captions", "add
  graphics to the reel" or "measure retention" on their own camera footage — or, in Spanish,
  "montar un reel", "quitar los silencios", "ponerle subtítulos", "editar este video vertical".
---

# /reel

Runbook for building a vertical reel end to end. The steps run in order and each one is
verified before moving to the next. The heavy work — ingest, transcription, silence
measurement, rendering — runs on Lana through the `lana` MCP; your machine writes React,
looks at frames and packages files.

**Read `KNOWHOW.md` before improvising anything.** This file says *what to do*; that one says
*what goes wrong*, why no check catches it, and how to verify the fix. Every silent failure
listed there cost a re-render at least once.

A parenthesised tag such as `I5` marks a **behaviour invariant**: a rule learned the hard way, one that
changes what the agent decides. If you edit these files, you may rewrite a sentence — do not
weaken one. A `must` that becomes a `should`, or a `never` that becomes an `avoid`, is a silent
regression that only shows up in a bad reel.

## What this skill does — and does not do (v1)

Does: vertical talking-head reels from your own camera footage — silence cutting, captions,
headlines, cards, boards, lower thirds, transitions, sound effects from Lana's pack, fonts from
Google Fonts or your own, resources from Lana's shared library, proof renders and a final render
on Lana's GPU.

Not in v1: teleprompter-glance removal, hand tracking, headlines behind the person, voice
echo, background music, local rendering. Those need capabilities that do not exist as MCP
tools yet; they are tracked in the repository's issues. Do not substitute a local tool for
them — see "Don'ts".

Also not wired, for a different reason: **`plan.voice`**, a field of the `Plan` type in
`template/src/types.ts`. Nothing writes it — no `CONFIG` key feeds it and nothing here promises
the capability — and `Reel.tsx` guards it (`plan.voice ? … : null`), so an empty `voice` is the
correct default, not an oversight. If you open the type and wonder why the field is dead: that is
why, and wiring it starts by deciding what feeds it. It is **unrelated to the "voice echo"**
above, which is an audio effect, not this field.

## Requirements

- **Claude Code** with the `lana` MCP authorized. Not connected yet, or a tool answers
  `FORBIDDEN_SCOPE`: see the `lana-mcp-render` skill, section 0.
- **`python3` >= 3.10** — every script in `scripts/` is stdlib only.
- **`node` >= 20** — `npm run check` (`tsc --noEmit`) before spending a render job.
- **`ffmpeg` and `ffprobe` (required, not optional).** They are how you *see* the material:
  extracting a frame and looking at it is the only way to decide mirroring, subject side and
  color. `ffmpeg` is also used to add a silent audio track to an mp4 that has none, and to
  verify the finished file. That is all. It is **never** used to transcode the take, to
  measure silence on the take, or to render — those run on Lana (I36).

`python3 setup.py` verifies all three and fails with the install command for your OS if one is
missing. A script exiting 2 with `!! ffmpeg/ffprobe not found on PATH — run setup.py` (or a
single-tool variant) is this requirement, not a bug in the take.

## The rule that governs everything

**Cuts come from the MEASURED AUDIO. Text comes from the transcript. Never the other way
around.** (I1)

`lana_measure_silence` returns `silence.speech[] {start_ms, end_ms}` — physical measurement of
where there is voice. `lana_transcribe` returns `words[]` — the text. In long files with many
takes, word timestamps are **shifted by seconds**, not inflated: **never derive a cut from a
word timestamp** (I2). They also merge a false start with its retry into one sentence, so a
repetition that you can hear lives nowhere in the data.

**Captions: a page lives until its last word ends.** Never a fixed millisecond cap. A page
closes at the start of the next page or at `last word + 150 ms`, whichever comes first (I3). A
fixed 1100 ms cap once killed pages mid-word for five releases and nobody measured it.

```bash
python3 ~/.claude/skills/reel/scripts/reel/check_captions.py   # mandatory before EVERY render
```

**If it prints `!!`, there is no render** (I4). If you change pagination (another
`combineTokens…`, another font, another size), adapt the check with `--page-ms`; never remove it.

## Step 0 — New project

```bash
python3 ~/.claude/skills/reel/scripts/reel/new_project.py ~/reels/my-first --name my-first --source ~/Movies/take.MOV
export REEL_PROJECT=~/reels/my-first
```

Every script resolves the project from `$REEL_PROJECT`, or the current directory, or up to
three levels above it. There are no hardcoded paths.

Then check what the service offers before spending anything:
`lana_get_capabilities(topic="limits")` → `save_result.py caps-limits <path>` →
`caps.py limits --check`.

## Step 1 — Look at the take, decide with the user, upload it as it is

```bash
python3 ~/.claude/skills/reel/scripts/reel/probe_source.py raw/take.MOV --record
```

It prints duration, resolution, fps, rotation, color transfer and whether there is an audio
track, and writes three JPG frames at 10/50/90 % of the take.

**Look at the frames** — open each one with `Read` (I5). Three things are decided here and none
of them can be automated:

- **Is it mirrored?** If there is text in the scene and it reads backwards, yes. Mirroring is
  a prop (`plan.mirror` → `scaleX(-1)`), never an ffmpeg filter. **When you mirror, the subject
  changes side and the safe column for graphics becomes the opposite one.**
- **Which side is the subject on?** Read it off the frame; it decides the graphics column.
- **How does the color look?** A frame extracted from an HLG take may look washed out on your
  screen. Judge mirroring and side on it, not color: Lana's ingest handles HLG.

### USER DECISION — ask, do not assume

1. **Do we mirror the video?** (I5)
2. **Full script or trimmed?** It changes the final duration and which lines exist. (I6)
3. **When the script and the recording differ, which one wins?** Recommend the audio, or
   trimming the audio — **never a caption that says a word that is not heard.** (I7)

Then upload the take **exactly as it is**. Do not transcode it, do not flip it, do not trim it
locally: the ingest produces the h264 proxy and the 16 kHz wav, mirroring is a prop, and
silence is measured on Lana (I36).

**A reel take is `take`** (1 s–10 min), not `episode`, which demands **60 s minimum** and rejects
a short clip *permanently* — a `REJECTED` asset cannot be re-confirmed. `prep_upload.py` catches
it locally first: `!! 34.4s with --purpose episode is below the 60s floor; use --purpose take
instead (1-600s)`. Windows per purpose: `lana-mcp-render/SKILL.md` §1.

```bash
python3 ~/.claude/skills/reel/scripts/lana/prep_upload.py raw/take.MOV --purpose take --key clip --emit
#   → lana_create_upload(**args)
python3 ~/.claude/skills/reel/scripts/lana/transfer.py put raw/take.MOV --url <upload_url> --header <k=v> --key clip
#   → lana_confirm_upload(asset_id=...)
python3 ~/.claude/skills/reel/scripts/lana/register_asset.py clip --asset-id <uuid> --ingest-job <uuid>
#   → lana_wait_job(job_id=<ingest_job_id>, timeout_s=180)   # repeat while timed_out
```

`register_asset.py` closes by printing the next step, `wait: lana_wait_job("<ingest_job_id>")`.
Do it: **after every `confirm_upload`, wait for the ingest job to a terminal state**, or the
gateway keeps counting it in flight and you hit a phantom quota (I30). Every uploaded mp4 must
also carry an audio track — one without it fails with `INGEST_ERROR`, and `prep_upload.py` adds
a silent one automatically.

This is the handshake for every Lana call in this runbook: **emit → call → save**. A script
prints the exact arguments (`--emit`), you call the chat tool with them, you hand the result back
to a script. No script here ever talks to the gateway or sees a credential (I35).

## Step 2 — Transcribe and measure silence (in parallel)

```
lana_transcribe(asset_id=<uuid>, language="en")        ┐ both after the ingest succeeded
lana_measure_silence(asset_id=<uuid>, noise_db=-35, min_silence_ms=150)  ┘
lana_wait_job(...) ×2
```

```bash
python3 ~/.claude/skills/reel/scripts/lana/save_result.py transcript <path to the tool result>
python3 ~/.claude/skills/reel/scripts/lana/save_result.py silence <path to the tool result>
python3 ~/.claude/skills/reel/scripts/reel/takes.py --table
```

Each speech region is one take; the table gives start and end in milliseconds, which is
exactly the format of the SEL in `videoconfig.py`. A recording with a high noise floor does
not separate takes at −40 dB; −35 is the default for that reason.

A long transcript does not come back inline. If `save_result.py` prints `transcript exceeds
inline limit: run transfer.py get <result_url> -o lana/transcript.raw.json and re-run
save_result.py transcript lana/transcript.raw.json`, do exactly that — the signed URL is in the
tool result you already have.

Mapping the script against the catalogue is the judgement work:

- **Pick the LATEST take that matches the line, not the first one that sounds similar** (I9).
  The good ones are usually the second or third repetition.
- **Discard takes flagged `hallucination`** — words transcribed over silence (I10).
- **False starts inside one take** ("And if you are a developer… and if you are a developer,
  74 %") are merged by the transcriber into one sentence and spread over the script without
  complaining; you only hear them in the video. `check_repeats.py` finds them per speech
  region and prints where to start the line. Run it after every build. A take that lasts much
  longer than its line (11 s for a 5 s line) is suspect (I11).

Multi-file: a SEL line can come from any source. Four fields use the default source; with five,
the first is the asset key. Every extra file is another `episode` upload registered in
`project.json`, with its own transcript and silence results.

## Step 3 — Lana's shared library

Before the style questions, look at what the shared library offers: fonts, alpha overlays,
textures, B-roll and audio, none of which you upload.

```
lana_get_capabilities(topic="library")
```
```bash
python3 ~/.claude/skills/reel/scripts/lana/save_result.py caps-library <path to the tool result>
python3 ~/.claude/skills/reel/scripts/lana/caps.py library
```

`caps.py library` prints **every** entry with its `license` field exactly as it comes,
`unknown` included; nothing is hidden and nothing is filtered by license (I15). It closes with
a count: `N of M entries have license "unknown" — verify before commercial use (README §Shared
library & licenses)`.

- Pick candidates by `kind` and `tags` for the visual intent — **never list the whole
  catalogue at the user** (I12). For three candidates at most, `lana_get_asset("lib:<id>")`
  returns the contract of use and an inline preview image: **confirm by looking at the image
  with the user, never blind by name.**
- **If a chosen entry shows `license: unknown`, say so to the user once** and point at the
  repository README, section "Shared library & licenses": it is the user who verifies the
  license before publishing commercially (I15).
- **Explicit user choices win over any suggestion of this skill** — "use font X", "no
  overlays" (I13).
- Never invent or hand-type a library id: it comes from `caps.library.entries[].file` of the
  current release (I14). Selection criteria per `kind`, and what to do with
  `LIBRARY_RELEASE_UNAVAILABLE`: `references/library.md`.

## Step 4 — Styles: one question per element

Before writing `videoconfig.py`, the user chooses the style of EACH element. **Never assume
"like last time": every element is shown and confirmed on every video** (I8).

```bash
python3 ~/.claude/skills/reel/scripts/reel/styles.py questions            # rounds ready for AskUserQuestion
python3 ~/.claude/skills/reel/scripts/reel/styles.py remember answers.json
python3 ~/.claude/skills/reel/scripts/lana/brand.py --emit answers.json   # → lana_set_brand_defaults(**args)
```

Four rounds, up to four questions each, passed as they are to `AskUserQuestion`: text · image ·
rhythm and brand · typography and sound. Library fonts are offered as pair candidates with their
license visible in the label. The previous choice appears first as "(last time)", pulled from
`lana_get_capabilities(topic="brand")` and your local last-style file — showing it is not the
same as assuming it (I8). Every round, option and `CONFIG` key: `references/style-questions.md`.

**What is measured is not asked** (I16): where a headline lands, how long the hook lasts, where
the face is — the code decides that, not a question.

## Closing the idea

The last cut decides whether the reel feels finished. Eight rules, each one with a real failure
behind it: `references/closing.md`. In short, and in order:

1. **Never a hard cut** — the clip ends with air, `hold_f = 10` (333 ms) (I18).
2. **The ending is measured against the hook's debt**: a list, a number or a question that the
   hook promised is either paid by the last cut, or the hook changes (I19).
3. **Never close on a word the transcript hallucinated over silence** — verify there is voice
   over it in `speech[]` first (I20).
4. False closing markers ("so, anyway", "in the end") do not close anything (I21).
5. Referential dependency in the entry: include the antecedent or change the entry; three hops
   or 45 s is the practical limit (I21).
6. There are four kinds of closure — phrase, semantic, narrative, emotional; the phrase one is
   the cheapest and the most deceiving (I21).
7. Some structures close without resolving, and that is fine — but "curiosity → deferred
   payoff" only with a declared destination (I21).
8. The hook is not the structure (I21).

## Step 5 — Plan

Write `videoconfig.py` (one `CONFIG` dict: SEL, titles, punch, bw, transitions, boards,
inserts, gfx, style), then:

```bash
python3 ~/.claude/skills/reel/scripts/reel/build.py
```

**When it finishes it prints which line each effect ended up anchored to. Read that map, every
time** (I22). Effects are anchored by line index: adding or removing one SEL line shifts every
later index, and the render completes with no error and the effects on the wrong lines.

`build.py` also prints the total duration (it fails above 180 s, the per-composition limit), the
number of cuts, any gap over 8 s, `hook_end_ms`, and the key moments it picked for the proof job.

## Step 6 — Before rendering

```bash
python3 ~/.claude/skills/reel/scripts/reel/check_retention.py
python3 ~/.claude/skills/reel/scripts/reel/check_captions.py
python3 ~/.claude/skills/reel/scripts/reel/check_repeats.py
```

Target: **no gap over 8 s without a visual event, hook before 4 s. Close the gaps by ADDING
punches and cards, not by trimming the script** (I23). All three must print `ok`; if any prints
`!!`, fix it before spending a job (I4).

## Step 7 — Optional effects

**Boards** are full-frame plans that replace the camera: a chalk board drawn stroke by stroke, or
a screenshot with a marker. One scene per line, each stroke entering **on the word that names
it**; they enter and leave with a crosswarp while the voice and captions keep running. For a new
video you **write new scenes** in `template/src/Boards.tsx` — the two bundled ones are
demonstrations, not a library. No Lottie: a prebuilt animation cannot land on the word being said
(KNOWHOW §3).

**Split screen**: a board with `"split": true` lives in the top band while the person keeps
talking below. Measure the crop with real frames of the source before fixing it, and move the
captions to the top band so they do not cover the face.

**Hook video**: `"hookVideo"` plays at a rate derived from the spoken length of line 0, so it
lasts exactly as long as the hook.

**Lower third**: `{"line": 4, "num": "1", "text": "HEADLINE"}` — a number block plus a headline,
3.6 s, swiping in at the start of the line.

Screenshots and images for cards upload as `purpose=image`; inserted clips and the hook video as
`purpose=context`, which has **no duration floor** (a still probes as 0 s and is valid material)
and asks for confirmation past 10 min. Same handshake as step 1; register each one with
`register_asset.py` so
`staticFile("assets/<key>.<ext>")` resolves.

## Step 8 — Package and proof render

```bash
python3 ~/.claude/skills/reel/scripts/lana/make_pkg.py
cd "$REEL_PROJECT" && npm run check          # tsc, seconds; a failed job costs minutes
python3 ~/.claude/skills/reel/scripts/lana/make_bundle.py
python3 ~/.claude/skills/reel/scripts/lana/prep_upload.py lana-pkg/bundle.zip --purpose bundle --emit
#   → lana_create_upload → transfer.py put → lana_confirm_upload → register_asset.py bundle
python3 ~/.claude/skills/reel/scripts/lana/make_submit.py --proof --emit
#   → lana_submit_render(**args) → lana_wait_job(...) → transfer.py get <read_url> -o out/proof-1.mp4
python3 ~/.claude/skills/reel/scripts/reel/probe_source.py out/proof-1.mp4 --frames 1
```

**Validate the key moments before the final render** (I25). The proof is ONE job with up to
four ~3 s windows — hook, first headline, first card or board, closing — picked by `build.py`.
Extract one frame per proof and **look at it yourself**, then watch the clips with the user. A
layout bug costs minutes of render.

**Iterate on the plan, not on the render**: fix `videoconfig.py`, re-run `build.py`, `make_pkg.py`,
`make_bundle.py`, re-upload the bundle, submit again. Group corrections — the daily quota is 50
jobs and a full reel spends 6 to 12 (I32).

## Step 9 — Final render and verification

```bash
python3 ~/.claude/skills/reel/scripts/lana/make_submit.py --final --emit
#   → lana_submit_render(**args) → lana_wait_job(...) → save_result.py job <path>
python3 ~/.claude/skills/reel/scripts/lana/transfer.py get <read_url> -o out/final.mp4
python3 ~/.claude/skills/reel/scripts/lana/verify_output.py --job lana/jobs/<job_id>.json --file out/final.mp4
```

`save_result.py job` prints the download line for the file it recorded —
`download: transfer.py get <read_url from the job result> -o out/<name>.mp4`. The URL lives an
hour; on `URL expired or invalid: ask the tool again`, read the job again, do not edit the URL.

**Mandatory** (I26): the output duration matches the plan, and `silencedetect` over the output
shows zero silences except the pauses the SEL marked as acted. This five-second check would
have saved four failed iterations on the first video ever built with this skill.

## Don'ts

- **Never derive a cut from transcript word timestamps.** They are shifted in multi-take files
  and they merge repetitions. Cuts come from `lana_measure_silence` (I2).
- **Never render without validating the proof frames.** A layout bug costs minutes (I25).
- **Never assume the user's decisions** — mirroring, trimming, script versus audio. Ask (I27).
  An asset the user chose is never replaced by a generated one: it already happened once, an
  image the user sent was swapped for a generated one "to avoid them a problem". Say the
  objection and do what they asked.
- **Never use a generative video model to composite over a real person.** They regenerate the
  shot. To put something over a hand you track it (I28).
- **Never replace a brand's logo with a generated image.** Generated images are for concepts
  without a brand (I28).
- **Never invent a sound effect that already exists in the material.** Ask where an element
  comes from before fabricating it (I29).
- **Do not synthesize or download new sound effects.** Use the pack from
  `lana_get_capabilities(topic="sfx")`, or the two bundled CC0 files (I17).
- **Never invent a library id or type one from memory.** It comes from
  `caps.library.entries[].file` of the current release (I14).
- **Never hide or filter a library entry by its license.** Show the field as it comes and tell
  the user (I15).
- **Never transcode the take before uploading it, never measure silence locally on the take,
  never render locally.** `ffmpeg` is for looking at frames, adding a missing audio track and
  verifying the output — nothing else (I36).
- **Never call `lana_get_capabilities()` without a topic** (72 KB into context), and **never
  poll `lana_get_job` in a loop** — use `lana_wait_job(timeout_s=180)` and call it again while
  it answers `timed_out` (I33, I34).
