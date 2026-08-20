# Offline-distilled bilinear / IRT head — unpaid advance (2026-08-20)

**Option:** A (winning-strategy Scorer v2)  
**Serve candidate unchanged:** `data/scorer-hard-logistic.json` + `config/models.yaml`  
**No** `TRAINED_PATH=trained`. **No** paid pools.

## What changed (code)

| Seam | Change |
| --- | --- |
| `scorer.hash_text_latent` | Deterministic signed hashing-trick bag (tokens + char trigrams); features-only, not a neural embed |
| `featurize_bilinear(..., hash_dim=)` | Optional hash trunk for live or teacher features |
| `train --bilinear-hash-dim N` | Live hash capacity on bilinear hop |
| `train --bilinear-distill-hash-dim N` | Offline teacher on hash trunk → ridge map base features → teacher query latent; **serve `hash_dim=0`** |
| Tests | `tests/test_bilinear_scorer.py` (+3); 10 passed |

## Experiments vs serve (frozen `data/gold-verified.jsonl`, ship knobs)

| Artifact | gate | AUC | BSS | ECE_w | P-spread | rcd | trained succ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **`scorer-hard-logistic.json` (serve)** | **true** | **0.754** | **+0.00063** | **0.007** | **0.102** | +0.000687 | 0.112 |
| `scorer-hard-bilinear.json` (prior) | false | 0.713 | −0.121 | 0.120 | 0.207 | +0.000687 | 0.112 |
| `scorer-hard-bilinear-matched-cal.json` (Mix1 internal cal, no dense) | false | 0.677 | −1.639 | 0.388 | 0.389 | +0.000687 | — |
| `scorer-hard-bilinear-hash32.json` (live hash + dense-hard-cal) | false | 0.732 | −0.168 | 0.146 | 0.229 | +0.000687 | 0.112 |
| `scorer-hard-bilinear-distill48.json` (distill Mix1 + dense-hard-cal) | false | 0.721 | −0.105 | 0.112 | 0.202 | +0.000687 | 0.112 |
| **`scorer-hard-bilinear-distill48-gymalt.json`** (distill Mix1-train∪gym-alt-seed1 + dense-hard-cal) | **false** | **0.747** | **+0.058** | **0.076** | **0.076** | **−0.000278** | **0.124** |

## Honest read

1. **Matched Mix1-only cal failed.** Dense-hard-cal fails geometry (Spearman 0.333) but still calibrates better than n_cal=32 Mix1 holdout (Platt overfits → BSS collapse).
2. **Live hash did not beat prior bilinear** on gate bars (AUC up vs old bilinear, BSS still negative).
3. **Best unpaid bilinear:** offline distill on **geometry-passing** `gold-sparse-hard-mix1-train-gym-alt-merged.jsonl`:
   - Beats serve on **BSS**, **proxy success**, and **`rules_cost_delta` (clears ≤0)**
   - Loses gate on **P-spread 0.076 &lt; 0.10** and **ECE_w 0.076 &gt; 0.03** (same failure family as logistic gym-alt merge refit)
4. **Factor-scale / p-blend sweeps** did not jointly recover spread≥0.10 and ECE_w≤0.03 while dominating serve. Pure logistic remains the only `replay_gate_pass=true` artifact.

## Follow-up (same day): gate recovery via latent dim

See `.scratch/scorer-pioneer-lift/distill-gate-recovery-2026-08-20.md`.

- Lowering `--bilinear-distill-latent-dim` to **14–18** yields `replay_gate_pass=true` (best: **ld18**).
- Gate-pass distill beats serve on AUC/BSS/spread but **loses** prior distill’s rcd&lt;0 / succ 0.124.
- **Still do not replace serve.**

## Serve recommendation

**Keep** `data/scorer-hard-logistic.json`. Shadow only: `data/scorer-hard-bilinear-distill48-ld18-gymalt.json`.

## Remaining blockers

1. Hash-teacher distill: gate-pass XOR cost-win under unpaid knobs; joint domination of serve not achieved.
2. True offline **neural** embed teacher (MiniLM/Qwen3 offline → distill) still untried — hashing teacher is a stand-in.
3. Docker + `SWE_EVAL_CMD` for Verified session-gold promotion.
4. Ship `rules_cost_delta>0` unless operator adopts shadow cost overlay t=0.15 (~2pp success trade).

## Reproduce

```powershell
$env:PYTHONPATH='src'; $env:AIAND_TRAIN='1'
python -m aiand_router.train fit --bilinear --bilinear-distill-hash-dim 48 `
  --gold data/gold-sparse-hard-mix1-train-gym-alt-merged.jsonl `
  --cal data/gold-dense-hard-cal-merged.jsonl `
  --out data/scorer-hard-bilinear-distill48-gymalt.json `
  --geometry-train data/gold-sparse-hard-mix1-train-gym-alt-merged.jsonl `
  --geometry-eval data/gold-verified.jsonl

python -m aiand_router.replay_report --gold data/gold-verified.jsonl `
  --artifact data/scorer-hard-bilinear-distill48-gymalt.json `
  --models config/models.yaml

python -m pytest tests/test_bilinear_scorer.py -q
```
