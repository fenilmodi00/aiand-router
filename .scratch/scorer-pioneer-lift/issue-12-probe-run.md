# Issue 12 probe run log (redacted)

Date: 2026-08-14  
Shell: Windows PowerShell. `$env:PYTHONPATH="src"`. `$env:AIAND_TRAIN="1"` for gold only.  
Secrets: none printed. `AIAND_API_KEY` / `ROUTER_API_KEY` / `.env` values redacted as `<REDACTED>`. Code default `BUDGET_LIMIT_USD` unchanged (15). Operator `.env` may differ; do not treat `data/spend.txt` as the code default.

Frozen eval: `data/gold-verified.jsonl` (eval-only; never fit).  
Smith: no local `smith-tool.jsonl` / HuggingFace `SWE-smith-trajectories` cache. Stand-in: `datasets/train-queries.jsonl` (prompt JSONL; `ingest_path` tags `source=swe-smith`). Not a HuggingFace tool-traj dump.

---

## 1. Unpaid pool

```
python -m aiand_router.train pool --smith datasets/train-queries.jsonl --eval data/gold-verified.jsonl --out data/pool-hard.jsonl --n 40 --verified-like
```

```
pool n=22 -> data/pool-hard.jsonl
```

Pool inspect (unpaid): n=22; all `hint_bin=hard`, `phase=plan`, `needs_tools=false`, `source=swe-smith`; all carry inferred `json_schema={"type":"object","required":[]}` (word `json` in “unused import of json”); tokens 31–58; no `resolved`/`y`/`success`; 0 collisions vs frozen eval; 4/22 prompt overlap with `data/gold-sparse-400.jsonl`.

---

## 2. Paid sparse gold (opt-in)

```
$env:AIAND_TRAIN="1"
python -m aiand_router.train gold --queries data/pool-hard.jsonl --out data/gold-sparse-hard.jsonl --limit 40
```

`.env` loaded by `train` `__main__` (`AIAND_API_KEY=<REDACTED>`, `AIAND_BASE_URL=<REDACTED>`). Cache-first.

```
gold 20 cells spend=2.6030
gold 40 cells spend=2.6033
gold 60 cells spend=2.6076
gold 80 cells spend=2.6121
gold done cells=88 spend=2.6251 -> data\gold-sparse-hard.jsonl
```

`data/spend.txt` after: `2.625149` (was `2.602575` before this run; delta ≈ 0.0226).  
Cells: 88 (22 prompts × 4 sparse anchors). Observed 27 all `success=false` `success_tier=verified`. Unobserved 61 (budget 429 skip — operator spend already near `.env` cap; code default still 15). No `resolved`/`y` keys on gold rows. Frozen `data/gold-verified.jsonl` not written.

---

## 3. Geometry (unpaid)

```
python -m aiand_router.geometry --train data/gold-sparse-hard.jsonl --eval data/gold-verified.jsonl
```

```
{
  "train": {
    "per_id": {
      "qwen/qwen3.6-27b": 0.0,
      "moonshotai/kimi-k2.7-code": 0.0,
      "deepseek-ai/deepseek-v4-pro": 0.0,
      "deepseek-ai/deepseek-v4-flash": 0.0
    },
    "y_rate": 0.0,
    "frac_log1p_gt_4_8": 0.0,
    "frac_log1p_le_4_14": 1.0
  },
  "eval": {
    "per_id": {
      "moonshotai/kimi-k2.7-code": 0.12359550561797752,
      "deepseek-ai/deepseek-v4-flash": 0.07865168539325842,
      "deepseek-ai/deepseek-v4-pro": 0.0,
      "qwen/qwen3.6-27b": 0.07865168539325842
    },
    "y_rate": 0.0702247191011236,
    "frac_log1p_gt_4_8": 0.0,
    "frac_log1p_le_4_14": 0.9887640449438202
  },
  "spearman_train_eval": 0.0,
  "kill_spearman": false,
  "prefer_logistic": true,
  "eval_is_fit_gold": false,
  "recommended_artifact": "data/scorer-logistic.json"
}
kill_spearman False
prefer_logistic True
recommended_artifact data/scorer-logistic.json
```

Observed rates (27 cells): Flash 0/7, Kimi 0/7, Pro 0/9, Qwen 0/4. Spearman 0 because train rates have zero variance (`geometry.spearman` returns 0.0 when `dx==0`).

---

## Decision

**Do not scale. Failed pass. Not the ticket Spearman<0 / y≈0.39 kill.**

- Pass needs Spearman > 0, y in ~0.07–0.22, holdout order Kimi > Flash = Qwen > Pro. Got Spearman **0**, y_rate **0**, all models tied at 0.
- `kill_spearman` is **false** (rho is not < 0). y_rate is **not** ~0.39.
- Stop: no dense `--gold --dense --exclude`, no logistic fit, no `--cost-gold`, no issue 07, no issue 13.

`TRAINED_PATH` still shadow. Artifact still `not_spec_floors`. Rec B closed. Verified eval-only.
