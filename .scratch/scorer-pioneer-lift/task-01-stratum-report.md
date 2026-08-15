# Task 01 report: Stratum-sampled train query pool

**Status:** DONE_WITH_CONCERNS  
**Commit:** `9c53098` — Sample the train query pool by stratum so gold is not a first-N pile of trivial edits.

## What you implemented

Unpaid train-pool ingest + sampler the operator can run without `AIAND_TRAIN=1` and without a live provider:

```text
python -m aiand_router.train pool --smith smith-tool.jsonl [--bfcl bfcl.jsonl] [--gym gym.jsonl] [--r2e r2e.jsonl] [--eval verified.jsonl lite.jsonl tb.jsonl] --n 4000 --out datasets/train-pool.jsonl
```

Output JSONL rows are gold/fit-ready: `prompt`, `phase` (phase family), `hint_bin`, `needs_tools`, `source`, optional `instance_id`. Never `resolved` / `success` / `y`.

Behavior:

- **Stratum sample** on independent margins (bin 15/40/30/15, phase family edit/tool/plan/debug/discover/summarize, tools 75/25), greedy deficit fill — not first-N, not shuffle-then-truncate.
- **SWE-smith `tool` trajs** primary (`--smith`). One query per trajectory from the first user message; phase via `detect_phase` on tool calls; `hint_bin` is a query-only prior (keywords + tokens), not gold.
- **BFCL ≤ 15% of n** (`--bfcl`), tagged `source=bfcl`, phase `tool`.
- **SWE-Gym / R2E extra only** when smith cannot fill n.
- **Eval dumps absent:** path names matching Verified / Lite / Terminal-Bench ingest as empty; TB canary string dropped; SWE-bench-shaped `FAIL_TO_PASS` / `PASS_TO_PASS` rows skipped.
- **Collision-filter:** `--eval` JSONL instance_id / task_id / normalized problem text vs pool prompts.
- **Dump `resolved` unused as y** — never copied onto output.
- **Teacher/gold `--limit`:** `_read_queries` loads the file then `sample_stratum` instead of first-N.

Did **not**: download dumps, call live aiand, flip `TRAINED_PATH`, change `BUDGET_LIMIT_USD` (stays 15), re-run gold/silver/fit, add Pioneer dashboard, add deps.

## TDD evidence

### RED — pool CLI missing / treated as paid train

```text
python -m pytest tests/test_pool.py::test_pool_cli_stratum_samples_not_first_n_trivial -q --tb=short
F
assert code == 0
E   assert 2 == 0
refusing: set AIAND_TRAIN=1 to run paid teacher/gold/fit. Not for CI.
```

Expected miss: no `pool` subcommand; opt-in refuse.

### GREEN — unpaid pool writes mixed JSONL (then the mixer gap)

After adding `pool` + ingest, that test passed once. Strengthening the fixture to 400 leading trivials + 6 non-trivial exposed shuffle-truncate (still first-N in spirit):

```text
python -m pytest tests/test_pool.py::test_pool_cli_stratum_samples_not_first_n_trivial -q --tb=short
F
assert bins != {"trivial"}
E   AssertionError: assert {'trivial'} != {'trivial'}
pool n=20 -> ...\pool.jsonl
```

Expected miss: `mix_sources` took shuffled first-n smith **before** stratum sample, so a trivial-heavy dump stayed all-trivial.

Fix: cap BFCL in the candidate set, keep full smith (gym/r2e only if smith < n), **then** `sample_stratum`.

```text
python -m pytest tests/test_pool.py::test_pool_cli_stratum_samples_not_first_n_trivial -q --tb=short
.  1 passed
```

### RED — eval-shaped FAIL_TO_PASS rows leaked

```text
python -m pytest tests/test_pool.py::test_pool_drops_fail_to_pass_eval_shaped_rows -q --tb=short
F
assert {'eval-shaped', 'ok-traj'} == {'ok-traj'}
```

Expected miss: parser treated SWE-bench task rows as smith trajs.

Fix: `parse_smith_row` returns [] when `FAIL_TO_PASS` / `PASS_TO_PASS` present.

```text
python -m pytest tests/test_pool.py -q
.........  9 passed
```

## Tests run and results

| Command | Result |
| --- | --- |
| `python -m pytest tests/test_pool.py -q` | **9 passed** |
| `python -m pytest tests/test_pool.py tests/test_train.py -q` | **28 passed** (1 unrelated Starlette/httpx warning) |
| `python -m pytest tests/ -q --tb=line` | **132 passed, 7 failed** |

The 7 failures are pre-existing `tests/test_gateway.py` `KeyError: 'x-router-reason'`, accepted out of scope for this spec (`gateway-reason-dropped.md`). No new failures in pool/train/replay/hop.

Fixture-only; no live provider; no dump downloads.

## Files changed

| File | Role |
| --- | --- |
| `src/aiand_router/pool.py` | ingest, collision-filter, source mix, stratum sampler, JSONL writer |
| `src/aiand_router/train.py` | unpaid `pool` subcommand; `_read_queries` stratum-samples `--limit` |
| `tests/test_pool.py` | CLI/JSONL seams: mix, BFCL cap, collision, eval absent, resolved unused, gym extra, tools present/absent |

## Commits

`9c53098` Sample the train query pool by stratum so gold is not a first-N pile of trivial edits.

Not pushed.

## Self-review / concerns

1. **`hint_bin` is a heuristic prior** (keywords + token length), not a teacher label. Gold still has to run; this ticket only builds the query pool. A dump of uniformly long “rename” prompts could still look non-trivial on length alone, or short hard bugs could look trivial.
2. **One query per trajectory**, not every tool turn. Ponytail default; if gold still looks like single-issue statements rather than coding-agent steps, split turns next.
3. **Occupied-stratum floor ≥ 20** from the production sparse-train grill is not applied. Fine for fixture n; for operator `--n 4000` empty cells stay empty and small occupied cells are not forced to 20.
4. **Collision-filter needs `--eval` JSONL** (or eval-like filenames / `FAIL_TO_PASS`). A smith dump whose `instance_id`s overlap Verified will leak if the operator omits `--eval` and the rows look like trajs.
5. **Gym/R2E share the smith parser.** Real OpenHands dumps may need a richer message walk; fixtures cover the extra-only mix rule.
6. **Full-suite 7 gateway failures** are unchanged and out of scope.

skipped: live dump download, per-turn trajectory explosion, occupied-floor 20, README, synthetic query regen. Add when an operator has local smith/BFCL JSONL and wants n=4000 gold.

## Fix — Important review findings (eval required, smith primary)

Operator contract: refuse to write a pool unless `--eval` is provided (collision-filter always runs) and `--smith` contributes the primary set. Gym/R2E stay extra-only; gym-only is refused. Did not touch Minors (independent margins, hint_bin, soft tools assert, Starlette, O(n²) sort).

### RED — pool without `--eval` still wrote

```text
python -m pytest tests/test_pool.py::test_pool_without_eval_exits_nonzero_and_writes_nothing -q --tb=short
F                                                                        [100%]
================================== FAILURES ===================================
___________ test_pool_without_eval_exits_nonzero_and_writes_nothing ___________
tests\test_pool.py:288: in test_pool_without_eval_exits_nonzero_and_writes_nothing
    assert code != 0
E   assert 0 != 0
---------------------------- Captured stdout call -----------------------------
pool n=1 -> C:\Users\nasri\AppData\Local\Temp\pytest-of-nasri\pytest-132\test_pool_without_eval_exits_n0\pool.jsonl
=========================== short test summary info ===========================
FAILED tests/test_pool.py::test_pool_without_eval_exits_nonzero_and_writes_nothing
1 failed in 0.70s
```

Expected miss: omitted `--eval` returned 0 and wrote JSONL.

### GREEN — `--eval` required before write

`run_pool` returns 2 and skips `write_pool` when eval paths are empty. Existing CLI tests pass an eval JSONL (empty of collisions is allowed).

```text
python -m pytest tests/test_pool.py::test_pool_without_eval_exits_nonzero_and_writes_nothing -q --tb=short
.                                                                        [100%]
1 passed in 0.43s
```

### RED — gym-only (no/empty smith) became the whole pool

```text
python -m pytest tests/test_pool.py::test_pool_gym_only_without_smith_is_refused -q --tb=short
F                                                                        [100%]
================================== FAILURES ===================================
_________________ test_pool_gym_only_without_smith_is_refused _________________
tests\test_pool.py:307: in test_pool_gym_only_without_smith_is_refused
    assert no_smith != 0
E   assert 0 != 0
---------------------------- Captured stdout call -----------------------------
pool n=10 -> C:\Users\nasri\AppData\Local\Temp\pytest-of-nasri\pytest-134\test_pool_gym_only_without_smi0\pool.jsonl
=========================== short test summary info ===========================
FAILED tests/test_pool.py::test_pool_gym_only_without_smith_is_refused
1 failed in 0.57s
```

Expected miss: missing smith treated gym as the fill set.

### GREEN — smith must contribute after parse

`build_pool` refuses when `--smith` is missing or ingest/parse yields zero rows. Eval-named dumps passed as `--smith` now refuse (empty ingest) instead of writing `[]`.

```text
python -m pytest tests/test_pool.py::test_pool_gym_only_without_smith_is_refused -q --tb=short
.                                                                        [100%]
1 passed
```

### Covering tests (re-run for reviewers)

```text
python -m pytest tests/test_pool.py -q --tb=short
...........                                                              [100%]
11 passed in 0.83s
```

**Result:** 11 passed. `tests/test_train.py` not re-run (gold/`--limit` untouched). Unpaid; no `AIAND_TRAIN=1`; no live provider.

Commit: `1c53479` Refuse to write a train pool unless --eval collision-filter and --smith primary are present. Not pushed.

## Fix 2 — Critical argv=None paid refuse + Important smith-after-filter

Unpaid `python -m aiand_router.train pool` must skip the paid opt-in when `__main__` calls `main()` with `argv=None` (read `sys.argv[1:]`, same as `parse_args`). After collision-filter, smith must still contribute rows; gym/R2E stay extra-only and cannot become the whole pool. Empty mixes are not written. Paid teacher/gold/fit refuse is unchanged. Did not touch Minors, `TRAINED_PATH`, or `BUDGET_LIMIT_USD`.

### RED — `main()` with `argv=None` still refused unpaid pool

```text
python -m pytest tests/test_pool.py::test_pool_main_argv_none_reads_sys_argv tests/test_pool.py::test_pool_refuses_when_smith_all_collide_even_if_gym_present -q --tb=short
FF                                                                       [100%]
================================== FAILURES ===================================
___________________ test_pool_main_argv_none_reads_sys_argv ___________________
tests\test_pool.py:436: in test_pool_main_argv_none_reads_sys_argv
    assert code == 0
E   assert 2 == 0
---------------------------- Captured stderr call -----------------------------
refusing: set AIAND_TRAIN=1 to run paid teacher/gold/fit. Not for CI.
________ test_pool_refuses_when_smith_all_collide_even_if_gym_present _________
tests\test_pool.py:478: in test_pool_refuses_when_smith_all_collide_even_if_gym_present
    assert code != 0
E   assert 0 != 0
---------------------------- Captured stdout call -----------------------------
pool n=1 -> C:\Users\nasri\AppData\Local\Temp\pytest-of-nasri\pytest-137\test_pool_refuses_when_smith_a0\pool.jsonl
=========================== short test summary info ===========================
FAILED tests/test_pool.py::test_pool_main_argv_none_reads_sys_argv - assert 2...
FAILED tests/test_pool.py::test_pool_refuses_when_smith_all_collide_even_if_gym_present
2 failed in 0.43s
```

Expected miss: `is_pool` used the passed `argv` only, so `argv=None` hit `_refuse()`. Collision-filtered smith + gym wrote a gym-only pool (`n=1`, exit 0).

### GREEN — sys.argv pool is unpaid; filtered-empty smith refuses

`main()` copies `sys.argv[1:]` when `argv is None`. `build_pool` raises after collision-filter if no `swe-smith` rows remain (and if the mix is empty). Gym/R2E still fill n only when smith survives.

```text
python -m pytest tests/test_pool.py::test_pool_main_argv_none_reads_sys_argv tests/test_pool.py::test_pool_refuses_when_smith_all_collide_even_if_gym_present -q --tb=short
..                                                                       [100%]
2 passed in 0.24s
```

Paid refuse still holds: `tests/test_train.py::test_train_refuses_without_opt_in` and `test_gold_refuses_without_opt_in` — 2 passed.

### Covering tests (re-run for reviewers)

```text
python -m pytest tests/test_pool.py -q --tb=short
.............                                                            [100%]
13 passed in 0.44s
```

**Result:** 13 passed. Unpaid; no `AIAND_TRAIN=1`; no live provider.

Commit: `5be80c9` Detect pool from sys.argv so unpaid python -m aiand_router.train pool skips paid refuse; keep smith primary after collision-filter. Not pushed.
