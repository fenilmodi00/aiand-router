# Calibration for router P(success)

Type: research
Status: resolved
Blocked by: none
Part of: [Production trained coding router](../map.md)

## Question

What does **calibrated P(success)** require in the literature — reliability diagrams, ECE, Brier, Platt vs isotonic vs temperature scaling?

What production or academic **routers** actually document calibration (not just a 0–1 score)? What is the **minimum eval** a promotion gate should demand so “beats rules” cannot pass a cheaper miscalibrated scorer?

Pioneer claims calibrated success probability; their docs do not describe the method. Do not invent their internals. Cite primary sources only.

Findings land on branch `research/calibration` as `.scratch/trained-router/research/calibration.md`.

## Answer

Calibrated P(success) means predicted rates match observed rates (reliability diagram + ECE + Brier), not a 0–1 score. Accuracy/AUC/“confidence” is not calibration; a constant dummy is perfectly calibrated and useless. Binary: Platt if \(n_\text{cal}\lesssim 1000\), isotonic if larger; temperature scaling is multiclass softmax. Pioneer claims calibration and **does not** document a method — do not invent it. No production coding-router vendor reviewed here publishes ECE/Brier.

**Promotion-gate calibration check (numbers still HITL on ticket 08):** selection-conditioned Brier skill \(>0\) **and** dual-binning ECE (equal-width \(M=10/15\) + equal-mass) vs a pre-declared baseline, plus the reliability diagram, on a split unused for train/calibrator/threshold. \(y\) = session gold if present else success gold; \(\hat p\) = P(success) of the **selected** model. Never fit threshold on the promotion split.

Detail: [`.scratch/trained-router/research/calibration.md`](../research/calibration.md) on `research/calibration` @ `345379f`.
