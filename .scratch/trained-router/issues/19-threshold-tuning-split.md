# Threshold-tuning split

Type: grilling
Status: resolved
Blocked by: 16, 17
Part of: [Production trained coding router](../map.md)

## Question

Where does the **threshold-tuning split** come from, how large is it, and which **gold** does the retune constraint use?

[Effort tier threshold and max_regret](17-effort-tier-threshold-max-regret.md) froze the procedure: disjoint from train, calibrator, and promotion; fit medium before shadow; minimize list-price USD s.t. session gold **and** escalate each ≥ rules − 1 pp. [Bootstrap dump set](16-bootstrap-dump-set.md) forbids **eval-only** dumps (SWE-bench family + Terminal-Bench) from threshold/max_regret fit. Promotion stays Verified/Lite.

Tension: retune was stated in **session gold** terms, but harness resolve bits live on eval-only dumps that must not be used to fit threshold. Decide dump source, n, and whether the constraint is session gold, success gold, or a bootstrap proxy.

HITL — do not resolve without the human.

## Answer

**Third held-out bootstrap split**, dense, **n≥300** SWE-like. Disjoint from sparse-train ([Sparse-train n and stratum fractions](18-sparse-train-n-and-stratum-fractions.md)), the calibrator **dense gold slice** ([Gold matrix sampling](13-gold-matrix-sampling.md)), 3×5 smoke, and promotion (Verified/Lite + TB). Not flywheel.

**Source:** required dumps (smith `tool` + smith tasks); gym/r2e/rebench only if ingested; collision-filter vs the SWE-bench family. BFCL may be extra tools rows only — not required, does not count toward n≥300.

**Matrix:** every *eligible* model (same shape as the calibrator dense slice, query-disjoint). One prod-like completion per cell + dump F2P/P2P (or dump harness). Gateway cache. Dump teacher `resolved` is not y (optional sampling filter only).

**Stratum:** complexity bin × phase family × tools-present vs not. Same axes as the rest of the map. No retune-only tilt; do not copy sparse-train margin % onto this split. Gym/r2e not a retune hard-require.

**Retune constraint y** (search procedure stays [Effort tier threshold and max_regret](17-effort-tier-threshold-max-regret.md); this ticket owns the labels): minimize list-price USD s.t. **success gold** (escalate) **and** **bootstrap resolve** each ≥ rules − 1 pp. Never silver. Never Verified/Lite/TB **session gold**.

**Bootstrap resolve:** per-candidate aiand completion vs allowed-dump tests. Not session gold (promotion-gate only). Not success gold.

**Spend:** second dense slice + per-cell test exec; same order as calibrator dense, plus eval Docker/CPU. Spec only — this repo does not run it.

**Order unchanged:** train → calibrate → retune medium on this split → shadow at fitted medium → promotion gate on Verified/Lite.

Glossary: **Threshold-tuning split**, **Bootstrap resolve**. Session gold stays promotion-gate only. Dense gold slice ≠ this split.

Rejected: success-gold-only retune, dump teacher `resolved` as y, Verified/Lite for fit, carve from calibrator slice, flywheel/3×5 as the split, sparse-train anchors only, n≥200 / n≥500 / no floor, retune-specific stratum table, broaden session gold, edit 17’s Answer.

## Comments

- Graduated from map fog after [Effort tier threshold and max_regret](17-effort-tier-threshold-max-regret.md) and [Bootstrap dump set](16-bootstrap-dump-set.md). Operating-point search is specified; the split itself is not.
- Grill round 1 (all recs): **Q1 B** dual constraint — success gold / escalate on every retune row + dump session resolve on SWE-like subset; BFCL escalate/tools only; never Verified/Lite/TB. **Q2 A** dense (every eligible), query-disjoint from calibrator dense slice. **Q3 A** third held-out bootstrap split (smith `tool` + smith tasks + BFCL; gym/r2e/rebench only if ingested); not cal slice, not flywheel, not 3×5.
- Grill round 2 (all recs): **Q4 A** per-candidate aiand completion vs dump F2P/P2P (not dump teacher `resolved`; not lazy). **Q5 A** n≥300 SWE-like with bootstrap resolve; BFCL extra only, does not count. **Q6 A** same stratum axes as dense gold slice; no gym/r2e hard-require; no retune tilt; no % table here ([Sparse-train n and stratum fractions](18-sparse-train-n-and-stratum-fractions.md) owns sparse-train margins).
- Grill round 3 (all recs): **Q7 A** keep **threshold-tuning split**. **Q8 A** **bootstrap resolve**; session gold stays gate-only. **Q9 A** 17 owns search + ship table; this ticket owns y (pointer comment on 17, do not edit 17’s Answer).
