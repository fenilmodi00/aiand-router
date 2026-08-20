# 07 — GBDT opt-in only after labels transfer

**What to build:** One explicit GBDT + post-hoc calibrator after ranking already transfers, if logistic still misses replay bars. Trees must split on more than log1p(tokens). Not a length-stump zoo. Rec B / live embed stay closed. Replay re-run. Shadow and not_spec_floors unless 08 is separately taken.

**Blocked by:** 06 — Dual replay (only if the gate fails and Spearman > 0)

**Status:** taken once — cost-gold real after catalog priors; GBDT did **not** clear BSS/ECE_m. Keep logistic shadow artifact.

- [x] Taken only when 06 fails and geometry Spearman > 0 (transferring labels)
- [x] One GBDT + calibrator (`data/scorer-hard-gbdt.json` on Mix1 + merged cal); logistic remains the shadow default
- [x] Rec B and live embed stay closed; replay re-run; no auto-flip

GBDT vs logistic on verified: BSS −0.014 / ECE_m 0.221 (worse). Discarded.
