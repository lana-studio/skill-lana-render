#!/usr/bin/env python3
"""tools/check_no_network.py — enforce the network boundary: nothing in this repo
talks to the Lana MCP gateway directly.

The only network code allowed anywhere is scripts/lana/transfer.py, moving bytes
through a URL the agent already has (a signed upload_url/read_url/result_url) —
never a token, never JSON-RPC.

AST-parses every *.py file (plus a light text scan for *.sh and template/**/*.ts(x)):

  - fails if a network module (urllib, http.client, socket, ssl, requests, httpx,
    aiohttp, websocket(s), ftplib, smtplib) is imported outside transfer.py;
  - fails if transfer.py imports anything outside its stdlib allowlist;
  - fails if subprocess/os.system/os.popen invoke security/curl/wget/nc/ssh/scp/
    rsync/ftp/openssl;
  - fails if ffmpeg/ffprobe are invoked from a file other than probe_source.py,
    prep_upload.py or verify_output.py;
  - fails if a literal ffmpeg argument looks like a network URL/protocol
    (http://, https://, rtmp://, tcp://, -protocol_whitelist) — ffmpeg is never a
    network client here;
  - fails if the literal "mcp.lanastudio.pe" appears in any .py file, transfer.py
    included (it only ever sees URLs the agent hands it as arguments);
  - fails if any .py reads an environment variable whose name contains TOKEN,
    SECRET, CREDENTIAL or PASSWORD;
  - fails if a *.sh file shells out to curl/wget/security;
  - fails if a template/**/*.ts(x) file calls fetch(/XMLHttpRequest or contains a
    bare http(s):// URL outside a comment.

Exit 0 = clean. Exit 1 = findings (`path:line: rule: excerpt`). Exit 2 = execution error.
Only stdlib.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _shared import (  # noqa: E402
    allowed_skip_counts,
    forbidden_allow_prefix,
    is_allowed,
    list_files,
    read_text,
    skill_rel,
)

TRANSFER_SCRIPT = "scripts/lana/transfer.py"

NETWORK_MODULES = {
    "urllib", "urllib.request", "urllib.parse", "urllib.error",
    "http.client", "socket", "ssl", "requests", "httpx", "aiohttp",
    "websocket", "websockets", "ftplib", "smtplib",
}
# ssl and urllib.parse are also needed by transfer.py itself for TLS + query
# parsing; only the "acts as a network client on its own" modules are network
# modules for every OTHER file. transfer.py is exempt from this rule entirely
# (its own allowlist below is stricter and takes over).

TRANSFER_ALLOWED_IMPORTS = {
    "urllib.request", "urllib.parse", "urllib.error",
    "ssl", "hashlib", "json", "os", "sys", "argparse", "pathlib", "time",
}

BLOCKED_SUBPROCESS_TOKENS = {
    "security", "curl", "wget", "nc", "ssh", "scp", "rsync", "ftp", "openssl",
}
FFMPEG_TOKENS = {"ffmpeg", "ffprobe"}
FFMPEG_ALLOWED_FILES = {
    "scripts/reel/probe_source.py",
    "scripts/lana/prep_upload.py",
    "scripts/lana/verify_output.py",
}
SUBPROCESS_CALL_TARGETS = {
    "subprocess.run", "subprocess.call", "subprocess.check_call",
    "subprocess.check_output", "subprocess.Popen",
}
OS_SHELL_CALL_TARGETS = {"os.system", "os.popen"}

FFMPEG_NETWORK_MARKERS = ("http://", "https://", "rtmp://", "tcp://", "-protocol_whitelist")

MCP_HOST_LITERAL = "mcp.lanastudio.pe"

# Same self-reference note as check_clean.py's SELF_EXEMPT_FILES, scoped just as
# tightly: this file's own MCP_HOST_LITERAL constant is a Python string literal
# equal to the value mcp-literal-in-python searches for, and check_clean.py
# defines its own constant for the full endpoint that contains that same host
# as a substring — both are pattern-as-data, not a leak. tools/_shared.py does
# NOT contain this literal anywhere (verified: emptying this set and
# re-running finds only these two files) and stays fully scanned, same as
# every other file. All AST-based rules (imports, subprocess, ffmpeg, env
# vars) still run on both files normally — only the literal-substring scan
# below skips them.
SELF_EXEMPT_FILES = {"tools/check_clean.py", "tools/check_no_network.py"}

ENV_CREDENTIAL_MARKERS = ("TOKEN", "SECRET", "CREDENTIAL", "PASSWORD")

SH_NETWORK_RE = re.compile(r"\b(curl|wget)\b|\bsecurity\s")

# (?<!:) keeps this from treating the "//" inside "http://"/"https://" as a
# line-comment start (that would silently swallow the rest of the line,
# including the very URL literal this check exists to catch).
TS_COMMENT_RE = re.compile(r"(?<!:)//.*?$|/\*.*?\*/", re.MULTILINE | re.DOTALL)
TS_NETWORK_RE = re.compile(r"\bfetch\s*\(|\bXMLHttpRequest\b|https?://")


class Finding:
    __slots__ = ("path", "line", "rule", "excerpt")

    def __init__(self, path: str, line: int, rule: str, excerpt: str):
        self.path = path
        self.line = line
        self.rule = rule
        self.excerpt = excerpt.strip()[:160]

    def as_dict(self) -> dict:
        return {"path": self.path, "line": self.line, "rule": self.rule, "excerpt": self.excerpt}

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.rule}: {self.excerpt}"


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------

def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted_name(node.value)
        return f"{base}.{node.attr}" if base is not None else None
    return None


def _collect_import_aliases(tree: ast.AST) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                aliases[bound] = alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            for alias in node.names:
                bound = alias.asname or alias.name
                aliases[bound] = f"{node.module}.{alias.name}"
    return aliases


def _resolve(func_node: ast.AST, aliases: dict[str, str]) -> str | None:
    dotted = _dotted_name(func_node)
    if dotted is None:
        return None
    parts = dotted.split(".")
    head = aliases.get(parts[0], parts[0])
    return ".".join([head] + parts[1:])


def _string_constants(node: ast.AST) -> list[str]:
    out = []
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            out.append(child.value)
    return out


def _first_token(call: ast.Call) -> str | None:
    if not call.args:
        return None
    arg = call.args[0]
    if isinstance(arg, (ast.List, ast.Tuple)):
        if not arg.elts:
            return None
        first = arg.elts[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value
        return None
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        parts = arg.value.split()
        return parts[0] if parts else None
    return None


# ---------------------------------------------------------------------------
# Python (AST) rules
# ---------------------------------------------------------------------------

def check_python_file(rel_posix: str, source: str) -> list[Finding]:
    findings: list[Finding] = []
    try:
        tree = ast.parse(source, filename=rel_posix)
    except SyntaxError as exc:
        return [Finding(rel_posix, exc.lineno or 1, "syntax-error", str(exc))]

    is_transfer = skill_rel(rel_posix) == TRANSFER_SCRIPT
    aliases = _collect_import_aliases(tree)

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            lineno = node.lineno
            if isinstance(node, ast.Import):
                modules = [a.name for a in node.names]
            else:
                modules = [node.module] if node.module else []
            for module in modules:
                if module is None:
                    continue
                top = module.split(".")[0]
                dotted_or_top = module if module in NETWORK_MODULES else top
                is_network = module in NETWORK_MODULES or top in NETWORK_MODULES
                if is_transfer:
                    if module not in TRANSFER_ALLOWED_IMPORTS and top not in {
                        m.split(".")[0] for m in TRANSFER_ALLOWED_IMPORTS
                    }:
                        findings.append(Finding(
                            rel_posix, lineno, "transfer-import-not-allowed",
                            f"import {module}",
                        ))
                elif is_network:
                    findings.append(Finding(
                        rel_posix, lineno, "network-import-outside-transfer",
                        f"import {module}",
                    ))

        elif isinstance(node, ast.Call):
            target = _resolve(node.func, aliases)
            lineno = node.lineno

            if target in SUBPROCESS_CALL_TARGETS or target in OS_SHELL_CALL_TARGETS:
                token = _first_token(node)
                if token:
                    basename = Path(token).name
                    if basename in BLOCKED_SUBPROCESS_TOKENS:
                        findings.append(Finding(
                            rel_posix, lineno, "blocked-subprocess", f"{target}(...{basename}...)",
                        ))
                    elif basename in FFMPEG_TOKENS:
                        if skill_rel(rel_posix) not in FFMPEG_ALLOWED_FILES:
                            findings.append(Finding(
                                rel_posix, lineno, "ffmpeg-not-allowlisted",
                                f"{basename} invoked outside the 4 allowed scripts",
                            ))
                        for s in _string_constants(node):
                            if any(marker in s for marker in FFMPEG_NETWORK_MARKERS):
                                findings.append(Finding(
                                    rel_posix, lineno, "ffmpeg-network-arg", s,
                                ))

            elif target in {"os.environ.get", "os.getenv"}:
                if node.args:
                    first = node.args[0]
                    if isinstance(first, ast.Constant) and isinstance(first.value, str):
                        if any(m in first.value.upper() for m in ENV_CREDENTIAL_MARKERS):
                            findings.append(Finding(
                                rel_posix, lineno, "env-credential-read", f"{target}({first.value!r})",
                            ))

        elif isinstance(node, ast.Subscript):
            base = _resolve(node.value, aliases)
            if base == "os.environ":
                key_node = node.slice
                if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                    if any(m in key_node.value.upper() for m in ENV_CREDENTIAL_MARKERS):
                        findings.append(Finding(
                            rel_posix, node.lineno, "env-credential-read",
                            f"os.environ[{key_node.value!r}]",
                        ))

    if rel_posix not in SELF_EXEMPT_FILES and MCP_HOST_LITERAL in source:
        for i, line in enumerate(source.splitlines(), start=1):
            if MCP_HOST_LITERAL in line:
                findings.append(Finding(rel_posix, i, "mcp-literal-in-python", line))

    return findings


def check_shell_file(rel_posix: str, source: str) -> list[Finding]:
    findings = []
    for i, line in enumerate(source.splitlines(), start=1):
        if SH_NETWORK_RE.search(line):
            findings.append(Finding(rel_posix, i, "shell-network-client", line))
    return findings


def check_template_ts_file(rel_posix: str, source: str) -> list[Finding]:
    stripped = TS_COMMENT_RE.sub("", source)
    findings = []
    for i, line in enumerate(stripped.splitlines(), start=1):
        if TS_NETWORK_RE.search(line):
            findings.append(Finding(rel_posix, i, "template-network-call", line))
    return findings


def collect_findings(root: Path, allow_prefixes: list[str] | None = None) -> list[Finding]:
    allow_prefixes = allow_prefixes or []
    findings: list[Finding] = []
    for rel in list_files(root):
        if is_allowed(rel, allow_prefixes):
            continue
        rel_posix = rel.as_posix()
        suffix = Path(rel_posix).suffix

        if suffix == ".py":
            source = read_text(root / rel)
            if source is not None:
                findings.extend(check_python_file(rel_posix, source))
        elif suffix == ".sh":
            source = read_text(root / rel)
            if source is not None:
                findings.extend(check_shell_file(rel_posix, source))
        elif suffix in {".ts", ".tsx"} and skill_rel(rel_posix).startswith("template/"):
            source = read_text(root / rel)
            if source is not None:
                findings.extend(check_template_ts_file(rel_posix, source))

    return findings


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Enforce the network boundary: no script talks to the MCP gateway directly.")
    parser.add_argument("--root", default=".", help="Directory to scan (default: cwd)")
    parser.add_argument(
        "--allow", action="append", default=[],
        help="Path prefix (relative to --root) to exclude entirely; repeatable. "
             "Mirrors check_clean.py --allow, for the same reason: a test suite's own "
             "fixtures legitimately contain the literals these rules search for.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a human table.")
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        print(f"!! check_no_network.py: --root {args.root!r} is not a directory", file=sys.stderr)
        return 2

    # Same --allow contract as check_clean.py, by the same shared helper:
    # scripts/, template/, skills/, assets/, examples/, tests/ can never be exempted.
    bad_allow = forbidden_allow_prefix(args.allow)
    if bad_allow is not None:
        print(
            f"!! check_no_network.py: --allow {bad_allow!r} is forbidden "
            "(scripts/, template/, skills/, assets/, examples/, tests/ can never be exempted)",
            file=sys.stderr,
        )
        return 2

    try:
        all_files = list_files(root)
        findings = collect_findings(root, args.allow)
    except Exception as exc:  # noqa: BLE001 - top-level CLI boundary
        print(f"!! check_no_network.py: execution error: {exc}", file=sys.stderr)
        return 2

    counts: dict[str, int] = {}
    for f in findings:
        counts[f.rule] = counts.get(f.rule, 0) + 1

    # The "allowed: <dir> (N files skipped)" line is required always, from both
    # checkers. stderr keeps --json's stdout pure JSON for the tests that
    # json.loads(result.stdout) directly.
    allowed_counts = allowed_skip_counts(all_files, args.allow)
    for prefix, n in allowed_counts:
        print(f"allowed: {prefix} ({n} files skipped)", file=sys.stderr)

    if args.json:
        print(json.dumps({
            "ok": not findings,
            "counts": counts,
            "allowed": [{"dir": prefix, "files_skipped": n} for prefix, n in allowed_counts],
            "findings": [f.as_dict() for f in findings],
        }, indent=2))
    else:
        if counts:
            width = max(len(r) for r in counts)
            print(f"{'rule'.ljust(width)}  count")
            for rule in sorted(counts):
                print(f"{rule.ljust(width)}  {counts[rule]}")
            print()
            for f in findings:
                print(str(f))
        else:
            print("check_no_network: 0 findings")

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
