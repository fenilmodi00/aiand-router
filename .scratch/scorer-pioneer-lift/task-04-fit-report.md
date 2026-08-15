# Task 04 report: Silver + Rec A fit

**Status:** DONE_WITH_CONCERNS  
**Commit:** `15e629b` — Omit live calibrated P(success) unless a gold intercept exists so silver cannot unstick an unseen catalog id.

Owned: `src/aiand_router/scorer.py`, `tests/test_scorer.py`, `tests/test_train.py`, `tests/test_trained_hop.py`. Did not rewrite pool, hop policy, replay gate (05), or gold y (02). Did not add GBDT (06). Did not flip `TRAINED_PATH` (07). Artifact still `not_spec_floors`. Code default `BUDGET_LIMIT_USD` stays **15**.

Task 2/3 + issues 02/03 already shipped Motif→GLM teacher, parse-fail escalate, unlabeled, silver-on-unobserved fit, gold intercepts, cal-slice Platt, `n_train==0` skip, predicted bin, shadow hop. This ticket filled the **live** gap and locked the rest with TDD.

## What shipped

1. **Live P(success):** `score_eligible` emits calibrated logistic P only for ids with a **gold intercept**. Weights without intercepts (silver-alone) are ignored. Cal-only ids still onboard via the gold `p_success` table (issue 03), not silver logistic.
2. **Fit locks (already true, now tested):** silver regularizer only on unobserved cells; unlabeled rows do not enter weights; intercepts from train-gold marginals; Platt y is cal-gold; artifact `not_spec_floors` with no threshold / max_regret / gbdt.
3. **Hop lock:** Rec A artifact (weights + intercepts + `bin_weights`) loads on **shadow**; complexity bin from request-observable features; no `hint_bin` header.

Operator recipe unchanged: `fit --gold sparse --cal dense --silver silver.jsonl --out data/scorer.json` (`AIAND_TRAIN=1`; unit tests use FakeProvider).

## TDD

### RED → GREEN 1 — live score omits silver-only weights

```
python -m pytest tests/test_scorer.py::test_score_eligible_omits_ids_with_silver_weights_but_no_gold_intercept -q --tb=short
```

**RED:** `assert 'm/silver' not in ps` failed — logistic path used `ic=0` and emitted `P=0.5`.  
**GREEN:** if `intercepts` is present, ids missing from it skip logistic; table onboard only when `p_success` has gold.

### Locks (already green; no production change)

| Test | What it locks |
|---|---|
| `test_fit_then_score_omits_ids_with_no_success_gold` | fit+`score_eligible` omits silver-only ids; `not_spec_floors`; no threshold/gbdt |
| `test_fit_silver_unobserved_regularizes_weights_not_intercepts_or_platt` | unobserved silver moves weights; intercepts = gold logit; unlabeled ignored; Platt y = cal-gold |
| `test_fit_cal_only_id_onboards_via_table_not_calibrated_logistic` | cal-only live P is gold table mean, not silver 0.1 |
| `test_shadow_loads_rec_a_and_predicts_bin_without_hint_bin` | shadow + predicted bin, no `hint_bin` |

Existing seams left in place: parse-fail escalate, unlabeled teacher, K3 skip, cal-slice Platt, `n_train==0` skip intercept/weight.

## Tests

- Focused: `tests/test_train.py` + `test_scorer.py` + `test_trained_hop.py` → **76 passed**
- Full suite: **157 passed, 7 failed** — the pre-existing `test_gateway.py` `x-router-reason` failures (out of scope)

## Files

- `src/aiand_router/scorer.py` — skip calibrated logistic unless gold intercept exists
- `tests/test_scorer.py` — live silver-only omit
- `tests/test_train.py` — fit+score, unobserved regularizer, cal-only table onboard
- `tests/test_trained_hop.py` — shadow Rec A without `hint_bin`

## Skipped (YAGNI)

Replay gate (05), GBDT (06), `TRAINED_PATH=trained` (07), live embed, Rec B, Pioneer dashboard, retune-on-silver, KL silver prior (logistic soft-label is enough).

## Concerns

1. Cal-only ids still get a **constant** live P from the gold table (issue 03 onboard), not Platt-calibrated logistic. Silver cannot invent that row; a dense/cal cell can.
2. Adding silver on unobserved cells slightly moves Platt `a`,`b` via changed weights (second-order). Platt **y** stays cal-gold; the ticket lock pins reconstruction, not equality vs a gold-only fit.
3. Student P(success) features at fit still use JSONL `hint_bin` when present; serve substitutes the predicted bin. Train/serve skew if pool `hint_bin` ≠ predicted bin.
4. Teacher salvage CLI and in-loop GLM salvage remain from Task 3 (scope extra, not this ticket).
