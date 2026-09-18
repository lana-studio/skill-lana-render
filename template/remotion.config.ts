/**
 * This project never renders locally in the shipped flow — the skill always
 * renders through the Lana MCP (lana_submit_render), never `npx remotion
 * render`, and `@remotion/cli` is NOT a dependency of this template
 * (package.json). This file is excluded from `npm run check` (tsconfig.json)
 * and has no effect unless a contributor installs `@remotion/cli` themselves
 * for local `remotion studio` preview while writing videoconfig.py — never
 * add it to package.json or a runbook.
 *
 * All configuration options: https://remotion.dev/docs/config
 */
import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
