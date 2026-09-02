# 07: Cheap tier burns reasoning tokens on trivial prompts

**What to build:** Trivial traffic on the low tier wastes reasoning: "hi, how are you" on deepseek-v4-flash spent 33 reasoning tokens producing a 79-token total response for a greeting (repeated across the easy tier in the benchmark run). Once per-tier routing policy is real (ticket 04), easy-tier traffic should run with minimal/no reasoning effort where the model supports it (flash serves effort `none`), cutting both latency and cost on exactly the requests where reasoning adds nothing. After this ticket, an easy-tier greeting completes in well under the current ~5s mean with no reasoning-token overhead, and quality on the easy tier of the benchmark matrix does not regress.

**Blocked by:** 04 (effort policy per tier is part of the routing-policy work; setting it before routing escalates correctly would tune against a broken baseline).

**Status:** ready-for-agent

- [ ] Easy-tier traffic routed to flash runs with no/minimal reasoning effort
- [ ] Benchmark matrix easy tier re-run: pass rate unchanged, latency and cost reduced, recorded
- [ ] Hardest-tier behavior untouched (still full effort where escalated)

## Outcome (2026-09-02)

Fixed at the hard-pin seam rather than per-tier: every hard-pinned turn
(classifier/probe/title-gen/compaction — trivially short internal calls) now
dispatches at minimal reasoning effort via applyPolicyEffortToEmit(opts, none),
which clamps to the model's declared menu (flash → none; kimi-k2.7 [high] →
high, i.e. unchanged; motif-3 → low). Emit sites: ProxyMessages, sibling
failover, ProxyOpenAIChatCompletion (internal/proxy/service.go).

Post-D1 context: easy-tier *auto* traffic no longer reaches flash by default
(the scorer picks mid-tier motif-3 for the QA matrix), so the QA observation
(flash burning reasoning on greetings) now applies only to the remaining
hard-pin paths — which this change covers. Scored turns keep their policy
effort untouched (regression test pins this).

Tests: internal/proxy/hardpin_effort_test.go — hard-pinned classifier turn on
flash emits reasoning.effort=none (asserted on the outbound upstream body);
non-hard-pinned turn on the same model emits no effort override.
