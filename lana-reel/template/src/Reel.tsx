import React from "react";
import {
  AbsoluteFill, Audio, Sequence, interpolate, random, spring,
  useCurrentFrame, useVideoConfig,
} from "remotion";
import { Video } from "@remotion/media";
import { loadFont } from "@remotion/google-fonts/Anton";
import { asset } from "./assets";
import { CaptionsBlock } from "./Captions";
import { KeywordGraphics } from "./Graphics";
import { BoardView } from "./Boards";
import { getFonts, fontsFor, useFontFiles, fs, type FontSet } from "./Fonts";
import { SfxProvider, SfxAudio, SfxAt } from "./Sfx";
import type { Plan, Ritmo, Gfx } from "./types";

export type { Plan, Ritmo, Gfx };

const { fontFamily } = loadFont();
export const FPS = 30;
// Final air: frames that keep running after the last word. 10 f = 333 ms at
// 30 fps. With 0 the reel cut on the last phoneme and read as "unfinished"
// even when the idea itself had landed. Not a freeze: the air is the last
// take running MUTED, which is what avoids both the ugly freeze frame and
// the silence that trips `silencedetect`. Tunable per video via the plan:
// "hold_f": <frames>.
export const HOLD_F = 10;
export const holdFrames = (p: { hold_f?: number }): number =>
  Math.max(0, Math.round(p.hold_f ?? HOLD_F));
const GLITCH_LEN = 14;
const PUNCH_F = 40;                // sustained reframe for ~1.3s after a cut
const SWISH_HALF = 5;              // 5 frames each side of the cut (~0.33s total)
const XW_HALF = 6;                 // crosswarp: 6 frames each side (0.4s total)
// Split screen: a 1100px band at the top for the illustrating material, the
// speaker below. The source rows shown at scale 1 are configurable per
// project (a talking-head close-up usually frames the face around rows
// 400..1220); captions move to the top band (y=930) while split is active,
// never over the face.
const SPLIT_TOP = 1100;
const SPLIT_SRC_Y = 400;
const SPLIT_CAP_TOP = 930;

/* ─────────── Word-by-word title break ─────────── */
export const TitleBreak: React.FC<{ words: { text: string; ms: number }[]; startMs: number; sub?: string | null; subMs?: number | null; lift?: number; fonts?: FontSet }> = ({ words, startMs, sub, subMs, lift = 0, fonts }) => {
  const F = fonts ?? getFonts();
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const fSub = sub && subMs != null ? Math.round(((subMs - startMs) / 1000) * fps) : null;
  const pSub = fSub != null ? spring({ frame: frame - fSub, fps, durationInFrames: 6, config: { damping: 16, stiffness: 300 } }) : 0;
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", pointerEvents: "none", transform: `translateY(${-lift}px)` }}>
      <div style={{ ...fs(F.display, 118), lineHeight: 1.08, color: "#F2E3C9", textAlign: "center", maxWidth: 960, textShadow: "0 6px 30px rgba(0,0,0,0.75)", display: "flex", flexWrap: "wrap", justifyContent: "center", columnGap: 28 }}>
        {words.map((w, i) => {
          const f0 = Math.round(((w.ms - startMs) / 1000) * fps);
          if (frame < f0) return null;
          const p = spring({ frame: frame - f0, fps, durationInFrames: 4, config: { damping: 20, stiffness: 400 } });
          return <span key={i} style={{ display: "inline-block", transform: `scale(${0.85 + 0.15 * p})` }}>{w.text}</span>;
        })}
      </div>
      {sub && fSub != null && frame >= fSub ? (
        <div style={{ marginTop: 26, ...fs(F.accent, 54), color: "#FFC400", textAlign: "center", maxWidth: 960, textShadow: "0 6px 24px rgba(0,0,0,0.8)", transform: `translateY(${(1 - pSub) * 30}px) scale(${0.9 + 0.1 * pSub})`, opacity: pSub }}>{sub}</div>
      ) : null}
    </AbsoluteFill>
  );
};

/* ─────────── Hook banner: slams in at frame 0 ─────────── */
export const HookBanner: React.FC<{ text: string; tag: string; fonts?: FontSet }> = ({ text, tag, fonts }) => {
  const F = fonts ?? getFonts();
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const p = spring({ frame, fps, durationInFrames: 8, config: { damping: 15, stiffness: 300 } });
  const out = interpolate(frame, [durationInFrames - 5, durationInFrames], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div style={{
        position: "absolute", top: 146, left: 0, right: 0,
        transform: `translateY(${(1 - p) * -120}px) skewY(${(1 - p) * -2}deg)`, opacity: out,
      }}>
        <div style={{ background: "#FFC400", padding: "22px 30px", transform: "rotate(-1.4deg)", boxShadow: "0 18px 50px rgba(0,0,0,0.55)" }}>
          <div style={{ ...fs(F.display, 74), lineHeight: 1, color: "#0A0A0B", textAlign: "center" }}>{text}</div>
        </div>
        <div style={{ marginTop: 12, marginLeft: 62, display: "inline-block", background: "#0A0A0B", padding: "8px 18px", transform: "rotate(-1.4deg)" }}>
          <div style={{ ...fs(F.accent, 27), color: "#FFC400" }}>{tag}</div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* ─────────── News-ticker lower third ─────────── */
const LT_F = 108;
const LowerThird: React.FC<{ num: string; text: string }> = ({ num, text }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pin = spring({ frame, fps, durationInFrames: 10, config: { damping: 16, stiffness: 260 } });
  const pout = interpolate(frame, [LT_F - 8, LT_F], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const x = (1 - pin) * -1100 + pout * -1100;
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div style={{ position: "absolute", top: 150, left: 0, display: "flex", alignItems: "stretch", transform: `translateX(${x}px) skewX(-6deg)`, filter: `blur(${(1 - pin) * 10 + pout * 10}px)` }}>
        <div style={{ background: "#FFC400", width: 128, display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 18px 50px rgba(0,0,0,0.55)" }}>
          <div style={{ fontFamily, fontSize: 96, color: "#0A0A0B", lineHeight: 1, transform: "skewX(6deg)" }}>{num}</div>
        </div>
        <div style={{ background: "#0A0A0B", padding: "0 40px 0 30px", display: "flex", alignItems: "center", boxShadow: "0 18px 50px rgba(0,0,0,0.55)", borderRight: "6px solid #FFC400" }}>
          <div style={{ fontFamily, fontSize: 40, color: "#F2E3C9", letterSpacing: 2, textTransform: "uppercase", whiteSpace: "nowrap", transform: "skewX(6deg)" }}>{text}</div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* CROSSWARP — the real transition.
 * Unlike the glitch or the whip pan (an effect ON TOP of a hard cut), here
 * both shots exist at once: the outgoing take runs a few frames past its
 * cut and the incoming one starts a few frames early. Both stretch in
 * opposite directions while one dissolves over the other. The cut stops
 * existing: one image turns into the other. */
const CrossWarp: React.FC<{ src: string; mirror?: boolean; c: NonNullable<Ritmo["crosswarp"]>[number] }> = ({ src, mirror, c }) => {
  const frame = useCurrentFrame();
  const p = Math.min(1, Math.max(0, frame / (XW_HALF * 2)));
  const ease = p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
  const SHIFT = 520, STRETCH = 0.6, BLUR = 16;
  const d = c.dir;
  const flip = mirror ? "scaleX(-1) " : "";
  return (
    <AbsoluteFill>
      {/* incoming: arrives stretched from the other side and settles */}
      <AbsoluteFill style={{
        transform: `translateX(${d * SHIFT * (1 - ease)}px) scaleX(${1 + STRETCH * (1 - ease)})`,
        filter: `blur(${BLUR * (1 - ease)}px)`,
      }}>
        <Video src={asset(c.inSrc ?? src)} trimBefore={Math.max(0, c.inFromF - XW_HALF)}
               trimAfter={c.inFromF + XW_HALF + 2} volume={0}
               style={{ width: "100%", height: "100%", objectFit: "cover", transform: flip || undefined }} />
      </AbsoluteFill>
      {/* outgoing: stretches the other way and fades out on top */}
      <AbsoluteFill style={{
        opacity: 1 - ease,
        transform: `translateX(${-d * SHIFT * ease}px) scaleX(${1 + STRETCH * ease})`,
        filter: `blur(${BLUR * ease}px)`,
      }}>
        <Video src={asset(c.outSrc ?? src)} trimBefore={Math.max(0, c.outFromF - XW_HALF)}
               trimAfter={c.outFromF + XW_HALF + 2} volume={0}
               style={{ width: "100%", height: "100%", objectFit: "cover", transform: flip || undefined }} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

/* White flash for 2 frames as each clip enters: reads as a stack of cuts,
 * not a fade. */
const InsertFlash: React.FC = () => {
  const frame = useCurrentFrame();
  const op = interpolate(frame, [0, 2], [0.75, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return op > 0 ? <AbsoluteFill style={{ backgroundColor: "#fff", opacity: op, pointerEvents: "none" }} /> : null;
};

/* ─────────── Closing plate (blinking IG glyph) ─────────── */
const IgGlyph: React.FC<{ color: boolean }> = ({ color }) => (
  <svg width="190" height="190" viewBox="0 0 24 24" fill="none">
    <defs><linearGradient id="igg" x1="0" y1="1" x2="1" y2="0">
      <stop offset="0" stopColor="#F9CE34" /><stop offset="0.5" stopColor="#EE2A7B" /><stop offset="1" stopColor="#6228D7" />
    </linearGradient></defs>
    <rect x="2.5" y="2.5" width="19" height="19" rx="5.5" stroke={color ? "url(#igg)" : "#fff"} strokeWidth="1.8" />
    <circle cx="12" cy="12" r="4.3" stroke={color ? "url(#igg)" : "#fff"} strokeWidth="1.8" />
    <circle cx="17.4" cy="6.6" r="1.1" fill={color ? "#EE2A7B" : "#fff"} />
  </svg>
);
const ClosingPlate: React.FC = () => {
  const frame = useCurrentFrame();
  const color = Math.floor(frame / 30) % 2 === 1;
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <AbsoluteFill style={{ backgroundColor: "rgba(0,0,0,0.72)" }} />
      <div style={{ position: "absolute", top: 520, left: 0, right: 0, display: "flex", justifyContent: "center" }}><IgGlyph color={color} /></div>
    </AbsoluteFill>
  );
};

/* ─────────── Assembly ─────────── */
export const Reel: React.FC<{ plan: Plan; ritmo: Ritmo; gfx: Gfx[] }> = ({ plan, ritmo, gfx }) => {
  const frame = useCurrentFrame();
  useFontFiles();
  const fonts = fontsFor(ritmo.fonts);
  const flip = plan.mirror ? "scaleX(-1) " : "";

  let punchScale = 1;
  for (const pu of ritmo.punch) {
    const f0 = Math.round((pu.ms / 1000) * FPS);
    if (frame >= f0 && frame < f0 + PUNCH_F) punchScale = 1.32;
  }
  // Whip pan: the image sweeps out to one side and the next sweeps in from
  // the other. The hard cut is HIDDEN inside the blur, exactly the way it's
  // done in editing: it's not an effect on top of the cut, the cut is the
  // movement.
  let swX = 0, swBlur = 0, swSX = 1;
  for (const sw of (ritmo.swish ?? [])) {
    const f0 = Math.round((sw.ms / 1000) * FPS) - SWISH_HALF;
    const f1 = f0 + SWISH_HALF * 2;
    if (frame >= f0 && frame < f1) {
      const p = (frame - f0) / (f1 - f0);
      const amt = Math.sin(Math.PI * p);
      const dir = sw.dir ?? -1;
      swX = (p < 0.5 ? -p * 2 : (1 - p) * 2) * 190 * dir * (p < 0.5 ? 1 : -1);
      swBlur = 26 * amt;
      swSX = 1 + 0.2 * amt;
    }
  }

  // Boards (screenshot / chalk): the full frame enters with a crosswarp. The
  // base video is the outgoing shot on entry and the incoming shot on exit:
  // it gets its half of the warp here; the board gets the other half below.
  const XW_SHIFT = 520, XW_STRETCH = 0.6, XW_BLUR = 16;
  const easeIO = (p: number) => (p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2);
  let bdX = 0, bdSX = 1, bdBlur = 0, inBoard = false;
  const boardFx: { b: NonNullable<Plan["boards"]>[number]; op: number; x: number; sx: number; blur: number; y: number }[] = [];
  // sp: how much "split screen" is active this frame (0 = full frame). One
  // window for the hookVideo, one per split board. XW_HALF-frame ramps on
  // each side, except frame 0 (the hook starts already split).
  let sp = 0;
  const splitWins: { f0: number; f1: number }[] = [];
  if (plan.hookVideo && !plan.hookVideo.full) splitWins.push({ f0: 0, f1: plan.hookVideo.durF });
  for (const b of (plan.boards ?? [])) if (b.split) splitWins.push({ f0: b.fromF, f1: b.fromF + b.durF });
  for (const w of splitWins) {
    const a0 = w.f0 - XW_HALF, a1 = w.f0 + XW_HALF, z0 = w.f1 - XW_HALF, z1 = w.f1 + XW_HALF;
    if (frame < a0 || frame >= z1) continue;
    let e = 1;
    if (w.f0 === 0 && frame < a1) e = 1;
    else if (frame < a1) e = easeIO((frame - a0) / (a1 - a0));
    else if (frame >= z0) e = 1 - easeIO((frame - z0) / (z1 - z0));
    sp = Math.max(sp, e);
  }
  for (const b of (plan.boards ?? [])) {
    const a0 = b.fromF - XW_HALF, a1 = b.fromF + XW_HALF;
    const z0 = b.fromF + b.durF - XW_HALF, z1 = b.fromF + b.durF + XW_HALF;
    if (frame < a0 || frame >= z1) continue;
    inBoard = frame >= b.fromF && frame < b.fromF + b.durF;
    const d = b.dir;
    if (b.split) {
      // in the band: crossfade + slide down from above; the base video
      // doesn't warp, the split screen sliding in IS the transition
      const e = frame < a1 ? easeIO((frame - a0) / (a1 - a0)) : frame >= z0 ? 1 - easeIO((frame - z0) / (z1 - z0)) : 1;
      boardFx.push({ b, op: e, x: 0, sx: 1, blur: 0, y: -140 * (1 - e) });
      continue;
    }
    if (frame < a1) {                                   // entering: base exits
      const e = easeIO((frame - a0) / (a1 - a0));
      bdX = -d * XW_SHIFT * e; bdSX = 1 + XW_STRETCH * e; bdBlur = XW_BLUR * e;
      boardFx.push({ b, op: e, x: d * XW_SHIFT * (1 - e), sx: 1 + XW_STRETCH * (1 - e), blur: XW_BLUR * (1 - e), y: 0 });
    } else if (frame >= z0) {                           // leaving: base enters
      const e = easeIO((frame - z0) / (z1 - z0));
      bdX = d * XW_SHIFT * (1 - e); bdSX = 1 + XW_STRETCH * (1 - e); bdBlur = XW_BLUR * (1 - e);
      boardFx.push({ b, op: 1 - e, x: -d * XW_SHIFT * e, sx: 1 + XW_STRETCH * e, blur: XW_BLUR * e, y: 0 });
    } else {
      boardFx.push({ b, op: 1, x: 0, sx: 1, blur: 0, y: 0 });
    }
  }

  let bwAmt = 0, flash = 0;
  for (const w of ritmo.bw) {
    const f0 = Math.round((w.ms / 1000) * FPS), f1 = Math.round((w.endMs / 1000) * FPS);
    if (frame >= f0 && frame < f1) bwAmt = 1;
    for (const fb of [f0, f1]) {
      if (frame >= fb) flash = Math.max(flash, interpolate(frame, [fb, fb + 3], [0.9, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
    }
  }
  // While an inserted clip plays, keyword cards are from ANOTHER section and
  // would cover someone else's material — hide by opacity (never unmount,
  // so the entrance sound doesn't re-fire on return).
  const inInsert = (plan.inserts ?? []).some((it) => frame >= it.fromF && frame < it.fromF + it.durF);
  const hookEndF = Math.round((ritmo.hookEndMs / 1000) * FPS);
  const closingF = Math.round((ritmo.closingMs / 1000) * FPS);
  const hold = holdFrames(plan);
  const totalF = plan.total + hold;
  // The plan's last take: during the final air it keeps running, muted.
  const lastSeg = plan.segments.length
    ? plan.segments.reduce((a, b) => (b.globalF + b.durF >= a.globalF + a.durF ? b : a))
    : null;

  return (
    <SfxProvider value={ritmo.sfx ?? {}}>
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {/* Split screen: the base video is clipped to the bottom band and
          slides down until its own rows [SPLIT_SRC_Y..] land in
          [SPLIT_TOP..1920]. */}
      <AbsoluteFill style={{ clipPath: sp > 0.001 ? `inset(${SPLIT_TOP * sp}px 0 0 0)` : undefined }}>
      <AbsoluteFill style={{ transform: sp > 0.001 ? `translateY(${(SPLIT_TOP - SPLIT_SRC_Y) * sp}px)` : undefined }}>
      <AbsoluteFill style={{
        transformOrigin: "58% 40%",
        transform: `${flip}scale(${punchScale}) translateX(${swX + bdX}px) scaleX(${swSX * bdSX})`,
        filter: [
          bwAmt > 0.01 ? `grayscale(${bwAmt}) contrast(${1 + 0.1 * bwAmt})` : "",
          swBlur > 0.4 ? `blur(${swBlur}px)` : "",
          bdBlur > 0.4 ? `blur(${bdBlur}px)` : "",
        ].filter(Boolean).join(" ") || undefined,
      }}>
        {plan.segments.map((s, i) => (
          <Sequence key={i} from={s.globalF} durationInFrames={s.durF}>
            <Video src={asset(s.src ?? plan.src)} trimBefore={s.fromF} trimAfter={s.fromF + Math.ceil(s.durF * (s.rate ?? 1)) + 1}
                   playbackRate={s.rate ?? 1} volume={1}
                   style={{ width: "100%", height: "100%", objectFit: "cover" }} />
          </Sequence>
        ))}
        {/* Final air: the take keeps running, MUTED (no freeze, no last-frame
            still). This is where the 150ms tail of the last caption page
            lands — with HOLD_F = 0 it used to get truncated on the cut. */}
        {hold > 0 && lastSeg ? (
          <Sequence from={plan.total} durationInFrames={hold}>
            <Video src={asset(lastSeg.src ?? plan.src)}
                   trimBefore={lastSeg.fromF + Math.ceil(lastSeg.durF * (lastSeg.rate ?? 1))}
                   playbackRate={lastSeg.rate ?? 1} volume={0}
                   style={{ width: "100%", height: "100%", objectFit: "cover" }} />
          </Sequence>
        ) : null}
      </AbsoluteFill>
      </AbsoluteFill>
      </AbsoluteFill>

      {/* Top band of the hook: a clip at exactly the speed needed to last as
          long as the spoken line. */}
      {plan.hookVideo ? (
        <Sequence from={0} durationInFrames={plan.hookVideo.durF}>
          {/* full: the hook clip covers the whole frame (the base video's
              audio keeps playing) */}
          <div style={{ position: "absolute", left: 0, top: 0, width: 1080, height: plan.hookVideo.full ? 1920 : SPLIT_TOP, overflow: "hidden", background: "#000" }}>
            <Video src={asset(plan.hookVideo.src)} trimBefore={0} trimAfter={Math.ceil(plan.hookVideo.durF * plan.hookVideo.rate) + 1}
                   playbackRate={plan.hookVideo.rate} volume={0}
                   style={{ position: "absolute", left: 0, top: plan.hookVideo.full ? 0 : -(plan.hookVideo.srcY ?? 0), width: 1080, height: 1920, display: "block" }} />
          </div>
        </Sequence>
      ) : null}
      {/* yellow rule between the two bands */}
      {sp > 0.001 ? <div style={{ position: "absolute", left: 0, right: 0, top: SPLIT_TOP - 3, height: 6, background: "#FFC400", opacity: sp }} /> : null}

      {plan.voice ? <Audio src={asset(plan.voice)} /> : null}

      {/* Crosswarp: sits over the base video (covers the hard cut below) but
          under captions and graphics. No audio of its own: the base video's
          audio keeps going. */}
      {(ritmo.crosswarp ?? []).map((c, i) => (
        <Sequence key={`xw${i}`} from={c.atF - XW_HALF} durationInFrames={XW_HALF * 2}>
          <CrossWarp src={plan.src} mirror={plan.mirror} c={c} />
          <SfxAudio moment="transition" nth={i} />
        </Sequence>
      ))}

      {/* Inserted clips (other people's material) in a burst: sit OVER the
          base video but OUTSIDE the punch wrapper, so a reframe never moves
          them. Own audio underneath — the host's voice still leads. */}
      {(plan.inserts ?? []).map((it, i) => (
        <Sequence key={`ins${i}`} from={it.fromF} durationInFrames={it.durF}>
          <AbsoluteFill style={{ backgroundColor: "#000" }}>
            {it.crop ? (
              /* background: the same clip zoomed and blurred, so the crop
                 doesn't float over black */
              <AbsoluteFill style={{ transform: `scale(${it.bgZoom ?? 3})`, filter: "blur(26px) brightness(0.5)" }}>
                <Video src={asset(it.src)} trimBefore={Math.round(it.fromS * FPS)}
                       trimAfter={Math.round(it.fromS * FPS) + it.durF} volume={0}
                       style={{ width: "100%", height: "100%", objectFit: "cover" }} />
              </AbsoluteFill>
            ) : null}
            <AbsoluteFill style={it.crop
              ? { clipPath: `inset(${it.crop.top}px ${it.crop.right}px ${it.crop.bottom}px ${it.crop.left}px)` }
              : undefined}>
              <Video
                src={asset(it.src)}
                trimBefore={Math.round(it.fromS * FPS)}
                trimAfter={Math.round(it.fromS * FPS) + it.durF}
                volume={0}   /* other people's clips carry NO audio: only the host's voice plays */
                style={{ width: "100%", height: "100%", objectFit: "cover" }}
              />
            </AbsoluteFill>
          </AbsoluteFill>
          <InsertFlash />
        </Sequence>
      ))}

      {/* Boards: full frame with their half of the crosswarp. The whoosh
          plays on both edges. */}
      {boardFx.map(({ b, op, x, sx, blur, y }, i) => b.split ? (
        <div key={`bd${i}`} style={{ position: "absolute", left: 0, top: 0, width: 1080, height: SPLIT_TOP, overflow: "hidden", opacity: op, transform: `translateY(${y}px)` }}>
          <BoardView board={b} frame={frame} />
        </div>
      ) : (
        <AbsoluteFill key={`bd${i}`} style={{ opacity: op, transform: `translateX(${x}px) scaleX(${sx})`, filter: blur > 0.4 ? `blur(${blur}px)` : undefined }}>
          <BoardView board={b} frame={frame} />
        </AbsoluteFill>
      ))}
      {(plan.boards ?? []).flatMap((b, i) => [b.fromF, b.fromF + b.durF].map((F, k) => (
        <Sequence key={`bdw${i}-${k}`} from={F - XW_HALF} durationInFrames={XW_HALF * 2 + 3}>
          <SfxAudio moment="board" nth={i * 2 + k} />
        </Sequence>
      )))}

      {ritmo.captions === "none" ? null : <CaptionsBlock words={plan.captions} suppress={ritmo.titles} splitWins={splitWins} splitTop={SPLIT_CAP_TOP} font={fonts.captions.display} />}
      <AbsoluteFill style={{ opacity: inInsert || inBoard ? 0 : 1, pointerEvents: "none" }}>
        <KeywordGraphics gfx={gfx} fps={FPS} />
      </AbsoluteFill>

      {flash > 0 && <AbsoluteFill style={{ backgroundColor: "#fff", opacity: flash, pointerEvents: "none" }} />}

      {ritmo.hookBanner ? (
        <Sequence from={0} durationInFrames={hookEndF}>
          <HookBanner text={ritmo.hookBanner} tag={ritmo.hookTag} fonts={fonts.hook} />
          <SfxAudio moment="title" />
        </Sequence>
      ) : null}

      {ritmo.closingStyle === "none" ? null : (
        <Sequence from={closingF} durationInFrames={totalF - closingF}>
          <ClosingPlate />
        </Sequence>
      )}

      {(ritmo.lowerthirds ?? []).map((lt, i) => (
        <Sequence key={`lt${i}`} from={Math.round((lt.ms / 1000) * FPS)} durationInFrames={LT_F}>
          <LowerThird num={lt.num} text={lt.text} />
          <SfxAudio moment="lowerthird" nth={i} />
        </Sequence>
      ))}

      {ritmo.titles.map((ti, i) => <SfxAt key={`ts${i}`} moment={i === 0 && ritmo.sfx?.map?.hook ? "hook" : "title"} atF={Math.round((ti.ms / 1000) * FPS)} nth={i} />)}
      <SfxAt moment="closing" atF={closingF} />
      {ritmo.titles.map((ti, i) => (
        <Sequence key={`t${i}`} from={Math.round((ti.ms / 1000) * FPS)}
                  durationInFrames={Math.max(12, Math.round(((ti.endMs - ti.ms) / 1000) * FPS))}>
          <TitleBreak words={ti.words} startMs={ti.ms} sub={ti.sub} subMs={ti.subMs} lift={ritmo.titleLift ?? 0} fonts={fonts.titles} />
        </Sequence>
      ))}

      {(ritmo.swish ?? []).map((sw, i) => (
        <Sequence key={`sw${i}`} from={Math.round((sw.ms / 1000) * FPS) - SWISH_HALF}
                  durationInFrames={SWISH_HALF * 2 + 3}>
          <SfxAudio moment="whip" nth={i} />
        </Sequence>
      ))}

      {ritmo.glitch.map((g, i) => (
        <Sequence key={`g${i}`} from={Math.round((g.ms / 1000) * FPS) - 4} durationInFrames={GLITCH_LEN}>
          <GlitchOverlay />
          <SfxAudio moment="glitch" nth={i} />
        </Sequence>
      ))}

    </AbsoluteFill>
    </SfxProvider>
  );
};

/* ─────────── Glitch transition ─────────── */
const GlitchOverlay: React.FC = () => {
  const frame = useCurrentFrame();
  const amp = interpolate(frame, [0, 4, 9, GLITCH_LEN], [0, 26, 14, 0]);
  const bars = 7;
  const flash = interpolate(frame, [4, 6, 8], [0, 0.55, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {Array.from({ length: bars }).map((_, i) => {
        const y = (1920 / bars) * i;
        const dx = (random(`gx${i}-${frame}`) - 0.5) * amp * 2;
        const hue = i % 3 === 0 ? "rgba(255,0,80,0.28)" : i % 3 === 1 ? "rgba(0,229,255,0.28)" : "rgba(255,255,255,0.12)";
        return <div key={i} style={{ position: "absolute", top: y, left: 0, right: 0, height: 1920 / bars, background: hue, transform: `translateX(${dx}px) skewX(${(random(`gs${i}-${frame}`) - 0.5) * 6}deg)`, mixBlendMode: "screen", opacity: amp > 2 ? 1 : 0 }} />;
      })}
      <AbsoluteFill style={{ background: "repeating-linear-gradient(0deg, rgba(0,0,0,0.35) 0px, rgba(0,0,0,0.35) 3px, transparent 3px, transparent 7px)", opacity: amp > 2 ? 0.6 : 0 }} />
      <AbsoluteFill style={{ backgroundColor: "#fff", opacity: flash }} />
    </AbsoluteFill>
  );
};
