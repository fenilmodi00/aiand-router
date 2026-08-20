"""Phase 4 probes for gate-fail hypotheses. Tag: [DEBUG-gate06]"""
from __future__ import annotations

import json
from pathlib import Path

from aiand_router.replay_report import (
    _eligible,
    _load_gold,
    _rank_auc,
    _brier_skill,
    _ece_equal_width,
    BUDGET,
    EFFORT,
    replay_report,
)
from aiand_router.router import load_config, load_models, select_model
from aiand_router.scorer import (
    _calibrator_ab,
    _gbdt_z,
    _sigmoid,
    featurize,
    load_scorer,
    predict_complexity_bin,
    score_eligible,
    trained_select,
)


def main() -> None:
    cfg = load_config(Path("config/models.yaml"))
    models = load_models(cfg)
    art = load_scorer(Path("data/scorer.json"))
    assert art is not None
    items, success = _load_gold(Path("data/gold-verified.jsonl"))
    raw = [
        json.loads(l)
        for l in Path("data/gold-verified.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    hint = {}
    for r in raw:
        hint.setdefault(r["prompt"], str(r.get("hint_bin") or "standard"))

    # H4: hint vs predicted bin AUC
    def auc_for(use_hint: bool) -> float:
        pairs = []
        a, b = _calibrator_ab(art)
        gbdt = art.get("gbdt") or {}
        intercepts = art.get("intercepts") or {}
        table = art.get("p_success") or {}
        for item in items:
            bin_ = (
                hint[item["prompt"]]
                if use_hint
                else predict_complexity_bin(
                    art,
                    phase=item["phase"],
                    needs_tools=item["needs_tools"],
                    tokens=item["tokens"],
                )
            )
            x = featurize(item["phase"], item["needs_tools"], item["tokens"], bin_)
            for m in _eligible(cfg, models, item):
                mid = m.id
                if (item["prompt"], mid) not in success:
                    continue
                if mid in gbdt and (not intercepts or mid in intercepts):
                    p = _sigmoid(a * _gbdt_z(gbdt[mid], x) + b)
                elif mid in table:
                    p = float(table[mid])
                else:
                    continue
                pairs.append((p, 1 if success[(item["prompt"], mid)] else 0))
        return _rank_auc(pairs)

    agree = sum(
        1
        for item in items
        if predict_complexity_bin(
            art,
            phase=item["phase"],
            needs_tools=item["needs_tools"],
            tokens=item["tokens"],
        )
        == hint[item["prompt"]]
    )
    print("[DEBUG-gate06] H4 bin_agree", agree, "/", len(items))
    print("[DEBUG-gate06] H4 auc_pred", auc_for(False))
    print("[DEBUG-gate06] H4 auc_hint", auc_for(True))

    # H2: how many clear medium threshold; would higher theta change picks?
    clear_counts = {0.10: 0, 0.30: 0, 0.50: 0, 0.55: 0, 0.60: 0}
    flash_below = {t: 0 for t in clear_counts}
    for item in items:
        eligible = _eligible(cfg, models, item)
        _, ps = score_eligible(
            art,
            [m.id for m in eligible],
            phase=item["phase"],
            needs_tools=item["needs_tools"],
            tokens=item["tokens"],
        )
        flash_p = ps.get("deepseek-ai/deepseek-v4-flash")
        for t in clear_counts:
            survivors = [mid for mid, p in ps.items() if p >= t]
            if survivors:
                clear_counts[t] += 1
            if flash_p is not None and flash_p < t:
                flash_below[t] += 1
    print("[DEBUG-gate06] H2 prompts_with_survivor", clear_counts)
    print("[DEBUG-gate06] H2 flash_below_theta", flash_below)

    # H5: mean P by model vs holdout y
    from collections import defaultdict

    sum_p = defaultdict(float)
    n_p = defaultdict(int)
    for item in items:
        eligible = _eligible(cfg, models, item)
        _, ps = score_eligible(
            art,
            [m.id for m in eligible],
            phase=item["phase"],
            needs_tools=item["needs_tools"],
            tokens=item["tokens"],
        )
        for mid, p in ps.items():
            if (item["prompt"], mid) in success:
                sum_p[mid] += p
                n_p[mid] += 1
    print("[DEBUG-gate06] H5 mean_P vs holdout")
    for mid in sorted(n_p):
        ys = [
            1 if success[(it["prompt"], mid)] else 0
            for it in items
            if (it["prompt"], mid) in success
        ]
        print(
            f"  {mid}: mean_P={sum_p[mid]/n_p[mid]:.3f} holdout_y={sum(ys)/len(ys):.3f} n={len(ys)}"
        )

    # H3: confirm cost bar unreachable
    n_rules_not_cheap = 0
    from aiand_router.replay_report import _pick_cheapest

    for item in items:
        eligible = _eligible(cfg, models, item)
        kw = dict(
            phase=item["phase"],
            needs_tools=item["needs_tools"],
            tokens=item["tokens"],
            effort=EFFORT,
            allowed=None,
            spend_usd=0.0,
            budget_usd=BUDGET,
        )
        r = select_model(cfg, models, **kw)
        c = _pick_cheapest(eligible)
        if c and r.model.id != c.id:
            n_rules_not_cheap += 1
    print("[DEBUG-gate06] H3 rules_not_cheapest", n_rules_not_cheap, "of", len(items))

    # H1: selected-hop P vs y for trained (always Flash)
    selected = []
    for item in items:
        kw = dict(
            phase=item["phase"],
            needs_tools=item["needs_tools"],
            tokens=item["tokens"],
            effort=EFFORT,
            allowed=None,
            spend_usd=0.0,
            budget_usd=BUDGET,
        )
        t = trained_select(cfg, models, art, **kw)
        y = success.get((item["prompt"], t.model.id))
        if t.confidence is not None and y is not None:
            selected.append((float(t.confidence), 1.0 if y else 0.0))
    mean_p = sum(p for p, _ in selected) / len(selected)
    mean_y = sum(y for _, y in selected) / len(selected)
    print(
        "[DEBUG-gate06] H1 selected mean_P",
        round(mean_p, 4),
        "mean_y",
        round(mean_y, 4),
        "brier_skill",
        _brier_skill(selected),
        "ece_w",
        _ece_equal_width(selected),
    )

    # Counterfactual: rescale Platt bias so mean P ~= mean y (calibrate level only)
    # Find b' such that sigmoid(a*z + b') has mean ~ mean_y — approximate via shifting b
    a, b = _calibrator_ab(art)
    # raw z for flash picks
    zs = []
    for item in items:
        eligible = _eligible(cfg, models, item)
        bin_ = predict_complexity_bin(
            art,
            phase=item["phase"],
            needs_tools=item["needs_tools"],
            tokens=item["tokens"],
        )
        x = featurize(item["phase"], item["needs_tools"], item["tokens"], bin_)
        head = (art.get("gbdt") or {}).get("deepseek-ai/deepseek-v4-flash")
        if head:
            zs.append(_gbdt_z(head, x))
    # grid search b
    best = None
    for b2 in [i / 10 for i in range(-40, 20)]:
        sel = [(_sigmoid(a * z + b2), mean_y) for z in zs]  # placeholder
        # rebuild with real y
        sel2 = []
        i = 0
        for item in items:
            head = (art.get("gbdt") or {}).get("deepseek-ai/deepseek-v4-flash")
            if not head:
                continue
            bin_ = predict_complexity_bin(
                art,
                phase=item["phase"],
                needs_tools=item["needs_tools"],
                tokens=item["tokens"],
            )
            x = featurize(item["phase"], item["needs_tools"], item["tokens"], bin_)
            z = _gbdt_z(head, x)
            y = success.get((item["prompt"], "deepseek-ai/deepseek-v4-flash"))
            if y is None:
                continue
            sel2.append((_sigmoid(a * z + b2), 1.0 if y else 0.0))
        bs = _brier_skill(sel2)
        ece = _ece_equal_width(sel2)
        mp = sum(p for p, _ in sel2) / len(sel2)
        if best is None or abs(mp - mean_y) < abs(best[0] - mean_y):
            best = (mp, b2, bs, ece)
    print("[DEBUG-gate06] H1 best_level_match", best)


if __name__ == "__main__":
    main()
