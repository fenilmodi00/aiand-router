# Gold matrix sampling

Type: grilling
Status: resolved
Blocked by: 04, 10
Part of: [Production trained coding router](../map.md)

## Question

For **success gold**, do we run **every eligible candidate** per bootstrap query, or a **stratified sparse** subset (cheap + mid + premium per stratum)?

[Teacher labeling for multi-candidate success](02-teacher-labeling-multi-candidate.md): gold requires real aiand runs; a teacher cannot invent it. Full matrix is the literature gold standard; sparse is the credit-saving fallback (never a single model). Wait for [Bootstrap coding-agent datasets](04-bootstrap-coding-agent-datasets.md) (how many queries) and [Teacher model from aiand catalog](10-teacher-model-from-aiand-catalog.md) (budget posture).

HITL — do not resolve without the human.

## Answer

**Hybrid gold matrix. Not full N×Q, not sparse everywhere.**

- **Dense gold slice** (held-out): every *eligible* model, **n≥300** stratified queries, one prod-like completion (gateway cache). Calibrator + reliability + new-model onboard. 3×5 stays smoke, disjoint.
- **Sparse gold** (train): thousands of queries × **sparse-train anchors** = Flash + measured trio (when eligible). Never a single model. K3 / Motif / Gemma / GLM / GPT-OSS only here via dense slice + flywheel (optional thin `hard|frontier`×tools K3 probe, not every train row).
- **Flywheel:** observed hop (+ escalate) + small 2–3 explore. Missing cell ≠ 0.
- **Eligible set only**, not the full catalog. **Stratum** = `complexity_bin` × phase × tools-present vs not — not empirical difficulty.
- **New catalog id:** rules-only until a dense slice **including that id** hits n≥300. Silver alone does not unstick trained P(success) for it.
- **Spec spend band** (candidate runs, not teacher): dense n≥300 × eligible + sparse thousands × 4 anchors — low hundreds to low thousands USD at current list prices. Dump ingest stays [Bootstrap dump set](16-bootstrap-dump-set.md). Teacher $ is [Teacher model from aiand catalog](10-teacher-model-from-aiand-catalog.md).

Retrain cadence stays fog. Exact sparse-train n / stratum mix → [Sparse-train n and stratum fractions](18-sparse-train-n-and-stratum-fractions.md) after [Bootstrap dump set](16-bootstrap-dump-set.md).

## Comments

- [Bootstrap coding-agent datasets](04-bootstrap-coding-agent-datasets.md) is resolved. Query volume can come from SWE-smith (~5k SFT / ~26k dump), SWE-Gym (~491 success / 5.3k verifier), R2E-Gym (~3.2k), plus task dumps for relabel (~50k / 21k / 4.7k). None already have per-aiand `success_gold` — matrix runs are still required. Still wait on [Teacher model from aiand catalog](10-teacher-model-from-aiand-catalog.md) for budget. [note](../research/bootstrap-datasets.md)
- Grill round 1 (all recs): **C** hybrid (dense held-out measured slice for cal/reliability + new-model onboard; sparse train; flywheel = observed hop + small explore; 3×5 smoke disjoint). **B** spec budget band: dense cal **n≥300 × full eligible** + sparse train **thousands × 3–4 anchors** (low hundreds–low thousands USD); dump ingest stays [Bootstrap dump set](16-bootstrap-dump-set.md). **A** stratum = `complexity_bin` × phase × tools-present vs not (not empirical difficulty). Teacher $ stays [Teacher model from aiand catalog](10-teacher-model-from-aiand-catalog.md).
- Grill round 2 (all recs): **A** sparse-train anchors = Flash + measured trio (K3/Motif/Gemma/GLM/GPT-OSS only on dense slice + flywheel; optional thin `hard|frontier`×tools K3 probe, not every train row). **Eligible set only**, not full catalog. **One** prod-like completion per cell (gateway cache). New-model onboard = same dense bar **n≥300 including the new id** before trained may emit P(success) for it; silver alone does not unstick. Retrain cadence stays fog.
- [Teacher model from aiand catalog](10-teacher-model-from-aiand-catalog.md) is resolved. Teacher $ is separate: spec few thousand query-only rows (cheap-then-escalate, Motif→GLM / Gemma→GLM); this repo smokes ~100. Do not fold teacher spend into the gold-matrix band.
- [Bootstrap dump set](16-bootstrap-dump-set.md) is resolved. Required: smith `tool` + smith tasks + BFCL; gym/r2e allowed; rebench optional. Sparse-train n / stratum mix graduated to [Sparse-train n and stratum fractions](18-sparse-train-n-and-stratum-fractions.md).
- [Student training target](14-student-training-target.md) resolved: gold + query-only silver regularizer (unobserved only); silver does not unstick live trained pick. Aligns with round-2 rec here (new-id onboard waits for success gold; how much gold still this ticket).
