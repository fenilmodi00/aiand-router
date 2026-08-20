"""Unpaid replay table: bilinear variants vs serve logistic."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from aiand_router.replay_report import build_report  # noqa: E402
from aiand_router.router import load_config, load_models  # noqa: E402
from aiand_router.scorer import load_scorer  # noqa: E402


def main() -> None:
    cfg = load_config(ROOT / "config" / "models.yaml")
    models = load_models(cfg)
    arts = [
        "data/scorer-hard-logistic.json",
        "data/scorer-hard-bilinear.json",
        "data/scorer-hard-bilinear-matched-cal.json",
        "data/scorer-hard-bilinear-hash32.json",
        "data/scorer-hard-bilinear-distill48.json",
        "data/scorer-hard-bilinear-distill48-gymalt.json",
    ]
    hdr = (
        f"{'artifact':48} {'pass':5} {'auc':7} {'bss':9} "
        f"{'ece_w':7} {'spread':7} {'rcd':10} {'succ':7}"
    )
    print(hdr)
    for p in arts:
        art = load_scorer(ROOT / p)
        r = build_report(ROOT / "data" / "gold-verified.jsonl", art, models, cfg)
        pol = r.get("policies", {}).get("trained", {})
        print(
            f"{p:48} {str(r.get('replay_gate_pass')):5} "
            f"{float(r.get('rank_auc') or 0):7.3f} "
            f"{float(r.get('brier_skill') or 0):9.4f} "
            f"{float(r.get('ece_equal_width') or 0):7.3f} "
            f"{float(r.get('mean_p_spread') or 0):7.3f} "
            f"{float(r.get('rules_cost_delta') or 0):+10.6f} "
            f"{float(pol.get('success_rate') or 0):7.3f}"
        )
        meta = (art or {}).get("bilinear") or {}
        if meta:
            distill = meta.get("distill") or {}
            print(
                f"  hash_dim={meta.get('hash_dim')} "
                f"distill={distill.get('mode')} "
                f"teacher={meta.get('teacher_hash_dim')} "
                f"dim={meta.get('dim')} "
                f"n_gold={(art or {}).get('n_gold')} "
                f"n_cal={(art or {}).get('n_cal')}"
            )


if __name__ == "__main__":
    main()
