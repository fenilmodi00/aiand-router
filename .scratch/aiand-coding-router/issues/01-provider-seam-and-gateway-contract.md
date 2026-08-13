# 01 — Provider seam and gateway contract

**What to build:** A client can talk to the gateway as OpenCode would, while aiand is replaced by a fake upstream. The existing routing behaviour becomes proven: wrong keys spend nothing, a full budget rejects new calls, `router/auto` picks by phase and effort, a pinned model is forwarded unchanged, bad tool JSON escalates once, and a stream is passed through without a second try.

**Blocked by:** None — can start immediately.

**Status:** resolved

- [x] The app accepts a fake aiand upstream so tests never call the real provider
- [x] Missing or wrong `ROUTER_API_KEY` returns 401 and the fake upstream is not called
- [x] Spend already at `BUDGET_LIMIT_USD` returns 429 and the fake upstream is not called
- [x] `router/auto` + `x-agent-phase: summarize` forwards Qwen; plan does not forward K3; `x-routing-effort: max` may forward K3
- [x] A pinned registry model id is forwarded unchanged (baseline pin)
- [x] Invalid tool-call JSON causes exactly one escalation to a higher-quality model; `X-Router-Escalated-From` is set
- [x] A streamed response is SSE-passthrough; the fake upstream is called once
- [x] JSONL records phase, selected model, reason, and cost; `/v1/models` includes `router/auto`
