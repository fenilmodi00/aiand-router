# Task 2 fix: reject wrong-length weights

Review: `.scratch/scorer-pioneer-lift/task-2-review.md`
Important finding only. Do not chase Minors.

## Finding

`_dot` truncates to `min(len(w), len(x))` in `src/aiand_router/scorer.py`. After featurize expanded to 17 dims, a transitional artifact with short `weights` still takes the weights branch and misaligns family coeffs onto token-bin slots instead of falling back to `p_success`.

## Fix (ponytail)

In `score_eligible`, before `_dot`: if `len(w) != len(x)`, do not use those weights. Fall back to that id's `p_success` table entry if present; otherwise omit the id (same as missing weights). Do not invent P(success).

TDD at `score_eligible` public seam: a short `weights` vector plus a known `p_success` must yield the table P, not a truncated-dot P.

Owned files only: `src/aiand_router/scorer.py`, `tests/test_scorer.py`.

Run `tests/test_scorer.py` and `tests/test_trained_hop.py`. Commit. Append results to `.scratch/scorer-pioneer-lift/task-2-scorer-report.md`.
