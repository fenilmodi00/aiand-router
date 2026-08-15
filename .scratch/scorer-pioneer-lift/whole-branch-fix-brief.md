# Whole-branch must-fix (one pass)

Fix only these three. Do not chase deferred can-stay items or Fowler smells.

## 1. GLM teacher `reasoning_effort`

Spec: Teacher `max_completion_tokens` and minimum published `reasoning_effort` so JSON can finish.

`_teacher_call` sets effort only for Motif. Apply `MIN_REASONING_EFFORT` for GLM escalate/salvage too (`"none"` if that is the published min). File: `src/aiand_router/train.py`. Test in `tests/test_train.py` at the teacher-body seam.

## 2. Replay gate vs always-cheapest

Spec: “Disagreement > 0 (policy is not identical to always-cheapest-eligible).”

`replay_gate_pass` currently uses rules ≠ trained. Trained=always-Flash can pass if rules sometimes pick dear.

Fix: gate must fail when trained picks are identical to always-cheapest-eligible (the always-Flash / cheapest-eligible policy already in the report). Keep reporting rules≠trained as a field. File: `src/aiand_router/replay_report.py`, `tests/test_replay_report.py`.

## 3. Rank AUC skip unscored

Spec: rank AUC on per-prompt P(success). Do not impute `0.5` for gold cells the Scorer omitted (`ps.get(mid, 0.5)`). Skip pairs where `mid not in ps`. File: `src/aiand_router/replay_report.py` + a test that would fail if 0.5 were imputed.

## Do not touch

Stratum sampling, retune, salvage CLI, `gold_is_holdout` constant, short `bin_weights`, `hint_bin` rename, gateway `x-router-reason`, Fowler smells.

TDD. Commit. Append to `.scratch/scorer-pioneer-lift/whole-branch-fix-report.md`.
Run covering tests: `tests/test_train.py`, `tests/test_replay_report.py`.
