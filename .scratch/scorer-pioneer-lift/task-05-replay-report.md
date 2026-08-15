# Task 05 report: Holdout replay gate

**Status:** DONE_WITH_CONCERNS  
**Commit:** `40a64cd` — Keep shadow and not_spec_floors when holdout replay misses a bar so the Scorer can be judged without live aiand.

Owned: `src/aiand_router/replay_report.py`, `tests/test_replay_report.py`. Did not rewrite pool, gold y, silver/fit, or hop. Did not add GBDT (06). Did not flip `TRAINED_PATH` (07). Artifact flag stays `not_spec_floors`. Code default `BUDGET_LIMIT_USD` stays **15**.

Task 1 already shipped `replay_report` (policies, disagreement, AUC skip-unscored, Brier/ECE, `rules_cost_delta`, `--gold` as holdout). Whole-branch already required trained ≠ always-cheapest and AUC skip-unscored. This ticket filled the **gate** gaps.

## What shipped

1. **Always-cheapest bar:** `replay_gate_pass` compares trained policy stats to `always_cheapest` (min unit-cost eligible), not only `always_flash`. Report still includes always-Flash vs always-strong.
2. **Failing any bar keeps shadow:** `apply_replay_gate` stamps `replay_gate_pass`, `path=shadow`, `not_spec_floors=true`. Passing bars still do not auto-flip path or stamp Verified.
3. **Operator grep:** CLI prints `replay_gate_pass`, `path=shadow`, `not_spec_floors` (plus the JSON report). Cost vs rules remains `rules_cost_delta` (never named savings).
4. **Unit tests:** fixture gold only; `_report()` calls `assert_not_production_floors`; toy fixture may fail the bars without failing the suite (we assert the bool / that it is False on this toy, never that AUC ≥ 0.65).

Numeric bars (AUC ≥ 0.65, P-spread ≥ 0.10, Brier skill > 0, dual ECE ≤ 0.03, trained success ≥ rules − 1 pp, rules cost delta < 0, trained ≠ always-cheapest) live in `replay_gate_pass`. They are operator/replay-gate, not CI floors on the toy fixture.

## TDD

### RED → GREEN 1 — fail keeps shadow + `not_spec_floors`

```
python -m pytest tests/test_replay_report.py::test_failing_any_bar_keeps_shadow_and_not_spec_floors -q --tb=short
```

**RED:** `KeyError: 'replay_gate_pass'` — report had metrics only.  
**GREEN:** `apply_replay_gate` stamps `replay_gate_pass`, `path=shadow`, `not_spec_floors=true`.

### RED → GREEN 2 — trained ≠ always-cheapest-eligible

```
python -m pytest tests/test_replay_report.py::test_replay_gate_fails_when_trained_is_always_cheapest_even_if_not_flash -q --tb=short
```

**RED:** `assert True is False` — gate used `always_flash`; trained=cheapest with dear fallback still passed.  
**GREEN:** policies include `always_cheapest`; gate compares trained to that.

### RED → GREEN 3 — CLI grep lines

```
python -m pytest tests/test_replay_report.py::test_cli_stdout_grepable_shadow_and_not_spec_floors -q --tb=short
```

**RED:** JSON had `"path": "shadow"` but stdout lacked `path=shadow`; CLI did not print `not_spec_floors`.  
**GREEN:** print `path={report['path']}` and `not_spec_floors`; does not set `TRAINED_PATH=trained`.

### Locks (already true after GREEN 1–2; no extra production change)

| Test | What it locks |
|---|---|
| `test_passing_gate_still_keeps_shadow_and_not_spec_floors` | pass still `path=shadow` + `not_spec_floors` (no 07 flip, no Verified stamp) |
| `test_failing_numeric_bar_keeps_shadow_and_not_spec_floors` | each numeric bar miss → gate False + shadow |
| `test_trained_success_below_rules_minus_1pp_fails_gate` | trained success ≥ rules − 1 pp |
| `test_replay_gate_fails_when_trained_is_always_cheapest` | trained = Flash/cheapest still fails |
| `test_rank_auc_skips_unscored_gold_ids` | AUC does not impute 0.5 (whole-branch) |
| `test_replay_gate_pass_is_bool_on_toy_fixture` | toy may fail bars; still shadow |
| `assert_not_production_floors` tests | unit tests reject Verified n≥300 / staffed stamp |

## Tests

- Focused: `tests/test_replay_report.py` → **22 passed**
- Full suite: **169 passed, 7 failed** — pre-existing `test_gateway.py` `x-router-reason` (out of scope)

## Files

- `src/aiand_router/replay_report.py` — `always_cheapest` policy, `apply_replay_gate`, CLI grep lines, gate vs cheapest-eligible
- `tests/test_replay_report.py` — gate outcome, per-bar, CLI, production-floor helper on `_report()`

## Skipped (YAGNI)

GBDT refit (06), `TRAINED_PATH=trained` (07), hash-split mixed gold, Pioneer dashboard, live aiand, sklearn internals, savings %.

## Concerns

1. Full suite not green: 7 pre-existing `test_gateway.py` header failures, outside owned files.
2. Toy fixture fails several bars (AUC 0.5, negative Brier skill, ECE, trained=always-cheapest). That is intended; it does not claim the operator holdout passed.
3. `gold_is_holdout` remains a constant flag; `--gold` help is still the contract that the file is unused for train/cal.
4. `apply_replay_gate` always stamps `path=shadow` even when bars pass. Issue 07 is the manual flip.
