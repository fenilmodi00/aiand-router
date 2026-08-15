### Spec Compliance
- ✅ Unpaid `python -m aiand_router.train pool` skips paid opt-in when `__main__` calls `main()` with `argv=None`. `main` copies `sys.argv[1:]` before the pool check (`train.py:828-831`, `train.py:932-936`). Covering test: `test_pool_main_argv_none_reads_sys_argv` (`tests/test_pool.py:358-386`).
- ✅ Paid teacher/gold/fit still refuse without `AIAND_TRAIN=1` (`train.py:830-831`). Pool returns before provider/spend setup.
- ✅ Once past that gate, `pool` writes stratum-sampled JSONL (independent bin × phase-family × tools deficit margins) — `pool.py:14-24`, `pool.py:218-244`; not first-N / not all-trivial — `tests/test_pool.py:32-73`.
- ✅ SWE-smith is required primary ingest; missing `--smith` or zero parsed smith rows refuse and write nothing — `pool.py:272-276`, `tests/test_pool.py:231-267`.
- ✅ After collision-filter, smith must still contribute; gym/R2E cannot become the whole pool. Empty mix is not written — `pool.py:294-298`, `tests/test_pool.py:389-425`.
- ✅ BFCL capped at ≤ 15% of n before stratum pick — `pool.py:25`, `pool.py:252-254`, `tests/test_pool.py:80-125`.
- ✅ Verified / Lite / Terminal-Bench path names ingest as empty (eval-as-smith refuses); TB canary dropped; `FAIL_TO_PASS` / `PASS_TO_PASS` skipped — `pool.py:26-29`, `pool.py:137-138`, `pool.py:192-215`, `tests/test_pool.py:164-197`, `tests/test_pool.py:270-289`.
- ✅ `--eval` is required before write; collision-filter vs instance_id / normalized prompt — `pool.py:307-311`, `pool.py:196-206`, `pool.py:287-293`, `tests/test_pool.py:128-162`, `tests/test_pool.py:326-335`.
- ✅ Dump `resolved` / success / y never written — `pool.py:124-133`, `tests/test_pool.py:200-214`.
- ✅ Teacher/gold `--limit` uses `sample_stratum` instead of first-N — `train.py:98-106`, `tests/test_pool.py:338-350`.
- ✅ No live aiand in this ticket, `BUDGET_LIMIT_USD` default still 15 (`train.py:871`), no `TRAINED_PATH` flip, no hop/serve/scorer/fit, no second server — diff is `pool.py` + small `train.py` CLI/`_read_queries` only.
- ✅ Tests assert CLI/JSONL observables; unit path unpaid — `tests/test_pool.py`.
- ⚠️ Cannot verify from diff: real SWE-Gym / R2E / BFCL dump shapes (gym/R2E share `parse_smith_row`); CLI trusts `--smith` is a tool traj dump.

### Strengths
- Both prior re-review blockers are closed with operator-observable tests: `argv=None` now matches `parse_args`/`sys.argv`, and smith-primary is checked on the post-collision `kept` set (gym-only after a wiped smith dump refuses and writes nothing). Empty mix also refuses (`pool.py:297-298`).
- Source mix still matches the ticket on the happy path (smith primary, BFCL cap, gym/R2E shortfall-only) with CLI tests for the trivial-prefix trap, eval path blocks, FAIL_TO_PASS, unused dump `resolved`, required `--eval`, and gym-only refuse.
- Output schema stays gold/fit-ready prompts only. `_read_queries` keeps teacher/gold `--limit` on the same sampler.
- Fix 2 is tightly scoped: no hop, budget default, artifact stamp, or `TRAINED_PATH` change.

### Issues
#### Critical
- None.

#### Important
- None. The argv=None paid-refuse path and post-filter smith-primary gap from the prior re-review are closed in this diff.

#### Minor
- `--eval` on a missing path is still a silent empty collision set (`_read_jsonl` returns `[]` if `not path.exists()`, `pool.py:56-58`). The flag is required; a typo still ships an unfiltered pool.
- After collision-filter, `sample_stratum` can still omit surviving smith rows when `len(smith) < n` and extra/BFCL push the candidate pool above n (`pool.py:247-259`, `pool.py:294-296`). The written mix is not re-checked for `source=swe-smith`. Happy path with smith ≥ n cannot drop smith (BFCL cap). Not the prior gym-only-after-total-collision case.
- Stratum targets are independent bin/phase/tools margins (`pool.py:218-244`), not joint `(bin × phase × tools)` cells, and there is no occupied-cell floor. Adequate to beat first-N trivial piles.
- `hint_bin` is keyword + token heuristics (`pool.py:74-83`); `_FRONT_RE` includes `verified`. Train-only prior is fine; mix can be noisy.
- `test_pool_cli_stratum_samples_not_first_n_trivial` tools assert is still soft (`tools == {True, False} or True in tools`, `tests/test_pool.py:72`).
- `sample_stratum` re-sorts remaining each pick (`pool.py:237-238`) — O(n²), fine at n≈4k.
- `--smith` / `--eval` are still argparse-optional; requirement is runtime-only. `--eval` uses `nargs="*"`.

### Assessment
**Task quality:** Approved
**Reasoning:** Fix 2 closes both prior blockers: unpaid `python -m aiand_router.train pool` now skips paid refuse when `main()` sees `argv=None`, and smith-primary is enforced after collision-filter so a wiped smith dump plus gym/R2E cannot write. Remaining gaps are minors (independent margins, `--eval` typo path, heuristic `hint_bin`).
