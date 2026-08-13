# Promotion gate numeric bars

Type: grilling
Status: resolved
Blocked by: 03, 04
Part of: [Production trained coding router](../map.md)

## Question

What **numbers** does “beats rules” require before trained may leave shadow?

Standing preference: non-inferior quality (escalate rate and/or task success), strictly lower cost, calibration trustworthy (e.g. ECE / reliability). No invented savings %.

Need, from research: calibration metrics that are standard, and how large a held-out bootstrap we can actually get. Then freeze deltas, ECE (or equivalent) ceiling, and minimum held-out size for the spec.

HITL — do not resolve without the human.

## Answer

Promote out of shadow only if **all** of the following hold on a frozen promotion split unused for train, calibrator, or threshold/max_regret:

1. **Quality (non-inferior, 1 pp):** session gold (resolve / `tests_passed`) **and** per-request escalate rate, each ≥ rules − 0.01 absolute. Session gold worse than that cannot be rescued by escalate-only.
2. **Cost:** total list-price USD **rules cost delta < 0**. No minimum %. Equal → no promote. Not called savings.
3. **Calibration (selection-conditioned):** Brier skill \(>0\); equal-width ECE \(M=10\) **and** equal-mass ECE \(\le 0.03\); reliability diagram attached. Report \(M=15\) + MCE, do not gate on them alone. \(\hat p\) = P(success) of the **selected** hop; calibration \(y\) = **success gold** (no-escalate + tools), **not** session gold (one session bit ≠ every hop).
4. **Split:** primary **SWE-bench Verified (500)**; Lite (300) OK as cheaper proxy until Verified is run, not a substitute after. Floor **n ≥ 300** session-gold tasks. **Terminal-Bench (80–89) = canary only** (do not train; n too small to pass/fail ECE alone). ECE/Brier use hops inside those sessions.

Calibrator hygiene unchanged: Platt if \(n_\text{cal}\lesssim 1000\), else isotonic. Live effort threshold/max_regret is **not** this ticket → [Effort tier threshold and max_regret](17-effort-tier-threshold-max-regret.md).

## Comments

- [Calibration for router P(success)](03-calibration-for-router-p-success.md) and [Bootstrap coding-agent datasets](04-bootstrap-coding-agent-datasets.md) are resolved. Freeze: non-inferior quality + strictly lower cost **and** selection-conditioned **Brier skill \(>0\)** + **dual-binning ECE** (equal-width \(M=10/15\) + equal-mass) vs a pre-declared ceiling, plus the reliability diagram, on a split unused for train/calibrator/threshold. \(y\) = session gold if present else success gold. Platt if \(n_\text{cal}\lesssim 1000\), else isotonic. ECE ceiling is still this ticket (literature working range after post-hoc maps is a few points, e.g. Guo often \(\le 2\%\), UCCI \(0.03\)). Held-out size: SWE-bench Verified/Lite (500/300) and Terminal-Bench (80–89, **do not train**) are eval gold, not train. [calibration](../research/calibration.md) · [datasets](../research/bootstrap-datasets.md)
- Grill: Q1–Q4 all take the recs (1 pp both quality bars; rules cost delta < 0; ECE ≤ 0.03; Verified/Lite/TB canary, n ≥ 300). Calibration \(y\) refined to success gold on selected hops, not session gold.
