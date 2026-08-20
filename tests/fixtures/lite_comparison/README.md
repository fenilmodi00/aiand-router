# Synthetic Lite dual-policy comparison fixture

**Label:** `bounded_check_only` · `label_type=harness_proxy` · `comparison_mode=fixture_replay`

This is a **checked-in unpaid synthetic** dual-policy corpus for `aiand_router.lite_runner`.
Each row carries shared `module` / `tests` plus `policies.rules` / `policies.trained` patches so the harness-proxy verifier can diverge offline.

## What this proves

- Offline comparison-mode plumbing works end-to-end without HTTP or API credits.
- Rules vs trained resolve rates can be measured on a tiny synthetic slice.

## What this does **not** prove

- Not SWE-bench Lite / Verified session gold
- Not production parity
- Not a promotion gate (`n` << session-gold floor)
- Patches are hand-authored fixtures, not model/gateway outputs

## Run

```powershell
$env:PYTHONPATH='src'
python scripts/run_lite_comparison.py
```

Defaults:

- fixture: `tests/fixtures/lite_comparison/fixture.json`
- results JSONL: `tests/fixtures/lite_comparison/results.jsonl`
- markdown report: `tests/fixtures/lite_comparison/report.md`
