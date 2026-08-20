# rules_cost_delta diagnosis — scorer-hard-logistic (2026-08-20)

Unpaid eval-only on `data/gold-verified.jsonl`. Serve candidate **not** mutated.

## Baseline (ship medium 0.10 / 0.20)

| Metric | Value |
| --- | --- |
| `replay_gate_pass` | `true` |
| `rules_cost_delta` | `+0.000687` |
| `rules_cost_delta_where_rules_ne_cheapest` | `+0.000167` |
| `savings_vs_most_expensive` | `0.000899` |
| `rank_auc` | `0.7542` |
| `brier_skill` | `0.000631` |
| `mean_p_spread` | `0.1022` |
| `ece_equal_width` | `0.00688` |
| `disagreement_rate` | `1.0` |
| trained success / cost | `0.1124` / `0.002307` |
| rules success / cost | `0.0225` / `0.001620` |

## Where trained is more expensive

- **Systemic, not a few outliers.** n=89; trained_more_expensive=72; trained_cheaper=17; same-cost=0.
- Positive mass `+0.0918` vs negative `-0.0307` → mean `+0.000687`.
- Top-20 hops only ~55% of positive mass; top-5 ~14% — not a long-tail of a few bad prompts.
- Trained pick rules: `threshold`×72 (all Kimi), `fallback_declined`×17 (Flash).

### Pair counts (rules → trained)

| rules | trained | n | mean delta | sum delta |
| --- | --- | ---: | ---: | ---: |
| `deepseek-v4-pro` | `kimi-k2.7-code` | 53 | `+0.000799` | `+0.042342` |
| `deepseek-v4-flash` | `kimi-k2.7-code` | 19 | `+0.002603` | `+0.049454` |
| `deepseek-v4-pro` | `deepseek-v4-flash` | 17 | `-0.001804` | `-0.030665` |

Flash→Kimi (19 hops) is the largest per-hop overspend; Pro→Kimi (53 hops) is the largest total mass.

### Selected model mix (ship)

| model | rules n | trained n |
| --- | ---: | ---: |
| `deepseek-v4-flash` | 19 | 17 |
| `deepseek-v4-pro` | 70 | 0 |
| `kimi-k2.7-code` | 0 | 72 |

### Quality on cost-regression hops

n_pos=72; trained_success=10; rules_success=2; both=0; neither=60; trained_only=10.
Proxy quality gain from Kimi is real but sparse; most expensive upgrades fail for both policies.

## Unpaid threshold / max_regret sweep

Override only `trained_effort.medium` on the frozen artifact (no retune on verified).

- Grid 108 cells; `gate_pass`=45; **gate_pass ∧ rcd≤0 = 9** (all at `threshold=0.15`, any `max_regret` in {0.03…0.30} — identical policy).
- Fine sweep: transition is sharp around Kimi conf≈0.14–0.15. `t=0.14` still rcd>0 and BSS fails; `t=0.15` clears cost and keeps gate.
- Mechanism: raise bar so Kimi below 0.15 declines → Flash fallback. Mix 72 Kimi/17 Flash → **25 Kimi / 64 Flash**.

### Official CLI verification (overlay)

```text
python -m aiand_router.replay_report --gold data/gold-verified.jsonl \
  --artifact data/scorer-hard-logistic-cost-overlay.json \
  --models config/models.cost-overlay-t015.yaml
```

| Metric | ship serve | cost overlay t=0.15 |
| --- | ---: | ---: |
| `replay_gate_pass` | true | true |
| `rules_cost_delta` | **+0.000687** | **-0.000688** |
| `rules_cost_delta_where_rules_ne_cheapest` | +0.000167 | **-0.001023** |
| `savings_vs_most_expensive` | 0.000899 | 0.002274 |
| `rank_auc` | 0.7542 | 0.7542 |
| `brier_skill` | 0.000631 | 0.000599 |
| `ece_equal_width` | 0.00688 | 0.00188 |
| trained success | 0.1124 | 0.0899 |
| `n_selected` | 72 | 25 |
| `parity_blockers` includes `rules_cost_delta_not_negative` | **yes** | **no** |

AUC unchanged; BSS still >0 with negligible absolute drop. Proxy success drops ~2.2pp but stays ≫ rules (0.0225) and above always_flash (0.0787).

## Shadow experiment artifacts (do not promote)

| Path | Role |
| --- | --- |
| `config/models.cost-overlay-t015.yaml` | medium threshold 0.15 (only intentional diff) |
| `data/scorer-hard-logistic-cost-overlay.json` | same weights; `serve_candidate=false`; overlay metadata |
| `data/scorer-hard-logistic-cost-overlay-meta.json` | fine-sweep numbers |
| `.scratch/scorer-pioneer-lift/diagnose_rules_cost_delta.py` | reproducible diagnosis |

## Verdict

- **Cost gap is systemic Kimi overspend** vs rules (Pro/Flash), not a few prompts.
- **Safe unpaid knob fix exists:** medium `threshold=0.15` (keep `max_regret=0.20`).
- **Serve candidate unchanged:** keep `data/scorer-hard-logistic.json` + ship `models.yaml` as quality-primary shadow serve (higher proxy success).
- **Cost-primary shadow experiment:** use the overlay pair above; it clears `rules_cost_delta` on verified replay while keeping `local_replay_gate_pass`.
- Still **not** parity: `not_spec_floors`, n=89≪300, ECE_mass waived, no session-gold promotion, no `TRAINED_PATH=trained`.
