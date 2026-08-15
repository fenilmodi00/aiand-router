# 01 — Stratum-sampled query pool

**What to build:** A train prompt pool an operator can feed into gold and fit, sampled so complexity bin × phase family × tools strata show up as coding-agent steps rather than a pile of trivial edits. SWE-smith `tool` trajectories are the primary source; BFCL is at most 15% of n; SWE-Gym / R2E may join as extra pool. SWE-bench Verified, Lite, and Terminal-Bench stay out of the train pool. Dump teacher `resolved` is not success gold and is never used as y.

**Blocked by:** None — can start immediately.

**Status:** resolved

- [x] Train pool is sampled across complexity bin × phase family × tools strata
- [x] Stratum mix is not all trivial edits
- [x] SWE-smith `tool` trajectories are the primary source
- [x] BFCL is ≤ 15% of n
- [x] SWE-Gym / R2E, if used, are extra pool only
- [x] SWE-bench Verified, Lite, and Terminal-Bench are absent from the train pool
- [x] Pool is collision-filtered
- [x] Dump teacher `resolved` is unused as y

## Answer

Unpaid `python -m aiand_router.train pool` writes a stratum-sampled JSONL (bin × phase family × tools) from local dumps. SWE-smith `tool` trajs are primary; BFCL ≤ 15% of n; gym/R2E extra only if smith cannot fill n. Verified/Lite/Terminal-Bench paths are skipped; `--eval` collision-filters instance_id/prompt; `FAIL_TO_PASS` rows and TB canaries are dropped. Dump `resolved` is never written as y. Teacher/gold `--limit` uses the same sampler instead of first-N.

Files: `src/aiand_router/pool.py`, `src/aiand_router/train.py`, `tests/test_pool.py`. Commit `9c53098`. Report: `.scratch/scorer-pioneer-lift/task-01-stratum-report.md`.
