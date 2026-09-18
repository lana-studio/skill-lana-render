# Closing the idea — the eight rules

The last cut decides whether the reel feels finished. Each rule below has a real failure behind
it, found by going through a corpus of published clips that "felt cut" or "felt unfinished"
even though nothing was technically wrong with them.

Read this before fixing the last cut, and apply the rules **in this order**.

---

## 1. Never a hard cut

The clip ends with air, not on the last phoneme. The edit provides it: `HOLD_F = 10` (333 ms at
30 fps), adjustable per video with `"hold_f"` in `CONFIG`. The tail of the last caption page and
any audio fade live inside that air.

**The air is not a freeze.** It is the last take still running, muted. A frozen frame looks
wrong, and 333 ms is short enough that the final `silencedetect` check does not count it as a
silence (`d=0.4`).

## 2. The ending is measured against the hook's debt

If the hook promises a list, a number or a question, **the final cut either pays it or the hook
changes.** This is the number one failure of the corpus.

Worked example: a clip whose hook promised five points ended with one of them paid. The fix was
not a longer ending — it was entering later, past the promise, so the clip no longer owed four
points.

## 3. Never close on a hallucinated word

A word the transcript placed over silence is the cleanest false ending there is: a polite
"Thanks." at the end of a mute stretch. **Before fixing the last cut, verify that the word has
voice over it** in `silence.speech[]`. If it does not, it is not a boundary — it is not even a
word.

## 4. False closing markers

"So, anyway", "in the end", "so there you go" followed by something that changes nothing do
**not** close anything. They sound like an ending while the situation is unchanged or worse.

Worked example: a clip ended on "…blocked forever. So, anyway, I'll just wait" — it sounds
final, and the protagonist is worse off than at the start; the real closing arrived eighty
seconds later. Either find the statement that actually changes the state, or cut before the
marker.

## 5. Referential dependency in the entry

If the first line hangs on "that", "there", "because of it", either include the antecedent or
change the entry point. **Review the whole chain, not just the previous sentence:** a line like
"I never asked you how long it takes" needs the question asked two turns earlier.

Practical limit: **three hops or 45 seconds.** Beyond that the clip does not stand on its own,
and the fix is a different entry, not more context.

## 6. There are four kinds of closure

Phrase, semantic, narrative and emotional. **The phrase-level one is the cheapest and the most
deceiving:** there is a full stop, there is no ending. A reel wins with semantic + emotional.

If the emotional peak arrives **before** the resolution and what follows is commentary, cutting
on the peak is valid. Worked example: a clip whose peak was a single absurd image kept going for
nine seconds explaining the source, and ended cold.

**It is almost always fixed by trimming, not by extending.** In the five-points example above,
the correct payoff only appears after cutting twelve seconds off the start.

## 7. Some structures close without resolving — and that is fine

- Story → Meaning (saying the meaning out loud makes it worse)
- Prediction → Reasoning
- Observation → Interpretation
- Curiosity → Deferred payoff, **only with a declared destination** ("comment MAP and I'll send
  it")

Open with no declared destination is not mystery: it is a cut.

## 8. The hook is not the structure

Opening with a provocative question does not turn the clip into question → answer. **The
structure is fixed by what the material does**; the hook only fixes where you enter — and what
it promises has to be paid (rule 2).
