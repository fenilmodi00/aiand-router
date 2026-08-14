# 11 — Prefer logistic until ranking transfers

**What to build:** Stop serving the length-stump GBDT as the shadow judgment artifact while train↔verified Spearman < 0. Logistic stays the fit default. Document the operator recipe (`--artifact data/scorer-logistic.json` / fit without `--gbdt`). Optional CLI note when the loaded artifact has `gbdt`. Do not add another GBDT-on-length zoo. Do not flip `TRAINED_PATH`. Do not overwrite bars to fake a pass.

**Blocked by:** 08 — Geometry lock (recommendation is the lock’s output).

**Status:** resolved

- [x] Fit without `--gbdt` remains the default; `--gbdt` help warns about short-prompt collapse
- [x] Replay prints a prefer-logistic note when the artifact contains `gbdt`
- [x] Operator recipe documented (logistic copy until Spearman > 0)
- [x] No second model zoo; Rec B / live embed stay closed
- [x] `TRAINED_PATH` not flipped; `not_spec_floors` unchanged
- [x] Code default `BUDGET_LIMIT_USD` stays 15

## Answer

Fit default is still logistic. `--gbdt` help says length stumps collapse on short prompts; prefer logistic until Spearman(train, eval) > 0. Replay prints `prefer_logistic=true use --artifact data/scorer-logistic.json until train-eval spearman > 0` when the artifact has `gbdt`. Geometry lock recommends the same path. Does not overwrite `data/scorer.json` or flip `TRAINED_PATH`.

### Operator recipe (no spend)

```
python -m aiand_router.geometry --train data/gold-sparse-400.jsonl --cal data/gold-dense-100.jsonl --eval data/gold-verified.jsonl
python -m aiand_router.replay_report --gold data/gold-verified.jsonl --artifact data/scorer-logistic.json --models config/models.yaml
```

Fit (when new hard gold exists; still opt-in, still no `--gbdt` until Spearman > 0):

```
python -m aiand_router.train fit --gold <sparse-hard> --cal <dense-hard> --out data/scorer.json
```

Files: `src/aiand_router/replay_report.py`, `src/aiand_router/train.py`, `src/aiand_router/geometry.py`, `tests/test_replay_report.py`, `tests/test_train.py`.
