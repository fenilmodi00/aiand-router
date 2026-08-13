# AIand Coding Router

Status: ready-for-agent

## Problem Statement

I am building a hackathon project for the aiand model provider. I do not want to train a model. I want a routing layer that coding agents can use by changing only their base URL.

Today, pointing an agent at aiand means I pick one model for the whole task. That wastes money on summaries and discovery, and it under-powers planning and debug. I have about $50 of aiand credits. I need judges to see different models chosen at different agent steps, with a real cost comparison, without inventing a savings percentage.

I need this to work as a product (a gateway), not as a custom agent. A thin demo agent is only a flashlight. OpenCode is the real-harness proof. Cursor is not required.

## Solution

An OpenAI-compatible gateway. Clients send `model: router/auto`. The gateway detects the current coding-agent phase (header or heuristics), filters the aiand pool with hard constraints, and picks the cheapest eligible model whose quality prior clears that phase’s bar.

Quality priors start as public Artificial Analysis Intelligence Index scores, labeled as not measured on aiand. They are overwritten only where a small cached eval exists. Kimi K3 is not selected just because it has the highest index; it is eligible only when the bar is high or routing effort is max.

The gateway holds the aiand key. Clients send a local router key. A soft dollar budget stops runaway spend. Failures the proxy can see (empty, timeout, rate limit, invalid tool JSON) escalate once to a stronger model. A flashlight agent may also report test/patch outcome so the demo can show test-fail → stronger model.

Judges see a recorded run plus a tiny live playground, and a single HTML replay over the request log. A 3-model × ~5-task cache supports three executed baselines: premium-only, Kimi-only, and adaptive. A learned router may exist as a module but stays dark unless that cache beats the rules.

## User Stories

1. As a coding-agent user, I want to point OpenCode at the gateway and send `router/auto`, so that I do not pick an aiand model myself.
2. As a coding-agent user, I want streaming chat completions to work, so that OpenCode and similar clients stay interactive.
3. As a coding-agent user, I want tool/function calling to pass through unchanged, so that the agent can read files, edit, and run commands.
4. As a coding-agent user, I want structured JSON / tool arguments to be validated, so that a malformed call is retried or escalated instead of silently breaking the loop.
5. As a coding-agent user, I want the gateway to accept a normal OpenAI chat-completions body, so that I do not need a custom SDK.
6. As a coding-agent user, I want missing `x-agent-phase` to be normal, so that OpenCode still gets a routed model.
7. As a flashlight-agent author, I want to send `x-agent-phase`, so that the demo can show an explicit discover → plan → edit → debug → summarize path.
8. As a flashlight-agent author, I want to send `x-routing-effort`, so that I can force cheap-first or allow K3 for a “max” step.
9. As a flashlight-agent author, I want to send `x-allowed-models`, so that a playground can constrain the pool without editing the registry.
10. As a flashlight-agent author, I want to POST a structured test/patch outcome, so that the next step can escalate after a real test failure.
11. As a judge, I want to see different models chosen at different phases, so that I believe this is a router and not a single-model proxy.
12. As a judge, I want a one-sentence routing reason per request, so that I understand why Flash was picked instead of K3.
13. As a judge, I want to compare adaptive vs premium-only vs Kimi-only on the same small task set, so that the savings number is measured.
14. As a judge, I want a recorded successful run I can replay, so that the live demo does not depend on a lucky inference.
15. As a judge, I want a tiny live “ask the router” playground, so that I know the recording is not fake.
16. As a judge, I want the registry to list all nine briefed models, so that I see the full aiand catalog story.
17. As a credit owner, I want the gateway to hold `AIAND_API_KEY` and require `ROUTER_API_KEY` from clients, so that a screenshot of OpenCode config cannot leak provider credits.
18. As a credit owner, I want a soft `BUDGET_LIMIT_USD`, so that a loop dies before it empties the wallet.
19. As a credit owner, I want every paid call cached by request identity, so that the same immutable prompt/model/tools/temperature is not billed twice.
20. As a credit owner, I want Motif-3 disabled until it appears on my org catalog, so that the gateway does not 404 on a briefed-but-absent model.
21. As a credit owner, I want K3 excluded from normal effort, so that “highest AA” cannot spend $12.50/1M on a summary.
22. As a credit owner, I want Qwen used when the bar is low, so that discovery and summaries can be free.
23. As the router, I want phase `discover` to use a low quality bar, so that a cheap/free model can list and read a repo.
24. As the router, I want phase `plan` to use a high quality bar, so that architecture is not left to the cheapest model.
25. As the router, I want phase `edit` to pick the cheapest model that clears the edit bar, so that implementation is not pinned to a marketing “coding specialist” unless that model is actually cheapest-above-bar.
26. As the router, I want phase `tool` to require tool-capable models, so that a no-tools model is never selected when `tools` are present.
27. As the router, I want phase `debug` to raise the bar after test/compiler failure text, so that repair uses a stronger model.
28. As the router, I want phase `summarize` to use the lowest bar, so that wrap-up stays cheap.
29. As the router, I want to drop models that cannot fit estimated tokens, so that a long repo dump does not hit a 131k model.
30. As the router, I want to drop unhealthy or disabled models, so that a catalog miss does not fail the request.
31. As the router, I want to drop models whose estimated cost exceeds remaining budget, so that a premium call is not started when the reserve is gone.
32. As the router, I want a configured fallback when nothing is eligible, so that the client still gets a response.
33. As the router, I want `routing_effort=low` to ignore the phase bar, so that a playground can force cheap-first.
34. As the router, I want `routing_effort=max` to raise the bar to the premium floor, so that K3 becomes eligible on purpose.
35. As the router, I want measured success to override AA when present, so that the 3×5 cache can change a prior without a code change.
36. As the router, I want every AA number labeled public / not-aiand, so that I never claim provider-hosted quality I did not measure.
37. As the gateway, I want to escalate once on empty response, so that a blank completion is not the end of the turn.
38. As the gateway, I want to escalate once on timeout, 429, or 5xx, so that provider blips do not kill the agent loop.
39. As the gateway, I want to escalate once on invalid tool JSON, so that a broken function-call does not poison the next turn.
40. As the gateway, I want streaming requests not to escalate mid-stream, so that OpenAI-compatible SSE is not rewritten after the client has already started reading.
41. As the gateway, I want response headers for phase, selected model, reason, threshold, and candidates, so that a dashboard can explain a decision without parsing logs.
42. As the gateway, I want each request appended to a JSONL log with tokens, cost, latency, and outcome, so that replay and spend accounting share one record.
43. As the gateway, I want `/v1/models` to return `router/auto` plus the registry, so that OpenCode can list a selectable virtual model.
44. As the gateway, I want `/health` to show spend vs budget and whether the aiand key is set, so that I can debug a dead process without printing secrets.
45. As the gateway, I want rejected auth to return 401 without calling aiand, so that a wrong client key cannot spend credits.
46. As the gateway, I want a pinned real model id (when the client sends one that exists) to bypass auto-select, so that the eval harness can run premium-only and Kimi-only baselines.
47. As a demo operator, I want a ~200-line flashlight loop (discover → plan → edit → test → fix → summarize), so that judges see per-step routing without integrating OpenHands.
48. As a demo operator, I want a seeded repo with a failing test and a clear fix, so that the live story does not depend on “add OAuth to FastAPI.”
49. As a demo operator, I want a second harder task only if the first is already green, so that escalation has a money shot without risking the whole demo.
50. As a demo operator, I want an `opencode.json` snippet in the README, so that “change the base URL” is a real claim.
51. As a demo operator, I want one HTML page that reads the JSONL log, so that I can replay phase, candidates, winner, reason, cost, and test outcome without running Streamlit.
52. As an evaluator, I want a request cache keyed by prompt, model, system prompt, tool schema, temperature, and max tokens, so that matrix reruns are free.
53. As an evaluator, I want to measure only Qwen, Kimi K2.7 Code, and DeepSeek V4 Pro on about five tasks, so that the $10 eval budget is enough.
54. As an evaluator, I want three executed baselines (premium, Kimi-only, adaptive), so that the slide has a real chart.
55. As an evaluator, I want the other five baseline modes stubbed, not executed, so that the CLI can grow later without spending credits now.
56. As an evaluator, I want a task schema that can later hold 50–100 tasks, so that the runner does not have to be rewritten after the demo.
57. As an evaluator, I want to refuse inventing X% savings, so that the README only reports numbers from the cache.
58. As a future owner, I want a LearnedRouter module that stays dark unless the 3×5 cache beats rules on a held-out slice, so that training cannot block the demo.
59. As a future owner, I want the provider adapter separate from routing policy, so that aiand request wiring can change without rewriting selection.
60. As a future owner, I want model metadata in configuration, so that a new aiand model can be added without rewriting the router.
61. As a future owner, I want secrets out of logs and frontend responses, so that keys never appear in the replay page.
62. As a future owner, I want configurable log redaction and max token/cost/timeout limits, so that a bad client cannot unbounded-spend.
63. As a README reader, I want to know what is measured vs assumed, so that I do not treat AA priors as aiand benchmarks.
64. As a README reader, I want to know how much credit the demo uses, so that I can decide whether to press run.

## Implementation Decisions

- The product is a FastAPI OpenAI-compatible gateway. The flashlight agent is a client of that gateway, not the other way around.
- Virtual model ids treated as “auto” are `router/auto`, `aiand-router`, and `auto`. Any other id that exists in the registry is a pin (used by eval baselines).
- Six phases only: `discover`, `plan`, `edit`, `tool`, `debug`, `summarize`. Fourteen-phase taxonomies are rejected.
- Phase detection order: `x-agent-phase` if it is one of the six; else heuristics on recent tool names, tool output, and last user text; else `edit` if tools are present, else `plan`. Unknown phase headers are ignored, not errors.
- Quality is `measured_success * 100` when set, otherwise the AA index. Models with a null AA index are ineligible for auto-select.
- Policy: compute a numeric bar from phase + effort; drop models that fail hard constraints; drop models at or above the premium AA floor unless effort is `max` or the bar itself is at that floor; pick the lowest blended unit cost, breaking ties by higher quality.
- Effort mapping: `low` sets bar to 0; `medium` uses the phase bar; `high` raises the bar to at least 50; `max` raises the bar to the premium floor (default 58).
- Default phase bars (from the prototype registry): discover 35, plan 50, edit 40, tool 38, debug 50, summarize 24. These are configuration, not code constants.
- Blended unit cost from the prototype: `0.4 * input_per_1m + 0.6 * output_per_1m`.
- Hard constraints: enabled, allow-list, tools required, context window vs estimated tokens, remaining budget vs a cheap cost estimate, AA present, premium-floor gate.
- Fallback model is configured (prototype: Qwen 3.6 27B) when the eligible set is empty.
- Escalation: one retry to the next enabled model with strictly higher quality. Triggers: empty message, 408/429/5xx, other 4xx from upstream, invalid tool-call JSON. Not on `effort=low`. Not mid-stream.
- Auth: `Authorization: Bearer <ROUTER_API_KEY>`. Upstream: `Authorization: Bearer <AIAND_API_KEY>` to `https://api.aiand.com/v1/chat/completions`, plus `X-Aiand-Metrics: true`.
- Budget: process-local spend file; reject new calls with 429 when spend ≥ `BUDGET_LIMIT_USD` (default 15).
- Observability: `X-Router-Phase`, `X-Router-Model`, `X-Router-Reason`, `X-Router-Threshold`, `X-Router-Candidates`, optional `X-Router-Escalated-From`. JSONL row per request. `/health` reports spend and whether the provider key is set, never the key itself.
- Streaming: pass SSE through; request `stream_options.include_usage` when the client streams so later accounting can improve. First-slice accounting may be zero on streams.
- Registry lists all nine briefed ids. Motif-3 ships `enabled: false` until `GET /v1/models` for this org lists it. Prices come from the public aiand catalog; K3 prices are the public listing used in grilling and must be confirmed against the org catalog before a paid max-effort call.
- Measured trio for the cache: Qwen 3.6 27B, Kimi K2.7 Code, DeepSeek V4 Pro (GLM 5.2 only if Pro misbehaves).
- Request cache key: hash of prompt + model id + system prompt + tool schema + temperature + max tokens. Cache before any paid duplicate.
- Flashlight outcome endpoint: structured `{tests_passed, patch_applied}` (and optional failure text). Used for demo escalation and replay, not required of OpenCode.
- Replay is one static HTML page over JSONL/SQLite-equivalent log. No Streamlit, no second long-lived app.
- LearnedRouter is a second implementation behind the same decision interface as the rules router. It is not consulted until an explicit comparison on the held-out slice of the 3×5 cache says it wins. No embedding/training pipeline is required to ship.
- Provider adapter stays separate from selection. The HTTP app must accept a fake upstream so tests never call aiand.
- One person owns credits. Eval and playground share the same budget limiter.

Prototype decision shape (keep this contract even if files move):

```
Decision:
  model, phase, threshold, reason, candidates[]

select_model(...) -> Decision
  eligible.sort(key=lambda m: (m.unit_cost, -m.quality))
  chosen = eligible[0]
```

## Testing Decisions

A good test asserts what a client or judge can observe: HTTP status, response body, `X-Router-*` headers, whether aiand was called, spend increment, and JSONL fields. Tests do not assert regex internals, YAML parse details, or httpx call shapes.

**Single seam: the ASGI app with a fake aiand upstream.**

That is the highest seam. Inject a provider that records the upstream body (especially `model`) and returns a scripted completion, stream, 429, empty message, or invalid tool JSON. Drive the app as OpenCode would: `POST /v1/chat/completions` and `GET /v1/models`.

Cover on that seam:

- 401 without a valid router key; no provider call
- 429 when spend is already at the budget; no provider call
- `router/auto` + `x-agent-phase: summarize` selects Qwen and forwards that model id
- `x-agent-phase: plan` selects the cheapest model at or above the plan bar and does not select K3
- `x-routing-effort: max` may select K3
- pinned Kimi id is forwarded unchanged (baseline pin)
- tools present → only tool-capable models
- invalid tool JSON → one escalation to a higher-quality model; header records the hop
- stream: SSE passthrough; no second upstream call
- JSONL contains phase, selected, reason, cost
- `/v1/models` includes `router/auto`

Do not add a second seam for `select_model` / `detect_phase` unless an HTTP test cannot express the case. Prefer more scripted provider responses over more unit files.

No prior art: the repo has no test suite yet. Live aiand calls are not CI. They are a manual smoke after the fake-provider tests pass, and only when the credit owner opts in.

If this seam does not match what you want (for example you would rather test `select_model` directly and keep HTTP thin), say so before `/to-tickets` or `/implement`. The rest of the spec does not depend on a different seam.

## Out of Scope

- Cursor integration
- Kubernetes, docker-compose, Modal, vLLM Semantic Router stack
- Training a classifier as a demo blocker
- 50–100 SWE-bench tasks this cycle
- Executing all eight original baselines
- Hosting aiand models ourselves
- Invented quality or savings claims
- Per-step routing that requires a custom phase header from third-party clients
- Mid-stream escalation
- BYOK (client sends the real aiand key)
- PostgreSQL, Redis, Streamlit
- Research writeups of Pioneer / FireRouter / LLMRouter / RouterArena / CrossRouter as a blocker (a short RESEARCH.md after the proxy works is enough)

## Further Notes

`DESIGN.md` wins over `Draft_agnet.md` when they disagree. The draft is historical context, not the contract.

Public catalog at grilling time did not list Motif-3; K3 may be org-gated. Confirm with `GET /v1/models` before a paid max-effort call.

Edit-phase currently prefers Flash over Kimi Code because Flash is cheaper and has a higher AA score. That is the agreed policy. A coding-specific prior is a later change, not a bug in this spec.

Build order if an agent slices the work: fake-provider test seam and gateway completion → opt-in aiand smoke → flashlight + OpenCode snippet → 3×5 cache + three baselines + replay page → LearnedRouter only if the cache beats rules.
