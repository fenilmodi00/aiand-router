# Query Pool Coverage Report

Generated: 2026-08-21

Total rows: **4039**  (band 4000–5000)

## Bin margins (target 15/40/30/15)

| bin | n | frac | target | ok |
|-----|---:|-----:|-------:|----|
| trivial | 617 | 0.153 | 0.15 | PASS |
| standard | 1600 | 0.396 | 0.40 | PASS |
| hard | 1205 | 0.298 | 0.30 | PASS |
| frontier | 617 | 0.153 | 0.15 | PASS |

Bin overall: PASS

## Tools margins (target 75/25)

| needs_tools | n | frac | target | ok |
|-------------|---:|-----:|-------:|----|
| True | 3000 | 0.743 | 0.75 | PASS |
| False | 1039 | 0.257 | 0.25 | PASS |

Tools overall: PASS

## Family / phase margins (target 30/25/15/15/10/5)

| phase | n | frac | target | ok |
|-------|---:|-----:|-------:|----|
| edit | 1200 | 0.297 | 0.30 | PASS |
| tool | 1000 | 0.248 | 0.25 | PASS |
| plan | 600 | 0.149 | 0.15 | PASS |
| debug | 600 | 0.149 | 0.15 | PASS |
| discover | 410 | 0.102 | 0.10 | PASS |
| summarize | 229 | 0.057 | 0.05 | PASS |

Phase overall: PASS

## Stratum floors (occupied ≥20, take-all below)

Distinct occupied strata: **48 / 48**  (unoccupied 0)
Floor: 20 — under-floor violations: 0
All occupied strata ≥ floor — **PASS**.

## Count band

Rows 4039 in band [4000, 5000] — PASS

## Projected teacher cost

Avg cost per row (incl. ≤25% escalate): **$0.0015**
Full pool (4039 rows): **$6.06** — fits $8 tranche: YES
Teacher-eligible only (2139 rows): **$3.21** — fits $8: YES

## C1 gate arithmetic (teacher → silver)

Teacher-eligible rows available: **2139**
C1 requires silver ≥ 3500 rows (escalate ≤25%)
Shortfall vs 1:1 yield: **1361 rows** — need 3500 teacher rows for 3500 silver at 100% yield.
At 90% yield: need ~3889 teacher rows (have 2139, shortfall 1750).
Pool total 4039 rows @ $0.0015 avg = $6.06 (within $8: YES).
**Honest assessment:** pool is 4039 rows; teacher-eligible subset is the C1 bottleneck. Growing pool to ≥~4000 teacher-eligible rows (total ~5000) would clear C1 at 90% yield.

## Manifest consistency

Manifest total 4039 (metadata total 4039)
Pool hashes 4039, manifest hashes 4039, intersection 4039
Pool not in manifest: 0, manifest not in pool: 0
Consistent (sets equal): **PASS**
Splits: {'promotion-holdout': 300, 'threshold-tune': 300, 'dense-cal': 300, 'teacher-silver': 2139, 'sparse-train': 1000}
spend_before_A: 8.16

## Overall

Spec margins overall: **PASS**
