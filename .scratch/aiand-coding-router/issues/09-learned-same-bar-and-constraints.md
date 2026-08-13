# 09 — Learned path uses the same bar and constraints as rules

**What to build:** If the learned flag is on, selection still respects hard constraints and the phase/effort quality bar. Summarize cannot pick K3; tool requests still require tool-capable models; over-budget models still drop. Default path stays dark (rules only) until comparison says learned won.

Prototype decision shape (keep this contract):

```
Decision:
  model, phase, threshold, reason, candidates[]

eligible.sort(key=lambda m: (m.unit_cost, -m.quality))  # rules
# learned may change the sort/score only — same eligible set
```

**Blocked by:** None — can start immediately.

**Status:** resolved

- [x] Rules and learned share one eligibility filter (enabled, allow-list, tools, context, budget, AA present, premium-floor / phase bar)
- [x] With learned flag on + `x-agent-phase: summarize`, upstream model is not K3; reason may say learned
- [x] With learned flag on + tools present, only tool-capable models are forwarded
- [x] Without the flag, gateway still uses rules only
- [x] Proven on the fake-upstream HTTP seam
