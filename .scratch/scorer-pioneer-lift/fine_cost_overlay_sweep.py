"""Fine sweep around cost-fixing threshold for hard-logistic shadow overlay."""

from __future__ import annotations

import copy
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from diagnose_rules_cost_delta import eval_knobs, short  # noqa: E402
from aiand_router.replay_report import (  # noqa: E402
    BUDGET,
    COMPLETION_TOKENS,
    EFFORT,
    _load_gold,
)
from aiand_router.router import estimate_cost, load_config, load_models, select_model  # noqa: E402
from aiand_router.scorer import load_scorer, trained_select  # noqa: E402


def main() -> None:
    cfg = load_config(ROOT / "config" / "models.yaml")
    models = load_models(cfg)
    artifact = load_scorer(ROOT / "data" / "scorer-hard-logistic.json")
    items, success = _load_gold(ROOT / "data" / "gold-verified.jsonl")

    print("=== fine threshold sweep ===")
    rows = []
    for th in [0.10, 0.11, 0.12, 0.13, 0.14, 0.145, 0.15, 0.155, 0.16, 0.17]:
        for mr in [0.03, 0.20]:
            g = eval_knobs(cfg, models, artifact, items, success, th, mr)
            row = {
                "t": th,
                "r": mr,
                "pass": g["replay_gate_pass"],
                "rcd": g["rules_cost_delta"],
                "bss": g["brier_skill"],
                "auc": g["rank_auc"],
                "spread": g["mean_p_spread"],
                "tr": g["policies"]["trained"]["success_rate"],
                "ru": g["policies"]["rules"]["success_rate"],
                "save": g["savings_vs_most_expensive"],
                "ece_w": g["ece_equal_width"],
            }
            rows.append(row)
            print(
                f"t={th:.3f} r={mr:.2f} pass={row['pass']} rcd={row['rcd']:+.6f} "
                f"bss={row['bss']:.6f} tr={row['tr']:.4f} save={row['save']:.6f}"
            )

    print("\n=== pick mix ===")
    for th, mr, label in [
        (0.10, 0.20, "ship"),
        (0.15, 0.03, "overlay_tight_r"),
        (0.15, 0.20, "overlay_ship_r"),
        (0.14, 0.20, "t014"),
        (0.13, 0.20, "t013"),
    ]:
        cfg2 = copy.deepcopy(cfg)
        cfg2["trained_effort"]["medium"] = {"threshold": th, "max_regret": mr}
        mix: Counter[str] = Counter()
        fb = thr = regret = 0
        deltas = []
        succ = 0
        for item in items:
            text = str(item.get("prompt") or "")
            kw = dict(
                phase=item["phase"],
                needs_tools=item["needs_tools"],
                tokens=item["tokens"],
                effort=EFFORT,
                allowed=None,
                spend_usd=0.0,
                budget_usd=BUDGET,
                text=text,
            )
            rules = select_model(
                cfg2, models, **{k: v for k, v in kw.items() if k != "text"}
            )
            trained = trained_select(cfg2, models, artifact, **kw)
            mix[short(trained.model.id)] += 1
            if trained.rule == "fallback_declined":
                fb += 1
            elif trained.rule == "threshold":
                thr += 1
            elif trained.rule == "max_regret":
                regret += 1
            deltas.append(
                estimate_cost(trained.model, item["tokens"], COMPLETION_TOKENS)
                - estimate_cost(rules.model, item["tokens"], COMPLETION_TOKENS)
            )
            if success.get((item["prompt"], trained.model.id)):
                succ += 1
        print(
            label,
            "mix=",
            dict(mix),
            "fb=",
            fb,
            "thr=",
            thr,
            "regret=",
            regret,
            "mean_d=",
            round(sum(deltas) / len(deltas), 6),
            "succ=",
            round(succ / len(items), 4),
        )

    out = ROOT / "data" / "scorer-hard-logistic-cost-overlay-meta.json"
    # Prefer lowest r among rcd<=0 gate-pass with highest tr success, then highest bss
    safe = [r for r in rows if r["pass"] and r["rcd"] <= 0]
    safe.sort(key=lambda r: (-r["tr"], -r["bss"], r["r"], r["t"]))
    meta = {
        "base_artifact": "data/scorer-hard-logistic.json",
        "serve_candidate": False,
        "shadow_experiment": True,
        "note": (
            "Unpaid medium effort overlay: raise threshold so kimi below bar declines "
            "to flash fallback; clears rules_cost_delta on verified replay without "
            "retuning. Does not replace serve candidate."
        ),
        "recommended_overlay": (
            safe[0]
            if safe
            else None
        ),
        "ship_baseline": next(r for r in rows if r["t"] == 0.10 and r["r"] == 0.20),
        "fine_sweep": rows,
    }
    # Prefer t=0.15 with ship-like max_regret=0.20 if present in safe (same metrics)
    preferred = [r for r in safe if r["t"] == 0.15 and r["r"] == 0.20]
    if preferred:
        meta["recommended_overlay"] = preferred[0]
    elif safe:
        meta["recommended_overlay"] = safe[0]
    out.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print("\nWrote", out)
    print("recommended", meta["recommended_overlay"])


if __name__ == "__main__":
    main()
