# Student training target

Type: grilling
Status: resolved
Blocked by: 01, 13
Part of: [Production trained coding router](../map.md)

## Question

What supervises the student’s per-eligible P(success): **success gold only**, **teacher silver only**, or **gold where present + silver as distill/regularizer** (Zooter-style)?

Calibration must use a held-out **measured** slice, not silver. Wait for [Scorer architectures under a 10ms hop](01-scorer-architectures-under-10ms.md) and [Gold matrix sampling](13-gold-matrix-sampling.md).

HITL — do not resolve without the human.

## Answer

**Gold + query-only silver regularizer** — not gold-only, not silver-only, not Zooter. Same recipe for bootstrap and flywheel.

- **Student** = tiny hop head (bin + per-eligible P(success)), not the teacher and not the learned stub.
- **Observed cells:** `success_gold` only (BCE/Brier). Gold wins if silver disagrees; no silver loss there.
- **Unobserved cells:** teacher **silver P(success)** as a small KL/MSE prior. Skip cells with neither gold nor silver (don’t impute 0). Retrain batch includes a teacher pass.
- **Never** fit Platt/isotonic, ECE, Brier, threshold, or the promotion gate on silver — held-out **measured** slice only.
- **λ** is a train hyperparam, not a spec number. Spec: small regularizer, gold dominates, silver unobserved-only.
- **New catalog models:** silver may train the head; live trained pick stays **rules-only** until a **dense gold slice** including that id hits n≥300 ([Gold matrix sampling](13-gold-matrix-sampling.md)). Shadow may log the prior with a reason_code.
- Complexity-bin head stays teacher bins. Session gold stays promotion-gate only. Response-RM/judge distill (true Zooter) is not this recipe.

## Comments

- [Scorer architectures under a 10ms hop](01-scorer-architectures-under-10ms.md) is resolved. Rec A/B are both query-time tiny heads over survivors; they still need a training target. Calibration research: **never** calibrate or gate on teacher silver. Still wait on [Gold matrix sampling](13-gold-matrix-sampling.md). [scorer](../research/scorer-architectures.md) · [calibration](../research/calibration.md)
- Claimed. Grilling despite [Gold matrix sampling](13-gold-matrix-sampling.md) still open: bootstrap density does not change flywheel sparsity (observed hop only) or “missing ≠ 0.” Silver-only is out (calibrate/gate on measured only). Round 1: gold-only vs gold + query-only silver regularizer; “Zooter-style” is not query-only silver.
- Grill round 1 (all recs): drop “Zooter-style”; **student** = tiny scorer; supervise P(success) with **gold + query-only silver regularizer**; silver loss **unobserved cells only** (gold wins on observed); never calibrate/gate on silver; same recipe bootstrap + flywheel.
- [Scorer shape Rec A vs Rec B](15-scorer-shape-rec-a-vs-b.md) resolved: student shape is Rec A (**Scorer**). Does not change gold vs silver.
- Grill round 2 (all recs): new ids **gold to serve** (silver may train, does not unstick live pick; onboard n stays [Gold matrix sampling](13-gold-matrix-sampling.md)); **λ** train hyperparam; skip cells with neither gold nor silver.
- [Gold matrix sampling](13-gold-matrix-sampling.md) is resolved. Gold is hybrid (dense n≥300 full eligible + sparse Flash+trio train); missing ≠ 0; cal/gate still measured-only. Unblocks this ticket’s density assumptions.
