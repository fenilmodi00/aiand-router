# Task 1 fix: lock fixture arithmetic + holdout warning

Review: `.scratch/scorer-pioneer-lift/task-1-review.md`
Fix Important findings only. Do not chase Minors.

## Important 1 — tests must lock policy/calibration arithmetic

`tests/test_replay_report.py` currently only checks ranges and `isinstance`. Pin the 4×2 fixture:

- oracle success is the known fraction (review: 3/4 with a no-winner prompt — verify from `tests/fixtures/replay_gold.jsonl`, use that literal)
- always-Flash vs always-strong success/cost differ in the direction the fixture implies
- `rules_cost_delta` sign is the trained−rules list-price delta (never named savings)
- Brier is vs a constant base rate of selected-hop labels (skill formula, not a dummy 0.0)
- disagreement > 0 remains

Public seam only. Do not assert sklearn internals.

## Important 2 — CLI `--gold` is the holdout file

Do not invent a hash split. Add CLI help (and/or a report field) that `--gold` is assumed unused for train/cal. Passing mixed gold contaminates the gate.

## Owned files

`src/aiand_router/replay_report.py`, `tests/test_replay_report.py` only.

TDD, covering tests, commit, append to `.scratch/scorer-pioneer-lift/task-1-replay-report.md`.
