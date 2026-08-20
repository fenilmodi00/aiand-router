# Hard-y gold probe recipe

Critical-path blocker for Pioneer parity: label success on a **verified-like** query pool with **strict y** (expected / schema / pytest), then prove **geometry_pass** before any scale-up or fit on dense-easy gold.

Frozen eval holdout: `data/gold-verified.jsonl` (never fit y).

## Geometry bars (unpaid)

Run after sparse gold:

```
$env:PYTHONPATH = "src"
python -m aiand_router.geometry --train <sparse-gold.jsonl> --eval data/gold-verified.jsonl
```

| Flag | Pass | Kill |
| --- | --- | --- |
| `spearman_train_eval` | > 0 | ≤ 0 → `kill_spearman` |
| `train.y_rate` | 0.07–0.22 (`y_in_hard_band`) | ~0.39 dense-easy → `kill_y_easy`; 0 → `kill_y_empty` |
| `holdout_like_order` | Kimi ≫ Flash ≈ Qwen ≫ Pro | required for `geometry_pass` |
| `geometry_pass` | all three | abort recipe / refit |

`fit` and `retrain --plan-only` refuse when `geometry_pass=false` unless `GEOMETRY_OVERRIDE=1`.

## Merge gate (unpaid)

Concatenate new gold onto Mix1 train or retune **only if**:

1. **Standalone** new gold (`--merge` file alone) vs `data/gold-verified.jsonl` has `geometry_pass=true` (order + y + Spearman).
2. **Combined** base+new vs verified also has `geometry_pass=true`.

Combined-only pass is **insufficient**. Seed-14: standalone `holdout_like_order=false` (y 0.102, Spearman 0.949) but mix1-train merge **would** pass combined-only — merge now **refuses** (`standalone_geometry_pass=false`). Merged refit on that path regressed replay (logistic AUC 0.739, BSS −0.04, `replay_gate_pass=false`); do not serve merged refit.

```
python -m aiand_router.geometry --train data/gold-sparse-hard-mix1-train.jsonl --eval data/gold-verified.jsonl --merge <new-gold.jsonl> --out data/gold-sparse-hard-mix1-train-merged.jsonl
```

Refuses without writing `--out` when standalone or combined fails. Same for retune base `data/gold-sparse-hard-mix1-retune.jsonl`. Seed-11/12/13/14 probes all **refused** (standalone and/or combined). Do not use `data/gold-sparse-hard-mix1-retune-candidate.jsonl`.

## Winning recipe (Mix1 near-miss flashlight)

Validated paid probe (issue 03 / hard-transfer):

| Knob | Value |
| --- | --- |
| Smith | `data/smith-tool-sample.jsonl` (real tool trajectories) |
| Tasks | `data/smith-task-checks.jsonl` (FAIL_TO_PASS + gold-revert expected) |
| Pool | `--verified-like --prompt-family flashlight --seed 11 --verified-like-max-tokens 200 --near-miss-lo 0.55 --near-miss-hi 0.88 --min-expected-len 24` |
| Gold | sparse anchors only (Flash + measured trio); issue-02 y |
| n | 40 prompts → ~160 cells |
| Budget | code default cap **$15** (`BUDGET_LIMIT_USD = spend_before + 15`) |

**Existing pass artifact:** `data/gold-sparse-hard-mix1.jsonl` → Spearman **+0.949**, y_rate **0.181**, `geometry_pass=true`. Mix1 train slice still Spearman **1.0**, y **0.170**, order true.

**Do not copy the seed-11 n400 top-up or seed-12 Mix1-like sample as the next recipe.** Those used the same flashlight/near-miss family but the **n400 stratum draw** (and the F2P-cap sample) did **not** reproduce Mix1 rates. Seed-13 (`mix1like` draw) also failed: y **0.086**, order false, **25/32 all-fail**.

### Winner-pattern diagnosis (Mix1 vs seeds vs verified)

Unpaid: `python scripts/hard_y_probe.py winner-diagnosis`

| Slice | n | y | Flash | Qwen | Kimi | Pro | order | geo | kimi-only | all-four | all-fail | flash+qwen+kimi | qwen−Flash |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Mix1 | 40 | 0.181 | 0.10 | 0.125 | 0.425 | 0.075 | true | pass | 12 | 3 | 23 | 1 | 1 |
| Mix1 train | 28 | 0.170 | 0.107 | 0.107 | 0.393 | 0.071 | true | pass | 8 | 2 | 17 | 1 | 0 |
| Seed-11 top-up | 30 | 0.225 | 0.133 | 0.200 | 0.433 | 0.133 | **false** | fail | 7 | 4 | 17 | 0 | 2 |
| Seed-11 probe | 32 | 0.211 | 0.125 | 0.188 | 0.406 | 0.125 | **false** | fail | 7 | 4 | 19 | 0 | 2 |
| Seed-12 | 32 | 0.023 | 0.031 | 0.000 | 0.031 | 0.031 | **false** | fail | 0 | 0 | 31 | 0 | 0 |
| Seed-13 | 32 | 0.086 | 0.031 | 0.062 | 0.219 | 0.031 | **false** | fail | 5 | 1 | 25 | 0 | 1 |
| Seed-14 | 32 | 0.102 | 0.063 | 0.094 | 0.219 | 0.031 | **false** | fail | 4 | 1 | 25 | 0 | 1 |
| Seed-15 | 32 | 0.250 | 0.094 | 0.188 | 0.531 | 0.188 | **false** | fail | 10 | 2 | 14 | 0 | 4 |
| Seed-16 | 32 | 0.047 | 0.000 | 0.000 | 0.188 | 0.000 | **false** | fail | 6 | 0 | 26 | 0 | 0 |
| Verified (eval) | 89 | 0.070 | 0.079 | 0.079 | 0.124 | 0.000 | true | — | 5 | 0 | 72 | 1 | 5 |

### Seed-11 vs Mix1 (why order died)

Per-id success (sparse cells):

| Slice | Flash | Qwen | Kimi | Pro | y | order |
| --- | --- | --- | --- | --- | --- | --- |
| Mix1 n=40 | 0.10 | 0.125 | 0.425 | 0.075 | 0.181 | true |
| Mix1 train n=28 | 0.107 | 0.107 | 0.393 | 0.071 | 0.170 | true |
| Seed-11 top-up n=32 | 0.125 | 0.188 | 0.406 | 0.125 | 0.211 | **false** (Flash=Pro; Qwen−Flash > 3pp) |
| Seed-12 Mix1-like n=32 | 0.031 | 0.000 | 0.031 | 0.031 | 0.023 | **false** (y below hard band; Spearman 0) |

Prompt traits were almost identical on Mix1 vs seed-11 (flashlight, expected present, near-miss ~0.73, expected length ~47). The gap is **winner pattern**, not missing FAIL_TO_PASS on gold:

- Mix1: **12/40 Kimi-only**, 3 all-four, **1** Qwen-without-Flash, **1** Flash+Qwen+Kimi (Pro miss) — that last cell is what keeps Flash > Pro.
- Seed-11: **7/32 Kimi-only**, **4 all-four**, **2** Qwen-without-Flash, **zero** Flash-without-Pro → Flash≡Pro and Qwen pulls ahead.
- n400 vs Mix1 pool: FAIL_TO_PASS **mean 5.3 / p90 20** vs Mix1 **mean 2.4 / p90 4**. Head-32 of n400 was even heavier (mean 7.4). Gold y is expected-match, not pytest, but heavy suites correlated with the n400 draw that flattened Flash/Pro.

Seed-12 tightened sampling (`max_fail_to_pass=6`, near-miss 0.60–0.84, exclude labeled prompts, seed 12). F2P on the 32-query file looked Mix1-like (mean 1.8, max 5) but y collapsed: **31/32 all-fail**, 3 success cells on one prompt (Flash=Kimi=Pro). Cap+tighter nm overshot hardness.

Seed-13 drew from `mix1like` (F2P 1–6); y **0.086** (below hard band), **5/32 kimi-only** vs Mix1 **12/40**, Flash=Pro **0.031**.

**Stop spend on n400 / seed-12 / seed-13 / seed-14 / seed-15 / seed-16 / blind mix1like / kimi-only-targeted / order-conservative seeds.** Seed-15 and seed-16 both failed standalone geometry (opposite failure shapes). Current **smith** pool definitions are not a justified next-paid source. Do not claim parity.

**gym-alt-seed1 (2026-08-20):** first SWE-Gym `gym_alt` paid probe on `data/pool-hard-gym-alt-n40.jsonl` n=32 → `data/gold-sparse-hard-probe-gym-alt-seed1.jsonl`. Unpaid preflight: `.scratch/scorer-pioneer-lift/gym-alt-preflight-2026-08-20.md` (`scripts/gym_alt_preflight.py`). Standalone geometry **pass**: Spearman **1.0**, y **0.125**, `holdout_like_order=true`. Winner mix: 1 kimi-only / 3 all-four / 27 all-fail. Spend Δ **+$0.557**. Combined merge into mix1-train (n=240) geometry **pass**; refit `scorer-hard-logistic-gym-alt-merged.json` **replay fail** (P-spread 0.084). Diagnosis: `gym-alt-merge-replay-diagnosis-2026-08-20.md`. Do not blind seed2 from legacy n40.

**gym-alt-seed2 unpaid (2026-08-20):** sampling fix — `collect_gym_alt_order_mix_queries` (Mix1 order-mix quotas, `kimi_heavy` 60% / `mixed` 40%, no fail_heavy; no smith mutation required). HF cache expanded to 1200. Pool: `data/pool-hard-gym-alt-seed2-n40.jsonl`. Preflight projected kimi-only **0.409** / all-fail **0.505** (winner-mix gate pass). Report: `gym-alt-seed2-preflight-2026-08-20.md`. Build:

```powershell
$env:PYTHONPATH = "src"
python scripts/hard_y_probe.py gym-alt-pool `
  --gym-tasks data/dump_cache/swe_gym_tasks.jsonl `
  --out data/pool-hard-gym-alt-seed2-n40.jsonl --sample-n 40 --seed 18
python scripts/gym_alt_preflight.py --pool data/pool-hard-gym-alt-seed2-n40.jsonl --seed-name gym-alt-seed2
```

**gym-alt-seed2 paid (2026-08-20):** `data/gold-sparse-hard-probe-gym-alt-seed2.jsonl` n=32. Preflight projected ko 0.409 / af 0.505; **actual 32/32 all-fail**. Standalone geometry **fail**: y 0.023, Spearman 0.816, `holdout_like_order=false`. Spend Δ +$0.399. **Do not blind seed3** from order-mix gym_alt pools — offline winner-mix gate falsified.

### Observable trait gap (offline, 2026-08-20)

Per-prompt F2P / near-miss / expected-length are **nearly identical** between Mix1-passing and failed seed batches (pool-joined). The separating signal is **batch winner-pattern composition**, not missing hard checks:

| Signal | Mix1 (pass) | Seed-15 (fail) | Seed-16 (fail) | Verified holdout |
| --- | --- | --- | --- | --- |
| kimi-only frac | 0.30 | 0.31 | 0.19 | 0.06 |
| all-fail frac | 0.58 | 0.44 | **0.81** | 0.81 |
| qwen-without-flash frac | 0.03 | 0.13 | 0.00 | 0.06 |
| y_rate | 0.181 | 0.250 | **0.047** | 0.070 |
| nm mean (pool-joined) | 0.73 | 0.72 | — | — |
| order-breaking nm mean (Mix1 labeled) | — | — | — | 0.84 vs 0.72 preserving |

Seed-15 matched Kimi-only **rate** but inflated successes (y **0.25**), qwen-without-flash (**4/32**), and Flash≡Pro — mutation-marker filtering alone cannot fix this.

Seed-16 (order-conservative) overshot hardness the other way: **26/32 all-fail**, Flash=Qwen=Pro **0**, y **0.047** below hard band — class-quota preflight pass did not buy holdout-like order.

### Order-mix conservative proxy (new unpaid sampler)

Predicts **holdout-like winner-mix suitability** without labels at pool time:

1. **Offline calibration** from Mix1 gold + `data/pool-hard-mix-near_miss_seed11.jsonl`: bucket = `f2p × near-miss band × mutation` → pattern fractions using **order-preserving prompts only**.
2. **Unlabeled score** `order_mix_likelihood_score`: preserving pattern mass − 2× breaking mass, minus nm **>0.85** easy-win penalty.
3. **Class quotas** from Mix1: `fail_heavy` **35%**, `kimi_heavy` **42.5%**, `mixed` **20%** (not F2P×nm strata alone).
4. **Hard gates:** flashlight, mutation marker (waived for calibrated `kimi_heavy` and `mixed` buckets), nm **0.55–0.85**, expected **24–80**, exclude `f2p4_nm_hi` (Mix1 all-four precursor).

Different from prior pools:

| Pool | What it optimizes | Why insufficient alone |
| --- | --- | --- |
| `pool-hard-mix-winner-stratified.jsonl` | F2P×nm strata vs Mix1 | Seed-14 failed order despite Spearman 0.95 |
| `pool-hard-mix-kimi-only-targeted.jsonl` | Kimi-only mutation envelope | Seed-15 paid fail: right kimi-only rate, wrong qwf/y |
| `pool-hard-mix-mix1like.jsonl` | Broad near-miss dump | Seed-13 y collapsed |
| **`pool-hard-mix-order-conservative.jsonl`** | **Pattern-likelihood + class quotas** | **Seed-16 paid fail:** y below band; 26/32 all-fail; Flash=Pro=Qwen=0 |

Rebuild (unpaid):

```powershell
$env:PYTHONPATH = "src"
python scripts/hard_y_probe.py order-mix-pool `
  --from-pool data/pool-hard-mix-mix1like.jsonl `
  --mix1 data/gold-sparse-hard-mix1.jsonl `
  --mix1-pool data/pool-hard-mix-near_miss_seed11.jsonl `
  --out data/pool-hard-mix-order-conservative.jsonl `
  --sample-n 32
python scripts/order_mix_preflight.py --write-pool
```

**Dry-run preflight (unpaid, 2026-08-20, pass after mixed waiver fix):**

```powershell
$env:PYTHONPATH = "src"
python scripts/order_mix_preflight.py --write-pool
```

| Metric | Before mixed waiver | After mixed waiver |
| --- | --- | --- |
| Reservoir (`pool-hard-mix-order-conservative-reservoir.jsonl`) | n=**51** | n=**95** |
| Dry-run sample (`pool-hard-mix-order-conservative.jsonl`) | n=**27** / 32 | n=**32** / 32 |
| `fail_heavy` | **40.7%** vs **35%** (+5.7 pp, pass) | **34.4%** vs **35%** (−0.6 pp, pass) |
| `kimi_heavy` | **51.9%** vs **42.5%** (+9.3 pp, pass) | **43.8%** vs **42.5%** (+1.2 pp, pass) |
| `mixed` | **7.4%** vs **20%** (−12.6 pp, **fail**) | **21.9%** vs **20%** (+1.9 pp, pass) |
| Class fraction gate (~10 pp) | **false** | **true** |
| Mix1 retroactive score_delta | **+1.10** (pass) | **+1.10** (pass) |
| Paid gold justified (preflight gate) | **no** | **yes** → seed-16 paid; **geometry_pass=false** |

**Mixed supply diagnosis:** 69 unblocked `mixed`-class rows existed in `pool-hard-mix-mix1like.jsonl`, but **67/67 rejections** were `no_mutation_marker`. The mutation waiver previously covered only `kimi_heavy`; extending it to calibrated `mixed` buckets (see `ORDER_MIX_MUTATION_WAIVER_CLASSES` in `pool.py`) restores supply without relaxing nm/F2P/flashlight gates.

Sampler fixes in this pass: largest-remainder quotas, quota-capped backfill (no kimi overshoot), mutation-marker waiver for calibrated `kimi_heavy` **and `mixed`** buckets, separate reservoir vs `--sample-n 32` draw. Full report: `.scratch/scorer-pioneer-lift/order-mix-preflight-2026-08-20.md`.

**Seed-16 paid result (closed):** preflight re-confirmed `paid_gold_justified=true` (class fractions within ~10 pp; projected ~$0.66). Paid n=32 → `data/gold-sparse-hard-probe-seed16.jsonl`. Standalone vs verified: `geometry_pass=false`, Spearman **0.816**, y **0.047** (below hard band), `holdout_like_order=false`. **No merge / retune / replay.** Do not re-spend on this pool.


### Dry-run (no credits)

```powershell
$env:PYTHONPATH = "src"
.\scripts\run_hard_y_probe.ps1
```

Default `-Queries` is `data/pool-hard-mix-winner-stratified.jsonl` (winner-mix proxy strata). `data/pool-hard-mix-kimi-only-targeted.jsonl` is now a **failed paid recipe**, not the preferred next source. Dry-run samples n=`-Limit` with F2P **2–4**, Mix1 nm **0.55–0.88**, prints cost preflight, exits before gold.

Rebuild the winner-stratified dump pool (unpaid, no gold):

```powershell
python scripts/hard_y_probe.py winner-stratified-pool `
  --smith data/smith-tool.jsonl `
  --tasks data/smith-task-checks.jsonl `
  --eval data/gold-verified.jsonl `
  --mix1-pool data/pool-hard-mix-near_miss_seed11.jsonl `
  --out data/pool-hard-mix-winner-stratified.jsonl
```

### Kimi-only-targeted pool (failed paid recipe; keep for analysis only)

Mix1 has **12/40 Kimi-only** wins — the pattern that preserves Flash≫Pro and holdout order. Unpaid trait envelope from labeled Mix1 Kimi-only cells + smith-tool mutation markers (`func_pm_remove_assign`, `func_pm_remove_cond`, `func_pm_class_rm`, …):

| Trait | Mix1 Kimi-only n=12 | Kimi-only pool n=47 |
| --- | --- | --- |
| F2P mean / p90 | 2.58 / 4 | **1.87 / 4** |
| near-miss mean | 0.73 | **0.71** |
| expected len mean | 44.5 | **43.8** |
| prompt tokens mean | 142 | **153** |
| Mix1 prompt overlap | — | **0** |

Rebuild (unpaid, ~80s on full `smith-tool.jsonl`):

```powershell
python scripts/hard_y_probe.py kimi-only-pool `
  --smith data/smith-tool.jsonl `
  --tasks data/smith-task-checks.jsonl `
  --eval data/gold-verified.jsonl `
  --out data/pool-hard-mix-kimi-only-targeted.jsonl
```

Dry-run histogram vs Mix1 Kimi-only subset prints in JSON (`mix1_kimi_n`, `mix1_kimi_mutation_markers`, `mutation_markers`). Keep this pool for offline diagnosis only until a materially different sampling rule is justified.

Winner-pattern table only:

```powershell
python scripts/hard_y_probe.py winner-diagnosis --eval data/gold-verified.jsonl
```

Legacy mix1like dump (F2P 1–6, **not** the next paid source):

```powershell
python scripts/hard_y_probe.py mix1like-pool --smith data/smith-tool.jsonl --tasks data/smith-task-checks.jsonl --eval data/gold-verified.jsonl --out data/pool-hard-mix-mix1like.jsonl
```

Manual smith rebuild (small n, not the dump-wide mix1like file):

```powershell
python -m aiand_router.train pool --smith data/smith-tool-sample.jsonl --tasks data/smith-task-checks.jsonl --eval data/gold-verified.jsonl --out data/pool-hard-mix-near_miss_seed11.jsonl --n 40 --verified-like --prompt-family flashlight --seed 11 --verified-like-max-tokens 200 --near-miss-lo 0.55 --near-miss-hi 0.88 --min-expected-len 24 --max-fail-to-pass 6

python scripts/hard_y_probe.py project --queries data/pool-hard-mix-mix1like.jsonl --limit 32
```

### Seed-15 result (paid, now closed)

Seed-15 was the paid check on `data/pool-hard-mix-kimi-only-targeted.jsonl` with `-Limit 32`, `-MinFailToPass 1`, `-MaxFailToPass 4`.

| File | spend_after | geometry_pass | Spearman | y_rate | holdout_like_order | merge | retune | replay |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `data/gold-sparse-hard-probe-seed15.jsonl` | **14.076110** | **false** | **0.5** | **0.25** | **false** | no | no | no |

Winner-pattern failure at **high** y (qwen-without-flash inflated; Flash≡Pro). Disproves kimi-only-targeted as next paid.

### Seed-16 result (paid, now closed)

Seed-16 was the paid check on `data/pool-hard-mix-order-conservative.jsonl` with `-Limit 32`, `-MinFailToPass 1`, `-MaxFailToPass 5`, nm **0.55–0.85**. Unpaid preflight passed; spend before **14.076110**, `BUDGET_LIMIT_USD=29.07611`.

| File | spend_after | Δ | geometry_pass | Spearman | y_rate | holdout_like_order | merge | retune | replay |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `data/gold-sparse-hard-probe-seed16.jsonl` | **14.482688** | **+$0.407** | **false** | **0.816** | **0.047** | **false** | no | no | no |

Failure shape: **too hard** — 26/32 all-fail, Flash=Qwen=Pro=0, 6/32 kimi-only only; y below hard band. Disproves order-mix conservative even after class-fraction preflight pass.

Operational rule from here:

1. **Do not run further blind paid probes** from order-conservative, kimi-only-targeted, winner-stratified, or mix1like.
2. **Do not merge or retune from seed-15 or seed-16.**
3. **Do not do replay comparisons** off those merges.
4. **Require new unpaid proxy analysis** that explains both failure modes (seed-15 too easy/wrong winners; seed-16 too hard/all-fail) before any more spend.
5. Do not scale dense/fit on dense-easy `gold_sparse.jsonl`. Do not set `TRAINED_PATH=trained`.

### Mix1 replay: logistic is the serve candidate

Frozen eval: `data/gold-verified.jsonl`. Do **not** retune on `data/tune.jsonl` (dense-easy; 0.83 thresholds). Keep Pioneer ship defaults in `config/models.yaml`.

| Artifact | AUC | BSS | ECE_w | spread | policy | replay_gate_pass |
| --- | --- | --- | --- | --- | --- | --- |
| `data/scorer-hard-logistic.json` | 0.754 | >0 | 0.007 | 0.102 | not always-Flash | **true** (Pioneer cost semantics; still `not_spec_floors`, n=89) |
| Merged refit (seed-14 train merge, **do not serve**) | 0.739 | <0 | — | — | — | **false** |
| `data/scorer-hard-bilinear.json` (unpaid Mix1 gold + dense-hard-cal, **no silver**; identity proj + frozen intercepts + inverted-Platt guard) | 0.713 | <0 | 0.120 | 0.207 | not always-Flash | false |
| `data/scorer-hard-bilinear-distill48-gymalt.json` (2026-08-20 unpaid: hash teacher distill on Mix1-train∪gym-alt) | 0.747 | **+0.058** | 0.076 | 0.076 | rcd&lt;0, succ 0.124 | **false** (spread+ECE) |
| `data/scorer-hard-bilinear-probe.json` (pre-fix; silver + 32-d collapse + inverted Platt `a<0`) | 0.635 | <0 | 0.035 | 0.066 | always-Flash | false |
| `data/scorer-hard-logistic-mix1.json` (silver-regularized refit) | 0.532 | 0 | 0.205 | 0.223 | success 0.0 | false — do not serve |

Bilinear lost to logistic on Mix1 replay **after** the fit/score bugs were fixed. Remaining gap is **capacity vs label**, not underflow: Mix1 n=160 cannot identify a useful query×model residual beyond per-model logistic; unmatched dense cal (664 rows, not verified-like) miscalibrates BSS/ECE. **Serve candidate is logistic.** Do not serve bilinear.

Cost gate (Pioneer): savings vs `most_expensive_eligible`. `rules_cost_delta` is reported (and sliced where rules ≠ cheapest) and is **not** named savings. Logistic can spend more than rules on quality-first hops and still pass the cost bar.

This is **not** Pioneer parity and **not** a `TRAINED_PATH=trained` promotion (`apply_replay_gate` stays `path=shadow`).

### Post-probe refit (after geometry_pass)

Prefer **logistic** (`-Logistic`). Bilinear remains experimental.

```powershell
$env:PYTHONPATH = "src"
$env:AIAND_TRAIN = "1"   # fit is local; no live completions
.\scripts\run_hard_y_refit.ps1 -Logistic -SkipRetune `
  -TrainGold data/gold-sparse-hard-mix1.jsonl `
  -CalGold data/gold-dense-hard-cal-merged.jsonl `
  -Out data/scorer-hard-logistic.json
```

Silver regularizer on Mix1 collapsed holdout transfer (see `data/scorer-hard-logistic-mix1.json`). Fit without `--silver` for the current serve artifact.

Chain:

```
hard-y gold → geometry_pass → fit logistic --geometry-train/eval → ship-default thresholds (no easy-tune retune) → replay gate
```

Experimental bilinear:

```powershell
python -m aiand_router.train fit --bilinear `
  --gold data/gold-sparse-hard-mix1.jsonl `
  --cal data/gold-dense-hard-cal-merged.jsonl `
  --silver data/silver.jsonl `
  --out data/scorer-hard-bilinear.json `
  --geometry-train data/gold-sparse-hard-mix1.jsonl `
  --geometry-eval data/gold-verified.jsonl
```

## Geometry sweep (existing files vs verified)

```powershell
python scripts/hard_y_probe.py geometry-sweep --eval data/gold-verified.jsonl `
  data/gold-sparse-hard-mix1.jsonl data/gold-sparse-hard.jsonl data/gold_sparse.jsonl
```

## Kill conditions (abort recipe)

1. `kill_spearman` — inverted model ranking vs frozen verified
2. `kill_y_easy` — y_rate closer to ~0.39 than hard band (current `gold_sparse.jsonl` / `gold_sparse.jsonl` fit path)
3. `kill_y_empty` — all failures / no observed successes
4. `holdout_like_order=false` — even with positive Spearman, do not treat as pass

## Synthetic fixture (CI)

`tests/fixtures/hard_y_probe/` — verified-like short prompts with holdout-like order. Proves geometry + `fit --bilinear --geometry-train/eval` end-to-end without spend.

## `--verified-like` empty mix (fixed)

`--prompt-family` default is `flashlight`. Copied `expected` / `json_schema` / `tests` on dump prompts are family `other`, so a strict family match made `--verified-like` refuse with `hard-check mix is empty`. Pool now keeps those dump-copied checks under default flashlight (does **not** invent schema). Mix1 still needs `--prompt-family flashlight` plus `--near-miss-lo/hi` (near-miss ratio is `None` without the flashlight mark, so family-other rows stay out of Mix1).

`scripts/run_hard_y_probe.ps1` defaults `-Queries` to `data/pool-hard-mix-winner-stratified.jsonl` and samples with F2P **2–4**, Mix1 near-miss **0.55–0.88**, excluding Mix1 + seed-11/12/13 gold. Empty `-Queries` still rebuilds from `data/smith-tool-sample.jsonl`. Do not label the n400 file in order.

## Winner-mix stratified query pool (unpaid, no gold)

Local dumps: `data/smith-tool.jsonl` (~4GB tool trajs), `data/smith-tool-sample.jsonl`, `data/smith-task-checks.jsonl`. Mix1 calibration pool: `data/pool-hard-mix-near_miss_seed11.jsonl` (n=40, the queries that produced passing Mix1 gold).

`data/pool-hard-mix-winner-stratified.jsonl` — **n=152** unlabeled queries from `smith-tool` + task join, filtered to flashlight + nm **0.55–0.88** + F2P **2–4** + expected **24–80**, then **proxy-stratified** to match Mix1's f2p×near-miss histogram (no label cheating at pool time). Collision-filtered vs frozen eval + all labeled Mix1/seed gold.

| Metric | Mix1 pool n=40 | Winner-strat n=152 |
| --- | --- | --- |
| F2P mean / p90 | 2.4 / 4 | **2.76 / 4** |
| near-miss mean | 0.73 | **0.72** |
| expected len mean | 47 | **52** |
| prompt tokens mean | 142 | **152** |
| Mix1 prompt overlap | — | **0** |

Proxy-stratum fractions (pool vs Mix1 calibration): `f2p4_nm_hi` **0.059 vs 0.333** (dump under-supplies this Mix1-heavy bin — expect to oversample it on the first 32-query paid draw), `f2p2_nm_mid` **0.191 vs 0.238**, `f2p3_nm_mid` **0.151 vs 0.0** (dump-only stratum). Rebuild: `python scripts/hard_y_probe.py winner-stratified-pool …`.

Legacy `data/pool-hard-mix-mix1like.jsonl` — n=399, F2P **1–6**; **not** the next paid source (seed-13 killed y).

Older `data/pool-hard-mix-near_miss-n400.jsonl` is a 400-draw **without** F2P cap (mean F2P **5.3**) and is **not** the next paid source.

`train retune` still needs **≥300 labeled gold rows** that **pass geometry**. Current paths (unpaid sweep vs `data/gold-verified.jsonl`):

| Source | n (cells) | y | order | geometry_pass | Notes |
| --- | --- | --- | --- | --- | --- |
| `mix1-retune.jsonl` | 172 | 0.163 | false | **false** | stuck |
| `mix2.jsonl` | 160 | 0.138 | false | **false** | alone insufficient |
| retune + mix2 | 196 | 0.153 | false | **false** | 34/40 prompt overlap |
| retune + seed-14 | 300 | 0.137 | false | **false** | hits n but order fail |
| retune + mix1 | 284 | 0.166 | true | **true** | overlap mix1; not fresh |
| mix1 (full) | 160 | 0.181 | true | **true** | below n=300 |

**No unpaid path reaches ≥300 rows with `geometry_pass=true` without bad seed probes or mix1 overlap.** Do not retune on `tune.jsonl`.

### Paid top-ups (stop n400)

| Batch | File | y | Spearman | order | merge | spend Δ |
| --- | --- | --- | --- | --- | --- | --- |
| Seed-11 n400 | `gold-sparse-hard-probe-seed11.jsonl` / `mix1-topup32.jsonl` | 0.211 | 0.83 | false (Flash=Pro 0.125) | refused | prior |
| Seed-12 Mix1-like | `gold-sparse-hard-probe-seed12.jsonl` | 0.023 | 0.0 | false | refused | **+$0.44** (ledger 12.43 → 12.87) |
| Seed-13 mix1like | `gold-sparse-hard-probe-seed13.jsonl` | 0.086 | 0.83 | false (Flash=Pro) | refused | prior |
| Seed-14 winner-strat | `gold-sparse-hard-probe-seed14.jsonl` | 0.102 | 0.95 | false (standalone) | **refused** (strict merge) | prior |
| Seed-15 kimi-only-targeted | `gold-sparse-hard-probe-seed15.jsonl` | 0.250 | 0.50 | false (standalone) | **refused** (no merge attempted) | spend_after **14.076110** |
| Seed-16 order-conservative | `gold-sparse-hard-probe-seed16.jsonl` | 0.047 | 0.82 | false (standalone) | **refused** (no merge attempted) | Δ **+$0.407** → **14.482688** |

**Do not run another blind seed batch.** Seed-15 and seed-16 disproved kimi-only-targeted and order-conservative as next-paid moves. No further paid probes until sampling logic changes materially and offline proxy analysis supports a new design.

Rebuild winner-stratified (unpaid):

```powershell
python scripts/hard_y_probe.py winner-stratified-pool --smith data/smith-tool.jsonl --tasks data/smith-task-checks.jsonl --out data/pool-hard-mix-winner-stratified.jsonl
python scripts/hard_y_probe.py sample --queries data/pool-hard-mix-winner-stratified.jsonl --out data/pool-hard-mix-near_miss_seed14.jsonl --limit 32 --seed 14 --min-fail-to-pass 2 --max-fail-to-pass 4 --exclude data/gold-sparse-hard-mix1.jsonl
python -m aiand_router.geometry --train data/gold-sparse-hard-mix1-retune.jsonl --eval data/gold-verified.jsonl --merge data/gold-sparse-hard-probe-seed14.jsonl --out data/gold-sparse-hard-mix1-retune-merged.jsonl
```

For a 300-cell fresh retune slice use `-Limit 75` **only after** a future 32-query batch passes geometry under a materially changed sampler. Do not rebuild from n400.

## Remaining Pioneer blockers (not parity)

- **n≪ Verified floor** — Mix1 logistic gate is on n=89 selected-cal 72; equal-mass ECE 0.143 is waived (`n < 150`), not a staffed Verified (n≥300 / sparse 4000) pass
- **Bilinear** ranking recovered after identity-proj / frozen-intercept / inverted-Platt fix (AUC 0.713, not always-Flash) but still loses logistic (0.754, BSS>0, ECE_w 0.007). Experimental only; do not serve
- **Silver regularizer** on Mix1 logistic collapsed transfer; unmatched cal (`gold-dense-hard-cal-merged`) still not verified-like
- **Retune n=172** — no concat path (mix2, seed-14, retune+mix2) reaches ≥300 with `geometry_pass`. retune+mix1 (284) passes but overlaps mix1
- **Seed-14 strict merge** — standalone fail blocked merge; merged refit regressed replay vs `scorer-hard-logistic.json`
- **Blind seed draws ≠ Mix1 winner pattern** — F2P-heavy n400 flattens Flash/Pro; winner-stratified / mix1like overshoot all-fail; kimi-only-targeted failed on seed-15 (high y, wrong order); order-conservative failed on seed-16 (low y, all-fail). New unpaid proxy work is required before any more spend
- **Train–serve length skew** on legacy sparse gold (long prompts; stumps dead on verified tokens)
- **K3** silver-only until dense gold onboarding
- **Operator flip** (`TRAINED_PATH=trained`) still blocked: bounded + Verified gates, not this shadow replay bit
- **Session gold / SWE-bench Verified n=500** still unpaid/unrun — proxy y ≠ session resolve
