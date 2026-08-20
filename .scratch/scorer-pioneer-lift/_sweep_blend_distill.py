"""Unpaid sweeps: factor-scale and p-blend for distill-gymalt vs logistic."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from aiand_router.replay_report import (  # noqa: E402
    BUDGET,
    COMPLETION_TOKENS,
    EFFORT,
    _ece_equal_width,
    _eligible,
    _load_gold,
    _rank_auc,
    _brier_skill,
    apply_replay_gate,
    replay_report,
)
from aiand_router.router import estimate_cost, load_config, load_models, select_model  # noqa: E402
from aiand_router.scorer import load_scorer, pick_cheapest_above_bar, score_eligible  # noqa: E402


def main() -> None:
    cfg = load_config(ROOT / "config" / "models.yaml")
    models = load_models(cfg)
    log = load_scorer(ROOT / "data" / "scorer-hard-logistic.json")
    bi = load_scorer(ROOT / "data" / "scorer-hard-bilinear-distill48-gymalt.json")
    items, success = _load_gold(ROOT / "data" / "gold-verified.jsonl")

    print("=== factor scale on distill-gymalt ===")
    for scale in [1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0]:
        art = copy.deepcopy(bi)
        for _mid, row in (art.get("bilinear") or {}).get("models", {}).items():
            row["factor"] = [float(v) * scale for v in row["factor"]]
        r = apply_replay_gate(
            replay_report(ROOT / "data" / "gold-verified.jsonl", art, models, cfg)
        )
        print(
            f"scale={scale:.2f} pass={r['replay_gate_pass']} "
            f"auc={r['rank_auc']:.3f} bss={r['brier_skill']:.4f} "
            f"ece={r['ece_equal_width']:.3f} spread={r['mean_p_spread']:.3f} "
            f"rcd={r['rules_cost_delta']:+.6f} "
            f"succ={r['policies']['trained']['success_rate']:.3f}"
        )

    print("=== p-blend logistic + distill-gymalt ===")
    thr = float(cfg.get("trained_effort", {}).get("medium", {}).get("threshold", 0.10))
    mr = float(cfg.get("trained_effort", {}).get("medium", {}).get("max_regret", 0.20))
    for w in [0.0, 0.25, 0.4, 0.5, 0.6, 0.75, 1.0]:
        spreads: list[float] = []
        selected: list[tuple[float, float]] = []
        pairs: list[tuple[float, int]] = []
        trained_picks = []
        rules_picks = []
        for item in items:
            text = str(item.get("prompt") or "")
            elig = _eligible(cfg, models, item)
            ids = [m.id for m in elig]
            _, ps_l = score_eligible(
                log,
                ids,
                phase=item["phase"],
                needs_tools=item["needs_tools"],
                tokens=item["tokens"],
                text=text,
            )
            _, ps_b = score_eligible(
                bi,
                ids,
                phase=item["phase"],
                needs_tools=item["needs_tools"],
                tokens=item["tokens"],
                text=text,
            )
            ps = {i: (1 - w) * float(ps_l.get(i, 0.0)) + w * float(ps_b.get(i, 0.0)) for i in ids}
            if len(ps) >= 2:
                vals = list(ps.values())
                spreads.append(max(vals) - min(vals))
            pick, _ = pick_cheapest_above_bar(elig, ps, threshold=thr, max_regret=mr)
            rules_dec = select_model(
                cfg,
                models,
                phase=item["phase"],
                needs_tools=item["needs_tools"],
                tokens=item["tokens"],
                effort=EFFORT,
                allowed=None,
                spend_usd=0.0,
                budget_usd=BUDGET,
            )
            trained_picks.append(pick)
            rules_picks.append(rules_dec.model)
            if pick is not None:
                y = 1.0 if success.get((item["prompt"], pick.id), False) else 0.0
                selected.append((float(ps[pick.id]), y))
            for mid, p in ps.items():
                pairs.append((float(p), 1 if success.get((item["prompt"], mid), False) else 0))

        tr_s = sum(
            1
            for item, m in zip(items, trained_picks)
            if m and success.get((item["prompt"], m.id), False)
        ) / len(items)
        ru_s = sum(
            1
            for item, m in zip(items, rules_picks)
            if m and success.get((item["prompt"], m.id), False)
        ) / len(items)
        tr_c = sum(
            estimate_cost(m, item["tokens"], COMPLETION_TOKENS)
            for item, m in zip(items, trained_picks)
            if m
        ) / len(items)
        ru_c = sum(
            estimate_cost(m, item["tokens"], COMPLETION_TOKENS)
            for item, m in zip(items, rules_picks)
            if m
        ) / len(items)
        spread = sum(spreads) / len(spreads) if spreads else 0.0
        auc = _rank_auc(pairs)
        bss = _brier_skill(selected)
        ece = _ece_equal_width(selected)
        gate = (
            tr_s >= ru_s - 0.01
            and auc >= 0.65
            and spread >= 0.10
            and bss > 0
            and ece <= 0.03
        )
        print(
            f"w_bi={w:.2f} pass={gate} auc={auc:.3f} bss={bss:.4f} "
            f"ece={ece:.3f} spread={spread:.3f} rcd={tr_c - ru_c:+.6f} succ={tr_s:.3f}"
        )


if __name__ == "__main__":
    main()
