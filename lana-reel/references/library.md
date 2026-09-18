# Lana's shared library (step 3)

A curated pack of creative resources that lives on Lana — fonts, alpha overlays, textures,
B-roll and audio — shared across every project. **The binaries are never uploaded or
re-uploaded from here:** Lana's harness resolves them at render time.

**The catalogue is never copied into this file, into any other file of this skill, or into a
script.** It is requested live, because the active release changes over time.

## Releases

A release (`1.0.0`, `1.1.0`, …) is an **immutable** batch of resources with fixed ids, hashes
and provenance. `lana_get_capabilities(topic="library")` returns the ACTIVE release
(`library.release`) with up to 40 entries (`truncated: true` if there are more), plus
`requires_lana_mcp_render`, `harness_version` and `harness_compatible`.

A render job records the release it was submitted with. If that release is no longer installed
on the box, the job fails with `LIBRARY_RELEASE_UNAVAILABLE` — it never updates itself, and
`make_submit.py` refuses to submit a selection made against a different release.

## `lib:<id>` vs `lib/<id>.<ext>`

- **`lib:<id>`** (or `lib:<id>@<release>`) is what you pass to `lana_get_asset(...)`: it is for
  **seeing** a resource — contract of use plus an inline preview image — before choosing it.
- **`lib/<id>.<ext>`** is the exact literal that goes inside `staticFile(...)` in the React
  code. It comes from `entries[].file` of the current session. **Never typed from memory, never
  invented** (I14).

## Previews

`lana_get_asset("lib:<id>")` returns the usage contract as JSON **and** one inline JPEG preview
(≤ 1024 px). Look at it with the user before choosing (I12).

**Do not cache `preview.url`.** It is a signed URL that expires in one hour; if you need to show
it again later, call the tool again.

## Licenses: shown, never filtered

`caps.py library` prints **every** entry with its `license` field exactly as it comes,
`unknown` included, plus `attribution_required`. Nothing is hidden, nothing is marked
"ineligible", nothing is sorted by license (I15). The listing closes with a count, not a filter:

```
N of M entries have license "unknown" — verify before commercial use (README §Shared library & licenses)
```

When the user picks an entry whose `license` is `unknown`, **say so once** and point at the
repository README, section "Shared library & licenses": verifying the license before publishing
commercially is the user's responsibility, not this skill's. `build.py` prints the same count
when it registers the selection.

## Selection criteria per `kind`

- **overlay** — check `media.alpha` (it must be `true` to composite it with
  `<OffthreadVideo transparent>`) and `media.fps` (it should not clash with the project's fps,
  normally 30).
- **font** — `font.family` / `font.weight` / `font.style`. The library does not ship variable
  weights: pick the published weight closest to what the style asks for, and do not assume more
  weights exist.
- **texture / broll** — `media.width` / `media.height` against the destination (1080×1920). If
  they do not match exactly, crop or use `objectFit` in the code; do not ask for another version.
- **audio** — `audio.hit_ms` to align the impact of a whoosh with the cut, exactly like the SFX
  pack; `audio.loop` and `audio.default_volume` if they apply.

## On `LIBRARY_RELEASE_UNAVAILABLE`

The release you composed with (or pinned with `lib:<id>@<release>`) is no longer installed.
**Do not retry the same job as it is.** Ask `lana_get_capabilities(topic="library")` again,
recompose against the active release, and confirm with the user whether the chosen resource
still exists under another id.

`make_submit.py` refuses to submit before you get there, with `library release mismatch: active
is X, selection was made with Y — it will not be silently swapped`. That refusal is the feature:
a resource picked by the user is never quietly replaced by whatever now carries that id.

## Don'ts

- Do not copy `entries[]` into this file or into any script: ask for it live.
- Do not use an id that is not in `entries[].file` of the current session (I14).
- Do not leave a `lib/<id>` in the code without its entry in the project's library selection:
  `make_pkg.py` rejects it (exit 1).
- Do not hide, filter or reorder entries by license (I15).
