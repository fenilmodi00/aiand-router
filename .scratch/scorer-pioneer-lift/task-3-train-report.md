# Task 3 report: Train gold / teacher / cal-slice fit

**Status:** DONE_WITH_CONCERNS  
**Commit:** `59aa821` — Fit Platt on held-out gold cal slice so P(success) is not an in-sample smoke compress.

## What changed

Owned files only:

- `src/aiand_router/train.py` — held-out gold cal-slice Platt; train-gold intercepts + feature correction; silver regularizer on unobserved cells only; `n_cal` on artifact
- `src/aiand_router/cache.py` — cache key includes `reasoning_effort` (gold/teacher body parity)
- `tests/test_train.py` — cal-slice / silver-unobserved / verified-y seam tests

Did **not** edit `scorer.py`, `replay_report.py`, or flip `TRAINED_PATH`. Did not ingest SWE-smith / Verified / Terminal-Bench. Did not add embed ablation, GBDT zoo, or auto `path=trained`. Code default `BUDGET_LIMIT_USD` remains **15**.

## Fit behavior (Pioneer-shaped)

1. **Gold y order** (unchanged seam, covered by tests): verified (`tests_passed` / expected / pytest) → gateway proxy (tools/JSON/one-word/…) → never nonempty alone when a stronger check exists; `finish_reason=length` + empty content → fail.
2. **Silver** only appended for `(prompt, model_id)` **not** in observed gold. Never used for Platt / gates.
3. **Split:** unique gold prompts → train (front of sorted) + cal (tail, `CAL_FRAC=0.2`, ≥1 when ≥2 prompts). Single-prompt gold → no cal → identity Platt `(a=1,b=0)`.
4. **Train:** per-model intercept from **train-gold** marginals (`logit(rate)`), then logistic feature correction on train-gold + silver-unobserved.
5. **Calibrator:** Platt on **cal-gold zs/ys only** (after train weights).
6. **Bin head:** `bin_weights` from silver `complexity_bin` × `featurize_observable` (no live `hint_bin`).
7. **Catalog:** ids without observed gold get no `weights` / `p_success` / intercept from silver alone. No K3 gold cells (existing sparse/dense guards).
8. **Artifact:** `not_spec_floors: true`.

## Artifact schema emitted (for Task 2 serve)

| Key | Meaning |
|-----|---------|
| `weights` | per-model feature logistic weights (Rec A) |
| `intercepts` | per-model logit intercept from train-gold marginals |
| `platt` | `{a, b}` post-hoc calibrator fit on cal-gold only |
| `bin_weights` | per-bin logistic on request-observable features |
| `p_success` | mean gold success rate per measured id (summary / fallback) |
| `complexity_bin` | mode of silver bins (fallback when no `bin_weights`) |
| `not_spec_floors` | always `true` this cycle |
| `n_gold` / `n_cal` / `n_silver` | row counts (`n_cal` = cal-gold **cells**) |

Serve already understands `weights`, `platt`, and when present `intercepts`, `bin_weights`, `not_spec_floors`. Extra `n_*` keys are informational.

## Tests

- `tests/test_train.py`: **14 passed** (existing seams green + cal-slice / silver-unobserved / verified-y).
- With hop/scorer: `test_train` + `test_trained_hop` + `test_scorer` → **40 passed**.
- Full suite: collection error on sibling `tests/test_replay_report.py` (`replay_report` module WIP); ignoring that file → **98 passed, 7 failed** in `tests/test_gateway.py` (`KeyError: 'x-router-reason'`) — looks like concurrent Task 2 `scorer.py` WIP, not this train commit (owned files only; `scorer.py` left unstaged).

## Skipped (YAGNI)

Offline embed ablation, SWE-smith ingest, GBDT zoo, automatic `path=trained`, Pioneer dashboard, inventing savings %, rewriting train CLI (`--cal` file flag), separate dense-cal path arg (auto holdout from gold prompts instead).

## Concerns

1. Cal slice is a **prompt-tail holdout inside `--gold`**, not a separate dense `--cal` JSONL. Operators who want an explicit dense/cal file must concatenate or rely on sorted prompt tails until a CLI flag is added.
2. Full-repo green is blocked by sibling Task 1/2 WIP (`replay_report`, gateway header failures), not by this commit.
3. Intercepts for models that appear only on cal prompts (no train-gold cells) fall back to rate `0.5` if silver fills xs — rare under sparse/dense recipes that run the same anchors on every prompt.

## Fix round (Critical + Important)

**Status:** DONE  
**Commit:** `1d30631` — Keep budget-skipped gold missing and freeze intercept bias so verified y is not overwritten.

### TDD

| Finding | RED | GREEN |
|---|---|---|
| C1 budget 429 → unobserved | `test_gold_budget_skip_is_unobserved_not_failure`: 4 observed `success=False` cells | 429 / pre-call skip writes `unobserved: true`, no gold y |
| I2 expected before tool_calls | `test_gold_expected_beats_tool_calls_proxy`: proxy `True` | `_gold_label` checks `expected` then `_pytest_verify` before `tool_calls` |
| I2 no query-level `tests_passed` | `test_gold_query_level_tests_passed_is_not_y` + json/one-word: stamped verified fail | query-level `tests_passed` ignored; per-completion pytest still verified |
| I3 freeze `w[0]` | `test_fit_binary_intercept_freezes_bias_column`: `w[0]≈-0.12` | `_fit_binary_intercept` skips dim 0; `w[0]` stays 0 |
| I4 cal-slice pins Platt | strengthened test passed on current code; injected `cal_gold+train_gold` leak → `a` 1.27 ≠ −1.76 | leak reverted; artifact `platt` equals `_fit_platt` on cal-gold zs/ys only |

### Tests

- `tests/test_train.py`: **18 passed**
- Did not chase Minors (`relabel`/`salvage` CLI, GLM `reasoning_effort`, teacher field, TOCTOU). Did not edit `scorer.py`.
