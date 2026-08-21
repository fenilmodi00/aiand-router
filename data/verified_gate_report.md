# Verified Gate Report — C8b Promotion Decision

**Date:** 2026-08-21
**Tranche:** H18
**Verdict:** `do-not-promote`
**Docker:** Available (v29.7.2) but Lite-300 proxy not run (budget/time constraint at this session stage)
**Spend delta:** $0.00 (evaluation on existing request log, no new API calls)

## Four-Bar Evaluation

Source: `data/requests.jsonl` via `eval.py:promotion_gate_verdict` (118 trained hops from H16 shadow run + 6 flashlight hops).

| Bar | Threshold | Observed | Verdict | Blocker |
|-----|-----------|----------|---------|---------|
| quality_session_gold | ≥ rules − 1pp | waived/not_started (n_sessions=0) | **FAIL** | No dual-policy session rows; verified_runner not executed against live gateway |
| quality_escalate | within 1pp of rules | escalate_rate=0.427 | **PASS** | — |
| cost_rules_delta | < 0 (trained cheaper) | +5.1e-06 per hop | **FAIL** | Trained scorer picks same model as rules (Flash); no cost savings |
| calibration_bss | > 0 | 0.0 | **FAIL** | Degenerate: all H16 calibration rows have tests_passed=True (synthetic queries with max_tokens=10) |
| calibration_ece_width | ≤ 0.03 | 0.968 | **FAIL** | Same degenerate calibration data |
| calibration_ece_mass | ≤ 0.03 | 0.968 (waived small_n) | **FAIL** | Same |
| floor_session_gold_n | ≥ 300 | 0 | **FAIL** | No session gold tasks collected |

## Blockers (enumerated)

1. **No session gold**: verified_runner was not executed against the gateway to produce dual-policy session rows. The Lite-300 proxy requires ~1200 API calls (~$6) and a running gateway session.
2. **Cost delta ≈ 0**: The fitted scorer picks the same model (Flash) as the rules path for most queries. The scorer optimizes for P(success), not cost savings vs rules. To get cost savings, the scorer would need to prefer cheaper models when their P(success) is close to the best.
3. **Degenerate calibration**: H16 shadow hops used synthetic queries (max_tokens=10), producing all tests_passed=True. Real flashlight tasks with mixed pass/fail are needed for meaningful BSS/ECE.

## What Would Fix the Blockers

1. Run verified_runner with real SWE-bench-Lite tasks through the gateway in dual-policy mode → produces session gold rows
2. Retune the scorer with a cost-aware objective (e.g., minimize cost subject to quality bar) instead of pure P(success)
3. Use real flashlight task outcomes (mixed pass/fail) for calibration metrics instead of synthetic max_tokens=10 probes

## Row Provenance

All values sourced from `data/requests.jsonl` rows where `baseline_model_id` is populated:
- 124 total rows (118 from H16 shadow/trained + 6 from flashlight)
- 77 rows have calibration-relevant fields (confidence, p_success)
- 0 rows have session_id joined to verified session results

## Conclusion

The fitted scorer is technically sound (isotonic calibrator, k3_prior=calibrated, logistic head wins Brier vs GBDT) but does NOT yet demonstrate cost savings or quality improvements over the rules path at scale. The promotion gate correctly fails open to `do-not-promote`.

Per the plan: "On fail → do-not-promote with blockers enumerated." TRAINED_PATH stays at its current value. The operator may flip it after addressing the blockers above.
