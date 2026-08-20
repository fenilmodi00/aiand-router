# 06 — Refit if the gate fails

**What to build:** If the replay gate fails, one more lift — either a larger train n or one GBDT + post-hoc calibrator, not both as a zoo — then replay is re-run. Rec B and live embed stay closed. Serve stays shadow and the artifact stays `not_spec_floors`.

**Blocked by:** 05 — Holdout replay gate (only if the gate fails)

**Status:** resolved

- [x] Taken only when the replay gate fails
- [x] One more train n and/or one GBDT + post-hoc calibrator — not both as a zoo
- [x] Rec B stays closed
- [x] Live embed stays closed
- [x] Replay is re-run after the refit
- [x] Serve stays shadow
- [x] Artifact stays `not_spec_floors`

## Answer

Operator replay on `data/gold-verified.jsonl` + `data/scorer.json` **failed** (AUC 0.295, Brier skill −0.317, dual ECE > 0.03, cost delta > 0). Took **one GBDT + post-hoc Platt** (`fit --gbdt`), not larger n and not Rec B. Refit on sparse-400 / dense-100 / silver; verified holdout unused. Replay re-run still fails (AUC 0.261, Brier skill −3.80); `path=shadow`, `not_spec_floors=true`. No live embed. Issue 07 not taken.

Report: `.scratch/scorer-pioneer-lift/task-06-or-07-report.md`. Evidence: `operator-replay-run.md`.
