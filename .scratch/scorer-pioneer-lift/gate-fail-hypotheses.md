# Gate-fail hypotheses (issue 06 lift still red)

Phase 1 loop (red, deterministic, ~7s):

```
$env:PYTHONPATH="src"
python -m aiand_router.replay_report --gold data/gold-verified.jsonl --artifact data/scorer.json --models config/models.yaml
```

Observed: `replay_gate_pass=false`, AUC 0.261, P-spread 0.388, Brier skill −3.80, ECE 0.525/0.525, cost_delta 0, trained ≡ always-cheapest (Flash), path=shadow.

Minimised: first 3 verified prompts still fail with same mode (disagree=0, cost_d=0, auc≪0.5, p_spread≈0.39).

## Ranked hypotheses

### H1 — Dense-cal vs verified holdout base-rate mismatch (most likely for Brier/ECE)

Dense cal overall success ≈ 0.39 (Flash 0.69, Qwen 0.70); verified holdout ≈ 0.07 (Flash 0.079, Pro 0.0, Kimi 0.124). GBDT+Platt fit on easy cal → selected-hop P≈0.60 on Flash while y≈0.08 → ECE≈0.5, Brier skill ≪ 0.

**Prediction:** If we recalibrate (or temperature-scale) so selected P matches a hard base rate closer to sparse/holdout-like ~0.08–0.22 without training on verified, Brier skill rises and ECE falls. If we only swap tree depth and keep the same cal labels, Brier/ECE stay terrible.

### H2 — Always-cheapest collapse (threshold admits everyone)

Medium θ=0.10; measured trio all score ≫ θ (Flash≈0.60, Pro≈0.65); cheapest-above-bar = Flash every row. Rules also always Flash → cost_delta=0 and trained == always-cheapest bar fails.

**Prediction:** Raising effective θ (or shrinking overconfident P) until some rows drop Flash below θ (or max_regret excludes cheap) will create disagreement and ≠ always-cheapest. Cost_delta < 0 still needs rules ≠ cheapest somewhere (see H5).

### H3 — Structural impossibility of `rules_cost_delta < 0` on this holdout

On all 89 verified prompts, rules pick = Flash = cheapest eligible. Flash is the global cheapest catalog model and clears every phase bar present in the holdout. Trained cannot be strictly cheaper than rules.

**Prediction:** No artifact change alone yields `rules_cost_delta < 0` on `data/gold-verified.jsonl`. Only a holdout where rules sometimes picks non-Flash, or a gate-definition change, can clear that bar.

### H4 — Feature / bin train–serve skew (`hint_bin` vs predicted bin)

Fit may condition on JSONL `hint_bin`; serve predicts bin from observables. Skew inverts ranking → AUC ≪ 0.5.

**Prediction:** Replaying with forced train `hint_bin` as the serve bin feature lifts AUC toward ≥0.5 (or higher). If AUC stays ~0.26, skew is not the driver.

### H5 — GBDT overfit / silver leakage into z (ranking inverted)

GBDT trees + silver regularizer invent ranking opposite of verified gold (Pro highest P, but Pro y=0 on holdout; Kimi lowest among trio but best holdout y).

**Prediction:** Dropping silver from fit and/or using logistic-only on sparse gold improves holdout AUC vs current GBDT. If AUC stays inverted, the gold label geometry (sparse/dense vs verified) is the cause, not silver/GBDT mechanics alone.

---

## Falsification results (Phase 4)

- **H1 confirmed:** selected mean_P≈0.604 vs mean_y≈0.079; Platt `b` shift to −2.1 → ECE≈0.003, Brier skill≈0 (level fix only).
- **H2 confirmed:** Flash never below θ=0.60; always-cheapest on all 89.
- **H3 confirmed:** `rules_not_cheapest=0/89`; no catalog id cheaper than Flash → `rules_cost_delta < 0` unreachable.
- **H4 falsified:** AUC 0.261 with predicted bin **or** hint_bin.
- **H5 confirmed (geometry):** sparse↔verified Spearman −0.6; GBDT P unique=1 on holdout (all stumps on `log1p(tokens)` with thr≳4.8; verified tokens≤62). Logistic still AUC 0.295. AUC ceilings without verified leak: sparse-rates 0.40, dense-rates 0.47, inverted-sparse 0.60 — all &lt; 0.65.

**Winning account:** Holdout/train label anti-correlation + structural cost bar (H3+H5), amplified by GBDT length-stump / easy-cal collapse (H1+H2). Gate cannot pass honestly on this holdout.
