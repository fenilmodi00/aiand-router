# C4 Gate Report — Dense Calibration Slice + Threshold-Tune Split

**Date:** 2026-08-21
**Tranche:** E10 (dense-cal n~300 x eligible-except-K3 + threshold-tune n~300 x SPARSE_ANCHORS)
**Budget cap:** $15 (BUDGET_LIMIT_USD=47.568, starting spend $32.568)

## Spend

| Metric | Value |
|--------|-------|
| Spend before E10 | $32.568065 |
| Spend after E10 | $36.181042 |
| Delta | $3.612977 |
| Cap | $15.00 |

## Dense Gold (data/gold_dense.jsonl)

| Metric | Value |
|--------|-------|
| Total cells | 2,264 |
| Observed (non-unobserved) | 2,264 |
| Unobserved (429 rate-limited) | 0 |
| Unique queries | 283 |
| Models | 8 (all eligible except K3) |
| Manifest split | dense-cal (300 assigned, 283 achieved) |

### Per-model coverage

| Model | Cells | Threshold | Verdict |
|-------|------:|----------:|---------|
| deepseek-ai/deepseek-v4-flash | 283 | 250 | PASS |
| deepseek-ai/deepseek-v4-pro | 283 | 250 | PASS |
| google/gemma-4-31b-it | 283 | 250 | PASS |
| moonshotai/kimi-k2.7-code | 283 | 250 | PASS |
| motif-technologies/motif-3 | 283 | 250 | PASS |
| openai/gpt-oss-120b | 283 | 250 | PASS |
| qwen/qwen3.6-27b | 283 | 250 | PASS |
| zai-org/glm-5.2 | 283 | 250 | PASS |

**Shortfall note:** 283 achieved vs 300 assigned. 17 queries excluded by `--exclude data/gold_sparse.jsonl` (belt-and-suspenders disjointness guard). 283 >= 250 threshold, no cap-stop.

## Threshold-Tune Gold (data/threshold_tune.jsonl)

| Metric | Value |
|--------|-------|
| Total cells | 1,200 |
| Observed | 1,200 |
| Unobserved | 0 |
| Unique queries | 300 |
| Models | 4 (SPARSE_ANCHORS: Flash, Qwen3.6-27B, Kimi-K2.7-Code, DeepSeek-V4-Pro) |
| Manifest split | threshold-tune (300 assigned, 300 achieved) |

## C4 Gate Results

| Gate | Threshold | Actual | Verdict |
|------|-----------|--------|---------|
| Disjoint-set assertion | 0 overlaps | 0 overlaps, total=3012=union | **PASS** |
| Per-model coverage (dense) | n>=250 | 283 per model | **PASS** |
| ECE trending down | ECE < baseline | 0.1625 < 0.3396 | **PASS** |
| Spend delta | <= $15 | $3.613 | **PASS** |

### Disjoint-set detail

| Split | Size |
|-------|-----:|
| sparse-train | 2,112 |
| dense-cal | 300 |
| threshold-tune | 300 |
| promotion-holdout | 300 |
| **Total** | **3,012** |
| **Union** | **3,012** |

All pairwise intersections empty. Total == sum of split sizes == union size.

### ECE detail

Predictions: per-model base-rate from sparse gold (SPARSE_ANCHORS) or AA/100 (non-anchors).
Baseline: constant prediction = 0.748 (silver C1 mean p_success).

| Bin | n | avg_pred | avg_obs | gap |
|-----|--:|---------:|--------:|----:|
| [0.2,0.3) | 283 | 0.2400 | 0.2615 | 0.0215 |
| [0.3,0.4) | 283 | 0.3000 | 0.7880 | 0.4880 |
| [0.4,0.5) | 283 | 0.4700 | 0.8233 | 0.3533 |
| [0.5,0.6) | 283 | 0.5300 | 0.9435 | 0.4135 |
| [0.7,0.8) | 283 | 0.7666 | 0.7845 | 0.0178 |
| [0.9,1.0) | 849 | 0.9972 | 0.9953 | 0.0019 |

- ECE (per-model base-rate): 0.1625
- Baseline ECE (const=0.748): 0.3396
- Mean success rate (dense gold): 0.8233
- Trending down: YES (52.2% reduction vs baseline)

**Key finding:** SPARSE_ANCHOR predictions (bins [0.7,0.8) and [0.9,1.0)) are well-calibrated (gaps 0.02, 0.002). Non-anchor AA-based predictions (bins [0.3,0.4) through [0.5,0.6)) significantly underestimate actual success — AA indices are public priors that don't account for query-specific difficulty. Dense gold provides the calibration signal needed for these models.

## Overall Verdict: **PASS**

All four C4 gates pass. Dense calibration slice and threshold-tune split are ready for Phase F (calibration unlock).
