"""Finer unpaid cost–quality frontier on verified replay (medium effort only).

Replay hardcodes EFFORT=medium, so per-effort knobs are not exercised here.
Looks for gate_pass ∧ rcd≤0 with trained success closer to ship 0.112 than overlay 0.090.
Does not mutate serve candidate / models.yaml.
"""

from __future__ import annotations

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
from aiand_router.scorer import load_scorer, score_eligible, trained_select  # noqa: E402

SHIP_T, SHIP_R = 0.10, 0.20
OVERLAY_T, OVERLAY_R = 0.15, 0.20
SHIP_SUCC = 0.11235955056179775
OVERLAY_SUCC = 0.0898876404494382


def conf_hist(cfg, models, artifact, items) -> dict:
    """Kimi confidence under ship knobs (threshold selection pool)."""
    cfg2 = json.loads(json.dumps(cfg))  # deep copy via json
    cfg2.setdefault("trained_effort", {})["medium"] = {
        "threshold": SHIP_T,
        "max_regret": SHIP_R,
    }
    kimi_confs: list[float] = []
    rules: list[str] = []
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
        r = select_model(cfg2, models, **{k: v for k, v in kw.items() if k != "text"})
        t = trained_select(cfg2, models, artifact, **kw)
        rules.append(short(r.model.id))
        if "kimi" in t.model.id and t.confidence is not None:
            kimi_confs.append(float(t.confidence))
    kimi_confs.sort()
    buckets = Counter()
    for c in kimi_confs:
        # 0.005-wide bins from 0.10..0.16
        b = round(int(c * 200) / 200, 3)  # floor to 0.005
        buckets[f"{b:.3f}"] += 1
    return {
        "n_kimi_ship": len(kimi_confs),
        "kimi_conf_min": kimi_confs[0] if kimi_confs else None,
        "kimi_conf_max": kimi_confs[-1] if kimi_confs else None,
        "kimi_conf_unique_sorted": sorted(set(round(c, 6) for c in kimi_confs)),
        "bins_0_005": dict(sorted(buckets.items())),
        "n_above": {
            f">{t:.4f}": sum(1 for c in kimi_confs if c >= t)
            for t in [0.10, 0.12, 0.13, 0.14, 0.142, 0.145, 0.148, 0.149, 0.15, 0.152, 0.155]
        },
        "rules_mix": dict(Counter(rules)),
    }


def mix_at(cfg, models, artifact, items, success, th: float, mr: float) -> dict:
    cfg2 = json.loads(json.dumps(cfg))
    cfg2.setdefault("trained_effort", {})["medium"] = {"threshold": th, "max_regret": mr}
    mix: Counter[str] = Counter()
    reason: Counter[str] = Counter()
    succ = 0
    deltas = []
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
        rules = select_model(cfg2, models, **{k: v for k, v in kw.items() if k != "text"})
        trained = trained_select(cfg2, models, artifact, **kw)
        mix[short(trained.model.id)] += 1
        reason[trained.rule] += 1
        deltas.append(
            estimate_cost(trained.model, item["tokens"], COMPLETION_TOKENS)
            - estimate_cost(rules.model, item["tokens"], COMPLETION_TOKENS)
        )
        if success.get((item["prompt"], trained.model.id)):
            succ += 1
    return {
        "mix": dict(mix),
        "reason": dict(reason),
        "mean_delta": sum(deltas) / len(deltas) if deltas else 0.0,
        "succ": succ / len(items) if items else 0.0,
    }


def main() -> None:
    cfg = load_config(ROOT / "config" / "models.yaml")
    models = load_models(cfg)
    artifact = load_scorer(ROOT / "data" / "scorer-hard-logistic.json")
    items, success = _load_gold(ROOT / "data" / "gold-verified.jsonl")

    hist = conf_hist(cfg, models, artifact, items)
    print("=== kimi confidence under ship knobs ===")
    print(json.dumps(hist, indent=2))

    # Dense threshold grid around cliff + broader anchors; finer max_regret
    thresholds = [
        0.10,
        0.12,
        0.13,
        0.135,
        0.14,
        0.141,
        0.142,
        0.143,
        0.144,
        0.145,
        0.146,
        0.147,
        0.148,
        0.149,
        0.1495,
        0.15,
        0.151,
        0.152,
        0.155,
        0.16,
    ]
    regrets = [0.03, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]

    print("\n=== fine frontier (medium only; replay EFFORT=medium) ===")
    rows = []
    for th in thresholds:
        for mr in regrets:
            g = eval_knobs(cfg, models, artifact, items, success, th, mr)
            tr = g["policies"]["trained"]["success_rate"]
            row = {
                "t": th,
                "r": mr,
                "pass": g["replay_gate_pass"],
                "rcd": g["rules_cost_delta"],
                "bss": g["brier_skill"],
                "auc": g["rank_auc"],
                "spread": g["mean_p_spread"],
                "tr": tr,
                "ru": g["policies"]["rules"]["success_rate"],
                "save": g["savings_vs_most_expensive"],
                "ece_w": g["ece_equal_width"],
                "n_selected": g["n_selected"],
                "succ_vs_ship": tr - SHIP_SUCC,
                "succ_vs_overlay": tr - OVERLAY_SUCC,
                "closer_to_ship_than_overlay": abs(tr - SHIP_SUCC) < abs(tr - OVERLAY_SUCC),
            }
            rows.append(row)

    # Deduplicate identical policy outcomes for readability (same tr/rcd/pass/n_sel)
    unique_keys = {}
    for r in rows:
        key = (round(r["rcd"], 12), round(r["tr"], 12), r["pass"], r["n_selected"], round(r["bss"], 12))
        unique_keys.setdefault(key, []).append((r["t"], r["r"]))

    print("\nunique policy outcomes (t,r groups):")
    for key, pairs in unique_keys.items():
        rcd, tr, passed, n_sel, bss = key
        print(
            f"  rcd={rcd:+.6f} tr={tr:.4f} pass={passed} n_sel={n_sel} bss={bss:.6f} "
            f"pairs={pairs[:6]}{'...' if len(pairs) > 6 else ''}"
        )

    safe = [r for r in rows if r["pass"] and r["rcd"] <= 0]
    # Prefer success closest to ship (maximize tr), then least |rcd| overshoot, then ship-like regret
    safe.sort(key=lambda r: (-r["tr"], abs(r["rcd"]), -r["r"] if r["r"] == SHIP_R else 1, r["t"]))

    better_than_overlay = [
        r
        for r in safe
        if r["tr"] > OVERLAY_SUCC + 1e-12 and r["closer_to_ship_than_overlay"]
    ]

    # Mix snapshots at key points
    mix_ship = mix_at(cfg, models, artifact, items, success, SHIP_T, SHIP_R)
    mix_overlay = mix_at(cfg, models, artifact, items, success, OVERLAY_T, OVERLAY_R)
    mix_pre = mix_at(cfg, models, artifact, items, success, 0.149, SHIP_R)
    mix_pre2 = mix_at(cfg, models, artifact, items, success, 0.1495, SHIP_R)

    # Best gate-pass with rcd>0 but lower rcd than ship (partial cost progress)
    partial = [r for r in rows if r["pass"] and r["rcd"] > 0]
    partial.sort(key=lambda r: (r["rcd"], -r["tr"]))

    out = {
        "replay_effort": EFFORT,
        "per_effort_note": (
            "Verified replay_report hardcodes EFFORT=medium; low/high/max knobs "
            "are not evaluated on this holdout. Per-effort overlay unsupported here."
        ),
        "ship": {"t": SHIP_T, "r": SHIP_R, "succ": SHIP_SUCC, "mix": mix_ship},
        "overlay_t015": {"t": OVERLAY_T, "r": OVERLAY_R, "succ": OVERLAY_SUCC, "mix": mix_overlay},
        "kimi_confidence": hist,
        "mix_t0149": mix_pre,
        "mix_t01495": mix_pre2,
        "n_grid": len(rows),
        "n_safe_rcd_le0_gate": len(safe),
        "n_better_than_overlay_toward_ship": len(better_than_overlay),
        "best_safe": safe[0] if safe else None,
        "best_better_than_overlay": better_than_overlay[0] if better_than_overlay else None,
        "best_partial_cost_gate_pass": partial[0] if partial else None,
        "unique_outcomes": [
            {
                "rcd": k[0],
                "tr": k[1],
                "pass": k[2],
                "n_selected": k[3],
                "bss": k[4],
                "knob_pairs": v,
            }
            for k, v in unique_keys.items()
        ],
        "frontier_rows": rows,
        "verdict": (
            "FOUND intermediate overlay"
            if better_than_overlay
            else "FALSIFIED: no unpaid medium knob clears rcd<=0 with succ closer to ship than t=0.15"
        ),
    }

    out_path = ROOT / "data" / "cost-frontier-fine-2026-08-20.json"
    out_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print("\n=== verdict ===")
    print(out["verdict"])
    print("best_safe:", out["best_safe"])
    print("best_better_than_overlay:", out["best_better_than_overlay"])
    print("best_partial:", out["best_partial_cost_gate_pass"])
    print("Wrote", out_path)


if __name__ == "__main__":
    main()
