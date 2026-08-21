# C2 Gate Report — Sparse Gold Tranche A

**Date:** 2026-08-21
**Commit:** (pending)
**Spend before:** $23.021
**Spend after:** $27.757
**Spend delta:** $4.736 (cap $15.00)

## Run Configuration

| Parameter | Value |
|-----------|-------|
| Command | `python -m aiand_router.train gold --queries data/queries_spec.jsonl --split sparse-train --limit 1000 --out data/gold_sparse_part_a.jsonl` |
| Split | `sparse-train` (manifest-filtered, disjoint from teacher-silver) |
| Limit | 1000 queries (first half of 2112 sparse-train ids) |
| Anchors | SPARSE_ANCHORS = (deepseek-v4-flash, qwen3.6-27b, kimi-k2.7-code, deepseek-v4-pro) |
| K3 | Excluded (assert zero) |
| BUDGET_LIMIT_USD | 38.021 ($23.021 + $15 cap) |
| GOLD_MAX_TOKENS | 1024 |
| GOLD_REASONING_MAX_TOKENS | 4096 |

## C2 Gate Evaluation

| Check | Threshold | Actual | Status |
|-------|-----------|--------|--------|
| deepseek-v4-flash rows | >= 800 | 1000 | PASS |
| qwen3.6-27b rows | >= 800 | 1000 | PASS |
| kimi-k2.7-code rows | >= 800 | 1000 | PASS |
| deepseek-v4-pro rows | >= 800 | 1000 | PASS |
| K3 rows | 0 | 0 | PASS |
| Spend delta | <= $15.00 | $4.74 | PASS |

**C2 VERDICT: PASS**

## Per-Anchor Coverage

| Anchor | Rows | Success | Fail | Success Rate |
|--------|------|---------|------|-------------|
| deepseek-ai/deepseek-v4-flash | 1000 | 997 | 3 | 99.7% |
| qwen/qwen3.6-27b | 1000 | 999 | 1 | 99.9% |
| moonshotai/kimi-k2.7-code | 1000 | 786 | 214 | 78.6% |
| deepseek-ai/deepseek-v4-pro | 1000 | 994 | 6 | 99.4% |
| **Total** | **4000** | **3776** | **224** | **94.4%** |

## Success Tier Distribution

All 4 anchors share the same per-query tier assignment (tier is query-determined, not model-determined):

| Tier | Count | % | Description |
|------|-------|---|-------------|
| proxy | 2932 | 73.3% | Gateway rule: tool_calls present, or needs_tools without tool_calls, or JSON/keyword format checks |
| weak | 1068 | 26.7% | Text-presence check only (no specific verification possible) |
| verified | 0 | 0.0% | pytest/harness (no sparse-train queries have dump-provided tests/expected/schema) |

## Harness-vs-Gateway Label Ratio

| Source | Count | % |
|--------|-------|---|
| Harness (verified tier) | 0 | 0.0% |
| Gateway rule (proxy tier) | 2932 | 73.3% |
| Weak (text presence) | 1068 | 26.7% |

**Ratio:** harness:proxy = 0.000 (no sparse-train queries have dump-provided harness; all labels are gateway-rule or weak text-presence).

## Notes

- All 4 anchors were eligible for all 1000 queries (no eligibility filter shortfalls).
- Kimi-K2.7-Code has a notably lower success rate (78.6%) vs the other three (99.4-99.9%), driven by the weak tier where text presence checks fail more often.
- Cache resume worked: the first ~400 queries overlapped with a previous run (gold_sparse.jsonl had 1720 lines), and those cells were served from cache (free).
- No 429 rate-limit responses (unobserved=0).
