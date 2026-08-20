"""Unpaid medium threshold/max_regret grid on scale retune holdout; check verified."""
from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path

from aiand_router.replay_report import (
    BUDGET,
    _brier_skill,
    _ece_equal_mass,
    _ece_equal_width,
    _load_gold,
    _rank_auc,
)
from aiand_router.router import eligible_models, estimate_cost, load_config, load_models, select_model
from aiand_router.scorer import SHIP_EFFORT, load_scorer, score_eligible, trained_select

ROOT = Path(__file__).resolve().parents[2]
cfg0 = load_config(ROOT / "config" / "models.yaml")
models = load_models(cfg0)
art = load_scorer(ROOT / "data" / "scorer-hard-logistic.json")


def _prompts(path: Path) -> set[str]:
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.add(json.loads(line)["prompt"])
    return out


mix1 = _prompts(ROOT / "data" / "gold-sparse-hard-mix1.jsonl")
cal = _prompts(ROOT / "data" / "gold-dense-hard-cal.jsonl")
retune_items, retune_success = _load_gold(ROOT / "data" / "gold-sparse-hard-scale.jsonl")
retune_items = [it for it in retune_items if it["prompt"] not in mix1 and it["prompt"] not in cal]
ver_items, ver_success = _load_gold(ROOT / "data" / "gold-verified.jsonl")
print("retune n", len(retune_items))


def eval_split(items, success, thr: float, regret: float) -> dict:
    cfg = copy.deepcopy(cfg0)
    cfg["trained_effort"] = dict(SHIP_EFFORT)
    cfg["trained_effort"]["medium"] = {"threshold": thr, "max_regret": regret}
    selected: list[tuple[float, float]] = []
    auc_pairs: list[tuple[float, int]] = []
    spreads: list[float] = []
    disagree = 0
    rules_s = train_s = rules_n = train_n = 0
    costs_r: list[float] = []
    costs_t: list[float] = []
    picks: Counter[str] = Counter()
    for item in items:
        kw = dict(
            phase=item["phase"],
            needs_tools=item["needs_tools"],
            tokens=item["tokens"],
            effort="medium",
            allowed=None,
            spend_usd=0.0,
            budget_usd=BUDGET,
        )
        rules = select_model(cfg, models, **kw)
        tr = trained_select(cfg, models, art, **kw)
        picks[tr.model.id.split("/")[-1]] += 1
        if rules.model.id != tr.model.id:
            disagree += 1
        yr = success.get((item["prompt"], rules.model.id))
        yt = success.get((item["prompt"], tr.model.id))
        if yr is not None:
            rules_n += 1
            rules_s += int(yr)
        if yt is not None:
            train_n += 1
            train_s += int(yt)
        _, elig = eligible_models(cfg, models, **kw)
        costs_r.append(estimate_cost(rules.model, item["tokens"], 800))
        costs_t.append(estimate_cost(tr.model, item["tokens"], 800))
        if tr.confidence is not None and yt is not None:
            selected.append((float(tr.confidence), 1.0 if yt else 0.0))
        _, ps = score_eligible(
            art,
            [m.id for m in elig],
            phase=item["phase"],
            needs_tools=item["needs_tools"],
            tokens=item["tokens"],
        )
        if len(ps) >= 2:
            spreads.append(max(ps.values()) - min(ps.values()))
        for mid in [m.id for m in elig]:
            if (item["prompt"], mid) in success and mid in ps:
                auc_pairs.append(
                    (float(ps[mid]), 1 if success[(item["prompt"], mid)] else 0)
                )
    n = len(items)
    return {
        "n": n,
        "auc": _rank_auc(auc_pairs),
        "spread": (sum(spreads) / len(spreads)) if spreads else 0.0,
        "bss": _brier_skill(selected),
        "ece_w": _ece_equal_width(selected),
        "ece_m": _ece_equal_mass(selected),
        "rules_s": (rules_s / rules_n) if rules_n else 0.0,
        "train_s": (train_s / train_n) if train_n else 0.0,
        "disagree": (disagree / n) if n else 0.0,
        "cost_delta": ((sum(costs_t) - sum(costs_r)) / n) if n else 0.0,
        "picks": dict(picks),
        "n_sel": len(selected),
    }


cands = []
for thr in [0.05, 0.06, 0.07, 0.08, 0.09, 0.10, 0.12, 0.15, 0.18, 0.20]:
    for reg in [0.05, 0.10, 0.15, 0.20, 0.30, 0.50]:
        r = eval_split(retune_items, retune_success, thr, reg)
        score = (
            (1 if r["bss"] > 0 else 0)
            + (1 if r["ece_w"] <= 0.03 else 0)
            + (1 if r["ece_m"] <= 0.03 else 0)
            + (1 if r["train_s"] >= r["rules_s"] - 0.01 else 0)
            + (1 if r["auc"] >= 0.65 else 0)
            + (1 if r["spread"] >= 0.10 else 0)
        )
        cands.append((score, r["bss"], -r["ece_m"], -r["ece_w"], thr, reg, r))

cands.sort(reverse=True)
print("TOP retune:")
for score, bss, _, _, thr, reg, r in cands[:15]:
    print(
        f"  score={score} thr={thr} reg={reg} bss={r['bss']:.4f} "
        f"ece_w={r['ece_w']:.4f} ece_m={r['ece_m']:.4f} auc={r['auc']:.3f} "
        f"spr={r['spread']:.3f} ts={r['train_s']:.3f} rs={r['rules_s']:.3f} "
        f"d={r['disagree']:.2f} picks={r['picks']}"
    )

thr, reg = cands[0][4], cands[0][5]
print("best verified", thr, reg, eval_split(ver_items, ver_success, thr, reg))
print("ship retune", eval_split(retune_items, retune_success, 0.10, 0.20))
print("ship verified", eval_split(ver_items, ver_success, 0.10, 0.20))

# also try any with bss>0 on retune, report verified
print("\nretune bss>0 -> verified:")
seen = set()
for score, bss, _, _, thr, reg, r in cands:
    if r["bss"] <= 0:
        continue
    key = (thr, reg)
    if key in seen:
        continue
    seen.add(key)
    v = eval_split(ver_items, ver_success, thr, reg)
    print(
        f"  thr={thr} reg={reg} retune_bss={r['bss']:.4f} ver_bss={v['bss']:.4f} "
        f"ver_ece_w={v['ece_w']:.4f} ver_ece_m={v['ece_m']:.4f} "
        f"ver_ts={v['train_s']:.3f} picks={v['picks']}"
    )
