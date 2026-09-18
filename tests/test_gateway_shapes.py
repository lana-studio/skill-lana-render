"""tests/test_gateway_shapes.py — key-parity for tests/fixtures/gateway/*.

The mandatory check this fixture family exists for: every key a captured
fixture carries must be a RECOGNIZED field for that shape — never an
invented one. If the gateway adds/renames a field, this is the test that
goes red, and the fix is to re-capture the fixture (via anonymize.py against
a fresh real response), never to hand-edit the JSON to make the test pass
again.

Known-field sets below are sourced from one thing only: a real, COMPLETE
capture (job.render.succeeded.json has every McpJobView field the gateway
sent, confirmed by diffing it against the normalizers' own field reads in
save_result.py) — not reconstructed from memory. A trimmed/partial capture
(the transcribe/silence fixtures only carry the top-level fields relevant to
their own kind) is checked as a SUBSET of that same known-field set, not
required to match it exactly — omission is fine, an unrecognized key is not.
"""
from __future__ import annotations

import json

import pytest

from conftest import FIXTURES
from deferred_skips import DEFERRED

# Hallazgo 17 (2026-09-17, final amendment): the `@pytest.mark.skip`s
# below (see tests/deferred_skips.py.DEFERRED for the current,
# authoritative count; deliberately not re-stated as a number here — it
# drifts out of sync the moment a deferral closes) are the ONLY skips this
# whole suite (tests/ + tools/tests/) is
# allowed to produce — tests/conftest.py's pytest_sessionfinish checks
# every skip's (nodeid, reason) pair against tests/deferred_skips.py's
# DEFERRED dict and fails the SESSION (not just this file) on anything
# else, or on an entry here that stopped skipping (a capture landed and
# the decorator wasn't removed). Reasons are imported from DEFERRED, never
# retyped here, so the two can't drift apart. Closing one of these means,
# in the same commit: write the fixture + delete the decorator + delete
# the DEFERRED entry — see test_create_upload_shape below for the first
# one actually closed this way.
#
# Each needs a REAL gateway capture a human has to make — there's
# nothing a script can provision on its own (contrast make_pkg.py's
# node_modules, which it CAN provision or fail loudly on instead of ever
# skipping) — see gateway-response-shapes.md §8, fixtures are captured,
# never hand-written.

GATEWAY = FIXTURES / "gateway"

# services/mcp-gateway/app/schemas/jobs.py's McpJobView — sourced from the
# one COMPLETE real capture this family has (job.render.succeeded.json).
MCP_JOB_VIEW_KEYS = {
    "job_id", "kind", "status", "asset_id", "created_at", "started_at",
    "finished_at", "progress", "phase", "queue_position",
    "cancel_requested_at", "retry_of_job_id", "compute_seconds",
    "gpu_seconds", "timed_out", "waited_s", "upstream_unconfirmed_since",
    "error", "transcription", "render", "ingest", "silence", "segment",
    "clock",
}
TRANSCRIPTION_RESULT_KEYS = {
    "language", "duration_s", "words", "segments", "speakers",
    "result_url", "clock",
}
TRANSCRIPT_WORD_KEYS = {"word", "start_s", "end_s", "confidence"}
TRANSCRIPT_SEGMENT_KEYS = {"text", "start_s", "end_s", "speaker"}
SILENCE_RESULT_KEYS = {
    "duration_ms", "noise_db", "min_silence_ms", "rms_window_ms",
    "speech", "silences", "rms", "audio_asset_id", "result_url", "clock",
}
SILENCE_REGION_KEYS = {"start_ms", "end_ms"}
RENDER_STATUS_KEYS = {
    "phase", "outputs", "warnings", "logs_tail", "library", "render_time_ms",
}
RENDER_OUTPUT_KEYS = {
    "composition_id", "asset_id", "duration_s", "size_bytes", "width",
    "height", "read_url",
}
SFX_CAPABILITIES_KEYS = {"pack_version", "count", "sfx", "quickstart"}
SFX_VIEW_KEYS = {
    "name", "category", "duration_ms", "hit_ms", "loop", "tags", "license",
    "default_volume", "variant_of",
}
LIBRARY_CAPABILITIES_KEYS = {
    "release", "generated_at", "count", "truncated",
    "requires_lana_mcp_render", "harness_version", "harness_compatible",
    "entries", "quickstart",
}
LIBRARY_ENTRY_VIEW_KEYS = {
    "id", "kind", "name", "description", "tags", "file", "ext",
    "content_type", "size_bytes", "sha256", "media", "font", "audio",
    "license", "attribution_required", "preview_ref",
}
# lana_create_upload's CreateUploadResponse (services/mcp-gateway/app/
# schemas/tools.py:890) — no purpose restriction in the shape itself.
CREATE_UPLOAD_RESPONSE_KEYS = {
    "asset_id", "upload_url", "method", "headers", "expires_at", "purpose", "next_step",
}
# lana_confirm_upload's ConfirmUploadResponse(AssetView) (tools.py:1064,
# AssetView :980) + ingest_status. Same key set for every purpose — only
# the VALUES differ (e.g. ingest_job_id is null for purpose=bundle/image/
# font, set for purpose=episode/context).
CONFIRM_UPLOAD_RESPONSE_KEYS = {
    "asset_id", "status", "filename", "content_type", "size_bytes", "duration_s",
    "width", "height", "created_at", "read_url", "rejection_reason", "purpose",
    "video_codec", "hdr_transfer", "fps", "derived_from_asset_id", "derived_kind",
    "derived_meta", "proxy_version", "proxy_current", "proxy_asset_id",
    "audio_asset_id", "hdr_policy", "clock", "ingest_job_id", "ingest_status",
}
# McpErrorDetail (errors.py:612) — the INNER error object, as it appears
# once something (the MCP client, or a tool that returns it as a plain
# document) has already stripped the outer isError/structuredContent
# envelope. See test_error_forbidden_scope_shape's DEFERRED reason for why
# this is a DIFFERENT shape from what that test asks for, not a subset.
MCP_ERROR_DETAIL_KEYS = {
    "code", "message", "guidance", "field_path", "retry_after_s", "request_id", "retryable",
}
# lana_submit_render/lana_transcribe/lana_measure_silence's immediate
# return value (jobs.py:534) — the E3 "submission ack", never a result:
# has job_id + poll_after_s, never created_at.
JOB_SUBMISSION_ACCEPTED_KEYS = {
    "job_id", "kind", "status", "poll_after_s", "reused_existing", "retry_of_job_id", "clock",
}
# McpJobView.ingest: IngestResult (jobs.py:198).
INGEST_RESULT_KEYS = {
    "clock", "proxy_asset_id", "audio_asset_id", "hdr_policy", "source", "proxy", "metrics",
}
INGEST_SOURCE_KEYS = {"codec", "width", "height", "fps", "duration_s", "color_transfer", "rotation"}
INGEST_PROXY_KEYS = {"codec", "encoder", "width", "height", "fps", "duration_s", "size_bytes", "gop"}


def _load(name: str) -> dict:
    return json.loads((GATEWAY / name).read_text(encoding="utf-8"))


def _assert_keys_known(actual: dict, known: set[str], where: str) -> None:
    unknown = set(actual.keys()) - known
    assert not unknown, f"{where}: unrecognized key(s) {unknown} — re-capture, don't hand-edit"


def test_job_transcribe_succeeded_shape():
    obj = _load("job.transcribe.succeeded.json")
    assert obj["_captured"]["job_kind"] == "TRANSCRIBE"
    _assert_keys_known({k: v for k, v in obj.items() if k != "_captured"}, MCP_JOB_VIEW_KEYS, "job.transcribe top-level")
    _assert_keys_known(obj["transcription"], TRANSCRIPTION_RESULT_KEYS, "transcription")
    for w in obj["transcription"]["words"]:
        _assert_keys_known(w, TRANSCRIPT_WORD_KEYS, "transcription.words[]")
    for seg in obj["transcription"]["segments"]:
        _assert_keys_known(seg, TRANSCRIPT_SEGMENT_KEYS, "transcription.segments[]")


def test_job_silence_succeeded_shape():
    obj = _load("job.silence.succeeded.json")
    assert obj["_captured"]["job_kind"] == "SILENCE"
    _assert_keys_known({k: v for k, v in obj.items() if k != "_captured"}, MCP_JOB_VIEW_KEYS, "job.silence top-level")
    _assert_keys_known(obj["silence"], SILENCE_RESULT_KEYS, "silence")
    for r in obj["silence"]["speech"]:
        _assert_keys_known(r, SILENCE_REGION_KEYS, "silence.speech[]")
    for r in obj["silence"]["silences"]:
        _assert_keys_known(r, SILENCE_REGION_KEYS, "silence.silences[]")


def test_job_render_succeeded_shape():
    obj = _load("job.render.succeeded.json")
    assert obj["_captured"]["job_kind"] == "RENDER"
    _assert_keys_known({k: v for k, v in obj.items() if k != "_captured"}, MCP_JOB_VIEW_KEYS, "job.render top-level")
    assert set(obj.keys()) - {"_captured"} == MCP_JOB_VIEW_KEYS, "this is the one COMPLETE capture — it should match exactly, not just be a subset"
    _assert_keys_known(obj["render"], RENDER_STATUS_KEYS, "render")
    for out in obj["render"]["outputs"]:
        _assert_keys_known(out, RENDER_OUTPUT_KEYS, "render.outputs[]")
    # the exact bug this fixture already regression-tests elsewhere
    # (test_job_redacts_read_url_and_result_url): outputs live under
    # render, never at the top level.
    assert "outputs" not in obj


def test_caps_sfx_shape():
    obj = _load("caps.sfx.json")
    payload = obj.get("sfx", obj)
    _assert_keys_known({k: v for k, v in payload.items() if k != "_captured"}, SFX_CAPABILITIES_KEYS, "caps.sfx")
    for e in payload.get("sfx") or []:
        _assert_keys_known(e, SFX_VIEW_KEYS, "sfx.sfx[]")


@pytest.mark.parametrize("name", ["caps.library.unknown.json", "caps.library.mixed.json"])
def test_caps_library_shape(name):
    obj = _load(name)
    payload = obj.get("library", obj)
    _assert_keys_known({k: v for k, v in payload.items() if k != "_captured"}, LIBRARY_CAPABILITIES_KEYS, name)
    for e in payload.get("entries") or []:
        _assert_keys_known(e, LIBRARY_ENTRY_VIEW_KEYS, f"{name}: entries[]")


def test_caps_brand_is_marked_derived_not_captured():
    """caps.brand.json is the one fixture in this directory NOT sourced from
    a real capture (QA has none for topic="brand" yet) — it must say so
    itself, not just in a commit message, so a reviewer opening the file
    alone still sees it."""
    obj = _load("caps.brand.json")
    assert "_fixture_note" in obj
    assert "schema-derived" in obj["_fixture_note"]
    assert "_captured" not in obj, "would misrepresent this as a real capture"


# --- Explicitly missing: named per the contract, not silently absent. ---
# Each skip names exactly which real tool call/response would produce it.
# Reasons come from deferred_skips.DEFERRED — see this module's own import
# and the comment above; never retyped here.

# --- Closed 2026-09-17: real captures from Martín's reel that shipped end
# to end (render job 8ca17ecb-066e-479e-92a5-c38fabdd8038, 12.97s,
# 1080x1920, verified frame-by-frame) — INCLUDING the render that failed
# first on bug 19 (job 13fcb00e-...), before the SFX-pack fix. Anonymized
# via anonymize.py; job.render.failed.json's logs_tail additionally had its
# absolute box filesystem path replaced with the literal
# "<redacted-box-path>" by hand first (private on-prem infra, not a signed
# URL — outside anonymize.py's own SIGNED_URL_KEYS rule), the only manual
# step beyond anonymize.py's standard pass. ---

def test_submit_accepted_shape():
    obj = _load("submit.accepted.json")
    _assert_keys_known({k: v for k, v in obj.items() if k != "_captured"}, JOB_SUBMISSION_ACCEPTED_KEYS, "submit.accepted")
    assert "created_at" not in obj, "an ack is not a result — no created_at"
    assert obj["status"] == "QUEUED"


def test_job_ingest_succeeded_shape():
    obj = _load("job.ingest.succeeded.json")
    assert obj["_captured"]["job_kind"] == "INGEST"
    _assert_keys_known({k: v for k, v in obj.items() if k != "_captured"}, MCP_JOB_VIEW_KEYS, "job.ingest top-level")
    _assert_keys_known(obj["ingest"], INGEST_RESULT_KEYS, "ingest")
    _assert_keys_known(obj["ingest"]["source"], INGEST_SOURCE_KEYS, "ingest.source")
    _assert_keys_known(obj["ingest"]["proxy"], INGEST_PROXY_KEYS, "ingest.proxy")
    assert obj["ingest"]["proxy_asset_id"] is not None
    assert obj["ingest"]["audio_asset_id"] is not None


def test_job_render_failed_shape():
    """Two properties no hand-written fixture would have gotten right:
    `outputs: []` on a failure (never omitted, never null), and `warnings`
    populated even though the job failed (ASSET_PROXY_SUBSTITUTED fired
    regardless — a warning isn't a predictor of success)."""
    obj = _load("job.render.failed.json")
    assert obj["_captured"]["job_kind"] == "RENDER"
    _assert_keys_known({k: v for k, v in obj.items() if k != "_captured"}, MCP_JOB_VIEW_KEYS, "job.render.failed top-level")
    _assert_keys_known(obj["render"], RENDER_STATUS_KEYS, "render")
    _assert_keys_known(obj["error"], MCP_ERROR_DETAIL_KEYS, "error")
    assert obj["status"] == "FAILED"
    assert obj["render"]["outputs"] == []
    assert obj["render"]["warnings"], "warnings can be populated on a FAILED job too, not just a successful one"
    assert obj["error"]["code"] == "RENDER_ERROR"


@pytest.mark.skip(reason=DEFERRED["tests/test_gateway_shapes.py::test_error_forbidden_scope_shape"])
def test_error_forbidden_scope_shape():
    _load("error.forbidden_scope.json")


@pytest.mark.skip(reason=DEFERRED["tests/test_gateway_shapes.py::test_confirm_upload_episode_shape"])
def test_confirm_upload_episode_shape():
    _load("confirm_upload.episode.json")


@pytest.mark.skip(reason=DEFERRED["tests/test_gateway_shapes.py::test_confirm_upload_image_shape"])
def test_confirm_upload_image_shape():
    _load("confirm_upload.image.json")


# --- Closed 2026-09-17: real captures from team-lead's D18 bundle-validation
# probe against the real gateway (request_ids f9baa3d9.../1bf054b6.../
# e1215879... — traceable in the gateway's own logs), anonymized via
# anonymize.py — never hand-written. ---

def test_create_upload_shape():
    """CreateUploadResponse has no purpose restriction in its own shape —
    this capture (purpose=bundle) satisfies it directly."""
    obj = _load("create_upload.json")
    _assert_keys_known({k: v for k, v in obj.items() if k != "_captured"}, CREATE_UPLOAD_RESPONSE_KEYS, "create_upload")


def test_confirm_upload_bundle_shape():
    """NOT a substitute for test_confirm_upload_episode_shape or
    test_confirm_upload_image_shape (purpose=bundle is a different value,
    not a superset) — its own dedicated case, added because the real data
    was there and honestly labeled rather than force-fit into either."""
    obj = _load("confirm_upload.bundle.json")
    _assert_keys_known({k: v for k, v in obj.items() if k != "_captured"}, CONFIRM_UPLOAD_RESPONSE_KEYS, "confirm_upload.bundle")
    assert obj["purpose"] == "bundle"
    assert obj["ingest_job_id"] is None, "purpose=bundle must never enqueue ingest"


@pytest.mark.parametrize(
    "name,expected_code",
    [
        ("error.asset_not_found.json", "ASSET_NOT_FOUND"),
        ("error.invalid_argument_unknown.json", "INVALID_ARGUMENT"),
        ("error.invalid_argument_type.json", "INVALID_ARGUMENT"),
    ],
)
def test_error_bare_shape(name, expected_code):
    """The bare, ALREADY-UNWRAPPED McpErrorDetail — a real, valid shape in
    its own right (this is what save_result.py's tool-result files
    ordinarily see day to day, per parse_tool_result's own 'bare document'
    branch), but explicitly NOT what test_error_forbidden_scope_shape asks
    for (the outer isError/structuredContent envelope) — see that test's
    DEFERRED reason. Three real variants, not just one: ASSET_NOT_FOUND is
    the exact error real end-to-end D17 v2 verification hit (a late
    rejection at _resolve_render_assets, proving check_imports had already
    passed); the two INVALID_ARGUMENT captures show the same bare shape
    holds across a different code and both `field_path` flavors (an
    unknown argument name, and a wrong-typed known one)."""
    obj = _load(name)
    _assert_keys_known({k: v for k, v in obj.items() if k != "_captured"}, MCP_ERROR_DETAIL_KEYS, name)
    assert obj["code"] == expected_code
    assert obj["retryable"] is False
