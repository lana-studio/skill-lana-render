# Changelog

This repository is versioned together with the `lana-mcp-render` service: the version here is
the minimum service version it needs. Dates are the release date of the tag.

## 1.5.0 — first public release

The first public version of the two skills. Requires `lana-mcp-render >= 1.5.0`.

### What is in it

- **`skills/reel`** — the full runbook for a vertical talking-head reel: look at the take, cut
  it from measured audio, align captions to the script, headlines, cards, boards, lower thirds,
  transitions, the sound-effects pack, Lana's shared library, retention checks, a proof render
  and a verified final render. Plus `KNOWHOW.md`: every silent failure found in production, with
  how to detect it.
- **`skills/lana-mcp-render`** — how to operate the MCP server: onboarding, the 13 tools, upload
  and ingest, transcription and silence, quotas, the code the renderer accepts, errors, and a
  hello render that verifies the whole path in one job.
- **`scripts/`** — one family of standard-library Python scripts, shared by both skills.
- **`template/`** — a Remotion project pinned to the version the renderer runs (4.0.484),
  in a single mode: it renders on Lana.
- **`assets/`** — five OFL fonts and two CC0 sound effects.
- **`examples/first-reel/`** — a worked example that starts with recording 30 seconds on your
  phone.

### What is deliberately not in it

- **Any client other than Claude Code**, Codex CLI included.
- **Windows.**
- **Local rendering.** The render happens on Lana; that is the design, not a limitation to work
  around.
- **Teleprompter-glance removal, hand tracking, headlines behind the person, voice echo.** These
  exist in the private version of this skill as local machine-learning pipelines. They are out
  until they exist as MCP tools, because requiring a GPU on your machine would defeat the point.
- **Background music.** No catalogue ships here.
- **Any credential handling.** No script reads a token, none talks to the gateway directly, and
  no signed URL is written to disk.
