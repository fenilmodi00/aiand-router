# Task 1: Offline replay report (the spec's single new seam)

Read first: `.scratch/scorer-pioneer-lift/spec.md` (Testing Decisions), `CONTEXT.md`.

## Where this fits

The hop is already shipped (shadow default). This task is the **quality seam**: an offline replay report over a frozen gold JSONL + current Scorer artifact + rules picker. Same inputs, no live aiand. It extends the existing helper pattern; do **not** add a second HTTP stack or Pioneer dashboard.

## Owned files (ONLY these)

- `src/aiand_router/replay_report.py` (new)
- `tests/test_replay_report.py` (new)
- `tests/fixtures/replay_gold.jsonl` (tiny fixture; create if needed)
- Optional: `tests/fixtures/replay_scorer.json` tiny artifact fixture

Do **not** edit `scorer.py`, `train.py`, `cache.py`, `app.py`, or hop tests. Import public APIs:

- `aiand_router.scorer`: `load_scorer`, `score_eligible`, `pick_cheapest_above_bar`, `effort_knobs`, `trained_select` as needed
- `aiand_router.router`: `select_model`, `load_models`, `load_config`, `eligible_models`, `estimate_cost`

If a public function is missing, **do not patch other modules**. Call what exists; put any thin adapter in `replay_report.py`.

## Implement (TDD)

Write the failing test first, then the module.

Public function, e.g. `replay_report(gold_path, artifact, models, cfg, holdout_ids=...) -> dict` (names may match repo style).

On a **holdout** prompt split unused for train/calibrator, the report must include:

- rules vs trained vs oracle (cheapest gold-success) vs always-Flash vs always-strong: **success rate** and **list-price cost**
- disagreement rate (rules pick ≠ trained pick)
- rank AUC and mean per-prompt P(success) spread
- Brier and Brier skill vs constant base rate
- equal-width ECE (M=10) and equal-mass ECE on **selected-hop** P(success)

Assertion helpers:

- Unit tests use the **tiny fixture** only
- Fail CI if replay is invoked in unit tests against **production** floors (Verified n≥300, staffed promotion bars). Provide a helper that unit tests call so production floors cannot sneak into `tests/test_replay_report.py`.
- Do **not** assert sklearn internals.

Numeric bars from the spec (replay gate, not Verified promotion) may be **computed and reported**. Unit tests must **not** require a smoke artifact to pass AUC ≥ 0.65. Fixture gold should make metrics computable and helpers testable (e.g. disagreement > 0 on the fixture; Brier skill defined; ECE defined). A separate function `replay_gate_pass(report) -> bool` may exist for operators; unit tests must not fail the suite when that returns False on a toy fixture.

CLI: `python -m aiand_router.replay_report` reading gold JSONL + artifact path is fine. No live provider.

## Constraints

- Ponytail: shortest code. Stdlib + numpy/sklearn only if already a project dep. No new dependencies.
- Vocabulary: CONTEXT.md (`success gold`, `calibrated P(success)`, `complexity bin`, never “learned router”).
- Savings still vs `most_expensive_eligible` only if you mention cost; cost vs rules is **rules cost delta**, never named savings %.
- Do not flip `TRAINED_PATH`. Do not stamp Verified. Do not clone Pioneer UI.
- Existing tests stay green. Run `tests/test_replay_report.py` then a focused related file if you import hop code.

## Commit

Commit **only owned files** on the current branch. Message: why (offline replay gate so shadow can be judged without live aiand).

## Report

Write full report to `.scratch/scorer-pioneer-lift/task-1-replay-report.md` (TDD red/green evidence, files, tests). Return status DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT, commits, one-line test summary.
