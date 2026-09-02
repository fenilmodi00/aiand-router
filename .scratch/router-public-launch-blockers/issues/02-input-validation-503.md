# 02: Client-input garbage returns misleading 503 "cluster scorer failed"

**What to build:** Malformed client input — `messages` missing, `messages: []`, `max_tokens: -5`, `max_tokens: "eighty"` — currently travels all the way into the routing layer and surfaces as `503 "Router unavailable: cluster scorer failed and no fallback is configured."` An operator seeing a 503 pages themselves for an outage that is actually a client sending junk; the client gets a retryable-signal error for their own mistake. After this ticket, these cases are rejected at the API layer with a clean 4xx validation error naming the offending field, before any routing happens, on every surface (OpenAI chat, Anthropic messages, responses).

Same signature, all four breaker cases, 100% deterministic. The validation belongs in pre-dispatch request validation at the handler level (both wire-format handlers), not inside the scorer — the scorer's fail-closed 503 contract is correct for genuine scorer failures and must stay untouched.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Missing/empty `messages` → 400 with a JSON validation error naming `messages`
- [ ] Non-positive or non-numeric `max_tokens` → 400 naming `max_tokens`
- [ ] Same guarantees on the Anthropic `/v1/messages` surface
- [ ] Genuinely-broken scorer still yields the fail-closed 503 (fail-closed contract intact)
- [ ] Breaker re-run: the four cases flip from "broke (503)" to "ok (clean 4xx)"

## Progress (2026-09-02) — FIXED
Pre-dispatch validation at the handler layer on both wire formats (internal/api/openai/validate.go,
internal/api/anthropic/validate.go): missing/empty messages and non-positive/non-numeric
max_tokens (and max_completion_tokens / max_output_tokens on the OpenAI surfaces) now 400
invalid_request_error naming the field, before any routing. Scorer fail-closed 503 contract
untouched (regression test proves cluster.ErrClusterUnavailable still 503s on a valid body).
Verified live on the local ORT router: all four breaker cases flip to clean 400s.
