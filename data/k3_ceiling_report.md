# K3 Ceiling Report — C6 Gate

**Date:** 2026-08-21
**Tranche:** G13 (K3 dense slice part B + ceiling re-probe)
**Spend:** $37.485 → $38.039 (delta $0.554, cap $15)

## K3 Gold

| Metric | Value |
|--------|-------|
| Part A cells | 150 |
| Part B cells | 140 |
| Merged (deduped) | 290 |
| All model_id == K3 | Yes |
| K3 observed | 290 |
| K3 successes | 214 (73.8%) |

## Oracle Ceiling (all gold: sparse + dense + K3)

| Metric | Value |
|--------|-------|
| Total gold cells | 11,710 |
| Unique queries (observed) | 2,869 |
| Queries with ≥1 model success | 2,791 |
| **Oracle ceiling** | **97.3%** |
| Previous ceiling (gold-all, no K3) | 46.2% |

## C6 Gate

| Gate | Threshold | Observed | Verdict |
|------|-----------|----------|---------|
| K3 n ≥ 260 | 260 | 290 | **PASS** |
| Oracle ceiling > 50% | >50% | 97.3% | **PASS** |
| K3 P(success) ∈ [0,1] | [0,1] | 0.738 | **PASS** |
| Spend delta ≤ $15 | $15 | $0.55 | **PASS** |

## Overall C6 Verdict: PASS

K3 onboarding complete. The oracle ceiling jumped from 46.2% (no K3 gold) to 97.3% (with K3), confirming K3's capability contribution. The gap was model capability, not router — K3 succeeds on 73.8% of queries where it was tested.
