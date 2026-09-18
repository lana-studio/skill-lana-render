/* Sound effects by MOMENT, played against Lana's SFX pack
 * (lana_get_capabilities(topic="sfx")). The harness stages the whole
 * deployed pack's wav files on every job, unconditionally — every render
 * plays sound through asset("sfx/<name>") over that staged pack. There is
 * no local, no-pack fallback: this skill requires a harness recent enough
 * to always have the pack mounted (`caps.py --check` enforces the minimum
 * service_version before anything renders), so a "pack missing" branch
 * could never actually run — it would just be more code to keep in sync
 * for nothing. If a name isn't synthesized or downloaded for a moment that
 * has none, that moment stays silent rather than guessing a substitute.
 * Risers: the payoff is at hit_ms, so playback starts hit_ms before the
 * target frame. Volume: default_volume from the manifest, overridable by
 * ritmo.sfx.levels (brand defaults, lana_set_brand_defaults).
 */
import React, { createContext, useContext } from "react";
import { Audio, Sequence, useVideoConfig } from "remotion";
import { asset } from "./assets";
import type { SfxChoice, Moment } from "./types";

export type { SfxChoice, Moment };

/* If the requested name isn't in the deployed pack: its main variant
 * (variant_of), one of its own variants, a close relative, or silence. */
const FALLBACK: Record<string, string[]> = {
  "whoosh-long": ["whoosh", "whoosh-2"], "whoosh-reverse": ["whoosh-2", "whoosh"], "whoosh-short": ["whoosh"],
  "impact": ["impact-2", "hit-sub"], "boom": ["hit-sub", "bass-drop"], "braam": ["riser", "riser-2"],
  "pop-3": ["pop-2", "pop"], "bubble": ["pop-2", "pop"], "glitch-2": ["glitch"], "ding-2": ["ding"], "click-2": ["click"],
  "record-scratch": ["vine-boom"], "chalk": [], "chalk-2": [], "marker": [], "typewriter-loop": [], "typewriter-key": ["tick"],
  "water-drop": ["pop"], "cash": ["coin"], "crowd-ohh": [], "laugh-short": [], "applause-short": [],
};
export const resolveName = (sfx: SfxChoice, name: string): string => {
  if (!name || !sfx.pack || !sfx.names) return name;
  const have = new Set(sfx.names);
  if (have.has(name)) return name;
  for (const alt of [...(FALLBACK[name] ?? []), name.replace(/-\d+$/, "")]) if (alt && have.has(alt)) return alt;
  return "";
};
export const DEFAULT_MAP: Record<Moment, string> = {
  transition: "whoosh-long", board: "whoosh-long", card: "pop", stack: "pop-2", whip: "whip", glitch: "glitch",
  title: "impact", hook: "riser", closing: "notification", lowerthird: "whoosh-short", chalk: "chalk",
  marker: "marker", tvoff: "tv-off", reveal: "bass-drop",
};
/* Public subset of the 1.0.0 pack manifest (name -> duration, payoff offset,
 * default volume, variants). Kept as a fallback for `metaOf` when
 * ritmo.sfx.meta (from lana/caps.sfx.json via build.py) doesn't have an
 * entry; refresh from lana_get_capabilities(topic="sfx") if the pack changes.
 * Names verified 2026-09-17 against services/remotion-renderer-onprem/
 * sfx-pack/sfx.json (48/48). */
export const PACK: Record<string, { duration_ms: number; hit_ms: number; default_volume: number; variants?: string[] }> = {
  "whoosh": { duration_ms: 420, hit_ms: 0, default_volume: 0.34, variants: ["whoosh-2"] },
  "whoosh-2": { duration_ms: 420, hit_ms: 0, default_volume: 0.34 },
  "whoosh-short": { duration_ms: 250, hit_ms: 0, default_volume: 0.30 },
  "whoosh-long": { duration_ms: 600, hit_ms: 0, default_volume: 0.34 },
  "whoosh-reverse": { duration_ms: 500, hit_ms: 0, default_volume: 0.34 },
  "whip": { duration_ms: 200, hit_ms: 0, default_volume: 0.50 },
  "swell": { duration_ms: 1500, hit_ms: 1450, default_volume: 0.35 },
  "glitch": { duration_ms: 500, hit_ms: 0, default_volume: 0.50, variants: ["glitch-2"] },
  "glitch-2": { duration_ms: 480, hit_ms: 0, default_volume: 0.50 },
  "impact": { duration_ms: 440, hit_ms: 0, default_volume: 0.45, variants: ["impact-2"] },
  "impact-2": { duration_ms: 500, hit_ms: 0, default_volume: 0.45 },
  "hit-sub": { duration_ms: 600, hit_ms: 0, default_volume: 0.45 },
  "boom": { duration_ms: 1000, hit_ms: 0, default_volume: 0.50 },
  "bass-drop": { duration_ms: 1500, hit_ms: 0, default_volume: 0.50 },
  "riser": { duration_ms: 2500, hit_ms: 2400, default_volume: 0.40, variants: ["riser-2"] },
  "riser-2": { duration_ms: 2000, hit_ms: 1900, default_volume: 0.40 },
  "braam": { duration_ms: 2500, hit_ms: 2300, default_volume: 0.45 },
  "heartbeat": { duration_ms: 2000, hit_ms: 0, default_volume: 0.30 },
  "tv-off": { duration_ms: 800, hit_ms: 0, default_volume: 0.45 },
  "vine-boom": { duration_ms: 1000, hit_ms: 0, default_volume: 0.55 },
  "record-scratch": { duration_ms: 600, hit_ms: 0, default_volume: 0.50 },
  "crowd-ohh": { duration_ms: 800, hit_ms: 0, default_volume: 0.35 },
  "laugh-short": { duration_ms: 800, hit_ms: 0, default_volume: 0.35 },
  "applause-short": { duration_ms: 1500, hit_ms: 0, default_volume: 0.35 },
  "fail": { duration_ms: 1200, hit_ms: 0, default_volume: 0.40 },
  "ding": { duration_ms: 500, hit_ms: 0, default_volume: 0.40, variants: ["ding-2"] },
  "ding-2": { duration_ms: 400, hit_ms: 0, default_volume: 0.40 },
  "click": { duration_ms: 150, hit_ms: 0, default_volume: 0.40, variants: ["click-2"] },
  "click-2": { duration_ms: 120, hit_ms: 0, default_volume: 0.40 },
  "tick": { duration_ms: 100, hit_ms: 0, default_volume: 0.45 },
  "switch": { duration_ms: 330, hit_ms: 0, default_volume: 0.40 },
  "notification": { duration_ms: 350, hit_ms: 0, default_volume: 0.35 },
  "pop": { duration_ms: 220, hit_ms: 0, default_volume: 0.35, variants: ["pop-2", "pop-3"] },
  "pop-2": { duration_ms: 200, hit_ms: 0, default_volume: 0.35 },
  "pop-3": { duration_ms: 150, hit_ms: 0, default_volume: 0.35 },
  "bubble": { duration_ms: 220, hit_ms: 0, default_volume: 0.35 },
  "chalk": { duration_ms: 450, hit_ms: 0, default_volume: 0.20, variants: ["chalk-2"] },
  "chalk-2": { duration_ms: 400, hit_ms: 0, default_volume: 0.20 },
  "marker": { duration_ms: 400, hit_ms: 0, default_volume: 0.30 },
  "page-flip": { duration_ms: 400, hit_ms: 0, default_volume: 0.30 },
  "shutter": { duration_ms: 490, hit_ms: 0, default_volume: 0.40, variants: ["shutter-2"] },
  "shutter-2": { duration_ms: 314, hit_ms: 0, default_volume: 0.40 },
  "typewriter-loop": { duration_ms: 1000, hit_ms: 0, default_volume: 0.25 },
  "typewriter-key": { duration_ms: 100, hit_ms: 0, default_volume: 0.25 },
  "water-drop": { duration_ms: 500, hit_ms: 0, default_volume: 0.40 },
  "cash": { duration_ms: 600, hit_ms: 0, default_volume: 0.40 },
  "coin": { duration_ms: 300, hit_ms: 0, default_volume: 0.40 },
  "error": { duration_ms: 400, hit_ms: 0, default_volume: 0.40 },
};
const SfxContext = createContext<SfxChoice>({});
export const SfxProvider = SfxContext.Provider;
export const useSfx = () => useContext(SfxContext);

export const sfxName = (sfx: SfxChoice, moment: Moment, nth = 0): string => {
  const mapped = sfx.map?.[moment];
  if (mapped === "") return "";                // "" in the map = this moment stays silent
  const base = resolveName(sfx, mapped ?? DEFAULT_MAP[moment]);
  if (!base) return "";
  const vars = (PACK[base]?.variants ?? []).map((v) => resolveName(sfx, v)).filter((v) => v && v !== base);
  if ((sfx.rotate ?? true) && vars.length && nth > 0) return [base, ...vars][nth % (vars.length + 1)];
  return base;
};
const metaOf = (sfx: SfxChoice, name: string) => sfx.meta?.[name] ?? PACK[name];
export const sfxVolume = (sfx: SfxChoice, name: string, fallback?: number): number =>
  sfx.levels?.[name] ?? fallback ?? metaOf(sfx, name)?.default_volume ?? 0.35;
export const sfxHitFrames = (sfx: SfxChoice, name: string, fps: number): number => Math.round(((metaOf(sfx, name)?.hit_ms ?? 0) / 1000) * fps);

/* <SfxAudio moment nth volumeMul/>: a one-shot at frame 0 of the Sequence
 * that contains it, played over the pack file the harness always stages.
 * No name for this moment (silenced in the map, or the moment simply has
 * none) -> nothing, never an error. */
export const SfxAudio: React.FC<{ moment: Moment; nth?: number; volumeMul?: number; name?: string }> = ({ moment, nth = 0, volumeMul = 1, name }) => {
  const sfx = useSfx();
  const n = name ?? sfxName(sfx, moment, nth);
  if (!n) return null;
  return <Audio src={asset(`sfx/${n}.wav`)} volume={sfxVolume(sfx, n) * volumeMul} />;
};
/* <SfxAt moment atF/>: at an ABSOLUTE frame; for risers, playback starts
 * hit_ms early so the payoff lands on atF. If there's no room (atF < hit),
 * falls back to the "title" one-shot (impact) right at atF. */
export const SfxAt: React.FC<{ moment: Moment; atF: number; nth?: number; volumeMul?: number }> = ({ moment, atF, nth = 0, volumeMul = 1 }) => {
  const sfx = useSfx();
  const { fps } = useVideoConfig();
  let n = sfxName(sfx, moment, nth);
  if (!n) return null;
  let hit = sfxHitFrames(sfx, n, fps);
  if (hit > 0 && atF - hit < 0) { n = sfxName(sfx, "title", nth); hit = 0; if (!n) return null; }
  const dur = Math.max(2, Math.ceil(((metaOf(sfx, n)?.duration_ms ?? 600) / 1000) * fps) + 2);
  return (
    <Sequence from={atF - hit} durationInFrames={dur}>
      <SfxAudio moment={moment} nth={nth} volumeMul={volumeMul} name={n} />
    </Sequence>
  );
};
