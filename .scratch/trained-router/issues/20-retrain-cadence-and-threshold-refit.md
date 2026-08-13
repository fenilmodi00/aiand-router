# Retrain cadence and threshold refit

Type: grilling
Status: resolved
Blocked by: 13, 17, 19
Part of: [Production trained coding router](../map.md)

## Question

Beyond **new-model onboard** (dense gold slice n≥300 including the new id before trained may score it), what **retrain cadence** does the spec freeze, and does flywheel **refit medium threshold + max_regret** or those stay **frozen until a full retrain**?

[Gold matrix sampling](13-gold-matrix-sampling.md) left cadence as fog. [Threshold-tuning split](19-threshold-tuning-split.md) forbids using flywheel as the *bootstrap* retune split; it does not say whether a later production holdout may retune. [Effort tier threshold and max_regret](17-effort-tier-threshold-max-regret.md): fitted numbers are runtime config; order is train → calibrate → retune → shadow → gate.

HITL — do not resolve without the human.

## Answer

**Event + operator. Freeze \(t,r\) until full retrain. Re-shadow + re-gate. No calendar, no volume quota, no independent rolling retune.**

**Full retrain fires when** (i) new catalog id onboard (dense gold slice n≥300 including that id — already frozen), or (ii) **drift canary** trips, or (iii) an operator triggers. Spec names the triggers; aiand presses the button. Retrain batch includes a teacher pass.

**Drift canary** (monitor only — never train/cal/retune/gate-fit): rolling **n≥300 production hops or 7 days, whichever later**. Trip if escalate rate is >1 pp worse than rules, **or** BSS≤0, **or** equal-width \(M=10\) or equal-mass ECE>0.03 — same definitions as the promotion gate, on **serve hops**, not Verified.

**\(t,r\):** live fitted medium stays frozen between retrains. Every full retrain: train → calibrate → retune medium on a **production retune holdout** → shadow at fitted medium → promotion gate (Verified, medium only) → live. Other rungs = Pioneer offsets from the new medium, then clamp/order as in [Effort tier threshold and max_regret](17-effort-tier-threshold-max-regret.md). Bootstrap **threshold-tuning split** is **v1 only**. If fitted medium misses the 1 pp constraint → do not ship that retrain.

**Production retune holdout:** n≥300, dense (every eligible), query-disjoint from that retrain’s train/cal. **y** = success gold / escalate each ≥ rules − 1 pp. Session gold stays the Verified re-gate. Never Verified/Lite/TB for fit. No bootstrap resolve required (flywheel has no dump F2P).

**During replacement:**
- Drift trip → immediately `path=rules`, reason_code `retrain_drift`. Shadow the candidate. Previous trained does not stay live.
- Operator or new-id (no drift trip) → keep previous trained live until the replacement gates. New id stays rules-only until that replacement includes its dense n≥300.

Failed gate → keep serving whatever was live before that attempt (rules after a drift trip; previous trained otherwise). No live A/B.

Glossary: **Drift canary**, **Production retune holdout**. Do not overload threshold-tuning split.

Rejected: quarterly/monthly calendar, every-N-hops, v1-never-retrain, independent rolling retune, skip Verified, hot-swap, production-canary-as-gate, reuse bootstrap TTS forever, dual bootstrap-resolve on flywheel, ECE-only / no-window canary, always-rules on any retrain, keep-bad-hop-after-drift, live A/B.

## Comments

- Graduated from map fog after the proposal-grade spec. Onboard bar is frozen; calendar/volume/drift triggers and threshold-vs-retrain coupling are not.
- Grill round 1 (all recs): **Q1 A** event + operator (new-id, gate-metric drift canary, or operator); no calendar/volume. **Q2 A** freeze \(t,r\) until full retrain; then train → cal → retune on a fresh production holdout (never Verified/Lite/TB); bootstrap TTS is v1 only.
- Grill round 2 (all recs): **Q3 A** re-shadow + Verified re-gate before live; failed gate does not ship. **Q4 A** production retune holdout n≥300 dense; y = success gold / escalate; bootstrap TTS is v1 only. **Q5 A** drift canary = n≥300 hops or 7 days, whichever later; trip on escalate 1 pp miss or BSS≤0 or ECE>0.03; monitor only.
- Grill round 3 (all recs): **Q6 A** drift → rules immediately (`retrain_drift`); operator/new-id keep previous trained until replacement gates. **Q7 A** glossary **drift canary** + **production retune holdout**.
