# SWE-Gym gym_alt unpaid preflight

- Pool: `D:/aiand-router/data/pool-hard-gym-alt-n40.jsonl` (n=40)
- Probe limit: n=32 seed `gym-alt-seed1`
- Collision hits vs excluded gold: `0`
- Paid gold justified: `true`
- API key present: `true`

## Trait histogram vs Mix1 (offline)

| metric | gym_alt | Mix1 pool | delta |
| --- | --- | --- | --- |
| F2P mean | 1.275 | 2.400 | -1.125 |
| near-miss mean | 0.702 | 0.733 | -0.031 |
| expected len mean | 58.175 | 46.775 | +11.400 |
| prompt tokens mean | 228.200 | 141.725 | +86.475 |

- n_f2p_2_4: gym_alt `8` vs Mix1 `21`

## Budget

- Projected gold USD (n=32): `0.659`
- Spend file: `14.482688`
- Within budget cap (+15.0 USD): `True`

## Trait warnings (non-blocking)

- F2P mean lighter than Mix1 by 1.12 (gym_alt max_f2p=3; winner-pattern risk)
- prompt_tokens mean +86 vs Mix1 (higher list-price / behavior risk)

## Geometry predictor

- Offline preflight valid: `False`
- Smith seeds 11–16 and seed-16 order-mix preflight falsified offline trait predictors; gym_alt is a fresh task family (fix patches, lighter F2P). Only standalone geometry after paid gold is authoritative.

## Paid command (only if justified + key present)

```powershell
$env:PYTHONPATH = "src"
$spend = [double](Get-Content D:/aiand-router/data/spend.txt -Raw).Trim()
$env:BUDGET_LIMIT_USD = ([double](Get-Content D:/aiand-router/data/spend.txt -Raw).Trim() + 15)
$env:AIAND_TRAIN = "1"
$env:TRAIN_CONCURRENCY = "10"
python -m aiand_router.train gold `
  --queries D:/aiand-router/data/pool-hard-gym-alt-n40.jsonl `
  --out data/gold-sparse-hard-probe-gym-alt-seed1.jsonl `
  --limit 32
python -m aiand_router.geometry --train data/gold-sparse-hard-probe-gym-alt-seed1.jsonl --eval data/gold-verified.jsonl
```

## gym-alt-seed1 paid result (closed)

| Field | Value |
| --- | --- |
| Gold | `data/gold-sparse-hard-probe-gym-alt-seed1.jsonl` |
| Spend before (preflight) | `14.482688` |
| Spend after | `15.039308` |
| Spend Δ | `+0.556620` |
| `geometry_pass` | **true** |
| Spearman | `1.0` |
| y_rate | `0.125` (in hard band) |
| holdout_like_order | **true** |
| Winner pattern | 1 kimi-only / 3 all-four / 27 all-fail / 0 qwen-without-flash |
| Merge / retune / replay | **not attempted this turn** |

Standalone geometry **passed** on the first gym_alt probe. This does **not** authorize blind scale-up: run strict **combined** merge gate vs Mix1 train base before any fit/retune. Serve candidate remains `data/scorer-hard-logistic.json` (shadow). Do not flip `TRAINED_PATH`. Do not claim parity.
