# 05 — Holdout replay gate

**What to build:** An offline replay gate over frozen holdout success gold + the current Scorer artifact + the rules picker, with no live aiand. The gold input (`--gold`) is the holdout. The report compares rules vs trained vs oracle vs always-Flash vs always-strong on success rate and list-price cost, plus disagreement, rank AUC, mean P-spread, Brier and Brier skill, and dual ECE on selected-hop calibrated P(success). Cost vs rules is rules cost delta. This cycle’s bars (not SWE-bench Verified promotion): AUC ≥ 0.65; P-spread ≥ 0.10; Brier skill > 0; dual ECE ≤ 0.03; trained success ≥ rules − 1 pp; rules cost delta < 0; trained ≠ always-cheapest-eligible. Failing any bar keeps shadow and `not_spec_floors`. Unit tests must not invoke production floors.

**Blocked by:** 04 — Silver + Rec A fit

**Status:** resolved

- [x] Replay is offline over frozen holdout gold JSONL + current Scorer artifact + rules picker; no live aiand
- [x] `--gold` is the holdout
- [x] Report includes rules vs trained vs oracle vs always-Flash vs always-strong (success rate + list-price cost)
- [x] Report includes disagreement, rank AUC, mean P-spread, Brier, Brier skill, and dual ECE on selected-hop calibrated P(success)
- [x] Cost vs rules is reported as rules cost delta
- [x] Holdout rank AUC ≥ 0.65
- [x] Mean P-spread ≥ 0.10
- [x] Brier skill > 0
- [x] Dual ECE ≤ 0.03 on selected-hop calibrated P(success)
- [x] Trained success ≥ rules − 1 pp
- [x] Rules cost delta < 0
- [x] Trained ≠ always-cheapest-eligible
- [x] Failing any bar keeps shadow and `not_spec_floors`
- [x] Unit tests do not invoke production floors

## Answer

Task 1 already shipped the offline replay CLI over holdout `--gold`. This ticket filled the gate seam: `replay_gate_pass` now compares trained ≠ always-cheapest-eligible (not only always-Flash); `apply_replay_gate` stamps `path=shadow` and `not_spec_floors=true` whether bars pass or fail (no auto-flip, no Verified stamp); CLI prints grepable `path=shadow` / `not_spec_floors` / `replay_gate_pass`. Numeric bars stay operator-side; the toy fixture is allowed to fail them. Unit tests call `assert_not_production_floors` and never spend.

Commit `40a64cd`. Report: `.scratch/scorer-pioneer-lift/task-05-replay-report.md`.
