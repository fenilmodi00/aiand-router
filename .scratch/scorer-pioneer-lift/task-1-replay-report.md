# Task 1: Offline replay report

Status: **DONE_WITH_CONCERNS**

## What shipped

Offline replay seam: frozen gold JSONL + Scorer artifact + rules picker. Same inputs, no live aiand.

Public API (`src/aiand_router/replay_report.py`):

- `replay_report(gold_path, artifact, models, cfg, holdout_ids=None) -> dict`
- `replay_gate_pass(report) -> bool` (operator gate; toy fixture is allowed to fail it)
- `assert_not_production_floors(gold_path, artifact)` (unit tests must call this)
- CLI: `python -m aiand_router.replay_report --gold … --artifact … [--models config/models.yaml]`

Report fields on the holdout split:

- policies `rules` / `trained` / `oracle` / `always_flash` / `always_strong`: `success_rate`, `list_price_cost`
- `disagreement_rate`, `rank_auc`, `mean_p_spread`
- `brier`, `brier_skill` vs constant base rate
- equal-width ECE (`M=10`) and equal-mass ECE on **selected-hop** calibrated P(success)
- `rules_cost_delta` (trained list-price − rules; never named savings)

Reuse only: `select_model`, `eligible_models`, `estimate_cost`, `load_models`, `load_config`, `load_scorer`, `score_eligible`, `trained_select`. No edits to `scorer.py` / `train.py` / `cache.py` / `app.py`.

## TDD

RED: `tests/test_replay_report.py` collected with `ModuleNotFoundError: aiand_router.replay_report` (pytest exit 2).

GREEN: implemented the module; `7 passed` in 0.32s.

Did not assert AUC ≥ 0.65 (or any replay-gate numeric bar) on the toy fixture. `replay_gate_pass` is only checked to return a `bool`.

## Files committed

`0911e86` Add an offline replay report so shadow can be judged without live aiand.

- `src/aiand_router/replay_report.py`
- `tests/test_replay_report.py`
- `tests/fixtures/replay_gold.jsonl` (4 prompts × 2 models)
- `tests/fixtures/replay_scorer.json` (`not_spec_floors`, tiny `p_success` map)

## Tests

```
python -m pytest tests/test_replay_report.py -q   # 7 passed
python -m pytest tests/test_replay_report.py tests/test_trained_hop.py tests/test_scorer.py -q
# 33 passed
```

Full `tests/`: 105 passed, **7 failed** in `tests/test_gateway.py` (`KeyError: x-router-reason`). Unowned (`app.py` / hop headers). Not introduced by this commit.

Production-floor helper: rejects unique-prompt n≥300 (Verified) and `not_spec_floors: false` / `n_gold≥4000`. Fixture tests call it before `replay_report`.

## Self-review (YAGNI / spec)

Skipped: sklearn, hash-default holdout split, Pioneer UI, live provider, TRAINED_PATH flip, Verified stamp.

`holdout_ids=None` means “every prompt in this gold file” (file is the holdout). CLI does not hash-split `gold-all.jsonl`. Operators should pass a holdout JSONL (or `holdout_ids` in-process).

always-Flash = `cfg["fallback_model"]` if eligible; always-strong = highest-quality eligible. Oracle = cheapest eligible with success gold.

## Concerns

1. Full suite not green: 7 pre-existing `test_gateway.py` header failures, outside owned files.
2. No automatic train/cal holdout split in the CLI; mixed gold files will replay train rows unless the caller filters.

## Fix pass (Important review findings)

Status: **DONE**

Commit `4f65b69` Lock replay fixture arithmetic and mark --gold as holdout so mixed gold cannot contaminate the gate.

Owned files only: `src/aiand_router/replay_report.py`, `tests/test_replay_report.py`.

### TDD

RED: pin tests already green against `0911e86` arithmetic; `test_cli_gold_is_holdout` failed (`holdout` missing from `--gold` help; no `gold_is_holdout` field). `1 failed, 7 passed`.

GREEN: `--gold` help states the file is the holdout, assumed unused for train/cal, no hash split; report includes `gold_is_holdout: True`. `8 passed` in 0.19s.

### Tests pinned from 4×2 fixture literals (not implementation internals)

- oracle success `3/4` (p0/p1/p2 have a gold winner; p3 neither)
- always-Flash vs always-strong success `2/4` each; flash list-price cost < strong
- `rules_cost_delta` is trained−rules list-price (never named savings)
- Brier / Brier skill vs constant base rate of selected-hop labels (flash gold y + artifact `p=0.85`); skill ≠ dummy `0.0`
- disagreement > 0 remains

```
python -m pytest tests/test_replay_report.py -q   # 8 passed
```

Skipped Minors (AUC 0.5 impute, fallback Brier drop, production-floor helper, oracle no-pick cost 0, dead hint_bin, try/return).
