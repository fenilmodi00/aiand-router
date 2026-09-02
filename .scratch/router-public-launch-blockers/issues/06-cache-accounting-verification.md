# 06: Prompt-cache token accounting is passed through but unverified for billing, and multi-turn cache patterns are untestable

**What to build:** The router passes provider prompt-cache telemetry through: `usage.prompt_tokens_details.cached_tokens` is the only cache field surfaced, it works in streaming and non-streaming, identical repeats show 512/512/512 cached tokens, and code-prefix variants grow block-granularly (512 → 768). Two gaps remain: (1) whether the cache-read discount is actually applied in billing is unverifiable from the API surface (token counts only, no cost object), and (2) the growing-conversation cache pattern — the most valuable real-world pattern — could not be tested because every multi-turn request failed (ticket 01's bug). After this ticket, cache accounting is trusted end to end: conversation-append cache patterns are re-measured post-01, and the billing question has a documented answer (verified discount application, or an explicit statement that cache accounting is pass-through-only and a follow-up owned by billing).

Deliverable includes the reusable cache-hit prompt-pattern guide (shared stable prefix first + variable tail last; one frozen system prompt per surface; append-don't-rewrite conversations; byte-identical prefixes sized past block granularity; same-route close-in-time bursts; pre-warm before latency-sensitive bursts) — checked into docs so customers can structure prompts for cache hits.

**Blocked by:** 01 (multi-turn must work before conversation-append cache patterns can be measured).

**Status:** ready-for-agent

- [ ] Growing-conversation scenario re-run: cached_tokens grows turn over turn, recorded
- [ ] Billing question answered in writing: discount applied where, or explicit pass-through statement
- [ ] Cache-hit prompt-pattern guide checked into docs
- [ ] Streaming conversation still surfaces cached_tokens in the final usage chunk

## Progress (2026-09-02)

- [x] Cache-hit prompt-pattern guide checked into docs: `docs/CACHE_PATTERNS.md` (plus index entry in `docs/README.md`).
- [x] Billing question answered in writing (Billing section in `docs/CACHE_PATTERNS.md`): **the discount is applied, not pass-through** — `catalog.EffectiveInputCost` prices cache-read tokens at the binding's cache-read multiplier, and the proxy feeds it `cached_tokens` everywhere it computes cost (`internal/proxy/service.go`, `internal/proxy/auxiliary_inference.go`), so persisted `actual_input_cost_usd`, dashboard metrics, the analytics export, and `cache_input_savings_usd` all reflect the discounted rate. Payment itself rides the installation's own upstream key (the provider bills its own cache pricing); there is no router-side prepaid drawdown in this deploy. No broken debit path found.
- [ ] Growing-conversation scenario re-run (`cached_tokens` grows turn over turn): depends on the B1 fix verification, which the coordinator runs live (multi-turn requests were 503 at QA time).
- [ ] Streaming conversation surfaces `cached_tokens` in the final usage chunk: to be confirmed in the same live pass (QA scenario D confirmed it pre-B1; re-confirm post-fix).

## Growing-conversation measurement (2026-09-02, coordinator, post-B1)
Live on the local ORT router (motif-3 via scorer, block-sized ~1600-token stable prefix):
turn 1 cached_tokens=0 (cold), turns 2-4 cached_tokens=1024 (block-granular, past the 768
threshold), model held by cache affinity across the conversation. Ticket-01 fix unblocked this
measurement; results recorded. Billing answer: discount applied (all router-computed costs flow
through catalog.EffectiveInputCost with the per-binding CacheReadMultiplier) — see
docs/CACHE_PATTERNS.md Billing section.
