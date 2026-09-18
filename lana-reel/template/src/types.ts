// Shared types for the reel template. Single source of truth for the shapes
// that `build.py` (the local script that turns videoconfig.py + transcript +
// silence into props) and the Lana render harness both have to agree on.
//
// Each domain file (Reel.tsx, Graphics.tsx, Boards.tsx, Fonts.tsx, Sfx.tsx)
// re-exports the subset of these types it owns, so existing imports like
// `import { Reel, type Plan } from "./Reel"` keep working.
import type { Caption } from "@remotion/captions";

export type Plan = {
  fps: number;
  total: number;
  // Asset key of the primary source clip (default segment source), e.g. "clip".
  // Resolved through asset() in assets.ts, never a raw staticFile literal.
  src: string;
  // Final air in frames (default HOLD_F = 10 in Reel.tsx). 0 = hard cut.
  hold_f?: number;
  // The video is shown flipped horizontally (scaleX(-1)) on the base <Video>
  // AND on both sides of CrossWarp. Decided by the user after looking at the
  // probe frames (probe_source.py) — on-screen text readable vs. subject side.
  mirror?: boolean;
  // Proof-job window in output frames [from, to), half-open. When present,
  // Root.tsx wraps this composition in <Sequence from={-from}> so the output
  // covers exactly [from, to) of the full timeline — one cheap job that
  // renders a handful of short windows to check the edit before spending a
  // full render.
  render_window?: [number, number];
  segments: { fromF: number; durF: number; globalF: number; line: number; src?: string; rate?: number }[];
  captions: Caption[];
  lines: { i: number; startMs: number; endMs: number; text: string }[];
  inserts?: {
    src: string; fromS: number; fromF: number; durF: number; bgZoom?: number;
    crop?: { top: number; right: number; bottom: number; left: number };
  }[];
  boards?: Board[];
  // Split screen: a hook clip runs in the top band while the base video keeps
  // talking below. rate = asset frames per spoken-line frame, so the clip
  // lasts exactly as long as the line it illustrates.
  hookVideo?: { src: string; durF: number; rate: number; srcY?: number; full?: boolean };
  // A separate voice track (two-video format: the voice comes from another
  // take), mounted once at frame 0.
  voice?: string;
};

export type Ritmo = {
  titles: {
    ms: number; endMs: number; text: string; capSuppressEndMs: number;
    words: { text: string; ms: number }[]; sub?: string | null; subMs?: number | null;
  }[];
  punch: { ms: number }[];
  bw: { ms: number; endMs: number }[];
  glitch: { ms: number }[];
  swish?: { ms: number; dir?: number }[];
  crosswarp?: { atF: number; outFromF: number; inFromF: number; dir: number; outSrc?: string; inSrc?: string }[];
  lowerthirds?: { ms: number; num: string; text: string }[];
  titleLift?: number;
  // Style choices from the questionnaire (scripts/reel/styles.py).
  captions?: "bold" | "none";
  closingStyle?: "plate" | "none";
  fonts?: FontChoice;
  sfx?: SfxChoice;
  closingMs: number;
  hookBanner: string;
  hookTag: string;
  hookEndMs: number;
};

// ─────────────────────────── Graphics.tsx ───────────────────────────
export type Gfx = {
  slug: string;
  // "image": a user asset (purpose=image) behind the label.
  // "text": no image, generic icon.
  kind: "image" | "text";
  label: string; sub?: string;
  ms: number; slot: number;
  asset?: string;                 // asset() key when kind === "image"
  accent?: string;                // hex color; falls back to "#FFC400"
  mode?: "stack"; stackEndMs?: number;
};

// ─────────────────────────── Boards.tsx ───────────────────────────
export type Scene = { line: number; name?: string | null; fromF: number; durF: number; words: { text: string; f: number }[] };
export type Board = {
  kind: "screenshot" | "chalk" | "image" | "band";
  fromF: number; durF: number; dir: number; scenes: Scene[];
  title?: string; sub?: string;
  split?: boolean;
  markers?: { x: number; y: number; w: number; h: number; word: string }[];
  src?: string; fit?: "width" | "pan"; width?: number; scale?: number; label?: string;
  marker?: { x: number; y: number; w: number; h: number; word: string };
};

// ─────────────────────────── Fonts.tsx ───────────────────────────
export type FontFace = { family: string; weight: number; italic?: boolean; upper?: boolean; tracking?: number; scale?: number };
export type FontSet = { id: string; name: string; display: FontFace; accent: FontFace };
export type FontUse = "hook" | "titles" | "captions";
export type FontChoice = string | { pair: string; uses?: FontUse[] };

// One entry of the generated fonts-manifest.ts (project.fonts.custom, or a
// shared-library font, kind=font): describes a single @font-face to
// register. `file` is already a staticFile(...) result — the same rule
// fonts-manifest.ts follows as assets-manifest.ts and library-manifest.ts.
// Canonical shape: make_pkg.py emits this exact annotation, because this
// placeholder IS the type contract a real generated project typechecks
// against.
export type FontFile = { family: string; weight: number; style: "normal" | "italic"; file: string };

// ─────────────────────────── Sfx.tsx ───────────────────────────
export type Moment =
  | "transition" | "board" | "card" | "stack" | "whip" | "glitch" | "title" | "hook"
  | "closing" | "lowerthird" | "chalk" | "marker" | "tvoff" | "reveal";
export type SfxChoice = {
  pack?: boolean;                               // true = the Lana SFX pack is mounted (lana_get_capabilities topic="sfx")
  kit?: string;                                  // named map, for lana_set_brand_defaults
  map?: Partial<Record<Moment, string>>;
  levels?: Record<string, number>;
  rotate?: boolean;                              // alternate -2/-3 variants when a moment repeats (default true)
  names?: string[];                              // names present in the deployed pack; if absent, assume it's complete
  meta?: Record<string, { duration_ms: number; hit_ms: number; default_volume: number; variant_of?: string | null }>;
};
