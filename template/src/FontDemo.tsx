import { AbsoluteFill, Sequence } from "remotion";
import { createTikTokStyleCaptions } from "@remotion/captions";
import { HookBanner, TitleBreak } from "./Reel";
import { CaptionPage } from "./Captions";
import { getFonts, useFontFiles } from "./Fonts";

/* Sample still for one font pair: hook banner + title with a small sub-line
 * + a caption page, over a plain gradient (no background photo ships with
 * the public template — style questionnaire, "look at it" step). One still
 * per pair, so the user picks by looking, not by name. */
export const FontDemo: React.FC<{ pair: string }> = ({ pair }) => {
  useFontFiles();
  const F = getFonts(pair);
  const page = createTikTokStyleCaptions({ captions: [
    { text: " YOU BOUGHT", startMs: 0, endMs: 400, timestampMs: null, confidence: null },
    { text: " THE", startMs: 400, endMs: 600, timestampMs: null, confidence: null },
    { text: " TV,", startMs: 600, endMs: 1000, timestampMs: null, confidence: null },
  ], combineTokensWithinMilliseconds: 1100 }).pages[0];
  return (
    <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 30%, #232323, #0A0A0A 70%)" }}>
      <AbsoluteFill style={{ background: "rgba(0,0,0,0.25)" }} />
      <Sequence from={0} durationInFrames={60}><HookBanner text="THE CLAUSE IS THERE" tag="EXAMPLE · READ IT" fonts={F} /></Sequence>
      <Sequence from={0} durationInFrames={60}>
        <TitleBreak words={[{ text: "IT", ms: 0 }, { text: "WAS", ms: 0 }, { text: "IN", ms: 0 }, { text: "THE", ms: 0 }, { text: "TERMS", ms: 0 }]} startMs={0} sub="and you accepted it" subMs={0} lift={120} fonts={F} />
      </Sequence>
      <Sequence from={0} durationInFrames={60}><CaptionPage page={page} pageStartMs={-500} font={F.display} /></Sequence>
      <div style={{ position: "absolute", left: 40, bottom: 40, fontFamily: "ui-monospace, Menlo, monospace", fontSize: 30, color: "#fff", background: "rgba(0,0,0,0.6)", padding: "8px 16px", borderRadius: 8 }}>{F.name}</div>
    </AbsoluteFill>
  );
};
