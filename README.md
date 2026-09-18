# skill-lana-render

A skill for [Claude Code](https://claude.com/claude-code) that turns a phone recording of you
talking into a finished vertical reel — captions aligned to what you actually said, silences
cut, headlines, cards, transitions and sound effects — **rendered on Lana Studio's GPU through
the `lana` MCP server**. Your machine writes React and looks at frames; ingest, transcription,
silence measurement and the render all run on Lana.

**Users: start with [`LEEME-PRIMERO.md`](LEEME-PRIMERO.md)** (Spanish). Install steps are in
[`INSTALAR.md`](INSTALAR.md); privacy, quotas, licenses and what is not in v1 are in
[`DETALLES.md`](DETALLES.md).

## Install, in short

1. In Claude Code: `npx skills add remotion-dev/skills` — Claude Code checks `node`, `python3`
   and `ffmpeg` while it installs Remotion's skills.
2. `mkdir -p ~/.claude/skills && cp -R lana-reel ~/.claude/skills/`
3. `claude mcp add --transport http lana https://mcp.lanastudio.pe/mcp`, then `/mcp` → `lana` →
   Authenticate. The initial `401` is normal.
4. Ask: `Make a reel out of take.MOV` — or fill in [`lana-reel/prompt-reel.md`](lana-reel/prompt-reel.md).

There is no setup script. The first project on a machine installs the Remotion template's
`node_modules` once, in `~/.reel/template/`.

## What is in this repository

| | |
|---|---|
| `lana-reel/` | **The skill — the only thing that gets installed.** `SKILL.md`, `KNOWHOW.md`, `references/`, `examples/`, `scripts/`, `template/`, `assets/`. |
| `LEEME-PRIMERO.md`, `INSTALAR.md`, `DETALLES.md` | The user-facing docs that ship next to it. |
| `tests/`, `tools/` | For contributors only; never shipped. |

## Contributing

Work on the skill in place by linking it instead of copying:

```bash
ln -s "$PWD/lana-reel" ~/.claude/skills/lana-reel
```

This repo has no CI. Before opening a PR, run `python3 tools/check.py` from the repo root.
`python3 tools/make_release.py` builds the zip users download
(`dist/lana-reel-<version>.zip`: the skill folder plus the three docs above).

[GitHub Issues](https://github.com/lana-studio/skill-lana-render/issues) are best effort, with no
SLA. **Never paste a token or a signed URL into an issue.**

## License

The code is [Apache-2.0](LICENSE). Bundled fonts (SIL OFL 1.1) and sound effects (CC0 1.0) are
listed in [NOTICE](NOTICE).
