# 03 — Dense/cal gold slice



**What to build:** A held-out dense gold slice where every eligible catalog id except K3 is actually run, so Platt and new-id calibrated P(success) have measured cells. The slice is disjoint from the train sparse gold rows used for feature fit, and it is unused for train weights — calibrator and new-id onboard only. Success gold uses the same y definition as sparse gold. Missing cells stay missing.



**Blocked by:** 01 — Stratum-sampled query pool



**Status:** resolved



- [x] Every eligible catalog id except K3 is run on the slice

- [x] No K3 gold cells

- [x] Missing cells stay missing, not labeled 0

- [x] Slice is unused for train weights (calibrator / new-id onboard only)

- [x] Slice is disjoint from train sparse gold rows used for feature fit

- [x] Same y definition as 02 — Sparse success-gold run



## Answer



Dense `--gold --dense` runs every enabled catalog id except K3, tags cells `dense: true`, and uses issue-02 y (`success` / `success_tier`; 429/budget skip stay unobserved). `--exclude` drops sparse-train prompts so the slice is disjoint. `fit --gold sparse --cal dense` (or concatenated gold with `dense: true`) fits intercepts/weights on sparse train rows only; Platt and new-id `p_success` come from the cal slice. K3 never. Opt-in, cache-first, `BUDGET_LIMIT_USD` default 15.



Files: `src/aiand_router/train.py`, `tests/test_train.py`. Commit `2cc87f5`. Report: `.scratch/scorer-pioneer-lift/task-03-cal-report.md`.


