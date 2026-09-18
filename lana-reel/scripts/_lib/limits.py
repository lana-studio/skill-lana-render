"""scripts/_lib/limits.py — mirror of mcp-gateway `app/schemas/common.py` at
lana-mcp-render 1.5.0. Copied by hand, not imported (the gateway is a private
service): keep these numbers in sync by re-reading `caps.py limits`/`caps.py
render` output against this file whenever `requires.lana_mcp_render` bumps.

These are HARD gateway limits (the render fails server-side past them);
scripts fail fast on the client side with the same numbers so a mistake costs
seconds, not a wasted job.
"""
from __future__ import annotations

# Render — RENDER_MAX_* (schemas/common.py)
RENDER_MAX_COMPOSITIONS_PER_JOB = 4
RENDER_MAX_DURATION_S_PER_COMPOSITION = 180
RENDER_MAX_ASSETS = 24
# Code files only (.ts/.tsx/.js/.jsx) — a bundle's .json (plan/ritmo/graphics,
# D17) never counts against either of these.
RENDER_MAX_FILES = 64
RENDER_MAX_CODE_BYTES = 256 * 1024

# Extensions counted as "code" for RENDER_MAX_FILES/RENDER_MAX_CODE_BYTES —
# mirrors the gateway's own bundle_scan.py, which sums only these four.
BUNDLE_CODE_EXTENSIONS = frozenset({".ts", ".tsx", ".js", ".jsx"})

# Bundle (purpose="bundle") — BUNDLE_MAX_* (schemas/common.py)
BUNDLE_MAX_BYTES = 20 * 1024 * 1024
BUNDLE_MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
BUNDLE_MAX_ENTRIES = 1000
BUNDLE_MAX_PROPS_BYTES = 1024 * 1024
BUNDLE_ALLOWED_EXTENSIONS = frozenset({
    ".tsx", ".ts", ".js", ".jsx", ".json", ".css", ".svg",
    ".png", ".jpg", ".jpeg", ".webp", ".wav", ".mp3",
})

# Upload (purpose=font) — no ingest, ttf/otf/woff2 only
FONT_MAX_BYTES = 5 * 1024 * 1024

# Upload — general
UPLOAD_MAX_BYTES = 2 * 1024**3  # 2 GiB, prep_upload.py's upload size limit

# Upload duration bounds by purpose (seconds), (min, max). NOT exposed by
# lana_get_capabilities today — checked: topic="ingest"'s IngestCapabilities
# (services/mcp-gateway/app/schemas/tools.py) has no duration field at all,
# so there's nothing to read this from at runtime. Hand-mirrored from
# services/media/app/services/probe.py's MIN_DURATION_SECONDS/
# MIN_TAKE_DURATION_SECONDS/MAX_TAKE_DURATION_SECONDS. If the gateway ever
# grows a way to expose these, read them from there instead of this mirror
# — until then, prep_upload.py fails locally with the same numbers rather
# than after the upload has already traveled and the asset is REJECTED
# server-side with no way to undo it. "context" has no floor (a still image
# probes as 0s and is valid); "episode"/"take" share the same 600s (10 min)
# ceiling as "context" but MAX_DURATION_SECONDS (4h) applies to "episode"
# specifically — the gateway's ceiling escape hatch (confirm_long_duration)
# isn't reachable through any MCP tool argument today, so exceeding it is
# just as unrecoverable as missing the floor; both are hard local failures.
UPLOAD_DURATION_BOUNDS_S = {
    "episode": (60.0, 4 * 3600.0),
    "take": (1.0, 10 * 60.0),
    "context": (0.0, 10 * 60.0),
}

# Asset mount extension — mirror of server.py::_resolve_render_assets +
# common.py::RENDER_ASSET_EXT_BY_CONTENT_TYPE (D16, the asset-registry
# escalation). register_asset.py fixes this at registration; save_result.py
# job (INGEST) recalculates it once proxy_asset_id arrives (a video with a
# proxy always mounts as mp4, regardless of the original container).
RENDER_ASSET_EXT_BY_CONTENT_TYPE = {
    "video/mp4": "mp4", "video/quicktime": "mov", "video/webm": "webm", "video/x-matroska": "mkv",
    "image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/svg+xml": "svg",
    "font/ttf": "ttf", "font/otf": "otf", "font/woff2": "woff2",
    "audio/mpeg": "mp3", "audio/mp4": "m4a", "audio/wav": "wav",
}


def resolve_asset_ext(content_type: str | None, has_proxy: bool) -> str | None:
    """The extension the render harness will mount an asset under. A video
    WITH a proxy always mounts as "mp4" (the ingest proxy is h264/mp4
    regardless of the original container — a .MOV mounts as
    assets/clip.mp4); checked before the content-type map, which is the
    fallback for everything else (no proxy yet, or a non-video asset like an
    image/font). None (caller falls back to the uploaded file's own suffix)
    if content_type is missing or not in the map — e.g. purpose="bundle"'s
    "application/zip", which never goes through this at all in practice."""
    if has_proxy and (content_type or "").startswith("video/"):
        return "mp4"
    if content_type is None:
        return None
    return RENDER_ASSET_EXT_BY_CONTENT_TYPE.get(content_type)


# Requirement declared in project.json.requires and checked by caps.py
REQUIRED_SERVICE_VERSION = "1.5.0"

# Quotas observed in prod — informative only,
# scripts never enforce them (the gateway does); printed by caps.py limits.
OBSERVED_QUOTAS = {
    "jobs_per_day": 50,
    "gpu_seconds_per_month": 36000,
    "concurrent_renders": 1,
}


def parse_semver(value: str) -> tuple[int, int, int]:
    """Best-effort MAJOR.MINOR.PATCH parse. Never raises: an unparsable
    component becomes 0, so a weird version string compares as very old
    instead of crashing a script mid-run."""
    parts = (value or "").strip().split(".")
    out = []
    for i in range(3):
        try:
            out.append(int(parts[i]))
        except (IndexError, ValueError):
            out.append(0)
    return (out[0], out[1], out[2])


def version_at_least(value: str, minimum: str = REQUIRED_SERVICE_VERSION) -> bool:
    """Semantic (not string) comparison — "1.10.0" must not compare less than
    "1.9.0". caps.py limits --check uses this instead of `value < minimum`."""
    return parse_semver(value) >= parse_semver(minimum)
