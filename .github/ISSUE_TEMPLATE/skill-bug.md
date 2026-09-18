---
name: Skill bug
about: A script fails, a check is wrong, or the reel comes out wrong
title: "[bug] "
labels: bug
---

**Never paste tokens, signed URLs or the contents of a credentials file.**

## What happened

<!-- One or two sentences. What did you expect, what did you get? -->

## Versions

```
# from ~/.claude/skills/reel/INSTALLED.json
version:
commit:
mode:

# from: python3 ~/.claude/skills/reel/scripts/lana/caps.py limits
service_version:
render_enabled:
```

## The exact command

```
# the command you ran, as you ran it
```

## The exact output

```
# paste the output. If a check printed lines starting with `!!`, include every one of them —
# they are the finding, and the first one is usually the cause of the rest.
#
# Two that are not bugs and do not need an issue:
#   !! ffmpeg/ffprobe not found on PATH — run setup.py -> setup.py was never run, or ffmpeg is not installed
#   !! URL expired or invalid: ask the tool again      -> a signed URL aged out; read the job again
```

## Environment

- OS and version:
- `python3 --version`:
- `node --version`:
- `ffmpeg -version` (first line):

## Anything else

<!-- Did it work before? Does it happen with every take or just one? -->
