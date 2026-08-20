# Verified filectx dual-policy batch (2026-08-20)

**Path:** local `sweb.eval` images only (no new pulls this run). Prior agent had already pulled 10880/10914/11066 (~4.18GB each local).

**Serve candidate unchanged:** `data/scorer-hard-logistic.json` + `TRAINED_PATH=shadow` (do not flip).

## Spend

| | USD |
| --- | ---: |
| before | 15.653121 |
| after | 15.662449 |
| delta | +0.009328 |
| budget cap | spend+15 at start (~30.65) |

## Instances (n=4 local images)

| instance | session_gold | file_context_source | has_target_paths | rules resolved | trained resolved |
| --- | --- | --- | --- | --- | --- |
| django__django-11099 | true | docker_cp | true | true | true |
| django__django-10880 | true | unavailable | false | true | true |
| django__django-10914 | false (needs_swe_eval) | unavailable | false | null | null |
| django__django-11066 | false (needs_swe_eval) | unavailable | false | null | null |

**Rates (including unlabeled):** session_gold **2/4 = 0.50**; rules resolve **2/4 = 0.50**; trained resolve **2/4 = 0.50**; docker_cp filectx **1/4**.

**Gate (labeled only):** `quality_session_gold` pass with rules=trained=1.0 on the 2 labeled rows; overall verdict `bounded_check_only` (floor n>=300 fail; cost/calibration fail at small n). `do_not_flip_trained_path: true`.

## Notes

1. Prior n=4 shell aborted mid-run; process completed 3/4 then died; **11066** finished in a separate paid remainder call (LLM likely cached; spend flat on remainder).
2. Path guessing fails on 3/4 → `file_context_source=unavailable` even with local images. 10880 still resolved without file bytes (lucky/simple patch). Scaling ROI needs better `likely_target_files` or broader docker-cp fallback.
3. No smith/gym_alt/order-mix gold probes. No serve candidate replace.

## Artifacts

- `data/verified_ids_filectx_n5.jsonl` (4 local ids)
- `data/verified_session_filectx_batch.jsonl` (canonical n=4)
- `data/verified_session_filectx_n5.jsonl` (same)
- `data/verified_session_filectx_11066.jsonl` (remainder)

## Next paid command (scale carefully)

Prefer instances where `guess_target_paths` succeeds **or** pull 1–2 images known to have path hints. Example after path-guess fix / curated ids:

```powershell
$spend = [double](Get-Content data/spend.txt -Raw).Trim()
$env:BUDGET_LIMIT_USD = [string]($spend + 15)
$env:PYTHONPATH='src'; $env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'
$env:SWE_EVAL_CMD='python scripts/swe_eval_cmd.py --instance {instance_id} --patch {patch_file}'
$env:TRAINED_PATH='shadow'; $env:SCORER_PATH='data/scorer-hard-logistic.json'; $env:UPSTREAM_TIMEOUT_S='300'
# gateway already on :8000 with same env
python scripts/run_verified_session.py --ids data/verified_ids_filectx_pathready.jsonl --limit 5 --budget-limit $env:BUDGET_LIMIT_USD --out data/verified_session_filectx_batch2.jsonl --no-fetch
python -m aiand_router.eval --gate --log data/requests.jsonl --sessions data/verified_session_filectx_batch2.jsonl
```

Unpaid first: scan Verified dump for ids with guessable paths + local/pullable images before paying.
