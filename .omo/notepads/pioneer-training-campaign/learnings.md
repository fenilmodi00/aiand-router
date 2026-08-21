# Learnings

## 2026-08-21 Session start
- Branch: evel; tree clean except .omo/ plan files.
- data/spend.txt = 8.16 at Phase A entry (spend_before_A). Single float line - never add comments/headers.
- data/split_manifest.json ALREADY EXISTS (68KB) from prior campaign - Task 1 must inspect/conform/extend, not blind-overwrite.
- Prior-campaign artifacts exist: queries_spec.jsonl, silver.jsonl, gold_sparse.jsonl, gold_dense.jsonl, scorer.json, bounded_gate_report.md.
- Windows/pwsh; use .venv\Scripts\python.exe if venv present else python; pytest.ini sets pythonpath=src, testpaths=tests.
- tests/conftest.py forces TRAINED_PATH=shadow.

## 2026-08-21 A1 split manifest + spend accounting pre-flight
- Inspected prior data/split_manifest.json: 68KB legacy schema `{"splits": {"promotion-holdout":300,"tune":300,"dense/cal":300,"sparse-train":3139},"sizes","total":4039,"seed":0}` — deviations from required schema: no `prompt_hash`/`instance_id`/`assigned_at` rows, keyed by instance_id not prompt_hash, split names `tune` vs `threshold-tune` and `dense/cal` vs `dense-cal`, missing `teacher-silver` split entirely, no `metadata.spend_before_A`. No blind overwrite: preserved all 4039 valid instance_ids from data/queries_spec.jsonl, reconciled by regenerating 4039 rows keyed by `sha256(prompt)[:12]` matching `train.py:_prompt_of(_messages(q))`, reusing `sample_stratum(seed=0)` deterministic machinery. Old counts partly preserved (promo/tune/dense 300 each) then remainder split via sample_stratum ordering: teacher-silver 2139 / sparse-train 1000 for remaining 3139 (ensures C1 gate 3500+ reachable when pool grows; old sparse 3139 was unsplit).
- Writer added to src/aiand_router/pool.py: `MANIFEST_VALID_SPLITS`, `_prompt_hash`, `_manifest_prompt_of`, `load_split_manifest`, `_validate_manifest_rows`, `validate_split_manifest`, `build_split_manifest_rows`, `write_split_manifest`. Uses `sample_stratum(seed=0)` then slices `[promo 300, threshold-tune 300, dense-cal 300, teacher-silver remainder-1000, sparse-train 1000]` deterministically. Metadata block `{"spend_before_A":8.16,"generated_at":"2026-08-21","total":4039,"seed":0}`.
- Readers in src/aiand_router/train.py: added `MANIFEST_VALID_SPLITS`, `_prompt_hash`, `_load_manifest_map`, `_guard_manifest_for_queries` raising `ValueError("split_manifest_overlap: ...")` on absent hash, double-assigned hash (manifest dup or query dup), invalid split, missing metadata.spend_before_A. Wired into `run_teacher` (allowed={"teacher-silver"}) and `run_gold` (dense? {"dense-cal"} : {"sparse-train"}) before any spend/cap.
- Spend accounting: data/spend.txt untouched `8.16\r\n` single float line; `SpendLog.total()` parses one float (any other content -> 0.0 disables budget). `spend_before_A` stored only in manifest metadata; tranche logic `BUDGET_LIMIT_USD = spend_before + tranche_cap`.
- Verified train.py:_complete pre-call budget check present at `src/aiand_router/train.py:171` `if spend.total() >= spend.limit_usd: return {"status":429,...}` BEFORE `await provider.complete(body)` — no fix needed, reported location/behavior. Minimal comment header added, no new sampler invented.
- Tests: tests/test_split_manifest_a1.py 8 cases (hash parity, schema 4039 rows, valid splits 5, metadata spend, deterministic rerun seed=0, absent-id refusal, double-assignment manifest+query dup, allowed-split enforcement) — all green. Baseline characterization: _load_manifest_map returns 4039 disjoint entries.
- data/split_manifest.json regenerated via `write_split_manifest(rows from queries_spec.jsonl)` — gitignored (data/) so force-added; conforms exactly to required row schema and valid splits.

