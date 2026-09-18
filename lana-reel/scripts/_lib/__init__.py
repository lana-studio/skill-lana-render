"""Shared library for the reel-skill scripts (scripts/reel/ and scripts/lana/).

Stdlib only. Never imports urllib/http.client/socket/requests/httpx (that is
scripts/lana/transfer.py's job alone — it's the only script that touches the
network at all) and never reads an environment variable whose name contains
TOKEN/SECRET/CREDENTIAL/PASSWORD.
"""

import sys as _sys


def force_utf8_output(streams=None, platform: str | None = None) -> None:
    """On Windows, stdout/stderr redirected to a pipe (which is how Claude
    Code reads every script) use the ANSI code page — cp1252 — and the first
    `→` a script prints raises UnicodeEncodeError. Every script imports this
    package, so this runs before any of them prints. A no-op everywhere
    else, and on any stream that is already UTF-8 or cannot be reconfigured
    (pytest's capture objects, for instance)."""
    if (platform or _sys.platform) != "win32":
        return
    for stream in streams if streams is not None else (_sys.stdout, _sys.stderr):
        encoding = (getattr(stream, "encoding", None) or "").lower().replace("-", "").replace("_", "")
        if encoding != "utf8" and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


force_utf8_output()
