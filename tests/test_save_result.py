"""tests/test_save_result.py — scripts/lana/save_result.py."""
from __future__ import annotations

import json

from conftest import SCRIPTS, run


def run_save(proj, args):
    return run(SCRIPTS / "lana" / "save_result.py", args, cwd=proj, env={"REEL_PROJECT": str(proj)})


def write(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")


def test_transcript_inline_normalizes_to_ms(project_dir, tmp_path):
    """Legacy/fallback shape: "text"/"start_ms"/"end_ms", already in ms —
    the real gateway shape is exercised separately below."""
    src = tmp_path / "raw.json"
    write(src, {"language": "en", "duration_ms": 2000, "words": [
        {"text": "hi", "start_ms": 0, "end_ms": 300.0},
        {"text": "there", "start_ms": 300.4, "end_ms": 600.9},
    ], "segments": [{"start_ms": 0, "end_ms": 600, "text": "hi there"}]})

    result = run_save(project_dir, ["transcript", str(src)])
    assert result.returncode == 0, result.stderr

    saved = json.loads((project_dir / "lana" / "transcript.json").read_text())
    assert saved["words"] == [{"t": "hi", "s": 0, "e": 300}, {"t": "there", "s": 300, "e": 601}]
    assert all(isinstance(w["s"], int) and isinstance(w["e"], int) for w in saved["words"])
    assert saved["segments"] == [{"s": 0, "e": 600, "text": "hi there"}]

    project = json.loads((project_dir / "project.json").read_text())
    assert project["jobs"]["transcribe"]["status"] == "SUCCEEDED"


def test_transcript_real_gateway_shape(project_dir, fixtures_dir):
    """Checked with the SAME lens as the silence crash, per team-lead's
    request: normalize_transcript() is output-allowlist-safe (never leaks a
    secret), but that says nothing about whether it reads the INPUT shape
    correctly — and it didn't. The real TranscriptWord/TranscriptSegment/
    TranscriptionResult (services/mcp-gateway/app/schemas/jobs.py) use
    `word` (not "text"/"t"), and `start_s`/`end_s`/`duration_s` in SECONDS
    (not "start_ms"/"end_ms"/"duration_ms" in ms) — verified against a live
    lana_transcribe result. This didn't crash like the silence bug: every
    word's `t` silently came out None and every `s`/`e` silently came out 0,
    which is worse, not better — a transcript that LOOKS normalized but
    carries no real text or timing, feeding straight into build.py's
    alignment. QA's actual anonymized job result, not schema-derived."""
    result = run_save(project_dir, ["transcript", str(fixtures_dir / "gateway" / "job.transcribe.succeeded.json")])
    assert result.returncode == 0, result.stderr
    saved = json.loads((project_dir / "lana" / "transcript.json").read_text())
    assert saved["duration_ms"] == 34325
    assert saved["words"][0] == {"t": "here", "s": 0, "e": 180}
    assert saved["words"][1] == {"t": "is", "s": 180, "e": 300}
    assert all(w["t"] for w in saved["words"]), "every word must have real text, not None"
    assert all(w["e"] >= w["s"] for w in saved["words"])
    assert saved["segments"][0]["text"].startswith("Here is the thing")
    assert saved["segments"][0]["s"] == 0
    assert saved["segments"][0]["e"] == 27600


def test_transcript_with_result_url_and_empty_words_exits_1_with_instruction(project_dir, tmp_path):
    src = tmp_path / "raw.json"
    write(src, {"words": [], "result_url": "https://blob.example.com/big.json?token=not-a-signature"})
    result = run_save(project_dir, ["transcript", str(src)])
    assert result.returncode == 1
    assert "transfer.py get" in result.stderr
    assert "exceeds inline limit" in result.stderr
    # the URL itself is never echoed
    assert "blob.example.com" not in result.stderr


def test_transcript_empty_words_no_result_url_exits_1(project_dir, tmp_path):
    """Output validation: never write an
    empty transcript, whatever the reason — here there's no result_url
    either, so the existing "exceeds inline limit" path can't fire; the
    output-side validator is the only thing that catches an otherwise
    genuinely empty transcript.json from ever being written."""
    src = tmp_path / "raw.json"
    write(src, {"language": "en", "duration_ms": 2000, "words": [], "segments": []})
    result = run_save(project_dir, ["transcript", str(src)])
    assert result.returncode == 1
    assert "words is empty" in result.stderr


def test_transcript_word_with_empty_text_exits_1(project_dir, tmp_path):
    """The exact shape of the 7th schema bug: words that LOOK normalized
    (right count, right structure) but every t is empty/None — this is the
    output-side check that catches it even if a FUTURE input-shape bug
    reintroduces the same silent corruption."""
    src = tmp_path / "raw.json"
    write(src, {"language": "en", "duration_ms": 2000, "words": [
        {"word": "hi", "start_s": 0, "end_s": 0.3},
        {"word": None, "start_s": 0.3, "end_s": 0.6},
    ]})
    result = run_save(project_dir, ["transcript", str(src)])
    assert result.returncode == 1
    assert "empty text" in result.stderr


def test_silence_normalizes_speech_pairs(project_dir, tmp_path):
    """Legacy/fallback shape: plain [start, end] pairs, already in ms — the
    real gateway shape is exercised separately below."""
    src = tmp_path / "raw.json"
    write(src, {"duration_ms": 5000, "noise_db": -35, "min_silence_ms": 150,
                "speech": [[0.0, 300.4], [400, 900]], "silences": [[300.4, 400]]})
    result = run_save(project_dir, ["silence", str(src)])
    assert result.returncode == 0, result.stderr
    saved = json.loads((project_dir / "lana" / "silence.json").read_text())
    assert saved["speech"] == [[0, 300], [400, 900]]
    project = json.loads((project_dir / "project.json").read_text())
    assert project["jobs"]["silence"]["noise_db"] == -35


def test_silence_empty_speech_no_result_url_exits_1(project_dir, tmp_path):
    """Output validation: never write an
    empty silence.json — no result_url here, so the existing "exceeds
    inline limit" path can't fire; the output-side validator is what
    catches a genuinely empty speech[] on its own."""
    src = tmp_path / "raw.json"
    write(src, {"duration_ms": 5000, "noise_db": -35, "min_silence_ms": 150, "speech": [], "silences": []})
    result = run_save(project_dir, ["silence", str(src)])
    assert result.returncode == 1
    assert "speech is empty" in result.stderr


def test_silence_real_gateway_shape_does_not_crash(project_dir, fixtures_dir):
    """QA's 6th finding: a real lana_measure_silence result nests speech/
    silences as lists of {start_ms, end_ms} OBJECTS (services/mcp-gateway/
    app/schemas/jobs.py's SilenceRegion), not [start, end] pairs. Unpacking
    a 2-key dict with `for a, b in [...]` silently binds the dict's KEY
    NAMES to a/b, so this used to hard-crash with `ValueError: could not
    convert string to float: 'start_ms'` — the worst of the six shape bugs,
    because it blocks step 1 of every real reel instead of degrading. This
    fixture is QA's actual anonymized job result, not derived from the
    schema (same lesson as the render/transcript fixtures: capture, don't
    guess)."""
    result = run_save(project_dir, ["silence", str(fixtures_dir / "gateway" / "job.silence.succeeded.json")])
    assert result.returncode == 0, result.stderr
    saved = json.loads((project_dir / "lana" / "silence.json").read_text())
    assert saved["duration_ms"] == 34325
    assert saved["speech"][0] == [0, 2977]
    assert saved["speech"][1] == [3211, 6985]
    assert len(saved["speech"]) == 13
    assert saved["silences"][0] == [2977, 3211]
    assert all(isinstance(pair[0], int) and isinstance(pair[1], int) for pair in saved["speech"])


def test_job_redacts_read_url_and_result_url(project_dir, fixtures_dir):
    """Regression: the real McpJobView schema (services/mcp-gateway/app/
    schemas/jobs.py) nests a RENDER job's signed URL at
    render.outputs[].read_url, NOT at the top level — a first version of
    save_result.py's redaction only covered 3 hand-enumerated shapes, none
    of them this one, and a real hello-render left a live Azure SAS URL on
    disk (found by QA against a real job; this fixture is that real job's
    shape, QA-anonymized — job_id/asset_id/signature are fake, every key
    name and nesting level is real). Asserted two ways: the exact nested
    path AND that the raw URL text is nowhere in the file at all, so this
    doesn't just re-encode the same enumeration bug on the test side."""
    fixture_text = (fixtures_dir / "tool-result-wrapped.txt").read_text()
    result = run_save(project_dir, ["job", str(fixtures_dir / "tool-result-wrapped.txt")])
    assert result.returncode == 0, result.stderr
    saved_path = project_dir / "lana" / "jobs" / "00000000-0000-4000-8000-000000000099.json"
    saved = json.loads(saved_path.read_text())
    assert saved["render"]["outputs"][0]["read_url"] == "<redacted>"
    # the literal signed-URL text from the fixture must not survive anywhere
    assert "stlanadev.blob.core.windows.net" not in saved_path.read_text()
    assert "FAKE-SIGNATURE-NOT-REAL" not in saved_path.read_text()
    assert "download: transfer.py get" in result.stderr
    assert fixture_text  # sanity: the fixture itself still has the URL to redact FROM



def test_job_redacts_nested_transcription_result_url_too(project_dir, tmp_path):
    """QA's note when handing over the real RENDER job shape: TranscriptionResult
    (McpJobView.transcription for a TRANSCRIBE-kind job) has its own nested
    result_url field (services/mcp-gateway/app/schemas/jobs.py), a DIFFERENT
    nesting shape again from render.outputs[].read_url. This is exactly what
    a truly recursive redactor (as opposed to one more enumerated case) is
    for — one test proves the whole class, not just the one shape QA had a
    real job for."""
    src = tmp_path / "transcribe_job.json"
    write(src, {
        "job_id": "00000000-0000-4000-8000-000000000077", "kind": "TRANSCRIBE", "status": "SUCCEEDED",
        "transcription": {
            "language": "en", "duration_s": 900.0, "segments": [], "words": [], "speakers": [],
            "result_url": "https://stlanadev.blob.core.windows.net/lana-media/FAKE/transcript.json?token=FAKE-NOT-REAL",
        },
    })
    result = run_save(project_dir, ["job", str(src)])
    assert result.returncode == 0, result.stderr
    saved = json.loads((project_dir / "lana" / "jobs" / "00000000-0000-4000-8000-000000000077.json").read_text())
    assert saved["transcription"]["result_url"] == "<redacted>"
    assert "stlanadev.blob.core.windows.net" not in json.dumps(saved)


def test_job_matches_stub_via_make_submit_args_json(project_dir, tmp_path):
    """Bug 10: real McpJobView/JobSubmissionAccepted objects carry neither a
    `request` field nor `idempotency_key` (services/mcp-gateway/app/schemas/
    jobs.py), so the first save after lana_submit_render can't find its
    stub from the tool result alone. Decided fix (option B, not a CLI flag —
    something the agent could forget to pass, silently): recover the key
    from lana-pkg/make_submit.args.json, the file make_submit.py --emit just
    wrote for this exact render a moment earlier in the same handshake."""
    project = json.loads((project_dir / "project.json").read_text())
    project["jobs"]["renders"] = [{"kind": "final", "idempotency_key": "fixture-reel-abcd1234-final", "bundle_sha256": "abcd1234", "job_id": None}]
    (project_dir / "project.json").write_text(json.dumps(project), encoding="utf-8")
    (project_dir / "lana-pkg").mkdir(parents=True, exist_ok=True)
    (project_dir / "lana-pkg" / "make_submit.args.json").write_text(
        json.dumps({"idempotency_key": "fixture-reel-abcd1234-final"}), encoding="utf-8",
    )

    src = tmp_path / "job.json"
    # Real McpJobView shape for a RENDER (see RenderStatus.outputs nesting) —
    # no request/idempotency_key field anywhere on it.
    write(src, {
        "job_id": "00000000-0000-4000-8000-000000000009", "status": "SUCCEEDED", "kind": "RENDER",
        "render": {"outputs": [{"composition_id": "Reel", "duration_s": 10.0}]},
    })
    result = run_save(project_dir, ["job", str(src)])
    assert result.returncode == 0, result.stderr
    updated = json.loads((project_dir / "project.json").read_text())
    stub = updated["jobs"]["renders"][0]
    assert stub["job_id"] == "00000000-0000-4000-8000-000000000009"
    assert stub["status"] == "SUCCEEDED"


def test_job_matches_single_null_job_id_stub_without_make_submit_args_json(project_dir, tmp_path):
    """Fallback of the fallback: no lana-pkg/make_submit.args.json at all
    (e.g. the agent's Write fallback path, not the persisted tool-results
    file make_submit.py wrote alongside) but there's exactly one stub still
    waiting on a job_id — safe to assume that's the one."""
    project = json.loads((project_dir / "project.json").read_text())
    project["jobs"]["renders"] = [{"kind": "final", "idempotency_key": "fixture-reel-abcd1234-final", "bundle_sha256": "abcd1234", "job_id": None}]
    (project_dir / "project.json").write_text(json.dumps(project), encoding="utf-8")

    src = tmp_path / "job.json"
    write(src, {
        "job_id": "00000000-0000-4000-8000-000000000009", "status": "SUCCEEDED", "kind": "RENDER",
        "render": {"outputs": [{"composition_id": "Reel", "duration_s": 10.0}]},
    })
    result = run_save(project_dir, ["job", str(src)])
    assert result.returncode == 0, result.stderr
    updated = json.loads((project_dir / "project.json").read_text())
    stub = updated["jobs"]["renders"][0]
    assert stub["job_id"] == "00000000-0000-4000-8000-000000000009"
    assert stub["status"] == "SUCCEEDED"


def test_job_no_match_fails_loud_not_silent(project_dir, tmp_path):
    """The actual fix in bug 10: with two stubs both still waiting on a
    job_id (so the single-null-stub fallback can't disambiguate either) and
    no make_submit.args.json, a RENDER result that can't be matched used to
    just vanish silently — exactly what made QA misdiagnose this as a
    missing --idempotency-key flag. Must now fail loud instead."""
    project = json.loads((project_dir / "project.json").read_text())
    project["jobs"]["renders"] = [
        {"kind": "proof", "idempotency_key": "fixture-reel-abcd1234-proof", "bundle_sha256": "abcd1234", "job_id": None},
        {"kind": "final", "idempotency_key": "fixture-reel-abcd1234-final", "bundle_sha256": "abcd1234", "job_id": None},
    ]
    (project_dir / "project.json").write_text(json.dumps(project), encoding="utf-8")

    src = tmp_path / "job.json"
    write(src, {
        "job_id": "00000000-0000-4000-8000-000000000009", "status": "SUCCEEDED", "kind": "RENDER",
        "render": {"outputs": [{"composition_id": "Reel", "duration_s": 10.0}]},
    })
    result = run_save(project_dir, ["job", str(src)])
    assert result.returncode == 1
    assert "not matched to any stub" in result.stderr


def test_job_non_render_kind_with_no_stub_is_not_an_error(project_dir, tmp_path):
    """A TRANSCRIBE/SILENCE job_id never has a render stub to match — that
    must stay silent (unlike an actual RENDER kind with no match), since
    save_job()'s render-matching branch also runs for every non-INGEST kind
    by design (see test_job_redacts_nested_transcription_result_url_too)."""
    src = tmp_path / "job.json"
    write(src, {"job_id": "00000000-0000-4000-8000-000000000099", "status": "SUCCEEDED", "kind": "SILENCE"})
    result = run_save(project_dir, ["job", str(src)])
    assert result.returncode == 0, result.stderr


def test_job_updates_ingest_status_on_matching_asset(project_dir, tmp_path):
    project = json.loads((project_dir / "project.json").read_text())
    project["assets"]["clip"]["ingest_job_id"] = "00000000-0000-4000-8000-000000000010"
    project["assets"]["clip"]["ingest_status"] = "PENDING"
    (project_dir / "project.json").write_text(json.dumps(project), encoding="utf-8")

    src = tmp_path / "job.json"
    write(src, {"job_id": "00000000-0000-4000-8000-000000000010", "status": "SUCCEEDED", "kind": "INGEST", "outputs": []})
    result = run_save(project_dir, ["job", str(src)])
    assert result.returncode == 0, result.stderr
    updated = json.loads((project_dir / "project.json").read_text())
    assert updated["assets"]["clip"]["ingest_status"] == "SUCCEEDED"


def test_job_ingest_success_recalculates_ext_from_proxy(project_dir, tmp_path):
    """D16/bug 9: register_asset.py can only guess ext from content_type
    before ingest runs (no proxy exists yet) — a .mov registers as "mov".
    Once the ingest job SUCCEEDS with a proxy_asset_id, the asset always
    mounts as its h264/mp4 proxy regardless of the original container, so
    this must flip clip.ext to "mp4" and record proxy_asset_id/
    audio_asset_id/hdr_policy from IngestResult (jobs.py)."""
    project = json.loads((project_dir / "project.json").read_text())
    project["assets"]["clip"]["ingest_job_id"] = "00000000-0000-4000-8000-000000000010"
    project["assets"]["clip"]["ingest_status"] = "PENDING"
    project["assets"]["clip"]["content_type"] = "video/quicktime"
    project["assets"]["clip"]["ext"] = "mov"
    (project_dir / "project.json").write_text(json.dumps(project), encoding="utf-8")

    src = tmp_path / "job.json"
    write(src, {
        "job_id": "00000000-0000-4000-8000-000000000010", "status": "SUCCEEDED", "kind": "INGEST",
        "ingest": {
            "proxy_asset_id": "00000000-0000-4000-8000-000000000011",
            "audio_asset_id": "00000000-0000-4000-8000-000000000012",
            "hdr_policy": "reinterpret",
        },
    })
    result = run_save(project_dir, ["job", str(src)])
    assert result.returncode == 0, result.stderr
    entry = json.loads((project_dir / "project.json").read_text())["assets"]["clip"]
    assert entry["ext"] == "mp4"
    assert entry["proxy_asset_id"] == "00000000-0000-4000-8000-000000000011"
    assert entry["audio_asset_id"] == "00000000-0000-4000-8000-000000000012"
    assert entry["hdr_policy"] == "reinterpret"


def test_job_ingest_pending_does_not_touch_ext(project_dir, tmp_path):
    """A non-terminal INGEST status (still PENDING/RUNNING) must not
    recalculate ext — there's no proxy_asset_id to recalculate FROM yet."""
    project = json.loads((project_dir / "project.json").read_text())
    project["assets"]["clip"]["ingest_job_id"] = "00000000-0000-4000-8000-000000000010"
    project["assets"]["clip"]["ingest_status"] = "PENDING"
    project["assets"]["clip"]["ext"] = "mov"
    (project_dir / "project.json").write_text(json.dumps(project), encoding="utf-8")

    src = tmp_path / "job.json"
    write(src, {"job_id": "00000000-0000-4000-8000-000000000010", "status": "RUNNING", "kind": "INGEST"})
    result = run_save(project_dir, ["job", str(src)])
    assert result.returncode == 0, result.stderr
    entry = json.loads((project_dir / "project.json").read_text())["assets"]["clip"]
    assert entry["ingest_status"] == "RUNNING"
    assert entry["ext"] == "mov"
    assert "proxy_asset_id" not in entry


def test_asset_defaults_to_clip_key(project_dir, tmp_path):
    """AssetView (services/mcp-gateway/app/schemas/tools.py) has no "key"
    field — a raw ConfirmUploadResponse never carries one — so with no
    --asset flag this must land on assets.clip via the CLI default, not
    because the tool result happened to have one."""
    src = tmp_path / "asset.json"
    write(src, {
        "asset_id": "00000000-0000-4000-8000-000000000301", "status": "ready",
        "ingest_job_id": "00000000-0000-4000-8000-000000000302",
    })
    result = run_save(project_dir, ["asset", str(src)])
    assert result.returncode == 0, result.stderr
    project = json.loads((project_dir / "project.json").read_text())
    assert project["assets"]["clip"]["asset_id"] == "00000000-0000-4000-8000-000000000301"
    assert project["assets"]["clip"]["ingest_status"] == "PENDING"


def test_asset_with_flag_registers_under_that_key_not_clip(project_dir, tmp_path):
    """Bug found in the schema sweep: main() parsed --asset for every kind
    but only ever threaded it to transcript/silence — `asset` silently read
    a nonexistent obj["key"] instead and always fell back to "clip",
    clobbering it on a second (e.g. "context") asset registration."""
    src = tmp_path / "asset.json"
    write(src, {"asset_id": "00000000-0000-4000-8000-000000000401", "status": "ready"})
    clip_before = json.loads((project_dir / "project.json").read_text())["assets"].get("clip")
    result = run_save(project_dir, ["asset", str(src), "--asset", "context"])
    assert result.returncode == 0, result.stderr
    project = json.loads((project_dir / "project.json").read_text())
    assert project["assets"]["context"]["asset_id"] == "00000000-0000-4000-8000-000000000401"
    # the pre-existing clip entry (fixture project.json) must be untouched
    assert project["assets"].get("clip") == clip_before


def test_parser_tolerates_wrapped_result(project_dir, fixtures_dir):
    result = run_save(project_dir, ["caps-render", str(fixtures_dir / "tool-result-wrapped.txt")])
    # tool-result-wrapped.txt is a job result, not a render-caps result, but
    # the point of this test is the PARSER: a leading non-JSON line must not
    # crash the read, whatever kind interprets the object afterward.
    assert result.returncode in (0, 1)
    assert "not a JSON tool result" not in result.stderr


def test_is_error_result_exits_1(project_dir, tmp_path):
    """McpErrorDetail (services/mcp-gateway/app/schemas/errors.py) lives
    under structuredContent when isError is true — not as bare top-level
    code/text fields (an earlier, schema-invented shape this fixture used
    to use)."""
    src = tmp_path / "err.json"
    write(src, {
        "isError": True,
        "structuredContent": {"code": "FORBIDDEN_SCOPE", "message": "missing scope render:create", "retryable": False},
    })
    result = run_save(project_dir, ["caps-limits", str(src)])
    assert result.returncode == 1
    assert "FORBIDDEN_SCOPE" in result.stderr
    assert "missing scope render:create" in result.stderr


def test_e2_mcp_text_envelope_unwrapped(project_dir, tmp_path):
    """E2: an MCP CallToolResult with the real payload only inside
    content[0].text (no structuredContent at all) must be unwrapped before
    any kind-specific normalizer ever sees it."""
    src = tmp_path / "wrapped.json"
    inner = {"service_version": "1.5.0", "render_enabled": True}
    write(src, {"content": [{"type": "text", "text": json.dumps(inner)}]})
    result = run_save(project_dir, ["caps-limits", str(src)])
    assert result.returncode == 0, result.stderr
    saved = json.loads((project_dir / "lana" / "caps.limits.json").read_text())
    assert saved["service_version"] == "1.5.0"


def test_e2_prefers_structured_content_over_reparsing_text(project_dir, tmp_path):
    """When both are present, structuredContent is the one already-parsed
    source of truth — content[0].text is a redundant human-readable render
    of the same data and should never be re-parsed instead."""
    src = tmp_path / "wrapped.json"
    write(src, {
        "content": [{"type": "text", "text": json.dumps({"service_version": "0.0.0-wrong"})}],
        "structuredContent": {"service_version": "1.5.0", "render_enabled": True},
    })
    result = run_save(project_dir, ["caps-limits", str(src)])
    assert result.returncode == 0, result.stderr
    saved = json.loads((project_dir / "lana" / "caps.limits.json").read_text())
    assert saved["service_version"] == "1.5.0"


def test_e3_submission_ack_rejected_with_next_step(project_dir, tmp_path):
    """E3: JobSubmissionAccepted (job_id + poll_after_s, no created_at) is
    the agent's most likely operation mistake — passing lana_submit_render's
    own immediate return value straight to save_result.py instead of
    polling lana_wait_job first. Must name the exact next call, not just
    reject as invalid."""
    src = tmp_path / "ack.json"
    write(src, {
        "job_id": "00000000-0000-4000-8000-000000000055", "kind": "RENDER", "status": "QUEUED",
        "poll_after_s": 10, "reused_existing": False, "retry_of_job_id": None,
    })
    result = run_save(project_dir, ["job", str(src)])
    assert result.returncode == 1
    assert "submission ack" in result.stderr
    assert 'lana_wait_job("00000000-0000-4000-8000-000000000055")' in result.stderr


def test_e4_real_job_view_not_misdetected_as_ack(project_dir, fixtures_dir):
    """A real McpJobView (has created_at) must never trip the E3 check,
    even though it also has a job_id — created_at is the discriminator."""
    result = run_save(project_dir, ["job", str(fixtures_dir / "tool-result-wrapped.txt")])
    assert result.returncode == 0, result.stderr
    assert "submission ack" not in result.stderr


def test_not_json_exits_2(project_dir, tmp_path):
    src = tmp_path / "garbage.txt"
    src.write_text("this is not json at all, no braces here", encoding="utf-8")
    result = run_save(project_dir, ["transcript", str(src)])
    assert result.returncode == 2
    assert "not a JSON tool result" in result.stderr


def test_caps_saves_with_saved_at(project_dir, tmp_path):
    src = tmp_path / "limits.json"
    write(src, {"service_version": "1.5.0", "render_enabled": True, "limits": {"max_render_duration_s": 600, "max_render_width": 1920, "max_render_height": 1080, "max_render_fps": 30, "max_render_spec_bytes": 65536, "allowed_upload_content_types": ["video/mp4"], "upload_sas_ttl_s": 3600, "read_sas_ttl_s": 3600, "quota": {}}})
    result = run_save(project_dir, ["caps-limits", str(src)])
    assert result.returncode == 0, result.stderr
    saved = json.loads((project_dir / "lana" / "caps.limits.json").read_text())
    assert saved["service_version"] == "1.5.0"
    assert "_saved_at" in saved
    # LimitsInfo has no max_assets field (services/mcp-gateway/app/schemas/
    # tools.py) — only RenderLimitsInfo (topic="render") does. Bug found in
    # the schema sweep: this used to write project.caps["max_assets"] from a
    # field that can never be present on a real topic="limits" snapshot.
    project = json.loads((project_dir / "project.json").read_text())
    assert "max_assets" not in project["caps"]
