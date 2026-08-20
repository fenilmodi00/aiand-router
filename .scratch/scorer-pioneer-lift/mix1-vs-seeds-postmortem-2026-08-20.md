# Unpaid post-mortem: Mix1 vs seeds 11–16 (2026-08-20)

**Conclusion:** Only **Mix1** (seed-11 recipe, n=40) passes standalone geometry. Seeds 11–16 **top-up / variant pools** all fail. **Class-quota preflight does not predict standalone geometry** (seed-16: preflight pass → geometry fail).

**Serve candidate unchanged:** `data/scorer-hard-logistic.json` (shadow only; `not_spec_floors`).

**Spend:** seed-16 Δ **+$0.41** → total **~$14.48**. No merge, retune, or replay on failed batches.

---

## Failure-mode table (one view)

| Batch | Pool / recipe | n | y | Spearman | order | geo | Failure mode | kimi-only | all-fail | qwf | Flash≡Pro signal |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Mix1** | near-miss seed-11 flashlight | 40 | **0.181** | **0.949** | **true** | **pass** | — (reference pass) | 12 | 23 | 1 | Flash **0.10** > Pro **0.075** |
| Seed-11 | n400 top-up / probe | 32 | 0.211 | 0.83 | false | fail | Qwen pulls ahead; Flash≡Pro | 7 | 19 | 2 | Flash **= Pro** 0.125 |
| Seed-12 | mix1like + F2P cap | 32 | **0.023** | 0.0 | false | fail | y below band; nearly all-fail | 0 | **31** | 0 | all models ~0.03 |
| Seed-13 | mix1like draw | 32 | 0.086 | 0.83 | false | fail | y below band; Flash≡Pro | 5 | 25 | 1 | Flash **= Pro** 0.031 |
| Seed-14 | winner-stratified | 32 | 0.102 | 0.95 | false | fail | Spearman high but order false | 4 | 25 | 1 | Flash **= Pro** 0.031 |
| Seed-15 | kimi-only-targeted | 32 | **0.250** | 0.50 | false | fail | y above band; qwf inflated | 10 | 14 | **4** | Flash **= Pro** |
| Seed-16 | order-conservative | 32 | **0.047** | 0.82 | false | fail | y below band; all-fail overshoot | 6 | **26** | 0 | Flash=Qwen=Pro **0** |
| Verified (eval) | frozen holdout | 89 | 0.070 | — | **true** | — | target geometry | 5 | 72 | 5 | Pro **0** |

**qwf** = qwen-without-flash (order-breaking pattern). **geo** = standalone `geometry_pass` vs `data/gold-verified.jsonl`.

---

## What preflight got wrong (seed-16)

| Preflight signal (unpaid) | Result | Standalone geometry (paid) |
| --- | --- | --- |
| Class fractions (fail_heavy / kimi_heavy / mixed) | **pass** (~10 pp) | **fail** |
| Mix1 retroactive proxy score | **pass** (+1.10) | **fail** |
| Projected cost | **pass** (~$0.66) | spent +$0.41 |

Preflight optimizes **unlabeled class mix**; geometry requires **labeled winner-pattern composition** (Flash > Pro, limited qwf, y in 0.07–0.22). Those are not the same random variable.

---

## Policy (no further blind paid draws)

Do **not** spend on: order-conservative, kimi-only-targeted, winner-stratified, mix1like, or another seed from smith pools until a **new label source** or materially different sampler exists.

**Smith-pool gold expansion is blocked** until holdout-like winner order can be predicted offline — current proxy stack (F2P×nm strata, mutation markers, class quotas, pattern likelihood) has been falsified by seeds 11–16.

---

## Honest unpaid next paths

| Path | Status | Notes |
| --- | --- | --- |
| Mix1-only retune/threshold | **refused** | `train retune` needs n≥300; Mix1 has 160 cells; no geometry-passing concat path |
| Replay parity posture | **implemented** | `replay_report` now stamps `local_replay_gate_pass`, `production_parity=false`, `parity_blockers` |
| Lite / session-gold dry-run | **ready, unpaid** | `python -m aiand_router.lite_runner --fixture data/lite_fixture.json` — fixture only; no HTTP |
| **SWE-Gym `gym_alt` pool** | **chosen unpaid advance** | `pool ingest --profile gym_alt`; `train pool --gym-tasks …`; dry-run n=113 / sample n=40 at `data/pool-hard-gym-alt-*.jsonl`. Still needs **paid** gold for geometry. |
| Verified ids scaffold | **implemented unpaid** | `lite_runner --ids-only --bench verified` → `data/verified_ids_scaffold.json` (`session_gold=false`) |
| Verified n=500 promotion | **not started** | runbook §(a); requires paid session gold |
| Smith-pool gold expansion | **blocked** | seeds 11–16 exhausted family |

Full ranking: `.scratch/scorer-pioneer-lift/unpaid-next-path-2026-08-20.md`.

---

## Remaining blockers to parity

1. No second geometry-passing hard-gold batch (scale / merge / retune blocked).
2. `rules_cost_delta > 0` on verified replay (trained more expensive than rules).
3. Equal-mass ECE 0.143 waived at n=72 — not production-grade.
4. No session-gold promotion gate (Verified n≥500).
5. `TRAINED_PATH=trained` correctly blocked.
6. Smith-derived pool family exhausted as paid label source without new design.
