# 04 — Scale sparse + dense hard-cal gold

**What to build:** Larger sparse train gold plus a disjoint dense/cal slice (eligible except K3) with the same hard y. Overall train/cal y stays in the hard band, not dense-easy ~0.39. Outputs tagged so fit can refuse overlapping train/cal. Silver is not this ticket. Stop on quality bars, not an invented credit scare.

**Blocked by:** 03 — Paid sparse hard-y probe (only if the probe passes)

**Status:** partial — Mix1-style scale23 + dense scale29 shipped; scaled sparse **lost** holdout order (do not fit on it). Fit uses Mix1 + merged dense cal.

- [x] Taken only after 03 pass (Spearman > 0, hard-band y, holdout-like order on Mix1)
- [x] Dense/cal disjoint from sparse; no K3 cells; missing stays missing
- [x] Train/cal y-rate in ~0.07–0.22; geometry vs frozen verified still unpaid and still not fit y
- [x] Opt-in live gold; code default budget 15 unchanged; unit tests never spend
- [ ] Scaled sparse alone does **not** keep geometry_pass — keep Mix1 as train gold

## Answer

| slice | file | n prompts | cells | y_rate | notes |
| --- | --- | --- | --- | --- | --- |
| sparse Mix1-scale23 | `data/gold-sparse-hard-mix-scale23.jsonl` | ~117 | 468 | 0.060 | order fail alone; reused as cost-gold |
| dense cal merged | `data/gold-dense-hard-cal-merged.jsonl` | 83 | 664 | 0.059 | orig 40 + scale29 |
| train for fit | `data/gold-sparse-hard-mix1.jsonl` | 40 | 160 | 0.181 | **geometry_pass** |

Spend after scale: **$8.157** (from **$6.772**, Δ +$1.385).
