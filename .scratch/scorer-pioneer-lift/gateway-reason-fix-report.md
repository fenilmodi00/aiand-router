# Gateway `x-router-reason` fix report

## Status

**Fixed.** Shadow hops again emit `X-Router-Reason`. Trained hops still omit it.

## Root cause

Default `TRAINED_PATH` is `shadow`. With a live `data/scorer.json`, `apply_trained_path` sets `decision.path = "shadow"`, and `_router_headers` only emitted the machine-path headers — so gateway tests that still assert the rules Decision-contract `x-router-reason` hit `KeyError`.

## Fix

One branch in `_router_headers` (`src/aiand_router/app.py`): when `path == "shadow"`, set `X-Router-Reason` from `decision.reason`. Did not flip `TRAINED_PATH`, did not change `apply_trained_path`, did not rewrite the gateway.

## TDD

1. Red: `test_summarize_phase_forwards_flash_on_pioneer_score` → `KeyError: 'x-router-reason'`
2. Green: same test after the one-line header restore
3. Suite slice: 7 formerly failing gateway tests + `tests/test_trained_hop.py` + `tests/test_scorer.py` → **43 passed**

## Commit

`Restore x-router-reason on shadow hops so gateway Decision-contract seams stay green.`

## Skipped

- Changing default hop to `off`
- Emitting reason on `trained` (would break `test_trained_serves_cheapest_above_bar`)
- Scorer / TRAINED_PATH policy changes
