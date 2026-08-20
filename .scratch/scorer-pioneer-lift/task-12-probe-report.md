# Task 12 report — paid hard-y probe

**Status:** resolved (probe ran; **do not scale**)  
**Date:** 2026-08-14  
**Decision:** **fail-pass / stop.** Not ticket kill (`kill_spearman` false; y_rate 0 ≠ ~0.39). Not pass (Spearman 0, y_rate 0, no holdout model order). Issue **07 not taken**. No Rec B / `TRAINED_PATH` flip / Verified-as-fit. Code default `BUDGET_LIMIT_USD` stays **15**.

Evidence log: `.scratch/scorer-pioneer-lift/issue-12-probe-run.md`

## What ran

1. Unpaid `train pool --verified-like --n 40` collision-filtered vs frozen `data/gold-verified.jsonl`. Wrote `data/pool-hard.jsonl` **n=22** (verified-like filter; asked 40).
2. Opt-in sparse gold `AIAND_TRAIN=1` → `data/gold-sparse-hard.jsonl` **88 cells**, cache-first. Spend `2.602575` → `2.625149` (delta ≈ 0.023). Keys: `success` / `success_tier`; never `resolved` / `y`.
3. Unpaid geometry vs frozen verified. `eval_is_fit_gold=false`.

No HuggingFace SWE-smith `tool` traj dump on disk (searched `data/`, `datasets/`, `.scratch/`, D: depth-4 `*smith*`, no HF cache). `--smith` was **`datasets/train-queries.jsonl`** (only local query JSONL `parse_smith_row` accepts). Ingest tags `source=swe-smith`; this is **not** `SWE-smith-trajectories`.

## Geometry

| | train (hard probe) | eval (frozen verified) |
|---|---|---|
| y_rate | **0.0** (27 observed / 88) | 0.070 |
| Flash / Qwen / Kimi / Pro | 0 / 0 / 0 / 0 | 0.079 / 0.079 / 0.124 / 0.0 |
| Spearman | **0.0** | |
| kill_spearman | **false** | |
| prefer_logistic | **true** | |
| tokens | all `log1p` ≤ 4.14 | almost all short |

Pass bar (Spearman > 0 **and** y closer to ~0.07–0.22 than ~0.39 **and** Kimi > Flash = Qwen > Pro): **miss**.  
Easy-y kill (~0.39) / `kill_spearman`: **not fired**. Operational stop is the same as kill: **do not scale**.

## Why y=0 (not a ranking test)

- `--verified-like` inferred `json_schema` with `required: []` because prompts contain the word `json` (“Delete the unused import of json …”). Issue-02 schema y then requires parseable JSON. Prose answers → `success=false`, `success_tier=verified`.
- 61/88 cells **unobserved** (budget 429). Operator `.env` cap already near `spend.txt` ~2.60; **code default 15 not changed**. Filling those cells would need a higher operator cap, not a code edit.
- Observed 27 are all failures; model order is a four-way tie at 0 → Spearman undefined/0.

## Constraints held

Frozen verified eval-only; dump `resolved` unused; no invented gold cells; no Rec B; no `TRAINED_PATH` flip; no Verified-as-fit; no GBDT; no issue 07; cache-first; secrets redacted.

## Next (not taken)

Do **not** run dense `--gold --dense --exclude`, logistic `fit` (no `--gbdt`), or `--cost-gold`. Do **not** take issue 13 / 07.

A later probe is only worth spend if (a) a real SWE-smith `tool` JSONL exists locally, and (b) hard checks are real `expected` / schema / pytest on those rows — not inferred schema from the word `json`. Optional: raise **operator** `.env` budget to finish unobserved cells on a *new* pool; do not change the code default.
