/* Font pairs offered by the style questionnaire (scripts/reel/styles.py).
 * Each pair has a DISPLAY face (hook banner, big titles, captions) and an
 * ACCENT face (hook tag, small line under a title).
 *
 * Two origins:
 * - Google Fonts (@remotion/google-fonts): the render harness downloads it
 *   from fonts.gstatic.com. Every pair below is OFL, so nothing ships in the
 *   bundle and there is no license to redistribute.
 * - File (project.fonts.custom[key], purpose="font"): the user's own .ttf,
 *   uploaded and referenced as assets/<key>.ttf. Also used for a shared
 *   library font (lib/<id>.ttf), offered with its `license` visible and
 *   never filtered out — verify the license yourself before commercial use.
 */
import { useEffect, useState } from "react";
import { continueRender, delayRender } from "remotion";
import { loadFont as Anton } from "@remotion/google-fonts/Anton";
import { loadFont as ArchivoBlack } from "@remotion/google-fonts/ArchivoBlack";
import { loadFont as OpenSans } from "@remotion/google-fonts/OpenSans";
import { loadFont as Montserrat } from "@remotion/google-fonts/Montserrat";
import { loadFont as EBGaramond } from "@remotion/google-fonts/EBGaramond";
import { loadFont as PlayfairDisplay } from "@remotion/google-fonts/PlayfairDisplay";
import { loadFont as Poppins } from "@remotion/google-fonts/Poppins";
import { loadFont as Raleway } from "@remotion/google-fonts/Raleway";
import { loadFont as Inter } from "@remotion/google-fonts/Inter";
import { loadFont as Nunito } from "@remotion/google-fonts/Nunito";
import { loadFont as Baloo2 } from "@remotion/google-fonts/Baloo2";
import { loadFont as Quicksand } from "@remotion/google-fonts/Quicksand";
import { loadFont as GreatVibes } from "@remotion/google-fonts/GreatVibes";
import { FONT_FILES } from "./fonts-manifest";
import type { FontFace, FontSet, FontChoice, FontUse } from "./types";

export type { FontFace, FontSet, FontChoice, FontUse };

// `any` on purpose: every @remotion/google-fonts/<Family> loader has its own
// literal-union type for weights/subsets/style (e.g. Anton has no italic),
// so a shared structural type would fight each family's generics. g() is
// the single call site that narrows back to FontFace.
type Loader = (style?: any, opts?: any) => { fontFamily: string };
const g = (loader: Loader, weight: number, italic = false, extra: Partial<FontFace> = {}): FontFace => {
  const { fontFamily } = loader(italic ? "italic" : "normal", { weights: [String(weight)], subsets: ["latin", "latin-ext"] });
  return { family: fontFamily, weight, italic, upper: true, tracking: 1, scale: 1, ...extra };
};
/* File font: family AND weight come from the @font-face entry the manifest
 * declared (a manifest entry has one fixed weight per file) — no second
 * weight argument to keep in sync with useFontFiles(). Not used by any
 * pair below (the default questionnaire is all Google Fonts) — exported
 * for a project that adds its own pair against project.fonts.custom or a
 * shared-library font (lib/<id>.ttf). */
export const fontFromFile = (key: string, extra: Partial<FontFace> = {}): FontFace => {
  const ff = FONT_FILES[key];
  if (!ff) throw new Error(`font "${key}" is not in fonts-manifest.ts — register it in project.fonts.custom or pick a Google Fonts pair`);
  return { family: ff.family, weight: ff.weight, italic: ff.style === "italic", upper: true, tracking: 1, scale: 1, ...extra };
};
// Script faces read as lowercase, larger than their sibling: at the same
// pixel size a script face looks small next to a sans/serif display face.
export const scriptFace = (face: FontFace, scale: number): FontFace => ({ ...face, upper: false, tracking: 0, scale });

/* Grouped for the questionnaire (`group`): bold / editorial / geometric /
 * rounded / script, up to 4 pairs each. Every family below is verified to
 * exist in @remotion/google-fonts 4.0.484 with the weights used here. */
export const FONT_GROUPS = ["bold", "editorial", "geometric", "rounded", "script"] as const;
export type FontGroup = (typeof FONT_GROUPS)[number];

export const FONT_PAIRS: Record<string, { group: FontGroup; build: () => FontSet }> = {
  anton: { group: "bold", build: () => ({ id: "anton", name: "Anton / Anton", display: g(Anton, 400, false, { tracking: 2 }), accent: g(Anton, 400, false, { tracking: 3 }) }) },
  archivo: { group: "bold", build: () => ({ id: "archivo", name: "Archivo Black / Open Sans", display: g(ArchivoBlack, 400, false, { tracking: 0 }), accent: g(OpenSans, 600, false, { tracking: 3 }) }) },
  montserrat: { group: "editorial", build: () => ({ id: "montserrat", name: "Montserrat / EB Garamond Italic", display: g(Montserrat, 800, false, { tracking: 0 }), accent: g(EBGaramond, 500, true, { upper: false, tracking: 0, scale: 1.15 }) }) },
  playfair: { group: "editorial", build: () => ({ id: "playfair", name: "Playfair Display / Raleway", display: g(PlayfairDisplay, 800, false, { tracking: 0 }), accent: g(Raleway, 400, false, { upper: false, tracking: 0, scale: 1.1 }) }) },
  poppins: { group: "geometric", build: () => ({ id: "poppins", name: "Poppins / Playfair Display Italic", display: g(Poppins, 700, false, { tracking: 0 }), accent: g(PlayfairDisplay, 500, true, { upper: false, tracking: 0, scale: 1.1 }) }) },
  inter: { group: "geometric", build: () => ({ id: "inter", name: "Inter Black / Raleway Light", display: g(Inter, 900, false, { tracking: -1 }), accent: g(Raleway, 300, false, { upper: false, tracking: 1, scale: 1.05 }) }) },
  nunito: { group: "rounded", build: () => ({ id: "nunito", name: "Nunito Black / Nunito", display: g(Nunito, 900, false, { tracking: 0 }), accent: g(Nunito, 400, false, { upper: false, tracking: 0, scale: 1.1 }) }) },
  baloo: { group: "rounded", build: () => ({ id: "baloo", name: "Baloo 2 / Quicksand", display: g(Baloo2, 800, false, { tracking: 0 }), accent: g(Quicksand, 500, false, { upper: false, tracking: 0, scale: 1.1 }) }) },
  elegant: { group: "script", build: () => ({ id: "elegant", name: "Raleway / Great Vibes", display: g(Raleway, 800, false, { tracking: 2 }), accent: scriptFace(g(GreatVibes, 400), 1.5) }) },
  garamond: { group: "script", build: () => ({ id: "garamond", name: "EB Garamond / Great Vibes", display: g(EBGaramond, 500, false, { tracking: 1 }), accent: scriptFace(g(GreatVibes, 400), 1.5) }) },
};
export const FONT_IDS = Object.keys(FONT_PAIRS);
export const DEFAULT_FONT_PAIR = "anton";
export const getFonts = (id?: string | null): FontSet => (FONT_PAIRS[id ?? DEFAULT_FONT_PAIR] ?? FONT_PAIRS[DEFAULT_FONT_PAIR]).build();

/* Questionnaire pick: one pair and which uses it applies to; anything else
 * stays on the default pair. */
export const fontsFor = (choice: FontChoice | null | undefined): Record<FontUse, FontSet> => {
  const base = getFonts(DEFAULT_FONT_PAIR);
  if (!choice) return { hook: base, titles: base, captions: base };
  const pair = typeof choice === "string" ? choice : choice.pair;
  const uses = typeof choice === "string" ? (["hook", "titles", "captions"] as FontUse[]) : (choice.uses ?? ["hook", "titles", "captions"]);
  const F = getFonts(pair);
  return { hook: uses.includes("hook") ? F : base, titles: uses.includes("titles") ? F : base, captions: uses.includes("captions") ? F : base };
};

/* CSS for one face at a base size. */
export const fs = (face: FontFace, size: number) => ({
  fontFamily: face.family, fontWeight: face.weight, fontStyle: face.italic ? "italic" : "normal",
  fontSize: Math.round(size * (face.scale ?? 1)), letterSpacing: face.tracking ?? 0,
  textTransform: (face.upper ? "uppercase" : "none") as "uppercase" | "none",
});

/* Registers @font-face for every file font (project.fonts.custom, purpose=
 * "font", resolved as assets/<key>.ttf; or a shared-library font, lib/<id>.
 * <ext>) and blocks the render until the browser has them loaded. Once per
 * composition. A project with no file fonts renders this as a no-op. */
let injected = false;
export const useFontFiles = () => {
  const [handle] = useState(() => delayRender("file fonts"));
  useEffect(() => {
    if (typeof document === "undefined") { continueRender(handle); return; }
    const entries = Object.entries(FONT_FILES);
    if (entries.length === 0) { continueRender(handle); return; }
    if (!injected) {
      const st = document.createElement("style");
      // x.file is ALREADY a staticFile(...) result — never re-wrap it in staticFile() again.
      st.textContent = entries.map(([, x]) =>
        `@font-face{font-family:"${x.family}";font-weight:${x.weight};font-style:${x.style};src:url("${x.file}") format("truetype");font-display:block;}`).join("\n");
      document.head.appendChild(st);
      injected = true;
    }
    Promise.all(entries.map(([, x]) => document.fonts.load(`${x.style} ${x.weight} 24px "${x.family}"`)))
      .then(() => continueRender(handle))
      .catch((e) => { console.error("file fonts", e); continueRender(handle); });
  }, [handle]);
};
