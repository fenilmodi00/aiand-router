# tests — Pytest Suite

**Generated:** 2026-08-21
**Commit:** 492a192
**Branch:** v0

## OVERVIEW

~400 tests across 22 `test_*.py` modules. Single framework: pytest, no coverage plugin.

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Gateway / headers | `test_gateway.py` (49 tests) | `TestClient` + `FakeProvider`, cascade config |
| Pool stratum | `test_pool.py` (51 tests) | Largest suite — `build_pool` sampling |
| Training fit | `test_train.py` / `test_scorer.py` | Teacher→gold, `score_eligible` unit tests |
| Isolation | `conftest.py` | `autouse` fixture forces `TRAINED_PATH=shadow` |
| Fixtures | `fixtures/` | Checked-in JSON/JSONL — pool_spec, lite_comparison, verified_instances |
| Preflight gates | `test_*_preflight.py` | Load `scripts/*.py` via `importlib.util.spec_from_file_location` |

## CONVENTIONS

- `pytest.ini`: `pythonpath=src`, `testpaths=tests`. Run with `python -m pytest` from repo root.
- `conftest.py` clamps `TRAINED_PATH=shadow` so `.env` cannot flip live path in tests. Modules may override (e.g. `test_gateway.py` pins `off`).
- Preflight tests import scripts without subprocess: `spec_from_file_location` → `build_report()`.
- `FakeProvider` / `httpx.MockTransport` mock aiand upstream — no live network in CI.
- `pytest.skip` when optional data (`data/dump_cache/*.jsonl`, `data/verified_ids_scaffold.json`) missing.

## ANTI-PATTERNS

- Never set `TRAINED_PATH=trained` in tests — promotion-gate owned only.
- Never add `pytest-cov` flags without installing — plugin not in `requirements.txt`.
- Never treat `demo/seed/test_*.py` as repo tests — they are seed task targets for `flashlight`.
