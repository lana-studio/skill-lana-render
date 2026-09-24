# lana-reel

A skill for [Claude Code](https://claude.com/claude-code) or Codex CLI that turns a phone
recording of you talking to the camera into a finished vertical reel: silences cut, captions
aligned to what you actually said, headlines, cards, transitions and sound effects. Ingest,
transcription, silence measurement and the render run on **Lana Studio's GPU** through the `lana`
MCP server, so your machine does not need to be powerful.

---

## Install

**You do not install this by hand.** Open Claude Code or Codex and paste:

> Instala la skill lana-reel siguiendo el README de https://github.com/lana-studio/skill-lana-render

Your agent clones the repository, reads this file and runs the steps below. You only do three
things yourself:

1. Have a **Lana Studio** account ([lanastudio.pe](https://lanastudio.pe)).
2. Approve the commands your agent asks to run (and type your password if a package manager
   needs `sudo`).
3. When your agent tells you to: restart it and log in — **Claude Code:** run `/mcp` → `lana` →
   Authenticate; **Codex:** run `codex mcp login lana` — in the browser, log in with the Lana
   Studio account, and say "continue". Nobody can do the login for you.

Supported: macOS 13+ and Linux, including WSL2, on **Claude Code** or **Codex CLI 0.156 or newer**
(`codex --version`). **Windows 10/11 is experimental** (Claude Code only — see "Install steps",
step 1): the code handles it, but nobody has made a full reel on Windows yet — if you do, tell us
how it went in an issue.

---

## Install steps — for the agent

You are Claude Code or Codex CLI, and the user asked you to install this skill. Run the steps
**in order**. **Verify each one before moving on**; if a step fails, stop, show the user the exact
error and what you tried, and do not improvise a different install method. Tell the user in one
line what each step is doing.

### Step 0 — Which client are you

You are either **Claude Code** or **Codex CLI**. Use your column below for every later step
marked "Claude Code:" / "Codex:".

| | Claude Code | Codex CLI |
|---|---|---|
| Skill folder | `~/.claude/skills/lana-reel` | `~/.agents/skills/lana-reel` |
| Register the `lana` MCP server | `claude mcp add --scope user --transport http lana https://mcp.lanastudio.pe/mcp` | `codex mcp add lana --url https://mcp.lanastudio.pe/mcp` |
| Log in | `/mcp` → `lana` → Authenticate | `codex mcp login lana` |
| What the user runs for you | prefix the command with `!` | ask them to run it in a separate terminal and tell you when it is done |

Codex needs **Codex CLI 0.156 or newer** — check with `codex --version`.

### Step 1 — Platform

Run `uname -s`:

| Output | Platform |
|---|---|
| `Darwin` | macOS |
| `Linux` | Linux, or WSL2 on Windows — both follow the Linux instructions |
| starts with `MINGW`, `MSYS` or `CYGWIN` | **Windows (experimental, Claude Code only)** — Claude Code's Git Bash |

On Windows, tell the user once that support is experimental and continue. Two rules apply to
every later step and to every reel:

- **`python3` means `py -3`.** The docs and the runbook say `python3`; on Windows `python3` is
  often a Microsoft Store placeholder that does nothing. Use the `py` launcher.
- Paths with `~` work as they are: in Git Bash `~` is the user's profile folder, the same one
  Claude Code reads skills from.

### Step 2 — Prerequisites

| Tool | Minimum | Check |
|---|---|---|
| `git` | any | `git --version` |
| `python3` (`py -3` on Windows) | 3.10 | `python3 -c 'import sys; print(sys.version_info >= (3, 10))'` → `True` |
| `node` + `npm` | node 20 | `node -v` → `v20` or higher; `npm -v` |
| `ffmpeg` + `ffprobe` | any | `ffmpeg -version`, `ffprobe -version` |

Check all four, then install **only what is missing or too old**, in one command:

- **macOS:** `brew install <missing>` (`python@3.12`, `node`, `ffmpeg`, `git`). If `brew` itself
  is missing, do not install Homebrew yourself — it asks for the user's password interactively.
  Give the user the one-line installer from [brew.sh](https://brew.sh) and ask them to run it —
  **Claude Code:** with the `!` prefix; **Codex:** in a separate terminal, then tell you when it's
  done — then re-check.
- **Linux (Debian/Ubuntu):** the command needs `sudo`, so ask the user to run it themselves:
  `sudo apt-get install -y python3 nodejs npm ffmpeg git` — **Claude Code:** with the `!` prefix
  (`! sudo apt-get install -y python3 nodejs npm ffmpeg git`); **Codex:** in a separate terminal,
  then tell you when it's done. If the distribution's `node` is older than 20, tell the user; do
  not add third-party package repositories without asking. Other distributions: the equivalent
  command of their package manager.
- **Windows (Claude Code only):** `winget install --exact --id <id>` for each missing tool —
  `Python.Python.3.12`, `OpenJS.NodeJS.LTS`, `Gyan.FFmpeg` (`git` is already there: Claude Code on
  Windows needs Git for Windows). winget may open a confirmation window; if it cannot run from
  your shell, ask the user to run the command with the `!` prefix. **Programs installed now are
  not on the PATH of the running Claude Code**: ask the user to restart Claude Code and say
  "continue the lana-reel install", then resume at the re-check below.

Re-run the four checks. All must pass before step 3.

### Step 3 — Get the source

- **The user gave a git URL** (normally `https://github.com/lana-studio/skill-lana-render`):
  - `~/.reel/src/skill-lana-render` does not exist →
    `git clone --depth 1 <url> ~/.reel/src/skill-lana-render`
  - it exists → `git -C ~/.reel/src/skill-lana-render pull --ff-only`
- **The user gave a local folder or an unzipped release**: use it as it is.

Call the result `<src>`. Verify: `<src>/lana-reel/SKILL.md` and `<src>/lana-reel/VERSION` exist.

### Step 4 — Install the skill folder

The skill is the folder `<src>/lana-reel/` — the whole folder, not its contents. The target
folder — call it `<dest>` — is:

- **Claude Code:** `~/.claude/skills/lana-reel/`
- **Codex:** `~/.agents/skills/lana-reel/`

First look at what is already there, at `<dest>`:

- **`<dest>` is a symlink** → a contributor's checkout. Do not touch it; tell the user and skip to
  step 5.
- **It is a directory** → an older install. Replace it: `rm -rf <dest>`.
- **Absent** → nothing to remove.

Then:

```bash
mkdir -p "$(dirname <dest>)" && cp -R <src>/lana-reel <dest>
```

Verify: `test -f <dest>/SKILL.md && cat <dest>/VERSION`.

Version 1.5.0 shipped as two skills, `reel` and `lana-mcp-render`. **Claude Code:** if
`~/.claude/skills/reel` or `~/.claude/skills/lana-mcp-render` exist, **ask the user before
deleting them**: a folder named `reel` may be a different skill of their own. **Codex** has no
prior version to migrate from.

### Step 5 — Remotion's skills (recommended)

```bash
npx skills add remotion-dev/skills
```

They teach the agent Remotion's conventions when it writes a reel's React. If the command asks
questions interactively, ask the user to run it themselves — **Claude Code:** with the `!` prefix;
**Codex:** in a separate terminal, then tell you when it's done. If it fails, tell
the user and continue: the skill works without them. The Remotion template's own `node_modules`
are not installed here — the first reel installs them once in `~/.reel/template/` (about a
minute).

### Step 6 — Register the Lana MCP server, for every folder

**Claude Code**

The server must be registered at **user scope**. Without `--scope user`, `claude mcp add` registers
it only for the current folder, and the user's next reel — opened in another folder — would have
no `lana` tools.

1. `claude mcp get lana`
   - Shows `Scope: User config` → already done; go to step 7.
   - Shows another scope (local or project) → `claude mcp remove lana -s <that scope>`, then
     add it as below.
   - Not found → add it:
2. `claude mcp add --scope user --transport http lana https://mcp.lanastudio.pe/mcp`
3. Verify: `claude mcp get lana` shows `Scope: User config`. It is normal for it to say it needs
   authentication at this point.

**Codex**

There is no `--scope` flag: `~/.codex/config.toml` already applies to every folder.

1. `codex mcp get lana`
   - Shows `url: https://mcp.lanastudio.pe/mcp` → already done; go to step 7.
   - Shows a different URL → `codex mcp remove lana`, then add it as below.
   - Not found → add it:
2. `codex mcp add lana --url https://mcp.lanastudio.pe/mcp`
3. Verify: `codex mcp get lana` shows `transport: streamable_http` and the URL above. It is normal
   for it to say it needs authentication at this point.

### Step 7 — Hand over to the user: restart and log in

You cannot restart the client or complete an OAuth login. Stop here and tell the user, in their
language, exactly this:

**Claude Code**

1. Close Claude Code and open it again (it only detects a new skill and a new MCP server on
   start).
2. Type `/mcp`, choose **lana**, then **Authenticate**. The browser opens: log in with the Lana
   Studio account and accept the permissions. A `401` right before the browser opens is normal —
   it is what starts the login.
3. Come back and say: "continue the lana-reel install".

**Codex**

1. In a separate terminal: `codex mcp login lana`. The browser opens: log in with the Lana Studio
   account and accept the permissions. If the browser already opened on its own during
   `codex mcp add` and the login already finished, skip this. Without a graphical browser (SSH,
   WSL): `codex mcp login lana --no-browser` prints a URL — open it yourself, log in, and paste
   back the callback URL it gives you.
2. Open `codex` again — a restart is required for it to load the server and the skill.
3. Check with `/mcp` that `lana` shows as connected.
4. Come back and say: "continue the lana-reel install".

The permissions it must grant are `lana:mcp`, `assets:read`, `assets:write`,
`transcription:create`, `analysis:create`, `analysis:read`, `render:create`, `render:read` and
`jobs:read`.

### Step 8 — After the restart: the hello render

1. Check that the `lana_*` tools are available. If not: the user did not restart or did not
   authenticate — go back to step 7.
2. `lana_get_capabilities(topic="limits")` — never without a topic. Confirm `render_enabled` is
   `true` and there is daily quota left.
3. Run the hello render exactly as `<dest>/examples/hello-render.md` says (Claude Code:
   `~/.claude/skills/lana-reel/examples/hello-render.md`; Codex:
   `~/.agents/skills/lana-reel/examples/hello-render.md`), from a scratch folder. One job, about
   two minutes. It checks the login, the permissions, the quota, the sound-effects pack and the
   download in one shot.
4. If a tool answers `FORBIDDEN_SCOPE`, the message names the missing permission. **Claude Code:**
   ask the user to repeat `/mcp` → `lana` → Authenticate and accept it. **Codex:** ask the user to
   run `codex mcp logout lana && codex mcp login lana` and accept it.

### Step 9 — Done

Tell the user the install works (version from `VERSION`, and that the hello render played), and
how to make their first reel:

1. Record 30–45 seconds on the phone, **vertical**, talking to the camera.
2. Put the file in a folder of its own and open your client (Claude Code or Codex) **in that
   folder**.
3. Ask for it — "Hazme un reel con take.MOV" is enough — or fill in the brief at
   `~/.claude/skills/lana-reel/prompt-reel.md` (Codex:
   `~/.agents/skills/lana-reel/prompt-reel.md`) and paste it. On Codex the skill can also be
   invoked directly with `$lana-reel`.

The skill looks at the video, asks what it cannot decide alone (mirroring, full or trimmed
script, style), renders a proof and then the final. A full reel uses 6 to 12 of the 50 daily Lana
jobs.

---

## Update and uninstall

- **Update:** ask your agent to "update lana-reel following the README of
  https://github.com/lana-studio/skill-lana-render". It repeats steps 3, 4 and 9 (step 3 pulls,
  step 4 replaces the folder); the MCP server and the login stay as they are.
- **Uninstall:**
  - **Claude Code:** `rm -rf ~/.claude/skills/lana-reel ~/.reel` and `claude mcp remove lana -s user`.
  - **Codex:** `rm -rf ~/.agents/skills/lana-reel ~/.reel` and `codex mcp remove lana`.

  Your material on Lana is deleted from your Lana Studio account, not from here.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| The skill does not show up (Claude Code) | The path must be exactly `~/.claude/skills/lana-reel/SKILL.md` — no extra folder in between. Restart Claude Code. |
| The skill does not show up (Codex) | The path must be exactly `~/.agents/skills/lana-reel/SKILL.md` — no extra folder in between. Restart Codex — it only detects a new skill on start. |
| No `lana_*` tools in a new folder (Claude Code) | The server was registered without `--scope user`. Step 6. |
| No `lana_*` tools in a new folder (Codex) | Codex was not restarted after `codex mcp add`, or the login did not finish — check `codex mcp list`'s `Auth` column. Step 6–7. |
| `FORBIDDEN_SCOPE` | A permission was not accepted at login. Claude Code: `/mcp` → `lana` → Authenticate again. Codex: `codex mcp logout lana && codex mcp login lana`. |
| `!! ffmpeg/ffprobe not found on PATH` | Step 2. |
| `npm not found` | Node.js 20 or newer is missing. Step 2. |
| Windows: `python3` does nothing or opens the Microsoft Store | Use `py -3`. Step 1. |
| Windows: a tool was installed but is still "not found" | Your client was not restarted after winget. Step 2. |
| Windows: `node_modules: junction of …` or `copy of …` | Normal: Windows refused a symlink and the skill used what needs no privilege. |

---

## Details

### What runs where

| On your machine | On Lana |
|---|---|
| Looking at frames of the video (`ffmpeg`) | Ingest: h264 proxy + 16 kHz audio |
| Writing the plan and the React | Word-level transcription |
| Type-checking and packaging | Silence measurement |
| Verifying the finished file | Person segmentation |
| | The render (GPU) |

### Your data

- **Your material is not used to train models.** This is a commitment of Lana Studio about how the
  service operates; unlike everything below, it is not something this repository's code can show
  you.
- **What you upload is processed on Lana Studio's machines** — ingest, transcription and render. It
  does not go through a third-party media API.
- **Transfers are direct and signed.** A tool returns a signed URL and your machine moves the bytes;
  files do not pass through the MCP server. Upload URLs expire in 15 minutes, download URLs in 1
  hour.
- **Nothing in this repository touches a credential.** No script reads a token, none talks to the
  gateway, and no signed URL is written to disk. The only network call a script makes is moving
  bytes to or from a URL a tool just returned.
- **Job records are kept 7 days** after they finish; then `lana_get_job` answers `JOB_NOT_FOUND`.
  The rendered file is not deleted with the record: it stays in your Lana Studio storage, available
  through `lana_get_asset`.
- **You delete your material from your Lana Studio account.** Deleting an original deletes
  everything derived from it (proxy, extracted audio). There is no delete tool over MCP in this
  version.

### Shared library & licenses

Lana offers a library of resources — fonts, alpha overlays, textures, B-roll, audio — that a render
can use **without uploading anything**. The skill shows every entry with its `license` field
**exactly as it comes**.

**Some entries say `license: unknown`.** They are shown anyway, with that value visible; the skill
never hides or filters an entry by its license. **Checking the license before publishing
commercially is your decision**, not the skill's. Entries also carry `attribution_required`.

### Quotas

| | |
|---|---|
| Jobs per day | 50 |
| Jobs in flight at once | 3 |
| Concurrent renders | 1 |
| GPU seconds per month | 36 000 |

Every kind of job counts as in flight: ingest, transcription, silence, segmentation and render. A
full reel uses 6 to 12. The GPU is shared: when several people render at once, the queue grows.

### Not in this version

- Clients other than Claude Code and Codex CLI.
- Verified Windows support: it is experimental (see "Install"), and on Claude Code only — Codex on
  Windows has not been tried.
- Teleprompter-glance removal, hand tracking, headlines behind the person, voice echo.
- Background music.
- Local rendering — on purpose: rendering is what the MCP server exists for.

Teleprompter-glance removal and the rest of that line need capabilities that do not exist as MCP
tools yet.

**Codex CLI support is new**: the login flow (client registration, PKCE, scopes) was verified
against Lana's authorization server with Codex's exact request; a complete reel driven from Codex
has not been run by the maintainers yet. Tell us in an issue how it went. Requires Codex CLI 0.156
or newer (`codex --version`).

### Versions

The skill is versioned **together with the `lana-mcp-render` service**: the first two numbers of
`lana-reel/VERSION` are the minimum service version it needs (1.5.1 needs 1.5 or newer); the third
changes only when the skill changes. The skill checks it by itself at the start of every reel. The
Remotion template is pinned to the exact version the renderer uses (4.0.484). History:
[CHANGELOG.md](CHANGELOG.md).

## Support

[GitHub Issues](https://github.com/lana-studio/skill-lana-render/issues), best effort, **no SLA and
no guaranteed response time**. There is no support email or private channel.

**Never paste a token or a signed URL into an issue.**

## Contributing

Work on the skill in place by linking it instead of copying (step 4 leaves a symlink alone):

```bash
ln -s "$PWD/lana-reel" ~/.claude/skills/lana-reel   # Claude Code
ln -s "$PWD/lana-reel" ~/.agents/skills/lana-reel   # Codex
```

| | |
|---|---|
| `lana-reel/` | **The skill — the only thing that gets installed.** `SKILL.md`, `KNOWHOW.md`, `references/`, `examples/`, `scripts/`, `template/`, `assets/`. |
| `tests/`, `tools/` | For contributors only; never shipped. |

This repo has no CI. Before opening a PR, run `python3 tools/check.py` from the repo root.
`python3 tools/make_release.py` builds the zip for users without git
(`dist/lana-reel-<version>.zip`: the skill folder, this README, `LICENSE` and `NOTICE`); step 3
accepts the unzipped folder.

## License

The code is [Apache-2.0](LICENSE). Bundled resources carry their own license, listed in
[NOTICE](NOTICE): the five fonts in `lana-reel/assets/fonts/` are SIL Open Font License 1.1 and the
two sound effects in `lana-reel/assets/sfx/` are CC0 1.0.
