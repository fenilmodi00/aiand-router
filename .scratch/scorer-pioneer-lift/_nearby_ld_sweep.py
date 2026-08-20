"""Nearby latent-dim check around gate-passing h48/ld16."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
os.environ["AIAND_TRAIN"] = "1"

from aiand_router.replay_report import apply_replay_gate, replay_report  # noqa: E402
from aiand_router.router import load_config, load_models  # noqa: E402
from aiand_router.train import OPT_IN_ENV, main as train_main  # noqa: E402

os.environ[OPT_IN_ENV] = "1"
cfg = load_config(ROOT / "config" / "models.yaml")
models = load_models(cfg)
gold = str(ROOT / "data" / "gold-sparse-hard-mix1-train-gym-alt-merged.jsonl")
cal = str(ROOT / "data" / "gold-dense-hard-cal-merged.jsonl")
evalg = str(ROOT / "data" / "gold-verified.jsonl")
out_dir = ROOT / "data" / "_sweep_distill"
out_dir.mkdir(parents=True, exist_ok=True)

for ld in [12, 14, 16, 18, 20, 22]:
    out = out_dir / f"fit_gymalt_h48_ld{ld}_r0.05.json"
    rc = train_main(
        [
            "fit",
            "--gold", gold,
            "--cal", cal,
            "--out", str(out),
            "--bilinear",
            "--bilinear-distill-hash-dim", "48",
            "--bilinear-distill-latent-dim", str(ld),
            "--geometry-train", gold,
            "--geometry-eval", evalg,
        ],
        provider=None,
        spend=None,
    )
    if rc != 0:
        print(f"ld={ld} FIT_FAIL")
        continue
    art = json.loads(out.read_text(encoding="utf-8"))
    r = apply_replay_gate(replay_report(evalg, art, models, cfg))
    print(
        f"ld={ld} pass={r['replay_gate_pass']} auc={r['rank_auc']:.3f} "
        f"bss={r['brier_skill']:+.4f} ece={r['ece_equal_width']:.3f} "
        f"spread={r['mean_p_spread']:.3f} rcd={r['rules_cost_delta']:+.6f} "
        f"succ={r['policies']['trained']['success_rate']:.3f}"
    )
