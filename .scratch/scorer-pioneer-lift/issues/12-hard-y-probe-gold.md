# 12 — Hard-y probe live gold (paid)

**What to build:** Small sparse success-gold run on the verified-like pool (issue 09) with issue-02 y (`expected` / schema / `tests_passed` overrides weak proxies; dump `resolved` never y). Kill if Spearman vs frozen verified is still < 0 or y-rate stays dense-easy (~0.39). Pass if Spearman > 0 with holdout-like model order (Kimi > Flash = Qwen > Pro) and overall y closer to ~0.07–0.22 than ~0.39. Cache-first, `AIAND_TRAIN=1`, code default budget 15.

**Blocked by:** 09 — Verified-like train/cal query pool

**Status:** needs-info

- [ ] Sparse gold on a small verified-like pool (not frozen Verified/Lite/TB)
- [ ] Same y as issue 02; dump `resolved` unused
- [ ] Dense/cal, if run, is disjoint and hard (not the current easy ~39% slice)
- [ ] Kill: Spearman vs frozen verified < 0, or y-rate stays ~0.39
- [ ] Pass: Spearman > 0 and y in ~0.07–0.22
- [x] Live gold is opt-in; unit tests never spend
- [ ] Do not scale (issue 13) unless this probe passes

## Comments

NEEDS_CONTEXT — paid cells. Machinery (issues 08–11) is in. Do not invent gold cells. Do not take issue 07. Frozen `data/gold-verified.jsonl` stays eval-only. `BUDGET_LIMIT_USD` code default stays 15.

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
