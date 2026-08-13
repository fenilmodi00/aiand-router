# 06 — Opt-in aiand smoke

**What to build:** The credit owner runs one streamed tool-call against the real aiand endpoint through the gateway. This confirms the adapter and streaming, not the routing policy. Not a CI job. Do not run it unless the owner opts in.

**Blocked by:** 01 — Provider seam and gateway contract

**Status:** ready-for-human

- [x] A documented one-command or curl path sends a streamed chat completion with a tool through the gateway to aiand
- [ ] A successful run shows tokens streaming and a tool call in the client
- [ ] Spend file and JSONL record the real call
- [x] The command is opt-in and will not run in CI

## Comments

Agent shipped `python -m aiand_router.smoke` (refuses unless `AIAND_SMOKE=1`) and a curl snippet in the README. The live streamed tool-call still needs the credit owner; it was not executed here.
