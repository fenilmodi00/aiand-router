# 10 — Dual shadow eval (cost-meaningful bootstrap slice)

**What to build:** Keep `gold-verified` (or `--gold`) as eval-only. Add a second, disjoint bootstrap holdout path (`--cost-gold`) where rules can disagree with cheapest-eligible, so `rules_cost_delta` is a real comparison rather than H3’s structural zero. Replay both offline. Do not rewrite verified gate bars. Do not train on Verified/Lite/TB. Fixture-testable: a cost slice where `rules_ne_cheapest_rate > 0`.

**Blocked by:** None for the seam (paid bootstrap gold is issue 12).

**Status:** resolved

- [x] `--gold` stays the eval-only holdout (typically frozen verified)
- [x] `--cost-gold` is a separate bootstrap holdout, unused for fit
- [x] Report includes `rules_ne_cheapest_rate` so H3 is visible
- [x] Cost judgment can be read on the cost slice without changing verified bars
- [x] Top-level `replay_gate_pass` still comes from `--gold`; no fake pass
- [x] Failing bars keep `path=shadow` and `not_spec_floors`
- [x] Unit tests never spend / never invoke production floors

## Answer

`python -m aiand_router.replay_report --gold <eval> --cost-gold <bootstrap> --artifact …` keeps the gate on `--gold` (`path=shadow`, `not_spec_floors`). `rules_ne_cheapest_rate` is on every report. `cost_slice` is where `rules_cost_delta < 0` can be real. Bars on verified are unchanged. Paid bootstrap gold still needed (issue 12).

Files: `src/aiand_router/replay_report.py`, `tests/test_replay_report.py`.
