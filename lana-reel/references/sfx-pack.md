# The sound-effects pack

Lana's renderer ships a pack of sound effects. **They are never uploaded, they do not count as
assets of your render, and they do not consume quota** — you reference one by name:

```tsx
<Audio src={staticFile("sfx/<name>.wav")} volume={0.3} />
```

`lana_get_capabilities(topic="sfx")` is the authoritative list, and the only one your code
should trust: it returns `pack_version`, `count` and, per effect, `name`, `category`,
`duration_ms`, `hit_ms`, `loop`, `tags`, `license`, `default_volume` and `variant_of`.
`caps.py sfx` prints it as a table. A name that is not in the pack fails the render with
`VALIDATION_ERROR`.

**Do not synthesize or download new effects** (I17).

## How to place one

- **One-shot** (`hit_ms: 0`): start it on the frame of the cut or of the word.
- **Riser** (`riser`, `riser-2`, `swell`): the impact lands at `hit_ms`, so it starts earlier —
  `from = f0 - Math.round(hit_ms * fps / 1000)`.
- **Loop** (`loop: yes`): repeat it with `<Loop>`, do not chain copies.
- **Variants**: a name with `variant_of` set is an alternative take of that effect. Rotate to it
  when the base name would sound more than three times.
- **Level**: at least 6 dB under the voice; never more than two effects inside 100 ms.
  `default_volume` is already tuned against uncompressed voice.

## Suggested moment → name

A starting map, not a rule: transition and board → `whoosh-long` · card → `pop` · stacked card →
`pop-2` · whip → `whip` · glitch → `glitch` · headline → `impact` · hook → `riser` · closing →
`notification` · lower third → `whoosh-short` · chalk stroke → `chalk` · marker → `marker` ·
screen off → `tv-off` · reveal → `bass-drop`. An empty string in the map means **that moment is
silent**, which is a legitimate choice.

## The catalogue

Snapshot of the pack manifest, for planning. Two columns deserve attention:

- **Available** — `not yet` means the entry is declared in the manifest but its file is not in
  the shipped pack, so it is **excluded from `topic="sfx"` and rejected by validation**. Only the
  available ones are usable today. Ask `topic="sfx"` rather than trusting this column.
- **License** — `CC0` is CC0-1.0; `Lana-Synth` is `LicenseRef-Lana-Synth`, synthesized by Lana
  and shipped under the same terms as the renderer. Neither requires attribution.

Durations are milliseconds; `—` means the manifest does not declare one yet.

| name | category | available | duration | hit | loop | volume | variant of | license |
|---|---|---|---|---|---|---|---|---|
| `applause-short` | comedy | not yet | — | 0 | — | 0.35 | — | CC0 |
| `crowd-ohh` | comedy | not yet | — | 0 | — | 0.35 | — | CC0 |
| `fail` | comedy | yes | 1200 | 0 | — | 0.4 | — | Lana-Synth |
| `laugh-short` | comedy | not yet | — | 0 | — | 0.35 | — | CC0 |
| `record-scratch` | comedy | not yet | — | 0 | — | 0.5 | — | CC0 |
| `vine-boom` | comedy | yes | 1000 | 0 | — | 0.55 | — | Lana-Synth |
| `chalk` | foley | not yet | — | 0 | — | 0.2 | — | CC0 |
| `chalk-2` | foley | not yet | — | 0 | — | 0.2 | chalk | CC0 |
| `marker` | foley | not yet | — | 0 | — | 0.3 | — | CC0 |
| `page-flip` | foley | yes | 382 | 0 | — | 0.3 | — | CC0 |
| `shutter` | foley | yes | 258 | 0 | — | 0.4 | — | CC0 |
| `shutter-2` | foley | yes | 144 | 0 | — | 0.4 | shutter | CC0 |
| `typewriter-key` | foley | not yet | — | 0 | — | 0.25 | — | CC0 |
| `typewriter-loop` | foley | not yet | — | 0 | yes | 0.25 | — | CC0 |
| `water-drop` | foley | not yet | — | 0 | — | 0.4 | — | CC0 |
| `bass-drop` | impact | yes | 1500 | 0 | — | 0.5 | — | Lana-Synth |
| `boom` | impact | not yet | — | 0 | — | 0.5 | — | CC0 |
| `hit-sub` | impact | yes | 600 | 0 | — | 0.45 | — | Lana-Synth |
| `impact` | impact | not yet | — | 0 | — | 0.45 | — | CC0 |
| `impact-2` | impact | yes | 393 | 0 | — | 0.45 | impact | CC0 |
| `cash` | misc | not yet | — | 0 | — | 0.4 | — | CC0 |
| `coin` | misc | yes | 131 | 0 | — | 0.4 | — | CC0 |
| `error` | misc | yes | 400 | 0 | — | 0.4 | — | Lana-Synth |
| `tv-off` | misc | yes | 800 | 0 | — | 0.45 | — | Lana-Synth |
| `braam` | riser | not yet | — | 0 | — | 0.45 | — | CC0 |
| `heartbeat` | riser | yes | 2000 | 0 | yes | 0.3 | — | Lana-Synth |
| `riser` | riser | yes | 2500 | 2401 | — | 0.4 | — | Lana-Synth |
| `riser-2` | riser | yes | 2000 | 1901 | — | 0.4 | riser | Lana-Synth |
| `swell` | riser | yes | 1500 | 1451 | — | 0.35 | — | Lana-Synth |
| `glitch` | transition | yes | 500 | 0 | — | 0.5 | — | Lana-Synth |
| `glitch-2` | transition | not yet | — | 0 | — | 0.5 | glitch | CC0 |
| `whip` | transition | yes | 164 | 0 | — | 0.5 | — | CC0 |
| `whoosh` | transition | yes | 420 | 0 | — | 0.34 | — | Lana-Synth |
| `whoosh-2` | transition | yes | 420 | 0 | — | 0.34 | whoosh | Lana-Synth |
| `whoosh-long` | transition | not yet | — | 0 | — | 0.34 | — | CC0 |
| `whoosh-reverse` | transition | not yet | — | 0 | — | 0.34 | — | CC0 |
| `whoosh-short` | transition | yes | 145 | 0 | — | 0.3 | — | CC0 |
| `bubble` | ui | not yet | — | 0 | — | 0.35 | — | CC0 |
| `click` | ui | yes | 129 | 0 | — | 0.4 | — | CC0 |
| `click-2` | ui | yes | 94 | 0 | — | 0.4 | click | CC0 |
| `ding` | ui | yes | 500 | 0 | — | 0.4 | — | Lana-Synth |
| `ding-2` | ui | yes | 400 | 0 | — | 0.4 | ding | Lana-Synth |
| `notification` | ui | yes | 350 | 0 | — | 0.35 | — | Lana-Synth |
| `pop` | ui | yes | 220 | 0 | — | 0.35 | — | Lana-Synth |
| `pop-2` | ui | yes | 200 | 0 | — | 0.35 | pop | Lana-Synth |
| `pop-3` | ui | not yet | — | 0 | — | 0.35 | pop | CC0 |
| `switch` | ui | yes | 272 | 0 | — | 0.4 | — | CC0 |
| `tick` | ui | yes | 100 | 0 | — | 0.45 | — | Lana-Synth |
