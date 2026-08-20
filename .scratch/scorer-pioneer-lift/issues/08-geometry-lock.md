# 08 — Geometry lock (no spend)

**What to build:** An unpaid CLI that prints train vs cal vs frozen eval gold geometry: per-id success rates, Spearman(train rates, eval rates), token/`log1p` histograms, and y base rates. Kill the current sparse/dense recipe if Spearman vs frozen verified is still < 0. Recommend the logistic artifact for shadow until Spearman > 0. Do not train on the eval dump. Do not flip `TRAINED_PATH`. Do not spend.

**Blocked by:** None — can start immediately.

**Status:** resolved

- [x] Unpaid CLI prints per-id success rates for train, cal, and eval gold
- [x] CLI prints Spearman(train model rates, eval model rates)
- [x] CLI prints token / `log1p` histograms and y base rates
- [x] Kill flag when Spearman(train, eval) < 0
- [x] Recommends logistic for shadow while Spearman < 0 (no GBDT serve)
- [x] Eval gold is not used as fit y
- [x] No live aiand; no `AIAND_TRAIN` required
- [x] `TRAINED_PATH` stays shadow; artifact stays `not_spec_floors`

## Answer

Unpaid `python -m aiand_router.geometry --train … --cal … --eval …` prints per-id rates, Spearman, token/`log1p` fracs, y-rates, `kill_spearman`, and `recommended_artifact`. `--eval` is eval-only (`eval_is_fit_gold=false`). Spearman < 0 → `prefer_logistic` and `data/scorer-logistic.json`. No spend, no `TRAINED_PATH` flip.

Files: `src/aiand_router/geometry.py`, `tests/test_geometry.py`.
