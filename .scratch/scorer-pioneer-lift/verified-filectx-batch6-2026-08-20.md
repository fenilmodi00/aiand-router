# Verified filectx batch6 - remaining local misses (2026-08-20)

**HARD:** no `docker pull`. Local 12 django `sweb.eval` images only.
Gateway: `TRAINED_PATH=shadow`, `SCORER_PATH=data/scorer-hard-logistic.json`.
**Serve candidate unchanged.** Do **not** flip `TRAINED_PATH`.

## Unpaid (minimal)

- Feed same-session `swe_eval_detail` / reason into the debug turn via
  `_debug_instruction_with_harness_feedback` (truncated apply/malformed lines).
- Unit test: `test_debug_instruction_includes_harness_feedback`.

No gold injection. No new images.

## Paid retest (n=4 remaining misses)

Ids: `10914`, `11532`, `12754`, `13512` (all images already local).

| instance | session_gold | resolved (rules/trained) | file_context_source | swe_eval_reason |
| --- | --- | --- | --- | --- |
| django__django-10914 | **true** | **true / true** | docker_cp | (resolved) |
| django__django-11532 | **true** | **true / true** | docker_cp | (resolved) |
| django__django-12754 | false | null / null | docker_cp | `swebench_instance_error` (malformed / missing line number) |
| django__django-13512 | false | null / null | docker_cp | `swebench_instance_error` (Hunk #1 FAILED on forms/fields.py) |

**Rates:** session_gold **2/4**; docker_cp **4/4**.

## Spend

| | USD |
| --- | ---: |
| before | 15.742347 |
| after | 15.757069 |
| delta | +0.014722 |
| budget cap | spend+15 |

## Cumulative local-12

Unique `session_gold=true`: **10 / 12**  
(10880, **10914**, 11066, 11099, **11532**, 11880, 13786, 14011, 14140, 15252).

Still unresolved: **12754, 13512**.

Merged: `data/verified_session_filectx_all.jsonl`.

## Gate

```
python -m aiand_router.eval --gate --log data/requests.jsonl --sessions data/verified_session_filectx_all.jsonl
```

Verdict: **`bounded_check_only`**. `do_not_flip_trained_path: true`. Floor n≥300 still fail.
Rules/trained resolve rate on labeled sessions: **0.80 / 0.80**.

## Artifacts

- `data/verified_ids_filectx_batch6_misses.jsonl`
- `data/verified_ids_filectx_batch6_remain.jsonl` (mid-run resume after duplicate-runner kill)
- `data/verified_session_filectx_batch6_misses.jsonl`
- `data/verified_session_filectx_batch6_remain.jsonl`
- Inventory: `local-sweb-eval-inventory-2026-08-20.md`

## Exhaustion / next

Local-12 set is **largely exhausted for useful retries**: 10/12 gold; remaining 2 are repeat apply/malformed failures after harden + harness-feedback debug. Further paid re-runs without new unpaid patch/path fixes have low expected ROI. Still **no** new docker pulls. No TRAINED_PATH flip.
