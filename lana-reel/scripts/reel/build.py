#!/usr/bin/env python3
"""scripts/reel/build.py — turn videoconfig.py's CONFIG into a render plan.

    python3 build.py [--proof-windows 4]

Ported from the private skill's build.py (alignment engine, anchors, gaps,
titles, boards) and build-lana.py (the two measured corrections for
Lana-sourced words), rewritten against the new data sources:
`lana/transcript.json` + `lana/silence.json` instead of whisper-per-take.

THE RULE THAT GOVERNS EVERYTHING: cuts come from `lana/silence.json`'s
measured `speech[]` regions; text and its rhythm come from
`lana/transcript.json`, aligned by `difflib` against the script line in
CONFIG["sel"]. Never the reverse.

Two measured corrections carried over from build-lana.py, applied ONCE to an
asset's whole word stream before any line alignment (never per query — a
correction applied twice would double up):
  - a per-word duration cap of `300 + 80*len(word)` ms (faster-whisper
    stretches the last word before a pause; override via env
    REEL_WORD_SHIFT_MS only changes the second correction, not this cap);
  - `WORD_START_SHIFT_MS = 180`: a word's start is pushed 180 ms later when
    it follows a pause > 300 ms (Lana starts a word ~0.2-0.3s early out of
    silence; override via env REEL_WORD_SHIFT_MS).

Validates CONFIG: sel non-empty, 4/5-field rows,
start<end, asset keys exist with purpose in (episode, context), indices of
titles/punch/bw/glitch/crosswarp/closing/inserts/boards/lowerthirds within
range(len(sel)), inserts/gfx/boards asset refs exist, total duration <= 180s
(RENDER_MAX_DURATION_S_PER_COMPOSITION), and the removed keys
(music/flags/handfx/secretfx/cutouts/cutoutsOff) raise an explicit
"not supported in the public skill" error rather than being silently ignored.

Writes src/plan.json, src/ritmo.json, src/graphics.json (converted into
lana-pkg/src/plan.ts/ritmo.ts/gfx.ts by make_pkg.py, which imports
those .ts modules from Root.tsx — D17, "still black after the
asset-registry fix": in bundle mode the harness loses inputProps between
prepare and render, so the plan travels INSIDE the code as generated .ts
modules + defaultProps, never as `props` and never as a `.json` import, D17
v2: the gateway can't resolve a `.json` import), and lana-pkg/proofs.json
(`[{"id": "Reel-proof-N", "label": <moment>, "window": [a, b]}, ...]`, up to
--proof-windows entries — the moments chosen: hook, first title, first
card/board, closing). lana-pkg/props.json is no longer written at all.
Prints the anchor map (which SEL line each effect landed on) and the
moments chosen for the proof job.

plan.json's field names match template/src/types.ts's `Plan` exactly, not
this script's own CONFIG-side vocabulary: a segment/insert/crosswarp side's
source asset key is written under "src" (what Reel.tsx actually reads via
`asset(s.src ?? plan.src)`), never "asset" — CONFIG itself can still say
"asset" (inserts/gfx/boards CONFIG entries do), but the OUTPUT field name
follows the Plan type, not the input's. plan.mirror comes straight from
project.json's source.mirror (the user's decision after looking at
probe_source.py's frames) — this is the one field every other part of the
pipeline assumes is wired up correctly, since it's the entire reason ffmpeg
is a requirement of this skill in the first place. CONFIG["hook_video"] =
{"asset", "src_frames", "src_y"?, "full"?} (a registered context/episode
asset) produces plan.hookVideo, timed to line 0's own duration exactly like
the private skill's build-lana.py did.

`!!` and exit 1 on: a CONFIG validation failure; total duration > 180 s; a SEL
line with no match (ratio < 0.6) — prints the line and the 3 best transcript
candidates.
"""
from __future__ import annotations

import argparse
import difflib
import os
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import io as _io  # noqa: E402
from _lib import limits as _limits  # noqa: E402
from _lib import project as _project  # noqa: E402

FPS_DEFAULT = 30
DEFAULT_MAX_GAP_MS = 350
DEFAULT_NAT_GAP_MS = 200
DEFAULT_EDGE_PAD_MS = 90
TITLE_MAX_MS = 3600
WORD_START_SHIFT_MS = int(os.environ.get("REEL_WORD_SHIFT_MS", "180"))
MATCH_PAD_MS = 30
REMOVED_KEYS = ("music", "flags", "handfx", "secretfx", "cutouts", "cutoutsOff")
PROOF_WINDOW_FRAMES = 90


def _norm(text: str) -> str:
    """Duplicated from takes.py/check_repeats.py on purpose (see their
    docstrings): each script in this family reads standalone."""
    s = unicodedata.normalize("NFD", text.lower())
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]", "", s)


def _word_cap_ms(word: str) -> int:
    return 300 + 80 * len(word)


# --------------------------------------------------------------------------
# word correction (build-lana.py's two measured fixes, applied once per asset)
# --------------------------------------------------------------------------

def corrected_words(raw_words: list[dict]) -> list[dict]:
    """raw_words: [{t,s,e}] in chronological order for one asset. Returns a
    new list with the duration cap and start-shift applied, still sorted."""
    capped = []
    for w in raw_words:
        s, e = w["s"], w["e"]
        cap = _word_cap_ms(w["t"])
        e = min(e, s + cap)
        capped.append({"t": w["t"], "s": s, "e": e})
    fixed = []
    prev_end = -10**9
    for w in capped:
        s, e = w["s"], w["e"]
        if s - prev_end > 300:
            s = min(s + WORD_START_SHIFT_MS, e - 60)
        fixed.append({"t": w["t"], "s": s, "e": e})
        prev_end = e
    return fixed


# --------------------------------------------------------------------------
# alignment: script text <-> corrected transcript words in a known window
# --------------------------------------------------------------------------

def align(script_text: str, window_words: list[dict]) -> list[dict]:
    """Assigns each script word a (start_ms, end_ms) interpolated from
    window_words via difflib.SequenceMatcher on normalized tokens — same
    method as the private skill's align(), just fed corrected Lana words
    instead of a whisper-on-isolated-clip transcript."""
    script_words = [w for w in script_text.split() if w.strip()]
    if not window_words:
        return [{"text": w, "s": 0, "e": 180} for w in script_words]
    a_tokens = [_norm(w["t"]) for w in window_words]
    b_tokens = [_norm(w) for w in script_words]
    sm = difflib.SequenceMatcher(None, a_tokens, b_tokens, autojunk=False)
    out: list[tuple[float, float] | None] = [None] * len(script_words)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(j2 - j1):
                out[j1 + k] = (window_words[i1 + k]["s"], window_words[i1 + k]["e"])
        else:
            if j1 == j2:
                continue
            t0 = window_words[i1]["s"] if i1 < len(window_words) else window_words[-1]["e"]
            t1 = (
                window_words[i2 - 1]["e"] if (i2 - 1 < len(window_words) and i2 > i1)
                else (window_words[i1]["e"] if i1 < len(window_words) else window_words[-1]["e"])
            )
            if t1 <= t0:
                t1 = t0 + 200 * (j2 - j1)
            step = (t1 - t0) / (j2 - j1)
            for k in range(j2 - j1):
                out[j1 + k] = (t0 + k * step, t0 + (k + 1) * step)
    last = window_words[0]["s"]
    for k in range(len(out)):
        if out[k] is None:
            out[k] = (last, last + 180)
        last = out[k][1]
    return [{"text": script_words[k], "s": out[k][0], "e": out[k][1]} for k in range(len(script_words))]


def _best_candidate_windows(script_text: str, asset_words: list[dict], a: int, b: int, top_n: int = 3) -> list[str]:
    """Slides a window the length of the script line across the WHOLE
    corrected transcript (not just [a,b]) and returns the top_n candidates by
    match ratio — diagnostic help for a SEL line that doesn't match its own
    declared window (wrong take chosen in takes.py, typo in the script, …)."""
    script_len = len([w for w in script_text.split() if w.strip()])
    if not asset_words or script_len == 0:
        return []
    scored = []
    for i in range(len(asset_words) - script_len + 1):
        window = asset_words[i:i + script_len]
        ratio = match_ratio(script_text, window)
        scored.append((ratio, window[0]["s"], window[-1]["e"], " ".join(w["t"] for w in window)))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [f"{r:.2f} [{s}-{e}ms] {txt!r}" for r, s, e, txt in scored[:top_n]]


def match_ratio(script_text: str, window_words: list[dict]) -> float:
    a_tokens = [_norm(w["t"]) for w in window_words]
    b_tokens = [_norm(w) for w in script_text.split() if w.strip()]
    if not a_tokens or not b_tokens:
        return 0.0
    return difflib.SequenceMatcher(None, a_tokens, b_tokens, autojunk=False).ratio()


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------

def _sel_row(row) -> tuple[str, int, int, str, bool]:
    if len(row) == 4:
        return (None, *row)  # asset filled in by the caller (default asset)
    return tuple(row)


def validate_config(cfg: dict, project: dict, default_asset: str) -> list[str]:
    problems = []
    for key in REMOVED_KEYS:
        if key in cfg:
            problems.append(f"CONFIG[{key!r}] is not supported in the public skill")

    sel = cfg.get("sel") or []
    if not sel:
        problems.append("CONFIG['sel'] is empty")

    assets = project.get("assets") or {}
    n = len(sel)
    for i, row in enumerate(sel):
        if len(row) not in (4, 5):
            problems.append(f"sel[{i}] must have 4 or 5 fields, got {len(row)}")
            continue
        asset, a, b, text, _keep = _sel_row(row)
        asset = asset or default_asset
        if a >= b:
            problems.append(f"sel[{i}]: start_ms {a} >= end_ms {b}")
        if not text or not text.strip():
            problems.append(f"sel[{i}]: empty text")
        if len(row) == 5:
            entry = assets.get(asset)
            if not entry or entry.get("purpose") not in ("episode", "context"):
                problems.append(f"sel[{i}]: asset key {asset!r} not found with purpose episode/context")

    def check_indices(name: str, indices) -> None:
        for idx in indices:
            if not (0 <= idx < n):
                problems.append(f"CONFIG[{name!r}] index {idx} out of range(len(sel)={n})")

    check_indices("titles", (cfg.get("titles") or {}).keys())
    check_indices("punch", cfg.get("punch") or [])
    check_indices("bw", cfg.get("bw") or [])
    check_indices("glitch", cfg.get("glitch") or [])
    check_indices("crosswarp", [i for i, _d in cfg.get("crosswarp") or []])
    if "closing" in cfg:
        check_indices("closing", [cfg["closing"]])
    check_indices("inserts", [it["line"] for it in cfg.get("inserts") or []])
    check_indices("boards", [bd["line"] for bd in cfg.get("boards") or []])
    check_indices("lowerthirds", [lt["line"] for lt in cfg.get("lowerthirds") or []])

    for it in cfg.get("inserts") or []:
        if it.get("asset") and it["asset"] not in assets:
            problems.append(f"inserts: asset {it['asset']!r} not in project.assets")
    for kw, g in (cfg.get("gfx") or {}).items():
        if g.get("asset") and g["asset"] not in assets:
            problems.append(f"gfx[{kw!r}]: asset {g['asset']!r} not in project.assets")
    for bd in cfg.get("boards") or []:
        if bd.get("src") and bd["src"] not in assets:
            problems.append(f"boards: src {bd['src']!r} not in project.assets")

    hook_video_cfg = cfg.get("hook_video")
    if hook_video_cfg:
        hv_asset = hook_video_cfg.get("asset")
        if not hv_asset or hv_asset not in assets:
            problems.append(f"hook_video: asset {hv_asset!r} not in project.assets")
        elif assets[hv_asset].get("purpose") not in ("episode", "context"):
            problems.append(f"hook_video: asset {hv_asset!r} must have purpose episode/context")

    return problems


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------

def load_transcripts_and_silence(project_dir: Path, sel, default_asset: str):
    assets_used = list(dict.fromkeys((_sel_row(r)[0] or default_asset) for r in sel))
    transcripts, silences, corrected = {}, {}, {}
    for asset in assets_used:
        suffix = "" if asset == "clip" else f"{asset}."
        t_path = project_dir / "lana" / f"{suffix}transcript.json"
        s_path = project_dir / "lana" / f"{suffix}silence.json"
        if not t_path.is_file() or not s_path.is_file():
            _io.fail(f"missing {t_path} or {s_path} for asset {asset!r}", code=2)
        transcripts[asset] = _io.read_json(t_path)
        silences[asset] = _io.read_json(s_path)
        corrected[asset] = corrected_words(transcripts[asset].get("words") or [])
    return assets_used, transcripts, silences, corrected


def window_of(corrected_asset_words, a, b):
    return [w for w in corrected_asset_words if w["s"] >= a - MATCH_PAD_MS and w["e"] <= b + MATCH_PAD_MS]


def build(project_dir: Path, cfg: dict, project: dict, proof_windows: int) -> dict:
    default_asset = "clip"
    sel = [_sel_row(r) for r in cfg["sel"]]
    sel = [(asset or default_asset, a, b, text, keep) for asset, a, b, text, keep in sel]

    style = cfg.get("style") or {}
    gaps_cfg = style.get("gaps") or {}
    max_gap_ms = gaps_cfg.get("max", DEFAULT_MAX_GAP_MS)
    nat_gap_ms = gaps_cfg.get("nat", DEFAULT_NAT_GAP_MS)
    edge_pad_ms = gaps_cfg.get("pad", DEFAULT_EDGE_PAD_MS)

    _assets_used, _transcripts, silences, corrected = load_transcripts_and_silence(project_dir, sel, default_asset)

    fps = project.get("fps", FPS_DEFAULT)
    segments, captions, lines = [], [], []
    global_ms = 0.0

    for idx, (asset, a, b, text, keep) in enumerate(sel):
        regs = silences[asset].get("speech") or []
        inside = [list(r) for r in regs if r[1] > a and r[0] < b] or [[a, b]]

        if keep:
            pieces = [[max(a, inside[0][0] - edge_pad_ms), min(b, inside[-1][1] + edge_pad_ms)]]
        else:
            pieces = []
            cur = [max(a, inside[0][0] - edge_pad_ms), inside[0][1]]
            for nxt in inside[1:]:
                gap0, gap1 = cur[1], nxt[0]
                if gap1 - gap0 > max_gap_ms:
                    cur[1] += nat_gap_ms // 2
                    pieces.append(cur)
                    cur = [nxt[0] - nat_gap_ms // 2, nxt[1]]
                else:
                    cur[1] = nxt[1]
            cur[1] = min(b, cur[1] + edge_pad_ms)
            pieces.append(cur)

        line_start = global_ms
        local_map = []
        for ps, pe in pieces:
            dur_f = max(1, round((pe - ps) / 1000 * fps))
            segments.append({
                "src": asset, "fromF": round(ps / 1000 * fps), "durF": dur_f,
                "globalF": round(global_ms / 1000 * fps), "line": idx,
            })
            local_map.append((ps - a, pe - a, global_ms))
            global_ms += dur_f / fps * 1000

        window_words = window_of(corrected[asset], a, b)
        ratio = match_ratio(text, window_words)
        if ratio < 0.6:
            candidates = _best_candidate_windows(text, corrected[asset], a, b)
            _io.fail(
                f"sel[{idx}] no match (ratio {ratio:.2f}): {text!r}\n"
                f"    3 best candidates in the transcript near this window: {candidates}",
                code=1,
            )

        # align() must work in the SAME coordinate space as local_map (which
        # is relative to `a`, matching `pieces`/segments) — window_words are
        # in absolute asset time (Lana transcribes the whole file, unlike
        # the private skill's per-take whisper, whose output was already
        # local to the extracted clip). Shifting by `a` here is what keeps
        # this a straight port of the private align()/local_map pairing.
        window_local = [{"t": w["t"], "s": w["s"] - a, "e": w["e"] - a} for w in window_words]
        line_words = []
        for w in align(text, window_local):
            seg = next((m for m in local_map if m[0] <= w["s"] < m[1]), None) \
                or min(local_map, key=lambda m: abs(m[0] - w["s"]))
            gs = seg[2] + max(0, w["s"] - seg[0])
            ge = seg[2] + min(w["e"] - seg[0], seg[1] - seg[0])
            cap = {
                "text": w["text"] if not captions else " " + w["text"],
                "startMs": round(gs), "endMs": round(max(gs + 60, ge)),
                "timestampMs": None, "confidence": None,
            }
            captions.append(cap)
            line_words.append(cap)
        lines.append({
            "i": idx, "startMs": round(line_start), "endMs": round(global_ms),
            "text": text, "keep": bool(keep), "words": line_words,
        })

    total = round(global_ms / 1000 * fps)
    if total / fps > _limits.RENDER_MAX_DURATION_S_PER_COMPOSITION:
        _io.fail(
            f"total duration {total / fps:.1f}s exceeds "
            f"{_limits.RENDER_MAX_DURATION_S_PER_COMPOSITION}s (RENDER_MAX_DURATION_S_PER_COMPOSITION)",
            code=1,
        )

    # ---- ritmo ----
    titles = []
    for li, spec in sorted(cfg.get("titles", {}).items()):
        sub = None
        if isinstance(spec, dict):
            txt, n_lines, sub = spec["text"], spec.get("lines", 1), spec.get("sub")
        elif isinstance(spec, (list, tuple)):
            txt, n_lines = spec[0], spec[1] if len(spec) > 1 else 1
        else:
            txt, n_lines = spec, 1
        st = lines[li]["startMs"]
        en = min(lines[min(li + n_lines - 1, len(lines) - 1)]["endMs"], st + TITLE_MAX_MS)
        span = en - st
        words = txt.split()
        step = (span * 0.65) / max(1, len(words))
        titles.append({
            "ms": st, "endMs": en, "text": txt, "capSuppressEndMs": en,
            "words": [{"text": w, "ms": round(st + k * step)} for k, w in enumerate(words)],
            "sub": sub, "subMs": round(st + len(words) * step) if sub else None,
        })

    def line_ms(indices):
        return [{"ms": lines[i]["startMs"]} for i in indices]

    ritmo = {
        "titles": titles,
        "punch": line_ms(cfg.get("punch", [])),
        "bw": [{"ms": lines[i]["startMs"], "endMs": lines[i]["endMs"]} for i in cfg.get("bw", [])],
        "glitch": line_ms(cfg.get("glitch", [])),
        "crosswarp": [
            c for c in (
                (lambda frame: (lambda out_, in_: {
                    "atF": frame, "outFromF": out_[0], "outSrc": out_[1],
                    "inFromF": in_[0], "inSrc": in_[1], "dir": d,
                } if out_ is not None and in_ is not None else None)(
                    next(((s["fromF"] + s["durF"], s["src"]) for s in segments if s["globalF"] + s["durF"] == frame), None),
                    next(((s["fromF"], s["src"]) for s in segments if s["globalF"] == frame), None),
                ))(round(lines[i]["startMs"] / 1000 * fps))
                for i, d in cfg.get("crosswarp", [])
            ) if c
        ],
        "lowerthirds": [
            {"ms": lines[lt["line"]]["startMs"], "num": lt["num"], "text": lt["text"]}
            for lt in cfg.get("lowerthirds", [])
        ],
        "closingMs": lines[cfg["closing"]]["startMs"] if "closing" in cfg else lines[-1]["startMs"],
        "hookBanner": cfg.get("hook_banner", ""),
        "hookTag": cfg.get("hook_tag", ""),
        "hookEndMs": min(lines[0]["endMs"], lines[0]["startMs"] + 4200),
        "hold_f": cfg.get("hold_f", 10),
    }

    # Bug 19 follow-up (2026-09-17): the actual incident that burned a real
    # render job wasn't just the missing `names` field above — it was that
    # nothing stopped the pipeline from proceeding all the way to
    # make_pkg.py/make_submit.py with style.sfx_kit selecting SFX and
    # lana/caps.sfx.json never having been saved at all (the agent skipped
    # `caps.py sfx` / `save_result.py caps sfx`). "mute" is the only kit
    # that legitimately has no SFX (styles.py's own description: "full" =
    # every pack sound available, "minimal" = whooshes + one hook hit,
    # "mute" = "No SFX"); either of the other two without a pack on disk
    # means Sfx.tsx WILL be asked to resolve names it has nothing to check
    # against. Fail here, before a single job is spent, rather than let an
    # unresolved SFX name reach the renderer and 404 mid-render.
    sfx_kit = (cfg.get("style") or {}).get("sfx_kit", "full")
    caps_sfx_path = project_dir / "lana" / "caps.sfx.json"
    if sfx_kit != "mute" and not caps_sfx_path.is_file():
        _io.fail(
            f"style.sfx_kit={sfx_kit!r} uses the SFX pack, but {caps_sfx_path} doesn't exist — "
            "run caps.py sfx (after save_result.py caps-sfx <lana_get_capabilities result>) "
            'first, or set style.sfx_kit to "mute" if this reel has no SFX',
            code=1,
        )
    if caps_sfx_path.is_file():
        sfx_data = _io.read_json(caps_sfx_path)
        sfx_topic = sfx_data.get("sfx") or sfx_data  # unwrap the topic="sfx" envelope
        sfx_list = sfx_topic.get("sfx") or []
        ritmo["sfx"] = {
            "pack": True,
            # bug 19 (2026-09-17): Sfx.tsx's resolveName() bails out with
            # `if (!name || !sfx.pack || !sfx.names) return name;` — without
            # `names` the whole FALLBACK table is unreachable and an unmapped
            # role name (e.g. DEFAULT_MAP.title = "impact", absent from the
            # 0.9.0 pack) reaches the renderer verbatim and 404s mid-render,
            # burning a real render job. The pack's own name list is the only
            # thing that can arm it.
            "names": [e["name"] for e in sfx_list if e.get("name")],
            "meta": {
                e["name"]: {
                    "duration_ms": e.get("duration_ms"), "hit_ms": e.get("hit_ms"),
                    "default_volume": e.get("default_volume"), "variant_of": e.get("variant_of"),
                }
                for e in sfx_list
            },
        }
    else:
        ritmo["sfx"] = {"pack": False, "meta": {}}

    # ---- graphics: matched over the SAME words as the captions ----
    flat = [_norm(c["text"]) for c in captions]
    gfx_accents = cfg.get("gfx_accents", {})
    gfx = []
    for kw, spec in (cfg.get("gfx") or {}).items():
        pat = [_norm(x) for x in kw.split()]
        hit = None
        for i in range(len(flat) - len(pat) + 1):
            if flat[i:i + len(pat)] == pat:
                hit = i
                break
        if hit is None:
            _io.eprint(f"  !! no match for gfx keyword: '{kw}'")
            continue
        ms = captions[hit]["startMs"]
        entry = {**spec, "keyword": kw, "ms": ms, "accent": gfx_accents.get(kw, "#FFC400")}
        gfx.append(entry)
    gfx.sort(key=lambda x: x["ms"])

    twins = [(t["ms"], t["endMs"]) for t in titles]
    pop = [g for g in gfx if g.get("mode") != "stack"]
    stk = [g for g in gfx if g.get("mode") == "stack"]
    slot = 0
    for g in pop:
        under = any(g["ms"] < t1 and g["ms"] + 2400 > t0 for t0, t1 in twins)
        if under and slot % 2 == 1:
            slot += 1
        g["slot"] = slot
        slot += 1

    def line_of(ms):
        return next((L["i"] for L in lines if L["startMs"] <= ms < L["endMs"]), -1)

    groups, cur_group = [], []
    for g in stk:
        if cur_group and (g["ms"] - cur_group[-1]["ms"] > 5000 or line_of(g["ms"]) - line_of(cur_group[-1]["ms"]) > 1):
            groups.append(cur_group)
            cur_group = []
        cur_group.append(g)
    if cur_group:
        groups.append(cur_group)
    for grp in groups:
        last_line = next((L for L in lines if L["startMs"] <= grp[-1]["ms"] < L["endMs"]), None)
        end = min(grp[-1]["ms"] + 1800, last_line["endMs"] if last_line else grp[-1]["ms"] + 1800)
        for k, g in enumerate(grp):
            g["slot"] = k
            g["stackEndMs"] = end

    # ---- boards ----
    boards = []
    for bd in cfg.get("boards", []):
        l0, l1 = bd["line"], bd.get("end_line", bd["line"])
        f0 = round(lines[l0]["startMs"] / 1000 * fps)
        f1 = round(lines[l1]["endMs"] / 1000 * fps)
        scenes = []
        names = bd.get("scenes", [])
        for li in range(l0, l1 + 1):
            L = lines[li]
            scenes.append({
                "line": li, "name": names[li - l0] if li - l0 < len(names) else None,
                "fromF": round(L["startMs"] / 1000 * fps),
                "durF": round((L["endMs"] - L["startMs"]) / 1000 * fps),
                "words": [{"text": c["text"].strip(), "f": round(c["startMs"] / 1000 * fps)} for c in L["words"]],
            })
        entry = {
            "kind": bd["kind"], "fromF": f0, "durF": f1 - f0,
            "dir": bd.get("dir", 1), "scenes": scenes,
            "title": bd.get("title", ""), "sub": bd.get("sub", ""),
        }
        for k in ("src", "fit", "width", "label"):
            if k in bd:
                entry[k] = bd[k]
        boards.append(entry)

    inserts = []
    for it in cfg.get("inserts", []):
        L = lines[it["line"]]
        end = lines[it.get("end_line", it["line"])]["endMs"]
        dur = (end - L["startMs"] - it.get("at_ms", 0)) if it.get("to_line_end") else it.get("dur_ms", 1000)
        inserts.append({
            "src": it["asset"], "fromS": it.get("from_s", 0),
            "fromF": round((L["startMs"] + it.get("at_ms", 0)) / 1000 * fps),
            "durF": max(1, round(dur / 1000 * fps)),
        })

    plan = {
        "fps": fps, "total": total, "src": default_asset, "hold_f": cfg.get("hold_f", 10),
        "mirror": bool((project.get("source") or {}).get("mirror", False)),
        "segments": segments, "captions": captions, "lines": lines,
        "inserts": inserts, "boards": boards,
    }

    hook_video_cfg = cfg.get("hook_video")
    if hook_video_cfg:
        hook_dur_f = max(1, round((lines[0]["endMs"] - lines[0]["startMs"]) / 1000 * fps))
        src_frames = hook_video_cfg.get("src_frames", hook_dur_f)
        plan["hookVideo"] = {
            "src": hook_video_cfg["asset"],
            "durF": hook_dur_f,
            "rate": round(src_frames / hook_dur_f, 4),
            "srcY": hook_video_cfg.get("src_y", 0),
            "full": hook_video_cfg.get("full", False),
        }

    proof_specs = _pick_proof_moments(titles, boards, plan, proof_windows)

    return {"plan": plan, "ritmo": ritmo, "gfx": gfx, "proof_specs": proof_specs, "lines": lines,
            "titles": titles, "boards": boards}


def _pick_proof_moments(titles, boards, plan, n_windows):
    total = plan["total"]
    moments = {"hook": (0, PROOF_WINDOW_FRAMES)}
    if titles:
        f = round(titles[0]["ms"] / 1000 * plan["fps"])
        moments["title"] = (max(0, f - 15), max(0, f - 15) + PROOF_WINDOW_FRAMES)
    if boards:
        f = boards[0]["fromF"]
        moments["board"] = (max(0, f - 15), max(0, f - 15) + PROOF_WINDOW_FRAMES)
    hold_f = plan.get("hold_f", 10)
    moments["closing"] = (max(0, total - 75), total + hold_f)

    ordered = list(moments.items())
    while len(ordered) < n_windows:
        midpoint = total // 2
        ordered.append((f"mid-{len(ordered)}", (max(0, midpoint - 45), max(0, midpoint - 45) + PROOF_WINDOW_FRAMES)))
    return ordered[:n_windows]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Build plan/ritmo/graphics + proof props from videoconfig.py.")
    parser.add_argument("--proof-windows", type=int, default=4)
    args = parser.parse_args(argv)

    project_dir = _project.find_project()
    project = _project.load(project_dir)
    cfg = _project.load_config(project_dir)

    problems = validate_config(cfg, project, default_asset="clip")
    if problems:
        _io.fail("\n".join(problems), code=1)

    result = build(project_dir, cfg, project, args.proof_windows)
    plan, ritmo, gfx = result["plan"], result["ritmo"], result["gfx"]

    _io.write_json(project_dir / "src" / "plan.json", plan)
    _io.write_json(project_dir / "src" / "ritmo.json", ritmo)
    _io.write_json(project_dir / "src" / "graphics.json", gfx)

    # D17 v2: the plan travels inside the code — make_pkg.py converts these
    # three .json files into lana-pkg/src/plan.ts/ritmo.ts/gfx.ts,
    # imported by the generated Root.tsx — never as lana_submit_render's
    # `props` argument (in bundle mode the harness drops inputProps between
    # prepare and render) and never as a `.json` import (the gateway's
    # check_imports can't resolve one). proofs.json only records WHICH
    # window each proof composition should render; make_pkg.py's Root.tsx
    # generator does the actual render_window override on the imported plan.
    proofs = [
        {"id": f"Reel-proof-{i}", "label": name, "window": list(window)}
        for i, (name, window) in enumerate(result["proof_specs"], start=1)
    ]
    _io.write_json(project_dir / "lana-pkg" / "proofs.json", proofs)

    n_cuts = len(plan["segments"])
    total_s = plan["total"] / plan["fps"]
    _io.eprint(
        f"{project.get('name')}: {len(cfg['sel'])} lines | {n_cuts} cuts | {total_s:6.1f}s | "
        f"{len(plan['captions'])} words | {len(gfx)} graphics"
    )
    for li, spec in sorted(cfg.get("titles", {}).items()):
        txt = spec.get("text") if isinstance(spec, dict) else (spec[0] if isinstance(spec, (list, tuple)) else spec)
        _io.eprint(f"    TITLE   {txt!r:34s} -> [{li}] {result['lines'][li]['text'][:46]}")
    for li in cfg.get("bw", []):
        _io.eprint(f"    BW      {'':34s} -> [{li}] {result['lines'][li]['text'][:46]}")
    for li in cfg.get("glitch", []):
        _io.eprint(f"    GLITCH  {'':34s} -> [{li}] {result['lines'][li]['text'][:46]}")
    for li, _d in cfg.get("crosswarp", []):
        _io.eprint(f"    XWARP   {'':34s} -> [{li}] {result['lines'][li]['text'][:46]}")
    for bd in result["boards"]:
        _io.eprint(f"    BOARD   {bd['kind']:34s} -> [{bd['scenes'][0]['line']}..{bd['scenes'][-1]['line']}] {bd['durF']/plan['fps']:.1f}s")
    if "closing" in cfg:
        _io.eprint(f"    CLOSING {'':34s} -> [{cfg['closing']}] {result['lines'][cfg['closing']]['text'][:46]}")
    _io.eprint("proof windows (frames):")
    for name, window in result["proof_specs"]:
        _io.eprint(f"    {name:10s} {window}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
