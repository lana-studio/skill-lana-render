# Hello render — five calls, one job, about two minutes

The first thing to run after installing. It renders two seconds of video on Lana's GPU from two
small source files, and in doing so it verifies, in one shot: the OAuth authorization, the
scopes you were actually granted, that you have render enabled and quota left, that the
renderer is new enough to have the sound-effects pack mounted, and that you know how to download
a result.

It does not need a project: run it from anywhere.

`<skill>` = the folder that contains `SKILL.md` — `~/.claude/skills/lana-reel` in Claude Code,
`~/.agents/skills/lana-reel` in Codex.

## The five calls

### 1. Emit the arguments

```bash
python3 <skill>/scripts/lana/make_probe.py --emit
```

It prints — and writes to `hello-render.args.json` — the exact arguments for the render:

```json
{
  "entry": "src/index.tsx",
  "files": {
    "src/index.tsx": "…registerRoot(RemotionRoot)…",
    "src/Root.tsx": "…<Composition id=\"Hello\" durationInFrames={60} …>…"
  },
  "compositions": ["Hello"],
  "idempotency_key": "hello-render-20260920-1431"
}
```

Two files, under 3 KiB. This is the one place in the whole skill where `files` is used instead
of a bundle: there is no project to package. The composition draws a title in a Google Font
(`--font Anton` by default) and plays one effect from the pack
(`--sfx whoosh-short` by default), which is what makes it a real end-to-end check.

### 2. Submit the render

```
lana_submit_render(**args)
```

Expected: `{"job_id": "<uuid>", "kind": "RENDER", "status": "QUEUED"}`.

### 3. Wait for it

```
lana_wait_job(job_id="<uuid>", timeout_s=180)
```

Expected: `status: "SUCCEEDED"` with `render.outputs[0]` carrying `composition_id: "Hello"`,
`duration_s: 2.0`, a `size_bytes` and a signed `read_url`. If it comes back with
`timed_out: true`, call it again with the same `job_id` — that is not an error (I34).

### 4. Download the result

```bash
python3 <skill>/scripts/lana/transfer.py get "<read_url>" -o out/hello.mp4
```

`read_url` lives one hour and is re-signed every time you read the job; if it expires, read the
job again rather than editing the URL.

### 5. Check it

```bash
python3 <skill>/scripts/lana/verify_output.py --job lana/jobs/<job_id>.json
```

It prints `ok` — or, when the job failed, translates the known cases (see below).

Play `out/hello.mp4`: two seconds, a title on a dark background, one whoosh. That is the whole
pipeline working.

## When it fails

| What you see | What it means | What to do |
|---|---|---|
| `FORBIDDEN_SCOPE` naming a scope | That scope was not granted at authorization time | `/mcp` → `lana` → Authenticate again and grant the scope the message names |
| `RENDER_NOT_ENABLED` or `PLAN_NOT_ELIGIBLE` | Render is not enabled for your account | Nothing to fix in the code — this is an account gate |
| `QUOTA_EXCEEDED` | A quota is exhausted | The detail says which one and when it renews |
| `ASSET_ERROR` on a font key | The service is older than the font path | Report it as an issue with the version you got from `topic="limits"` |
| Logs mentioning `public/sfx/` and a 404 | The renderer is older than the sound-effects pack | Same: report the version |
| `VALIDATION_ERROR` on `files['src/Root.tsx']:<n>` | The generated code references something the service does not know | Re-run `make_probe.py --emit` — do not hand-edit the arguments |
| `UNAUTHENTICATED` | The server is not authorized yet | `/mcp` → `lana` → Authenticate. A 401 on the very first attempt is the normal start of that flow |

Cost: **one job** out of your daily 50, and a couple of GPU seconds. Running it twice within the
same minute reuses the job, because the `idempotency_key` carries the date and time to the
minute (I32).
