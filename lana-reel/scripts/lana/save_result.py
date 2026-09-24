#!/usr/bin/env python3
"""scripts/lana/save_result.py — the "guardar" (save) step of the
emit -> call -> save handshake: a script prints the exact args for an MCP
tool, the agent calls that tool from the chat, and this script takes the
tool's result and writes it into the project.

    python3 save_result.py <kind> <path|-> [--asset <key>]

kind in: caps-limits | caps-sfx | caps-brand | caps-library | caps-render |
         transcript | silence | job | asset

`<path>` is a file holding the raw JSON of an MCP tool result — normally the
one the client persists under `tool-results/` (Claude Code does this
automatically), or one the agent `Write`'d as a last resort when that
persisted-result path isn't available. `-` reads from stdin. `_lib.io.parse_tool_result` tolerates either a bare JSON object
or one wrapped in something else.

- caps-*: writes lana/caps.<topic>.json (+ `_saved_at`). If the result carries
  `error`/`isError`, exits 1 with the error code.
- transcript: accepts a McpJobView (reads `.transcription`) or a
  TranscriptionResult directly. If `words` is empty and a `result_url` is
  present, exits 1 with the instruction to fetch it via transfer.py first —
  the URL itself is never printed. Normalizes to
  {language, duration_ms, words:[{t,s,e}], segments:[...]} (integer ms) and
  writes lana/transcript.json (or lana/<asset>.transcript.json with --asset);
  registers project.jobs.transcribe.
- silence: same shape idea -> {duration_ms, noise_db, min_silence_ms,
  speech:[[s,e]], silences:[[s,e]]}; lana/silence.json (or
  lana/<asset>.silence.json); registers project.jobs.silence with params.
- job: writes lana/jobs/<job_id>.json with read_url/result_url replaced by
  "<redacted>"; updates project.jobs.renders[] for a RENDER job (matched by
  job_id if already recorded; otherwise this is the first save after submit
  and the stub still has job_id: null — the tool result never echoes
  idempotency_key back, so it's recovered from
  lana-pkg/make_submit.args.json, or failing that the single stub still
  waiting on a job_id; no flag to remember, and no match at all is `!!`
  exit 1, never silent), or the matching asset's ingest_status for an
  INGEST job (matched by assets.*.ingest_job_id). Prints status/phase/
  error.code, outputs[], and — on SUCCEEDED with outputs — a
  `download: transfer.py get <read_url from the job result> -o out/<name>.mp4`
  instruction (the agent has the URL from the tool result already; this
  script never echoes it).
- asset: shortcut equivalent to register_asset.py from a raw AssetView,
  writing project.assets[--asset] (default "clip") — the key is never read
  from the tool result itself (AssetView has no such field).

Exit codes: 0 ok, 1 validation/error result, 2 missing/unparsable input.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import io as _io  # noqa: E402
from _lib import limits as _limits  # noqa: E402
from _lib import project as _project  # noqa: E402

CAPS_KINDS = {
    "caps-limits": "limits",
    "caps-sfx": "sfx",
    "caps-brand": "brand",
    "caps-library": "library",
    "caps-render": "render",
}
REDACTED_JOB_FIELDS = ("read_url", "result_url", "upload_url")


def read_input(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    p = Path(path)
    if not p.is_file():
        _io.fail(f"{path} does not exist", code=2)
    return p.read_text(encoding="utf-8")


def discriminate_envelope(obj: dict) -> dict:
    """What lands in save_result.py's input file is one of five shapes,
    discriminated by KEYS, never guessed (the gateway envelope contract):

    - E2: an MCP text envelope, `{"content": [{"type": "text",
      "text": "<json>"}], ...}` (`structuredContent` preferred over
      re-parsing `content[0].text` when both are present) — unwrapped here,
      recursively, so every caller downstream only ever sees a real payload.
    - E1: an error result — `isError == true`, or a `structuredContent`
      carrying both `code` and `retryable` — raised here as
      `gateway error <code>: <message>` (+ `guidance` if present); no
      caller below this ever has to check for it again.
    - E3: `JobSubmissionAccepted` (the submit ACK, not a job result) — has
      `job_id` and `poll_after_s`, but never `created_at` (which every real
      `McpJobView` always has). This is "the agent's most likely operation
      error": passing lana_submit_render/lana_transcribe/lana_measure_
      silence's own immediate return value straight to save_result.py
      instead of polling lana_wait_job first. Raised here with the exact
      next step, not just "invalid input".
    - E4/E5 (a real `McpJobView` or a naked result_url document) are
      returned as-is; each `save_*` function's own kind-specific logic
      handles those two the same way it always has.
    """
    content = obj.get("content")
    if isinstance(content, list) and content:
        structured = obj.get("structuredContent")
        if isinstance(structured, dict):
            return discriminate_envelope(structured)
        first = content[0]
        if isinstance(first, dict) and first.get("type") == "text" and isinstance(first.get("text"), str):
            try:
                inner = json.loads(first["text"])
            except (ValueError, TypeError):
                inner = None
            if isinstance(inner, dict):
                return discriminate_envelope(inner)

    structured = obj.get("structuredContent")
    structured = structured if isinstance(structured, dict) else {}
    is_error = obj.get("isError") is True or ("code" in structured and "retryable" in structured)
    if is_error:
        error = obj.get("error")
        error = error if isinstance(error, dict) else structured
        code = error.get("code")
        message = error.get("message") or obj.get("text")
        guidance = error.get("guidance")
        parts = [f"gateway error {code}: {message or ''}".strip()]
        if guidance:
            parts.append(guidance)
        _io.fail("\n".join(parts), code=1)

    if "job_id" in obj and "poll_after_s" in obj and "created_at" not in obj:
        job_id = obj.get("job_id")
        _io.fail(
            f"this is a submission ack (job {job_id}, {obj.get('kind')} {obj.get('status')}), "
            f'not a job result — call lana_wait_job("{job_id}") and save that result',
            code=1,
        )

    return obj


def load_result(path: str) -> dict:
    text = read_input(path)
    try:
        obj = _io.parse_tool_result(text)
    except ValueError:
        _io.fail("not a JSON tool result", code=2)
    if not isinstance(obj, dict):
        _io.fail("tool result is not a JSON object", code=2)
    return discriminate_envelope(obj)


def check_error(obj: dict) -> None:
    if obj.get("isError") or obj.get("error"):
        error = obj.get("error")
        code = error.get("code") if isinstance(error, dict) else obj.get("code")
        message = error.get("message") if isinstance(error, dict) else obj.get("text")
        _io.fail(f"tool returned an error: {code} {message or ''}".strip(), code=1)


def save_caps(topic: str, obj: dict, project_dir: Path | None) -> int:
    check_error(obj)
    import time

    payload = _redact(obj)
    payload["_saved_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    lana_dir = (project_dir or Path.cwd()) / "lana"
    dest = lana_dir / f"caps.{topic}.json"
    _io.write_json(dest, payload)
    _io.eprint(f"saved {dest}")
    if project_dir is not None:
        project = _project.load(project_dir)
        caps = project.setdefault("caps", {})
        if topic == "limits":
            # LimitsInfo (services/mcp-gateway/app/schemas/tools.py) has no
            # max_assets field — that field only exists on RenderLimitsInfo,
            # under topic="render"'s render.limits.max_assets, which this
            # topic never sees. Nothing downstream reads caps.max_assets
            # (only the hardcoded _limits.RENDER_MAX_ASSETS constant is
            # actually used for enforcement), so it is not persisted here.
            caps["service_version"] = obj.get("service_version")
            caps["fetched_at"] = payload["_saved_at"]
        elif topic == "sfx":
            sfx = obj.get("sfx") or {}
            caps["sfx_pack_version"] = sfx.get("pack_version")
        elif topic == "library":
            library = obj.get("library") or {}
            project.setdefault("library", {})["release"] = library.get("release")
            caps["library_release"] = library.get("release")
        _project.save(project_dir, project)
    return 0


def _asset_filename(base: str, asset: str) -> str:
    return f"{asset}.{base}.json" if asset and asset != "clip" else f"{base}.json"


def _ms(d: dict, ms_key: str, s_key: str, *fallback_keys: str) -> float:
    """Reads a millisecond value from a dict that may express it several
    ways: `<ms_key>` already in ms (this script's own normalized shape, or
    a future gateway one), `<s_key>` in SECONDS — the REAL shape
    services/mcp-gateway/app/schemas/jobs.py's TranscriptWord/
    TranscriptSegment/TranscriptionResult actually use (`start_s`/`end_s`/
    `duration_s`, verified against a live job result, not assumed from the
    field's name alone) — or any of `fallback_keys` (this script's own
    short internal names, "s"/"e"), tried last and assumed already-ms.
    Missing/None at every key returns 0.0; callers that need to distinguish
    "truly absent" check presence themselves before calling this."""
    if d.get(ms_key) is not None:
        return float(d[ms_key])
    if d.get(s_key) is not None:
        return float(d[s_key]) * 1000
    for k in fallback_keys:
        if d.get(k) is not None:
            return float(d[k])
    return 0.0


def _word_text(w: dict) -> str:
    # The real TranscriptWord field is "word" — verified against a live
    # lana_transcribe result. "text"/"t" are tolerated as fallbacks (a
    # hypothetical future gateway shape, or this script's own output fed
    # back in), never the primary path.
    for k in ("word", "text", "t"):
        if w.get(k) is not None:
            return w[k]
    return ""


def normalize_transcript(obj: dict) -> dict:
    payload = obj.get("transcription", obj)
    words = payload.get("words") or []
    if not words and payload.get("result_url"):
        _io.fail(
            "transcript exceeds inline limit: run "
            "`transfer.py get <result_url> -o lana/transcript.raw.json` and re-run "
            "`save_result.py transcript lana/transcript.raw.json`",
            code=1,
        )
    norm_words = []
    for w in words:
        norm_words.append({
            "t": _word_text(w),
            "s": round(_ms(w, "start_ms", "start_s", "s")),
            "e": round(_ms(w, "end_ms", "end_s", "e")),
        })
    segments = []
    for seg in payload.get("segments") or []:
        segments.append({
            "s": round(_ms(seg, "start_ms", "start_s", "s")),
            "e": round(_ms(seg, "end_ms", "end_s", "e")),
            "text": seg.get("text", ""),
        })
    duration_ms = None
    if payload.get("duration_ms") is not None:
        duration_ms = round(float(payload["duration_ms"]))
    elif payload.get("duration_s") is not None:
        duration_ms = round(float(payload["duration_s"]) * 1000)
    return {
        "language": payload.get("language"),
        "duration_ms": duration_ms,
        "words": norm_words,
        "segments": segments,
    }


def _validate_transcript_output(normalized: dict) -> list[str]:
    """Output-side safety net, independent of getting the INPUT shape right
    (the 7th schema bug in the systematic sweep was exactly a normalizer
    that read the wrong field names and produced a transcript that LOOKED
    normalized — same keys, same structure — but carried no real text or
    timing: every t came out None, every s/e came out 0). This never writes
    an empty or all-zero transcript, whatever the reason would have been."""
    problems = []
    words = normalized.get("words") or []
    if not words:
        problems.append("words is empty")
    duration_ms = normalized.get("duration_ms")
    ceiling = (duration_ms + 1000) if duration_ms is not None else None
    for i, w in enumerate(words):
        s, e = w.get("s"), w.get("e")
        if s is not None and e is not None and s > e:
            problems.append(f"words[{i}]: s > e ({s} > {e})")
        if not w.get("t"):
            problems.append(f"words[{i}]: empty text")
        if ceiling is not None and e is not None and e > ceiling:
            problems.append(f"words[{i}]: e ({e}) exceeds duration_ms+1000 ({ceiling})")
    return problems


def save_transcript(obj: dict, project_dir: Path | None, asset: str) -> int:
    check_error(obj)
    normalized = normalize_transcript(obj)
    problems = _validate_transcript_output(normalized)
    if problems:
        _io.fail("invalid transcript output, not writing:\n" + "\n".join(problems), code=1)
    lana_dir = (project_dir or Path.cwd()) / "lana"
    dest = lana_dir / _asset_filename("transcript", asset)
    _io.write_json(dest, normalized)
    _io.eprint(f"saved {dest}  ({len(normalized['words'])} words)")
    if project_dir is not None:
        project = _project.load(project_dir)
        job = obj.get("job_id") or (obj.get("transcription") or {}).get("job_id")
        project.setdefault("jobs", {})["transcribe"] = {"job_id": job, "status": "SUCCEEDED"}
        _project.save(project_dir, project)
    return 0


def normalize_silence(obj: dict) -> dict:
    payload = obj.get("silence", obj)

    def _pairs(key: str) -> list[list[int]]:
        # The real gateway shape (services/mcp-gateway/app/schemas/jobs.py's
        # SilenceRegion, verified against a live lana_measure_silence
        # result) is a list of {start_ms, end_ms} OBJECTS, not [start, end]
        # pairs — `for a, b in [...]` on a list of 2-key dicts silently
        # unpacks the dict's KEY NAMES, not its values, which is why this
        # used to crash with `ValueError: could not convert string to
        # float: 'start_ms'` instead of failing loudly and obviously. Also
        # accepts a plain [start, end] pair (this script's own internal
        # shape, or a hypothetical future one) so build.py's consumer side
        # — which DOES want plain pairs, `regs = ...; for r in regs: r[0],
        # r[1]` — never has to change.
        out = []
        for item in payload.get(key) or []:
            if isinstance(item, dict):
                a = _ms(item, "start_ms", "start_s")
                b = _ms(item, "end_ms", "end_s")
            else:
                a, b = item[0], item[1]
            out.append([round(float(a)), round(float(b))])
        return out

    return {
        "duration_ms": payload.get("duration_ms"),
        "noise_db": payload.get("noise_db"),
        "min_silence_ms": payload.get("min_silence_ms"),
        "speech": _pairs("speech"),
        "silences": _pairs("silences"),
    }


def _validate_silence_output(normalized: dict) -> list[str]:
    """Same output-side safety net as transcript, for the 6th schema bug's
    class: never write an empty or nonsensical silence file."""
    problems = []
    speech = normalized.get("speech") or []
    if not speech:
        problems.append("speech is empty")
    duration_ms = normalized.get("duration_ms")
    prev_end = None
    for i, pair in enumerate(speech):
        s, e = pair[0], pair[1]
        if s > e:
            problems.append(f"speech[{i}]: s > e ({s} > {e})")
        if prev_end is not None and s < prev_end:
            problems.append(f"speech[{i}]: not increasing (starts at {s}, previous ended at {prev_end})")
        if duration_ms is not None and e > duration_ms:
            problems.append(f"speech[{i}]: e ({e}) exceeds duration_ms ({duration_ms})")
        prev_end = e
    return problems


def save_silence(obj: dict, project_dir: Path | None, asset: str) -> int:
    check_error(obj)
    normalized = normalize_silence(obj)
    problems = _validate_silence_output(normalized)
    if problems:
        _io.fail("invalid silence output, not writing:\n" + "\n".join(problems), code=1)
    lana_dir = (project_dir or Path.cwd()) / "lana"
    dest = lana_dir / _asset_filename("silence", asset)
    _io.write_json(dest, normalized)
    _io.eprint(f"saved {dest}  ({len(normalized['speech'])} speech regions)")
    if project_dir is not None:
        project = _project.load(project_dir)
        project.setdefault("jobs", {})["silence"] = {
            "job_id": obj.get("job_id"),
            "status": "SUCCEEDED",
            "noise_db": normalized["noise_db"],
            "min_silence_ms": normalized["min_silence_ms"],
        }
        _project.save(project_dir, project)
    return 0


def _redact(value):
    """Recursively redacts REDACTED_JOB_FIELDS wherever they appear in a
    JSON-shaped structure, at ANY depth — not a fixed set of paths. The
    gateway's actual job shape nests a signed URL one level deeper than any
    hand-enumerated set of cases anticipates (verified live: a RENDER job's
    real read_url sits at render.outputs[].read_url, one level below what an
    earlier, enumerated version of this function covered — and there is no
    reason a future job shape won't nest it somewhere else again). Walks
    every dict and list; a redacted dict/list is a new object, never a
    mutation of the input, so a caller holding the original is unaffected."""
    if isinstance(value, dict):
        return {
            k: ("<redacted>" if k in REDACTED_JOB_FIELDS else _redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def _redact_job(obj: dict) -> dict:
    return _redact(obj)


def _recover_idempotency_key(project_dir: Path) -> str | None:
    """The tool result itself never carries idempotency_key back — neither
    JobSubmissionAccepted nor McpJobView has that field. Instead of asking
    the agent to pass it (a step it can forget, and forgetting it is
    silent), read it from lana-pkg/make_submit.args.json — what
    make_submit.py --emit wrote for THIS render a moment earlier, in the
    same emit-call-save handshake. None if the file is missing or
    unreadable; the caller falls back to matching the single render stub
    still waiting on a job_id."""
    path = project_dir / "lana-pkg" / "make_submit.args.json"
    if not path.is_file():
        return None
    try:
        data = _io.read_json(path)
    except (OSError, ValueError):
        return None
    return data.get("idempotency_key") if isinstance(data, dict) else None


def save_job(
    obj: dict,
    project_dir: Path | None,
    job_kind: str | None,
) -> int:
    job_id = obj.get("job_id")
    if not job_id:
        _io.fail("tool result has no job_id", code=1)
    redacted = _redact_job(obj)
    lana_dir = (project_dir or Path.cwd()) / "lana" / "jobs"
    dest = lana_dir / f"{job_id}.json"
    _io.write_json(dest, redacted)

    status = obj.get("status")
    phase = obj.get("phase")
    error = obj.get("error") or {}
    # McpJobView nests outputs[] under render (RenderStatus.outputs) for
    # kind=RENDER, NOT at the top level — the same wrong assumption that
    # caused the read_url redaction gap this function's file docstring
    # explains. obj.get("outputs") is kept as a fallback only in case a
    # future/other job kind ever puts it there; it is not the primary path.
    outputs = (obj.get("render") or {}).get("outputs") or obj.get("outputs") or []

    _io.eprint(f"status={status} phase={phase or ''}")
    if error:
        _io.eprint(f"error.code={error.get('code')}: {error.get('message', '')}")
    for out in outputs:
        _io.eprint(
            f"  output: {out.get('composition_id')}  {out.get('duration_s')}s  "
            f"{out.get('size_bytes')} bytes"
        )

    kind = (job_kind or obj.get("kind") or "").upper()

    if project_dir is not None:
        project = _project.load(project_dir)
        touched = False

        # INGEST: the job belongs to whichever asset recorded this job_id
        # when register_asset.py ran (assets.*.ingest_job_id).
        if kind != "RENDER":
            ingest = obj.get("ingest") or {}
            for asset in (project.get("assets") or {}).values():
                if asset.get("ingest_job_id") == job_id:
                    asset["ingest_status"] = status
                    touched = True
                    if status == "SUCCEEDED":
                        # IngestResult (services/mcp-gateway/app/schemas/
                        # jobs.py) is populated only on SUCCEEDED.
                        # proxy_asset_id is what makes the harness mount the
                        # h264 proxy instead of the original container —
                        # recompute ext now that it's actually known (D16 /
                        # bug 9); register_asset.py could only guess from
                        # content_type before ingest
                        # ran, since no proxy existed yet at that point.
                        proxy_asset_id = ingest.get("proxy_asset_id")
                        asset["proxy_asset_id"] = proxy_asset_id
                        asset["audio_asset_id"] = ingest.get("audio_asset_id")
                        asset["hdr_policy"] = ingest.get("hdr_policy")
                        new_ext = _limits.resolve_asset_ext(
                            asset.get("content_type"), has_proxy=bool(proxy_asset_id)
                        )
                        if new_ext:
                            asset["ext"] = new_ext

        # RENDER: matched by job_id if already recorded (a repeat save after
        # polling); otherwise this is the first save after lana_submit_render
        # and the stub still has job_id: null. Neither JobSubmissionAccepted
        # nor McpJobView carries idempotency_key back, so it can't come from
        # obj — recovered instead from lana-pkg/make_submit.args.json (what
        # make_submit.py --emit just wrote), or, failing that, the single
        # stub still waiting on a job_id. No flag, nothing the agent has to
        # remember to pass.
        if kind != "INGEST" and not touched:
            renders = project.setdefault("jobs", {}).setdefault("renders", [])
            match = next((r for r in renders if r.get("job_id") == job_id), None)
            if match is None:
                idem = _recover_idempotency_key(project_dir)
                if idem:
                    match = next(
                        (r for r in renders if r.get("idempotency_key") == idem), None,
                    )
            if match is None:
                null_stubs = [r for r in renders if r.get("job_id") is None]
                if len(null_stubs) == 1:
                    match = null_stubs[0]
            if match is not None:
                match["job_id"] = job_id
                match["status"] = status
                match["outputs"] = [
                    {
                        "composition_id": o.get("composition_id"),
                        "asset_id": o.get("asset_id"),
                        "duration_s": o.get("duration_s"),
                    }
                    for o in outputs
                ]
            elif kind == "RENDER" and renders:
                # Only fail loud when there was at least one stub to match
                # against and none fit — that's the real bug (a forgotten
                # idempotency key, a stale project.json). An empty renders[]
                # is not itself an error: make_probe.py's ad-hoc "hello
                # render" is a legitimate RENDER-kind job that was never
                # registered as a stub in the first place (it doesn't go
                # through make_submit.py at all), and other kinds fall
                # through this same branch (kind != "INGEST" also covers
                # TRANSCRIBE/SILENCE) with no render stub to match, ever.
                # What used to be a real problem — a RENDER result nobody's
                # project.json was expecting going completely unrecorded and
                # silent — is what made this bug hard to diagnose.
                _io.fail("render job not matched to any stub in project.json", code=1)
        _project.save(project_dir, project)

    if status == "SUCCEEDED" and outputs:
        first_name = (outputs[0].get("composition_id") or "render").lower()
        _io.eprint(
            f"download: transfer.py get <read_url from the job result> -o out/{first_name}.mp4"
        )

    return 0


def save_asset(obj: dict, project_dir: Path | None, key: str = "clip") -> int:
    check_error(obj)
    asset_id = obj.get("asset_id")
    if not asset_id:
        _io.fail("tool result has no asset_id", code=1)
    if project_dir is None:
        _io.eprint(f"asset_id={asset_id}")
        return 0
    project = _project.load(project_dir)
    # AssetView/ConfirmUploadResponse (services/mcp-gateway/app/schemas/
    # tools.py) has no "key" field at all — that's a project.json-local
    # concept the caller supplies, the same way transcript/silence take
    # --asset. Reading obj.get("key") always missed and silently defaulted
    # to "clip", so every save_result.py asset call landed on assets.clip
    # regardless of --asset, clobbering it when registering a second asset.
    entry = project.setdefault("assets", {}).setdefault(key, {})
    entry["asset_id"] = asset_id
    entry["ingest_job_id"] = obj.get("ingest_job_id")
    entry["ingest_status"] = "PENDING" if obj.get("ingest_job_id") else entry.get("ingest_status")
    _project.save(project_dir, project)
    _io.eprint(f"saved assets.{key}.asset_id = {asset_id}")
    if obj.get("ingest_job_id"):
        _io.eprint(f'wait: lana_wait_job("{obj["ingest_job_id"]}")')
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Save a persisted MCP tool result to project files.")
    parser.add_argument(
        "kind",
        choices=list(CAPS_KINDS) + ["transcript", "silence", "job", "asset"],
    )
    parser.add_argument("path")
    parser.add_argument(
        "--asset", default="clip",
        help="Asset key for multi-asset transcript/silence, or project.assets[key] for `asset`.",
    )
    parser.add_argument("--job-kind", choices=["INGEST", "RENDER"], help="Disambiguate a job result.")
    args = parser.parse_args(argv)

    try:
        project_dir = _project.find_project()
    except SystemExit:
        project_dir = None

    obj = load_result(args.path)

    if args.kind in CAPS_KINDS:
        return save_caps(CAPS_KINDS[args.kind], obj, project_dir)
    if args.kind == "transcript":
        return save_transcript(obj, project_dir, args.asset)
    if args.kind == "silence":
        return save_silence(obj, project_dir, args.asset)
    if args.kind == "job":
        return save_job(obj, project_dir, args.job_kind)
    if args.kind == "asset":
        return save_asset(obj, project_dir, args.asset)
    _io.fail(f"unknown kind {args.kind}", code=2)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
