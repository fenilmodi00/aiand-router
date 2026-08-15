# Task 2: Scorer serve lift — report

Status: **DONE_WITH_CONCERNS**

Commit: `436a8bb` Lift serve-side predicted bin and intercepts so cheapest-above-bar can separate models.

Owned files only: `src/aiand_router/scorer.py`, `tests/test_scorer.py`.

## What shipped

Serve-side Rec A scoring now:

1. Predicts complexity bin from **request-observable** features (`featurize_observable`: phase family, tools, tokens). Live hop does not need `hint_bin`.
2. Applies **per-model intercepts** (missing → 0), then feature correction `w·x`, then post-hoc calibrator.
3. Spreads P(success) across models on the same query when intercepts/weights differ (identity Platt does not collapse them).
4. Keeps old artifacts working: `p_success` table, or `weights` + global `platt` with no `intercepts`.
5. Leaves scorer-down to `apply_trained_path` (no invented P(success)).
6. Effort knobs unchanged: 0.05/0.30, 0.10/0.20, 0.20/0.15, 0.60/0.03. No `xhigh`.
7. Reads `not_spec_floors` but never writes/overwrites it.

Formula: `P = sigmoid(a * (intercept + w·x) + b)`.

Skipped (YAGNI): GBDT, live embed, per-id Platt, isotonic. Intercepts are the per-model term; global Platt/`calibrator` is the post-hoc map.

## TDD

- Existing WIP (`featurize_observable`, `predict_complexity_bin`, intercepts) was **not reverted**.
- New public-API tests added first. `test_calibrator_key_applies_after_intercepts` **failed red** (P stayed 0.5; `calibrator` ignored).
- Green: `_calibrator_ab` — use `calibrator.{a,b}` if present, else `platt.{a,b}`, else identity `(1, 0)`.
- Contract tests that locked WIP (intercepts change P; predicted bin when `hint_bin is None`; P-spread ≥ 0.10; old table/weights artifacts) passed against the existing intercept path.

## Tests

```
tests/test_scorer.py          14 passed
tests/test_trained_hop.py     21 passed (unedited)
tests/test_train.py + replay  green with scorer+hop (56 passed combined)
full suite                    114 passed, 7 failed
```

The 7 failures are `tests/test_gateway.py` `KeyError: 'x-router-reason'` — not in owned files, not caused by this serve lift.

## Follow-up: reject wrong-length weights

Commit: `a2adc15` Reject wrong-length scorer weights so stale artifacts fall back instead of silently mis-scoring.

Important finding: `_dot` truncated mismatched `weights` vs 17-dim `featurize`, so old short vectors silently mis-scored instead of falling back to `p_success`.

Fix: in `score_eligible`, if `len(w) != len(x)`, ignore those weights. Use that id's `p_success` if present, else omit. No invented P.

### TDD

- Red: `test_score_eligible_short_weights_use_table_p_not_truncated_dot` — 9-dim `weights` + table `p_success=0.42` scored `{m/a: ~1.0, m/b: ~1.0}` (truncated-dot) instead of `{m/a: 0.42}`.
- Green: `if not w or len(w) != len(x)` → table P for that id, else omit.

### Tests (after fix)

```
tests/test_scorer.py::test_score_eligible_short_weights_use_table_p_not_truncated_dot
  RED:  AssertionError: {'m/a': 0.9999999999999065, 'm/b': 0.9999999999999065} != {'m/a': 0.42}
  GREEN: passed

tests/test_scorer.py          15 passed
tests/test_trained_hop.py     21 passed (unedited)
36 passed, 1 warning in 2.32s
```

## Artifact schema Task 3 must emit

Serve consumes these keys. Fit should write them on the **cal slice** for Platt (not in-sample).

| Key | Required for logistic hop | Shape | Notes |
|-----|---------------------------|-------|--------|
| `weights` | yes (else table fallback) | `{model_id: [float, ...]}` | Dim = `featurize` = **17**: bias, tools, log1p(tokens), 4 token bins, **4 predicted-bin one-hots**, 6 phase families. Missing id → no live P(success). |
| `intercepts` | yes for spread | `{model_id: float}` | Gold-marginal logit. **Missing id → 0** (old artifacts keep working). |
| `bin_weights` | yes for live bin | `{trivial\|standard\|hard\|frontier: [float, ...]}` | Dim = `featurize_observable` = **13**: bias, tools, log1p, 4 token bins, 6 families. **No hint_bin.** Empty → fall back to `complexity_bin`. |
| `platt` | yes | `{a: float, b: float}` | Global Platt on logit `intercept + w·x`. Identity default `a=1, b=0`. Fit on **held-out gold cal slice only**. |
| `calibrator` | optional alias | `{kind: "platt", a, b}` | If `a` or `b` present, **overrides** `platt`. Same apply path. |
| `complexity_bin` | fallback | one of the four bins | Used only when `bin_weights` absent (old / table artifacts). |
| `p_success` | old-artifact fallback | `{model_id: float}` | Used only when `weights` is missing/empty. Hop fixture path. |
| `not_spec_floors` | keep `true` | bool | Serve **must not** overwrite. Stay true until production floors. |

**Not required this cycle:** per-id Platt, `platt_by_id`, GBDT blobs, embed vectors.

**Do not** put train-only `hint_bin` on the live request. Train JSONL may still record it; at serve the bin head uses observables, then that predicted bin is the one-hot inside `featurize`.

## Feature index (so fit matches serve)

`featurize_observable` (bin head):

`[1, needs_tools, log1p(tokens), t<128, 128≤t<512, 512≤t<2048, t≥2048, discover, plan, edit, tool, debug, summarize]`

`featurize` (P(success) head): same, with four bin one-hots **after** token bins and **before** families:

`[..., tok≥2048, trivial, standard, hard, frontier, discover, ...]`
