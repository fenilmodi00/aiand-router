# 05 — Logistic Rec A refit on hard gold

**What to build:** Rec A logistic Scorer the hop can load while still serving shadow: silver only on unobserved cells (Motif→GLM; parse-fail always escalates); per-model intercepts from gold marginals + query features; Platt/isotonic only on the hard dense-cal slice. Artifact stays not_spec_floors. No GBDT. No Rec B / live embed. No TRAINED_PATH flip. Ids without a dense gold slice stay rules-only for live P(success).

**Blocked by:** 04 — Scale sparse + dense hard-cal gold

**Status:** done (shadow artifact) — logistic refit on Mix1 + merged hard dense-cal; cal-brier Platt grid; no path flip.

- [x] Fit default is logistic (no --gbdt); silver never used for Platt / gate / threshold
- [x] Calibrator fit only on the hard dense-cal slice; train/cal overlap refused when configured
- [x] Artifact not_spec_floors; live hop stays path=shadow; apply_replay_gate does not auto-flip
- [x] HTTP hop on FakeProvider stays default shadow; unit tests never spend / never encode production floors

## Answer

```
$env:AIAND_TRAIN="1"
python -m aiand_router.train fit --gold data/gold-sparse-hard-mix1.jsonl --cal data/gold-dense-hard-cal-merged.jsonl --out data/scorer-hard-logistic.json
# then cal-only Platt grid → platt {a: 1.2, b: -0.2}
```

Artifact: `data/scorer-hard-logistic.json` — `not_spec_floors=true`, `n_cal=664`, `n_silver=0`. Do **not** set `TRAINED_PATH=trained` until issue 06 green.
