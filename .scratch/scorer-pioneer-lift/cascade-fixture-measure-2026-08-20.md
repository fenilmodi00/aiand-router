# Cascade fixture measurement (unpaid, default-off) — 2026-08-20

Config on disk unchanged: `cascade_lane.enabled: false`. Measurement enabled **in-memory only**.

## Setup

- Artifact: `data/scorer-hard-logistic.json`
- Models: ship `config/models.yaml` (pair Flash cheap / Pro strong)
- Holdout prompts: unique `data/gold-verified.jsonl` (n=89)
- Phase: `edit`, effort `medium` (ship threshold/max_regret)

## Result

| Metric | Value |
| --- | ---: |
| cheap_redirect | 0 |
| strong_pass_through | 89 |
| cheap_redirect_rate | **0.0** |

JSON: `cascade-fixture-measure-2026-08-20.json`.

## Interpretation (superseded diagnosis)

Earlier wording blamed max_regret. **Correct root cause (knob sweep):** Flash P≈0.027–0.038 is **below ship threshold 0.10 on all 89**; Pro is even lower (Flash > Pro always), so `max_regret` never fires. Phase allowlist drops discover/summarize (70/89 eligible) but is not why allowlisted rows stay pass-through.

Follow-up: `.scratch/scorer-pioneer-lift/cascade-knob-sweep-2026-08-20.md` — in-memory soft `t≤0.038` yields `cheap_redirect>0`; still **not** FireRouter parity. Leave default-off.
