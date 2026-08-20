# gym-alt merged refit replay failure — diagnosis (2026-08-20)

**Serve candidate unchanged:** `data/scorer-hard-logistic.json` (`replay_gate_pass=true`).

## What was tested

| Step | Artifact | Result |
| --- | --- | --- |
| Standalone geometry | `data/gold-sparse-hard-probe-gym-alt-seed1.jsonl` | **pass** (Spearman 1.0, y 0.125, order true) |
| Combined merge gate | `data/gold-sparse-hard-mix1-train-gym-alt-merged.jsonl` (n=240) | **pass** (Spearman 1.0, y 0.146, order true) |
| Refit + replay | `data/scorer-hard-logistic-gym-alt-merged.json` | **replay_gate_fail** |
| Counterfactual merge | `data/gold-sparse-hard-mix1-full-gym-alt-merged.jsonl` (n=288) | geometry pass |
| Counterfactual refit | `data/scorer-hard-logistic-mix1full-gym-alt-merged.json` | **replay_gate_fail** (different failure mode) |

## Replay gate breakdown — serve vs merged (mix1-train base)

| Gate | Serve (`scorer-hard-logistic.json`) | Merged refit | Notes |
| --- | --- | --- | --- |
| `rank_auc >= 0.65` | **0.754** pass | **0.750** pass | Slight drop, still ok |
| `mean_p_spread >= 0.10` | **0.102** pass | **0.084** **FAIL** | **Sole local gate failure** |
| `brier_skill > 0` | 0.0006 pass | **0.042** pass | Merged actually better |
| `ece_equal_width <= 0.03` | 0.007 pass | 0.030 pass | Merged barely passes |
| `trained >= rules - 1pp` | 11.2% vs 2.2% pass | same 11.2% pass | Routing quality preserved |
| `savings_vs_most_expensive > 0` | pass | pass | Merged slightly better |
| `not always_cheap w/o quality` | pass | pass | No flash collapse on this path |

**Verdict:** geometry pass does **not** imply replay pass. The merged refit fails on **P-spread only**, not AUC, ECE, always-flash, or quality-vs-rules.

## Root cause — P-spread collapse

1. **gym-alt winner mix is holdout-like but tie-heavy:** seed1 is 27/32 all-fail (84.4%) vs mix1-train 17/28 (60.7%). Merged train is 44/60 all-fail (73.3%) with kimi-only dropping 28.6% → 15.0%.

2. **Cheap-model discrimination collapsed in weights:** merged artifact gives flash/qwen/pro identical pooled P(success) ≈ **0.070** (serve: flash 0.057, qwen 0.065, pro 0.065). Flash and qwen weight vectors and intercepts are numerically identical after refit.

3. **Kimi separation shrinks:** Kimi P(success) drops **0.228 → 0.189**, narrowing max−min spread on verified replay prompts.

4. **Train-base confound:** serve candidate was fit on **full Mix1** (n_gold=160, 40 prompts). Merged refit used **mix1-train subset** (112 cells, 28 prompts) + gym-alt (128). The smaller Mix1 slice has less cross-model diversity before gym-alt dilution.

## Counterfactual — full Mix1 + gym-alt refit

Refit on `gold-sparse-hard-mix1-full-gym-alt-merged.jsonl` (288 cells) trades one failure for another:

| Gate | Full Mix1 + gym-alt refit |
| --- | --- |
| `mean_p_spread >= 0.10` | **0.114 pass** |
| `brier_skill > 0` | **−0.061 FAIL** |
| `ece_equal_width <= 0.03` | **0.065 FAIL** |
| trained success | **7.9% = always_flash** (down from 11.2%) |
| `rules_cost_delta` | **−0.0014** (cheaper than rules, but miscalibrated) |

Adding gym-alt to the full Mix1 base restores spread but **over-regularizes toward Flash** and breaks calibration. Neither merge base beats the serve candidate.

## Implications

- **Do not promote** `scorer-hard-logistic-gym-alt-merged.json` — strictly worse on the binding spread gate despite better BSS.
- **Do not run blind gym-alt seed2 paid probe** until merge/refit strategy is fixed (pool needs more kimi-only / mixed winners, not more all-fail mass).
- **Geometry is necessary but insufficient** — combined Spearman 1.0 can coexist with replay spread failure.
- **Accumulate scale before refit** — n=32 gym-alt top-up is too small to refit without collapsing cheap-model logits; target n≥300 combined before another refit attempt.

## Suggested operator next step (unpaid default)

1. Keep `data/scorer-hard-logistic.json` as serve candidate.
2. **Done unpaid (2026-08-20):** rebuild gym_alt with kimi-heavy/mixed order-mix quotas → `data/pool-hard-gym-alt-seed2-n40.jsonl`; preflight winner-mix gate pass (ko 0.409 / af 0.505). See `gym-alt-seed2-preflight-2026-08-20.md`.
3. **Paid seed2** only with operator approval (command in unpaid-next-path / seed2 preflight). Offline gate ≠ geometry.
4. Defer refit until combined geometry-passing gold ≥ 300 cells **and** offline spread proxy on serve artifact + new labels looks non-degenerate.
