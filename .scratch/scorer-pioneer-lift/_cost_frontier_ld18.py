"""Cost threshold frontier on distill ld18 vs logistic serve."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from diagnose_rules_cost_delta import eval_knobs  # noqa: E402
from aiand_router.replay_report import _load_gold  # noqa: E402
from aiand_router.router import load_config, load_models  # noqa: E402
from aiand_router.scorer import load_scorer  # noqa: E402

cfg = load_config(ROOT / "config" / "models.yaml")
models = load_models(cfg)
items, success = _load_gold(ROOT / "data" / "gold-verified.jsonl")

for label, path in [
    ("logistic", "data/scorer-hard-logistic.json"),
    ("distill_ld18", "data/scorer-hard-bilinear-distill48-ld18-gymalt.json"),
]:
    art = load_scorer(ROOT / path)
    print(f"=== {label} ===")
    for th in [0.10, 0.12, 0.13, 0.14, 0.145, 0.15, 0.16]:
        g = eval_knobs(cfg, models, art, items, success, th, 0.20)
        print(
            f"t={th:.3f} pass={g['replay_gate_pass']} "
            f"rcd={g['rules_cost_delta']:+.6f} bss={g['brier_skill']:+.4f} "
            f"ece={g['ece_equal_width']:.3f} spread={g['mean_p_spread']:.3f} "
            f"succ={g['policies']['trained']['success_rate']:.3f}"
        )
