# Router Beta QA — Final Report (2026-09-02)

Endpoint: `https://router-fd92e147.us-east-1b.builddns.com` · 4 subagents + root verification · all requests capped `max_tokens:80` · total upstream spend ≈ $0.02.

## Verdict: NOT ready for public launch — 3 defects, 1 strategy gap

### Launch blockers

**B1 — Multi-turn conversations 100% broken (all surfaces).**
Any request containing an assistant-role message fails:
- `/v1/chat/completions` → 400 `"The inference backend rejected this request as invalid."`
- `/v1/messages` (Anthropic surface) → 400, same body
- long-prefix variant → 503 `"cluster scorer failed"` (failover path after the 400)

Root cause (verified by wire-shape isolation): `writeResponsesContentMessage`
(`internal/translate/emit_openai_responses.go:415-419`) emits assistant history as
easy-input items with `content:[{"type":"output_text",...}]`. The aiand upstream
rejects that combination — `output_text` is only valid inside fully-typed
`{"type":"message"}` items. Evidence matrix (direct `/v1/responses` probes):

| assistant input shape | result |
|---|---|
| string content | 200 |
| easy-input + `input_text` parts | 200 |
| easy-input + `output_text` parts (**router's shape**) | **400** |
| typed `{"type":"message"}` + `output_text` | 200 |

Fix: emit `input_text` for assistant easy-input items (or emit fully-typed
message items). Unit test `responses_from_openai_chat_test.go:83` currently
asserts the broken shape — update it. Add a smoke cassette with
assistant-role traffic (none of the 14 existing cassettes contain any).

**B2 — Client-input validation gaps → misleading 503s.**
`messages` missing/empty and `max_tokens` -5 or non-numeric return
503 `"Router unavailable: cluster scorer failed and no fallback is configured."`
(4 of 40 breaker cases, same signature). These are client errors and should be
rejected 400 at the handler before routing (`internal/api/openai/completions.go`
pre-dispatch validation). Related: `model:"gpt-4o"` / `""` / missing are
silently rerouted to deepseek with no warning — decide: 404/400 or documented
aliasing, not silence.

**B3 — 30s ingress timeout kills slow requests (both modes).**
Hard reasoning prompts exceed 30s-to-first-byte on deepseek-v4-flash → the
deploy platform's proxy returns 504 `"upstream request timeout"` (non-stream)
or cuts the SSE stream (`curl: (18) transfer closed`, stream mode). Router's
own budget is 600s (`internal/server/server.go` chatCompletionTimeout) — the
cut is the builddns ingress, outside the router. Reproduced 4/4 on one
AIME-grade prompt; RoutingRunner saw 1 more (medium-long-03). Mitigations:
raise ingress timeout, or ensure first-byte arrives <30s (see D1 — correct
routing fixes this as a side effect).

### Strategy gap

**D1 — Routing is degenerate: zero difficulty awareness.**
60/60 prompts (easy → hardest, AIME/GPQA-grade included) routed to
`deepseek-ai/deepseek-v4-flash`. No escalation to qwen/motif/kimi/glm ever
fired. Cross-tabs by difficulty and by length are flat. The router currently
behaves as a static proxy to the cheapest model. Note the interaction: hardest
prompts on flash are exactly the >30s requests causing B3.
(Not necessarily misconfiguration — verify the deployed cluster bundle is
the intended `artifacts/latest` and that `auto` maps to the cluster scorer.)

### What works

- Auth: clean 401s on all 5 bad-key cases; no leaks.
- Malformed bodies: clean 400s (6/6). Note: missing `Content-Type: application/json` is accepted (200) — lenient but harmless.
- Streaming: valid SSE, `[DONE]` termination, `stream:"true"` string coerced.
- Concurrency: 20 parallel → 20/20 valid, 0 5xx, wall 52s.
- No crashes, no stack traces, no Go internals leaked beyond the B2 message.
- Unicode/150KB payloads/param spam: tolerated or cleanly rejected.
- **Prompt cache tokens DO flow back**: `usage.prompt_tokens_details.cached_tokens`
  (only cache field, streaming and non-streaming). Identical repeats: 512/512/512
  cached. Code-prefix variants: block-granular (512→768). Router keeps cache
  affinity on same-route requests. Caveat: billing-side discount application
  is not verifiable from the API surface (token counts only, no cost object).

### Quality (60-prompt matrix, GSM8K/MATH/HumanEval/GPQA/AIME/HLE/tau2-style)

| tier | pass | partial | fail | error |
|---|---|---|---|---|
| easy | 9 | 6 | 0 | 0 |
| medium | 7 | 7 | 0 | 1 (504) |
| hard | 14 | 1 | 0 | 0 |
| hardest | 12 | 3 | 0 | 0 |

42 pass / 17 partial / 0 fail / 1 error. No truncation at 80 tokens
(all `finish_reason:"stop"`); partials are open-ended prompts without
expected answers. Latency: easy mean 4.9s → hardest mean 9.9s, p95 25.5s,
max 28.7s (flash reasoning scales with difficulty).

### Cost (actual vs baseline, catalog prices)

| | total (60 req) | per req | savings |
|---|---|---|---|
| actual (98.3% deepseek-flash) | **$0.0156** | $0.000265 | — |
| kimi-k3 flagship baseline | $0.7259 | $0.0121 | **97.8%** |
| glm-5.3 baseline | $0.2328 | $0.0039 | **93.3%** |

Savings are real but currently trivially explained: a static proxy to the
cheapest model always saves ~98% vs flagship. The "smart routing saves money"
claim is NOT yet demonstrated — that requires escalation to actually fire on
hard prompts and still beat the flagship baseline (it would: even 100% glm-5.3
is 93% cheaper than kimi-k3).

Minor: flash burns ~60 reasoning tokens on "hi how are you" (79 total for a
greeting) — consider `reasoning_effort:none` for easy-tier traffic.

### Cache-hit prompt patterns (reusable list)

Full list: `cache_prompts.md`. Headlines: shared stable prefix first +
variable tail last; one frozen system prompt per surface; append-don't-rewrite
in conversations; byte-identical prefixes sized past block granularity
(≥768 tok for full-block hits); same route + close-in-time bursts; pre-warm
before latency-sensitive bursts.

## Artifacts

- `prompts.json` — 60 prompts, 12 cells (4 difficulty × 3 length), verified answers
- `breaker_results.json` — 40 edge cases
- `cache_results.json` / `cache_prompts.md` — cache scenarios + pattern list
- `routing_results.json` / `routing_summary.md` — full per-prompt records + tables
- `FINAL_REPORT.md` — this file

## Recommended order before public launch

1. Fix B1 (one-line part-type fix + test update + smoke cassette) — unblocks all multi-turn clients and CacheTester scenario B.
2. Fix B2 (pre-dispatch validation for messages/max_tokens; decide model-fallback policy).
3. Investigate D1 (routing escalation never fires) — also reduces B3 exposure.
4. Raise or route around the 30s ingress timeout (B3).
