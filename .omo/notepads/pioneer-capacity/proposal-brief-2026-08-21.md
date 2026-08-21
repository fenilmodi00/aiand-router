# Executive Brief — aiand-router → Pioneer-Class (2026-08-21)

**HEAD** `492a192` · **Price source** `config/models.yaml` · **Full report** `docs/prototype-to-pioneer-proposal-2026-08-21.md`

**One sentence:** We built a working OpenAI-compatible gateway (`router/auto`) that routes each coding-agent hop to the cheapest *capable* aiand model; the calibrated learned router is shadow-ready, quality-first, and gated to production by a Verified 500 holdout.

| What works now | Gated / next |
|---|---|
| Rules gateway: hard constraints → phase bar → score (`router.py:234,469`) | Trained shadow: features-only → calibrated `P(success)` → cheapest-above-bar (`scorer.py:401,550`) — not serving until gate |
| $50 at spec-margin: sparse ~430–2k, dense/cal ~300, K3 silver-only, teacher Motif-3→GLM5.2 (`train.py`) — labeled `bootstrap_partial` | Bounded check n~30–50 (`bounded_check_only`): BSS 0.404 ✓ / ECE 0.013 ✓ / ECE-mass 0.034 ✗ (honest shortfall) |
| Calibration: Platt + isotonic PAVA, `n_cal>1000→isotonic` (`metrics.py:26`) | Need `n_cal>1000` reallocated dense + 300-hop flywirl before re-spend |

**How far from Pioneer:** Data is binding (10–50% of spec floors), then architecture (signal poverty — no embeddings/confidence cascade), then compute (`research-...-gap-2026-08-21.md:138`). We are correctly *not* building Fireworks-class inference (kernels/scheduler, 140B tok/day [Google Cloud](https://cloud.google.com/blog/topics/startups/fireworks-ai-gen-ai-efficient-inference-engine)) — we are a gateway router *into* aiand.

> **Rule-based vs Scorer — 4-line verdict (see proposal §3.7)**
> - **Current posture:** Rules SERVE prod (`TRAINED_PATH=shadow` default at `scorer.py:49` + `app.py:155`; `conftest.py:10` clamps tests; F7 invariant — shared `EligibleSet` at `router.py:234,301` / `scorer.py:550`, K3 gated at `effort=max` via `premium_aa_floor 58`).
> - **Intent:** Complements not alternatives — rules = hard constraints at zero latency, scorer = cheapest-above-bar inside that envelope via calibrated `P(success)` (`scorer.py:401`; leanlm.ai pattern cited in gap report §73).
> - **Who wins now:** **Rules.** Scorer is honest shadow (BSS 0.404 ✓ / ECE-width 0.013 ✓ / ECE-mass 0.034 ✗ at `metrics.py:26-31`) on `bootstrap_partial` data (sparse 0.4–2k not 4k, dense/cal ~300, K3 silver-only, `n_cal` rarely >1000).
> - **What flips it:** `n_cal>1000` reallocated dense → isotonic + frozen strata + offline embedding ablation (Brier better AND ECE not worse) + hybrid cascade spike + Verified 500 gate (quality≥rules−1pp AND cost<0 AND BSS>0 AND ECE≤0.03). Next **$50** → **$200** staged.

**Target:** 45–85% cost at 95% quality ([tianpan](https://tianpan.co/blog/2025-11-03-llm-routing-model-cascades)), verified by dual-metric gate quality≥rules−1pp AND cost<0 AND BSS>0 AND ECE≤0.03 on 500 sessions.

**Ask — staged credits for labels (not GPU):** Next **$50** (close `n_cal→1000`, shadow 100-hop flywheel, router-timing headers) → **$200** to Verified gate (K3 dense + sparse 4k + 500-session holdout). ~$0.01 per sparse query, ~$0.0015 per teacher row (`pioneer-capacity.md:42`).

**Guarantees:** Rules-default-until-gate (`TRAINED_PATH=shadow` + `tests/conftest.py`), no invented savings % (vs `most_expensive_eligible` at `router.py:434`), no eval-dump training (`pool.py:collision_keys`), flywheel log store stays AI& infra.

*Commit 492a192 — read the full proposal for math (§4), flow diagram (§3.1), and resource tables (§7). Full head-to-head table at proposal §3.7.*
