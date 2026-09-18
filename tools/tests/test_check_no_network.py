"""Tests for tools/check_no_network.py — the network-boundary check.

Same discipline as test_check_clean.py: every rule gets a fixture built fresh
under tmp_path, and every fixture is asserted to actually make the check fail
with the specific rule it names.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent.parent
CHECK_NO_NETWORK = TOOLS_DIR / "check_no_network.py"


def run_check(root: Path, *extra_args: str) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, str(CHECK_NO_NETWORK), "--root", str(root), "--json", *extra_args],
        capture_output=True, text=True,
    )
    payload = json.loads(result.stdout) if result.stdout.strip() else {"ok": None, "findings": []}
    return result.returncode, payload


def rules_fired(payload: dict) -> set[str]:
    return {f["rule"] for f in payload["findings"]}


def write(root: Path, rel: str, content: str = "") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_clean_empty_root_passes(tmp_path):
    code, payload = run_check(tmp_path)
    assert code == 0
    assert payload["ok"] is True


def test_clean_transfer_script_passes(tmp_path):
    write(tmp_path, "scripts/lana/transfer.py", (
        "import argparse\n"
        "import hashlib\n"
        "import json\n"
        "import os\n"
        "import pathlib\n"
        "import sys\n"
        "import time\n"
        "import urllib.error\n"
        "import urllib.parse\n"
        "import urllib.request\n"
        "\n"
        "def put(path, url, headers):\n"
        "    req = urllib.request.Request(url, method='PUT')\n"
        "    return urllib.request.urlopen(req)\n"
    ))
    code, payload = run_check(tmp_path)
    assert code == 0, payload


# ---------------------------------------------------------------------------
# network-import-outside-transfer
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("module", [
    "urllib.request", "http.client", "socket", "requests", "httpx",
    "aiohttp", "websocket", "ftplib", "smtplib",
])
def test_network_import_outside_transfer_fails(tmp_path, module):
    write(tmp_path, "scripts/lana/caps.py", f"import {module}\n")
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "network-import-outside-transfer" in rules_fired(payload)


def test_network_import_in_transfer_is_allowed(tmp_path):
    write(tmp_path, "scripts/lana/transfer.py", "import urllib.request\n")
    code, payload = run_check(tmp_path)
    assert "network-import-outside-transfer" not in rules_fired(payload)


# ---------------------------------------------------------------------------
# transfer-import-not-allowed
# ---------------------------------------------------------------------------

def test_transfer_import_outside_allowlist_fails(tmp_path):
    write(tmp_path, "scripts/lana/transfer.py", "import requests\n")
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "transfer-import-not-allowed" in rules_fired(payload)


def test_transfer_import_from_allowlist_passes(tmp_path):
    write(tmp_path, "scripts/lana/transfer.py", (
        "import hashlib\nimport json\nimport os\nimport pathlib\n"
        "import sys\nimport time\nimport argparse\nimport ssl\n"
        "import urllib.request\nimport urllib.parse\nimport urllib.error\n"
    ))
    code, payload = run_check(tmp_path)
    assert "transfer-import-not-allowed" not in rules_fired(payload)


# ---------------------------------------------------------------------------
# blocked-subprocess
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cmd", [
    '["security", "find-generic-password"]',
    '["curl", "-o", "out.mp4", "https://example.com"]',
    '["wget", "https://example.com"]',
    '["ssh", "user@host"]',
])
def test_blocked_subprocess_fixture_fails(tmp_path, cmd):
    write(tmp_path, "scripts/lana/probe.py", f"import subprocess\nsubprocess.run({cmd})\n")
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "blocked-subprocess" in rules_fired(payload)


def test_os_system_blocked_token_fails(tmp_path):
    write(tmp_path, "scripts/lana/probe.py", 'import os\nos.system("curl https://example.com")\n')
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "blocked-subprocess" in rules_fired(payload)


def test_allowed_subprocess_tokens_pass(tmp_path):
    write(tmp_path, "scripts/reel/build.py", (
        "import subprocess\n"
        "subprocess.run(['git', 'rev-parse', 'HEAD'])\n"
        "subprocess.run(['npm', 'ci'])\n"
        "subprocess.run(['node', '-v'])\n"
    ))
    code, payload = run_check(tmp_path)
    assert "blocked-subprocess" not in rules_fired(payload)


# ---------------------------------------------------------------------------
# ffmpeg-not-allowlisted
# ---------------------------------------------------------------------------

def test_ffmpeg_outside_allowed_files_fails(tmp_path):
    write(tmp_path, "scripts/reel/build.py", (
        "import subprocess\n"
        "subprocess.run(['ffmpeg', '-i', 'in.mov', 'out.mp4'])\n"
    ))
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "ffmpeg-not-allowlisted" in rules_fired(payload)


def test_ffprobe_outside_allowed_files_fails(tmp_path):
    write(tmp_path, "scripts/reel/takes.py", (
        "import subprocess\n"
        "subprocess.run(['ffprobe', '-i', 'in.mov'])\n"
    ))
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "ffmpeg-not-allowlisted" in rules_fired(payload)


@pytest.mark.parametrize("allowed_file", [
    "scripts/reel/probe_source.py",
    "scripts/lana/prep_upload.py",
    "scripts/lana/verify_output.py",
    "lana-reel/scripts/reel/probe_source.py",
])
def test_ffmpeg_in_allowed_files_passes(tmp_path, allowed_file):
    write(tmp_path, allowed_file, (
        "import subprocess\n"
        "subprocess.run(['ffmpeg', '-ss', '1', '-i', 'in.mov', '-frames:v', '1', 'out.jpg'])\n"
    ))
    code, payload = run_check(tmp_path)
    assert "ffmpeg-not-allowlisted" not in rules_fired(payload)


# ---------------------------------------------------------------------------
# ffmpeg-network-arg
# ---------------------------------------------------------------------------

def test_ffmpeg_receiving_a_url_fails(tmp_path):
    write(tmp_path, "scripts/reel/probe_source.py", (
        "import subprocess\n"
        "subprocess.run(['ffmpeg', '-i', 'https://example.com/clip.mov', 'out.mp4'])\n"
    ))
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "ffmpeg-network-arg" in rules_fired(payload)


def test_ffmpeg_local_file_args_pass(tmp_path):
    write(tmp_path, "scripts/reel/probe_source.py", (
        "import subprocess\n"
        "subprocess.run(['ffmpeg', '-ss', '1', '-i', 'raw/clip.mov', '-frames:v', '1', 'out.jpg'])\n"
    ))
    code, payload = run_check(tmp_path)
    assert "ffmpeg-network-arg" not in rules_fired(payload)


# ---------------------------------------------------------------------------
# mcp-literal-in-python
# ---------------------------------------------------------------------------

def test_mcp_literal_in_python_fails(tmp_path):
    write(tmp_path, "scripts/lana/caps.py", 'HOST = "mcp.lanastudio.pe"\n')
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "mcp-literal-in-python" in rules_fired(payload)


def test_mcp_literal_in_transfer_py_also_fails(tmp_path):
    # The literal must not appear even in transfer.py itself — it only ever
    # handles URLs handed to it as arguments.
    write(tmp_path, "scripts/lana/transfer.py", 'HOST = "mcp.lanastudio.pe"\n')
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "mcp-literal-in-python" in rules_fired(payload)


# ---------------------------------------------------------------------------
# env-credential-read
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("snippet", [
    'os.environ["LANA_TOKEN"]',
    'os.environ.get("API_SECRET")',
    'os.getenv("DB_PASSWORD")',
    'os.environ["MCP_CREDENTIAL"]',
])
def test_env_credential_read_fails(tmp_path, snippet):
    write(tmp_path, "scripts/lana/caps.py", f"import os\nvalue = {snippet}\n")
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "env-credential-read" in rules_fired(payload)


def test_env_non_credential_read_passes(tmp_path):
    write(tmp_path, "scripts/lana/caps.py", 'import os\nproj = os.environ.get("REEL_PROJECT")\n')
    code, payload = run_check(tmp_path)
    assert "env-credential-read" not in rules_fired(payload)


# ---------------------------------------------------------------------------
# shell-network-client
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("line", [
    "curl -o out.mp4 https://example.com",
    "wget https://example.com",
    'security find-generic-password -s "x"',
])
def test_shell_network_client_fails(tmp_path, line):
    write(tmp_path, "install.sh", f"#!/bin/sh\n{line}\n")
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "shell-network-client" in rules_fired(payload)


def test_clean_shell_script_passes(tmp_path):
    write(tmp_path, "install.sh", "#!/bin/sh\nnpm ci\n")
    code, payload = run_check(tmp_path)
    assert "shell-network-client" not in rules_fired(payload)


# ---------------------------------------------------------------------------
# template-network-call
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("snippet", [
    "fetch('https://example.com')",
    "new XMLHttpRequest()",
    "const url = 'https://example.com/font.woff2';",
])
def test_template_network_call_fails(tmp_path, snippet):
    write(tmp_path, "template/src/Fonts.tsx", f"export const x = () => {{ {snippet} }};\n")
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "template-network-call" in rules_fired(payload)


def test_template_network_call_in_comment_is_ignored(tmp_path):
    write(tmp_path, "template/src/Fonts.tsx", (
        "// Google Fonts load in the box via @remotion/google-fonts, not fetch('https://...')\n"
        "export const x = 1;\n"
    ))
    code, payload = run_check(tmp_path)
    assert "template-network-call" not in rules_fired(payload)


def test_template_network_call_outside_template_dir_is_out_of_scope(tmp_path):
    write(tmp_path, "examples/first-reel/notes.tsx", "fetch('https://example.com')\n")
    code, payload = run_check(tmp_path)
    assert "template-network-call" not in rules_fired(payload)


# ---------------------------------------------------------------------------
# --allow excludes a whole prefix
# ---------------------------------------------------------------------------

def test_allow_prefix_excludes_directory(tmp_path):
    write(tmp_path, "tools/tests/fixtures/dirty.py", "import requests\n")
    code, payload = run_check(tmp_path)
    assert code == 1
    code2, payload2 = run_check(tmp_path, "--allow", "tools/tests")
    assert code2 == 0, payload2


# ---------------------------------------------------------------------------
# M-01: the "allowed: <dir> (N files skipped)" report line, and the hard
# rejection of a forbidden --allow prefix. Same contract as check_clean.py's
# equivalent tests, via the same tools/_shared.py helpers — mirrored here
# because clean-check.md §0 applies to this checker too, by the same flag.
# ---------------------------------------------------------------------------

def run_check_raw(root: Path, *extra_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECK_NO_NETWORK), "--root", str(root), *extra_args],
        capture_output=True, text=True,
    )


def test_allowed_line_always_printed_on_stderr(tmp_path):
    write(tmp_path, "vendor/dirty.py", "import requests\n")
    write(tmp_path, "vendor/other.py", "x = 1\n")
    result = run_check_raw(tmp_path, "--allow", "vendor", "--json")
    assert result.returncode == 0
    assert "allowed: vendor (2 files skipped)" in result.stderr
    payload = json.loads(result.stdout)
    assert payload["allowed"] == [{"dir": "vendor", "files_skipped": 2}]


def test_allowed_line_omitted_with_no_allow_flag(tmp_path):
    write(tmp_path, "README.md", "clean\n")
    result = run_check_raw(tmp_path, "--json")
    assert result.returncode == 0
    assert "allowed:" not in result.stderr
    payload = json.loads(result.stdout)
    assert payload["allowed"] == []


@pytest.mark.parametrize("forbidden", ["scripts", "template", "skills", "assets", "examples", "tests"])
def test_allow_forbidden_prefix_rejected(tmp_path, forbidden):
    result = run_check_raw(tmp_path, "--allow", forbidden)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "forbidden" in result.stderr
    assert forbidden in result.stderr
    assert result.stdout.strip() == ""


def test_allow_forbidden_prefix_blocks_before_any_scan(tmp_path):
    write(tmp_path, "scripts/dirty.py", "import requests\n")
    result = run_check_raw(tmp_path, "--allow", "scripts", "--json")
    assert result.returncode == 2
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------------
# syntax errors and execution errors
# ---------------------------------------------------------------------------

def test_syntax_error_is_reported_as_a_finding(tmp_path):
    write(tmp_path, "scripts/lana/broken.py", "def f(:\n    pass\n")
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "syntax-error" in rules_fired(payload)


def test_missing_root_is_execution_error(tmp_path):
    code, _ = run_check(tmp_path / "does-not-exist")
    assert code == 2


# ---------------------------------------------------------------------------
# self-exemption — same design as check_clean.py's SELF_EXEMPT_FILES: this
# checker's own source necessarily contains MCP_HOST_LITERAL as a Python
# string literal. Mirrors test_check_clean.py's two tests so the same risk
# (a rule silently widening its blind spot) is covered on this side too.
# ---------------------------------------------------------------------------

def test_self_exempt_file_is_still_scanned_by_non_exempt_rules(tmp_path):
    # mcp-literal-in-python is the ONLY rule exempted for these 3 files; a real
    # network import dropped into a copy of the checker's own source must
    # still fire network-import-outside-transfer.
    checker_source = CHECK_NO_NETWORK.read_text(encoding="utf-8")
    checker_source += "\nimport requests  # not part of the real tool\n"
    write(tmp_path, "tools/check_no_network.py", checker_source)

    code, payload = run_check(tmp_path)
    assert code == 1
    assert "network-import-outside-transfer" in rules_fired(payload)

    # Meanwhile mcp-literal-in-python must NOT fire for this same file, even
    # though the copied source legitimately contains MCP_HOST_LITERAL as a
    # Python string literal (the value the rule searches for).
    mcp_literal_hits = [
        f for f in payload["findings"]
        if f["path"] == "tools/check_no_network.py" and f["rule"] == "mcp-literal-in-python"
    ]
    assert mcp_literal_hits == []


def test_self_exempt_scope_is_pinned(tmp_path):
    sys.path.insert(0, str(TOOLS_DIR))
    import check_no_network  # noqa: PLC0415 - deliberate late import, see comment above

    assert check_no_network.SELF_EXEMPT_FILES == {
        "tools/check_clean.py",
        "tools/check_no_network.py",
    }
