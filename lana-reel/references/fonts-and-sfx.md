# Fonts, sound effects and library resources in a render

Everything the renderer can reach falls into exactly three `staticFile` literal forms. There is
no fourth.

```
staticFile("assets/<key>.<ext>")   // something you uploaded and listed in submit_render(assets=…)
staticFile("sfx/<name>.wav")       // a name from Lana's sound-effects pack
staticFile("lib/<id>.<ext>")       // an id from lana_get_capabilities(topic="library")
```

Anything else — `fonts/…`, a relative `../`, a leading `/`, an `http` URL — fails with
`VALIDATION_ERROR` at the gateway and again at the renderer, with `field_path` pointing at
`files['<path>']:<line>`.

**Template literals are not analyzed.** `staticFile(\`sfx/${name}.wav\`)` passes validation and
then breaks at render time when the file does not exist. That is why every path is centralized
in one `asset()` helper and never built inline (I31).

The extension must be the one the content type implies: a `font/ttf` asset is `.ttf`, an
`audio/mpeg` asset is `.mp3`, a video asset is `.mp4` (the proxy), and so on. A mismatch is a
`VALIDATION_ERROR` naming the expected extension.

---

## 1. Fonts

Three paths, in order of preference.

### Google Fonts — the default

The renderer loads them itself through `@remotion/google-fonts`. **Nothing is uploaded, nothing
travels in the bundle, and there is no license to redistribute.** The font pairs offered by the
style questionnaire are built only from Google Fonts for that reason.

```tsx
import { loadFont } from "@remotion/google-fonts/Anton";
const { fontFamily } = loadFont();
```

Check that the family and the weights you want exist in the version the box runs (4.0.484)
before committing to a pair.

### Your own font — `purpose="font"`

`lana_create_upload(purpose="font")` accepts `font/ttf`, `font/otf` and `font/woff2`, up to
5 MiB, with no ingest step. In the submit it goes in `assets` like any other file, and in the
code it is `staticFile("assets/<key>.<ext>")`:

```tsx
// @font-face { font-family: 'Brand'; src: url(staticFile("assets/brand.ttf")); }
```

Over 5 MiB you get `RESOURCE_LIMIT` on `size_bytes` — subset the font or convert it to woff2.
Only the fonts actually used by the chosen pair are sent; they count against the 24-asset limit.

### A library font — `lib/<id>.<ext>`

A library entry with `kind: "font"` is referenced directly as `staticFile("lib/<id>.<ext>")`.
**It is not uploaded, it does not count as one of your assets, and it does not need
`purpose="font"`.** The library does not ship variable weights: use the published
`font.weight` / `font.style`, do not assume more exist.

Library entries carry a `license` field that may read `unknown`. **It is shown as it comes,
never filtered** (I15); verifying it before publishing commercially is the user's call.

---

## 2. Sound effects

The pack lives **inside the renderer**. It is not uploaded, it does not count as an asset, and
it does not consume quota. `lana_get_capabilities(topic="sfx")` is the authoritative list; the
snapshot with every name is in `references/sfx-pack.md`.

```tsx
<Sequence from={f}>
  <Audio src={staticFile("sfx/whoosh-short.wav")} volume={0.3} />
</Sequence>
```

- **One-shots** have `hit_ms: 0` — fire them on the frame of the cut or the word.
- **Risers** (`riser`, `riser-2`, `swell`) land their impact at `hit_ms`, so they must start
  early: `from = f0 - Math.round(hit_ms * fps / 1000)`.
- **Loops** (`typewriter-loop`, `heartbeat`) have `loop: true` — repeat them with `<Loop>`.
- **Alternate variants** (`-2`, `-3`) when a name would sound more than three times.
- **Level**: keep effects at least 6 dB under the voice, and never stack more than two inside
  100 ms. `default_volume` is already tuned against uncompressed voice.
- A name that is not in the pack is a `VALIDATION_ERROR`.

**Do not synthesize or download new sound effects** (I17). If the pack does not have what you
need, say so — do not fabricate it, and do not invent a sound that is already in the recorded
material (I29).

---

## 3. Library resources

Textures, overlays, B-roll and audio from the shared library travel as `lib/<id>.<ext>` — the
binaries are never uploaded from your side, and they do not count against your asset budget
(they have their own per-job cap of 16 references).

An overlay needs `media.alpha: true` to composite with `<OffthreadVideo transparent>`. A job
records the library release it was submitted with; if that release is no longer installed, the
job fails with `LIBRARY_RELEASE_UNAVAILABLE` and you recompose against the active release.

---

## 4. Warnings that are not failures

- `ASSET_PROXY_SUBSTITUTED: <key> → proxy v1` — the render used the proxy instead of the
  original. This is the intended behaviour.
- `ASSET_NO_PROXY: <key>` — no proxy existed, so the original was used. Fine.
- `SFX_PACK_COPIED` — the pack was staged by copy instead of by hard link. Informational.
