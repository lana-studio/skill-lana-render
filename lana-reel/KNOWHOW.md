# KNOWHOW — what breaks, and how to catch it

Living document: when a new failure shows up, **add a section**; do not rewrite the old ones.
Every entry carries symptom, cause, why no check catches it, fix, and verification.

The numbers are **stable ids in order of discovery**, with gaps (entries that stopped applying
were removed, not renumbered) and not sorted. An id always means the same failure.

---

## 1. Silent failures — corrupt output that passes every check

The expensive ones. None of these raises an error.

### 1.1 Word timestamps drift by seconds

- **Symptom:** the video assembles with no errors, but the cuts land where the text does not,
  and the captions run out of sync.
- **Cause:** in long files with several takes the word timestamps are not inflated — they are
  **shifted**. Measured: the audio at 17.73 s said one sentence, the transcript put a different
  fragment there.
- **Why no check catches it:** valid JSON, plausible durations, completed render.
- **Fix:** cuts come from `silence.speech[]`, text from `transcription.words[]`, never the other
  way around. `build.py` also applies the two measured corrections: a per-word cap of
  `300 + 80·len(word)` ms (the model stretches the last word before a pause) and `+180 ms` on
  the first word after a pause longer than 300 ms.
- **Verification:** take an instant of the render, listen, compare with the caption shown there.

### 1.2 Effects anchored to the wrong line

- **Symptom:** the headline, the black-and-white or the glitch fires at the wrong moment.
- **Cause:** effects anchor by **line index**; adding or removing one SEL line shifts every
  later index.
- **Why no check catches it:** the index is still valid.
- **Fix:** `build.py` prints which line each effect landed on. Read it **every time** you touch
  the SEL.
- **Verification:** that anchor map.

### 1.3 Captions collapsing into one page

- **Symptom:** captions disappear from the whole video.
- **Cause:** `createTikTokStyleCaptions` paginates using the **leading space** of each token
  (`" hello"`). A parser that calls `.strip()` collapses everything into one giant page, which
  any "hide caption" rule then makes vanish.
- **Why no check catches it:** the data is correct and there are captions in the JSON.
- **Fix:** never strip the leading space of a caption token.
- **Verification:**
  `python3 -c "import json;print(repr(json.load(open('src/plan.json'))['captions'][0]['text']))"`
  → it must start with a space.

### 1.4 Graphics pointing at text that is not the caption text

- **Symptom:** the wrong card appears, or none does.
- **Cause:** a mis-transcribed proper noun fixed in a copy of the text instead of in the data
  that feeds captions **and** matcher.
- **Why no check catches it:** both structures are internally valid.
- **Fix:** one single source for both — do not add a second corrected copy of the line.
- **Verification:** `src/graphics.json` and `src/plan.json` carry the same wording.

### 1.6 A headline covering a whole line

- **Symptom:** ten seconds with no captions and the shot feels dead.
- **Cause:** the headline inherits the duration of the line it is anchored to.
- **Why no check catches it:** a long headline is a legal headline.
- **Fix:** `TITLE_MAX_MS = 3600`. **A headline is a hit, not a plate** (I24).
- **Verification:** no `titles[]` entry in `src/ritmo.json` longer than 3600 ms.

### 1.7 A card underneath a headline

- **Symptom:** the big text runs over a card.
- **Cause:** the headline occupies the central band and the low card position falls inside it.
- **Why no check catches it:** both elements sit exactly where they were asked to.
- **Fix:** `build.py` forces any card inside a headline window to the high position.
- **Verification:** **only visible in a still** — check the frame in the proof render.

### 1.8 A crosswarp between two identical frames

- **Symptom:** you configure a crosswarp and nothing happens. No error.
- **Cause:** the "cut" was continuous — `outFromF == inFromF`, so the crosswarp mixes an image
  with itself.
- **Why no check catches it:** it is a valid transition between two sources that happen to be
  equal.
- **Fix:** remove it, or anchor it to a line that really starts in another take.
- **Verification:**
  `python3 -c "import json;print([(c['outFromF'],c['inFromF']) for c in json.load(open('src/ritmo.json'))['crosswarp']])"`
  — matching numbers mean there is no cut to disguise.

### 1.10 An SVG filter erasing straight lines

- **Symptom:** a perfectly vertical or horizontal stroke in a board disappears.
- **Cause:** `filter="url(#chalk)"` with the default region (bounding box ±10 %) has nothing to
  work on when the box has zero width.
- **Why no check catches it:** the SVG is valid and every other stroke renders.
- **Fix:** `filterUnits="userSpaceOnUse" x="0" y="0" width="1080" height="1920"` on the `<filter>`.
- **Verification:** the proof frame of that board.

### 1.10b A large image scaled by the browser comes out "doubled"

- **Symptom:** a diagram shown above its native size renders with duplicated, offset text.
- **Cause:** the browser's upscaling — `transform` and `object-position` both do it.
- **Why no check catches it:** the file is intact and the props are right.
- **Fix:** pre-scale the image to its exact on-screen size before uploading, show it 1:1, pan
  with `object-position`.
- **Verification:** the proof frame of that insert.

### 1.12 A frame you extracted looks washed out (HLG)

- **Symptom:** the JPG `probe_source.py` wrote looks pale next to what the phone shows.
- **Cause:** phones record HLG; a frame pulled from an HLG take keeps or loses its color tags
  depending on the player.
- **Why no check catches it:** nothing failed — it is a viewing artifact of your own frame.
- **Fix:** nothing locally. The ingest applies its `hdr_policy` and produces the proxy the render
  uses. **Never tone-map the take yourself** (I36); judge mirroring and subject side on the
  frame, **not** color.
- **Verification:** `probe_source.py` prints `color_transfer`; HLG or PQ shows up there.

### 1.13 Split screen: the face is cut off or the captions cover it

- **Symptom:** in split mode the face falls below the frame, or the captions land on it.
- **Cause:** the source rows for the bottom band were guessed, not measured; and the normal
  caption height belongs to a full frame, not to a band.
- **Why no check catches it:** the composition is valid at every size.
- **Fix:** **measure with real frames of the source** before fixing the crop, and move the
  captions into the top band for those windows.
- **Verification:** one proof frame inside the split window.

### 1.13b A phone photo that comes out sideways

- **Symptom:** an inserted photo appears rotated 90°.
- **Cause:** EXIF rotation — some tools preserve the flag, some apply it, and a manual rotation
  on top puts it back on its side.
- **Why no check catches it:** it is a valid image with valid dimensions.
- **Fix:** check `rotation` in the `probe_source.py` output and re-save the photo upright before
  uploading. Do not "fix" it with a transform in React.
- **Verification:** `probe_source.py <photo>` reports rotation 0 after re-saving.

### 1.14 Captions that die mid-word (fixed per-page cap)

- **Symptom:** the caption lasts a second or less and disappears while the person is still
  saying that same word. Most visible with numbers and a slow delivery.
- **Cause:** pagination closing each page at `start + a fixed cap`, regardless of whether its
  words were still sounding.
- **Why no check catches it:** the data is correct — every word has its time; it is the life of
  the **page** that is cut. It survived five releases with 7–19 s per video of talking with no
  text, and nobody measured it.
- **Fix:** a page lives until `last word + 150 ms`, or the start of the next page, whichever
  comes first (I3).
- **Verification:** `check_captions.py` simulates the pagination and fails if a page dies
  mid-word; it runs before **every** render (I4). Not a Lana problem: the box renders the
  `Captions.tsx` you send, and the simulation reproduces the cuts with no render at all.

### 1.15 Doubled captions over an insert

- **Symptom:** in a window covered by an inserted clip the caption reads twice, in two fonts.
- **Cause:** the inserted clip was exported **with captions burned in** and the render draws its
  own on top. When both fonts match it just looks bold and you miss it.
- **Why no check catches it:** two valid layers.
- **Fix:** **never bake captions into an insert that the reel captions over.** Inserts ship
  clean; captions are drawn live by the composition.
- **Verification:** the proof frame inside the insert window.

### 1.16 A false start inside a take that the transcriber merges

- **Symptom:** you hear the beginning of a sentence twice, but the caption shows it once.
- **Cause:** the take holds the false start and the retry; the transcript returns the sentence
  ONCE and the aligner spreads it over the script. The repetition lives only in the audio.
- **Why no check catches it:** word count, timings and alignment ratio are all plausible.
- **Fix:** `check_repeats.py` looks for repeated n-grams (3 tokens or more) **inside the same
  speech region**, within 4 s of each other, and prints the millisecond to start the line at.
  Run it after every build (I11). Its limit: it only sees repetitions inside one region — a
  false start behind a long silence is a different take, covered by "latest take that
  matches" (I9).
- **Verification:** an earlier signal is a take of 11.7 s for a 5 s line.

### 1.17 The reel ends on the last phoneme and reads as "unfinished"

- **Symptom:** the video "feels cut" even though the idea closed. Reported as a script problem;
  it was not.
- **Cause:** `HOLD_F = 0`. The composition ended exactly with the last segment, so three things
  landed on one frame: the cut to black, the truncated 150 ms tail of the last caption page, and
  any audio fade reaching zero.
- **Why no check catches it:** the plan is correct, the captions measure well, and
  `check_captions.py` only looks at pagination, not at the end of the composition.
- **Fix:** `HOLD_F = 10` (333 ms at 30 fps), per-video via `"hold_f"` in `CONFIG` (I18). **The
  air is not a freeze:** it is the last take still running, muted.
- **Verification:** 333 ms does not break the final check — `silencedetect` at `d=0.4` does not
  count a 0.33 s silence, so `verify_output.py` still reports zero (I26).

### 1.11 "There are too many pauses" although the silence check says there are none

- **Symptom:** the user hears air that no check reports.
- **Cause:** at −40 dB the detector counts breath tails and mouth noise (−40…−50 dB) as voice,
  leaving 0.7–0.8 s of air around a cut.
- **Why no check catches it:** the threshold that ran classifies that air as speech.
- **Fix:** measure with `noise_db=-35` (room noise sits around −55) and tighten the gap policy
  with `style.silence`: `soft` / `normal` / `aggressive`. Careful with `keep_pauses=True`: it
  preserves **all** the internal air of that line — use it only on the exact stretch that
  carries the sound you want.
- **Verification:** re-measure, re-run `build.py`, and the gap report changes.

---

## 2. Bugs that break execution (with the literal error)

### 2.5 `Caption` from `@remotion/captions` demands extra fields

- **Symptom / error:** `Type '{ text; startMs; endMs; }' is missing … timestampMs, confidence`.
- **Cause:** the published type has five fields, not three.
- **Why no check catches it:** it is caught — by `tsc`, which is why `npm run check` runs before
  a render job.
- **Fix:** emit `timestampMs` and `confidence` as `null` from the build.
- **Verification:** `npm run check` → 0 errors.

### 2.1 Synced folders evict files (short note)

Cloud-sync folders (iCloud Drive, OneDrive, Dropbox) list a file with its real size but read it
back as 0 bytes, which surfaces as `spawn ENOEXEC`, a module that "cannot set properties of
undefined", or an empty media file. **Keep `~/.reel/template/node_modules` outside any synced folder** —
`new_project.py` installs it in `~/.reel` for that reason. Check with
`dd if=<file> of=/dev/null bs=1m count=1`: 0 bytes transferred means evicted.

---

## 3. Design decisions and why

- **The `build.py` engine is separate from `videoconfig.py`.** The engine is code, the config is
  data per video. Mixing them makes per-video hacks permanent.
- **Graphics live in one single column**, the one that avoids the face, the profile bar, the
  icon column and the platform caption at once. **Mirroring flips which column that is** — which
  is why step 1 asks.
- **Crosswarp is the default transition**, over glitch and whip pan. The other two are an effect
  *on top of* a hard cut; the crosswarp extends the outgoing take and pulls the incoming one
  forward, so **the cut stops existing**. It only works because the source is one continuous file.
- **Final air without a freeze** (§1.17): ten frames of the last take still running, muted.
  Neither a frozen frame nor a silence long enough for the final check to count.
- **`ClosingPlate` goes before the headlines in the JSX**, or its dark veil dims the closing
  headline.
- **Boards are drawn in SVG, not Lottie.** A Lottie file is a prebuilt animation with its own
  timing; it cannot land on the word being said. Strokes use `pathLength` + `strokeDashoffset`,
  text a growing `clipPath`, chalk texture `feTurbulence` + `feDisplacementMap`, and every
  stroke is anchored to the frame of its word.
- **A black-and-white effect ending on the frame a board starts** puts its white flash on top of
  the warp: move it or drop it.
- **`lana_get_asset` never sends `structuredContent`.** A client that receives it may discard the
  whole `content[]`, image included — which is how a library preview used to get lost. Read
  `content[0].text` as JSON.
- **Do not cache a library `preview.url`.** It is signed and expires in an hour; ask
  `lana_get_asset` again.

---

## 4. Tried and did NOT work — do not retry

- **Fixed-energy-threshold onset scanning** to find where speech starts inside a long file. It
  gets contaminated by neighbouring takes and returns suspiciously round numbers (exact
  multiples of the window step). Use the measured speech regions.
- **Searching the whole lower half of the frame for a "clean window"** free of burned-in text.
  False negatives: it reported "no clean window in 52 s" when the correct band had plenty. Sweep
  only the band where the captions themselves live.
- **CSS `filter: blur()` as a substitute for directional motion blur.** It is isotropic. The whip
  pan compensates with `scaleX`; for a real transition use the crosswarp with both shots.

---

## 5. Judgement (what the code does not capture)

- **Pick the latest take that matches the script.** A take with a real error ("in less than *one*
  minute" instead of "two minutes") was nearly used; the good one was the next repetition.
- **Confirm a stumble at word level.** Segment-level transcription once invented a duplication
  that did not exist, and once hid a real stumble that only showed word by word. The check works
  in both directions.
- **A pause marked in the script ("…", "(pause)") is acting: preserve it.** An unmarked pause is
  hesitation: cut it.
- **A burst of external material lasts as long as the sentence that narrates it**, not the
  minimum. Four clips of 0.8 s read as a blink; around 2 s each, covering the line, they work.
- **Verify the material before promising an effect.** The user remembered "one hand… the other
  hand… and then the icon". Measured: one hand on the first word, two on the second, none on the
  third.
- **Retention is fixed by adding events, not by trimming script** (I23), unless there really is
  surplus content. A 3:50 video with a 79 s gap had to be thrown away whole.

---

## 6. Process — the order to verify in

1. **Look at a frame of the source before anything else** — mirroring, subject side, rotation
   (`probe_source.py`, then `Read` the JPGs).
2. `build.py` → **read the anchor map it prints** (§1.2).
3. `check_retention.py`, `check_captions.py`, `check_repeats.py` **before** rendering, not after.
4. `npm run check` before spending a job — seconds against minutes.
5. The proof job at the key moments, with **one frame per proof looked at by you**, before the
   final render.
6. `verify_output.py --file` over the final output, always.

---

## 7. Lana specifics (learned in production, still true)

- **Every uploaded mp4 needs an audio track.** Without one it fails with `INGEST_ERROR: could not
  produce a valid proxy`. `prep_upload.py` adds a silent one and registers that file.
- **Wait for every ingest job to a terminal state.** The gateway counts as "in flight" any job
  nobody waited on, so you get a phantom `3/3` and a `QUOTA_EXCEEDED` with no cause (I30).
- **`INTERNAL_ERROR` on the first `confirm_upload` of a session** is a known first-call pattern:
  wait about 20 s and call it again.
- **`WORKER_LOST`** → `lana_retry_job`; if it returns the same failed job (`reused_existing`),
  call `lana_confirm_upload` on the asset again.
- **JPEG images have rendered broken in the past — prefer PNG** for cards and screenshots. Never
  upload a file whose content type does not match its extension: a jpg declared as `image/png`
  renders as a broken image.
- **`ASSET_PROXY_SUBSTITUTED: <key> → proxy v1` is a normal warning**, not a failure. So is
  `ASSET_NO_PROXY: <key>` (it uses the original).
- **`lana_measure_silence` is idempotent per (asset, parameters).** To relaunch a failed
  measurement you must change a parameter — `min_silence_ms` 150 → 151 — because `retry_job`
  does not cover it.

---

## 8. The agent's own process failures (not the code's)

- **Iterating four times patching the symptom without measuring the result.** The first video was
  rebuilt four times adjusting durations and thresholds without ever running `silencedetect` over
  the render. Five seconds of verification would have shown from the first iteration that the
  approach was wrong.
- **Replacing a user's decision with your own judgement.** They sent a specific image to use and a
  generated one was produced instead "to avoid them a problem". State the objection **and do what
  they asked** (I27).
- **Declaring a tool dead before it failed.** A job that was merely slow was given up on.
  Distinguish "it failed" (an explicit error) from "it is taking a while" — which is exactly what
  `lana_wait_job` returning `timed_out` means (I34).
- **Fabricating an element without asking where it came from.** A clap was synthesized that was
  already in the material (I29).
- **Giving an estimate without computing it.** "It lands at 1:45–2:00" was said; summing line by
  line it was 2:21.
