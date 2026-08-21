# C3 Gate Report — Sparse Gold Tranche B

**Date:** 2026-08-21
**Tranche:** B (second n≈1000 × 4 anchors)
**Budget cap:** $15 (BUDGET_LIMIT_USD=42.757, starting spend $27.757)

## Spend

| Metric | Value |
|--------|-------|
| Spend before tranche B | $27.7569 |
| Spend after tranche B | $32.5681 |
| Delta | $4.8112 |
| Cap | $15.00 |

## Cumulative Sparse Gold

| Metric | Value |
|--------|-------|
| Tranche A cells | 4,000 |
| Tranche B cells | 4,000 |
| Pre-existing cells | 1,258 |
| Merged total (deduped) | 9,156 |
| Observed (non-unobserved) | 8,954 |
| Unique queries (observed) | 2,296 |
| Models | 4 (Flash, Qwen3.6-27B, Kimi-K2.7-Code, DeepSeek-V4-Pro) |

## C3 Gate Results

| Gate | Threshold | Actual | Verdict |
|------|-----------|--------|---------|
| Cumulative unique queries | ≥ 1,800 | 2,296 | **PASS** |
| Held-out Brier < base-rate Brier | < 0.050079 | 0.042330 | **PASS** |
| Spearman ρ (anchor win-rate ordering) | > 0 | 0.800 | **PASS** |

### Brier Detail

- Train split: 7,154 observed cells (80% by prompt)
- Held-out split: 1,800 observed cells (20% by prompt)
- Held-out Brier (logistic): 0.042330
- Base-rate Brier (predict mean): 0.050079
- Improvement: 15.5% reduction

### Spearman Detail

Anchor win-rates by half:

| Anchor | Half A win-rate | Half B win-rate | Rank A | Rank B |
|--------|----------------|----------------|--------|--------|
| deepseek-v4-flash | 0.9982 | 0.9964 | 4 | 3 |
| qwen3.6-27b | 0.9982 | 1.0000 | 3 | 4 |
| kimi-k2.7-code | 0.7224 | 0.8102 | 1 | 1 |
| deepseek-v4-pro | 0.9937 | 0.9964 | 2 | 2 |

Spearman ρ = 0.800 (strong positive correlation of anchor ordering across halves).

## Overall Verdict: **PASS**

All three C3 gates pass. Sparse gold is sufficient for proceeding to Phase E (dense/cal).
