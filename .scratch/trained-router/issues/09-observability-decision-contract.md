# Observability Decision contract

Type: prototype
Status: resolved
Blocked by: none
Part of: [Production trained coding router](../map.md)

## Question

What should the **Decision + log/header contract** look like so a human can react to it before the spec freezes it?

Must include: selected model, phase (hint), complexity bin (`trivial` \| `standard` \| `hard` \| `frontier`), per-eligible P(success) (or at least winner confidence), rule (`threshold` | `max_regret` | `fallback_declined`), reason_codes, savings vs `most_expensive_eligible`, eligible ids.

Cheap artifact: a stub JSON row + example `X-Router-*` headers, not a dashboard. Link the prototype from this ticket; do not paste a huge dump into the issue body.

HITL — raise fidelity, then grill.

## Answer

**Slim headers (ex-ante) + full JSONL (ex-post).** Artifact: [observability-decision-contract.html](../prototypes/observability-decision-contract.html).

Headers (trained path): `X-Router-Model`, `Phase`, `Effort`, `Complexity-Bin`, `Confidence` (= winner P(success); omit if scorer down), `Rule` (`threshold` | `max_regret` | `fallback_declined`), `Path` (`rules` | `trained` | `shadow`), `Baseline-Model`, `Savings-Usd` (estimate), `Reason-Codes`, `Candidates` (eligible ids), `Threshold`, optional `Escalated-From` / `Trained-Would` (shadow only). Drop prose `X-Router-Reason` on the trained path; rules path may keep it.

JSONL is the record: all header fields plus `p_success` map for every eligible id, `max_regret`, realized `savings_usd` + `cost_usd` from actual tokens, `baseline_name: most_expensive_eligible`. Stream: estimate on headers at start; realized row when usage lands.

Shadow = **same row**: `path=shadow`, `selected` = rules pick, `trained_selected` / `trained_confidence`, `rules_cost_delta_usd` (trained − rules; not called savings). No second shadow file. Scorer down: `path=rules`, `rule=fallback_declined`, `reason_codes` include `scorer_down`, no fake confidence.

Rejected: fat headers, one JSON blob header, winner-only JSONL, separate shadow.jsonl, Pioneer rate-delta-only (no × tokens).

## Comments

- Prototype (throwaway): [observability-decision-contract.html](../prototypes/observability-decision-contract.html) — click scenarios for slim `X-Router-*` + JSONL. Not a dashboard.
- Grill: Q1–Q3 all take the recs (slim headers; ex-ante header / ex-post JSONL; full `p_success` + shadow on the same row).
- [Flywheel log store](22-flywheel-log-store.md) owns production location: same row, aiand infra, JSONL-compatible; this repo’s `data/requests.jsonl` is prototype only. Answer body unchanged.

- [Named savings baseline](06-named-savings-baseline.md) is resolved. Stamp savings vs `most_expensive_eligible` (log `baseline_model_id`; today usually K3 when eligible). Cost vs rules is **rules cost delta**, not savings. Ex-ante vs ex-post dollars still this ticket.
- [Complexity bin taxonomy](07-complexity-bin-taxonomy.md) is resolved. Live field/reason_code is `trivial|standard|hard|frontier` only. Bloom stays off the Decision/headers. Bin does not change the pick.
