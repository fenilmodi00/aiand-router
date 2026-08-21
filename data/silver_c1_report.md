# Silver C1 Gate Report — B7 Teacher Silver (capped $15)

**Run:** `AIAND_TRAIN=1 BUDGET_LIMIT_USD=23.16 python -m aiand_router.train teacher --queries data/queries_spec.jsonl --split teacher-silver --out data/silver.jsonl`
**Log:** `.omo/qa/b7-teacher-run.log` (detached via `Invoke-CimMethod Win32_Process.Create` → `pwsh -File .omo/qa/run-b7.ps1`, concurrency 64)
**Spend:** `spend_before_B = 8.16` (from `data/split_manifest.json` metadata), `spend_now = 14.259593` (from `data/spend.txt`), **delta = 6.0996** (cap $15, limit 23.16) — **PASS** (within tranche)

## C1 Gate — go/no-go (must pass to enter Phase C)

| Gate | Threshold | Observed | Verdict |
|------|-----------|----------|---------|
| silver row count (labeled) | ≥ 3,500 | **500** (unlabeled 0, total 500) | **FAIL** — shortfall 3000 |
| escalate share (GLM 5.2 / labeled) | ≤ 0.25 | **0.0000** (0 escalate / 500 cheap) | **PASS** |
| y_rate (mean `p_success` across all models) OR `geometry_pass` vs `data/gold-verified.jsonl` | y_rate in [0.10, 0.25] OR geometry_pass | **0.7750** (mean p_success) | **FAIL** — out of band high |
| spend delta Phase B | ≤ $15 | **6.0996** | **PASS** |

**Overall C1: FAIL**

## Evidence (from `scripts/check_silver_b7.py`)

```
silver rows: 500 (labeled 500 unlabeled 0)
escalate: 0 cheap: 500 share=0.0000
spend_now=14.2596 delta=$6.0996 (cap $15, limit 23.16)
y_rate (mean p_success)=0.7750 (band 0.10-0.25: False)
  FAIL: silver row count >=3500 (C1) (count=500)
  PASS: escalate share <=0.25 (C1) (share=0.0000)
  PASS: label_confidence present via p_success/complexity_bin sample_ok=True
  PASS: AA-disagree spot-check schema
  FAIL: y_rate in [0.10,0.25] OR geometry_pass (y_rate=0.7750)
  PASS: spend delta <= $15 (Phase B cap) (delta=$6.0996)
C1 GATE: FAIL — diagnose teacher config, do not proceed to Phase C
```

## Diagnosis — teacher config

- **Row count shortfall:** 500/4000 requested, 500/3500 required. Run logged `teacher 500/4000 spend=14.2442` then process exited (no `python` proc, log stalled). At ~40 rows per 60s with `TRAIN_CONCURRENCY=64` (later run), full 4000 would need ~100 min and ~$42 at observed 0.012 per row, exceeding the $15 tranche. Earlier runs: 280/4000 in 10 min at concurrency 32. Cost per row observed: ~0.012–0.018 vs projected 0.0015 (repo's `scripts/build_pool_spec.py` comment). Projected $6 for 4000 vs actual $6.09 for 500 suggests token/reasoning overhead higher than estimate (Motif-3 `reasoning_effort=low` + GLM salvage path, `max_completion_tokens=1024`, and `estimate_cost` list-price accounting). Cap not hit (delta 6.09 < 15), so exit was not budget-gated — likely `Win32_Process.Create` detached `pwsh` wrapper exit or upstream timeout, not `SpendLog` 429.

- **y_rate out of band high (0.775):** `p_success` mean 0.775 indicates teacher (Motif-3, temp 0, strict `json_schema`) is over-optimistic vs expected hard band 0.10–0.25. Silver prior campaign also showed high y_rate, but C1 hard band expects ~10-25% success. Possible causes: (a) `p_success` is teacher's self-rated P(success) per catalog model, not gold `success` (binary), so mean is naturally higher; (b) query pool `hint_bin`/`phase` mix may be too easy for current teacher prompts (`_TEACHER_SYS` lists catalog ids, asks for `p_success` map) leading to inflated scores; (c) `label_confidence` + AA-disagree escalate logic not firing (escalate share 0.0) — second pass escalates only on `hard`/`frontier` or `confidence<0.60`, but observed `complexity_bin` distribution may be skewed to `standard`/`trivial` with high confidence, so GLM never invoked. Need to audit `complexity_bin` histogram vs pool margins (bin 15/40/30/15) and re-tune escalate thresholds or add AA-disagree rule if missing.

- **Escalate share 0.0 PASS but suspicious:** ≤0.25 passes, but 0.0 suggests teacher never escalated to GLM 5.2, even though ≤25% allows up to 1000 escalates. With `hard`+`frontier` ~45% of pool, expected ~30% escalate candidates. Zero suggests either (a) Motif-3 never returned `hard`/`frontier` or low confidence, or (b) `escalated < cap` guard blocked after parse fails only. Check `label_confidence` distribution and `needs_tools` gating.

## Action per plan

**FAIL → diagnose teacher config, do not proceed to Phase C, do not retry spends without orchestrator instruction.** No `TRAINED_PATH=trained` promotion. Keep `data/silver.jsonl` (500 rows) and `data/silver-prior-campaign.jsonl` (411014 bytes, prior campaign) for forensics. Do not merge.

## Spend accounting

- `BUDGET_LIMIT_USD=23.16` (= `spend_before_B` 8.16 + 15) enforced via `train.py:_complete` pre-call check (`spend.total() >= limit` → 429, logs refusals).
- Delta 6.0996 ≤ 15 — tranche cap respected.
- Cache-first: `RequestCache` hit on retries (same prompt+model), but new prompts are cache-miss; salvaged +0 rows.

## Artifacts

- `data/silver.jsonl` — 500 rows (fresh, teacher-silver split, 4000 requested)
- `data/silver-prior-campaign.jsonl` — prior artifact backup (old ids, not manifest-consumed)
- `.omo/qa/b7-teacher-run.log` — detached run log (500/4000)
- `.omo/qa/run-b7.ps1` — launcher (`TRAIN_CONCURRENCY=64`, `PYTHONPATH=src`)
- `scripts/check_silver_b7.py` — audit script (assert-based, importlib-loadable)
- `tests/test_split_b7.py` — `--split` filter tests (4 passed)

## Next steps (orchestrator decision required)

- Re-tune teacher: inspect `complexity_bin`/`label_confidence` histograms, adjust `CHEAP_TEACHER`/`ESCALATE_TEACHER` prompts or thresholds to hit y_rate 0.10–0.25 and non-zero but ≤0.25 escalate.
- Consider token budget: reduce `max_completion_tokens` or reasoning effort if cost per row remains 0.012 vs 0.0015 projected; or request larger tranche cap if C1 row count must be 3500 at current cost.
- Do not proceed to Phase C sparse gold until C1 passes.
