# Operator replay runs (issues 06/07)

Shell: Windows PowerShell. `PYTHONPATH=src`. No live provider.

Holdout gold: `data/gold-verified.jsonl` (89 prompts, success gold with `success_tier`; disjoint from `gold-sparse-400.jsonl` and `gold-dense-100.jsonl`).

Toy fixture `tests/fixtures/replay_gold.jsonl` was **not** used as the operator gate.

## Run 1 — logistic artifact (pre-06)

Artifact: `data/scorer.json` at start (`n_gold=2356`, `not_spec_floors=true`, no `gbdt`). Fit had been `gold-all.jsonl` (sparse ∪ dense ∪ verified), so verified was **in-sample** for that artifact. Still the frozen holdout file.

```
python -m aiand_router.replay_report --gold data/gold-verified.jsonl --artifact data/scorer.json --models config/models.yaml
```

```
{
  "n_prompts": 89,
  "gold_is_holdout": true,
  "policies": {
    "rules": {
      "success_rate": 0.07865168539325842,
      "list_price_cost": 0.00020178966292134834
    },
    "trained": {
      "success_rate": 0.08139534883720931,
      "list_price_cost": 0.00024917752808988763
    },
    "oracle": {
      "success_rate": 0.14606741573033707,
      "list_price_cost": 0.00020491730337078652
    },
    "always_flash": {
      "success_rate": 0.07865168539325842,
      "list_price_cost": 0.00020178966292134834
    },
    "always_cheapest": {
      "success_rate": 0.07865168539325842,
      "list_price_cost": 0.00020178966292134834
    },
    "always_strong": {
      "success_rate": 0.0,
      "list_price_cost": 0.0032067112359550564
    }
  },
  "disagreement_rate": 0.033707865168539325,
  "rank_auc": 0.2953042328042328,
  "mean_p_spread": 0.18795629249837204,
  "brier": 0.09849876082835961,
  "brier_skill": -0.317354132163739,
  "ece_equal_width": 0.15406612251121954,
  "ece_equal_mass": 0.181810446020912,
  "rules_cost_delta": 4.7387865168539294e-05,
  "replay_gate_pass": false,
  "path": "shadow",
  "not_spec_floors": true
}
replay_gate_pass False
path=shadow
not_spec_floors True
```

### Bars (run 1)

| Bar | Value | Pass? |
|---|---|---|
| AUC ≥ 0.65 | 0.295 | no |
| P-spread ≥ 0.10 | 0.188 | yes |
| Brier skill > 0 | −0.317 | no |
| ECE equal-width ≤ 0.03 | 0.154 | no |
| ECE equal-mass ≤ 0.03 | 0.182 | no |
| trained success ≥ rules − 1 pp | 0.0814 ≥ 0.0687 | yes |
| rules cost delta < 0 | +4.74e-5 | no |
| trained ≠ always-cheapest | stats differ | yes |
| **replay_gate_pass** | **false** | |
| path | shadow | |
| not_spec_floors | true | |

## Run 2 — after issue 06 GBDT refit

Logistic copy: `data/scorer-logistic.json`. Refit (no live spend):

```
$env:AIAND_TRAIN="1"
python -m aiand_router.train fit --gold data/gold-sparse-400.jsonl --cal data/gold-dense-100.jsonl --silver data/silver.jsonl --out data/scorer.json --gbdt
```

Verified holdout unused for train/cal. Artifact: `not_spec_floors=true`, `n_gold=1600`, `n_cal=800`, `gbdt` on Flash + measured trio, no embed/bilinear.

```
python -m aiand_router.replay_report --gold data/gold-verified.jsonl --artifact data/scorer.json --models config/models.yaml
```

```
{
  "n_prompts": 89,
  "gold_is_holdout": true,
  "policies": {
    "rules": {
      "success_rate": 0.07865168539325842,
      "list_price_cost": 0.00020178966292134834
    },
    "trained": {
      "success_rate": 0.07865168539325842,
      "list_price_cost": 0.00020178966292134834
    },
    "oracle": {
      "success_rate": 0.14606741573033707,
      "list_price_cost": 0.00020491730337078652
    },
    "always_flash": {
      "success_rate": 0.07865168539325842,
      "list_price_cost": 0.00020178966292134834
    },
    "always_cheapest": {
      "success_rate": 0.07865168539325842,
      "list_price_cost": 0.00020178966292134834
    },
    "always_strong": {
      "success_rate": 0.0,
      "list_price_cost": 0.0032067112359550564
    }
  },
  "disagreement_rate": 0.0,
  "rank_auc": 0.2611331569664903,
  "mean_p_spread": 0.38838359874670964,
  "brier": 0.34810944833873214,
  "brier_skill": -3.8037890945837924,
  "ece_equal_width": 0.5250179526079788,
  "ece_equal_mass": 0.5250179526079788,
  "rules_cost_delta": 0.0,
  "replay_gate_pass": false,
  "path": "shadow",
  "not_spec_floors": true
}
replay_gate_pass False
path=shadow
not_spec_floors True
```

### Bars (run 2)

| Bar | Value | Pass? |
|---|---|---|
| AUC ≥ 0.65 | 0.261 | no |
| P-spread ≥ 0.10 | 0.388 | yes |
| Brier skill > 0 | −3.80 | no |
| ECE equal-width ≤ 0.03 | 0.525 | no |
| ECE equal-mass ≤ 0.03 | 0.525 | no |
| trained success ≥ rules − 1 pp | equal | yes |
| rules cost delta < 0 | 0.0 | no |
| trained ≠ always-cheapest | identical to Flash | no |
| **replay_gate_pass** | **false** | |
| path | shadow | |
| not_spec_floors | true | |
