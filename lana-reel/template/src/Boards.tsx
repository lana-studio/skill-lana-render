/* Full-frame boards that replace the camera for a few seconds. Both boards
 * and the base video cross-warp into each other (Reel.tsx). The base video
 * keeps running underneath with its audio: the voice still drives the edit,
 * and captions stay on top.
 *
 * Four engines:
 * - "chalk": an animated whiteboard, ONE scene per script line, where each
 *   stroke enters on the WORD that names it (board.scenes[].words). Drawn in
 *   SVG with stroke-dashoffset, no Lottie: a pre-baked .json wouldn't line up
 *   with the actual rhythm of the voice.
 * - "screenshot": a user-supplied image (a screenshot, a tweet, a headline)
 *   with a highlighter sweep over the part you're citing, plus a small
 *   attribution pill. Always full-bleed; never crops.
 * - "image": a user image (diagram, chart) either held centered with a
 *   marker box, or panned across for a wide multi-panel image.
 * - "band": a video sized to exactly the top band (1080x1100), with
 *   hand-drawn marker boxes on cue words — used for split-screen boards.
 */
import { AbsoluteFill, continueRender, delayRender, interpolate, spring, useVideoConfig } from "remotion";
import { Video } from "@remotion/media";
import { Sequence } from "remotion";
import { asset, MediaImg } from "./assets";
import { SfxAudio } from "./Sfx";
import { useEffect } from "react";
import { loadFont as loadCaveat } from "@remotion/google-fonts/Caveat";
import { loadFont as loadAnton } from "@remotion/google-fonts/Anton";
import type { Board, Scene } from "./types";

export type { Board, Scene };

const { fontFamily: HAND, waitUntilDone: caveatReady } = loadCaveat("normal", { weights: ["400", "500", "700"], subsets: ["latin", "latin-ext"] });
/* The board header used to flicker in the final render (never in stills):
 * each Chrome tab loads the font on its own, and in some the 700/400 weight
 * wasn't ready yet when that frame painted -> invisible text for one frame.
 * Block the frame until every weight in use is loaded. */
const useCaveat = () => {
  useEffect(() => {
    const h = delayRender("caveat");
    caveatReady()
      .then(() => Promise.all(["400", "500", "700"].map((w) => document.fonts.load(`${w} 58px "${HAND.split(",")[0].replace(/"/g, "")}"`))))
      .then(() => document.fonts.ready)
      .then(() => continueRender(h), () => continueRender(h));
  }, []);
};
const { fontFamily: ANTON } = loadAnton();

const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
const prog = (frame: number, f0: number, dur: number) => clamp01((frame - f0) / Math.max(1, dur));
const norm = (s: string) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]/g, "");
/** Frame (local to the scene) a word is said at; the fallback if it isn't
 *  found — a scene never breaks just because the real transcript doesn't
 *  contain the example cue word a demo scene was written against. */
const wf = (sc: Scene, word: string, fallback: number, nth = 0) => {
  const hits = sc.words.filter((w) => norm(w.text) === norm(word));
  const h = hits[nth] ?? hits[0];
  return h ? h.f - sc.fromF : fallback;
};

/* ───────────────────────── chalk drawing primitives ───────────────────────── */
const CHALK = "#F3EFE4", YEL = "#FFD35C", BG = "#15221C";

/* A stroke that draws itself in: pathLength=1 + dashoffset. A touch of
 * roughness from the filter below so it doesn't read as clean vector art. */
const Stroke: React.FC<{ d: string; p: number; color?: string; w?: number; dash?: boolean; op?: number }> =
  ({ d, p, color = CHALK, w = 7, dash = false, op = 0.94 }) => p <= 0 ? null : (
    <path d={d} fill="none" stroke={color} strokeWidth={w} strokeLinecap="round" strokeLinejoin="round"
          pathLength={1} strokeDasharray={dash ? "0.03 0.02" : 1} strokeDashoffset={dash ? 0 : 1 - p}
          opacity={op * (dash ? p : 1)} filter="url(#chalk)" />
  );
const rectPath = (x: number, y: number, w: number, h: number, r = 22) =>
  `M ${x + r} ${y} H ${x + w - r} Q ${x + w} ${y} ${x + w} ${y + r} V ${y + h - r} Q ${x + w} ${y + h} ${x + w - r} ${y + h} H ${x + r} Q ${x} ${y + h} ${x} ${y + h - r} V ${y + r} Q ${x} ${y} ${x + r} ${y} Z`;
const arrowPath = (x0: number, y0: number, x1: number, y1: number) => {
  const a = Math.atan2(y1 - y0, x1 - x0), L = 26;
  return `M ${x0} ${y0} L ${x1} ${y1} M ${x1 - L * Math.cos(a - 0.5)} ${y1 - L * Math.sin(a - 0.5)} L ${x1} ${y1} L ${x1 - L * Math.cos(a + 0.5)} ${y1 - L * Math.sin(a + 0.5)}`;
};
/* "handwritten" text: reveals left to right through a clip. */
const Hand: React.FC<{ x: number; y: number; t: string; p: number; size?: number; color?: string; anchor?: "start" | "middle" | "end"; bold?: boolean }> =
  ({ x, y, t, p, size = 54, color = CHALK, anchor = "start", bold = false }) => {
    if (p <= 0) return null;
    const w = t.length * size * 0.62;
    const x0 = anchor === "middle" ? x - w / 2 : anchor === "end" ? x - w : x;
    const id = `c${Math.round(x)}-${Math.round(y)}-${t.length}`;
    return (
      <g>
        <clipPath id={id}><rect x={x0 - 10} y={y - size} width={(w + 20) * p} height={size * 1.5} /></clipPath>
        <text x={x} y={y} clipPath={`url(#${id})`} fontFamily={HAND} fontSize={size} fontWeight={bold ? 700 : 500}
              fill={color} textAnchor={anchor} opacity={0.96}>{t}</text>
      </g>
    );
  };
const Chip: React.FC<{ x: number; y: number; w: number; h: number; t: string; p: number; color?: string }> =
  ({ x, y, w, h, t, p, color = YEL }) => p <= 0 ? null : (
    <g transform={`translate(${x + w / 2} ${y + h / 2}) scale(${0.6 + 0.4 * p}) translate(${-(x + w / 2)} ${-(y + h / 2)})`} opacity={Math.min(1, p * 2)}>
      <rect x={x} y={y} width={w} height={h} rx={h / 2} fill={color} opacity={0.95} />
      <text x={x + w / 2} y={y + h / 2 + 16} fontFamily={HAND} fontSize={50} fontWeight={700} fill="#14201B" textAnchor="middle">{t}</text>
    </g>
  );

/* ───────────────────────── demo scenes ─────────────────────────
 * Two generic scenes, wired to the drawing primitives above. Write new
 * scenes per video — these ship only as a working example and a fixture for
 * `npm run check` / the proof job. Cue words are examples: wf() falls back
 * to a fixed frame when the word isn't in the actual line, so a demo scene
 * never breaks against real material. */
const SceneDemoA: React.FC<{ sc: Scene; f: number }> = ({ sc, f }) => {
  const fPoint = wf(sc, "point", 20), fLeads = wf(sc, "leads", 55), fOutcome = wf(sc, "outcome", 95), fSo = wf(sc, "so", sc.durF - 40);
  const { fps } = useVideoConfig();
  const pChip = spring({ frame: f - fSo, fps, durationInFrames: 10, config: { damping: 12, stiffness: 260 } });
  return (
    <g>
      <Stroke d={rectPath(230, 700, 340, 170, 26)} p={prog(f, 0, 16)} />
      <Hand x={400} y={800} t="the point" p={prog(f, fPoint, 12)} anchor="middle" size={46} />
      <Stroke d={arrowPath(570, 785, 780, 785)} p={prog(f, fLeads, 12)} color={YEL} w={9} />
      <Stroke d={rectPath(800, 700, 340, 170, 26)} p={prog(f, fOutcome, 16)} />
      <Hand x={970} y={800} t="the outcome" p={prog(f, fOutcome + 14, 12)} anchor="middle" size={42} />
      <Chip x={430} y={1000} w={340} h={104} t="so what?" p={pChip} />
    </g>
  );
};
const SceneDemoB: React.FC<{ sc: Scene; f: number }> = ({ sc, f }) => {
  const items: [string, number][] = [["first", wf(sc, "first", 20)], ["second", wf(sc, "second", 70)], ["third", wf(sc, "third", 120)]];
  return (
    <g>
      {items.map(([label, f0], i) => {
        const p = prog(f, f0, 12);
        const y = 620 + i * 150;
        return (
          <g key={label}>
            <Stroke d={`M 220 ${y} l 26 30 l 50 -60`} p={p} color={YEL} w={10} />
            <Hand x={330} y={y + 16} t={label} p={p} size={50} />
          </g>
        );
      })}
    </g>
  );
};

/* Registry of scenes by NAME: each video's config declares which scene goes
 * on which line (board.scenes[].name). Consecutive lines with the same
 * prefix are not wiped against each other — they share the same drawing. */
const SCENES: Record<string, React.FC<{ sc: Scene; f: number }>> = {
  "demo-a": SceneDemoA,
  "demo-b": SceneDemoB,
};

export const ChalkBoard: React.FC<{ board: Board; frame: number }> = ({ board, frame }) => {
  useCaveat();
  // frame is GLOBAL; each scene starts at its own line. Consecutive lines
  // with the SAME name are one scene (their words are merged). Between
  // scenes of a different prefix: the outgoing one wipes left, the incoming
  // one writes in left to right; same prefix -> no wipe.
  const SW = 8;
  const merged: Scene[] = [];
  for (const sc of board.scenes) {
    const last = merged[merged.length - 1];
    if (last && last.name && last.name === sc.name) {
      last.durF = sc.fromF + sc.durF - last.fromF;
      last.words = [...last.words, ...sc.words];
    } else merged.push({ ...sc, words: [...sc.words] });
  }
  const pre = (n?: string | null) => (n ?? "").split("-")[0];
  return (
    <AbsoluteFill style={{ background: BG }}>
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at 30% 20%, rgba(255,255,255,0.06), transparent 55%), radial-gradient(ellipse at 80% 90%, rgba(255,255,255,0.05), transparent 50%)" }} />
      <AbsoluteFill style={{ boxShadow: "inset 0 0 260px rgba(0,0,0,0.75)" }} />
      <svg width={1080} height={1920} viewBox="0 0 1080 1920" style={{ position: "absolute", inset: 0 }}>
        <defs>
          {/* filterUnits=userSpaceOnUse: with the default region (bbox) a
              straight vertical line has a zero-width bbox and the filter
              erases it */}
          <filter id="chalk" filterUnits="userSpaceOnUse" x="0" y="0" width="1080" height="1920"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" result="n" /><feDisplacementMap in="SourceGraphic" in2="n" scale="3" /></filter>
        </defs>
        {/* underline below the header (the text itself is in HTML, see below) */}
        <path d={board.split ? "M 72 132 q 120 10 240 0 t 200 4" : "M 72 352 q 120 10 240 0 t 200 4"} fill="none" stroke={YEL} strokeWidth={5} strokeLinecap="round" opacity={0.8} />
        {merged.map((sc, i) => {
          const Comp = sc.name ? SCENES[sc.name] : undefined;
          if (!Comp) return null;
          const f = frame - sc.fromF;
          const end = sc.durF;
          if (f < -SW || f >= end + SW) return null;
          const samePrev = i > 0 && pre(merged[i - 1].name) === pre(sc.name);
          const sameNext = i < merged.length - 1 && pre(merged[i + 1].name) === pre(sc.name);
          const inP = samePrev ? 1 : prog(f, 0, SW), outP = sameNext ? (f >= end ? 1 : 0) : prog(f, end, SW);
          const w = 1080 * inP;
          return (
            <g key={i} clipPath={`url(#wipe${i})`} opacity={1 - outP} transform={`translate(${-60 * outP * (sameNext ? 0 : 1)} 70)`}>
              <clipPath id={`wipe${i}`}><rect x={0} y={0} width={w} height={1920} /></clipPath>
              <Comp sc={sc} f={Math.max(0, f)} />
            </g>
          );
        })}
      </svg>
      {/* Header in HTML, not SVG <text>: an un-clipped SVG <text> rasterized
          only halfway in parallel render and flickered — stills looked fine
          and hid the bug. */}
      <div style={{ position: "absolute", left: 72, top: board.split ? 54 : 274, fontFamily: HAND, fontSize: 58, fontWeight: 700, color: YEL, opacity: 0.95, whiteSpace: "nowrap" }}>{board.title ?? ""}</div>
      <div style={{ position: "absolute", right: 70, top: board.split ? 72 : 292, fontFamily: HAND, fontSize: 38, color: CHALK, opacity: 0.6, whiteSpace: "nowrap" }}>{board.sub ?? ""}</div>
    </AbsoluteFill>
  );
};

/* ───────────────────── screenshot + highlighter sweep ─────────────────────
 * A user-supplied screenshot (board.src, a registered "image" asset) held
 * full-bleed with a slow pan/zoom, and a highlighter path that sweeps in
 * over the region you're citing on a cue word. `board.label`/`board.sub`
 * are the attribution pill — write your own source and date per video;
 * nothing here is hardcoded. */
export const ScreenshotBoard: React.FC<{ board: Board; frame: number }> = ({ board, frame }) => {
  const sc = board.scenes[0];
  const f = frame - board.fromF;
  const m = board.marker;
  const fMark = m ? wf(sc, m.word, Math.round(board.durF * 0.4)) : 0;
  const ty = interpolate(f, [0, board.durF], [-40, -90]);
  const s = interpolate(f, [0, board.durF], [1, 1.06]);
  const mk = m ? prog(f, fMark, 14) : 0;
  const pill = prog(f, 10, 8);
  return (
    <AbsoluteFill style={{ background: "#0A0A0B", overflow: "hidden" }}>
      <div style={{ position: "absolute", left: 0, top: 0, width: 1080, transform: `translateY(${ty}px) scale(${s})`, transformOrigin: "50% 30%" }}>
        <MediaImg src={asset(board.src ?? "")} style={{ width: 1080, height: "auto", display: "block" }} />
        {m && mk > 0 ? (
          <svg width={1080} height={1920} viewBox="0 0 1080 1920" style={{ position: "absolute", inset: 0 }}>
            <path d={`M ${m.x} ${m.y + m.h / 2} C ${m.x + m.w * 0.33} ${m.y + m.h * 0.15}, ${m.x + m.w * 0.66} ${m.y + m.h * 0.85}, ${m.x + m.w} ${m.y + m.h / 2}`}
                  fill="none" stroke="#FFE034" strokeWidth={Math.max(24, m.h * 0.7)} strokeLinecap="round"
                  pathLength={1} strokeDasharray={1} strokeDashoffset={1 - mk} style={{ mixBlendMode: "multiply" }} opacity={0.62} />
          </svg>
        ) : null}
      </div>
      <AbsoluteFill style={{ boxShadow: "inset 0 0 220px rgba(0,0,0,0.55)" }} />
      {board.label ? (
        <div style={{ position: "absolute", top: 150, left: 62, transform: `translateY(${(1 - pill) * -40}px)`, opacity: pill,
                      background: "#0A0A0B", padding: "12px 22px", border: "3px solid #FFC400", borderRadius: 14, display: "inline-block" }}>
          <div style={{ fontFamily: ANTON, fontSize: 30, color: "#FFC400", letterSpacing: 4 }}>{board.label}{board.sub ? ` · ${board.sub}` : ""}</div>
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

/* ───────────────────── a user image as a full board ─────────────────────
 * fit "width": the image enters at `width` px centered, with a slow zoom,
 * and (if `marker` is set) a hand-drawn red box appears around it on cue.
 * fit "pan": the (wide) image is scaled `scale`x and panned left to right
 * over the whole line — for multi-panel diagrams. */
export const ImageBoard: React.FC<{ board: Board; frame: number }> = ({ board, frame }) => {
  const sc = board.scenes[0];
  const f = frame - board.fromF;
  const src = board.src ?? "";
  const label = prog(f, 6, 8);
  const pill = (
    <div style={{ position: "absolute", top: board.fit === "pan" ? 150 : 310, left: 62, transform: `translateY(${(1 - label) * -40}px)`, opacity: label,
                  background: "#0A0A0B", padding: "12px 22px", border: "3px solid #FFC400", borderRadius: 14, display: "inline-block" }}>
      <div style={{ fontFamily: ANTON, fontSize: 30, color: "#FFC400", letterSpacing: 4 }}>{board.label ?? ""}</div>
    </div>
  );
  if (board.fit === "pan") {
    const S = board.scale ?? 2;
    const H = 733 * S;
    const pct = interpolate(f, [8, board.durF - 8], [0, 100], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    return (
      <AbsoluteFill style={{ background: "#0A0A0B", overflow: "hidden" }}>
        <MediaImg src={asset(src)} style={{ position: "absolute", left: 0, top: 260, width: 1080, height: H, objectFit: "cover", objectPosition: `${pct}% 50%`, display: "block" }} />
        <AbsoluteFill style={{ boxShadow: "inset 0 0 220px rgba(0,0,0,0.6)" }} />
        {pill}
      </AbsoluteFill>
    );
  }
  const W0 = board.width ?? 1000;
  const W = W0 * interpolate(f, [0, board.durF], [1, 1.05]);
  const mk = board.marker ? prog(f, wf(sc, board.marker.word, 40), 14) : 0;
  return (
    <AbsoluteFill style={{ background: "#0A0A0B", overflow: "hidden" }}>
      <div style={{ position: "absolute", left: 0, right: 0, top: 0, height: 1920, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <MediaImg src={asset(src)} style={{ width: W, height: "auto", display: "block", borderRadius: 22, boxShadow: "0 30px 80px rgba(0,0,0,0.7)" }} />
      </div>
      {board.marker && mk > 0 ? (
        <svg width={1080} height={1920} viewBox="0 0 1080 1920" style={{ position: "absolute", inset: 0 }}>
          <path d={rectPath(board.marker.x, board.marker.y, board.marker.w, board.marker.h, 18)} fill="none" stroke="#FF4D4D" strokeWidth={9}
                strokeLinecap="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - mk} opacity={0.95} />
        </svg>
      ) : null}
      <AbsoluteFill style={{ boxShadow: "inset 0 0 220px rgba(0,0,0,0.6)" }} />
      {pill}
    </AbsoluteFill>
  );
};

/* ───────────────────── top band, a video sized to fit ─────────────────────
 * The asset already comes sized to the band (1080x1100) with any pan/zoom
 * baked in: a <Video> larger than the canvas double-buffers in the Lana
 * render and object-fit doesn't apply there. Marker boxes are hand-drawn on
 * cue words. */
export const BAND_H = 1100;
export const BandBoard: React.FC<{ board: Board; frame: number }> = ({ board, frame }) => {
  const f = frame - board.fromF;
  const label = prog(f, 6, 8);
  const findWord = (word: string) => {
    for (const sc of board.scenes) {
      const hit = sc.words.find((w) => norm(w.text) === norm(word));
      if (hit) return hit.f - board.fromF;
    }
    return 40;
  };
  return (
    <div style={{ position: "absolute", left: 0, top: 0, width: 1080, height: BAND_H, overflow: "hidden", background: "#0A0A0B" }}>
      <Video src={asset(board.src ?? "")} volume={0} style={{ position: "absolute", left: 0, top: 0, width: 1080, height: BAND_H, display: "block" }} />
      <svg width={1080} height={BAND_H} viewBox={`0 0 1080 ${BAND_H}`} style={{ position: "absolute", inset: 0 }}>
        {(board.markers ?? []).map((m, i) => {
          const mk = prog(f, findWord(m.word), 14);
          return mk <= 0 ? null : (
            <path key={i} d={rectPath(m.x, m.y, m.w, m.h, 18)} fill="none" stroke="#FF4D4D" strokeWidth={9}
                  strokeLinecap="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - mk} opacity={0.95} />
          );
        })}
      </svg>
      {(board.markers ?? []).map((m, i) => (
        <Sequence key={`mk${i}`} from={board.fromF + findWord(m.word)} durationInFrames={20}><SfxAudio moment="marker" nth={i} /></Sequence>
      ))}
      <div style={{ position: "absolute", inset: 0, boxShadow: "inset 0 0 160px rgba(0,0,0,0.55)" }} />
      <div style={{ position: "absolute", top: 14, left: 40, transform: `translateY(${(1 - label) * -40}px)`, opacity: label,
                    background: "#0A0A0B", padding: "10px 20px", border: "3px solid #FFC400", borderRadius: 14, display: "inline-block" }}>
        <div style={{ fontFamily: ANTON, fontSize: 28, color: "#FFC400", letterSpacing: 4 }}>{board.label ?? ""}</div>
      </div>
    </div>
  );
};

export const BoardView: React.FC<{ board: Board; frame: number }> = ({ board, frame }) =>
  board.kind === "band" ? <BandBoard board={board} frame={frame} />
  : board.kind === "screenshot" ? <ScreenshotBoard board={board} frame={frame} />
  : board.kind === "image" ? <ImageBoard board={board} frame={frame} />
  : <ChalkBoard board={board} frame={frame} />;
