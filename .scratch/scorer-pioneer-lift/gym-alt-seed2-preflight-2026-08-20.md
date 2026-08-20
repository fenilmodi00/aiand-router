# SWE-Gym gym_alt unpaid preflight

- Pool: `data/pool-hard-gym-alt-seed2-n40.jsonl` (n=40)
- Probe limit: n=32 seed `gym-alt-seed2`
- Collision hits vs excluded gold: `0`
- Paid gold justified: `true`
- API key present: `true`

## Trait histogram vs Mix1 (offline)

| metric | gym_alt | Mix1 pool | delta |
| --- | --- | --- | --- |
| F2P mean | 1.475 | 2.400 | -0.925 |
| near-miss mean | 0.720 | 0.733 | -0.012 |
| expected len mean | 52.125 | 46.775 | +5.350 |
| prompt tokens mean | 144.725 | 141.725 | +3.000 |

- n_f2p_2_4: gym_alt `16` vs Mix1 `21`

## Order-mix class + projected winner mix (offline)

- Classes: `{'mixed': 24, 'kimi_heavy': 16}`
- Class frac: `{'mixed': 0.6, 'kimi_heavy': 0.4}`
- Projected kimi-only: `0.4089` (floor 0.2; ok=`True`)
- Projected all-fail: `0.5054` (ceiling 0.7; ok=`True`)
- Winner-mix gate: `True`

## Budget

- Projected gold USD (n=32): `0.6571`
- Spend file: `15.039308`
- Within budget cap (+15.0 USD): `True`

## Trait warnings (non-blocking)

- F2P mean lighter than Mix1 by 0.93 (gym_alt max_f2p=3; winner-pattern risk)

## Geometry predictor

- Offline preflight valid: `False`
- Smith seeds 11–16 and seed-16 order-mix preflight falsified offline trait predictors; gym_alt winner-mix projection is a pool-construction gate only (kimi-only >=20% / all-fail <=70% from Mix1 buckets). Only standalone geometry after paid gold is authoritative.

## Paid command (only if justified + key present)

```powershell
$env:PYTHONPATH = "src"
$spend = [double](Get-Content D:/aiand-router/data/spend.txt -Raw).Trim()
$env:BUDGET_LIMIT_USD = ([double](Get-Content D:/aiand-router/data/spend.txt -Raw).Trim() + 15)
$env:AIAND_TRAIN = "1"
$env:TRAIN_CONCURRENCY = "10"
python -m aiand_router.train gold `
  --queries data/pool-hard-gym-alt-seed2-n40.jsonl `
  --out data/gold-sparse-hard-probe-gym-alt-seed2.jsonl `
  --limit 32
python -m aiand_router.geometry --train data/gold-sparse-hard-probe-gym-alt-seed2.jsonl --eval data/gold-verified.jsonl
```

## Paid result (2026-08-20)

- Gold: `data/gold-sparse-hard-probe-gym-alt-seed2.jsonl` (128 cells)
- Spend: 15.039 → **15.438** (Δ **+$0.399**)
- **Actual winner mix:** 32/32 all-fail (100%) — vs projected ko 0.409 / af 0.505
- Standalone geometry: **`geometry_pass=false`**, y 0.023, Spearman 0.816, `holdout_like_order=false`
- Per-id success: Flash=0, Qwen=0, Pro=0, Kimi=0.094
- **Conclusion:** winner-mix offline projection falsified; do not blind seed3 from order-mix gym_alt pools
