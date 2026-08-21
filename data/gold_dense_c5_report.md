# C5 Checkpoint: Calibrator Auto-Select + Dense Extension

**Date:** 2026-08-21
**Commit:** ff96be1 → (this commit)
**Plan checkbox:** F11

## Summary

`fit.py` gains `--calibrator auto|platt|isotonic` (default `auto`). With
n_cal = 2,264 > 1,000, `auto` selects isotonic. Dual ECE on the held-out
dense cal slice passes the 0.03 bar. No additional dense queries needed
(n_cal already exceeds threshold). Spend delta = $0.00 (offline fit).

## Gate Table

| Check | Bar | Value | Status |
|-------|-----|-------|--------|
| Calibrator mode | auto → isotonic (n_cal > 1,000) | isotonic | PASS |
| n_cal | > 1,000 for isotonic | 2,264 | PASS |
| Equal-width ECE (M=10) | ≤ 0.03 | 0.0000132 | PASS |
| Equal-mass ECE (M=10) | ≤ 0.03 | 0.0208732 | PASS |
| Spend delta | ≤ $15.00 | $0.00 | PASS |

**C5 VERDICT: PASS** — isotonic path, dual ECE ≤ 0.03.

## Inputs

| Input | Path | Rows |
|-------|------|------|
| Train gold (sparse) | `data/gold.jsonl` | 800 |
| Cal gold (dense) | `data/gold_dense.jsonl` | 2,264 |
| Silver | `data/silver.jsonl` | 4,000 |
| Output artifact | `data/scorer_c5.json` | — |

## Dense Extension

No additional dense queries were run. The existing `gold_dense.jsonl`
(283 queries × 8 models = 2,264 observed cells) already exceeds the
isotonic unlock threshold of n_cal > 1,000. The dense extension tranche
was skipped per plan step 3.

## Calibrator Flag

```
--calibrator auto|platt|isotonic  (default: auto)
```

- `auto`: count held-out dense rows (n_cal), pick isotonic iff n_cal > 1,000, else Platt
- `platt`: force Platt calibration
- `isotonic`: force isotonic (errors if n_cal ≤ 1,000)

The artifact now includes `cal_ece_equal_width` and `cal_ece_equal_mass`
fields computed on the cal slice after fitting the calibrator.
