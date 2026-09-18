import { useMemo } from "react";
import { Sequence, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { Caption } from "@remotion/captions";
import { createTikTokStyleCaptions } from "@remotion/captions";
import { loadFont } from "@remotion/google-fonts/Anton";
import { fs, type FontFace } from "./Fonts";

const { fontFamily } = loadFont();
const YELLOW = "#FFC400";

/** Glues loose punctuation onto the previous word. Do NOT strip the leading
 *  space on every token except the first — that's what
 *  `createTikTokStyleCaptions` uses to paginate. */
const cleanWords = (ws: Caption[]): Caption[] => {
  const out: Caption[] = [];
  for (const w of ws) {
    const t = w.text.trim();
    if (out.length && /^[.,;:¿?¡!…"'()-]+$/.test(t)) {
      const p = out[out.length - 1];
      p.text += t;
      p.endMs = w.endMs;
    } else out.push({ ...w });
  }
  return out;
};

const Outlined: React.FC<{ text: string; color: string; stroke?: number }> = ({ text, color, stroke = 13 }) => (
  <span style={{ position: "relative", display: "inline-block", marginRight: 15 }}>
    <span aria-hidden style={{ position: "absolute", inset: 0, color: "#000", WebkitTextStroke: `${stroke + 2}px #000`, transform: "translate(5px,5px)" }}>{text}</span>
    <span aria-hidden style={{ position: "absolute", inset: 0, color: "#000", WebkitTextStroke: `${stroke}px #000` }}>{text}</span>
    <span style={{ position: "relative", color }}>{text}</span>
  </span>
);

export const CaptionPage: React.FC<{ page: ReturnType<typeof createTikTokStyleCaptions>["pages"][number]; pageStartMs: number; top?: number; font?: FontFace }> = ({ page, pageStartMs, top = 1480, font }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const nowMs = pageStartMs + (frame / fps) * 1000;
  return (
    <div style={{ position: "absolute", top, left: 40, right: 40, textAlign: "center" }}>
      <div style={{ ...(font ? fs(font, 68) : { fontFamily, fontSize: 68, textTransform: "uppercase" as const, letterSpacing: 1 }), lineHeight: 1.12, transform: "skewX(-8deg)" }}>
        {page.tokens.map((t) => {
          const active = t.fromMs <= nowMs && t.toMs > nowMs;
          const entrance = Math.round(((t.fromMs - pageStartMs) / 1000) * fps);
          const p = spring({ frame: frame - entrance, fps, durationInFrames: 6, config: { damping: 14, stiffness: 260 } });
          const op = interpolate(p, [0, 0.5], [0, 1], { extrapolateRight: "clamp" });
          return (
            <span key={t.fromMs} style={{ display: "inline-block", whiteSpace: "pre", opacity: op, transform: `scale(${0.92 + 0.08 * p}) translateY(${(1 - p) * 12}px)` }}>
              <Outlined text={t.text.trim()} color={active ? YELLOW : "#fff"} />
            </span>
          );
        })}
      </div>
    </div>
  );
};

export const CaptionsBlock: React.FC<{
  words: Caption[]; suppress: { ms: number; capSuppressEndMs: number }[];
  // Split screen: pages that start inside a split window go to splitTop.
  splitWins?: { f0: number; f1: number }[]; splitTop?: number; font?: FontFace;
}> = ({ words, suppress, splitWins = [], splitTop = 930, font }) => {
  const { fps } = useVideoConfig();
  const caps = useMemo(() => cleanWords(words), [words]);
  const pages = useMemo(() => createTikTokStyleCaptions({ captions: caps, combineTokensWithinMilliseconds: 1100 }).pages, [caps]);
  return (
    <>
      {pages.map((page, i) => {
        const next = pages[i + 1] ?? null;
        const startMs = Math.max(0, page.startMs);
        // RULE (I3): a page lives until its last word ENDS (+150 ms tail) or
        // the next page starts, whichever comes first. Never a fixed ms cap:
        // with numbers or slow speech, a fixed 1100 ms cap cut a page mid-word
        // and left the screen blank while the speaker kept talking.
        const lastToMs = page.tokens[page.tokens.length - 1]?.toMs ?? page.startMs;
        const endMs = Math.min(next ? next.startMs : Infinity, Math.max(page.startMs + 1100, lastToMs + 150));
        // Compare by the page's START against the title's EXACT window: a
        // generous buffer eats neighboring words.
        if (suppress.some((ti) => startMs >= ti.ms && startMs < ti.capSuppressEndMs)) return null;
        const from = Math.round((startMs / 1000) * fps);
        const dur = Math.max(1, Math.round(((endMs - startMs) / 1000) * fps));
        const inSplit = splitWins.some((w) => from >= w.f0 && from < w.f1);
        return (
          <Sequence key={i} from={from} durationInFrames={dur}>
            <CaptionPage page={page} pageStartMs={startMs} top={inSplit ? splitTop : 1480} font={font} />
          </Sequence>
        );
      })}
    </>
  );
};
