# Task 3 fix: unobserved gold + verified-over-proxy

Review: `.scratch/scorer-pioneer-lift/task-3-review.md`
Fix Critical + Important. Do not chase Minors (`relabel`/`salvage` CLI, GLM reasoning_effort, teacher field, TOCTOU).

## Critical 1 — budget 429 cells must stay missing

`train.py` `_complete` 429 / pre-call budget skip currently writes `success=False`, `unobserved: False`. Spec: missing ≠ 0.

Fix: omit the cell or set `unobserved: true` and do **not** emit gold y. Do not fit on those rows.

TDD: fake provider + exhausted spend → no observed fail cell for the skipped model.

## Important 2 — verified overrides proxy

Gold y order: verified (`expected`, per-completion tests / `tests_passed` from **this** candidate) → gateway proxy (tools/JSON) → nonempty only when nothing stronger exists.

- Do not return `tool_calls` proxy success before `expected`.
- Do not copy query-level `tests_passed` onto every model. Derive from this completion (existing `_pytest_verify`) or store on the gold cell.

## Important 3 — intercept vs bias column

`_fit_binary_intercept` still learns `w[0]` while `intercepts` already lock the gold marginal. Serve applies `ic + w[0]`. Freeze `w[0]=0` when intercepts are used, **in train.py only**. Do not edit `scorer.py` (sibling fix owns it).

## Important 4 — cal-slice test must pin the invariant

`tests/test_train.py` cal-slice test must fail if silver or train-gold leaks into Platt (not just check keys / `n_cal` / gemma absent).

## Owned files

`src/aiand_router/train.py`, `tests/test_train.py`. `cache.py` only if required.

TDD, run `tests/test_train.py`, commit, append to `.scratch/scorer-pioneer-lift/task-3-train-report.md`.
