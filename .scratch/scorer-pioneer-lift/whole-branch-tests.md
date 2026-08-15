# Whole-branch test report

Fresh full suite after `8bb2677` (`8bb267756def4afd04f4e1bb5936bfce991f5f7f`).
Command: `python -m pytest tests/ -q --tb=line`
No code edits or commits.

## Counts

| | |
|---|---|
| **Passed** | **123** |
| **Failed** | **7** |
| **Warnings** | 1 (Starlette/httpx TestClient deprecation) |
| **Total** | **130** |
| Runtime | 7.43s |

## Failures (7)

All `KeyError: 'x-router-reason'` in `tests/test_gateway.py` (unowned):

1. `test_gateway.py::test_summarize_phase_forwards_flash_on_pioneer_score`
2. `test_gateway.py::test_learned_router_stays_dark_after_comparison`
3. `test_gateway.py::test_security_review_phase_is_first_class`
4. `test_gateway.py::test_max_regret_picks_stronger_when_cheap_is_far_behind`
5. `test_gateway.py::test_pioneer_score_beats_a_cheaper_weaker_model`
6. `test_gateway.py::test_summarize_picks_highest_pioneer_score`
7. `test_gateway.py::test_draft_phase_planning_is_first_class`

## In-scope vs unowned

### In-scope — 65 passed, 0 failed

| File | Collected | Result |
|---|---|---|
| `tests/test_scorer.py` | 15 | all passed |
| `tests/test_train.py` | 19 | all passed |
| `tests/test_replay_report.py` | 10 | all passed |
| `tests/test_trained_hop.py` | 21 | all passed |
| **Total in-scope** | **65** | **pass** |

### Unowned / out-of-scope

| File | Collected | Passed | Failed |
|---|---|---|---|
| `tests/test_gateway.py` | 46 | 39 | **7** |
| `tests/test_anthropic_messages.py` | | all passed | 0 |
| `tests/test_console.py` | | all passed | 0 |
| `tests/test_session_savings.py` | | all passed | 0 |
| **Unowned total** | **65** | **58** | **7** |

Gateway is the only failing file. In-scope scorer/train/replay/trained-hop suite is green.

## Verdict

In-scope branch work is green (65/65). Suite is red solely due to 7 unowned `test_gateway` header regressions (`x-router-reason`).
