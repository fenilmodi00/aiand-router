# Order-mix conservative dry-run preflight

- Pool: `D:/aiand-router/data/pool-hard-mix-order-conservative.jsonl` (sample n=32)
- Reservoir: `D:/aiand-router/data/pool-hard-mix-order-conservative-reservoir.jsonl` (n=95)
- Class fraction gate (~10pp): `true`
- Paid gold justified: `true` (preflight) → **paid seed-16 ran; standalone geometry FAILED**

## Class fractions vs Mix1

| class | observed | target | delta (pp) | within gate |
| --- | --- | --- | --- | --- |
| fail_heavy | 0.3438 | 0.3500 | -0.6 | True |
| kimi_heavy | 0.4375 | 0.4250 | +1.2 | True |
| mixed | 0.2188 | 0.2000 | +1.9 | True |

## Supply

- Quota shortfall: `{"fail_heavy": 0, "kimi_heavy": 0, "mixed": 0}`
- Projected gold USD (n=32): `0.657` (re-confirmed at paid time)
- Within budget cap: `True`

## Paid seed-16 result (closed)

| Field | Value |
| --- | --- |
| Gold | `data/gold-sparse-hard-probe-seed16.jsonl` |
| Spend before | `14.076110` |
| Spend after | `14.482688` |
| Spend Δ | `+0.406578` |
| `geometry_pass` | **false** |
| Spearman | `0.816` |
| y_rate | `0.046875` (below hard band) |
| holdout_like_order | **false** |
| Winner pattern | 6 kimi-only / 26 all-fail / Flash=Qwen=Pro=0 |
| Merge / retune / replay | **not attempted** |

**Do not re-run paid probes from this pool.** Class-quota preflight is insufficient to predict holdout-like order.

## Paid command (historical; do not re-run)

```powershell
$env:PYTHONPATH = "src"
$spend = [double](Get-Content D:/aiand-router/data/spend.txt -Raw).Trim()
$env:BUDGET_LIMIT_USD = ([double](Get-Content D:/aiand-router/data/spend.txt -Raw).Trim() + 15)
$env:AIAND_TRAIN = "1"
$env:TRAIN_CONCURRENCY = "10"
.\scripts\run_hard_y_probe.ps1 -Paid -Seed 16 -Limit 32 `
  -Queries D:/aiand-router/data/pool-hard-mix-order-conservative.jsonl `
  -MinFailToPass 1 -MaxFailToPass 5 -NearMissLo 0.55 -NearMissHi 0.85
```
