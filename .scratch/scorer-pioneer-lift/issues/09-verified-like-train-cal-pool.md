# 09 — Verified-like train/cal query pool

**What to build:** Pool machinery that samples a **train/cal** query set with verified-like difficulty (short, hard/frontier, tools/JSON, hard-check metadata) from allowed bootstrap dumps — not SWE-bench Verified / Lite / Terminal-Bench. Collision-filter vs `--eval`. Attach `expected` / JSON-schema / flashlight `tests` on **bootstrap** rows when present or inferable. Dump `resolved` is never y. This is the unpaid sampler for the hard-y probe; it does not mint gold cells.

**Blocked by:** None — can start immediately (uses issue 01 pool).

**Status:** resolved

- [x] `--verified-like` pool prefers short + hard/frontier (or JSON/tools-bearing) rows
- [x] Hard-check metadata (`expected` / `json_schema` / `pytest`/`tests`) is copied or attached on kept rows
- [x] Collision-filter vs `--eval` still runs; Verified/Lite/TB paths stay out of the train pool
- [x] Dump teacher `resolved` is unused as y
- [x] Unpaid (`AIAND_TRAIN` not required); unit tests never spend
- [x] Empty verified-like mix is not written

## Answer

`python -m aiand_router.train pool … --verified-like` keeps short prompts (≤62 tokens) that carry or infer `expected` / `json_schema` / pytest checks, still collision-filters vs `--eval`, and refuses an empty mix. Dump `resolved` is not written. Not the frozen Verified eval set. Paid gold is issue 12.

Files: `src/aiand_router/pool.py`, `src/aiand_router/train.py`, `tests/test_pool.py`.
