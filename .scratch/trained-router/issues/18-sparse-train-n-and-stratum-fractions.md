# Sparse-train n and stratum fractions

Type: grilling
Status: resolved
Blocked by: 13, 16
Part of: [Production trained coding router](../map.md)

## Question

Given the frozen **bootstrap dump** set, what exact **sparse-train n** and **per-stratum fractions** does the spec freeze?

[Gold matrix sampling](13-gold-matrix-sampling.md) already froze the shape: dense held-out n≥300 × eligible; sparse train **thousands** × Flash+trio; stratum = `complexity_bin` × phase × tools-present vs not. Dump membership is now frozen in [Bootstrap dump set](16-bootstrap-dump-set.md): required smith `tool` traj + smith tasks + BFCL; gym/r2e allowed; rebench optional. This ticket freezes the **numbers**, not dump membership or the hybrid matrix shape.

HITL — do not resolve without the human.

## Answer

**n = 4000** sparse-train **queries** (not cells) × Flash + measured trio when eligible (≤16k completions). Floor **n ≥ 3000** if the SWE-bench collision filter shrinks the pool. Optional gym/r2e/rebench may **add**, not cut smith. Disjoint from dense gold slice, 3×5, promotion, and the threshold-tuning carve ([Threshold-tuning split](19-threshold-tuning-split.md)). Spec spend only — this repo does **not** run sparse-train (stays 3×5 smoke + teacher ~100).

**Stratum** = complexity bin × **phase family** × tools-present vs not. Phase family = `discover | plan | edit | tool | debug | summarize` (same collapse as rules bars). 4×6×2 = 48 cells. No 48-cell joint table.

**Margins** (independent; ±5 pp OK; leftover after floors fills these, oversampling hard/frontier vs dump mass):

| Axis | Targets |
| --- | --- |
| bin | trivial 15% / standard 40% / hard 30% / frontier 15% |
| tools | present 75% / absent 25% |
| phase family | edit 30% / tool 25% / plan 15% / debug 15% / discover 10% / summarize 5% |

Occupied-stratum **floor ≥ 20**. Empty cells stay empty (no synthetic queries). If an occupied cell has <20 available after labeling, take all of them.

**Dump mix:** primary = smith `tool` traj steps. **BFCL ≤ 15%** of n (tool-JSON only). Tasks dump = teacher/relabel pool unless traj pool < n≥3000 after collision filter.

**K3 probe (optional, not v1-required):** ≤5% of n, `hard|frontier` × tools-present only. Not a 5th required anchor.

Glossary: **Phase family**; **Stratum** uses phase family, not raw alias.

Rejected: floor-only n, n=8000 as v1 freeze, raw phase aliases / drop-phase strata, uniform or dump-prevalence mix, 48 joint %, uncapped BFCL, required K3-on-every-hard-row, prototype sparse-n on the $15 cap.

## Comments

- Graduated from map fog after [Bootstrap dump set](16-bootstrap-dump-set.md). Required ingest ≈ smith `tool` ~24k trajs + smith tasks ~50k + BFCL ~4k; gym/r2e/rebench optional. Dense cal n≥300 already frozen; sparse-train n and stratum mix were still “thousands.”
- Grill: Q1–Q6 all take the recs (n=4000 floor ≥3000; phase family; independent margins + occ. floor 20; BFCL ≤15%; optional K3 probe ≤5%; spec only, no repo sparse-run).
