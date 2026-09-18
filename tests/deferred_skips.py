"""tests/deferred_skips.py — the ONLY allowlist of tests permitted to skip.

Hallazgo 17 (2026-09-17), final amendment: two earlier defenses (a CI grep
over the pytest log, then a `@pytest.mark.guard` marker selection) each had
a blind spot — the first matched the file PATH `test_gateway_shapes.py` and
turned 7 deliberate skips red; the second was invisible to a third,
sleeping skip mechanism (`pytest.skip()` inline in test_styles.py, gated on
Fonts.tsx). Neither approach generalizes to "the next mechanism nobody
thought of yet". The fix moves the check into `pytest` itself
(tests/conftest.py's `pytest_runtest_logreport`/`pytest_sessionfinish`):
that hook doesn't care WHERE a skip came from or HOW it was spelled — it
only asks "is this exact (nodeid, reason) pair listed here?"

DEFERRED = {"<nodeid>": "<exact skip reason string>", ...}

A test may skip ONLY if its nodeid is a key here AND its reported skip
reason matches the value exactly. Closing a deferral (a real fixture
capture lands) means, in the SAME commit: write the fixture, remove the
`@pytest.mark.skip` decorator, and remove that entry from this dict — or
tests/conftest.py's `pytest_sessionfinish` fails the run with "deferral
closed but still listed" (the fixture arrived and the skip is gone, but
this dict still claims it). Adding a NEW skip anywhere without an entry
here fails with "unexpected skip", regardless of mechanism.

Every value MUST start with the literal token `DEFERRED-CAPTURE: ` — a
`@pytest.mark.skip` without that token, even if listed here, is a contract
violation and a P0 in review. The reason strings
below are imported directly by test_gateway_shapes.py's own
`@pytest.mark.skip(reason=DEFERRED[...])` decorators — never duplicated by
hand — so the two can never drift out of sync with each other.
"""
from __future__ import annotations

DEFERRED: dict[str, str] = {
    "tests/test_gateway_shapes.py::test_error_forbidden_scope_shape": (
        "DEFERRED-CAPTURE: error.forbidden_scope.json — needs the OUTER MCP envelope "
        "(isError: true, or structuredContent.code/.retryable); real McpErrorDetail "
        "objects exist now (ASSET_NOT_FOUND, 2x INVALID_ARGUMENT) but they're already "
        "unwrapped by the client before being persisted, a different (also real, also "
        "valid) shape this test does not ask for — still not captured by anyone"
    ),
    "tests/test_gateway_shapes.py::test_confirm_upload_episode_shape": (
        "DEFERRED-CAPTURE: confirm_upload.episode.json — needs ConfirmUploadResponse "
        "purpose=episode specifically; real captures exist but they're purpose=bundle "
        "(the D18 probe) and purpose=take (Martín's reel), neither of which satisfies "
        "this test — see test_confirm_upload_bundle_shape instead (closed 2026-09-17)"
    ),
    "tests/test_gateway_shapes.py::test_confirm_upload_image_shape": (
        "DEFERRED-CAPTURE: confirm_upload.image.json — needs ConfirmUploadResponse "
        "purpose=image specifically; real captures exist but they're purpose=bundle "
        "(the D18 probe) and purpose=take (Martín's reel), neither of which satisfies "
        "this test — see test_confirm_upload_bundle_shape instead (closed 2026-09-17)"
    ),
}
# Closed 2026-09-17 (D18 bundle-validation probe): test_create_upload_shape
# — a real CreateUploadResponse satisfied it directly (no purpose
# restriction in the shape). Fixture: tests/fixtures/gateway/
# create_upload.json. Also closed as ADDITIVE coverage (never listed here
# — they were never deferred against an existing test, just new tests
# added alongside real data): test_confirm_upload_bundle_shape (fixture
# confirm_upload.bundle.json) and test_error_bare_shape, parametrized over
# 3 real error captures (error.asset_not_found.json,
# error.invalid_argument_unknown.json, error.invalid_argument_type.json).
#
# Closed 2026-09-17 (Martín's reel that shipped end to end, render job
# 8ca17ecb-...): test_submit_accepted_shape (fixture submit.accepted.json),
# test_job_ingest_succeeded_shape (fixture job.ingest.succeeded.json),
# test_job_render_failed_shape (fixture job.render.failed.json — the render
# that failed first on bug 19, before the SFX-pack fix; its logs_tail had
# an absolute box filesystem path manually redacted to
# "<redacted-box-path>" before anonymize.py ran, the only step beyond
# anonymize.py's own standard pass).
