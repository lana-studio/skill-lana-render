# Your first reel

This folder is the smallest real example: an 8-line talking-head script
(`videoconfig.py`), an empty `project.json` (`asset_id: null` everywhere — no
one's UUIDs are in this repo), and no video. There is nothing to download.

**Record 30-45 seconds on your phone, vertical, talking to camera**, and save
it as `raw/your-take.mov` inside this folder (`raw/` is gitignored). Say
whatever you want — `videoconfig.py`'s `sel` list is a placeholder script that
`build.py` will happily fail to match against your words; replace the lines
with (roughly) what you actually said before running `build.py`. The point of
this example is the *plumbing*, not the script.

Everything heavy — transcription, silence detection, and the render itself —
happens on Lana's infrastructure. Your machine only extracts a few JPEG frames
with `ffmpeg` so the agent can *see* your clip, and runs small Python scripts
that shuffle JSON files around. That's the whole "Pentium 4" idea.

## Before you start

`<skill>` = the folder that contains `SKILL.md` — `~/.claude/skills/lana-reel` in Claude Code,
`~/.agents/skills/lana-reel` in Codex.

1. Create an account at Lana Studio.
2. Register the server: Claude Code —
   `claude mcp add --scope user --transport http lana https://mcp.lanastudio.pe/mcp`; Codex —
   `codex mcp add lana --url https://mcp.lanastudio.pe/mcp`.
3. Log in: Claude Code — run `/mcp`, pick `lana`, and Authenticate; Codex — run
   `codex mcp login lana` and restart Codex (the first 401 is normal — it triggers RFC 9728
   discovery, then DCR, then PKCE).
4. Install the skill (the repository's `README.md`, section "Install").
5. Copy this folder somewhere of your own and work there:
   `cp -R <skill>/examples/first-reel ~/reels/first-reel && cd ~/reels/first-reel`

## The flow: 12 tool calls

Every interaction with Lana follows the same three-step handshake — **emit**
(a script prints the tool's arguments), **call** (you invoke the tool from
the chat), **save** (a script consumes the result). No script here ever talks
to `mcp.lanastudio.pe` directly; the agent is the one holding the
conversation with the tools.

### 0. Sanity check

```
lana_get_capabilities(topic="limits")
```
Confirms `service_version >= 1.5.0` and `render_enabled`. Save it:
```
$ python3 <skill>/scripts/lana/save_result.py caps-limits <path-from-tool-result>
saved lana/caps.limits.json
```

### 1. Look at your clip, then upload it

```
$ python3 <skill>/scripts/reel/probe_source.py raw/your-take.mov --frames 3 --record
duration: 34.1s  1080x1920  30.0 fps
rotation: 0°  has_audio: True
lana/frames/your-take-10.jpg
lana/frames/your-take-50.jpg
lana/frames/your-take-90.jpg
look at these frames before deciding: mirror? subject side? color?
```
The agent looks at the three frames with `Read`, asks you to confirm mirror /
subject side, and the script records the answer into `project.json`.

```
$ python3 <skill>/scripts/lana/prep_upload.py raw/your-take.mov --purpose take --key clip --emit
{
  "filename": "your-take.mov",
  "content_type": "video/quicktime",
  "size_bytes": 41823917,
  "purpose": "take",
  "title": "your-take"
}
```
`episode` has a 60s floor (`services/media/app/services/probe.py`'s
`MIN_DURATION_SECONDS`) — a 30-45s phone take is below it and gets rejected
locally with `!! ...s with --purpose episode is below the 60s floor; use
--purpose take instead`. `take` (1-600s) is the purpose that actually fits a
single clip like this one.

```
lana_create_upload(**args)              # call 1 — returns upload_url + headers
```

```
$ python3 <skill>/scripts/lana/transfer.py put raw/your-take.mov --url <upload_url>
put -> https://lana-media-dev.blob.core.windows.net/uploads/wr9k2p... (41823917 bytes)
upload: 100%
done: 41823917 bytes in 6.4s (HTTP 201)
```

```
lana_confirm_upload(...)                # call 2 — returns asset_id + ingest_job_id
```

```
$ python3 <skill>/scripts/lana/register_asset.py clip --asset-id <uuid> --ingest-job <uuid>
assets.clip: asset_id=<uuid> status=ready ext=mov
wait: lana_wait_job("<ingest_job_id>")
```

```
lana_wait_job(ingest_job_id)             # call 3 — waits for the proxy/wav ingest
```

```
$ python3 <skill>/scripts/lana/save_result.py job <path>
status=SUCCEEDED phase=
```

### 2. Transcribe and measure silence — never the other way around

```
lana_transcribe(asset_id, language="en")       # call 4
```
```
$ python3 <skill>/scripts/lana/save_result.py transcript <path>
saved lana/transcript.json  (87 words)
```

```
lana_measure_silence(asset_id, noise_db=-35, min_silence_ms=150)   # call 5
```
```
$ python3 <skill>/scripts/lana/save_result.py silence <path>
saved lana/silence.json  (3 speech regions)
```

```
$ python3 <skill>/scripts/reel/takes.py --table
ASSET         #     START       END     DUR FLAG           TEXT
--------------------------------------------------------------------------------------------------------------
clip          0      1180     11940  10.76s                Here is the thing nobody tells you about editing
clip          1     12300     22680  10.38s                Record it once, straight to camera, and let the
clip          2     23050     34120  11.07s                That is the whole idea, and it works every time

3 takes. Each row is a possible SEL entry:
  ("<ASSET>", <START>, <END>, "script text", False),
```

### 3. Build the plan and the bundle

Edit `videoconfig.py`'s `sel` list to match what you actually said (`takes.py
--words <a>-<b>` helps you find exact phrasing), then:

```
$ python3 <skill>/scripts/reel/build.py --proof-windows 4
first-reel: 8 lines | 8 cuts |   26.0s | 91 words | 0 graphics
    TITLE   'THIRTY SECONDS'                   -> [2] You need a phone, thirty seconds, and somethin
    TITLE   'NOT ON YOUR LAPTOP'               -> [6] Everything heavy runs on a render farm, not on
    XWARP                                      -> [4] The cuts happen later, from the pauses you alr
    CLOSING                                    -> [7] That is the whole idea: your first reel, from
proof windows (frames):
    hook       (0, 90)
    title      (141, 231)
    closing    (705, 790)
    mid-3      (345, 435)
```
This writes `src/plan.json`, `src/ritmo.json`, and `src/graphics.json` — not
`lana-pkg/props.json`, which D17 retired: the plan travels inside the bundle's
code, never as `lana_submit_render`'s `props` argument.

```
$ python3 <skill>/scripts/lana/make_pkg.py
files: 6, 41.3 KB total, 1 assets in ASSET_FILES
typecheck: ok (6 files)
```
The first time on a machine, `make_pkg.py` installs the Remotion template's
`node_modules` once at `~/.reel/template/` (`npm ci`, about a minute) and links
it into this folder before the typecheck.

```
$ python3 <skill>/scripts/lana/make_bundle.py
lana-pkg/bundle.zip: 37.8 KB compressed, 7 entries, 92.1 KB uncompressed, sha256=aa11bb22...
```

```
$ python3 <skill>/scripts/lana/prep_upload.py lana-pkg/bundle.zip --purpose bundle --emit
{
  "filename": "bundle.zip",
  "content_type": "application/zip",
  "size_bytes": 38707,
  "purpose": "bundle",
  "title": "bundle"
}
```
```
lana_create_upload(**args)               # call 6
```
```
$ python3 <skill>/scripts/lana/transfer.py put lana-pkg/bundle.zip --url <upload_url>
```
```
lana_confirm_upload(...)                 # call 7
```
```
$ python3 <skill>/scripts/lana/register_asset.py bundle --asset-id <uuid>
```

### 4. Proof job — one render, four ~3s windows

```
$ python3 <skill>/scripts/lana/make_submit.py --proof --emit
{
  "entry": "src/index.tsx",
  "bundle": "<asset_id>",
  "compositions": [
    "Reel-proof-1",
    "Reel-proof-2",
    "Reel-proof-3",
    "Reel-proof-4"
  ],
  "assets": {
    "clip": "<asset_id>"
  },
  "idempotency_key": "first-reel-aa11bb22-proof"
}
```
```
lana_submit_render(**args)               # call 8
lana_wait_job(job_id)                    # call 9
```
```
$ python3 <skill>/scripts/lana/save_result.py job <path>
status=SUCCEEDED phase=
  output: Reel-proof-1  3.0s  245312 bytes
  output: Reel-proof-2  3.0s  198765 bytes
  output: Reel-proof-3  3.0s  201044 bytes
  output: Reel-proof-4  3.0s  210998 bytes
download: transfer.py get <read_url from the job result> -o out/reel-proof-1.mp4
```
The filename comes from the first composition's id (`Reel-proof-1`,
lowercased) — not a generic `proof.mp4`.

```
$ python3 <skill>/scripts/lana/transfer.py get <read_url> -o out/reel-proof-1.mp4
$ python3 <skill>/scripts/reel/probe_source.py out/reel-proof-1.mp4 --frames 1
duration: 3.0s  1080x1920  30.0 fps
rotation: 0°  has_audio: True
lana/frames/reel-proof-1-10.jpg
look at these frames before deciding: mirror? subject side? color?
```
The agent looks at the proof frame(s) — this is your chance to catch a typo
or a wrong mirror decision for the cost of one small job, before spending a
full render.

```
$ python3 <skill>/scripts/lana/verify_output.py --job lana/jobs/<id>.json --file out/reel-proof-1.mp4
status: SUCCEEDED
```

### 5. The real thing

```
$ python3 <skill>/scripts/lana/make_submit.py --final --emit
{
  "entry": "src/index.tsx",
  "bundle": "<asset_id>",
  "compositions": [
    "Reel"
  ],
  "assets": {
    "clip": "<asset_id>"
  },
  "idempotency_key": "first-reel-aa11bb22-final"
}
```
```
lana_submit_render(**args)               # call 10
lana_wait_job(job_id)                    # call 11
```
```
$ python3 <skill>/scripts/lana/save_result.py job <path>
status=SUCCEEDED phase=
  output: Reel  27.3s  4830112 bytes
download: transfer.py get <read_url from the job result> -o out/reel.mp4
$ python3 <skill>/scripts/lana/transfer.py get <read_url> -o out/reel.mp4
$ python3 <skill>/scripts/lana/verify_output.py --job lana/jobs/<id>.json --file out/reel.mp4
status: SUCCEEDED
```

Wait, that's only 11 numbered calls above — the twelfth is the onboarding
`lana_get_capabilities(topic="limits")` from step 0. Twelve tool calls, zero
lines of JSON you had to write by hand, and `out/reel.mp4` is your first reel.

## What this example is not

- **No video ships in this repo.** `raw/`, `out/`, and `lana-pkg/bundle.zip`
  are gitignored; `check_clean.py`'s `large-binary` and `media-without-license`
  rules stay at 0 findings for this folder because there is nothing in it to
  flag.
- **No brand, no library selection, no custom font.** This is the bare path;
  `styles.py questions` and the shared library (`caps.py library`) are the
  next thing to try once this works.
- **Not a substitute for `SKILL.md`.** This README shows the shape of the
  flow; the skill itself carries the actual editing judgment (what makes a
  good cut, how captions page, when to reach for a title card).
