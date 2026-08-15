# Task 03 report: Dense/cal gold slice



**Status:** DONE_WITH_CONCERNS  

**Commit:** `2cc87f5` — Hold out dense/cal gold so Platt and new-id P(success) have measured cells unused for train weights.



Owned: `src/aiand_router/train.py`, `tests/test_train.py`. Did not rewrite pool, hop, replay, or issue-02 sparse y. Did not flip `TRAINED_PATH`. Did not expand into silver/gate/threshold (04). Artifact still `not_spec_floors`. Code default `BUDGET_LIMIT_USD` stays **15**.



Task 3 already had `--dense` (enabled catalog except K3) and a prompt-tail cal split inside `--gold`. This ticket made the dense slice held-out and unused for train weights.



## What shipped



1. **Dense gold cells** run every enabled catalog id except K3 (tools filter unchanged). JSONL marks `"dense": true`. Observed cells have `success` / `success_tier` from the same `_gold_label` as issue 02. K3 never. Missing (429 / budget skip) stays unobserved, not 0.

2. **Disjoint queries:** `gold --dense --exclude <sparse-queries-or-gold.jsonl>` skips those prompts.

3. **Unused for train weights:** `fit --gold sparse.jsonl --cal dense.jsonl` — intercepts/weights from `--gold` only; Platt from `--cal`; new-id `p_success` from cal cells (no weights invented). Concatenated `--gold` with `dense: true` rows is the same split without `--cal`. Prompt-tail holdout remains the fallback when neither `--cal` nor `dense` tags are present.



Operator recipe:



```

python -m aiand_router.train gold --queries pool.jsonl --out sparse.jsonl

python -m aiand_router.train gold --queries pool.jsonl --out dense.jsonl --dense --exclude sparse.jsonl

python -m aiand_router.train fit --gold sparse.jsonl --cal dense.jsonl --out data/scorer.json

```



(`AIAND_TRAIN=1`; live spend still opt-in. Unit tests use FakeProvider.)



## TDD



### RED → GREEN 1 — dense JSONL marks every eligible id except K3



```

python -m pytest tests/test_train.py::test_dense_gold_runs_every_eligible_id_except_k3 -q --tb=short

```



**RED:** `assert all(r.get("dense") is True)` failed — cells existed (8 = enabled minus K3) but had no `dense` field.  

**GREEN:** `--dense` writes `"dense": true` on observed and unobserved cells.



### RED → GREEN 2 — `--cal` unused for train weights; new-id onboard



```

python -m pytest tests/test_train.py::test_fit_dense_cal_unused_for_train_weights -q --tb=short

```



**RED:** `unrecognized arguments: --cal`.  

**GREEN:** `--cal` is Platt + `p_success` for cal-only ids (Gemma onboard via table); Flash intercept stays `_logit(1.0)` from sparse train (would drop if cal fails leaked). `not_spec_floors` still true.



### RED → GREEN 3 — dense queries disjoint from sparse train prompts



```

python -m pytest tests/test_train.py::test_dense_gold_excludes_sparse_train_prompts -q --tb=short

```



**RED:** `unrecognized arguments: --exclude`.  

**GREEN:** `--exclude` JSONL `prompt`s are not run.



### RED → GREEN 4 — concatenated `dense: true` still unused for train weights



```

python -m pytest tests/test_train.py::test_fit_dense_tagged_rows_unused_for_train_weights -q --tb=short

```



**RED:** intercept `1.10` (prompt-tail leaked False cal rows into train) vs `_logit(1.0)` ≈ `13.82`.  

**GREEN:** `dense: true` rows are cal even when names would sort into the train tail.



Issue-02 y (verified metadata first, `needs_tools` + missing `tool_calls` is fail, dump `resolved` / query-level `tests_passed` not y, unobserved stays missing) is unchanged shared `_gold_label` / `run_gold`.



## Tests



```

tests/test_train.py     31 passed

full suite              148 passed, 7 failed

```



The 7 failures are `tests/test_gateway.py` `KeyError: 'x-router-reason'` — out of scope.



## Concerns



1. `--exclude` is operator-owned. Same `--queries` for sparse and dense without `--exclude` still overlaps at gold-run time; fit will not use dense-tagged / `--cal` rows as train weights either way.

2. New-id onboard is artifact `p_success` (serve table fallback), not intercepts/weights. Ids that only appear on the cal slice stay out of `weights`.

3. Enabled teachers (Motif, GLM) are dense gold cells because the spec is “enabled catalog except K3.”

4. Prompt-tail 20% split remains when fit gets untagged mixed gold without `--cal`.



Skipped: Pioneer dashboard, live embed, Rec B, K3 gold, silver/gate/threshold (04), automatic `TRAINED_PATH=trained`.



## Fix



Critical + Important from `task-03-cal-review.md`. Exclude before `sample_stratum` so same-pool `--dense --exclude` can fill n from leftover; `--dense` requires `--exclude`; empty leftover fails closed (nonzero, no write); skip intercept/weight fit when `train_counts[mid] == 0`. Minors untouched.



### RED → GREEN 5 — same-pool exclude-before-sample is nonempty and disjoint



```

python -m pytest tests/test_train.py::test_dense_exclude_before_sample_same_pool_is_nonempty_and_disjoint tests/test_train.py::test_dense_exclude_empty_leftover_fails_closed tests/test_train.py::test_dense_requires_exclude tests/test_train.py::test_fit_cal_only_id_with_silver_gets_no_weights -q --tb=short

```



**RED:** 4 failed.

- same-pool: `assert rows` — dense JSONL empty (`gold done cells=0`) because sample-then-exclude dropped the dense prefix of the sparse sample.

- empty leftover: `assert code != 0` — wrote empty JSONL and returned 0.

- `--dense` without `--exclude`: `assert code != 0` — ran and wrote overlapping cal.

- cal-only + silver: Gemma appeared in `weights` (`train_counts==0` → `_logit(0.5)` + silver).



**GREEN:** exclude-then-sample; `--dense` refuses without `--exclude`; leftover-empty returns 2 and writes nothing; `n_train == 0` skips intercepts/weights (`p_success` onboard stays).



### Covering tests



```

python -m pytest tests/test_train.py -q --tb=short

```



```

...................................                                      [100%]

35 passed, 1 warning in 3.66s

```



(Starlette/httpx deprecation warning only; not a test failure.)


