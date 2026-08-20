# Verified filectx pathready batch2 (2026-08-20)

**Path:** path-ready curated ids + ≤2 new `sweb.eval` pulls. Gateway process env: `TRAINED_PATH=shadow`, `SCORER_PATH=data/scorer-hard-logistic.json`.

**Serve candidate unchanged:** `data/scorer-hard-logistic.json`. Do **not** flip `TRAINED_PATH` from this batch. (Note: checked-in `.env` may still say `trained` from an earlier operator hop-path experiment — gateway for this run was started with shadow.)

## Unpaid prep

1. **Bugfix:** `guess_target_paths` now extracts repo paths from GitHub `blob/<ref>/...` URLs (lookbehind blocked slash-prefixed paths). Fixes django-11066 (`django/contrib/contenttypes/management/__init__.py`). Tests added.
2. **Curate:** `data/verified_ids_filectx_pathready.json` + `.jsonl` — n=4 with non-empty plausible `.py` paths + local images.
3. **Pulls (≤2):** `django-12754`, `django-15252` (~4.19–4.4GB). Local already: 11066, 11099. docker-cp smoke verified on all four.

| instance | paths (guess) | image |
| --- | --- | --- |
| django__django-12754 | autodetector.py + inheritance tests | pulled |
| django__django-15252 | test/runner.py + migrations/* | pulled |
| django__django-11066 | contenttypes/management/__init__.py | local (blob fix) |
| django__django-11099 | auth/validators.py | local |

Pathready pool after filter: **124** plausible Verified dump rows; selected **4** under local+≤2-pull constraint (limit 5 → ran 4).

## Spend

| | USD |
| --- | ---: |
| before | 15.662449 |
| after | 15.680592 |
| delta | +0.018143 |
| budget cap | spend+15 at start (~30.66) |

## Results (n=4)

| instance | session_gold | file_context_source | has_target_paths | rules | trained |
| --- | --- | --- | --- | --- | --- |
| django__django-12754 | false (`needs_swe_eval`) | docker_cp | true | null | null |
| django__django-15252 | false (`needs_swe_eval`) | docker_cp | true | null | null |
| django__django-11066 | **true** | docker_cp | true | true | true |
| django__django-11099 | **true** | docker_cp | true | true | true |

**Rates:** session_gold **2/4 = 0.50**; rules resolve **2/4**; trained resolve **2/4**; docker_cp filectx **4/4** (was 1/4 on batch1).

Labeled-only quality: rules=trained=1.0 on the 2 gold rows. Unlabeled rows attempted SWE_EVAL_CMD (`swe_eval_attempted=true`) — still apply/resolve miss, not missing filectx.

## Gate

```
python -m aiand_router.eval --gate --log data/requests.jsonl --sessions data/verified_session_filectx_batch2.jsonl
```

Verdict: **`bounded_check_only`**. `quality_session_gold` pass; `floor_session_gold_n` fail (4≪300); BSS/ECE fail at small n. `do_not_flip_trained_path: true`.

## Artifacts

- `data/verified_ids_filectx_pathready.json` / `.jsonl`
- `data/verified_session_filectx_batch2.jsonl`
- Curator scratch: `.scratch/scorer-pioneer-lift/_curate_pathready.py`

## Blockers / next

1. Floor n≥300 still far away; do not promote.
2. Harder instances (12754/15252) get file bytes but still `needs_swe_eval` — flashlight+filectx ≠ applyable fix on harder bugs.
3. No smith/gym_alt train gold this turn.
4. Optional next paid: more pathready django ids with local images (pull ≤2), same shadow + SWE_EVAL_CMD recipe; or diagnose apply failures on 12754/15252 patches before scaling.

```powershell
$spend = [double](Get-Content data/spend.txt -Raw).Trim()
$env:BUDGET_LIMIT_USD = [string]($spend + 15)
$env:PYTHONPATH='src'; $env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'
$env:SWE_EVAL_CMD='python scripts/swe_eval_cmd.py --instance {instance_id} --patch {patch_file}'
$env:TRAINED_PATH='shadow'; $env:SCORER_PATH='data/scorer-hard-logistic.json'; $env:UPSTREAM_TIMEOUT_S='300'
# gateway already on :8000 with same env
python scripts/run_verified_session.py --ids data/verified_ids_filectx_pathready.jsonl --limit 5 --budget-limit $env:BUDGET_LIMIT_USD --out data/verified_session_filectx_batch3.jsonl --no-fetch
python -m aiand_router.eval --gate --log data/requests.jsonl --sessions data/verified_session_filectx_batch3.jsonl
```
