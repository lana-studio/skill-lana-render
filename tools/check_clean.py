#!/usr/bin/env python3
"""tools/check_clean.py — fail loudly on anything that must not reach a public repo.

Scans every versioned file under --root for content and assets that must never
reach the public repo: secrets, signed URLs, real UUIDs, private/internal names,
raw MCP JSON-RPC endpoints, credential-store CLI calls, unlicensed fonts, brand
logos, oversized or unlicensed binaries, Spanish-language leaks, references to
internal planning documents, decision-record identifiers, feature codenames,
internal team/process roles, and the "blocked" catalog marker.

Runs (1) by hand before the first push, (2) in CI on every push/PR, (3) as part
of this project's own internal pre-publish review.

Exit 0 = clean. Exit 1 = findings printed as `path:line: rule: excerpt`.
Exit 2 = execution error (bad --root, unreadable MANIFEST.json, etc).

Only stdlib.
"""
from __future__ import annotations

import argparse
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
)

NULL_UUID = "00000000-0000-4000-8000-000000000000"

UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}"
)

SECRET_TOKEN_RE = re.compile(
    r"Bearer\s+[A-Za-z0-9._-]{20,}"
    r"|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\."
    r"|sk-[A-Za-z0-9]{20,}"
    r"|ghp_[A-Za-z0-9]{30,}"
    r"|AKIA[0-9A-Z]{16}"
)

FORBIDDEN_NAMES = [
    "MarcaPersonal",
    "Reto-Video",
    "Reto ",
    "hablafu",
    "packsefectos",
    "voz.md",
    "music.json",
    "Lana-MCP-contexto",
    "AGENTS.md",
    "martinlengua",
    "@martincloudia",
    "ViewcciBackgroundSongs",
    "Referencias-Estilos",
    "jackclark",
    "theinformer",
    "Keychain",
    "Claude Code-credentials",
    ".credentials.json",
]

KEYCHAIN_CLI_MARKERS = [
    "security find-generic-password",
    "security find-internet-password",
    "find-generic-password",
    "find-internet-password",
]

RPC_ENDPOINT_SCOPE_EXT = {".py", ".ts", ".tsx", ".js", ".sh"}
RPC_LITERAL = "mcp.lanastudio.pe/mcp"

LOGO_BRAND_NAMES = [
    "anthropic", "claude", "openai", "google", "gmail", "youtube", "tiktok",
    "instagram", "facebook", "nvidia", "huggingface", "metricool", "gemini",
]

LARGE_BINARY_LIMIT = 1024 * 1024  # 1 MiB
LARGE_BINARY_EXEMPT_PREFIXES = ("assets/fonts/", "examples/first-reel/media/")

MEDIA_EXTS = {".mp4", ".mov", ".wav", ".mp3", ".png", ".jpg", ".webp"}
MEDIA_LICENSE_SCOPE_PREFIXES = ("assets/", "examples/")

FONT_EXTS = {".ttf", ".otf", ".woff", ".woff2"}
FONT_ALLOWED_DIR = "assets/fonts/"

SPANISH_MARKERS = [" el ", " la ", " que ", " para ", "ción ", "¿", "¡"]
SPANISH_LEAK_FILENAMES = {"SKILL.md", "KNOWHOW.md", "README.md"}

PRIVATE_DOC_REFS = [
    "docs/research/",
    "docs/superpowers/",
    "docs/features/",
    "~/projects/lana-studio",
]

# private-doc-ref also catches references that don't sit under a docs/ prefix but
# are just as internal-only: a decision-record id, a monorepo feature codename, or
# an internal team/process role. All three are "where this was decided" pointers
# that mean nothing outside the monorepo and, in the case of role names, describe
# an internal multi-agent workflow that shouldn't be visible in a product repo.
ADR_ID_RE = re.compile(r"\bADR-\d{4}\b")

# Known monorepo feature codenames: one per internal feature planning folder,
# plus a few discussed but never given their own folder (e.g. a parked feature
# referenced only in another feature's research notes). Necessarily incomplete
# for codenames not yet invented; ADR_ID_RE above is the future-proof half of
# this check, this list is the known-today half.
FEATURE_CODENAMES = [
    "mcp-creative-library",
    "mcp-fonts-library",
    "mcp-gateway-mvp",
    "mcp-oauth-keycloak",
    "mcp-reels-hito1",
    "mcp-reels-hito2",
    "mcp-render-box-mvp",
    "mcp-render-by-subscription",
    "mcp-robustez",
    "dead-hook-stingers",
    "media-rejection-visible",
    "reel-skill-public",
    "clip-closure-p0",
]

# Internal multi-agent workflow roles that run this project's engineering process
# inside Claude Code, plus a couple of process labels. None of these name a
# shipped service or skill — the public MCP render skill is deliberately not on
# this list; only internal, process-only names are.
INTERNAL_ROLE_NAMES = [
    "lana-architect",
    "lana-reviewer",
    "lana-qa",
    "lana-devops",
    "lana-backend",
    "lana-frontend",
    "lana-alchemy",
    "lana-infra",
    "lana-ceo",
    "lana-monitor",
    "lana-clip-director",
    "/lana-loop",
    "consejo de sabios",
    "orquestador",
]

# Third sub-category, found live: a bare reference to one of the internal
# planning pack's own document names, with no docs/... prefix in front of it
# (so PRIVATE_DOC_REFS above never saw it) — a code comment citing a doc by
# its filename alone instead of the full path. Same dead end for an external
# reader as an ADR id.
#
# Numbered top-level pack docs share one structural shape that no legitimate
# public doc name uses — a public skill's own reference docs are SKILL.md,
# KNOWHOW.md, README.md, or references/<kebab-case>.md, never a two-digit
# number prefix. This is the "detect the structure, not a list" half: it
# catches a numbered doc invented tomorrow, not just today's.
PACK_DOC_NUMBERED_RE = re.compile(r"\b\d{2}-[a-z][a-z0-9-]{2,50}\.md\b")

# The pack's other documents (02-adrs/, 03-contracts/, 04-implementation/,
# 07-delivery/) don't carry a number, and their shape — lowercase-kebab-case.md
# — is genuinely indistinguishable from a legitimate public skill reference
# doc (e.g. lana-mcp-render/references/tools-mcp-v4.md is real and public).
# No structural rule can tell them apart; this is the curated "known-today"
# list, same role FEATURE_CODENAMES plays for ADR_ID_RE.
NAMED_PACK_DOCS = [
    "behavior-invariants.md",
    "clean-check.md",
    "install-and-sync.md",
    "project-config.md",
    "scripts-io.md",
    "python-scripts.md",
    "remotion-template.md",
    "repo-hygiene-ci.md",
    "skill-docs-en.md",
    "publication-runbook.md",
    "translation-trace.md",
    "knowhow-triage.md",
    "published.md",
]

# Decision / invariant / gap codes from the pack's own taxonomy (D = decision,
# P = product question, R = requirement/risk, G = gap, I = invariant,
# B = blocker, C = criterion, F = failure point, T = test case; optionally
# hyphenated). Deliberately NOT matched on its own: a bare short code letter
# plus digits is common in unrelated code (priority levels, test ids, type
# params, building floors) and would be noise, not protection — flagging a
# check nobody can trust is worse than missing an isolated code with no other
# context. It only fires on a line that ALSO matches PACK_DOC_NUMBERED_RE or
# NAMED_PACK_DOCS — every real instance found so far paired the code with a
# doc-name citation on the same line; the doc-name match is the strong
# signal, the code match just sharpens the excerpt.
DECISION_CODE_RE = re.compile(r"\b[DPRGIBCFT]-?\d{1,3}\b")

# Fourth sub-category: the section-symbol notation ("§3.7.1", "per §3.7") the
# internal pack cites itself with everywhere, in requirements/architecture/
# ADRs alike.
#
# FOUND LIVE, CORRECTED: this was first shipped ungated, on the claim that
# "§" never appears in legitimate prose for any other reason. That's true of
# the *symbol* but wrong about the *practice* — the public skill docs
# (SKILL.md, KNOWHOW.md, references/*.md) cite each other and themselves by
# section too, and that's exactly what they should do: it's a reader
# navigating a document they have in hand, not a dead end. Five real
# instances were flagged: "(KNOWHOW §3)" and "lana-mcp-render/SKILL.md §1"
# inside skills/reel/SKILL.md, "(§1.17)"/"(§1.2)" inside skills/reel/
# KNOWHOW.md citing its own earlier sections, "(see §3)" inside a
# lana-mcp-render reference doc.
#
# The distinction that actually matters, per the same principle as
# DECISION_CODE_RE: the section number was never the citation, the DOCUMENT
# is — "§" is a detail of *which* document, not evidence on its own. So this
# is gated exactly like DECISION_CODE_RE, on the same line matching
# PACK_DOC_NUMBERED_RE or NAMED_PACK_DOCS (a private, non-shipping doc name):
# "§3.7.1 of 01-architecture.md" fires (that pack doc name is already a leak
# on its own; the section number just sharpens the excerpt). A bare "§3" or
# "(KNOWHOW §3)" with no private doc name anywhere on the line does not,
# because the reader can always follow it — either it's not naming a doc at
# all (an internal same-file cross-reference) or the doc it names is one
# they're already holding.
SECTION_REF_RE = re.compile(r"§\s?\d")

# KNOWN LIMITATION, considered and deliberately NOT implemented — read this
# before proposing "PR #\d+" or "issue #\d+" as a fifth sub-check.
#
# A monorepo PR/issue number ("fixed in PR #50") is exactly the same class of
# dead-end reference as an ADR id or a decision code, and it does leak in
# practice (the monorepo's own history is full of them). The blocker isn't
# detecting the shape — it's that this checker ships WITH the public repo and
# keeps running in ITS OWN CI on every future push/PR (check.yml, `on: [push,
# pull_request]`), not just once at the v1 export. Two numbers were
# considered:
#   - "issue #N": rejected outright — the publication runbook REQUIRES the
#     v1 README to cite the public repo's own first issue as "#1" ("Codex
#     CLI support (not in v1)"). A rule here would fire on our own mandated
#     text on day one.
#   - "PR #N" alone: looked safer at first — the public repo has zero PR
#     history of its own at the v1 export, so any "PR #N" in that snapshot
#     is unambiguous. But branch protection requires every future change
#     (including a one-line fix) to go through a numbered PR, so the repo
#     WILL accumulate its own PR numbers almost immediately after launch. A
#     permanent, ungated rule would then start firing on a maintainer's own
#     legitimate "fixed in PR #7" a few weeks in — the exact "check nobody
#     trusts, gets ignored" failure mode this file exists to avoid. There is
#     no static-text signal that distinguishes "our repo's own PR #N" from
#     "the monorepo's PR #N": both are just a number.
#
# Net: unlike ADR ids (the monorepo's numbering, never the public repo's) or
# section refs (a citation style with no legitimate ordinary use), a PR/issue
# number is structurally ambiguous about WHICH repo it belongs to, and that
# ambiguity doesn't resolve with more context — it gets worse over the
# public repo's own lifetime. If this repo's real PR volume turns out to
# stay near zero for a long stretch after launch, a time- or count-bounded
# version of this check might become viable; it isn't today.
CATALOG_BLOCKED_LITERAL = '"blocked": true'

# check_clean.py necessarily contains, as Python string literals, the exact
# markers these six rules search for (the forbidden-name list, the rpc-endpoint
# literal, the private-doc-ref path prefixes / feature-codename / internal-role
# lists, ...). ADR_ID_RE is the one exception that needs no exemption at all —
# it's a regex pattern (`\bADR-\d{4}\b`), not a literal ADR id, so it never
# matches itself. Scanning the rest against their own literal-substring rules
# is a self-reference paradox, not a real leak: this file is hygiene tooling
# that never ships to ~/.claude/skills/ and never touches private material.
#
# The exemption is scoped as tight as the evidence supports, not "the tools/
# directory" or "every hygiene script": tools/check_no_network.py and
# tools/_shared.py do NOT define any of these six rules' pattern constants, so
# with SELF_EXEMPT_RULES emptied and every file back in scope, only
# tools/check_clean.py itself ever fires (verified: emptying SELF_EXEMPT_RULES
# and re-running against the whole tree produces findings on this file alone).
# A private-doc-ref-style leak in check_no_network.py's or _shared.py's own
# prose is a real leak and stays fully scanned. check_no_network.py has its own
# separate, narrower self-exemption for its own mcp-literal-in-python rule —
# see SELF_EXEMPT_FILES there.
#
# Flagged for review in the role's report; not a general --ignore.
SELF_EXEMPT_FILES = {"tools/check_clean.py"}
SELF_EXEMPT_RULES = {
    rule_name for rule_name in (
        "signed-url", "forbidden-name", "keychain-cli",
        "rpc-endpoint-in-code", "private-doc-ref", "catalog-blocked",
    )
}


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


def _scan_lines_for_regex(rel_posix: str, lines: list[str], rule: str, pattern: re.Pattern) -> list[Finding]:
    out = []
    for i, line in enumerate(lines, start=1):
        for m in pattern.finditer(line):
            out.append(Finding(rel_posix, i, rule, line[max(0, m.start() - 20): m.end() + 20]))
    return out


def rule_secret_token(rel_posix: str, lines: list[str]) -> list[Finding]:
    return _scan_lines_for_regex(rel_posix, lines, "secret-token", SECRET_TOKEN_RE)


def rule_signed_url(rel_posix: str, lines: list[str]) -> list[Finding]:
    out = []
    for i, line in enumerate(lines, start=1):
        hit = (
            "sig=" in line
            or "sv=20" in line
            or "X-Amz-Signature=" in line
            or ("signature=" in line and "exp=" in line)
            or "/tool-results/" in line
        )
        if hit:
            out.append(Finding(rel_posix, i, "signed-url", line))
    return out


def rule_uuid(rel_posix: str, lines: list[str]) -> list[Finding]:
    if rel_posix.startswith("tests/") or "/tests/" in rel_posix:
        return []
    out = []
    for i, line in enumerate(lines, start=1):
        for m in UUID_RE.finditer(line):
            if m.group(0).lower() == NULL_UUID:
                continue
            out.append(Finding(rel_posix, i, "uuid", line[max(0, m.start() - 10): m.end() + 10]))
    return out


def rule_forbidden_name(rel_posix: str, lines: list[str]) -> list[Finding]:
    out = []
    for i, line in enumerate(lines, start=1):
        lower = line.lower()
        for name in FORBIDDEN_NAMES:
            if name.lower() in lower:
                out.append(Finding(rel_posix, i, "forbidden-name", line))
    return out


def rule_rpc_endpoint_in_code(rel_posix: str, lines: list[str]) -> list[Finding]:
    ext = Path(rel_posix).suffix
    if ext not in RPC_ENDPOINT_SCOPE_EXT:
        return []
    out = []
    for i, line in enumerate(lines, start=1):
        if RPC_LITERAL in line:
            out.append(Finding(rel_posix, i, "rpc-endpoint-in-code", line))

    # "/mcp" + jsonrpc is a file-scoped combination (a client typically posts to
    # the path in one place and builds the jsonrpc envelope in another), not
    # necessarily on the same line.
    has_mcp_path = any('"/mcp"' in line for line in lines)
    has_jsonrpc = any("jsonrpc" in line.lower() for line in lines)
    if has_mcp_path and has_jsonrpc:
        first_line = next(i for i, line in enumerate(lines, start=1) if '"/mcp"' in line)
        out.append(Finding(rel_posix, first_line, "rpc-endpoint-in-code", lines[first_line - 1]))
    return out


def rule_keychain_cli(rel_posix: str, lines: list[str]) -> list[Finding]:
    out = []
    for i, line in enumerate(lines, start=1):
        for marker in KEYCHAIN_CLI_MARKERS:
            if marker in line:
                out.append(Finding(rel_posix, i, "keychain-cli", line))
    return out


def rule_spanish_leak(rel_posix: str, text: str, allow_files: set[str]) -> list[Finding]:
    name = Path(rel_posix).name
    in_scope = name in SPANISH_LEAK_FILENAMES or (
        "references/" in rel_posix and rel_posix.endswith(".md")
    )
    if not in_scope or rel_posix in allow_files:
        return []

    body = text
    if name == "SKILL.md" and text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            body = text[end + 4:]

    lines = body.splitlines()
    hits: list[tuple[int, str]] = []
    for i, line in enumerate(lines, start=1):
        for marker in SPANISH_MARKERS:
            if marker in line:
                hits.append((i, line))
    if len(hits) < 3:
        return []
    return [Finding(rel_posix, i, "spanish-leak", line) for i, line in hits]


def rule_private_doc_ref(rel_posix: str, lines: list[str]) -> list[Finding]:
    out = []
    for i, line in enumerate(lines, start=1):
        for ref in PRIVATE_DOC_REFS:
            if ref in line:
                out.append(Finding(rel_posix, i, "private-doc-ref", line))
        for m in ADR_ID_RE.finditer(line):
            out.append(Finding(rel_posix, i, "private-doc-ref", line[max(0, m.start() - 20): m.end() + 20]))
        lower = line.lower()
        for name in FEATURE_CODENAMES:
            if name.lower() in lower:
                out.append(Finding(rel_posix, i, "private-doc-ref", line))
        for name in INTERNAL_ROLE_NAMES:
            if name.lower() in lower:
                out.append(Finding(rel_posix, i, "private-doc-ref", line))

        has_pack_doc = bool(PACK_DOC_NUMBERED_RE.search(line)) or any(
            name in lower for name in NAMED_PACK_DOCS
        )
        for m in PACK_DOC_NUMBERED_RE.finditer(line):
            out.append(Finding(rel_posix, i, "private-doc-ref", line[max(0, m.start() - 20): m.end() + 20]))
        for name in NAMED_PACK_DOCS:
            if name in lower:
                out.append(Finding(rel_posix, i, "private-doc-ref", line))
        if has_pack_doc:
            for m in DECISION_CODE_RE.finditer(line):
                out.append(Finding(rel_posix, i, "private-doc-ref", line[max(0, m.start() - 20): m.end() + 20]))
            for m in SECTION_REF_RE.finditer(line):
                out.append(Finding(rel_posix, i, "private-doc-ref", line[max(0, m.start() - 10): m.end() + 20]))
    return out


def rule_catalog_blocked(rel_posix: str, lines: list[str]) -> list[Finding]:
    out = []
    for i, line in enumerate(lines, start=1):
        if CATALOG_BLOCKED_LITERAL in line:
            out.append(Finding(rel_posix, i, "catalog-blocked", line))
    return out


TEXT_RULES = [
    rule_secret_token,
    rule_signed_url,
    rule_uuid,
    rule_forbidden_name,
    rule_rpc_endpoint_in_code,
    rule_keychain_cli,
    rule_private_doc_ref,
    rule_catalog_blocked,
]


def _load_font_manifest(root: Path) -> tuple[dict, Finding | None]:
    manifest_path = root / "assets" / "fonts" / "MANIFEST.json"
    if not manifest_path.is_file():
        return {}, None
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, Finding(
            "assets/fonts/MANIFEST.json", 1, "font-not-allowlisted",
            f"MANIFEST.json is not valid JSON: {exc}",
        )
    by_file = {}
    for entry in data if isinstance(data, list) else []:
        if isinstance(entry, dict) and "file" in entry:
            by_file[entry["file"]] = entry
    return by_file, None


def rule_font_not_allowlisted(root: Path, rel: Path, manifest: dict) -> list[Finding]:
    rel_posix = rel.as_posix()
    if Path(rel_posix).suffix.lower() not in FONT_EXTS:
        return []
    if not rel_posix.startswith(FONT_ALLOWED_DIR):
        return [Finding(rel_posix, 1, "font-not-allowlisted", "font file outside assets/fonts/")]
    filename = Path(rel_posix).name
    entry = manifest.get(filename)
    if entry is None:
        return [Finding(rel_posix, 1, "font-not-allowlisted", "not listed in assets/fonts/MANIFEST.json")]
    if entry.get("license") != "OFL-1.1":
        return [Finding(rel_posix, 1, "font-not-allowlisted", f"license={entry.get('license')!r}, expected OFL-1.1")]
    license_file = entry.get("license_file")
    if not license_file or not (root / "assets" / "fonts" / license_file).is_file():
        return [Finding(rel_posix, 1, "font-not-allowlisted", f"license_file {license_file!r} missing")]
    return []


def rule_logo_or_brand_asset(rel: Path) -> list[Finding]:
    rel_posix = rel.as_posix()
    parts_lower = [p.lower() for p in rel.parts]
    if "logos" in parts_lower:
        return [Finding(rel_posix, 1, "logo-or-brand-asset", "file under a logos/ directory")]
    if Path(rel_posix).suffix.lower() in {".svg", ".png"}:
        stem_lower = Path(rel_posix).name.lower()
        for brand in LOGO_BRAND_NAMES:
            if brand in stem_lower:
                return [Finding(rel_posix, 1, "logo-or-brand-asset", f"filename contains brand name {brand!r}")]
    return []


def rule_large_binary(root: Path, rel: Path) -> list[Finding]:
    rel_posix = rel.as_posix()
    if rel_posix.startswith(LARGE_BINARY_EXEMPT_PREFIXES):
        return []
    try:
        size = (root / rel).stat().st_size
    except OSError:
        return []
    if size > LARGE_BINARY_LIMIT:
        return [Finding(rel_posix, 1, "large-binary", f"{size} bytes > {LARGE_BINARY_LIMIT}")]
    return []


def rule_media_without_license(root: Path, rel: Path) -> list[Finding]:
    rel_posix = rel.as_posix()
    if Path(rel_posix).suffix.lower() not in MEDIA_EXTS:
        return []
    if not rel_posix.startswith(MEDIA_LICENSE_SCOPE_PREFIXES):
        return []
    directory = (root / rel).parent
    if (directory / "LICENSE").is_file():
        return []
    if any(directory.glob("*.license.txt")):
        return []
    return [Finding(rel_posix, 1, "media-without-license", "no LICENSE or *.license.txt in this directory")]


def collect_findings(root: Path, allow_prefixes: list[str], allow_files: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    files = list_files(root)
    manifest, manifest_error = _load_font_manifest(root)
    if manifest_error:
        findings.append(manifest_error)
    allow_file_set = set(allow_files)

    for rel in files:
        if is_allowed(rel, allow_prefixes):
            continue
        rel_posix = rel.as_posix()

        findings.extend(rule_font_not_allowlisted(root, rel, manifest))
        findings.extend(rule_logo_or_brand_asset(rel))
        findings.extend(rule_large_binary(root, rel))
        findings.extend(rule_media_without_license(root, rel))

        text = read_text(root / rel)
        if text is None:
            continue  # binary file: only the path/size rules above apply

        lines = text.splitlines()
        file_findings = []
        for rule_fn in TEXT_RULES:
            file_findings.extend(rule_fn(rel_posix, lines))
        file_findings.extend(rule_spanish_leak(rel_posix, text, allow_file_set))

        if rel_posix in SELF_EXEMPT_FILES:
            file_findings = [f for f in file_findings if f.rule not in SELF_EXEMPT_RULES]
        findings.extend(file_findings)

    return findings


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Fail loudly on anything that must not reach the public repo.")
    parser.add_argument("--root", default=".", help="Directory to scan (default: cwd)")
    parser.add_argument(
        "--allow", action="append", default=[],
        help="Path prefix (relative to --root) to exclude entirely from every rule; repeatable.",
    )
    parser.add_argument(
        "--allow-file", action="append", default=[],
        help="Exact relative path exempted from the spanish-leak rule only; repeatable.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a human table.")
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        print(f"!! check_clean.py: --root {args.root!r} is not a directory", file=sys.stderr)
        return 2

    # scripts/, template/, skills/, assets/, examples/, tests/ can never be
    # exempted — their own tests already use clean fixtures. This must fail
    # loudly (exit 2, no findings computed at all), not pass silently at exit 0
    # the way `--allow scripts` did before this check existed.
    bad_allow = forbidden_allow_prefix(args.allow)
    if bad_allow is not None:
        print(
            f"!! check_clean.py: --allow {bad_allow!r} is forbidden "
            "(scripts/, template/, skills/, assets/, examples/, tests/ can never be exempted)",
            file=sys.stderr,
        )
        return 2

    try:
        all_files = list_files(root)
        findings = collect_findings(root, args.allow, args.allow_file)
    except Exception as exc:  # noqa: BLE001 - this is the top-level CLI boundary
        print(f"!! check_clean.py: execution error: {exc}", file=sys.stderr)
        return 2

    counts: dict[str, int] = {}
    for f in findings:
        counts[f.rule] = counts.get(f.rule, 0) + 1

    # The "allowed: <dir> (N files skipped)" line is required always, regardless
    # of --json, so the reviewer sees what left scope even when the run is
    # otherwise silent (0 findings). Printed to stderr so --json's stdout stays
    # pure JSON (tools/tests/test_check_clean.py does json.loads(stdout)).
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
            print("check_clean: 0 findings")

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
