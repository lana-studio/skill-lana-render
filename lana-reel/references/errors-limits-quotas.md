# Errors, limits and quotas

## 1. Error codes

Every failure returns a stable `code`, a human `message`, often a `field_path` and a `guidance`
line, and a **`retryable`** flag. `retryable: true` means the same call could succeed on its
own; `retryable: false` means something has to change first — retrying is a waste of a job.

### Authentication and authorization

| Code | HTTP | Retryable | What to do |
|---|---|---|---|
| `UNAUTHENTICATED` | 401 | no | Authorize the server. Claude Code: `/mcp` → `lana` → Authenticate. Codex: `codex mcp login lana`. An initial 401 on a fresh install is the normal start of that flow. |
| `FORBIDDEN_SCOPE` | 403 | no | The message names the missing scope. Re-authorize and grant it. Claude Code: `/mcp` → `lana` → Authenticate. Codex: `codex mcp logout lana && codex mcp login lana`. |
| `TENANT_SUSPENDED` | 403 | no | Account suspended. |
| `UNKNOWN_LANA_USER` | 403 | no | The authenticated identity has no Lana account behind it. |
| `DISABLED_USER` | 403 | no | The account is disabled. |
| `SUBSCRIPTION_INVALID` | 403 | no | The subscription does not allow this. |
| `PLAN_NOT_ELIGIBLE` | 403 | no | Your plan is not eligible for render. |

### Shape of the call

| Code | HTTP | Retryable | What to do |
|---|---|---|---|
| `INVALID_ARGUMENT` | 422 | no | `field_path` says which argument. Fix and call again. |

### Consumption

| Code | HTTP | Retryable | What to do |
|---|---|---|---|
| `RATE_LIMITED` | 429 | **yes** | Back off and retry; honour `Retry-After` if present. |
| `QUOTA_EXCEEDED` | 429 | no | A quota is exhausted (see §3). The detail says which one and when it renews. Do not retry — wait, or reduce what you are spending. |

### Assets

| Code | HTTP | Retryable | What to do |
|---|---|---|---|
| `ASSET_NOT_FOUND` | 404 | no | The id does not belong to this account. |
| `ASSET_NOT_READY` | 409 | no | The upload has not been confirmed, or the ingest has not finished. Wait for the ingest job. |
| `INVALID_ASSET` | 400 | no | Wrong purpose or content type for what you are asking. The message carries the reason. |
| `UNSUPPORTED_CONTENT_TYPE` | 415 | no | Not one of the 14 allowed types (§2). |
| `EXPIRED_URL` | 410 | no | A signed URL expired. Ask the tool again — never re-sign it yourself. |
| `PROXY_REQUIRED` | 422 | no | You are transcribing or measuring an asset that has no proxy (a font, music or sfx purpose, or an ingest that never ran). Upload it again as `episode`. |
| `ASSET_OBSOLETE` | 422 | no | The derived asset no longer matches its source — re-derive it. |
| `INGEST_ERROR` | 422 | no | The ingest could not produce a valid proxy. **Nine times out of ten: an mp4 with no audio track.** |

### Render and code

| Code | HTTP | Retryable | What to do |
|---|---|---|---|
| `VALIDATION_ERROR` | 422 | no | Your code. Most often a `staticFile` literal that is not one of the three allowed forms; `field_path` is `files['<path>']:<line>`. |
| `RESOURCE_LIMIT` | 422 | no | A hard limit was crossed (§2). |
| `ASSET_ERROR` | 502 | **yes** | The renderer could not fetch or mount an asset. Retry once; if it repeats, check the asset. |
| `RENDER_ERROR` | 422 | no | The render itself failed — read `logs_tail`. |
| `RENDER_TIMEOUT` | 408 | no | The job passed the render timeout. Split the work or shorten the composition. |
| `RENDER_NOT_ENABLED` | 501 | no | Render is not enabled for this account in this deployment. |
| `SPEC_CONTAINS_URL` | 422 | no | A URL inside the spec. Assets travel as assets. |
| `SPEC_TOO_LARGE` | 413 | no | The spec is over the limit — use a bundle. |
| `BUNDLE_INVALID` | 422 | no | The zip breaks one of the bundle rules (§2). |
| `LIBRARY_RELEASE_UNAVAILABLE` | 409 | no | The library release you composed with is gone. Ask `topic="library"` again and recompose. |
| `SEGMENT_ERROR` | 422 | no | No person found in the first frame of a window, or an empty mask. Change `points` / `windows`. |

### Jobs and upstream

| Code | HTTP | Retryable | What to do |
|---|---|---|---|
| `JOB_NOT_FOUND` | 404 | no | Not a job of this account. |
| `IDEMPOTENCY_CONFLICT` | 409 | no | The same key was used with different arguments. Use a new key. |
| `WORKER_LOST` | 503 | **yes** | `lana_retry_job`. If it returns the same failed job (`reused_existing`), redo the step that created it. |
| `JOB_NOT_CANCELLABLE` | 409 | no | Already in a terminal state. |
| `JOB_NOT_RETRYABLE` | 409 | no | Still running — cancel it first if you want it stopped. |
| `SERVICE_UNAVAILABLE` | 503 | **yes** | Temporary. Back off and retry. |
| `ASR_UNAVAILABLE` | 503 | **yes** | The transcription service is down. Retry later. |
| `RENDERER_UNAVAILABLE` | 503 | **yes** | The renderer is down. Retry later. |
| `INTERNAL_ERROR` | 500 | **yes** | Retry once after about 20 s — on the first `confirm_upload` of a session this is a known pattern. |

## 2. Hard limits

These are enforced by the service; the client mirrors them so you can fail locally in
milliseconds instead of spending a job.

**Render, per job**

| Limit | Value |
|---|---|
| Compositions per job | 4 |
| Duration per composition | 180 s |
| Frames per composition | 5400 |
| Frames per job | 21600 |
| Max fps | 60 |
| Long side / short side | 1920 px / 480–1080 px |
| Assets per job | 24 |
| Asset size | 2 GiB |
| Output size | 512 MiB |
| Video bitrate | `2M`–`20M` (default `8M`) |
| Library references per job | 16 |

**Code by `files`**: 64 files, 256 KiB of code in total.

**Code by `bundle`**: 20 MiB compressed, 100 MiB uncompressed, 1000 entries, `props.json`
1 MiB. Allowed extensions (13): `.tsx .ts .js .jsx .json .css .svg .png .jpg .jpeg .webp .wav
.mp3`. No `public/`, no `node_modules/`, no `.git/`, no `dist/`, no font files.

**Upload**: 14 content types (listed in `references/tools.md`); a `font` purpose is capped at
5 MiB. Upload URLs live 15 minutes; read URLs live 1 hour and are re-signed each time you read
the job.

**Renderer**: Remotion 4.0.484 and React ^18.2.0 on the box; entry `src/index.tsx`. Pin your project to both versions — the renderer never runs `npm install` on your bundle, so what you build against is what has to match.

## 3. Quotas

| Dimension | Value | Renews |
|---|---|---|
| Jobs in flight | 3 | as jobs finish |
| Jobs per day | 50 | next day |
| Concurrent renders | 1 | as the render finishes |
| GPU seconds per month | 36 000 | next month |

All job kinds count toward "in flight": ingest, transcribe, silence, segment, render.

`lana_get_capabilities(topic="limits")` returns your consumption and the renewal date in
`limits.quota`. **Ask before spending**, rather than discovering it as a `QUOTA_EXCEEDED`.

A typical reel spends 6 to 12 jobs: 1 ingest + 1 transcribe + 1 silence + 0–6 for card images
and clips (only video ingests; an image does not) + 1 proof + 1 final + one or two relaunches.
A bundle upload costs no job — there is no ingest for a zip.

**The real constraint is a single GPU shared by everyone**, not the per-account quota: if
several people render at once, the queue gets longer. Group your corrections (I32).
