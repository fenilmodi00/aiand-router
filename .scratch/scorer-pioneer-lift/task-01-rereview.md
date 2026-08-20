### Spec Compliance
- ❌ Unpaid operator CLI `python -m aiand_router.train pool` still refuses without `AIAND_TRAIN=1`. `__main__` calls `main()` with `argv=None`; `is_pool` is then false (`train.py:828-831`, `train.py:932-936`). Tests pass only because they inject `main(["pool", ...])`. Focused check with `AIAND_TRAIN` unset and `argv=None`: exit 2, `refusing: set AIAND_TRAIN=1 to run paid teacher/gold/fit`.
- ✅ Once past that gate, `pool` writes stratum-sampled JSONL (independent bin × phase-family × tools deficit margins) — `pool.py:14-24`, `pool.py:218-244`; not first-N / not all-trivial — `tests/test_pool.py:32-73`
- ✅ SWE-smith is the required primary ingest; missing `--smith` or zero parsed smith rows refuse and write nothing — `pool.py:272-276`, `tests/test_pool.py:231-267`
- ⚠️ After collision-filter, smith can drop to zero while gym/R2E remain; `mix_sources` then treats extra as the fill set — `pool.py:247-259`, `pool.py:277-294`. Smith-primary is enforced on ingest, not on the written mix.
- ✅ BFCL capped at ≤ 15% of n before stratum pick — `pool.py:25`, `pool.py:252-254`, `tests/test_pool.py:80-125`
- ✅ Verified / Lite / Terminal-Bench path names ingest as empty (eval-as-smith now refuses); TB canary dropped; `FAIL_TO_PASS` / `PASS_TO_PASS` skipped — `pool.py:26-29`, `pool.py:137-138`, `pool.py:192-215`, `tests/test_pool.py:164-197`, `tests/test_pool.py:270-289`
- ✅ `--eval` is required before write; collision-filter vs instance_id / normalized prompt — `pool.py:303-306`, `pool.py:196-206`, `pool.py:287-293`, `tests/test_pool.py:128-162`, `tests/test_pool.py:326-335`
- ✅ Dump `resolved` / success / y never written — `pool.py:124-133`, `tests/test_pool.py:200-214`
- ✅ Teacher/gold `--limit` uses `sample_stratum` instead of first-N — `train.py:98-106`, `tests/test_pool.py:338-350`
- ✅ No live aiand in this ticket, `BUDGET_LIMIT_USD` default still 15, no `TRAINED_PATH` flip, no hop/serve/scorer/fit, no second server — diff is `pool.py` + small `train.py` CLI/`_read_queries` only
- ✅ Tests assert CLI/JSONL observables; unit path unpaid when argv is injected — `tests/test_pool.py`
- ⚠️ Cannot verify from diff: real SWE-Gym / R2E / BFCL dump shapes (gym/R2E share `parse_smith_row`); CLI trusts `--smith` is a tool traj dump

### Strengths
- Previous Important operator contracts are mostly closed: omitted `--eval` returns 2 and writes nothing; gym-only / empty smith is refused.
- Source mix still matches the ticket on the happy path (smith primary, BFCL cap, gym/R2E shortfall-only) with CLI tests for the trivial-prefix trap, eval path blocks, FAIL_TO_PASS, and unused dump `resolved`.
- Output schema stays gold/fit-ready prompts only. `_read_queries` keeps teacher/gold `--limit` on the same sampler.
- New tests (`test_pool_without_eval_exits_nonzero_and_writes_nothing`, `test_pool_gym_only_without_smith_is_refused`) assert the refuse-and-no-write seam.

### Issues
#### Critical
- Unpaid `python -m aiand_router.train pool` does not bypass opt-in. `main()` only treats the command as pool when the *passed* `argv` starts with `"pool"` (`train.py:828-831`). The module entry calls `main()` with no argv (`train.py:936`), so `is_pool` is false and `_refuse()` runs unless `AIAND_TRAIN=1` is already set. `parse_args(None)` would have read `sys.argv` correctly; the unpaid check does not. Covering tests never hit this path. Ticket answer and report claim the unpaid module command writes; it does not.

#### Important
- Smith-primary is still ingest-only. `build_pool` requires non-empty smith parse, then collision-filters, then `mix_sources` (`pool.py:272-294`). If every smith row hits `--eval` and `--gym`/`--r2e` remain, `len(smith) < n` and extra becomes the whole written pool — the same “extra-only can be the whole pool” gap, now behind a non-empty ingest. Also writes `n=0` with exit 0 when everything is filtered and no extra/BFCL remains.

#### Minor
- `--eval` on a missing path is a silent empty collision set (`_read_jsonl` returns `[]` if `not path.exists()`, `pool.py:56-58`). Flag is required; a typo still ships an unfiltered pool.
- Stratum targets are independent bin/phase/tools margins (`pool.py:218-244`), not joint `(bin × phase × tools)` cells, and there is no occupied-cell floor. Adequate to beat first-N trivial piles.
- `hint_bin` is keyword + token heuristics (`pool.py:74-83`); `_FRONT_RE` includes `verified`. Train-only prior is fine; mix can be noisy.
- `test_pool_cli_stratum_samples_not_first_n_trivial` tools assert is still soft (`tools == {True, False} or True in tools`, `tests/test_pool.py:72`).
- `sample_stratum` re-sorts remaining each pick (`pool.py:237-238`) — O(n²), fine at n≈4k.
- `--smith` / `--eval` are still argparse-optional; requirement is runtime-only. `--eval` uses `nargs="*"`.

### Assessment
**Task quality:** Needs fixes
**Reasoning:** The two prior Important footguns are mostly fixed, but the documented unpaid `python -m aiand_router.train pool` command still hits the paid refuse when `main()` sees `argv=None`, and tests do not cover that entry. Smith-primary is also not checked after collision-filter, so a fully filtered smith dump plus gym/R2E can still write an extra-only pool.
