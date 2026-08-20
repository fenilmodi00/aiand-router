# Verified filectx batch3 (2026-08-20)

**Path:** exclude already-run ids; prefer local images (none left unused); pull ≤3 new `sweb.eval` images; dual-policy filectx+SWE_EVAL. Gateway process: `TRAINED_PATH=shadow`, `SCORER_PATH=data/scorer-hard-logistic.json`.

**Serve candidate unchanged:** `data/scorer-hard-logistic.json`. Do **not** flip `TRAINED_PATH`.

## Unpaid prep

1. **Diagnosis** of batch2 misses 12754/15252: `.scratch/scorer-pioneer-lift/filectx-12754-15252-diagnosis-2026-08-20.md` — not empty patch / not missing docker_cp; `swe_eval_attempted` → harness `resolved:null` (apply/instance error). Secondary: distractor paths in guess.
2. **Curate** `data/verified_ids_filectx_batch3.json(l)` — exclude `{11099,10880,10914,11066,12754,15252}`. Local unused pathready = **0**; selected **3** pulls (cap 3; target list ≤8).
3. **Pulls (3):** 14140, 11532, 11880. docker_cp smoke OK on all three.

| instance | paths (plausible) | image |
| --- | --- | --- |
| django__django-14140 | expressions.py + tests | pulled |
| django__django-11532 | mail/tests + message.py | pulled |
| django__django-11880 | forms/fields.py + forms.py | pulled |

## Spend

| | USD |
| --- | ---: |
| before | 15.680592 |
| after | 15.696931 |
| delta | +0.016339 |
| budget cap | spend+15 at start (~30.68) |

## Results (n=3; limit 5 but only 3 ids)

| instance | session_gold | file_context_source | rules | trained |
| --- | --- | --- | --- | --- |
| django__django-14140 | **true** | docker_cp | false | false |
| django__django-11532 | false (`needs_swe_eval`, swe attempted) | docker_cp | null | null |
| django__django-11880 | **true** | docker_cp | true | true |

**Rates:** session_gold **2/3**; docker_cp **3/3**; rules resolve labeled 1/2 true (14140 labeled fail); trained matches rules on labeled rows.

## Cumulative (unique instances across filectx artifacts)

Unique Verified ids with any filectx session row: **9**. Unique `session_gold=true`: **5**  
(10880, 11066, 11099, 11880, 14140). Still ≪ floor 300.

## Gate

```
python -m aiand_router.eval --gate --log data/requests.jsonl --sessions data/verified_session_filectx_batch3.jsonl
```

Verdict: **`bounded_check_only`**. `quality_session_gold` pass; `floor_session_gold_n` fail (3≪300). `do_not_flip_trained_path: true`.

## Artifacts

- `data/verified_ids_filectx_batch3.json` / `.jsonl`
- `data/verified_session_filectx_batch3.jsonl`
- Diagnosis: `filectx-12754-15252-diagnosis-2026-08-20.md`
- Curator: `.scratch/scorer-pioneer-lift/_curate_batch3.py`

## Blockers / next

1. No unused local eval images after excluding prior 6; each new id needs a pull (≤3/turn).
2. 11532 same class as 12754/15252 (filectx + extractable patch → unlabeled apply).
3. Optional unpaid: filter distractor guesses (`plausible` + FAIL_TO_PASS rank) before more paid scale.
4. No smith/gym_alt train gold; no TRAINED_PATH flip.

```powershell
$spend = [double](Get-Content data/spend.txt -Raw).Trim()
$env:BUDGET_LIMIT_USD = [string]($spend + 15)
$env:PYTHONPATH='src'; $env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'
$env:SWE_EVAL_CMD='python scripts/swe_eval_cmd.py --instance {instance_id} --patch {patch_file}'
$env:TRAINED_PATH='shadow'; $env:SCORER_PATH='data/scorer-hard-logistic.json'; $env:UPSTREAM_TIMEOUT_S='300'
# gateway on :8000 with TRAINED_PATH=shadow
python .scratch/scorer-pioneer-lift/_curate_batch3.py   # or extend exclude list
# pull ≤3 new images from meta, then:
python scripts/run_verified_session.py --ids data/verified_ids_filectx_batch3.jsonl --limit 5 --budget-limit $env:BUDGET_LIMIT_USD --out data/verified_session_filectx_batch4.jsonl --no-fetch
python -m aiand_router.eval --gate --log data/requests.jsonl --sessions data/verified_session_filectx_batch4.jsonl
```
