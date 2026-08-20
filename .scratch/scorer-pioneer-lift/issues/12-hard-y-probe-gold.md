# 12 — Hard-y probe live gold (paid)

**What to build:** Small sparse success-gold run on the verified-like pool (issue 09) with issue-02 y (`expected` / schema / `tests_passed` overrides weak proxies; dump `resolved` never y). Kill if Spearman vs frozen verified is still < 0 or y-rate stays dense-easy (~0.39). Pass if Spearman > 0 with holdout-like model order (Kimi > Flash = Qwen > Pro) and overall y closer to ~0.07–0.22 than ~0.39. Cache-first, `AIAND_TRAIN=1`, code default budget 15.

**Blocked by:** 09 — Verified-like train/cal query pool

**Status:** resolved

- [x] Sparse gold on a small verified-like pool (not frozen Verified/Lite/TB)
- [x] Same y as issue 02; dump `resolved` unused
- [ ] Dense/cal, if run, is disjoint and hard (not the current easy ~39% slice)
- [x] Kill: Spearman vs frozen verified < 0, or y-rate stays ~0.39
- [x] Pass: Spearman > 0 and y in ~0.07–0.22
- [x] Live gold is opt-in; unit tests never spend
- [x] Do not scale (issue 13) unless this probe passes

## Comments

Probe ran 2026-08-14. **Do not scale.** Failed pass. `kill_spearman` false; y_rate 0 (not ~0.39). Issue 07 not taken. Frozen `data/gold-verified.jsonl` stayed eval-only. `BUDGET_LIMIT_USD` code default stays 15.

### Operator recipe (paid; cache-first)

Unpaid pool (collision-filter vs the frozen eval dump):

```
python -m aiand_router.train pool --smith <smith-tool.jsonl> --eval data/gold-verified.jsonl --out data/pool-hard.jsonl --n 40 --verified-like
```

Opt-in sparse gold (issue-02 y; not Verified as fit):

```
$env:AIAND_TRAIN="1"
python -m aiand_router.train gold --queries data/pool-hard.jsonl --out data/gold-sparse-hard.jsonl --limit 40
```

Geometry kill/pass (unpaid):

```
python -m aiand_router.geometry --train data/gold-sparse-hard.jsonl --eval data/gold-verified.jsonl
```

Stop if `kill_spearman` is true or `y_rate` stays ~0.39. Only then dense `--gold --dense --exclude` hard cal, logistic `fit` (no `--gbdt`), and a disjoint `--cost-gold` bootstrap where rules ≠ cheapest.

## Answer

**Fail-pass / do not scale.** Spearman **0.0**, `kill_spearman` **false**, train y_rate **0.0** (27 observed / 88; 61 budget-unobserved), all four sparse anchors 0. Frozen eval y_rate 0.070, order Kimi > Flash = Qwen > Pro. Pass missed (rho not > 0; y not in ~0.07–0.22; no holdout order). Easy-y kill (~0.39) did not fire. No dense/fit/`--cost-gold`. No issue 07 / 13.

`--smith` was `datasets/train-queries.jsonl` (no local SWE-smith `tool` dump / HF cache). Pool n=22 `--verified-like`. Inferred `json_schema` from the word `json` in “unused import of json” likely forced schema-fail y. Spend delta ≈ 0.023 (`spend.txt` 2.625). Code default budget 15 unchanged.

Reports: `issue-12-probe-run.md`, `task-12-probe-report.md`.
