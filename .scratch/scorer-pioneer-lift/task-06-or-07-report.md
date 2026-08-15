# Task 06/07 report: operator replay then one Rec A lift

**Status:** DONE_WITH_CONCERNS  
**Decision:** Issue **06** (gate failed). Issue 07 not taken.  
**Commit:** `cb7a9bf` — Add optional GBDT plus post-hoc Platt so a failed replay gate can take one Rec A lift without Rec B.

## Command / paths

Holdout: `data/gold-verified.jsonl` (89 prompts). Artifact: `data/scorer.json`. Models: `config/models.yaml`.

```
python -m aiand_router.replay_report --gold data/gold-verified.jsonl --artifact data/scorer.json --models config/models.yaml
```

Toy fixture was not the operator gate. Full stdout: `operator-replay-run.md`.

## Gate result (logistic, run 1)

**FAIL** (`replay_gate_pass=false`, `path=shadow`, `not_spec_floors=true`).

- AUC 0.295 (need ≥ 0.65) fail
- P-spread 0.188 (need ≥ 0.10) pass
- Brier skill −0.317 (need > 0) fail — spec trigger for GBDT
- dual ECE 0.154 / 0.182 (need ≤ 0.03) fail
- trained success ≥ rules − 1 pp pass
- rules cost delta +4.74e-5 (need < 0) fail
- trained ≠ always-cheapest pass

## Decision

Issue **06**: one GBDT + post-hoc calibrator (not larger n: no unused labeled gold without live spend; P-spread already cleared). Rec B closed. Live embed closed. Serve stays shadow. Artifact stays `not_spec_floors`. Issue **07** left needs-info.

## What shipped (06)

- `fit --gbdt`: per-id stump GBDT (stdlib, 24 trees) + existing cal-gold Platt. Logistic remains default.
- Serve prefers `gbdt` when present; gold-intercept omit still applies; no embed/bilinear.
- Default `TRAINED_PATH` still shadow. `apply_replay_gate` still never auto-flips.

Operator refit (holdout unused):

```
python -m aiand_router.train fit --gold data/gold-sparse-400.jsonl --cal data/gold-dense-100.jsonl --silver data/silver.jsonl --out data/scorer.json --gbdt
```

Replay re-run: still **FAIL** (AUC 0.261, Brier skill −3.80, ECE 0.525, cost delta 0, trained = always-cheapest). Path still shadow. P-spread rose to 0.388.

## TDD

RED: `--gbdt` unrecognized; `score_eligible` ignored trees (P=0.5); hop `trained-would` was table `dear/ok`.

GREEN: `tests/test_train.py::test_fit_gbdt_*`, `test_scorer.py::test_score_eligible_uses_gbdt_when_present`, `test_trained_hop.py::test_shadow_loads_gbdt_and_does_not_auto_flip`.

Focused: `test_train.py` + `test_scorer.py` + `test_trained_hop.py` + `test_replay_report.py` → **102 passed**.

## Concerns

1. GBDT did not clear the gate; Brier/ECE got worse (dense cal y is easier than verified holdout). One lift only — no second model, no Rec B.
2. Pre-06 logistic artifact had leaked verified into `gold-all` fit. Run 2 used the clean split.
3. 7 `test_gateway.py` `x-router-reason` failures remain out of scope.
4. Production Verified n≥300 still later. No `TRAINED_PATH=trained` flip.
