# 13 — Draft phase aliases map to the six phases

**What to build:** Clients that send Draft_agnet phase names still get per-step routing. `x-agent-phase: planning` (and the other Draft names) maps onto the six locked phases. Unknown headers stay ignored, not errors. Missing phase stays normal.

Locked phases: `discover`, `plan`, `edit`, `tool`, `debug`, `summarize`.

**Blocked by:** None — can start immediately.

**Status:** resolved

- [x] `x-agent-phase: planning` routes as `plan` (header `X-Router-Phase` is `plan`, not ignored → default)
- [x] Other Draft names map: intent→plan, repository_discovery/repository_summary→discover, code_generation/code_edit→edit, tool_call→tool, test_failure_analysis/debugging→debug, refactoring/security_review→edit, final_summary→summarize, test_execution→tool (or debug if failure text is present)
- [x] Unknown phase header is ignored; heuristics or default still apply; response is not 4xx
- [x] Missing `x-agent-phase` remains normal
- [x] Proven via fake-upstream HTTP headers, not phase-detector unit tests alone
