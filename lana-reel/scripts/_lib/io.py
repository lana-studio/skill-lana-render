"""scripts/_lib/io.py — small file/JSON helpers shared by every script.

Stdlib only (json, hashlib, pathlib, sys). No network.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

CHUNK_SIZE = 8 * 1024 * 1024  # 8 MiB — matches transfer.py's streaming chunk size


def read_json(path: Path | str) -> Any:
    """Read a JSON file. Raises FileNotFoundError / json.JSONDecodeError as-is;
    callers turn those into the script's own exit-2 / exit-1 messages so every
    script controls its own wording (see each script's docstring)."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path | str, data: Any, *, indent: int = 2, sort_keys: bool = False) -> None:
    """Write JSON, creating parent directories as needed. project.json and every
    lana/*.json file use indent=2, sort_keys=False so
    that hand-diffing a project across two runs is readable."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, sort_keys=sort_keys, ensure_ascii=False)
        f.write("\n")


def sha256_file(path: Path | str) -> str:
    """Streaming sha256 — never loads the whole file into memory (bundles/raw
    footage can be gigabytes)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def emit(args: dict, name: str, project_dir: Path | None = None) -> None:
    """The --emit convention: print ONLY the JSON of tool
    arguments to stdout (the agent reads this) and also persist it to
    <project>/lana-pkg/<name>.args.json. Human/progress messages never go
    through this function — they go to stderr via print(..., file=sys.stderr).
    """
    payload = json.dumps(args, indent=2, sort_keys=False, ensure_ascii=False)
    print(payload)
    if project_dir is not None:
        write_json(Path(project_dir) / "lana-pkg" / f"{name}.args.json", args)


def parse_tool_result(text: str) -> Any:
    """Tolerant parser for a persisted MCP tool result: the
    file save_result.py reads is normally the raw JSON `TextContent` Claude
    Code persisted under tool-results, but the agent's own `Write` fallback
    can wrap it in something else. If the text starts with '{' (after
    stripping whitespace) it's parsed directly; otherwise this scans for the
    first '{' and decodes a balanced object from there with
    `json.JSONDecoder().raw_decode`. Raises ValueError("not a JSON tool
    result") if neither works — callers turn that into exit 2.
    """
    stripped = text.lstrip()
    if stripped.startswith("{"):
        return json.loads(stripped)
    idx = text.find("{")
    if idx == -1:
        raise ValueError("not a JSON tool result")
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[idx:])
        return obj
    except json.JSONDecodeError as exc:
        raise ValueError("not a JSON tool result") from exc


def eprint(*values: Any, **kwargs: Any) -> None:
    """print() to stderr — the convention every script uses for human/progress
    messages so that --emit's stdout stays pure JSON."""
    print(*values, file=sys.stderr, **kwargs)


def fail(message: str, code: int = 1) -> None:
    """Print a `!!`-prefixed finding to stderr and exit with `code`. Never
    returns (raises SystemExit) — the -> None annotation is just conventional.
    Exit code convention every script in this family follows: 1 validation
    failed, 2 missing input file/project, 3 URL rejected (transfer.py only)."""
    for line in str(message).splitlines() or [""]:
        eprint(f"!! {line}")
    raise SystemExit(code)
