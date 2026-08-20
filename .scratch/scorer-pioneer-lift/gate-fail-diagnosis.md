# Gate-fail diagnosis (issue 06 lift → still red; 07 not taken)

**Status:** NEEDS_CONTEXT — operator `replay_gate_pass` cannot become true on `data/gold-verified.jsonl` with current train/cal labels and catalog, without forbidden verified leak or a gate-definition change. Issue **07 not taken**.

## Phase 1 — Feedback loop

```
$env:PYTHONPATH="src"
python -m aiand_router.replay_report --gold data/gold-verified.jsonl --artifact data/scorer.json --models config/models.yaml
```

Ran twice; identical. Red-capable (`replay_gate_pass` false), deterministic, ~7s, agent-runnable. Holdout/artifact/models present (not toy fixture).

**Red output (GBDT artifact, excerpt):**

```
rank_auc 0.261
mean_p_spread 0.388
brier_skill -3.804
ece_equal_width 0.525
ece_equal_mass 0.525
rules_cost_delta 0.0
disagreement_rate 0.0
replay_gate_pass False
path=shadow
not_spec_floors True
```

Matches operator symptom (post–issue-06 GBDT lift).

## Phase 2 — Reproduce + minimise

- Symptom match: trained ≡ always-Flash ≡ always-cheapest; AUC≪0.5; Brier/ECE catastrophic; cost_delta 0.
- Minimised: first **3** verified prompts still fail with the same mode (disagree=0, cost_d=0, p_spread≈0.39, auc≪0.5). Script: `_minimise_repro.py`.

Load-bearing: GBDT+Platt artifact + verified holdout + catalog where Flash is cheapest and clears all holdout phase bars.

## Phase 3–4 — Hypotheses (see `gate-fail-hypotheses.md`)

| ID | Hypothesis | Result |
|---|---|---|
| H1 | Dense-cal (~39% y) vs verified (~7% y) → overconfident selected P | **Confirmed.** Selected mean_P≈0.604 vs mean_y≈0.079. Shifting Platt `b`→−2.1 matches level (ECE≈0.003) but skill≈0 (no discrimination). |
| H2 | Threshold admits all → always-cheapest | **Confirmed.** Flash P never &lt; 0.60; survivors at θ∈{0.1…0.6} on all 89 prompts. |
| H3 | `rules_cost_delta &lt; 0` impossible on this holdout | **Confirmed.** Rules pick = Flash on 89/89; Flash is global cheapest; no cheaper catalog id. Trained cannot be strictly cheaper than rules. |
| H4 | `hint_bin` vs predicted-bin skew drives AUC | **Falsified.** AUC identical 0.261 with hint or predicted bin (bin agree only 37/89). |
| H5 | GBDT/silver invert ranking vs verified | **Confirmed (geometry).** Sparse vs verified model-rate Spearman **−0.6**. Mean_P ranks Pro≫Qwen≈Flash≫Kimi; holdout y ranks Kimi≫Flash=Qwen≫Pro(0). |

### Extra finding (GBDT serve collapse)

On verified holdout, **per-model P has std=0 / unique=1**. All 24×4 stumps split on `log1p(tokens)` with thresholds ≳4.8 (tokens≳120). Verified tokens are 13–62 (`log1p`≤4.14) → **every stump takes the left leaf** → intercept-only scores, then Platt from easy dense cal pushes P≈0.47–0.65.

Sparse train: 333/400 prompts have `log1p(tokens)>4.8`. Holdout: **0/89**. Train–serve length skew.

Logistic artifact (`data/scorer-logistic.json`) still fails but is less broken: AUC 0.295, Brier skill −0.317, some P variance (std≈0.01).

## Root cause

Two **hard blockers** (either alone fails the gate):

1. **AUC ceiling without verified leak.** Constant model rates from sparse → AUC≈0.40; from dense →≈0.47; inverted sparse →≈0.60. All **&lt; 0.65**. Only leaking verified marginals reaches ≈0.68 (forbidden as fit gold). Query-conditional GBDT cannot invent a transfer signal when train model ordering is anti-correlated with holdout.
2. **Cost bar unreachable.** `rules_cost_delta &lt; 0` requires trained list-price &lt; rules. On this holdout rules ≡ cheapest eligible (Flash). No scorer change fixes that.

Secondary (explains why the GBDT lift **worsened** Brier/ECE): length-only stumps dead on short verified prompts + Platt fit on easy dense-cal.

## Fix attempt / regression

No honest code change clears the operator gate without (a) training on verified, (b) changing gate bars, or (c) changing holdout/rules so rules sometimes picks non-Flash.

- Did **not** fake a pass.
- Did **not** train on Verified/Lite/Terminal-Bench.
- Did **not** open Rec B / live embed / second zoo.
- Did **not** take issue 07.
- `apply_replay_gate` still never auto-flips (`path=shadow`).

Optional later (out of this ticket’s pass criterion): diversify GBDT stumps beyond `log1p(tokens)`; calibrate on harder cal; restore logistic artifact for shadow until labels transfer. None of these clear AUC≥0.65 **and** cost_delta&lt;0 on current holdout.

## Operator replay after diagnosis

Unchanged fail on current `data/scorer.json` (GBDT). Logistic copy also fails (see `operator-replay-run.md` run 1).

## Issue 07

**Not taken** — `replay_gate_pass` remains false.

## What would unblock

NEEDS_CONTEXT from operator / larger gold spend:

- Holdout (still eval-only, unused for fit) where rules sometimes picks non-cheapest **and** train gold whose model ranking correlates with that holdout; **or**
- Explicit bar change (e.g. cost_delta ≤ 0 when rules≡cheapest; AUC floor acknowledging n); **or**
- Larger success-gold n with verified-like difficulty **in train/cal** (not the frozen eval holdout as fit y) so AUC can transfer.

## Commits

Diagnosis artifacts under `.scratch/scorer-pioneer-lift/` (this file, updated hypotheses, progress). No production flip.
