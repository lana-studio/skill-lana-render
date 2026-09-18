// DEVELOPMENT PLACEHOLDER — compiles and runs `npm run check`, but this is
// not what ships to Lana. `make_pkg.py` (scripts/lana/) generates the real
// Root.tsx from project.json before every bundle: `id={project.composition}`
// and one extra <Composition> per entry in the proof list — a proof job
// renders up to 4 short windows of the edit in a single job so you can
// check the timing before spending a full render.
//
// The plan/ritmo/graphics data is imported from `.ts` modules and passed as
// defaultProps, not sent as inputProps on the submit call. The Lana render
// harness (as deployed today) doesn't carry inputProps through from a
// bundle's prepare step to its render step — a render submitted that way
// comes back with whatever defaultProps the composition declared, not the
// real edit. Importing the plan as code sidesteps that entirely: it's
// already in the bundle by the time the composition mounts, nothing needs
// to travel separately. Each generated proof composition reuses the same
// imported plan and only overrides `render_window`.
//
// It's a `.ts` module and not `.json`: an earlier cut imported the plan from
// "./plan.json" and the gateway rejected the bundle with a VALIDATION_ERROR
// (unresolved_relative). The gateway's `check_imports` only resolves
// relative imports against its code file scan, which — like the 256 KiB
// code budget — only counts `.ts/.tsx/.js/.jsx`; a `.json` file is invisible
// to both. Shipping the plan as a `.ts` module puts it in that scan (so the
// import resolves) and in that budget (so the size is honest), with no
// `resolveJsonModule` needed either way.
//
// The pattern below — <Sequence from={-from}> wrapping the real component,
// paired with calculateMetadata reading plan.render_window — is verified,
// working Remotion behavior (4.0.484): negative `from` shifts the child's
// local frame by exactly -from, so output frame g sees the content that
// would have played at global frame (g + render_window[0]), for exactly
// render_window[1] - render_window[0] frames. No off-by-one, no clamping.
import { Composition, Sequence } from "remotion";
import { Reel, holdFrames } from "./Reel";
import { FontDemo } from "./FontDemo";
import type { Plan, Ritmo } from "./types";
import type { Gfx } from "./Graphics";
import plan from "./plan";
import ritmo from "./ritmo";
import gfx from "./gfx";

export const ReelWindow: React.FC<{ plan: Plan; ritmo: Ritmo; gfx: Gfx[] }> = (props) => {
  const [from] = props.plan.render_window ?? [0, 0];
  return (
    <Sequence from={-from} layout="none">
      <Reel {...props} />
    </Sequence>
  );
};

const meta = ({ props }: { props: { plan: Plan } }) => {
  const w = props.plan.render_window;
  return { durationInFrames: w ? w[1] - w[0] : props.plan.total + holdFrames(props.plan) };
};

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="Reel"
      component={ReelWindow}
      fps={30}
      width={1080}
      height={1920}
      durationInFrames={plan.total + holdFrames(plan)}
      defaultProps={{ plan, ritmo, gfx }}
      calculateMetadata={meta}
    />
    {/* Optional: one still per font pair for the style questionnaire's
        "look, then choose" step. Not part of the proof/final render path. */}
    <Composition
      id="FontDemo"
      component={FontDemo}
      fps={30}
      width={1080}
      height={1920}
      durationInFrames={60}
      defaultProps={{ pair: "anton" }}
    />
  </>
);
