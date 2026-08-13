# AIand Router vs Pioneer vs FireRouter

Primary-source dump (Pioneer + FireRouter docs only): [`.scratch/competitor-router-research.md`](competitor-router-research.md). This file is the **local-code verdict** against that dump.

Sources: official docs + this repo’s `src/aiand_router/router.py`, `config/models.yaml`, `src/aiand_router/app.py`. No published latency/eval numbers were found for Pioneer or FireRouter.

- Pioneer: https://docs.pioneer.ai/concepts/router
- Pioneer Claude Code / savings stamp: https://docs.pioneer.ai/claude-code
- Pioneer OpenCode: https://docs.pioneer.ai/opencode
- FireRouter overview: https://docs.fireworks.ai/ecosystem/firerouter/overview
- FireRouter preferences: https://docs.fireworks.ai/ecosystem/firerouter/routing-preferences
- FireRouter auth: https://docs.fireworks.ai/ecosystem/firerouter/authentication

## Positioning

| | AIand Coding Router | Pioneer Model Router | FireRouter |
| --- | --- | --- | --- |
| Product | Self-hosted OpenAI gateway over **aiand only** | Managed coding-task router | Managed **any-LLM** binary router (research preview) |
| Client model id | `router/auto` | `pioneer/auto` | `firerouter` |
| Wire | OpenAI `/v1/chat/completions` | OpenAI + Anthropic Messages | OpenAI + Anthropic Messages |
| Pool | 9 enabled aiand models (Motif-3 on, AA 47) | DeepSeek Flash/Pro, GLM 5.2, Sonnet 4.6, GPT-5.5, Opus 4.7 | GLM 5.2 (redirect) vs Claude Opus 4.8 (pass-through) |
| Keys | Gateway holds `AIAND_API_KEY`; client sends `ROUTER_API_KEY` | Pioneer key | Fireworks key + Anthropic BYOK per request |

## How routing works

**Pioneer** ([docs](https://docs.pioneer.ai/concepts/router)): trained low-latency coding router. Reads messages → calibrated P(success) per candidate → cheapest that clears `threshold` (default 0.20) without exceeding `max_regret` (default 0.15) vs the top scorer → else fallback (default Sonnet 4.6). Effort presets retune threshold + max_regret + pool.

**FireRouter** ([docs](https://docs.fireworks.ai/ecosystem/firerouter/overview)): scores each request independently (routing decision may stick inside a conversation). Binary: cheap Fireworks open model vs closed-source pass-through. Dial is `x-routing-preference` 1–5 ([prefs](https://docs.fireworks.ai/ecosystem/firerouter/routing-preferences)). No Anthropic key → redirect only.

**AIand** (`router.py`): detect phase (header or heuristics) → hard constraints (tools/JSON/stream/context/max-out/budget/AA present/premium floor/optional latency) → predicted success ≥ phase bar → medium/high: max Pioneer-inspired score; low: cheapest; max: strongest AA. Max-regret (8 AA points) only when bar ≥ 50. One post-inference escalate on empty / timeout / 429 / 5xx / bad tool JSON. Learned module stays dark.

Pioneer-inspired score here: `0.40·success + 0.20·capability + 0.15·tools + 0.10·latency + 0.10·health − 0.05·cost`.

## Routing quality (this catalog)

AA priors in `models.yaml` (not measured on aiand): Flash 52, Pro/GLM 53, K3 60, Motif 47, Kimi Code 42, Qwen 38, Gemma 30, OSS 24.

No model has `priors`, `latency_ms`, or `health` set → capability collapses to AA/100, latency is 800ms for everyone, health is 1.0. Tool flag is true for all. Score therefore ≈ `0.60·(AA/100) − 0.05·norm_cost`. Flash is both cheap and high-AA, so **default medium/high almost always selects Flash** whenever Flash clears the bar.

Phase bars today: summarize 24, discover 35, edit 40, tool 38, plan/debug/security 50, debug-after-fail 53. Flash (52) clears every bar except debug-fail. `effort=high` only raises the bar to 50 → still Flash. `effort=max` raises to 58 → K3 only. Max-regret almost never changes the set (eligible AA after the premium floor is 52–53).

So in practice this is a **2–3 model policy** (Flash / Pro-on-debug-fail / K3-on-max), not an 8-way Pioneer-style scorer. That is still a valid cheap-first coding router; it is not a calibrated per-task router.

Pioneer’s pool spans Flash → Opus and scores **this** conversation. FireRouter’s escape hatch is Opus 4.8. We have no closed-source ceiling; that is an aiand-product constraint, not a missing feature.

## Performance

None of the three publish router p50/p95. Pioneer claims “low-latency.” FireRouter does not state overhead. Our decision is in-process Python rules (microseconds–low ms). Inference latency is the selected model; `latency_ms` in the registry is unused static default. Escalation costs a second full inference (Pioneer’s fallback is pre-inference when the router declines). We do have a request cache and a soft budget; they do not document those as router features. FireRouter caches the **routing decision** inside a conversation; we rescore every request.

## What we already match

- Virtual model + keep `router/auto` in the response body
- Effort dial, allow-list, fallback, max-regret (shape, not calibration)
- OpenCode as the real harness proof
- Streaming + tools passthrough
- Decision logging (JSONL + `/replay` + `X-Router-*`)
- Honest “do not invent savings %”

## Still to implement (priority)

1. **Make medium not-always-Flash** — phase priors in YAML; raise plan/debug bars above 52 if those steps should use Pro; add `xhigh` (bar 53, K3 still gated).
2. **Overwrite `measured_success` from the 3×5 cache** when eval has been run.
3. **Dry-run playground** (`/v1/router/preview`) — Pioneer Routing Playground without spending.
4. **Structured observability** — `confidence`, `rule`, `reason_codes`, `savings_usd` vs premium/fallback (Pioneer `model_routing` / `pioneer_savings` / `/codex/session-savings`).
5. **Scorer-down fallback** — if `select_model` throws, still 200 with fallback (Pioneer: router unreachable → fallback, no client error).
6. **Live latency/health** from JSONL so score terms differentiate.
7. **Anthropic Messages / OpenAI Responses** only if Claude Code or Codex is in scope (currently cut; OpenCode is enough).
8. **Learned / per-request classifier** only if the cache beats rules (`DESIGN.md`).

## Do not chase

Cursor, K8s, BYOK, hosting Opus/Sonnet ourselves, inventing a savings percentage, matching Pioneer’s frontier pool.
