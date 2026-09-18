# The 13 `lana_*` tools — signatures and behaviour

Signatures as the server exposes them. Types are Python-style because that is how the schema
reads in the tool list; call them the way your client calls any MCP tool.

Two things are true of every tool: a failure carries a stable `code`
(`references/errors-limits-quotas.md`), and a tool whose name ends in `_job` needs the read
scope of that job's kind on top of `jobs:read`.

---

## Capabilities

### `lana_get_capabilities(topic=None) -> GetCapabilitiesResponse`

`topic ∈ {"render", "limits", "formats", "ingest", "sfx", "brand", "analysis", "library"}`.

**Always pass a topic** (I33): with none, the answer includes the JSON schema of every
composition and runs about 72 KB. Each topic is under 8 KB and carries its own `quickstart`.

- `limits` — versions, hard limits, allowed upload content types, and **your quota with what you
  have consumed and when it renews**. This is the first call of a session.
- `render` — render limits and the render quickstart (this is the only topic that includes
  composition schemas).
- `ingest` — `hdr_policies`, encoder, proxy quickstart.
- `sfx` — the sound-effects pack: `pack_version`, `count`, and per entry `name`, `category`,
  `duration_ms`, `hit_ms`, `loop`, `tags`, `license`, `default_volume`, `variant_of`.
- `brand` — your uploaded fonts, music and SFX, plus the defaults saved by
  `lana_set_brand_defaults`. **Requires `assets:read`**, checked in the handler.
- `analysis` — what `lana_segment_person` can do.
- `library` — the shared library: `release`, `count`, `truncated`, `requires_lana_mcp_render`,
  `harness_version`, `harness_compatible`, and `entries[]` with `id`, `kind`, `name`,
  `description`, `tags`, `file` (`lib/<id>.<ext>`, the exact `staticFile` literal), `ext`,
  `content_type`, `size_bytes`, `sha256`, `license`, `attribution_required`, `preview_ref`
  (`lib:<id>`). Up to 40 entries; `truncated: true` if there are more.

## Assets

### `lana_create_upload(filename, content_type, size_bytes, title=None, purpose=None) -> CreateUploadResponse`

Scope `assets:write`. `purpose ∈ {"episode", "take", "context", "image", "bundle", "font",
"music", "sfx"}`; omitted, it is inferred from the content type (`audio/*` infers `episode`).

Returns the `asset_id`, a signed `upload_url` with `method: "PUT"` and the `headers` to send.
**Send those headers exactly as given** — the signature includes the canonical content type.
Upload URLs live 15 minutes.

Allowed content types (14): `video/mp4`, `video/quicktime`, `video/x-matroska`, `audio/mpeg`,
`audio/mp4`, `audio/wav`, `image/png`, `image/jpeg`, `image/webp`, `image/svg+xml`,
`application/zip`, `font/ttf`, `font/otf`, `font/woff2`.

### `lana_confirm_upload(asset_id, hdr_policy="reinterpret") -> ConfirmUploadResponse`

Scope `assets:write`. `hdr_policy ∈ {"reinterpret", "tonemap"}`. For video and audio it queues
the ingest (h264 30 fps proxy + 16 kHz wav) and returns `ingest_job_id`; for `image`, `bundle`,
`font`, `music` and `sfx` there is no ingest and `ingest_job_id` is `null`.

Idempotent: on an already-confirmed asset it re-queues the ingest only if it is missing or if
`hdr_policy` changed. **Always wait for the ingest job to a terminal state** (I30).

### `lana_get_asset(asset_id, include_read_url=True) -> list[TextContent | ImageContent]`

Scope `assets:read`. Two modes:

- **A uuid** → metadata plus, if `include_read_url`, a fresh signed read URL (1 hour). **Do not
  cache it across sessions** — ask again.
- **`lib:<id>`** (or `lib:<id>@<release>`), an id from `topic="library"` → the contract of use, a
  minimal example, and **an inline preview image**. `include_read_url=False` returns JSON only.

This tool answers with unstructured content on purpose. Read `content[0].text` as JSON; never
expect a structured field.

## Analysis

### `lana_transcribe(asset_id, language=None, idempotency_key=None) -> JobSubmissionAccepted`

Scope `transcription:create`. Needs the ingest proxy (the clock is the proxy's). No diarization:
`speakers` comes back empty. Same `idempotency_key` means the same job, with no new GPU spent.

### `lana_measure_silence(asset_id, noise_db=-35, min_silence_ms=150, rms_window_ms=None) -> JobSubmissionAccepted`

Scope `analysis:create`. Runs `silencedetect` over the proxy audio (CPU, seconds). The finished
job carries `silence.speech[]`, `silence.silences[]` and, if you asked for it, `silence.rms[]`.
Needs the ingest finished. **Idempotent per (asset, parameters)** — to relaunch, change a
parameter.

### `lana_segment_person(asset_id, windows=None, points=None) -> JobSubmissionAccepted`

Scope `analysis:create`. Cuts the person out on the GPU and registers a VP9 webm with alpha as a
derived asset of the proxy, same clock. `windows=[[from_ms, to_ms], …]` restricts it to those
windows (±200 ms, merged when closer than 1 s); `null` means the whole shot (180 s max).
`points=[[x, y, 1|0], …]` forces the prompt in proxy pixels (1 = person, 0 = background).

On success: `job.segment.alpha_asset_id`, `segments[]` (with `alpha_start_frame` per window, for
`<OffthreadVideo transparent startFrom>`) and `mask_stats`. Re-ingesting the original leaves the
mask stale. Takes GPU time.

**A render does not accept an asset with alpha in v1**, so this tool has no composition path
through `/reel` yet. It is documented because the capability exists.

## Render

### `lana_submit_render(entry, files=None, bundle=None, compositions=None, props=None, assets=None, video_bitrate=None, idempotency_key=None) -> JobSubmissionAccepted`

Scope `render:create`, plus render enabled for the account. Either `files` (a path → source
dict) **or** `bundle` (the `asset_id` of a zip; then no `files` and no `props` — they travel
inside as `props.json`).

- `entry` — the module that calls `registerRoot`, e.g. `"src/index.tsx"`.
- `assets` — `{key: asset_id}`, 24 at most; videos, images, fonts and audio, reachable as
  `staticFile("assets/<key>.<ext>")`. The proxy substitutes the original automatically.
- `compositions` — which composition ids to render, 4 at most per job.
- `video_bitrate` — between `2M` and `20M`; the default is `8M`.
- `idempotency_key` — the same key returns the same job instead of spending a second one.

### `lana_set_brand_defaults(fonts=None, sfx=None) -> BrandDefaultsView`

Scope `assets:write`, plus render enabled. `fonts` takes `{pair, uses, assets}` and `sfx` takes
`{kit, map, levels, overrides}`. **`null` keeps a section; `{}` deletes it**; a section is
replaced whole, never merged key by key. Every `asset_id` is verified against your account
(`fonts.assets` must be `purpose="font"`, `sfx.overrides` must be `purpose="sfx"`), every name
in `sfx.map` / `sfx.levels` must exist in the pack, and each section must serialize under 8 KiB.
Read them back with `lana_get_capabilities(topic="brand")`.

## Jobs

### `lana_wait_job(job_id, timeout_s=120) -> McpJobView`

**The way to wait.** Waits server-side until the job reaches a terminal state or `timeout_s`
(5–180) expires, and returns the same view as `lana_get_job` plus `timed_out` and `waited_s`.
**`timed_out: true` is not an error: call it again with the same `job_id`** (I34).

### `lana_get_job(job_id) -> McpJobView`

State and result of a job of any kind (`INGEST`, `TRANSCRIBE`, `SILENCE`, `SEGMENT`, `RENDER`).
Each kind needs its own read scope on top of `jobs:read`: `assets:read`, `transcription:read`,
`analysis:read`, `analysis:read`, `render:read`. A finished job is not re-queried upstream.
**Do not call it in a loop** (I34).

The view carries `status`, `phase`, `error{code, message, field_path, guidance, retryable}`,
and per kind: `transcription` (`words[]`, `segments[]`), `silence` (`speech[]`, `silences[]`),
`segment`, `render` (`outputs[]` with `composition_id`, `asset_id`, `duration_s`, `size_bytes`
and a freshly signed `read_url`).

### `lana_cancel_job(job_id) -> McpJobView`

Asks to cancel a `QUEUED` or `RUNNING` job. Needs the **create** scope of that kind. The state
reaches `CANCELLED` within seconds; confirm with `lana_get_job`. A job already in a terminal
state answers `JOB_NOT_CANCELLABLE`.

### `lana_retry_job(job_id) -> JobSubmissionAccepted`

Retries a job that failed or expired through infrastructure (or one that was cancelled) **as a
new job**, returning the new `job_id` with `retry_of_job_id` set. Needs the create scope of that
kind. A job that is not in a terminal state answers `JOB_NOT_RETRYABLE`. It does not cover
silence jobs: change a parameter and measure again.
