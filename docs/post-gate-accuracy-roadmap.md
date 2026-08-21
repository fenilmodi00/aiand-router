# Post-Gate Accuracy Roadmap

Status: **reference only**. Nothing here is scoped for implementation. This note exists so the next accuracy lever is already named when its preconditions clear.

## Preconditions (both required)

1. The **Verified gate passes** (see `docs/runbook-production.md` section a): all four bars hold on session gold, n ≥ 300, verdict no longer `do-not-promote`. As of 2026-08-21 the verdict is `do-not-promote` (`data/verified_gate_report.md`).
2. The **embed-ablation gate opens** (section c of the runbook): embedding vectors are kept only if held-out success-gold Brier is strictly better and ECE is not worse than features-only.

## Next lever: history-conditioned routing

Both candidate designs condition the routing decision on conversation history rather than scoring each hop in isolation. This matters for coding agents, where a hop's difficulty depends on what happened in earlier turns (a debug hop after three failed edits is not equivalent to a fresh debug hop).

- **MTRouter** (ACL 2026) — multi-turn LLM routing: routes each turn using the dialogue context accumulated so far.
- **SWE-Router** (arXiv: [2607.00053](https://arxiv.org/abs/2607.00053)) — routing for SWE-bench-style agentic software engineering, conditioned on agent trajectory state.

## How it would slot in (orientation only, no commitment)

The router already receives phase and effort per hop; history conditioning would extend the trained hop's feature set with trajectory-derived signals (prior hop outcomes, escalation counts, session position). Any such change re-enters through the same path as everything else: refit offline, shadow, then the Verified gate. The flywheel log's `session_id` field (see runbook section b) is the join key that makes per-session features possible.

## Explicitly out of scope here

No implementation plan, no feature list, no training recipe. Pick this up only after both preconditions hold.
