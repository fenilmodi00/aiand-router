"""One-off retune geometry sweep (unpaid)."""
from __future__ import annotations

import json
from pathlib import Path

from aiand_router.geometry import (
    _load_gold,
    concat_gold,
    geometry_from_rows,
    geometry_report,
)

ROOT = Path(__file__).resolve().parents[2]
eval_p = ROOT / "data/gold-verified.jsonl"
files = {
    "mix1": "data/gold-sparse-hard-mix1.jsonl",
    "mix1-train": "data/gold-sparse-hard-mix1-train.jsonl",
    "mix1-retune": "data/gold-sparse-hard-mix1-retune.jsonl",
    "mix2": "data/gold-sparse-hard-mix2.jsonl",
    "seed14": "data/gold-sparse-hard-probe-seed14.jsonl",
    "seed11": "data/gold-sparse-hard-probe-seed11.jsonl",
    "seed12": "data/gold-sparse-hard-probe-seed12.jsonl",
    "seed13": "data/gold-sparse-hard-probe-seed13.jsonl",
}
rows_out = []
for name, f in files.items():
    p = ROOT / f
    if not p.exists():
        rows_out.append({"name": name, "error": "missing"})
        continue
    r = geometry_report(p, eval_p)
    n = len(_load_gold(p))
    rows_out.append(
        {
            "name": name,
            "n": n,
            "y_rate": round(r["train"]["y_rate"], 4),
            "order": r["holdout_like_order"],
            "geometry_pass": r["geometry_pass"],
            "spearman": round(r["spearman_train_eval"], 4),
        }
    )

base = ROOT / "data/gold-sparse-hard-mix1-retune.jsonl"
for extra_name, extra_f in [
    ("mix2", "data/gold-sparse-hard-mix2.jsonl"),
    ("seed14", "data/gold-sparse-hard-probe-seed14.jsonl"),
    ("mix1", "data/gold-sparse-hard-mix1.jsonl"),
]:
    extra = ROOT / extra_f
    if not base.exists() or not extra.exists():
        continue
    combined = concat_gold(_load_gold(base), _load_gold(extra))
    r = geometry_from_rows(combined, _load_gold(eval_p))
    rows_out.append(
        {
            "name": f"retune+{extra_name}",
            "n": len(combined),
            "y_rate": round(r["train"]["y_rate"], 4),
            "order": r["holdout_like_order"],
            "geometry_pass": r["geometry_pass"],
            "spearman": round(r["spearman_train_eval"], 4),
        }
    )

print(json.dumps(rows_out, indent=2))
