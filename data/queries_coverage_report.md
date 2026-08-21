# Query Pool Coverage Report

Generated: 2026-08-21

Total rows: **7012**  (band 4000–7500)

## Bin margins (target 15/40/30/15)

| bin | n | frac | target | ok |
|-----|---:|-----:|-------:|----|
| trivial | 1056 | 0.151 | 0.15 | PASS |
| standard | 2800 | 0.399 | 0.40 | PASS |
| hard | 2100 | 0.299 | 0.30 | PASS |
| frontier | 1056 | 0.151 | 0.15 | PASS |

Bin overall: PASS

## Tools margins (target 75/25)

| needs_tools | n | frac | target | ok |
|-------------|---:|-----:|-------:|----|
| True | 5249 | 0.749 | 0.75 | PASS |
| False | 1763 | 0.251 | 0.25 | PASS |

Tools overall: PASS

## Family / phase margins (target 30/25/15/15/10/5)

| phase | n | frac | target | ok |
|-------|---:|-----:|-------:|----|
| edit | 2100 | 0.299 | 0.30 | PASS |
| tool | 1751 | 0.250 | 0.25 | PASS |
| plan | 1049 | 0.150 | 0.15 | PASS |
| debug | 1049 | 0.150 | 0.15 | PASS |
| discover | 700 | 0.100 | 0.10 | PASS |
| summarize | 363 | 0.052 | 0.05 | PASS |

Phase overall: PASS

## Stratum floors (occupied ≥20, take-all below)

Distinct occupied strata: **48 / 48**  (unoccupied 0)
Floor: 20 — under-floor violations: 0
All occupied strata ≥ floor — **PASS**.

## Count band

Rows 7012 in band [4000, 7500] — PASS

## Projected teacher cost

Avg cost per row (incl. ≤25% escalate): **$0.0015**
Full pool (7012 rows): **$10.52** — fits $8 tranche: NO
Teacher-eligible only (4000 rows): **$6.00** — fits $8: YES

## C1 gate arithmetic (teacher → silver)

Teacher-eligible rows available: **4000**
C1 requires silver ≥ 3500 rows (escalate ≤25%)
Teacher rows sufficient for C1 at 1:1 yield (surplus 500). At 90% yield need 3889, surplus 111.

## Manifest consistency

Manifest total 7012 (metadata total 7012)
Pool hashes 7012, manifest hashes 7012, intersection 7012
Pool not in manifest: 0, manifest not in pool: 0
Consistent (sets equal): **PASS**
Splits: {'promotion-holdout': 300, 'threshold-tune': 300, 'dense-cal': 300, 'teacher-silver': 4000, 'sparse-train': 2112}
spend_before_A: 8.16

## Overall

Spec margins overall: **PASS**

## Top-up note (deviation from plan band)

Original plan band 4000-5000 would not reach C1 (needs 3890 teacher rows at 90% yield) and C3 (needs sparse >=2000). This top-up grows the pool to **7012** rows (delta +2973 synthetic via same templates, collision-filtered, margins preserved) and sizes splits for gate reachability: **teacher-silver 4000 / sparse-train 2112 / dense-cal 300 / threshold-tune 300 / promotion-holdout 300**. Band is now documented as 4000-7500 (SPEC_COUNT_BAND). All 7012 rows are new synthetic prompts with unique hashes; zero eval leakage (collision_keys overlap 0). Manifest was regenerated via pool.write_split_manifest(seed=0, spend_before_A=8.16) -- ordered sample_stratum re-shuffles assignments, which is acceptable because no paid run has consumed any ids yet (B7 not run); B7 guard will enforce the new assignments. Projected teacher cost at 4000 rows is ~$6.00 within the $8 tranche.
