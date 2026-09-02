# 05: 30s ingress timeout kills slow requests in both streaming and non-streaming modes

**What to build:** Hard reasoning prompts that exceed ~30s to first byte are cut by the builddns platform's ingress proxy — non-streaming requests get `504 "upstream request timeout"`, streaming requests get a severed connection with no data frame ever delivered. The router's own request budget is 600s, so this is entirely in the deploy platform layer. After this ticket, a legitimately slow (30–60s-to-first-byte) request either completes or fails with a clean, client-actionable error, in both modes.

Evidence: reproduced 4/4 on a single AIME-grade prompt (three non-stream 504s at ~30.8s + one stream cut at 31.8s with zero content frames); one more case in the 60-prompt run. Note the interaction: hardest-tier prompts on flash are exactly the slow ones, so ticket 04 (correct escalation) reduces exposure, and ticket 03 changes which models clients can name. Options to evaluate with the platform: raise the ingress timeout; or first-byte SLA. Also verify the router emits a usable error/telemetry when the ingress cuts an in-flight upstream call, instead of a dangling stream.

**Blocked by:** 04 (correct escalation changes which prompts are slow — measure after routing is fixed; keeps this ticket from chasing a moving target).

**Status:** ready-for-agent

- [ ] Ingress timeout raised to a value ≥ the worst-case legit first-byte latency, with the platform
- [ ] A 30–60s-to-first-byte request completes in streaming mode (verified with the AIME repro prompt)
- [ ] Same for non-streaming, or a documented decision that clients must stream for long requests
- [ ] Router-side behavior when the platform cuts an in-flight call is a clean error, not a dangling stream
- [ ] Re-run the slow-prompt repro from the QA report; passes or fails cleanly

## Progress (2026-09-02) — router-side mitigations landed
- Client-facing SSE keepalive extended to the OpenAI chat surface (internal/proxy/service.go):
  ": keepalive" comment frame after ROUTER_SSE_KEEPALIVE_INTERVAL_SECONDS of client-facing
  silence, same invariants as the Anthropic wrap (innermost, arms on first byte, record-boundary
  only, deferred Close). This keeps client connections alive through long reasoning phases and
  gives the ingress bytes to forward.
- Client-disconnect mid-stream is classified non-retryable (shouldFailover: context.Canceled /
  DeadlineExceeded → false) — no wasted second upstream call; verified by existing
  TestShouldFailover cases.
- Raising the builddns ingress timeout itself is a platform-team action outside this repo;
  also note D1's fix routes hard prompts to mid-tier models with lower first-byte latency,
  reducing exposure. Recommend raising ingress timeout to >=60s with the platform regardless.
- Not yet verifiable here: no docker for the smoke stack; keepalive verified by unit tests
  (sse_keepalive_test.go + proxy integration test) — live streams were too chatty to produce
  a 15s silence gap.
