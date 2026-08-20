# 02 — Sparse success-gold run

**What to build:** Sparse gold on the train pool: Flash and the measured trio actually run when eligible, so each observed cell is gateway-measurable success gold. K3 is never a gold cell. Missing cells stay missing — a budget skip or 429 is unobserved, not failure. When a query carries verified metadata (`tests_passed`, expected, JSON/schema), that overrides weak proxies such as a tool-call check. The operator can read gold JSONL with `success` / `success_tier`. Paid calls are cache-first, live gold is opt-in, the code default budget stays 15 unless the operator raises it, and runs stay concurrent within the cap.

**Blocked by:** 01 — Stratum-sampled query pool

**Status:** resolved

- [x] Flash and the measured trio actually run when eligible
- [x] No K3 gold cells
- [x] Unobserved cells stay missing, not labeled 0; budget skip and 429 are not failure
- [x] Verified metadata (`tests_passed`, expected, JSON/schema) overrides weak proxies, including a tool-call proxy
- [x] Operator-visible gold JSONL includes `success` / `success_tier`
- [x] Paid calls are cache-first
- [x] Live gold is opt-in via env
- [x] Code default budget is still 15 unless the operator raises it
- [x] Runs are concurrent within the cap

## Answer

Sparse gold runs Flash + measured trio when eligible (enabled, tools if required); K3 never. Observed cells are success gold (`success` / `success_tier`); budget skip and 429 stay unobserved. Verified `expected` / JSON-schema / pytest override tool-call proxies. Dump `resolved` is not y. Cache-first, `AIAND_TRAIN=1` opt-in, `BUDGET_LIMIT_USD` default 15, concurrent within `TRAIN_CONCURRENCY`.

Files: `src/aiand_router/train.py`, `tests/test_train.py`. Commit `ab06f39`. Report: `.scratch/scorer-pioneer-lift/task-02-gold-report.md`.
