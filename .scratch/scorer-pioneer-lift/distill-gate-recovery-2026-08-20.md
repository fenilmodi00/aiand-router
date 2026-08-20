# Distill gate recovery — unpaid (2026-08-20)

**Serve candidate unchanged:** `data/scorer-hard-logistic.json` + `config/models.yaml`  
**No** `TRAINED_PATH=trained`. **No** commits / paid pools.

## What changed (code)

| Seam | Change |
| --- | --- |
| `train --bilinear-distill-latent-dim N` | Cap teacher latent dim (was hardcoded `min(32, t_dim)`) |
| `train --bilinear-ridge-l2` | Ridge L2 for student←teacher map (default 0.05) |
| Distill meta | Records `ridge_l2` |
| Tests | `test_bilinear_distill_latent_and_ridge_cli` (11 pass) |

## Sweep coverage (unpaid)

- Post-hoc: Platt temperature, factor×temp, `a` rescale, logistic↔distill p-blend
- Retrain: hash_dim ∈ {32,48,64,96}, latent ∈ {def/16/24/32/48 + nearby 12–22}, ridge ∈ {0.02,0.05,0.1,0.2}
- Train subset: Mix1-only vs Mix1∪gym-alt
- Full grid dump: `.scratch/scorer-pioneer-lift/distill-gate-sweep-2026-08-20.json`

## Metrics vs serve (frozen `gold-verified.jsonl`)

| Artifact | gate | AUC | BSS | ECE_w | P-spread | rcd | succ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **`scorer-hard-logistic.json` (serve)** | **true** | **0.754** | **+0.00063** | **0.007** | **0.102** | +0.000687 | 0.112 |
| `scorer-hard-bilinear-distill48-gymalt.json` (prior best cost/BSS) | false | 0.747 | **+0.058** | 0.076 | 0.076 | **−0.000278** | **0.124** |
| `scorer-hard-bilinear-distill48-ld16-gymalt.json` | **true** | 0.792 | +0.0224 | 0.029 | 0.110 | +0.000687 | 0.112 |
| **`scorer-hard-bilinear-distill48-ld18-gymalt.json` (best gate distill)** | **true** | **0.791** | **+0.0316** | **0.022** | **0.105** | +0.000687 | 0.112 |

Nearby latent: ld14≈ld16 pass; ld18 best ECE/BSS among passers; ld12 ECE fail; ld20 spread&lt;0.10; ld22 spread fail.

## Honest read

1. **Gate recovery is real.** Lowering distill latent from 32→14–18 jointly clears `mean_p_spread≥0.10` and `ECE_w≤0.03` with `replay_gate_pass=true`.
2. **Cost/success wins of prior distill48 are not recovered** on the gate-passing latent: `rules_cost_delta` returns to serve’s **+0.000687**; succ back to 0.112.
3. **Post-hoc temp / factor / blend** never jointly beat serve on binding bars while keeping distill’s rcd&lt;0. Softening for ECE collapses spread (or BSS); sharpening for spread blows ECE.
4. **Mix1-only distill** gets spread but ECE stays too high (gate fail).
5. **Serve replace: no.** ld18 beats serve on AUC/BSS/spread with gate pass, but ECE is worse and rcd is unchanged — not clearly better on **all** binding concerns.

## Option B — logistic cost–quality frontier (shadow)

Ship medium threshold sweep on serve logistic (max_regret=0.20):

| t | gate | rcd | BSS | succ |
| ---: | ---: | ---: | ---: | ---: |
| 0.10 (ship) | true | +0.000687 | +0.0006 | 0.112 |
| 0.12 / 0.13 | true | +0.000599 | +0.0035 | 0.101 |
| 0.145 | false | −0.000249 | −0.0053 | 0.101 |
| **0.15** | **true** | **−0.000688** | +0.0006 | **0.090** |
| 0.16 | true | −0.001243 | +0.0015 | 0.079 |

No unpaid middle knob clears `rcd≤0` with less success loss than t=0.15. Existing shadow overlay remains: `config/models.cost-overlay-t015.yaml` + `data/scorer-hard-logistic-cost-overlay.json`.

On ld18 distill, raising threshold does **not** clear rcd (stays ≥+0.0001 through t=0.16).

## Serve recommendation

**Keep** `data/scorer-hard-logistic.json`.  
Shadow gate-pass distill: `data/scorer-hard-bilinear-distill48-ld18-gymalt.json` (experimental only).

## Is distill path exhausted?

**For hashing-trick teacher → ridge student under current gold:** largely yes for *joint* serve domination (gate + rcd≤0 + succ≥serve). Gate-pass exists; cost-win + gate-pass does not under unpaid knobs tried. Remaining headroom is **true neural embed teacher** (MiniLM/Qwen3 offline) or more geometry-passing hard-gold — not more hash-dim / temp / blend tweaks.

## Remaining blockers

1. Serve `rules_cost_delta>0` unless operator adopts t=0.15 overlay (~2pp succ).
2. Docker + `SWE_EVAL_CMD` for Verified session-gold.
3. Blind paid gym_alt/smith still blocked.
4. Gate-pass distill does not clear cost parity blocker.

## Reproduce

```powershell
$env:PYTHONPATH='src'; $env:AIAND_TRAIN='1'
python -m aiand_router.train fit --bilinear --bilinear-distill-hash-dim 48 `
  --bilinear-distill-latent-dim 18 `
  --gold data/gold-sparse-hard-mix1-train-gym-alt-merged.jsonl `
  --cal data/gold-dense-hard-cal-merged.jsonl `
  --out data/scorer-hard-bilinear-distill48-ld18-gymalt.json `
  --geometry-train data/gold-sparse-hard-mix1-train-gym-alt-merged.jsonl `
  --geometry-eval data/gold-verified.jsonl

python -m aiand_router.replay_report --gold data/gold-verified.jsonl `
  --artifact data/scorer-hard-bilinear-distill48-ld18-gymalt.json `
  --models config/models.yaml

python -m pytest tests/test_bilinear_scorer.py -q
```
