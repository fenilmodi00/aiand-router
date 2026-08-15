### Spec Compliance
- ✅ Unpaid `pool` CLI writes stratum-sampled JSONL without `AIAND_TRAIN=1` — `train.py:821-824`, `train.py:827-835`, `train.py:855-856`
- ✅ Sample targets complexity bin × phase family × tools (independent deficit margins) — `pool.py:14-24`, `pool.py:169-196`
- ✅ Mix is not first-N / not all-trivial under a trivial-heavy smith dump — `tests/test_pool.py:32-62`; sampler after full smith candidate set — `pool.py:199-212`
- ✅ SWE-smith is primary source tag/path; gym/R2E only when `len(smith) < n` — `pool.py:199-212`, `tests/test_pool.py:190-236`
- ✅ BFCL capped at ≤ 15% of n before stratum pick — `pool.py:25`, `pool.py:205-207`, `tests/test_pool.py:69-100`
- ✅ Verified / Lite / Terminal-Bench path names ingest as empty; TB canary dropped; `FAIL_TO_PASS` / `PASS_TO_PASS` rows skipped — `pool.py:26-29`, `pool.py:37`, `pool.py:99-101`, `pool.py:120-122`, `pool.py:163-165`, `tests/test_pool.py:144-180`, `tests/test_pool.py:239-260`
- ✅ Collision-filter vs `--eval` instance_id / normalized prompt — `pool.py:148-160`, `pool.py:215-239`, `tests/test_pool.py:103-141`
- ✅ Dump `resolved` / success / y never written on pool rows — `pool.py:108-117`, `tests/test_pool.py:183-187`
- ✅ Teacher/gold `--limit` uses `sample_stratum` instead of first-N — `train.py:98-106`, `tests/test_pool.py:280-291`
- ✅ No live aiand, budget default untouched, no `TRAINED_PATH` flip, no hop/serve/scorer/fit changes, no second server — diff is `pool.py` + small `train.py` CLI/`_read_queries` only
- ✅ Tests assert CLI/JSONL observables (sources, bins, caps, collisions, absent y); no sklearn internals; unit path unpaid — `tests/test_pool.py`
- ⚠️ Cannot verify from diff: real SWE-Gym / R2E / BFCL dump shapes beyond fixtures (gym/R2E share `parse_smith_row`; implementer notes OpenHands may need a richer walk)
- ⚠️ Cannot verify from diff: operator actually passes SWE-smith **tool** traj dumps (CLI trusts `--smith` path; no traj-type field check)

### Strengths
- Clear unpaid seam: `pool` bypasses opt-in refuse; paid cmds unchanged.
- Source mix order matches the ticket (smith primary, BFCL cap, gym/R2E shortfall-only) and is covered by focused CLI tests, including the trivial-prefix trap that forced sampling after mix rather than shuffle-truncate.
- Eval leakage defenses are layered: filename block, FAIL_TO_PASS skip, TB canary, optional `--eval` collision keys.
- Output schema is gold/fit-ready prompts only — no dump teacher label as y.
- `_read_queries` stratum sampling aligns teacher/gold limits with the same pool policy.

### Issues
#### Critical
- None.

#### Important
- Collision-filter is incomplete unless the operator passes `--eval`. Path blocks and FAIL_TO_PASS drops help, but a smith-shaped traj whose `instance_id` overlaps Verified still ships if `--eval` is omitted (`pool.py:215-239`; implementer concern #4). Spec checklist treats the pool as collision-filtered; this is an operator footgun, not an automatic guarantee.
- `--smith` is optional (`train.py:828`). With empty/missing smith, `mix_sources` treats gym/R2E as the fill set (`pool.py:208-211`), so “extra only” can become the whole pool. Prefer required `--smith` or refuse when smith contributes nothing.

#### Minor
- Stratum targets are **independent** bin/phase/tools margins (`pool.py:169-196`), not joint `(bin × phase × tools)` cells, and there is no occupied-cell floor (≥20). Adequate to beat first-N trivial piles; joint balance is weaker than the `×` wording suggests.
- `hint_bin` is keyword + token heuristics (`pool.py:54-64`); `_FRONT_RE` includes `verified`, so prompts that merely mention Verified get `frontier`. Train-only prior is fine; bin mix can be noisy on real dumps.
- `test_pool_cli_stratum_samples_not_first_n_trivial` tools assert is soft: `tools == {True, False} or True in tools` (`tests/test_pool.py:59`) passes on tools-only pools; the dedicated tools test covers both flags.
- Reported `pytest` run on pool+train includes 1 unrelated Starlette/httpx warning — not pristine output (accepted as unrelated; still a noise finding per gate rules).
- `sample_stratum` re-sorts the full remaining list each pick (`pool.py:191-192`) — fine at n≈4k; not wrong, just O(n²).

### Assessment
**Task quality:** Approved
**Reasoning:** The unpaid pool writer meets the ticket: stratum (non-first-N) sampling, smith-primary mix, BFCL cap, eval absence defenses, no dump `resolved` as y, and observable CLI/JSONL tests. Remaining gaps are operator contracts (require `--eval` / `--smith`) and heuristic stratum priors, not missing core behavior.
