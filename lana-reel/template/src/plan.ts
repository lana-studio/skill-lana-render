// DEVELOPMENT PLACEHOLDER — the empty plan `make_pkg.py` replaces with the
// real edit before every bundle. Module, not JSON: an `import … from
// "./plan.json"` was rejected by the gateway (VALIDATION_ERROR …
// unresolved_relative) because `check_imports` resolves relative imports
// against `scan.code_files`, which only holds `.ts/.tsx/.js/.jsx` — the same
// extension list that keeps `.json` out of the 256 KiB code budget also
// keeps it out of import resolution. A `.ts` module needs no
// `resolveJsonModule` and counts against that budget, which is intentional:
// the generated plan is real code size, not a side-channel prop.
//
// `make_pkg.py` emits `lana-pkg/src/plan.ts` with the exact same export
// signature (`export default (<JSON>) as unknown as Plan;`) so a generated
// project typechecks against the same contract this placeholder does.
import type { Plan } from "./types";
export default ({"fps":30,"total":30,"src":"clip","segments":[],"captions":[],"lines":[]}) as unknown as Plan;
