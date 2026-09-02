# Prompt-cache hit patterns

The router passes the upstream provider's prompt cache through untouched — it
neither rewrites your messages into a fixed shape nor strips cache telemetry.
When a serving model has already seen a prefix of your prompt, you pay for (and
the router bills) the reused tokens at the model's cache-read rate, and the
response's `usage` object tells you it happened:

```json
"usage": {
  "prompt_tokens": 814,
  "prompt_tokens_details": { "cached_tokens": 512 }
}
```

`usage.prompt_tokens_details.cached_tokens` is the only cache field the router
surfaces, and it appears identically in streaming (in the final usage chunk) and
non-streaming responses. Two things worth knowing before you optimize:

- **`prompt_tokens` does not shrink on a hit.** The counter always reports the
  full prompt; only the priced split changes.
- **The field is absent — not zero — on a cold prompt.** A missing
  `prompt_tokens_details` on the first request of a pattern is itself the
  signal that the cache knows nothing about your prefix yet.

Reported hits are block-granular: serving models account for cached tokens in
fixed blocks (512 and 768 whole tokens in our verification), so small prefixes
score zero or partial hits and only full blocks count.

---

## 1. Stable prefix first, variable tail last

Everything that stays the same between requests belongs at the *front* of the
`messages` array; everything that changes belongs at the end. The cache matches
the longest unchanged byte prefix, so a variable value halfway through the
prompt cuts off everything after it.

```
messages:
  [{system,  <product instructions — frozen>},
   {user,    <docs / code / rules — frozen>},
   {user,    <this request's actual question>}]
```

## 2. One frozen system prompt per surface

Give each product surface (one assistant, one pipeline stage, one agent) a
single system string and never interpolate into it. Dates, user names, request
IDs, and per-request configuration in the system message poison the cache key
for every other request. If a value must vary, move it to the last user
message.

## 3. Append, don't rewrite, in conversations

In a multi-turn conversation, keep every prior message verbatim and in its
original order, and append each new turn at the end. Editing, re-summarizing,
trailing-whitespace changes, or reordering an earlier message invalidates the
cached prefix from that point on — the cache matcher compares bytes, not
meaning.

```
turn 1: [{user, q1}]
turn 2: [{user, q1}, {assistant, a1}, {user, q2}]     -- prefix intact
turn 3: [{user, q1}, {assistant, a1}, {user, q2},
         {assistant, a2}, {user, q3}]                 -- prefix intact
```

This is the highest-value pattern: on a growing conversation, each turn's
cached count should grow with the history. (If it doesn't after a router
upgrade, re-verify that the router forwarded your messages unmodified.)

## 4. Byte-identical prefixes, sized past block granularity

The matcher is exact-prefix: no fuzzy matching, no reformatting, no template
whitespace drift, no alternate spellings of the shared context. And because
hits are recorded in blocks, a shared snippet of a couple hundred tokens may
never register. Size shared prefixes in the hundreds-to-thousands of tokens,
with roughly 768 tokens the threshold where full-block hits show up in the
usage breakdown.

## 5. Fire cache-sensitive traffic on one route, close in time

A shared prefix pays off only when requests land on the same model — every
served model has its own cache. Route cache-sensitive traffic the same way
every time (a `model` pin is the strongest guarantee; see
[Configuration](CONFIGURATION.md#routing-intent-via-the-model-field)), and send
the bursts close together. Warm prefixes held across gaps of tens of seconds in
verification; prefixes left idle for minutes go cold.

## 6. Pre-warm before a latency-sensitive burst

The first request carrying a new prefix populates the cache and gets no hit.
If a burst of traffic needs to start fast, send one throwaway request
containing the full prefix (`cached_tokens` will be absent on it) before the
real traffic arrives, so the burst starts warm on turn one.

---

## Billing

**The cache-read discount is applied in the router's own cost accounting — it
is not pass-through-only.** Every cost the router records is computed by
`catalog.EffectiveInputCost` (`internal/router/catalog/cost.go`), which splits
reported input tokens into fresh tokens (full input rate) and cache-read tokens
(the model binding's cache-read multiplier; `DefaultCacheReadMultiplier` 0.5
applies where a model publishes none, `internal/router/catalog/catalog.go`).
The proxy feeds that function the `cached_tokens` count extracted from the
upstream usage — the `ActualInputCostUSD` / `RequestedInputCostUSD` fields in
`internal/proxy/service.go` (`ProxyMessages` and `ProxyOpenAIChatCompletion`)
and `internal/proxy/auxiliary_inference.go` — rounds it through
`catalog.USDToMicros`, and persists it in
`router.model_router_request_telemetry.actual_input_cost_usd`
(`db/queries/model_router_request_telemetry.sql`, written via
`internal/postgres/telemetry.go`). Consequently the dashboard metrics, the
`/v1/analytics/routing-decisions` cost columns, the OTel `cost.actual_*`
span attributes, and the additive `cache_input_savings_usd` summary field
(`internal/proxy/cache_savings.go`) all already reflect the discounted rate.

Two clarifications on who pays what:

- **Payment itself goes through your own upstream key.** Each installation
  serves traffic with its own provider key (BYOK or the deployment's
  `AIAND_API_KEY`), so the upstream provider's bill applies *its* cache
  pricing. The router does not operate a prepaid balance drawdown in this
  deploy — credit checks happen at dashboard login and at the upstream
  (an upstream `402 insufficient_credits` is passed through as-is).
- **Router semantic-cache hits never reach an upstream at all**, so they bill
  nothing: the (rare) exact or semantic re-serve writes a minimal telemetry
  row without usage or cost columns and does not affect your provider spend.
