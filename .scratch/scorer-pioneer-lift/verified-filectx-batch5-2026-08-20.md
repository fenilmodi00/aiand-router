# Verified filectx batch5 — harden retest LOCAL ONLY (2026-08-20)

**HARD:** no `docker pull`. Local 12 django `sweb.eval` images only.
Gateway: `TRAINED_PATH=shadow`, `SCORER_PATH=data/scorer-hard-logistic.json`.
**Serve candidate unchanged.** Do **not** flip `TRAINED_PATH`.

## Unpaid harden (this cycle)

Based on logged `Patch Apply Failed` / malformed hunks (13512/14011):

1. **`normalize_unified_diff`** in `extract_unified_diff` — fix missing ` `/`+`/`-` markers, recompute `@@` counts, strip trailing prose.
2. **Path ranking** — legacy F2P `(module.Class)` nodeids; **primary-only** when any primary exists (drop tests — 10914 applied `global_settings` then failed a test hunk); settings-token → `django/conf/global_settings.py`; default limit **2**.
3. **`DEFAULT_MAX_FILES=2`** for docker-cp.
4. **Edit/debug prompts** — explicit hunk marker + count rules; no test hunks in production-file diffs.
5. Tests: `test_verified_runner.py` + `test_docker_file_context.py` green (53).

No gold patch injection.

## Local misses targeted (n=5)

`data/verified_ids_filectx_batch5_local_miss.jsonl`:
14011, 10914, 15252, 13512, 12754 (all images already local).

Skipped 11532 this round (still unresolved; optional next re-run).

## Spend

| | USD |
| --- | ---: |
| before | 15.713667 |
| after | 15.742347 |
| delta | +0.028680 |
| budget cap | spend+15 (~30.71) |

## Results (n=5; local-only; no pull)

| instance | session_gold | resolved (rules/trained) | file_context_source | swe_eval_reason |
| --- | --- | --- | --- | --- |
| django__django-14011 | **true** | false / false | docker_cp | (labeled) |
| django__django-10914 | false | null / null | docker_cp | `swebench_instance_error` |
| django__django-15252 | **true** | **true / true** | docker_cp | (resolved) |
| django__django-13512 | false | null / null | docker_cp | `swebench_instance_error` |
| django__django-12754 | false | null / null | docker_cp | `swebench_instance_error` |

**Rates:** session_gold **2/5**; docker_cp **5/5**. Harden recovered apply/label on 14011 (was prior apply-fail) and full resolve on 15252.

## Cumulative local-12

Unique `session_gold=true`: **8 / 12**  
(10880, 11066, 11099, 11880, 13786, **14011**, 14140, **15252**).

Still `needs_swe_eval`: **10914, 11532, 12754, 13512**.

Merged: `data/verified_session_filectx_all.jsonl`.

## Gate

```
python -m aiand_router.eval --gate --log data/requests.jsonl --sessions data/verified_session_filectx_all.jsonl
```

Verdict: **`bounded_check_only`**. `do_not_flip_trained_path: true`. Floor n≥300 still fail.

## Artifacts

- `data/verified_ids_filectx_batch5_local_miss.jsonl`
- `data/verified_session_filectx_batch5.jsonl`
- `data/verified_session_filectx_all.jsonl`
- Inventory: `local-sweb-eval-inventory-2026-08-20.md`

## Next (zero new images)

1. **Unpaid already landed post-batch5:** primary-only path set (above). Optional: inject `swe_eval_detail` into debug turn text.
2. Optional paid: re-run remaining **4** local misses (10914/11532/12754/13512) — still **no pull**.
3. No TRAINED_PATH flip; no smith/gym_alt train gold.

```powershell
$env:PYTHONPATH='src'; $env:PYTHONUTF8='1'
$env:TRAINED_PATH='shadow'
$env:SCORER_PATH='data/scorer-hard-logistic.json'
$env:SWE_EVAL_CMD='python scripts/swe_eval_cmd.py --instance {instance_id} --patch {patch_file}'
# remaining misses only — NO docker pull
```
