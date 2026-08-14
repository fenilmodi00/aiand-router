# Task 08+ report — Option A machinery (no paid gold)

**Status:** code-complete for unpaid slices 08–11. Issue 12 NEEDS_CONTEXT (live gold). Issue 07 not taken. `TRAINED_PATH` still shadow. Artifact still `not_spec_floors`. `BUDGET_LIMIT_USD` default 15.

**Date:** 2026-08-14  
**Path:** Option A from `next-path-decision.md` (verified-like train/cal gold + dual shadow eval).

## TDD evidence

Seams: unpaid geometry CLI JSON; `train pool` JSONL; `replay_report` CLI JSON; fit `--gbdt` help. No live aiand. FakeProvider / tmp JSONL only.

| Slice | Red | Green |
|---|---|---|
| 08 geometry | `ModuleNotFoundError: aiand_router.geometry` | `tests/test_geometry.py` 2 passed |
| 09 `--verified-like` | argparse `unrecognized arguments: --verified-like` | `test_pool_short_hard_*` 2 passed |
| 10 dual eval | `KeyError: rules_ne_cheapest_rate`; unrecognized `--cost-gold` | `test_dual_eval_*` + `rules_ne_cheapest_rate` 2 passed |
| 11 logistic | replay stdout missing `prefer_logistic`; fit help missing logistic/short | `test_replay_gbdt_artifact_prints_prefer_logistic` + `test_fit_gbdt_help_*` 2 passed |

Full suite: **181 passed**, **7 failed** (`test_gateway.py` `x-router-reason`, out of scope).

## What shipped

1. **Geometry lock** — `python -m aiand_router.geometry --train <sparse> --cal <dense> --eval <verified>`. Per-id rates, Spearman, `log1p` fracs, y-rates, `kill_spearman`, `prefer_logistic`, `eval_is_fit_gold=false`. Unpaid.
2. **Verified-like pool** — `train pool --verified-like`: tokens ≤ 62 + `expected`/`json_schema`/`pytest` (copied or inferred). Collision-filter vs `--eval`. Empty mix refused. Not Verified/Lite/TB as fit. Dump `resolved` unused.
3. **Dual eval** — `replay_report --gold <eval> --cost-gold <bootstrap>`. `rules_ne_cheapest_rate` on both. Gate still from `--gold`. Fixture: debug bar → rules≡cheapest (H3); summarize → rules≠cheapest and `cost_slice.rules_cost_delta < 0`. No bar rewrite.
4. **Logistic preference** — fit default unchanged; `--gbdt` help warns length-stump collapse; replay prints `prefer_logistic=true use --artifact data/scorer-logistic.json until train-eval spearman > 0` when artifact has `gbdt`. Does not overwrite `data/scorer.json`.

## Files

- `src/aiand_router/geometry.py` (new)
- `src/aiand_router/pool.py`, `train.py`, `replay_report.py`
- `tests/test_geometry.py`, `test_pool.py`, `test_replay_report.py`, `test_train.py`
- `.scratch/scorer-pioneer-lift/issues/08-geometry-lock.md` … `12-hard-y-probe-gold.md`
- `progress.md`

## What remains (paid)

Issue **12** — operator must run `AIAND_TRAIN=1` gold on the verified-like pool, then geometry. **Kill** if Spearman vs frozen verified still < 0 or y-rate ~0.39. **Do not invent gold cells.** Scale + logistic refit and a live `--cost-gold` JSONL wait on a passing probe. Issue 07 stays not taken.

## Constraints held

Verified/Lite/TB eval-only; dump `resolved` not y; silver not Platt y; shadow default; `not_spec_floors`; budget default 15; no Rec B / live embed / GBDT zoo; no fake `replay_gate_pass`.
