"""tests/test_make_submit.py — scripts/lana/make_submit.py."""
from __future__ import annotations

import json

from conftest import SCRIPTS, run


def run_make_submit(proj, args):
    return run(SCRIPTS / "lana" / "make_submit.py", args, cwd=proj, env={"REEL_PROJECT": str(proj)})


def seed(project_dir, manifest_assets=None, proofs=None, library_items=None, caps_release=None):
    """D16/bug 9: make_submit.py's assets map is sourced from the registry
    (_lib.project.ready_assets), not from a static-literal scan — so the
    fixture here seeds lana-pkg/manifest-summary.json (what make_pkg.py
    would have written from that SAME registry a moment earlier), not the
    old used-assets.json. D17: proof composition ids come from
    lana-pkg/proofs.json (a list of {id, label, window}), never from
    lana-pkg/props.json — make_submit.py no longer emits `props` at all."""
    project = json.loads((project_dir / "project.json").read_text())
    project["assets"]["bundle"] = {
        "file": "lana-pkg/bundle.zip", "purpose": "bundle",
        "asset_id": "00000000-0000-4000-8000-000000000001", "sha256": "abcd1234ffffffff",
    }
    if library_items is not None:
        project["library"]["items"] = library_items
        project["library"]["release"] = "1.0.0"
    (project_dir / "project.json").write_text(json.dumps(project), encoding="utf-8")

    if manifest_assets is None:
        manifest_assets = ["clip"]  # matches the fixture project.json's one ready asset
    (project_dir / "lana-pkg" / "manifest-summary.json").write_text(
        json.dumps({"assets": manifest_assets, "lib": [], "sfx": []}), encoding="utf-8"
    )
    if proofs is None:
        proofs = [
            {"id": "Reel-proof-1", "label": "hook", "window": [0, 90]},
            {"id": "Reel-proof-2", "label": "mid", "window": [10, 100]},
        ]
    (project_dir / "lana-pkg" / "proofs.json").write_text(json.dumps(proofs), encoding="utf-8")
    if caps_release is not None:
        (project_dir / "lana" / "caps.library.json").write_text(
            json.dumps({"library": {"release": caps_release}}), encoding="utf-8"
        )


def test_proof_emits_up_to_4_compositions(project_dir):
    seed(project_dir, proofs=[{"id": f"Reel-proof-{i}", "label": "x", "window": [0, 90]} for i in range(1, 6)])
    result = run_make_submit(project_dir, ["--proof", "--emit"])
    assert result.returncode == 0, result.stderr
    args = json.loads(result.stdout)
    assert len(args["compositions"]) == 4
    assert args["compositions"] == ["Reel-proof-1", "Reel-proof-2", "Reel-proof-3", "Reel-proof-4"]


def test_final_uses_project_composition(project_dir):
    seed(project_dir)
    result = run_make_submit(project_dir, ["--final", "--emit"])
    assert result.returncode == 0, result.stderr
    args = json.loads(result.stdout)
    assert args["compositions"] == ["Reel"]


def test_never_emits_props(project_dir):
    """D17: props never reaches the render in bundle mode (the harness
    drops inputProps between prepare and render) — make_submit.py must
    never emit a `props` key at all, for --proof or --final, so nobody is
    tempted to rely on it again."""
    seed(project_dir)
    for mode in (["--proof", "--emit"], ["--final", "--emit"]):
        result = run_make_submit(project_dir, mode)
        assert result.returncode == 0, result.stderr
        args = json.loads(result.stdout)
        assert "props" not in args


def test_assets_include_all_ready_registered_not_just_referenced(project_dir):
    """D16/bug 9's actual fix, tested directly: EVERY ready registered asset
    goes in the map, whether or not any code happens to staticFile() it —
    the harness stages the whole map regardless, and "used" was the wrong
    question (that's what caused the black render in the first place)."""
    project = json.loads((project_dir / "project.json").read_text())
    project["assets"]["card1"] = {
        "purpose": "image", "content_type": "image/png", "ext": "png",
        "asset_id": "00000000-0000-4000-8000-000000000005", "ingest_status": None,
    }
    (project_dir / "project.json").write_text(json.dumps(project), encoding="utf-8")
    seed(project_dir, manifest_assets=["clip", "card1"])
    result = run_make_submit(project_dir, ["--final", "--emit"])
    assert result.returncode == 0, result.stderr
    args = json.loads(result.stdout)
    assert args["assets"] == {
        "clip": "00000000-0000-4000-8000-000000000000",
        "card1": "00000000-0000-4000-8000-000000000005",
    }


def test_bundle_and_unready_assets_excluded(project_dir):
    """bundle is never a render asset (purpose == "bundle"); an asset still
    mid-ingest (ingest_status not SUCCEEDED/None) isn't ready yet either —
    neither belongs in the submit map."""
    project = json.loads((project_dir / "project.json").read_text())
    project["assets"]["pending_clip"] = {
        "purpose": "context", "content_type": "video/mp4",
        "asset_id": "00000000-0000-4000-8000-000000000006", "ingest_status": "PENDING",
    }
    (project_dir / "project.json").write_text(json.dumps(project), encoding="utf-8")
    seed(project_dir, manifest_assets=["clip"])
    result = run_make_submit(project_dir, ["--final", "--emit"])
    assert result.returncode == 0, result.stderr
    args = json.loads(result.stdout)
    assert args["assets"] == {"clip": "00000000-0000-4000-8000-000000000000"}
    assert "bundle" not in args["assets"]
    assert "pending_clip" not in args["assets"]


def test_custom_fonts_included_from_registry(project_dir):
    """register_asset.py always dual-writes a font: project.assets[key] (the
    same registry as any other asset, purpose="font") AND
    project.fonts.custom[key] (family/weight/style). manifest-summary.json's
    "assets" list already covers project.assets, so "brand" belongs there
    too — the fixture mirrors that dual write, matching real usage."""
    project = json.loads((project_dir / "project.json").read_text())
    project["fonts"]["custom"]["brand"] = {
        "family": "Brand", "weight": 700, "style": "normal",
        "asset_id": "00000000-0000-4000-8000-000000000501",
    }
    project["assets"]["brand"] = {
        "purpose": "font", "content_type": "font/ttf", "ext": "ttf",
        "asset_id": "00000000-0000-4000-8000-000000000501", "ingest_status": None,
    }
    (project_dir / "project.json").write_text(json.dumps(project), encoding="utf-8")
    seed(project_dir, manifest_assets=["clip", "brand"])
    result = run_make_submit(project_dir, ["--final", "--emit"])
    assert result.returncode == 0, result.stderr
    args = json.loads(result.stdout)
    assert args["assets"]["brand"] == "00000000-0000-4000-8000-000000000501"


def test_missing_manifest_summary_exits_2(project_dir):
    project = json.loads((project_dir / "project.json").read_text())
    project["assets"]["bundle"] = {
        "file": "lana-pkg/bundle.zip", "purpose": "bundle",
        "asset_id": "00000000-0000-4000-8000-000000000001", "sha256": "abcd1234ffffffff",
    }
    (project_dir / "project.json").write_text(json.dumps(project), encoding="utf-8")
    (project_dir / "lana-pkg").mkdir(parents=True, exist_ok=True)
    (project_dir / "lana-pkg" / "props.json").write_text(json.dumps({"Reel": {}}), encoding="utf-8")
    result = run_make_submit(project_dir, ["--final", "--emit"])
    assert result.returncode == 2
    assert "manifest-summary.json" in result.stderr


def test_stale_manifest_summary_disagreement_exits_1(project_dir):
    """The coherence guard: manifest-summary.json (make_pkg.py's snapshot of
    the registry) must match what THIS run of make_submit.py computes from
    the SAME registry right now — a mismatch means lana-pkg/ is stale
    (an asset was registered/removed since the last make_pkg.py run)."""
    seed(project_dir, manifest_assets=["clip", "card1_that_was_removed"])
    result = run_make_submit(project_dir, ["--final", "--emit"])
    assert result.returncode == 1
    assert "make_pkg.py and make_submit.py disagree" in result.stderr


def test_empty_registry_with_no_ready_assets_is_not_an_error(project_dir):
    """A legitimate degenerate case (e.g. a FontDemo proof using only Google
    Fonts, no registered assets at all): assets == {} is fine as long as the
    registry genuinely has nothing ready — this must NOT be confused with
    the black-render regression, which is an empty map DESPITE ready assets
    existing."""
    project = json.loads((project_dir / "project.json").read_text())
    project["assets"]["clip"]["asset_id"] = None
    (project_dir / "project.json").write_text(json.dumps(project), encoding="utf-8")
    seed(project_dir, manifest_assets=[])
    result = run_make_submit(project_dir, ["--final", "--emit"])
    assert result.returncode == 0, result.stderr
    args = json.loads(result.stdout)
    assert args["assets"] == {}


def test_stale_empty_manifest_summary_exits_1(project_dir):
    """The actual black-render regression, forced directly: a stale (e.g.
    pre-registration) manifest-summary.json says "nothing" while the
    registry genuinely has a ready asset right now. assets_map is derived
    directly from the live registry (never from the stale file itself), so
    it comes out non-empty here — and the coherence check is what catches
    the disagreement and fails loud instead of silently submitting empty."""
    seed(project_dir, manifest_assets=[])
    result = run_make_submit(project_dir, ["--final", "--emit"])
    assert result.returncode == 1
    assert "make_pkg.py and make_submit.py disagree" in result.stderr


def test_more_than_24_assets_exits_1(project_dir):
    project = json.loads((project_dir / "project.json").read_text())
    manifest_assets = ["clip"]
    for i in range(25):
        key = f"a{i}"
        project["assets"][key] = {
            "asset_id": f"00000000-0000-4000-8000-{i:012d}", "purpose": "image", "ingest_status": None,
        }
        manifest_assets.append(key)
    (project_dir / "project.json").write_text(json.dumps(project), encoding="utf-8")
    seed(project_dir, manifest_assets=manifest_assets)
    result = run_make_submit(project_dir, ["--final", "--emit"])
    assert result.returncode == 1
    assert "RENDER_MAX_ASSETS" in result.stderr


def test_library_release_mismatch_blocks(project_dir):
    seed(project_dir, library_items=[{"id": "x", "kind": "font", "file": "lib/x.otf"}], caps_release="1.1.0")
    result = run_make_submit(project_dir, ["--final", "--emit"])
    assert result.returncode == 1
    assert "release mismatch" in result.stderr


def test_library_release_match_passes(project_dir):
    seed(project_dir, library_items=[{"id": "x", "kind": "font", "file": "lib/x.otf"}], caps_release="1.0.0")
    result = run_make_submit(project_dir, ["--final", "--emit"])
    assert result.returncode == 0, result.stderr


def test_idempotency_key_format(project_dir):
    seed(project_dir)
    result = run_make_submit(project_dir, ["--final", "--emit"])
    args = json.loads(result.stdout)
    key = args["idempotency_key"]
    assert key == "fixture-reel-abcd1234-final"
    assert len(key) <= 64
    import re
    assert re.match(r"^[a-z0-9-]+$", key)


def test_attempt_appends_suffix(project_dir):
    seed(project_dir)
    result = run_make_submit(project_dir, ["--final", "--attempt", "2", "--emit"])
    args = json.loads(result.stdout)
    assert args["idempotency_key"] == "fixture-reel-abcd1234-final-2"


def test_registers_render_stub(project_dir):
    seed(project_dir)
    run_make_submit(project_dir, ["--final", "--emit"])
    project = json.loads((project_dir / "project.json").read_text())
    stub = project["jobs"]["renders"][0]
    assert stub["job_id"] is None
    assert stub["kind"] == "final"
    assert stub["idempotency_key"] == "fixture-reel-abcd1234-final"
