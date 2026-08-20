# Whole-branch must-fix report

**Status:** DONE  
**Commit:** `8bb2677` — Send GLM min reasoning_effort and fail always-Flash replay so the gate and rank AUC match spec.  
**Owned files:** `src/aiand_router/train.py`, `src/aiand_router/replay_report.py`, `tests/test_train.py`, `tests/test_replay_report.py`

Did not touch: stratum sampling, retune, salvage CLI, `gold_is_holdout`, short `bin_weights`, `hint_bin`, gateway `x-router-reason`, Fowler smells.

## TDD

| Finding | RED | GREEN |
|---|---|---|
| GLM teacher `reasoning_effort` | `test_teacher_call_sends_min_reasoning_effort_for_glm`: `KeyError: 'reasoning_effort'` | `_teacher_call` applies `MIN_REASONING_EFFORT` (GLM `"none"`); Motif still `"low"` |
| Gate vs always-cheapest | `test_replay_gate_fails_when_trained_is_always_cheapest`: `assert True is False` (rules≠trained still passed) | `replay_gate_pass` requires `trained != always_flash`; `disagreement_rate` still reported |
| Rank AUC skip unscored | `test_rank_auc_skips_unscored_gold_ids`: `assert 0.5 == 1.0` (imputed 0.5) | skip `mid not in ps`; omitted gold cell does not pull AUC to chance |

### RED output

```
FAILED tests/test_train.py::test_teacher_call_sends_min_reasoning_effort_for_glm
E       KeyError: 'reasoning_effort'

FAILED tests/test_replay_report.py::test_replay_gate_fails_when_trained_is_always_cheapest
E       AssertionError: assert True is False

FAILED tests/test_replay_report.py::test_rank_auc_skips_unscored_gold_ids
E       assert 0.5 == 1.0
```

### GREEN output

```
python -m pytest tests/test_train.py tests/test_replay_report.py -q
.............................                                            [100%]
29 passed, 1 warning in 2.21s
```

(Starlette/`httpx` deprecation warning only; not from this diff.)

## What changed

1. **`_teacher_call`** — `MIN_REASONING_EFFORT.get(model_id)` for Motif and GLM escalate/salvage (same map `_gold_body` already used).
2. **`replay_gate_pass`** — fail when trained policy stats equal `always_flash` (always-cheapest-eligible). `disagreement_rate` remains rules≠trained on the report.
3. **Rank AUC** — `if mid not in ps: continue` instead of `ps.get(mid, 0.5)`.
