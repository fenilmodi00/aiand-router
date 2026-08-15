# Task 3 re-review: Train gold / teacher / cal-slice fit

Original `674e885..59aa821` + fix `4f65b69..1d30631`. Verdict against `.scratch/scorer-pioneer-lift/task-3-train-brief.md`, `.scratch/scorer-pioneer-lift/task-3-fix-brief.md`, and spec stories 13–30, 35, 42–45.

### Spec Compliance

- ✅ Spec compliant. Gold y is verified (`_pytest_verify` / `expected`) then gateway proxy then weak nonempty; budget 429 / pre-call skip cells are `unobserved: true` with no gold y; silver regularizes only unobserved `(prompt, model_id)` in `gold_ids`; per-model intercepts from train-gold marginals with `w[0]` frozen; Platt on held-out gold cal-prompt tail only; `bin_weights` from `featurize_observable`; artifact `not_spec_floors: true`; no K3 gold cells; no `TRAINED_PATH` flip; code default `BUDGET_LIMIT_USD` still `"15"`. Owned files only (`train.py`, `cache.py`, `tests/test_train.py`).
- Extra vs shortest-diff brief (not a spec miss): `relabel` / `salvage` CLIs and in-loop teacher salvage; `SPARSE_LIMIT` 200→400. Same extras as the first review; fix brief said do not chase.
- ⚠️ Tests not re-run (implementer: `tests/test_train.py` 18 passed, TDD red/green per finding). Named outside-diff checks below.

Named risks (outside the concatenated diff, one check each):

- **Train/serve intercept:** `scorer.py:149-150` is `sigmoid(a * (ic + w·x) + b)` with leading bias `1.0` at `scorer.py:80`. With `_fit_binary_intercept` freezing `w[0]=0` (`train.py:581-584`), serve is `ic + 0`, not a double-counted marginal.
- **Cache vs budget:** `_complete` (`train.py:145-150`) returns cache hits before the 429 branch; cache hits stay unbilled observed gold. 429 is skip/missing, not a billing bug.
- **Fit on 429 rows:** `fit_scorer` (`train.py:631-636`) builds `observed` / `gold_cells` / cal split only from `not unobserved`. 429 rows have no `success` key, so they cannot enter train-gold y, intercepts, or Platt.

### Strengths

- **Previous Critical actually fixed.** `run_gold` (`train.py:490-499`) on `status == 429` writes `unobserved: True` and omits `success` / `success_tier`. `_complete` (`train.py:149-150`) still returns 429 on pre-call budget skip. `tests/test_train.py:490-518` (`test_gold_budget_skip_is_unobserved_not_failure`): exhausted spend, zero provider calls, no observed `success=False`, sparse anchors disjoint from observed ids, unobserved rows have no `success` key.
- **Previous Important 2 actually fixed.** `_gold_label` (`train.py:390-397`): query-level `tests_passed` removed; `expected` then `_pytest_verify` (already above) before `tool_calls`. `test_gold_expected_beats_tool_calls_proxy` (`tests/test_train.py:468-476`); `test_gold_query_level_tests_passed_is_not_y` (`:479-487`) plus json/one-word (`:321-322`) now expect weak/proxy, not stamped verified fail.
- **Previous Important 3 actually fixed.** `_fit_binary_intercept` (`train.py:581-584`) skips dim 0 on grad and update; `w` starts at zeros so `w[0]` stays 0. `test_fit_binary_intercept_freezes_bias_column` (`tests/test_train.py:521-526`).
- **Previous Important 4 actually fixed.** `test_fit_calibrates_on_held_out_gold_cal_slice_only` (`tests/test_train.py:400-413`) reconstructs Platt zs/ys from the sorted-tail cal-gold (all `success=False` in the fixture) and asserts artifact `platt.a` / `platt.b` equal `_fit_platt` on that slice. Silver y=1.0 or train-gold (all True) leaking in would move `a`,`b`. `assert cal_gold and all(r["success"] is False …)` also fails if `_split_cal_prompts` stops being the fail tail.
- Held-out cal slice is still the right shape: unique gold prompts, sorted tail, `CAL_FRAC=0.2` (`train.py:605-615`, `634-636`, `668-679`). Silver cannot enter Platt (`645-656` skip observed cells; cal loop is gold-only). Catalog ids that appear only in silver get no `weights` / `p_success` / intercept (`651-652`).
- Bin head uses request-observable features (`train.py:685`, `_row_x_observable`). Sparse = Flash + measured trio; dense = enabled catalog except K3 (`train.py:468-476`). Parse-fail still escalates outside the quality cap (`train.py:246-255`). Cache key includes `reasoning_effort`.

### Issues

#### Critical

None. The prior budget-429-as-observed-fail finding is addressed by `1d30631`.

#### Important

None. The prior verified-over-proxy, query-level `tests_passed`, intercept+bias double-count, and unpinned Platt-test findings are addressed by `1d30631`.

#### Minor

1. **Scope: `relabel` / `salvage` subcommands + in-loop teacher salvage** — `train.py:287-319`, `722-815`, `843-849`. Brief: do not rewrite the CLI; shortest diff. Parse-fail already escalates in `run_teacher`. Harmless if unused; fix brief said do not chase.
2. **GLM teacher never gets `reasoning_effort`** — `train.py:195-196`. Motif gets `low`; `MIN_REASONING_EFFORT` lists GLM as `none` but only `_gold_body` applies the map. Escalate JSON can still burn tokens on reasoning (story 18).
3. **Escalated silver rows still record `teacher: CHEAP_TEACHER`** — `train.py:262` vs salvage `310`. Operator JSONL cannot tell Motif vs GLM except on the extra salvage path.
4. **Concurrent budget check is TOCTOU** — `train.py:149-164`. `total()` is outside the lock; `add` is inside. Up to `TRAIN_CONCURRENCY` in-flight calls can all pass the cap. Soft budget (story 21). After this fix those extras are real observed cells, not fake 429 failures.
5. **`n_gold` counts unobserved rows** — `train.py:705` is `len(gold)`, not `len(observed)`. A budget-capped sparse run will report `n_gold` as written lines (including 429 skips), not measured cells. `n_cal` stays cal-gold cells only (`:706`). Informational; does not enter y.

### Assessment

**Task quality: Approved**

Requirements for success gold, missingness, silver-unobserved, intercepts, cal-slice Platt, and the four open review items are implemented and seam-tested in the owned files. Remaining items are the deferred Minors (extra CLIs, GLM effort, teacher field, TOCTOU) plus `n_gold` counting skips. This task gate can close; defer Minors to whole-branch review.
