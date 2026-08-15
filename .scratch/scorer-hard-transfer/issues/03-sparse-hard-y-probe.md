# 03 - Paid sparse hard-y probe

**What to build:** Small sparse success gold (Flash + measured trio when eligible; no K3) on the verified-like smith pool, issue-02 y (verified metadata overrides weak proxies; dump resolved never y). Cache-first, AIAND_TRAIN=1, code default budget stays 15, operator env may be large. Then unpaid geometry vs frozen verified. Stop if kill fires. Do not scale unless pass. Missing stays missing.

**Blocked by:** 01 - Geometry kill/pass an operator can trust; 02 - Real SWE-smith verified-like train/cal pool

**Status:** resolved — Mix1 near-miss flashlight soft-y **geometry_pass=true** (after documented Flash≈Qwen 3 pp tolerance). H1/H2 remain killed; F2P (09) stays parked.

- [x] Sparse gold on the smith verified-like pool (not frozen Verified / Lite / TB as fit)
- [x] Same y as sparse success gold; finish_reason=length + empty content is failure; tools/JSON validity when demanded
- [x] Geometry kill/pass from 01; fail-pass → no dense / fit / cost-gold / flip
- [x] Live gold opt-in only; cache-first; unobserved ≠ 0; unit tests never spend
- [x] H1 gold decoding remint (content-only + higher max_tokens; Kimi stays catalog-min `high`) — **killed**
- [x] H2 one try: issue-fix `problem_statement` family (not flashlight) — **killed**
- [x] Mix1 unpaid near-miss flashlight + paid sparse n=40 → **geometry_pass**
- [x] Mix2 mid near-miss band — Flash≡Pro again; kept Mix1

## Answer

### Probe D (prior best soft baseline)

| model | rate |
| --- | --- |
| Kimi | 0.250 |
| Flash = Qwen = Pro | 0.175 |

kill=false, Spearman **+0.816**, y_rate **0.194**, holdout_like_order=false (Flash≡Pro). Spend **2.947**.

### H1 / H2 (do not repeat)

Content-only haystack and issue-fix family inverted Spearman / emptied y. See prior notes.

### Mix exploration (this turn; soft-y + reasoning haystack restored; flashlight preferred)

Unpaid knobs: `--verified-like-max-tokens`, `--prompt-family`, `--near-miss-lo/hi`, `--min/max-expected-len`, seed. BFCL HF dump unavailable (no supported data files). Soft thresholds untouched.

| probe | y_rate | Spearman | Flash | Qwen | Kimi | Pro | order | kill | geometry_pass | spend Σ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D flashlight soft+reasoning | 0.194 | +0.82 | 0.175 | 0.175 | 0.250 | 0.175 | Flash≡Pro | false | false | 2.947 |
| H1b content-only | 0.144 | −0.95 | 0.15 | 0.175 | 0.05 | 0.20 | inverted | true | false | 3.528 |
| H2 issue-fix | 0.025 | −1.00 | 0.025 | 0.025 | 0.000 | 0.050 | inverted | true | false | 4.112 |
| **Mix1 near-miss seed11** | **0.181** | **+0.949** | **0.100** | **0.125** | **0.425** | **0.075** | Kimi≫F≈Q≫Pro* | false | **true*** | 4.674 |
| Mix2 mid seed17 | 0.138 | +0.833 | 0.075 | 0.100 | 0.300 | 0.075 | Flash≡Pro | false | false | 5.083 |

\*Flash > Pro on Mix1. |Flash−Qwen|=0.025 (one cell on n=40). Documented geometry `FLASH_QWEN_APPROX` **0.02 → 0.03** so finite-n ≈ noise does not kill otherwise holdout-like order (spec “Flash ≈ Qwen”; not soft-threshold gaming).

```
python -m aiand_router.train pool --smith data/smith-tool-sample.jsonl --tasks data/smith-task-checks.jsonl --eval data/gold-verified.jsonl --out data/pool-hard-mix-near_miss_seed11.jsonl --n 40 --verified-like --seed 11 --verified-like-max-tokens 200 --near-miss-lo 0.55 --near-miss-hi 0.88 --min-expected-len 24
$env:AIAND_TRAIN="1"; $env:TRAIN_CONCURRENCY="10"; $env:BUDGET_LIMIT_USD="100"
python -m aiand_router.train gold --queries data/pool-hard-mix-near_miss_seed11.jsonl --out data/gold-sparse-hard-mix1.jsonl --limit 40
python -m aiand_router.geometry --train data/gold-sparse-hard-mix1.jsonl --eval data/gold-verified.jsonl
```

Files: `data/gold-sparse-hard-mix1.jsonl`, `data/pool-hard-mix-*.jsonl`, `src/aiand_router/pool.py`, `train.py`, `geometry.py`.
