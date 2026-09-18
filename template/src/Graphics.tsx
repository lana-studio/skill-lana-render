/* Keyword cards: a small graphic that pops in next to a spoken keyword, or
 * stacks into a burst of chips for an enumeration ("three things changed:
 * ..."). Two kinds only — no brand logos ship with the public template:
 * "image" shows a user asset (purpose=image, registered in
 * project.assets), "text" shows a generic icon. `accent` comes from
 * CONFIG.gfx_accents (per-keyword hex, set by the agent in videoconfig.py);
 * default "#FFC400" if the video's config doesn't set one for a keyword. */
import { Sequence, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { loadFont } from "@remotion/google-fonts/Anton";
import { MediaImg } from "./assets";
import { SfxAudio } from "./Sfx";
import type { Gfx } from "./types";

export type { Gfx };

const { fontFamily } = loadFont();
const MONO = "ui-monospace, SFMono-Regular, Menlo, monospace";
const DEFAULT_ACCENT = "#FFC400";

const HOLD_F = 72;      // 2.4s on screen
const CARD = 300;

/* Left column, above the board band: never crosses into the subject (x>400)
 * nor into Instagram's own chrome (profile bar y<150, icons x>900/y>500,
 * caption y>1680). Alternates high/low so it doesn't read as static. */
const posFor = (slot: number) => ({ top: slot % 2 === 0 ? 322 : 672, left: 62 });

const Shell: React.FC<{ children: React.ReactNode; accent: string }> = ({ children, accent }) => (
  <div style={{
    position: "relative",   // without this, the card's absolutely-positioned
                             // image escapes the rounded corners (overflow
                             // doesn't clip it)
    width: CARD, height: CARD, borderRadius: 34, overflow: "hidden",
    background: "linear-gradient(160deg, rgba(20,20,22,0.96), rgba(8,8,10,0.96))",
    border: `3px solid ${accent}`,
    boxShadow: `0 26px 70px rgba(0,0,0,0.65), 0 0 0 1px rgba(255,255,255,0.06) inset, 0 0 46px ${accent}44`,
    display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 14,
  }}>{children}</div>
);

const Label: React.FC<{ t: string; size?: number; color?: string }> = ({ t, size = 40, color = "#fff" }) => (
  <div style={{ fontFamily, fontSize: size, color, letterSpacing: 1.5, textTransform: "uppercase", textAlign: "center", lineHeight: 1.05, padding: "0 16px" }}>{t}</div>
);
const Sub: React.FC<{ t: string }> = ({ t }) => (
  <div style={{ fontFamily: MONO, fontSize: 20, color: "#8A8F98", letterSpacing: 3, textTransform: "uppercase" }}>{t}</div>
);

const Face: React.FC<{ g: Gfx }> = ({ g }) => {
  const accent = g.accent ?? DEFAULT_ACCENT;

  if (g.kind === "image" && g.asset) {
    return (
      <Shell accent={accent}>
        <MediaImg src={g.asset} style={{ position: "absolute", inset: 0, width: CARD, height: CARD, objectFit: "cover" }} />
        <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: 104, background: "linear-gradient(transparent, rgba(0,0,0,0.55) 40%, rgba(0,0,0,0.94))" }} />
        <div style={{ position: "absolute", left: 0, right: 0, bottom: 18 }}>
          <Label t={g.label} size={38} />
          {g.sub ? <div style={{ textAlign: "center", marginTop: 6 }}><Sub t={g.sub} /></div> : null}
        </div>
      </Shell>
    );
  }

  // text card: a generic marker, the label, and an optional sub-line. Write
  // one call site per video for anything more specific — this is the
  // baseline every keyword card falls back to.
  return (
    <Shell accent={accent}>
      <div style={{ fontSize: 76, color: accent, lineHeight: 1 }}>◆</div>
      <Label t={g.label} size={40} />
      {g.sub ? <Sub t={g.sub} /> : null}
    </Shell>
  );
};

/** Spring in, hard cut out (Reel house style). */
const Pop: React.FC<{ g: Gfx }> = ({ g }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame, fps, durationInFrames: 9, config: { damping: 16, stiffness: 320 } });
  const { top, left } = posFor(g.slot);
  const dir = -1;
  return (
    <div style={{
      position: "absolute", top, left,
      transform: `translateX(${(1 - p) * 90 * dir}px) scale(${0.72 + 0.28 * p}) rotate(${(1 - p) * dir * 5}deg)`,
      opacity: interpolate(p, [0, 0.35], [0, 1], { extrapolateRight: "clamp" }),
    }}>
      <div style={{ position: "relative", width: CARD, height: CARD }}><Face g={g} /></div>
    </div>
  );
};

/* BURST chip: smaller, stacks in the left column and stays until the
 * enumeration ends — reads as a stack, not as loose flashes. Spring in,
 * hard cut out. */
const CHIP = 132;
const StackChip: React.FC<{ g: Gfx }> = ({ g }) => {
  const { fps } = useVideoConfig();
  const frame = useCurrentFrame();
  const p = spring({ frame, fps, durationInFrames: 8, config: { damping: 15, stiffness: 340 } });
  const accent = g.accent ?? DEFAULT_ACCENT;
  if (g.kind === "text") {
    // text chip (enumeration with no image): dark pill with an accent border
    return (
      <div style={{
        position: "absolute", left: 62, top: 322 + g.slot * 118,
        transform: `translateX(${(1 - p) * -70}px) scale(${0.7 + 0.3 * p})`, transformOrigin: "left center",
        opacity: interpolate(p, [0, 0.35], [0, 1], { extrapolateRight: "clamp" }),
        background: "rgba(10,10,12,0.94)", border: `3px solid ${accent}`, borderRadius: 48, padding: "18px 34px",
        boxShadow: `0 18px 44px rgba(0,0,0,0.6), 0 0 30px ${accent}44`,
      }}>
        <div style={{ fontFamily, fontSize: 44, color: "#fff", letterSpacing: 2, textTransform: "uppercase", whiteSpace: "nowrap" }}>
          <span style={{ color: accent, marginRight: 14 }}>▸</span>{g.label}
        </div>
      </div>
    );
  }
  return (
    <div style={{
      position: "absolute", left: 62, top: 322 + g.slot * 148,
      transform: `translateX(${(1 - p) * -70}px) scale(${0.7 + 0.3 * p})`,
      opacity: interpolate(p, [0, 0.35], [0, 1], { extrapolateRight: "clamp" }),
      display: "flex", alignItems: "center", gap: 16,
    }}>
      <div style={{
        width: CHIP, height: CHIP, borderRadius: 30, background: "#fff",
        display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden",
        boxShadow: `0 18px 44px rgba(0,0,0,0.6), 0 0 0 3px ${accent}`,
      }}>
        {g.asset ? <MediaImg src={g.asset} style={{ width: CHIP, height: CHIP, objectFit: "cover" }} /> : null}
      </div>
    </div>
  );
};

export const KeywordGraphics: React.FC<{ gfx: Gfx[]; fps: number }> = ({ gfx, fps }) => (
  <>
    {gfx.map((g, gi) => {
      const from = Math.round((g.ms / 1000) * fps);
      const dur = g.mode === "stack"
        ? Math.max(12, Math.round(((g.stackEndMs ?? g.ms + 1800) - g.ms) / 1000 * fps))
        : HOLD_F;
      return (
        <Sequence key={g.slug + g.ms} from={from} durationInFrames={dur}>
          {g.mode === "stack" ? <StackChip g={g} /> : <Pop g={g} />}
          <SfxAudio moment={g.mode === "stack" ? "stack" : "card"} nth={gi} />
        </Sequence>
      );
    })}
  </>
);
