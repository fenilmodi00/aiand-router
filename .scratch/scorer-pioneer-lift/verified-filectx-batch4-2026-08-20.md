# Verified filectx batch4 — LOCAL ONLY (2026-08-20)

**HARD constraint mid-turn:** no further `docker pull`. Disk space limited.
Gateway: `TRAINED_PATH=shadow`, `SCORER_PATH=data/scorer-hard-logistic.json`.
**Serve candidate unchanged.** Do **not** flip `TRAINED_PATH`.

## Pulls

- **Stopped / no new pulls after stop order.**
- Three images (13512 / 13786 / 14011) had already finished downloading earlier this turn before the stop; they are treated as **already-local** inventory only. No additional pulls.

## Unpaid (landed this cycle)

1. `guess_target_paths`: FAIL_TO_PASS–ranked + `plausible_target_paths` junk filter; default cap 4.
2. `docker_file_context.DEFAULT_MAX_FILES=4`; edit/context prompts use **copied** path keys.
3. Session rows log `swe_eval_reason` / `swe_eval_detail` (e.g. Patch Apply Failed).
4. Curator `_curate_batch4.py`: **`PULL_BUDGET=0`**, local images only.
5. Inventory: `.scratch/scorer-pioneer-lift/local-sweb-eval-inventory-2026-08-20.md`

## Local inventory (12 images)

All map to django Verified ids. After batch4, **0** unused local path-ready remain (every local image has a filectx session row).

## Spend

| | USD |
| --- | ---: |
| before | 15.696931 |
| after | 15.713667 |
| delta | +0.016736 |
| budget cap | spend+15 (~30.70) |

## Results (n=3; local-only; no pull)

| instance | session_gold | file_context_source | swe_eval_reason |
| --- | --- | --- | --- |
| django__django-13512 | false | docker_cp | `swebench_instance_error` (malformed patch / apply fail) |
| django__django-13786 | **true** | docker_cp | (resolved) |
| django__django-14011 | false | docker_cp | `swebench_instance_error` (malformed patch / apply fail) |

**Rates:** session_gold **1/3**; docker_cp **3/3**. Reason logging confirmed on both misses.

## Cumulative (unique filectx instances)

Unique ids: **12**. Unique `session_gold=true`: **6**  
(10880, 11066, 11099, 11880, 13786, 14140). Still ≪ floor 300.

Merged artifact: `data/verified_session_filectx_all.jsonl`.

## Gate

```
python -m aiand_router.eval --gate --log data/requests.jsonl --sessions data/verified_session_filectx_all.jsonl
```

Verdict: **`bounded_check_only`**. `do_not_flip_trained_path: true`.

## Artifacts

- `data/verified_ids_filectx_batch4.json(l)`
- `data/verified_session_filectx_batch4.jsonl`
- `data/verified_session_filectx_all.jsonl`
- Inventory + curator: see above

## Blockers / next (no downloads)

1. **No unused local eval images left** — cannot expand session_gold n without pulls or reclaim+different host.
2. Misses are apply/malformed hunks (now diagnosed in-row), not missing docker_cp.
3. Optional unpaid: tighten hunk/prompt further; optional **re-run** local misses (10914/11532/12754/13512/14011/15252) without new images.
4. Optional disk reclaim: `docker rmi` only if operator chooses which images to drop.
5. No smith/gym_alt train gold; no TRAINED_PATH flip.

```powershell
# Next unpaid (no pull): refresh inventory + confirm zero unused locals
$env:PYTHONPATH='src'; $env:PYTHONUTF8='1'
python .scratch/scorer-pioneer-lift/_curate_batch4.py
# optional: re-run a local miss only, e.g. 13512, still NO docker pull
```
