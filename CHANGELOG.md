# Changelog

This repository is versioned together with the `lana-mcp-render` service: major and minor
match the minimum service version it needs; a patch release changes only the client. Dates are the release date of the tag.

## Unreleased — install by asking Claude Code or Codex

Client-only change: still requires `lana-mcp-render >= 1.5.0`.

### Codex CLI

- **Codex CLI is now a supported client for the `lana` MCP server**, alongside Claude Code. The
  skill installs to `~/.agents/skills/lana-reel` on Codex (`~/.claude/skills/lana-reel` on Claude
  Code, unchanged) and registers with `codex mcp add lana --url https://mcp.lanastudio.pe/mcp` —
  there is no `--scope` flag to get wrong, `~/.codex/config.toml` already applies to every folder.
  Login is `codex mcp login lana` (or `--no-browser` without a graphical browser).
- **Skill files are path-agnostic now.** Every command inside `lana-reel/` that used to hardcode
  `~/.claude/skills/lana-reel` now says `<skill>`, defined once at the top of `SKILL.md` as "the
  folder that contains this SKILL.md". `README.md` keeps concrete per-client paths, since it is
  what installs the skill in the first place.
- **`README.md`'s install steps branch by client only where they actually differ**: a new "Step 0
  — Which client are you" table, then registering the MCP server, logging in, restarting, and
  what the user runs on your behalf (Claude Code's `!` prefix has no Codex equivalent — Codex asks
  the user to run the command in another terminal and report back).
- Error messages and reference docs that pointed only at `/mcp` → `lana` → Authenticate
  (`verify_output.py`, `references/errors-limits-quotas.md`, `references/mcp.md`) now name both
  recovery paths.
- Codex CLI support is new and only partly verified — see `README.md`, section "Not in this
  version".

- **One install document: `README.md`.** The user pastes one line into Claude Code with the
  repository URL; the agent clones it and follows the README's numbered steps (platform,
  prerequisites, source, skill folder, Remotion's skills, MCP registration, restart and login,
  hello render). The user only approves commands, restarts and logs in.
  `LEEME-PRIMERO.md`, `INSTALAR.md` and `DETALLES.md` are gone; their details (data, shared
  library & licenses, quotas, versions) live in the README, which is also where `SKILL.md` and
  `caps.py` already pointed ("README §Shared library & licenses").
- **The `lana` MCP server is registered with `--scope user`.** The previous command registered it
  only for the folder it ran in, so a reel opened in another folder had no `lana` tools.
- The release zip ships `README.md`, `LICENSE` and `NOTICE` next to the skill.

### Windows (experimental)

Not verified on a real Windows machine yet; these are the blockers found by reading the code.

- **Links without privilege.** Windows refuses symlinks without administrator rights or Developer
  Mode, so the first project could never be created. `_lib.io.link_dir` / `link_file` keep the
  symlink on macOS/Linux (a failure there is still an error) and on Windows fall back to a
  directory junction or a hard link, then a copy. Used by `new_project.py` and `make_pkg.py`.
- **tsc runs as `node …/typescript/bin/tsc`** instead of `node_modules/.bin/tsc`, which on Windows
  is a shell script that cannot be executed.
- **UTF-8 output.** On Windows a script's piped stdout/stderr used cp1252 and died on the first
  `→`; the `_lib` package now reconfigures them to UTF-8 there. ffprobe/ffmpeg/tsc output is
  decoded as UTF-8 on every system.
- **Install:** the README detects Git Bash, installs prerequisites with `winget`, and states that
  `python3` is `py -3` on Windows.

## 1.5.1 — simpler install

Client-only change: still requires `lana-mcp-render >= 1.5.0`.

### Simpler install

- **One skill, one folder: `lana-reel/`.** `reel` and `lana-mcp-render` are merged; the MCP
  runbook now lives in `lana-reel/references/mcp.md` and the hello render in
  `lana-reel/examples/hello-render.md`. `scripts/`, `template/` and `assets/` live inside the
  skill, so installing is copying one folder.
- **`install.py` and `setup.py` are gone.** Dependencies are checked when the user installs
  Remotion's skills from Claude Code; the template's `node_modules` install themselves once in
  `~/.reel/template/` the first time `new_project.py` (or `make_pkg.py`) needs them, and again
  when the pinned `package-lock.json` changes. `~/.reel/setup.json` is no longer read.
- **User docs in Spanish, next to the skill:** `LEEME-PRIMERO.md`, `INSTALAR.md`,
  `DETALLES.md`, and a brief template at `lana-reel/prompt-reel.md`.
- `tools/make_release.py` builds the zip users download.
- Upgrading from 1.5.0: delete `~/.claude/skills/reel` and `~/.claude/skills/lana-mcp-render`.

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
