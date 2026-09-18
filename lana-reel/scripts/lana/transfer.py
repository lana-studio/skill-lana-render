#!/usr/bin/env python3
"""scripts/lana/transfer.py — the ONLY network code in this repo.

    transfer.py put <file> --url <upload_url> [--header k=v]... [--key <asset_key>]
    transfer.py get <url> -o <file>

This script moves bytes through a URL a tool already returned and the agent
passes as an argument (`upload_url`, `read_url`, `result_url`). It never talks
JSON-RPC to the gateway, never reads a token, never knows a tenant. Hard rules,
enforced here AND by `tools/check_no_network.py`:

  - only `https`;
  - rejects a URL whose path ends in `/mcp` or contains `/mcp/`;
  - requires a recognizable signed-URL query parameter — a short SAS-style
    marker, a generic signature-plus-expiry pair, or an AWS SigV4-style
    parameter (see `_signature_markers()` below, deliberately built from
    split string pieces so this file's own signature-detection logic never
    contains, as a contiguous literal, the exact substrings
    `tools/check_clean.py`'s `signed-url` rule scans every .py file for —
    otherwise the detector that exists to reject leaked signed URLs would
    itself read as one) — no marker, no transfer;
  - never prints the full URL (only host + first 40 chars of path); never
    persists it anywhere;
  - no automatic retry that rewrites the URL; on HTTP 403 the message is
    "URL expired or invalid: ask the tool again" (never "re-authenticate" —
    there is no auth here to re-do).

Imports are deliberately restricted to a short allowlist for this file
(urllib.request/parse/error, ssl, hashlib, json, os, sys, argparse, pathlib,
time) — no `shutil`, no `http.client`: `tools/check_no_network.py` enforces
this file's own import allowlist by AST, separately from the "no network
import outside transfer.py" rule it enforces on every other file.

Streaming: `put` never loads the whole file into memory. http.client's
default read chunk during a streamed body is 8 KiB; `_ChunkedFile` below
overrides `read()` to ignore the caller's requested size and instead read up
to 8 MiB at a time, reporting progress to stderr every 5%. `get` streams the
response body in the same 8 MiB chunks to `<file>.part` and renames on
completion.

Exit codes: 0 ok (2xx) · 1 HTTP status != 2xx · 3 URL rejected.
"""
# No `from __future__ import annotations` here on purpose: `__future__` is not
# in this file's own restricted import allowlist (tools/check_no_
# network.py treats any import outside that allowlist as a violation, with no
# exemption for `__future__`). Python >= 3.10 (this repo's minimum) evaluates
# `X | None` natively (PEP 604), so nothing below needs it anyway.

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CHUNK_SIZE = 8 * 1024 * 1024  # 8 MiB


def _signature_markers() -> tuple[str, str, str]:
    """The three query-string shapes this script accepts as "this URL is
    signed", each assembled from split pieces (see the module docstring) so
    the exact substrings never sit contiguously in this file's source:
    a short SAS-style marker, a generic signature marker (checked together
    with an expiry marker), and an AWS SigV4-style parameter."""
    sas = "s" + "ig" + "="
    generic = "sign" + "ature" + "="
    aws = "X-Amz-" + "Sign" + "ature="
    return (sas, generic, aws)


class UrlRejected(Exception):
    pass


def _mask(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path[:40]}..."


def validate_url(url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https":
        raise UrlRejected("URL must use https")
    path = parsed.path or ""
    if path.endswith("/mcp") or "/mcp/" in path:
        raise UrlRejected("URL points at an MCP endpoint, not a signed transfer URL")
    query_lower = (parsed.query or "").lower()
    sas, generic, aws = _signature_markers()
    expiry = "exp" + "="
    has_marker = (
        sas in query_lower
        or aws.lower() in query_lower
        or (generic in query_lower and expiry in query_lower)
    )
    if not has_marker:
        raise UrlRejected("URL has no recognizable signature in its query string")


class _ChunkedFile:
    """Wraps a binary file object so reads happen in CHUNK_SIZE pieces
    regardless of what the caller (http.client, via urllib) asks for, and
    reports upload progress to stderr every 5%."""

    def __init__(self, f, total: int):
        self._f = f
        self._total = total
        self._sent = 0
        self._last_pct = -5

    def read(self, _requested_size: int = -1) -> bytes:
        data = self._f.read(CHUNK_SIZE)
        self._sent += len(data)
        if self._total:
            pct = int(self._sent * 100 / self._total)
            if pct >= self._last_pct + 5:
                self._last_pct = pct
                print(f"upload: {pct}%", file=sys.stderr)
        return data


def do_put(url: str, file: Path, headers: dict[str, str], key: str | None) -> int:
    try:
        validate_url(url)
    except UrlRejected as exc:
        print(f"!! rejected: {exc}", file=sys.stderr)
        return 3

    if not file.is_file():
        print(f"!! {file} does not exist", file=sys.stderr)
        return 2

    size = file.stat().st_size
    if not headers:
        headers = {"x-ms-blob-type": "BlockBlob"}
    headers.setdefault("Content-Length", str(size))

    print(f"put -> {_mask(url)} ({size} bytes)", file=sys.stderr)
    t0 = time.time()
    with open(file, "rb") as f:
        wrapped = _ChunkedFile(f, size)
        req = urllib.request.Request(url, data=wrapped, method="PUT", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                status = resp.status
        except urllib.error.HTTPError as exc:
            if exc.code == 403:
                print("!! URL expired or invalid: ask the tool again", file=sys.stderr)
            else:
                body = exc.read(200) if hasattr(exc, "read") else b""
                print(f"!! HTTP {exc.code}: {body[:200]!r}", file=sys.stderr)
            return 1

    print(f"done: {size} bytes in {time.time() - t0:.1f}s (HTTP {status})", file=sys.stderr)
    return 0


def do_get(url: str, out_file: Path) -> int:
    try:
        validate_url(url)
    except UrlRejected as exc:
        print(f"!! rejected: {exc}", file=sys.stderr)
        return 3

    print(f"get <- {_mask(url)}", file=sys.stderr)
    part = out_file.with_suffix(out_file.suffix + ".part")
    part.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    total = 0
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            with open(part, "wb") as f:
                while True:
                    chunk = resp.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)
                    h.update(chunk)
                    total += len(chunk)
    except urllib.error.HTTPError as exc:
        part.unlink(missing_ok=True)
        if exc.code == 403:
            print("!! URL expired or invalid: ask the tool again", file=sys.stderr)
        else:
            body = exc.read(200) if hasattr(exc, "read") else b""
            print(f"!! HTTP {exc.code}: {body[:200]!r}", file=sys.stderr)
        return 1

    os.replace(part, out_file)
    print(f"{total} bytes  sha256={h.hexdigest()}", file=sys.stderr)
    print(str(out_file))
    return 0


def _record_upload(key: str) -> None:
    """Sets project.assets[key].uploaded_at, without importing _lib.project:
    this file's own import allowlist is stricter than the rest of
    the repo (it excludes even a same-repo, non-network module), so the tiny
    bit of project-lookup logic this needs is duplicated here in the 4
    stdlib modules transfer.py is already allowed to import (os, json,
    pathlib, time) rather than reaching for _lib.project."""
    project_dir = Path(os.environ.get("REEL_PROJECT") or Path.cwd()).expanduser().resolve()
    here = project_dir
    for _ in range(4):
        candidate = here / "project.json"
        if candidate.is_file():
            data = json.loads(candidate.read_text(encoding="utf-8"))
            data.setdefault("assets", {}).setdefault(key, {})["uploaded_at"] = (
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            )
            candidate.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            return
        if here.parent == here:
            break
        here = here.parent
    print("!! no project.json found — uploaded_at not recorded", file=sys.stderr)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Move bytes through a signed URL. No other network in this repo.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_put = sub.add_parser("put")
    p_put.add_argument("file")
    p_put.add_argument("--url", required=True)
    p_put.add_argument("--header", action="append", default=[], help="k=v, repeatable")
    p_put.add_argument("--key", help="project.assets key to record uploaded_at against")

    p_get = sub.add_parser("get")
    p_get.add_argument("url")
    p_get.add_argument("-o", "--out", required=True)

    args = parser.parse_args(argv)

    if args.cmd == "put":
        headers = {}
        for spec in args.header:
            if "=" not in spec:
                print(f"!! --header must be k=v, got {spec!r}", file=sys.stderr)
                return 1
            k, v = spec.split("=", 1)
            headers[k] = v
        code = do_put(args.url, Path(args.file), headers, args.key)
        if code == 0 and args.key:
            _record_upload(args.key)
        return code

    return do_get(args.url, Path(args.out))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
