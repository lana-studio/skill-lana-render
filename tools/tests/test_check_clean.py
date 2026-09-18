"""Tests for tools/check_clean.py.

Every rule gets its own fixture, built fresh under tmp_path (never committed as
static dirty files — nothing here should break collection or ship a
fake-but-real-looking secret in the repo tree). Each test asserts the check
actually fails (exit 1) on the dirty fixture AND that the specific rule named
in check_clean.py is the one that fired — a check that can't fail is not
protection.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent.parent
CHECK_CLEAN = TOOLS_DIR / "check_clean.py"


def run_check(root: Path, *extra_args: str) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, str(CHECK_CLEAN), "--root", str(root), "--json", *extra_args],
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


# ---------------------------------------------------------------------------
# clean baseline: an empty root must pass
# ---------------------------------------------------------------------------

def test_clean_empty_root_passes(tmp_path):
    code, payload = run_check(tmp_path)
    assert code == 0
    assert payload["ok"] is True
    assert payload["findings"] == []


def test_clean_realistic_tree_passes(tmp_path):
    write(tmp_path, "README.md", "# reel-skill\n\nRecord thirty seconds on your phone.\n")
    write(tmp_path, "skills/reel/SKILL.md", "---\ndescription: mount a reel\n---\n\nDo the thing.\n")
    write(tmp_path, "scripts/lana/transfer.py", "import urllib.request\n")
    code, payload = run_check(tmp_path)
    assert code == 0, payload


# ---------------------------------------------------------------------------
# secret-token
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("secret", [
    "Authorization: Bearer abcdEFGH12345678901234567890",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.",
    "sk-abcdefghijklmnopqrstuvwx1234",
    "ghp_abcdefghijklmnopqrstuvwxyz0123456789",
    "AKIAABCDEFGHIJKLMNOP",
])
def test_secret_token_fixture_fails(tmp_path, secret):
    write(tmp_path, "leak.py", f"TOKEN = {secret!r}\n")
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "secret-token" in rules_fired(payload)


# ---------------------------------------------------------------------------
# signed-url
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("url", [
    "https://example.blob.core.windows.net/x?sig=abc123",
    "https://example.blob.core.windows.net/x?sv=2023-01-01",
    "https://s3.amazonaws.com/x?X-Amz-Signature=abc",
    "https://example.com/x?signature=abc&exp=123",
    "see .claude/projects/x/y/tool-results/mcp-lana-foo-123.txt",
])
def test_signed_url_fixture_fails(tmp_path, url):
    write(tmp_path, "notes.md", f"fetch from {url}\n")
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "signed-url" in rules_fired(payload)


# ---------------------------------------------------------------------------
# uuid
# ---------------------------------------------------------------------------

def test_uuid_fixture_fails(tmp_path):
    write(tmp_path, "project.json", '{"asset_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"}\n')
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "uuid" in rules_fired(payload)


def test_uuid_null_uuid_is_allowed(tmp_path):
    write(tmp_path, "project.json", '{"asset_id": "00000000-0000-4000-8000-000000000000"}\n')
    code, payload = run_check(tmp_path)
    assert code == 0
    assert "uuid" not in rules_fired(payload)


def test_uuid_under_tests_dir_is_exempt(tmp_path):
    write(tmp_path, "tests/fixtures/project.json", '{"asset_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"}\n')
    code, payload = run_check(tmp_path)
    assert code == 0
    assert "uuid" not in rules_fired(payload)


# ---------------------------------------------------------------------------
# forbidden-name
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("needle", [
    "MarcaPersonal", "Reto-Video", "this is the Reto season",
    "hablafu", "packsefectos", "read voz.md first", "music.json lives here",
    "Lana-MCP-contexto.md", "read AGENTS.md", "/Users/martinlengua/project",
    "@martincloudia", "ViewcciBackgroundSongs", "Referencias-Estilos",
    "jackclark", "theinformer", "stored in Keychain",
    "Claude Code-credentials", ".credentials.json",
])
def test_forbidden_name_fixture_fails(tmp_path, needle):
    write(tmp_path, "leak.md", f"See {needle} for details.\n")
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "forbidden-name" in rules_fired(payload)


# ---------------------------------------------------------------------------
# rpc-endpoint-in-code
# ---------------------------------------------------------------------------

def test_rpc_endpoint_literal_in_py_fails(tmp_path):
    write(tmp_path, "client.py", 'URL = "https://mcp.lanastudio.pe/mcp"\n')
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "rpc-endpoint-in-code" in rules_fired(payload)


def test_rpc_endpoint_jsonrpc_marker_in_py_fails(tmp_path):
    write(tmp_path, "client.py", 'path = "/mcp"\nbody = {"jsonrpc": "2.0"}\n')
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "rpc-endpoint-in-code" in rules_fired(payload)


def test_rpc_endpoint_allowed_in_markdown(tmp_path):
    write(tmp_path, "README.md", "claude mcp add --transport http lana https://mcp.lanastudio.pe/mcp\n")
    code, payload = run_check(tmp_path)
    assert code == 0
    assert "rpc-endpoint-in-code" not in rules_fired(payload)


# ---------------------------------------------------------------------------
# keychain-cli
# ---------------------------------------------------------------------------

def test_keychain_cli_fixture_fails(tmp_path):
    write(tmp_path, "lanarpc.py", 'subprocess.run(["security", "find-generic-password", "-s", "x"])\n')
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "keychain-cli" in rules_fired(payload)


# ---------------------------------------------------------------------------
# font-not-allowlisted
# ---------------------------------------------------------------------------

def test_font_outside_assets_fonts_fails(tmp_path):
    write(tmp_path, "template/public/Futura-Bold.ttf", "not a real font")
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "font-not-allowlisted" in rules_fired(payload)


def test_font_not_in_manifest_fails(tmp_path):
    write(tmp_path, "assets/fonts/Mystery.ttf", "not a real font")
    write(tmp_path, "assets/fonts/MANIFEST.json", "[]")
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "font-not-allowlisted" in rules_fired(payload)


def test_font_allowlisted_passes(tmp_path):
    write(tmp_path, "assets/fonts/Inter.ttf", "not a real font")
    write(tmp_path, "assets/fonts/OFL.txt", "SIL OPEN FONT LICENSE")
    write(tmp_path, "assets/fonts/MANIFEST.json", json.dumps([
        {"file": "Inter.ttf", "license": "OFL-1.1", "license_file": "OFL.txt"},
    ]))
    code, payload = run_check(tmp_path)
    assert code == 0, payload
    assert "font-not-allowlisted" not in rules_fired(payload)


# ---------------------------------------------------------------------------
# logo-or-brand-asset
# ---------------------------------------------------------------------------

def test_logo_dir_fails(tmp_path):
    write(tmp_path, "assets/logos/brand.svg", "<svg></svg>")
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "logo-or-brand-asset" in rules_fired(payload)


def test_brand_name_in_filename_fails(tmp_path):
    write(tmp_path, "assets/icons/youtube-icon.png", "not a real png")
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "logo-or-brand-asset" in rules_fired(payload)


# ---------------------------------------------------------------------------
# large-binary
# ---------------------------------------------------------------------------

def test_large_binary_outside_exempt_dirs_fails(tmp_path):
    path = write(tmp_path, "template/public/big-video.mp4")
    path.write_bytes(b"\x00" * (1024 * 1024 + 1))
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "large-binary" in rules_fired(payload)


def test_large_binary_in_first_reel_media_is_exempt_from_size_rule(tmp_path):
    path = write(tmp_path, "examples/first-reel/media/clip.mp4")
    path.write_bytes(b"\x00" * (1024 * 1024 + 1))
    write(tmp_path, "examples/first-reel/media/LICENSE", "CC0-1.0\n")
    code, payload = run_check(tmp_path)
    assert "large-binary" not in rules_fired(payload)


def test_large_font_in_exempt_dir_passes_size_rule(tmp_path):
    write(tmp_path, "assets/fonts/MANIFEST.json", json.dumps([
        {"file": "Huge.ttf", "license": "OFL-1.1", "license_file": "OFL.txt"},
    ]))
    write(tmp_path, "assets/fonts/OFL.txt", "SIL OPEN FONT LICENSE")
    path = tmp_path / "assets/fonts/Huge.ttf"
    path.write_bytes(b"\x00" * (2 * 1024 * 1024))
    code, payload = run_check(tmp_path)
    assert "large-binary" not in rules_fired(payload)


# ---------------------------------------------------------------------------
# media-without-license
# ---------------------------------------------------------------------------

def test_media_without_license_fails(tmp_path):
    path = write(tmp_path, "examples/first-reel/media/clip.mp4")
    path.write_bytes(b"\x00\x01\x02")
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "media-without-license" in rules_fired(payload)


def test_media_with_license_passes(tmp_path):
    path = write(tmp_path, "assets/sfx/glitch.wav")
    path.write_bytes(b"\x00\x01\x02")
    write(tmp_path, "assets/sfx/LICENSE", "CC0 1.0\n")
    code, payload = run_check(tmp_path)
    assert "media-without-license" not in rules_fired(payload)


# ---------------------------------------------------------------------------
# spanish-leak
# ---------------------------------------------------------------------------

def test_spanish_leak_in_skill_md_fails(tmp_path):
    write(tmp_path, "skills/reel/SKILL.md", (
        "---\ndescription: montar un reel\n---\n\n"
        "Esta es la regla que se usa para el montaje. La transcripción determina "
        "el texto que aparece en la pantalla, y para cada corte se revisa el audio.\n"
    ))
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "spanish-leak" in rules_fired(payload)


def test_spanish_leak_exempts_frontmatter(tmp_path):
    write(tmp_path, "skills/reel/SKILL.md", (
        "---\ndescription: montar un reel para que quitar los silencios funcione\n---\n\n"
        "Cut on speech regions. Never invent words the speaker did not say.\n"
    ))
    code, payload = run_check(tmp_path)
    assert code == 0, payload
    assert "spanish-leak" not in rules_fired(payload)


def test_spanish_leak_allow_file_exempts(tmp_path):
    write(tmp_path, "skills/reel/references/example.md", (
        "El ejemplo de código usa `for el in la_lista:` que no es prosa real, "
        "pero contiene los marcadores igual para la prueba.\n"
    ))
    code, payload = run_check(tmp_path)
    assert code == 1
    code2, payload2 = run_check(tmp_path, "--allow-file", "skills/reel/references/example.md")
    assert code2 == 0, payload2
    assert "spanish-leak" not in rules_fired(payload2)


# ---------------------------------------------------------------------------
# private-doc-ref
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ref", [
    "see docs/research/foo.md",
    "see docs/superpowers/plans/bar.md",
    "see docs/features/reel-skill-public/00-requirements.md",
    "lives at ~/projects/lana-studio/services",
])
def test_private_doc_ref_fixture_fails(tmp_path, ref):
    write(tmp_path, "README.md", f"Background: {ref}\n")
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "private-doc-ref" in rules_fired(payload)


@pytest.mark.parametrize("adr", ["ADR-0025", "ADR-0026", "ADR-0001", "ADR-9999"])
def test_private_doc_ref_adr_id_fixture_fails(tmp_path, adr):
    # A decision-record id is meaningless (and reveals monorepo-internal
    # numbering) outside the monorepo. Regex, not a fixed list — must catch an
    # ADR number invented tomorrow, not just the ones we know about today.
    write(tmp_path, "notes.md", f"This follows {adr} for the network boundary.\n")
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "private-doc-ref" in rules_fired(payload)


def test_private_doc_ref_adr_id_requires_word_boundary(tmp_path):
    # "ADR-00251" must not false-positive on "ADR-0025" as a bare substring —
    # the rule requires a 4-digit id with a boundary on both sides.
    write(tmp_path, "notes.md", "See ADR-00251-some-other-thing for context.\n")
    code, payload = run_check(tmp_path)
    assert "private-doc-ref" not in rules_fired(payload)


@pytest.mark.parametrize("codename", [
    "mcp-creative-library", "mcp-fonts-library", "mcp-gateway-mvp",
    "mcp-oauth-keycloak", "mcp-reels-hito1", "mcp-reels-hito2",
    "mcp-render-box-mvp", "mcp-render-by-subscription", "mcp-robustez",
    "dead-hook-stingers", "media-rejection-visible", "reel-skill-public",
    "clip-closure-p0",
])
def test_private_doc_ref_feature_codename_fixture_fails(tmp_path, codename):
    write(tmp_path, "notes.md", f"This builds on work from {codename}.\n")
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "private-doc-ref" in rules_fired(payload)


@pytest.mark.parametrize("role", [
    "lana-architect", "lana-reviewer", "lana-qa", "lana-devops",
    "lana-backend", "lana-frontend", "lana-alchemy", "lana-infra",
    "lana-ceo", "lana-monitor", "lana-clip-director", "/lana-loop",
    "Consejo de Sabios", "orquestador",
])
def test_private_doc_ref_internal_role_fixture_fails(tmp_path, role):
    write(tmp_path, "notes.md", f"Reviewed by {role} before merging.\n")
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "private-doc-ref" in rules_fired(payload)


def test_public_skill_name_is_not_flagged_as_internal_role(tmp_path):
    # lana-mcp-render is one of the two skills this repo publishes — it must
    # never be treated as an internal-role leak.
    write(tmp_path, "README.md", "Install both skills: reel and lana-mcp-render.\n")
    code, payload = run_check(tmp_path)
    assert "private-doc-ref" not in rules_fired(payload)


# ---------------------------------------------------------------------------
# private-doc-ref: pack document names (bare, no docs/ prefix) and
# decision/invariant codes gated on a same-line doc-name match
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("doc", [
    "00-requirements.md", "01-architecture.md", "05-acceptance-criteria.md",
    "06-review-checklist.md", "08-not-invented-yet.md",
])
def test_numbered_pack_doc_fixture_fails(tmp_path, doc):
    # Structural regex, not a list — must catch a numbered doc invented
    # tomorrow ("08-not-invented-yet.md" above), not just today's.
    write(tmp_path, "notes.ts", f"// see {doc} for the reasoning\n")
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "private-doc-ref" in rules_fired(payload)


@pytest.mark.parametrize("doc", [
    "behavior-invariants.md", "clean-check.md", "install-and-sync.md",
    "project-config.md", "scripts-io.md", "python-scripts.md",
    "remotion-template.md", "repo-hygiene-ci.md", "skill-docs-en.md",
    "publication-runbook.md", "translation-trace.md", "knowhow-triage.md",
    "published.md",
])
def test_named_pack_doc_fixture_fails(tmp_path, doc):
    write(tmp_path, "notes.ts", f"// see {doc} for the reasoning\n")
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "private-doc-ref" in rules_fired(payload)


def test_public_reference_doc_name_is_not_flagged_as_pack_doc(tmp_path):
    # lana-mcp-render/references/*.md are real public doc names that share
    # the same lowercase-kebab-case.md shape as the private contract docs
    # (that's exactly why NAMED_PACK_DOCS has to be a curated list instead of
    # a structural rule) — they must never be flagged.
    write(tmp_path, "notes.ts", "// see references/tools-mcp-v4.md and errors-limits-budget.md\n")
    code, payload = run_check(tmp_path)
    assert "private-doc-ref" not in rules_fired(payload)


def test_real_leak_shape_doc_name_and_decision_code_together(tmp_path):
    # The exact shape QA/the reviewer found live in template/src/.
    write(tmp_path, "assets.ts", (
        "// D16 (01-architecture.md, bug 9 — assets resolve via staticFile)\n"
        "export const ASSET_FILES = {};\n"
    ))
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "private-doc-ref" in rules_fired(payload)
    excerpts = " ".join(f["excerpt"] for f in payload["findings"] if f["rule"] == "private-doc-ref")
    assert "D16" in excerpts
    assert "01-architecture.md" in excerpts


@pytest.mark.parametrize("line", [
    "version 2.1 of the API, D16 elements wide, P2 priority",
    "T7 is a generic type parameter here",
    "the grid is C12 columns wide",
    "priority: P2",
    "R2 is the coefficient of determination",
    "floor B-01, room 204",
])
def test_bare_decision_code_without_doc_name_is_not_flagged(tmp_path, line):
    # This is the false positive the team lead warned about: D/P/R/G/I/B/C/F/T
    # followed by digits shows up constantly in ordinary code and prose
    # (dimensions, priorities, type params, stats, building floors) with no
    # relation to this project's decision taxonomy. Only flag it alongside an
    # actual pack-doc-name match on the same line — never on its own.
    write(tmp_path, "notes.ts", f"// {line}\n")
    code, payload = run_check(tmp_path)
    assert "private-doc-ref" not in rules_fired(payload)


def test_decision_code_mid_identifier_is_not_matched(tmp_path):
    # \b boundaries: "ID16" must not be read as (nothing) + "D16".
    write(tmp_path, "notes.ts", "// see ID16 in 01-architecture.md\n")
    code, payload = run_check(tmp_path)
    findings = [f for f in payload["findings"] if f["rule"] == "private-doc-ref"]
    # The doc name itself still fires (that's correct — it's still a leak);
    # what must NOT happen is a second, separate "D16" finding pulled out of
    # "ID16".
    assert code == 1
    assert not any(f["excerpt"].strip().startswith("D16") for f in findings)


# ---------------------------------------------------------------------------
# private-doc-ref: the internal pack's own section-reference notation
#
# CORRECTED, found live: this was first shipped ungated ("§ never appears in
# legitimate prose"), which missed that the public skill docs legitimately
# cite each other and themselves by section — that's normal navigation of a
# document the reader is holding, not a dead end. Gated exactly like
# DECISION_CODE_RE: fires only alongside a private (non-shipping) pack-doc
# name on the same line; a bare "§N" or a section cited next to a PUBLIC doc
# name (KNOWHOW, SKILL.md, a references/ doc) never fires on its own.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("line", [
    "per §3.7.1 of 01-architecture.md, ffmpeg is a requirement",
    "revert the filter from §3.5/R2, see scripts-io.md",
    "see §3.7 of clean-check.md for the closed escalations",
    "§8.1 of 05-acceptance-criteria.md covers the translation risk",
])
def test_section_ref_fixture_fails_alongside_a_private_doc_name(tmp_path, line):
    write(tmp_path, "notes.ts", f"// {line}\n")
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "private-doc-ref" in rules_fired(payload)


def test_bare_section_symbol_without_a_number_is_not_flagged(tmp_path):
    # "§" alone (e.g. a legal-style pilcrow reference with no digit after
    # it) isn't the internal citation shape this rule targets.
    write(tmp_path, "notes.md", "See § General Provisions below.\n")
    code, payload = run_check(tmp_path)
    assert "private-doc-ref" not in rules_fired(payload)


@pytest.mark.parametrize("path,line", [
    # The 5 real instances the reviewer found in the published skill docs —
    # each is a section citation with no private pack-doc name anywhere on
    # the line, so none of them should ever fire again.
    ("skills/reel/SKILL.md", "See `lana-mcp-render/SKILL.md` §1 for onboarding."),
    ("skills/reel/SKILL.md",
     "No Lottie: a prebuilt animation cannot land on the word being said (KNOWHOW §3)."),
    ("skills/reel/KNOWHOW.md", "An earlier entry covers this (§1.17)."),
    ("skills/reel/KNOWHOW.md", "See the framing note above (§1.2)."),
    ("skills/lana-mcp-render/references/errors-limits-quotas.md",
     "For quota errors, retry with backoff (see §3)."),
])
def test_section_ref_next_to_a_public_doc_is_never_flagged(tmp_path, path, line):
    write(tmp_path, path, f"{line}\n")
    code, payload = run_check(tmp_path)
    assert "private-doc-ref" not in rules_fired(payload)


def test_section_ref_alone_with_no_doc_name_at_all_is_not_flagged(tmp_path):
    # No doc named at all (a same-file cross-reference, e.g. "see §2 above")
    # is the most common shape of a legitimate internal link and must not
    # fire just because a pack-doc name happens to appear elsewhere in the
    # same file — the gate is per-line, not per-file: the doc-name line
    # still leaks on its own (that's correct), the section-only line must not.
    write(tmp_path, "notes.md", (
        "## Background\n\nSee 01-architecture.md for context.\n\n"
        "## Details\n\nAs covered above (see §2), this holds.\n"
    ))
    code, payload = run_check(tmp_path)
    findings = [f for f in payload["findings"] if f["rule"] == "private-doc-ref"]
    assert any("01-architecture.md" in f["excerpt"] for f in findings)
    assert not any("§" in f["excerpt"] for f in findings)


def test_issue_number_self_reference_is_never_flagged(tmp_path):
    # KNOWN LIMITATION (see the comment above CATALOG_BLOCKED_LITERAL in
    # check_clean.py): PR/issue numbers are deliberately NOT a sub-check.
    # This test pins the reason that matters most — the publication runbook
    # REQUIRES the v1 README to cite the public repo's own first issue as
    # "#1". If a future change ever adds issue-number matching, this is the
    # regression it would break on day one.
    write(tmp_path, "README.md", (
        "## Not in v1\n\nCodex CLI support is tracked in issue #1.\n"
    ))
    code, payload = run_check(tmp_path)
    assert "private-doc-ref" not in rules_fired(payload)


def test_pr_number_is_never_flagged(tmp_path):
    # Also deliberately not matched, for a different reason than issue
    # numbers: the public repo has none of its own at the v1 export, but
    # branch protection means it WILL accumulate its own PR history almost
    # immediately after launch (this checker keeps running in the public
    # repo's own CI forever, not just at v1) — a permanent "PR #\d+" rule
    # would start firing on a maintainer's own legitimate "fixed in PR #7"
    # within weeks. No static-text signal distinguishes "this repo's PR #N"
    # from "the monorepo's PR #N".
    write(tmp_path, "CHANGELOG.md", "## 1.5.1\n\n- Fixed subtitle timing (PR #7).\n")
    code, payload = run_check(tmp_path)
    assert "private-doc-ref" not in rules_fired(payload)


# ---------------------------------------------------------------------------
# catalog-blocked
# ---------------------------------------------------------------------------

def test_catalog_blocked_fails(tmp_path):
    write(tmp_path, "lana/caps.brand.json", '{"track": "x", "blocked": true}\n')
    code, payload = run_check(tmp_path)
    assert code == 1
    assert "catalog-blocked" in rules_fired(payload)


# ---------------------------------------------------------------------------
# --allow excludes a whole prefix from every rule
# ---------------------------------------------------------------------------

def test_allow_prefix_excludes_directory_from_every_rule(tmp_path):
    # Not "tests/fixtures" — "tests/" is one of the prefixes --allow must always
    # reject (see test_allow_forbidden_prefix_* below), so this uses an arbitrary
    # non-forbidden directory to exercise the general exclusion mechanism.
    write(tmp_path, "vendor/dirty.py", 'TOKEN = "AKIAABCDEFGHIJKLMNOP"\n')
    code, payload = run_check(tmp_path)
    assert code == 1
    code2, payload2 = run_check(tmp_path, "--allow", "vendor")
    assert code2 == 0, payload2
    assert payload2["findings"] == []


# ---------------------------------------------------------------------------
# M-01: the "allowed: <dir> (N files skipped)" report line, and the hard
# rejection of a forbidden --allow prefix (clean-check.md §0). Hallazgo:
# `--allow scripts` matched no rule and passed silently at exit 0, 0 findings
# — exactly what §0 forbids, and the report never showed what left scope even
# for the one --allow value the contract does permit (tools/tests).
# ---------------------------------------------------------------------------

def run_check_raw(root: Path, *extra_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECK_CLEAN), "--root", str(root), *extra_args],
        capture_output=True, text=True,
    )


def test_allowed_line_always_printed_on_stderr(tmp_path):
    write(tmp_path, "vendor/dirty.py", 'TOKEN = "AKIAABCDEFGHIJKLMNOP"\n')
    write(tmp_path, "vendor/other.py", "x = 1\n")
    result = run_check_raw(tmp_path, "--allow", "vendor", "--json")
    assert result.returncode == 0
    assert "allowed: vendor (2 files skipped)" in result.stderr
    # stdout must still be pure JSON (tests elsewhere do json.loads(stdout) directly)
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
    # never silently 0-findings/exit-0 — no JSON payload is even produced
    assert result.stdout.strip() == ""


def test_allow_forbidden_prefix_rejected_when_nested(tmp_path):
    result = run_check_raw(tmp_path, "--allow", "scripts/lana")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "forbidden" in result.stderr


def test_allow_forbidden_prefix_blocks_before_any_scan(tmp_path):
    # A real secret sits under the forbidden dir; the run must still refuse
    # the flag outright rather than "helpfully" using it to hide the secret.
    write(tmp_path, "scripts/dirty.py", 'TOKEN = "AKIAABCDEFGHIJKLMNOP"\n')
    result = run_check_raw(tmp_path, "--allow", "scripts", "--json")
    assert result.returncode == 2
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------------
# execution errors
# ---------------------------------------------------------------------------

def test_missing_root_is_execution_error(tmp_path):
    code, _ = run_check(tmp_path / "does-not-exist")
    assert code == 2


def test_malformed_manifest_is_reported_as_a_finding(tmp_path):
    # Malformed MANIFEST.json is scanned content, not a CLI misuse: it fails
    # loudly as a font-not-allowlisted finding (exit 1), not a crash (exit 2).
    write(tmp_path, "assets/fonts/MANIFEST.json", "{not json")
    code, payload = run_check(tmp_path)
    assert code == 1, payload
    assert "font-not-allowlisted" in rules_fired(payload)


# ---------------------------------------------------------------------------
# self-exemption (SELF_EXEMPT_FILES / SELF_EXEMPT_RULES) — the checker's own
# implementation files necessarily contain, as Python literals, the exact
# markers 6 literal-substring rules search for (see the SELF_EXEMPT_* comment
# in check_clean.py). That exemption is scoped to 3 exact paths and 6 named
# rules; these tests make sure it stays that narrow and can't quietly widen
# into a blind spot, or quietly hide a real secret.
# ---------------------------------------------------------------------------

def test_self_exempt_file_is_still_scanned_by_non_exempt_rules(tmp_path):
    # secret-token is NOT one of the 6 exempt rules. Drop a real-shaped secret
    # into a copy of the checker's own source (same relative path, so it hits
    # the SELF_EXEMPT_FILES branch) and confirm it still fires: the exemption
    # protects against self-matching the checker's *pattern definitions*, not
    # against an actual leaked secret sitting in that file.
    checker_source = CHECK_CLEAN.read_text(encoding="utf-8")
    checker_source += '\nLEAKED_TOKEN = "AKIAABCDEFGHIJKLMNOP"  # not part of the real tool\n'
    write(tmp_path, "tools/check_clean.py", checker_source)

    code, payload = run_check(tmp_path)
    assert code == 1
    assert "secret-token" in rules_fired(payload)

    # Meanwhile forbidden-name (one of the 6 exempt rules) must NOT fire for
    # this same file, even though the copied source legitimately contains
    # "MarcaPersonal" as a literal (it's the checker's own FORBIDDEN_NAMES list).
    forbidden_name_hits = [
        f for f in payload["findings"]
        if f["path"] == "tools/check_clean.py" and f["rule"] == "forbidden-name"
    ]
    assert forbidden_name_hits == []


def test_self_exempt_scope_is_pinned(tmp_path):
    # Import the real module (not a subprocess) so this test breaks the moment
    # someone adds a file or a rule to the exemption — widening it becomes a
    # conscious, reviewed change to this test, not a silent side effect of an
    # unrelated edit.
    sys.path.insert(0, str(TOOLS_DIR))
    import check_clean  # noqa: PLC0415 - deliberate late import, see comment above

    assert check_clean.SELF_EXEMPT_FILES == {"tools/check_clean.py"}
    assert check_clean.SELF_EXEMPT_RULES == {
        "signed-url",
        "forbidden-name",
        "keychain-cli",
        "rpc-endpoint-in-code",
        "private-doc-ref",
        "catalog-blocked",
    }
