# Lana MCP — how an agent operates it

Thirteen tools, all named `lana_*`: `get_capabilities`, `create_upload`, `confirm_upload`,
`get_asset`, `transcribe`, `measure_silence`, `segment_person`, `submit_render`,
`set_brand_defaults`, `get_job`, `wait_job`, `cancel_job`, `retry_job`. Exact signatures:
`references/tools.md`. Error codes, limits and quotas: `references/errors-limits-quotas.md`.

A parenthesised tag such as `I34` marks a **behaviour invariant** — a rule learned by paying for it.
If you edit this file you may rewrite the sentence; do not weaken the rule.

## 0. Before you start

1. A Lana Studio account (the normal sign-up).
2. Register the server, at a scope that applies to every folder:
   - **Claude Code:** `claude mcp add --scope user --transport http lana https://mcp.lanastudio.pe/mcp`
     — without `--scope user` the server exists only in the folder where the command ran, and the
     next reel, opened in another folder, has no `lana` tools.
   - **Codex:** `codex mcp add lana --url https://mcp.lanastudio.pe/mcp` — there is no `--scope`
     flag: `~/.codex/config.toml` already applies to every folder.
3. Log in:
   - **Claude Code:** `/mcp` → `lana` → **Authenticate**.
   - **Codex:** `codex mcp login lana` (without a graphical browser: `codex mcp login lana
     --no-browser`, which prints a URL and accepts the pasted-back callback), then restart Codex
     so it reloads the server.

   The initial 401 is normal — it is what triggers discovery, dynamic client registration and
   the PKCE flow in the browser.
4. Expected scopes: `lana:mcp`, `assets:read`, `assets:write`, `transcription:create`,
   `analysis:create`, `analysis:read`, `render:create`, `render:read`, `jobs:read`. If a call
   answers `FORBIDDEN_SCOPE`, the message names the scope that is missing: re-authorize in
   `/mcp` and grant it.
5. **Run the hello render** (`examples/hello-render.md`). One job, about two minutes, and it
   verifies OAuth, scopes, quota, the harness version and that you can download a result.

**Never call `lana_get_capabilities()` with no topic** — the full answer is around 72 KB of
context. Use `topic="limits"` first, then `render`, `ingest`, `sfx`, `brand`, `library` as you
need them (I33). Each one is under 8 KB and carries its own quickstart.

**No script in this repository talks to the gateway.** Scripts print the exact arguments of a
tool (`--emit`), you call the tool in the chat, and you hand the result back to a script. The
only network call any script makes is `transfer.py`, which moves bytes to or from a **signed URL
that a tool returned and you passed in as an argument**. There is no credential reader, no
token, no JSON-RPC client anywhere in this repository (I35).

## 1. Upload: create → PUT → confirm → wait for the ingest

**The `purpose` is validated against the file's real duration, and getting it wrong costs you the
upload.** The three audio/video purposes are not interchangeable:

| `purpose` | Duration accepted | Past the ceiling | For |
|---|---|---|---|
| `take` | **1 s – 10 min** | rejected outright | camera takes, the normal choice for a reel |
| `episode` | **60 s – 4 h** | needs explicit confirmation | a long recording you cut clips out of |
| `context` | **no floor – 10 min** | needs explicit confirmation | inserts, B-roll, stills (a still probes as 0 s) |

Under the floor is `INVALID_ASSET` with `duration_too_short`, and **that verdict is terminal**:
the asset goes to `REJECTED`, `lana_confirm_upload` refuses it from then on ("not in
pending_upload state"), and you re-upload the bytes under a new asset. A 40-second phone clip
sent as `episode` is the way this bites first-time users — it is `take`.

`prep_upload.py` checks the same windows locally and refuses before anything is uploaded, which
is why you should not hand-build `lana_create_upload` arguments for media. It is **stricter than
the service on the two confirmable ceilings** — over 10 min of `context`, over 4 h of `episode` —
and deliberately: the confirmation that would let the service accept those
(`confirm_long_duration`) is not exposed by any MCP tool, so from here such a file cannot be
confirmed at all. Failing locally just saves you the upload.

The rest, none of which has a duration rule: `image` (png/jpeg/webp/svg) · `bundle` (zip of
Remotion code, 20 MiB max) · `font` (ttf/otf/woff2, 5 MiB max, no ingest) · `music` / `sfx`
(your own audio, no ingest).

```
lana_create_upload(filename=…, content_type=…, size_bytes=…, purpose="take")  → upload_url + headers
transfer.py put <file> --url <upload_url> --header <k=v>          # PUT with those headers, as given
lana_confirm_upload(asset_id=<uuid>)                              → ingest_job_id for video/audio
lana_wait_job(job_id=<ingest_job_id>, timeout_s=180)              # repeat while timed_out
```

- **Upload the raw take exactly as it is.** A phone file (HEVC/HLG, 60 fps, rotation 90) is
  fine: the ingest produces the h264 30 fps proxy and the 16 kHz wav. Do not transcode first.
  The wait is the PUT itself — 700 MB is around half an hour.
- **Every uploaded mp4 must carry an audio track.** One without it fails with `INGEST_ERROR`.
  `prep_upload.py` adds a silent one and registers that file instead.
- **After every `confirm_upload`, wait for the ingest job to a terminal state** — the gateway
  counts jobs nobody waited on as in flight, which produces a phantom `3/3` and a
  `QUOTA_EXCEEDED` with no cause (I30).
- Content type must match the extension. Prefer **png** over jpeg for images.
- `INTERNAL_ERROR` on a session's first `confirm_upload`, and `WORKER_LOST`: both are recoverable
  and both are in `references/errors-limits-quotas.md` §1.

## 2. Transcribe and measure silence

Both run after the ingest succeeded, and they can run in parallel.

- `lana_transcribe(asset_id, language="en", idempotency_key=…)` — about 25 s for 5 minutes of
  source. Its `words[]` are **the text**, never the cuts: they merge repetitions and in long
  takes the times drift.
- `lana_measure_silence(asset_id, noise_db=-35, min_silence_ms=150)` → `silence.speech[]` and
  `silence.silences[]`. Validated identical to a local `silencedetect` at the same threshold.
  Recordings with a high noise floor do not separate takes at −40 dB; use −35.
- It is **idempotent per (asset, parameters)**: to relaunch a failed measurement, change a
  parameter (150 → 151 ms). `retry_job` does not cover silence jobs.
- A transcript over 256 KiB does not come inline: the result carries a signed `result_url`, and
  `save_result.py` says so — `transcript exceeds inline limit: run transfer.py get <result_url>
  -o lana/transcript.raw.json and re-run save_result.py transcript lana/transcript.raw.json`.

## 3. Jobs

**Never poll `lana_get_job` in a loop.** Use `lana_wait_job(job_id, timeout_s=180)`, which waits
server-side, and call it again while it answers `timed_out: true` — that flag is not an error
(I34). `lana_get_job` is for one-off checks of a job you already know is finished.

Reading a job requires the read scope of its kind: `render:read`, `transcription:read`,
`assets:read` (ingest), `analysis:read` (silence, segment).

## 4. Quotas

3 jobs in flight (every kind counts), 50 jobs per day, 1 concurrent render, 36 000 GPU seconds a
month. A full reel spends 6 to 12 jobs. Full table: `references/errors-limits-quotas.md` §3.

- **Group your corrections before re-rendering**, do not re-upload assets whose content has not
  changed, and remember that the **same `idempotency_key` means the same job** — that is how you
  avoid paying twice for an identical submit (I32).
- `lana_get_capabilities(topic="limits")` reports your consumption and the renewal date, so you
  can decide before spending instead of discovering it as a `QUOTA_EXCEEDED`.

## 5. The Remotion code Lana accepts

Two ways in: `files` (a path → content dict, 256 KiB of code and 64 files at most) or `bundle`
(a zip asset with `src/**` + `props.json`, no `public/`). **Use the bundle for anything real;
`files` is for the hello render.**

- **`staticFile()` accepts exactly three literal forms** — `assets/<key>.<ext>` (key from the
  submit's `assets` dict, extension from its content type), `sfx/<name>.wav` (a name from the
  pack) and `lib/<id>.<ext>` (an id from `topic="library"`). Anything else — `fonts/…`, `../`,
  a leading `/`, an `http` URL — is a `VALIDATION_ERROR` at the gateway and again at the
  renderer. **Template literals are not analyzed**, which is why every path is centralized in
  `asset()` (I31).
- **Fonts and sound effects**: Google Fonts load on the box with no upload; your own fonts travel
  as `purpose="font"` assets; library fonts as `lib/<id>.<ext>`; the SFX pack lives in the
  renderer and is neither uploaded nor counted as an asset — **do not synthesize or download new
  effects** (I17). Details in `references/fonts-and-sfx.md` and `references/sfx-pack.md`.
- **No video with alpha as an asset.** A person cut-out cannot be composited this way in v1.
- Normal warnings: `ASSET_PROXY_SUBSTITUTED: <key> → proxy v1` and `ASSET_NO_PROXY: <key>`.

## 6. Render

```
lana_submit_render(entry="src/index.tsx", bundle=<asset_id>, compositions=[…], assets={key: asset_id}, idempotency_key=…)
lana_wait_job(job_id, timeout_s=180)                       # repeat while timed_out
transfer.py get <render.outputs[0].read_url> -o out/final.mp4
verify_output.py --job lana/jobs/<job_id>.json --file out/final.mp4
```

Hard limits per job — 4 compositions, 180 s each, 24 assets, and the rest — are in
`references/errors-limits-quotas.md` §2. A 90 s render takes 4–5 minutes, more with a queue.
`read_url` is signed and lives one hour, re-signed on every job read: download it, do not store
it. `URL expired or invalid: ask the tool again` from `transfer.py` means exactly that — read the
job again, never patch the URL by hand.

## 7. Brand defaults

`lana_set_brand_defaults(fonts={pair, uses, assets}, sfx={kit, map, levels, overrides})` saves
the account's defaults; `null` keeps a section, `{}` deletes it. They come back in
`lana_get_capabilities(topic="brand")` together with the fonts, music and SFX you have uploaded.
Read them at the start of a video to pre-fill "last time"; write them when the style
questionnaire closes.

## 8. Errors

Every failure carries a stable `code`, a `retryable` flag, and often a `field_path` and a
`guidance` line. Full table of code → what to do, with the retryable column:
`references/errors-limits-quotas.md`.

## Don'ts

- Do not upload without waiting for the ingest. Do not transcode the take before uploading it.
- Do not derive cuts from `words[]`. Do not send an mp4 with no audio track.
- Do not use `staticFile` with your own paths, and do not put `public/` or a `.ttf` in a bundle.
- Do not call `lana_get_capabilities()` without a topic (I33).
- Do not poll `lana_get_job` in a loop — `lana_wait_job` exists for that (I34).
- Do not re-render for every small correction: group them (I32).
- Do not synthesize or download sound effects that the pack already has (I17).
