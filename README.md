# skill-lana-render

Two skills for [Claude Code](https://claude.com/claude-code) that turn a phone recording of you
talking into a finished vertical reel — captions aligned to what you actually said, silences
cut, headlines, cards, transitions and sound effects — **rendered on Lana Studio's GPU through
the `lana` MCP server**.

- **`reel`** — the runbook: look at the take, cut it, style it, check it, render it, verify it.
- **`lana-mcp-render`** — how to operate the MCP: connect, upload, transcribe, measure, render,
  download, and what every error code means.

Your machine writes React and looks at frames. **Everything heavy happens on Lana**: ingest,
transcription, silence measurement, person segmentation and the render itself. A ten-year-old
laptop is enough — that is the point of doing it over an MCP server instead of locally. This
repository is the **client**: the skills that run inside Claude Code. The server is Lana
Studio's own hosted service at `mcp.lanastudio.pe`, and its code is not part of this repository.

## Requirements

| | Why |
|---|---|
| **Claude Code** | The only supported client in v1. |
| **A Lana Studio account** | Sign up at [lanastudio.pe](https://lanastudio.pe); the MCP authorizes against it. |
| **`python3` >= 3.10** | Every script here is standard library only — nothing to `pip install`. |
| **`node` >= 20** | Type-checks the Remotion template before you spend a render job. |
| **`ffmpeg` >= 5 (with `ffprobe`)** | **Required.** It is how the agent *sees* your take: it pulls frames so it can decide mirroring, subject side and framing with you. It also adds a silent audio track to a video that has none, and verifies the finished file. It never transcodes, never measures silence and never renders — those run on Lana. |

```bash
brew install ffmpeg                # macOS
sudo apt install ffmpeg            # Debian / Ubuntu
sudo dnf install ffmpeg            # Fedora
sudo pacman -S ffmpeg              # Arch
```

macOS 13+ or Linux. No GPU, no virtualenv, no machine-learning model downloads. Windows is not
supported in v1.

## Install

```bash
git clone https://github.com/lana-studio/skill-lana-render.git && cd skill-lana-render
claude mcp add --transport http lana https://mcp.lanastudio.pe/mcp
claude                                   # then: /mcp → lana → Authenticate
python3 install.py                       # copies both skills into ~/.claude/skills/
python3 setup.py                         # checks python3, node, ffmpeg; installs the template
```

`install.py` never overwrites: if a skill of that name already exists it is moved to
`~/.claude/skill-backups/<name>-<date>/` first. `setup.py` **fails** if `ffmpeg` or `ffprobe` is
missing, and prints the install command for your system.

The initial `401` when you authenticate is normal — it is what starts the OAuth flow.

## Your first render

```
Run the hello render.
```

Five calls, one job, about two minutes: it renders two seconds of video with a Google Font and
one sound effect. Full walkthrough with expected output:
[`skills/lana-mcp-render/examples/hello-render/`](skills/lana-mcp-render/examples/hello-render/README.md).

**If it fails with `FORBIDDEN_SCOPE`, re-authorize in `/mcp` and grant the scope the message
names.** That one call also tells you whether render is enabled on your account, how much quota
you have left, and whether you can download a result.

## Your first reel

**Record 30 to 45 seconds on your phone, vertical, talking to camera.** There is no sample video
in this repository on purpose: your own face saying your own words is the material this skill is
built for, and it takes a minute to make.

Then, in Claude Code:

```
Make a reel out of raw/take.MOV
```

The agent will look at the frames, ask you three questions it cannot answer on its own (mirror
it? full script or trimmed? script or audio when they differ?), and take it from there.
A worked example with a script and a config to copy:
[`examples/first-reel/`](examples/first-reel/README.md).

Expect 6 to 12 Lana jobs for a complete reel, and one proof render before the final one.

## What runs where

| On your machine | On Lana |
|---|---|
| Looking at frames (`ffmpeg`) | Ingest: h264 proxy + 16 kHz audio |
| Writing the plan and the React | Transcription (word-level) |
| Type-checking and packaging | Silence measurement |
| Verifying the finished file | Person segmentation |
| | The render itself (GPU) |

## Your data

- **Your material is not used to train models.** This one is a commitment from Lana Studio about
  how the service is operated — unlike everything below it, it is not something the code in this
  repository can show you.

The rest you can verify here, because it is how the system is built:

- **Your uploads are processed on Lana Studio's own machines** — the ingest, the transcription
  and the render. They are not passed to a third-party media API.
- **Transfers are direct and signed.** A tool hands you a signed URL and your machine uploads or
  downloads the bytes; the files do not travel through the MCP server. Upload URLs expire in
  15 minutes, download URLs in 1 hour.
- **Nothing in this repository ever touches a credential.** No script reads a token, none talks
  to the gateway, and no signed URL is ever written to disk. The only network call any script
  makes is moving bytes to or from a URL a tool just returned.
- **Job records are kept for 7 days** after they finish; after that `lana_get_job` answers
  `JOB_NOT_FOUND`. **The rendered file is not deleted with the record** — it stays in your Lana
  Studio storage and is still reachable with `lana_get_asset`.
- **You delete your material from your Lana Studio account.** Deleting an original also deletes
  everything derived from it (proxy, extracted audio). There is no delete tool over MCP in v1.

Formal terms and a privacy policy will be linked here when they are published. If you have a
question this section does not answer, open an issue and ask.

## Shared library & licenses

Lana ships a shared library of creative resources — fonts, alpha overlays, textures, B-roll,
audio — that you can use in a render **without uploading anything**. Ask for it with
`lana_get_capabilities(topic="library")` and the skill shows you every entry with its `license`
field **exactly as it comes**.

**Some entries carry `license: unknown`.** They are shown to you anyway, with that value
visible; the skill never hides an entry or filters the catalogue by license. **Checking a
resource's license before you publish commercially is your call**, not something this skill
decides for you. Entries also carry `attribution_required`.

## Quotas

| | |
|---|---|
| Jobs per day | 50 |
| Jobs in flight at once | 3 |
| Concurrent renders | 1 |
| GPU seconds per month | 36 000 |

Every job kind counts toward "in flight": ingest, transcription, silence, segmentation, render.
`lana_get_capabilities(topic="limits")` reports what you have consumed and when it renews — ask
before you spend. The real constraint is a single shared GPU: if several people render at once,
the queue gets longer.

## Not in v1

- **Codex CLI and any other MCP client.** Claude Code only; tracked as an open issue here.
- **Windows.**
- Teleprompter-glance removal, hand tracking, headlines behind the person, voice echo.
- Background music.
- Local rendering — by design; the render is what the MCP server is for.

The first four need capabilities that do not exist as MCP tools yet. Do not substitute local
tools for them: the whole point is that this works on any machine.

## Support

[GitHub Issues](https://github.com/lana-studio/skill-lana-render/issues), **best effort, no SLA and no
guaranteed response time.** There is no support email and no private channel. Three templates
are provided: a skill bug, an MCP connection problem, and a capability request.

**Never paste a token or a signed URL into an issue.**

This repo has no CI. Before opening a PR, run `python3 tools/check.py` from the repo root.

## License

The code is [Apache-2.0](LICENSE). Bundled assets carry their own licenses, listed in
[NOTICE](NOTICE): the five fonts in `assets/fonts/` are under the SIL Open Font License 1.1
(`assets/fonts/OFL.txt`), and the two sound effects in `assets/sfx/` are CC0 1.0
(`assets/sfx/LICENSE`).

Fonts and sound effects that come from Lana's own catalogue at render time are not redistributed
here — see "Shared library & licenses" above.

## Versioning

This repository is versioned **together with the `lana-mcp-render` service**: version `1.5.0`
here needs `lana-mcp-render >= 1.5.0` on the server side. `caps.py limits --check` compares the
two and tells you if they drifted. The Remotion template is pinned to the exact version the
renderer runs (4.0.484) — do not bump it on its own.

See [CHANGELOG.md](CHANGELOG.md).
