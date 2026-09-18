// DEVELOPMENT PLACEHOLDER — see plan.ts for why this ships as a `.ts`
// module instead of JSON. `make_pkg.py` emits `lana-pkg/src/gfx.ts` with the
// same export signature. Named `gfx.ts`, not `graphics.ts`: the obvious name
// collides case-insensitively with the `Graphics.tsx` component on macOS
// and Windows, which makes TypeScript resolve `import ... from "./Graphics"`
// to this file instead of the component — breaks `tsc` locally and the
// pre-submit typecheck `make_pkg.py` runs on the generated bundle.
import type { Gfx } from "./Graphics";
export default ([]) as unknown as Gfx[];
