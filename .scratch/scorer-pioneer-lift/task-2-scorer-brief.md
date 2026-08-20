# Task 2: Scorer serve lift (predicted bin, intercepts, P-spread at hop)

Read first: `.scratch/scorer-pioneer-lift/spec.md` Implementation Decisions + user stories 5–9, 29–31, 35, 46. `CONTEXT.md`.

## Where this fits

Live hop already uses Rec A in-process. Smoke Scorer compresses P(success) and/or ignores predicted bin. This task lifts **serve-side** scoring so cheapest-above-bar can move. Fit/calibrator training lives in `train.py` (Task 3) — you consume artifact fields, you do not own the train CLI.

## Owned files (ONLY these)

- `src/aiand_router/scorer.py`
- `tests/test_scorer.py`

Do **not** edit `train.py`, `cache.py`, `app.py`, `replay_report.py`. If you need a new artifact key (`intercepts`, `bin_weights`, per-id Platt, `calibrator`), document it in the report so Task 3 can write it. Support **both** old artifacts (weights + global platt) and new ones so hop tests stay green.

## Implement (TDD)

Existing tests in `tests/test_scorer.py` and `tests/test_trained_hop.py` (you must not edit hop tests; they must stay green) are the contract.

Required serve behavior:

1. Complexity bin is **predicted from request-observable features only** (`featurize_observable`: phase family, tools, tokens). Live hop must not require train-only `hint_bin` on the HTTP request.
2. `score_eligible` applies **per-model intercepts** from the artifact when present, then feature correction, then post-hoc calibrator (`platt` or equivalent). Missing intercept → 0 (old artifacts still work).
3. Predicted P(success) must be able to **spread** across models on the same query (test with different intercepts/weights; mean |max-min| not collapsed by identity Platt).
4. Scorer-down stays the caller’s problem (`apply_trained_path`); do not invent fake P(success) when artifact is missing/corrupt.
5. Effort knobs stay 0.05/0.30, 0.10/0.20, 0.20/0.15, 0.60/0.03. No `xhigh`.
6. Rec A only: logistic (or artifact weights) + post-hoc calibrator. **Do not add GBDT or live embed.** Skip optional embed ablation.
7. Artifact flag `not_spec_floors` may be read but must not be overwritten here.

Ponytail: keep the current numpy-free / in-process style. No new deps. Shortest diff.

Tests: public behavior only (P(success) values, predicted bin labels, pick inputs). Do not assert sklearn internals.

There is already WIP in `scorer.py` (`featurize_observable`, `predict_complexity_bin`, `intercepts`). **Extend it; do not revert.** Fill remaining spec gaps (e.g. intercepts actually change P(success); predicted bin used when `hint_bin` is None).

## Commit

Commit only owned files. Message: why (serve-side predicted bin + intercepts so cheapest-above-bar can separate models).

## Report

Write `.scratch/scorer-pioneer-lift/task-2-scorer-report.md`. Return status, commits, test summary. Note any artifact schema Task 3 must emit.
