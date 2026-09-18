#!/usr/bin/env python3
"""scripts/reel/check_retention.py — what actually predicts retention.

    python3 check_retention.py

Reads src/plan.json, src/ritmo.json, src/graphics.json and reports: total
duration, the biggest gap WITHOUT a visual event, and how many seconds until
the hook lands. Retention target: no gap > 8s without a visual event, hook
before ~4s. This is a REPORT, not a gate (unlike check_captions.py/
check_repeats.py, which are mandatory before every render) — it always
exits 0; closing a gap is done by ADDING a punch/card/title to CONFIG in
videoconfig.py, never by trimming the script.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import io as _io  # noqa: E402
from _lib import project as _project  # noqa: E402

GAP_WARNING_S = 8.0


def collect_events(plan: dict, ritmo: dict, gfx: list[dict]) -> set[float]:
    fps = plan.get("fps", 30)
    events = {0.0}
    for it in plan.get("inserts") or []:
        events.add(it["fromF"] / fps * 1000)
    for bd in plan.get("boards") or []:
        events.add(bd["fromF"] / fps * 1000)
        events.add((bd["fromF"] + bd["durF"]) / fps * 1000)
        for scene in bd.get("scenes") or []:
            events.add(scene["fromF"] / fps * 1000)
            last = scene["fromF"]
            for w in scene.get("words") or []:
                if w["f"] - last >= fps * 2:  # a new synced word every >= 2s
                    events.add(w["f"] / fps * 1000)
                    last = w["f"]
    for t in ritmo.get("titles") or []:
        events.add(t["ms"])
        events.add(t["endMs"])
    for p in ritmo.get("punch") or []:
        events.add(p["ms"])
    for b in ritmo.get("bw") or []:
        events.add(b["ms"])
    for g in ritmo.get("glitch") or []:
        events.add(g["ms"])
    for c in ritmo.get("crosswarp") or []:
        events.add(c["atF"] / fps * 1000)
    for lt in ritmo.get("lowerthirds") or []:
        events.add(lt["ms"])
    for g in gfx:
        events.add(g["ms"])
    if "closingMs" in ritmo:
        events.add(ritmo["closingMs"])
    return events


def main(argv: list[str]) -> int:
    project_dir = _project.find_project()
    plan_path = project_dir / "src" / "plan.json"
    ritmo_path = project_dir / "src" / "ritmo.json"
    gfx_path = project_dir / "src" / "graphics.json"
    for p in (plan_path, ritmo_path, gfx_path):
        if not p.is_file():
            _io.fail(f"{p} not found — run build.py first", code=2)

    plan = _io.read_json(plan_path)
    ritmo = _io.read_json(ritmo_path)
    gfx = _io.read_json(gfx_path)

    fps = plan.get("fps", 30)
    total_ms = plan["total"] / fps * 1000
    events = sorted(collect_events(plan, ritmo, gfx))

    gaps = [(events[i + 1] - events[i], events[i]) for i in range(len(events) - 1)]
    gaps.append((total_ms - events[-1], events[-1]))
    worst = max(gaps) if gaps else (0.0, 0.0)
    hook_end_ms = ritmo.get("hookEndMs", 0)

    print(
        f"{total_ms/1000:5.1f}s | {len(events)} visual events | "
        f"biggest gap {worst[0]/1000:4.1f}s (at {worst[1]/1000:.1f}s) | hook by {hook_end_ms/1000:.1f}s"
    )
    for d, at in sorted(gaps, reverse=True)[:3]:
        marker = "  !!" if d / 1000 > GAP_WARNING_S else "    "
        print(f"{marker} gap {d/1000:4.1f}s starting at {at/1000:6.1f}s")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
