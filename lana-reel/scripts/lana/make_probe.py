#!/usr/bin/env python3
"""scripts/lana/make_probe.py — the "hello render": onboarding smoke test.

    python3 make_probe.py --emit [--font Anton] [--sfx whoosh-short]

No project required. Generates a 2-file Remotion program (composition
"Hello", 60 frames @ 30fps, a Google Font headline + one SFX pack sound) and
prints the exact `lana_submit_render` args in `files` mode (this is the one
place `files` is used instead of a bundle — 2 files, well under 3 KB, so
there is no bundle to build). `idempotency_key` is time-stamped so
re-running gives a fresh job.

`verify_output.py --job <path>` interprets the result: SUCCEEDED means the
box has Google Fonts + the SFX pack mounted; ASSET_ERROR/404-on-sfx mean an
old premium/harness.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import io as _io  # noqa: E402

ROOT_TSX = '''import React from "react";
import {{ Composition, AbsoluteFill, Audio, staticFile, useCurrentFrame }} from "remotion";
import {{ loadFont }} from "@remotion/google-fonts/{font_family_id}";

const {{ fontFamily }} = loadFont();

const Hello: React.FC = () => {{
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{{{ background: "#0A0A0A", justifyContent: "center", alignItems: "center" }}}}>
      <div style={{{{ fontFamily, fontSize: 120, color: "#FFC400" }}}}>HELLO {{frame}}</div>
      <Audio src={{staticFile("sfx/{sfx_name}.wav")}} volume={{0.8}} />
    </AbsoluteFill>
  );
}};

export const RemotionRoot: React.FC = () => (
  <Composition id="Hello" component={{Hello}} durationInFrames={{60}} fps={{30}} width={{1080}} height={{1920}} />
);
'''

INDEX_TSX = (
    'import { registerRoot } from "remotion";\n'
    'import { RemotionRoot } from "./Root";\n'
    "registerRoot(RemotionRoot);\n"
)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Build the hello-render args for lana_submit_render.")
    parser.add_argument("--font", default="Anton", help="Google Font family (as @remotion/google-fonts names it).")
    parser.add_argument("--sfx", default="whoosh-short", help="SFX pack entry name.")
    parser.add_argument("--emit", action="store_true")
    args = parser.parse_args(argv)

    root_tsx = ROOT_TSX.format(font_family_id=args.font, sfx_name=args.sfx)
    files = {"src/index.tsx": INDEX_TSX, "src/Root.tsx": root_tsx}

    idempotency_key = f"hello-render-{time.strftime('%Y%m%d-%H%M', time.gmtime())}"
    submit_args = {
        "entry": "src/index.tsx",
        "compositions": ["Hello"],
        "assets": {},
        "files": files,
        "props": {"Hello": {}},
        "idempotency_key": idempotency_key,
    }

    if args.emit:
        _io.emit(submit_args, "make_probe", None)
    else:
        _io.eprint(f"hello render ready: {idempotency_key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
