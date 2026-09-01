/**
 * aiand-router — route the pi coding agent through the Aiand Router.
 *
 * Wiring (all on the existing router surface — no router source change beyond
 * the installer):
 *   - provider:     register `aiand` with per-process knob headers (quality on
 *                   the main loop, speed/cheap in subagents).
 *   - metadata:     stamp body.metadata.user_id for sticky sessions + subagent
 *                   detection.
 *   - Loom UI:      branded header, Wooly animation, actual route, and saved $.
 *   - safety:       block catastrophic bash (unless AIAND_NO_SAFETY=1).
 *   - compaction:   protect long tool loops, then compact routed context.
 *   - dispatch:     parallel, context-isolated subagents — top-level process
 *                   only (no grandchildren).
 *
 * The same module loads in dispatched children via `-e <self>`; AIAND_PI_SUBAGENT
 * flips the provider knobs and suppresses the dispatch tool so fan-out doesn't recurse.
 */

import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { isSubagent } from "./config.js";
import { registerCompaction } from "./compaction.js";
import { registerDispatch } from "./dispatch.js";
import { registerForceModelCommands } from "./force-model.js";
import { registerMetadata } from "./metadata.js";
import { registerRoutedModel } from "./routed-model.js";
import { registerSafety } from "./safety.js";
import { registerAiand } from "./provider.js";

const SELF_PATH = fileURLToPath(import.meta.url);

export default function (pi: ExtensionAPI): void {
	// Register at load so the provider is available for `--list-models` and
	// print mode (dispatched children), and again on session_start so the right
	// knob headers survive `/reload` and new/resumed sessions.
	registerAiand(pi);
	pi.on("session_start", () => registerAiand(pi));

	registerMetadata(pi);
	registerForceModelCommands(pi);
	registerRoutedModel(pi);
	registerCompaction(pi);

	if (process.env.AIAND_NO_SAFETY !== "1") registerSafety(pi);

	// Only the top-level process fans out. Children (AIAND_PI_SUBAGENT=1) load
	// this same extension but get no dispatch tool, so subagents can't spawn
	// grandchildren.
	if (!isSubagent()) registerDispatch(pi, SELF_PATH);
}
