# Lite dual-policy comparison (synthetic)

**Verdict**: `bounded_check_only`

- Fixture: `tests/fixtures/lite_comparison/fixture.json`
- `label_type`: `harness_proxy`
- `comparison_mode`: `fixture_replay`
- n=10 (<< session-gold floor 300)

## Resolve rates (harness-proxy)

- rules: **3/10 (30.0%)**
- trained: **7/10 (70.0%)**
- trained − rules: **40.0 pp** (synthetic fixture delta only)

## Contingency

- both pass: 2
- both fail: 2
- rules only: 1
- trained only: 5

## Honesty

- `production_parity=false` — not SWE-bench Lite/Verified session gold.
- Patches are hand-authored dual-policy fixtures, not live gateway routes.
- Does **not** justify flipping `TRAINED_PATH`.
