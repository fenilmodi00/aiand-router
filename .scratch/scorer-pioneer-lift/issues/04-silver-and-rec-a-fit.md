# 04 — Silver + Rec A fit

**What to build:** A Rec A Scorer the live hop can load while still serving shadow: Motif cheap then GLM escalate writes silver P(success) only on unobserved cells; parse-fail always escalates; unlabeled stays unlabeled. Logistic Rec A fits per-model intercepts from gold marginals, then feature correction, then a calibrator on the dense gold slice only. Complexity bin is predicted from request-observable features. The artifact stays `not_spec_floors`. Path is not flipped to trained. No live embed. No GBDT in this ticket. Catalog ids without success gold get no live calibrated P(success) from silver alone.

**Blocked by:** 02 — Sparse success-gold run; 03 — Dense/cal gold slice

**Status:** resolved

- [x] Silver P(success) is written only on unobserved cells
- [x] Parse-fail always escalates
- [x] Silver is never used for Platt, the replay gate, or threshold
- [x] Unlabeled stays unlabeled
- [x] Ids without success gold get no live calibrated P(success) from silver alone
- [x] Logistic Rec A: per-model intercepts from gold marginals, then feature correction, then calibrator on the dense gold slice only
- [x] Complexity bin is predicted from request-observable features
- [x] Artifact `not_spec_floors` is true
- [x] `TRAINED_PATH` is not flipped; live hop stays shadow
- [x] No live embed
- [x] No GBDT in this ticket

## Answer

Fit already wrote silver only on unobserved cells, gold intercepts, and cal-slice Platt (`not_spec_floors`). Live `score_eligible` now emits calibrated logistic P only for ids with a gold intercept, so silver-alone weights cannot unstick an unseen catalog id. Cal-only ids still onboard via the gold table. Shadow hop loads the Rec A artifact and predicts complexity bin without `hint_bin`. No GBDT, no `TRAINED_PATH` flip.

Commit `15e629b`. Report: `.scratch/scorer-pioneer-lift/task-04-fit-report.md`.
