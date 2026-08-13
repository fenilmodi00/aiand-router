# 03 — Flashlight run and replay

**What to build:** A thin demo agent walks discover → plan → edit → test → fix → summarize against the gateway, can report whether tests passed and whether a patch applied, and a single HTML page replays each step’s phase, winner, reason, and cost. Judges can watch a run without OpenCode. The README OpenCode snippet remains the “change the base URL” claim; a live OpenCode session is not required to close this ticket.

**Blocked by:** 01 — Provider seam and gateway contract

**Status:** resolved

- [x] A flashlight client sends `router/auto` and `x-agent-phase` for each step of discover → plan → edit → test → fix → summarize
- [x] The flashlight can POST structured `{tests_passed, patch_applied}` (optional failure text) after the test step
- [x] A later debug step can use that outcome so the replay shows test-fail → stronger model
- [x] One HTML page reads the request log and shows phase, candidates, selected model, reason, cost, and test outcome
- [x] Secrets never appear in the replay page or log fields it renders
- [x] README still documents the OpenCode `baseURL` + `router/auto` snippet
