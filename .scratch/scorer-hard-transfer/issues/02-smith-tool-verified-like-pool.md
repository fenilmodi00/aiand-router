# 02 — Real SWE-smith verified-like train/cal pool

**What to build:** Unpaid pool from real SWE-smith tool trajectories as primary bootstrap dump: stratum-sampled (bin × phase family × tools), verified-like prefers short + hard/frontier + tools/JSON, collision-filter vs frozen eval, BFCL ≤ 15% of n, optional SWE-Gym / R2E as extra only. Hard-check metadata (expected / schema / flashlight tests) is copied when present — not invented. Dump resolved is never y. Refuses an empty mix. Not the frozen Verified dump as the train pool. Preserve: --smith must be real SWE-smith tool trajectories (not synthetic train-queries tagged as smith); do not invent json_schema from the word “json”.

**Blocked by:** None — can start immediately

**Status:** resolved

- [x] Primary source is SWE-smith tool traj; synthetic train-queries cannot masquerade as smith
- [x] Hard checks are copied from dump fields when present; no invented schema from the word “json”; no fake status contract
- [x] Collision-filter vs eval; Verified / Lite / Terminal-Bench stay out of the train pool
- [x] BFCL ≤ 15% of n; empty verified-like mix is refused; unpaid; unit tests never spend

## Answer

`--smith` requires SWE-smith **tool** trajectories. `--tasks` joins SWE-smith **tasks** by `instance_id` (not as the train pool): copies `FAIL_TO_PASS` and builds gold-revert `expected` from the bug patch (deleted lines = correct code). Optional flashlight repair prompt from the buggy hunk (correct lines stay out of the prompt; `needs_tools=false`). Streaming JSONL ingest (no `read_text` OOM on the 3.8GB dump). `--verified-like` requires copied hard checks and refuses an empty label-usable mix; long non-flashlight tool trajs cannot dominate. Dump `resolved` / traj `patch` never written as y. No invented `json_schema` from the word “json”.

### Obtain dumps (unpaid)

```
# trajectories (already on disk as data/smith-tool.jsonl)
# tasks → compact checks (FAIL_TO_PASS + expected + optional flashlight prompt)
# HF: SWE-bench/SWE-smith train parquet → data/smith-task-checks.jsonl
```

### Mint (ticket 03 input)

```
python -m aiand_router.train pool --smith data/smith-tool.jsonl --tasks data/smith-task-checks.jsonl --eval data/gold-verified.jsonl --out data/pool-hard.jsonl --n 40 --verified-like
```

Files: `src/aiand_router/pool.py`, `src/aiand_router/train.py`, `tests/test_pool.py`, `tests/test_train.py` (gold haystack / fail-closed on names-only F2P).
