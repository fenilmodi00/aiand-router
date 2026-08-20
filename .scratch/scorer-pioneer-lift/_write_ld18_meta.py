"""Write meta JSON for gate-pass distill shadows."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
rows = [
    {
        "artifact": "data/scorer-hard-bilinear-distill48-ld18-gymalt.json",
        "role": "best_gate_pass_distill",
        "knobs": {
            "bilinear_distill_hash_dim": 48,
            "bilinear_distill_latent_dim": 18,
            "bilinear_ridge_l2": 0.05,
            "train": "gold-sparse-hard-mix1-train-gym-alt-merged",
            "cal": "gold-dense-hard-cal-merged",
        },
        "metrics": {
            "replay_gate_pass": True,
            "rank_auc": 0.791,
            "brier_skill": 0.0316,
            "ece_equal_width": 0.022,
            "mean_p_spread": 0.105,
            "rules_cost_delta": 0.000687,
            "trained_success": 0.112,
        },
        "vs_serve": {
            "gate": "match (both true)",
            "auc": "better",
            "bss": "better",
            "ece": "worse but within bar",
            "spread": "better",
            "rcd": "same (still >0)",
            "succ": "same",
        },
        "serve_replace": False,
        "reason": "Beats serve on AUC/BSS/spread with gate pass, but rcd still +0.000687 and ECE worse than logistic; not clearly better on ALL binding concerns.",
    },
    {
        "artifact": "data/scorer-hard-bilinear-distill48-ld16-gymalt.json",
        "role": "gate_pass_alternate",
        "knobs": {
            "bilinear_distill_hash_dim": 48,
            "bilinear_distill_latent_dim": 16,
            "bilinear_ridge_l2": 0.05,
        },
        "metrics": {
            "replay_gate_pass": True,
            "rank_auc": 0.792,
            "brier_skill": 0.0224,
            "ece_equal_width": 0.029,
            "mean_p_spread": 0.110,
            "rules_cost_delta": 0.000687,
            "trained_success": 0.112,
        },
    },
]
out = ROOT / "data" / "scorer-hard-bilinear-distill48-ld18-gymalt-meta.json"
out.write_text(json.dumps({"date": "2026-08-20", "rows": rows}, indent=2) + "\n", encoding="utf-8")
print("wrote", out)
