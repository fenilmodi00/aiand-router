"""Probe selected-hop Platt / affine recalibration (unpaid)."""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

from aiand_router.replay_report import (
    BUDGET,
    _brier,
    _brier_skill,
    _ece_equal_mass,
    _ece_equal_width,
    _load_gold,
)
from aiand_router.router import eligible_models, load_config, load_models
from aiand_router.scorer import (
    SHIP_EFFORT,
    _dot,
    _gbdt_z,
    _sigmoid,
    featurize,
    load_scorer,
    predict_complexity_bin,
    trained_select,
)

ROOT = Path(__file__).resolve().parents[2]
cfg = load_config(ROOT / "config" / "models.yaml")
models = load_models(cfg)
art0 = load_scorer(ROOT / "data" / "scorer-hard-logistic.json")


def raw_z(artifact, mid: str, phase: str, needs_tools: bool, tokens: int) -> float | None:
    bin_ = predict_complexity_bin(artifact, phase=phase, needs_tools=needs_tools, tokens=tokens)
    x = featurize(phase, needs_tools, tokens, bin_)
    if artifact.get("gbdt"):
        head = (artifact.get("gbdt") or {}).get(mid)
        if not head:
            return None
        return _gbdt_z(head, x)
    w = (artifact.get("weights") or {}).get(mid)
    ic = (artifact.get("intercepts") or {}).get(mid)
    if w is None or ic is None:
        return None
    return float(ic) + _dot([float(v) for v in w], x)


def selected_pairs(gold_path: Path, artifact: dict, thr=0.10, regret=0.20):
    items, success = _load_gold(gold_path)
    cfg2 = copy.deepcopy(cfg)
    cfg2["trained_effort"] = dict(SHIP_EFFORT)
    cfg2["trained_effort"]["medium"] = {"threshold": thr, "max_regret": regret}
    pairs = []
    zs = []
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
        tr = trained_select(cfg2, models, artifact, **kw)
        y = success.get((item["prompt"], tr.model.id))
        if tr.confidence is None or y is None:
            continue
        z = raw_z(artifact, tr.model.id, item["phase"], item["needs_tools"], item["tokens"])
        pairs.append((float(tr.confidence), 1.0 if y else 0.0))
        if z is not None:
            zs.append((z, 1.0 if y else 0.0))
    return pairs, zs


def fit_platt(zs, ys, steps=80, lr=0.2):
    a, b = 1.0, 0.0
    n = len(zs)
    if n < 2:
        return a, b
    for _ in range(steps):
        ga = gb = 0.0
        for z, y in zip(zs, ys):
            p = _sigmoid(a * z + b)
            err = p - y
            ga += err * z
            gb += err
        a -= lr * ga / n
        b -= lr * gb / n
    return a, b


def metrics(pairs):
    return {
        "n": len(pairs),
        "bss": _brier_skill(pairs),
        "brier": _brier(pairs),
        "ece_w": _ece_equal_width(pairs),
        "ece_m": _ece_equal_mass(pairs),
        "pmean": sum(p for p, _ in pairs) / len(pairs) if pairs else 0,
        "ybar": sum(y for _, y in pairs) / len(pairs) if pairs else 0,
    }


cal_pairs, cal_zs = selected_pairs(ROOT / "data" / "gold-dense-hard-cal.jsonl", art0)
ver_pairs, ver_zs = selected_pairs(ROOT / "data" / "gold-verified.jsonl", art0)
print("baseline cal", metrics(cal_pairs))
print("baseline ver", metrics(ver_pairs))

# refit Platt on selected-hop cal zs
a, b = fit_platt([z for z, _ in cal_zs], [y for _, y in cal_zs])
print("selected-hop platt", a, b, "vs artifact", art0.get("platt"))

art1 = copy.deepcopy(art0)
art1["platt"] = {"a": a, "b": b}
ver2, _ = selected_pairs(ROOT / "data" / "gold-verified.jsonl", art1)
cal2, _ = selected_pairs(ROOT / "data" / "gold-dense-hard-cal.jsonl", art1)
print("after selected platt cal", metrics(cal2))
print("after selected platt ver", metrics(ver2))

# identity platt
art_id = copy.deepcopy(art0)
art_id["platt"] = {"a": 1.0, "b": 0.0}
ver_id, _ = selected_pairs(ROOT / "data" / "gold-verified.jsonl", art_id)
print("identity platt ver", metrics(ver_id))

# shrink toward cal ybar via temperature on probability: p' = ybar + (p-ybar)*t
ybar = metrics(cal_pairs)["ybar"]
for t in [0.0, 0.25, 0.5, 0.75, 1.0]:
    shrunk = [(ybar + t * (p - ybar), y) for p, y in ver_pairs]
    print(f"shrink t={t}", metrics(shrunk))

# constant ybar
const = [(ybar, y) for _, y in ver_pairs]
print("constant cal-ybar on ver", metrics(const))

# fit affine p' = sigmoid(a*logit(p)+b) on cal selected
def logit(p):
    p = min(1 - 1e-6, max(1e-6, p))
    return math.log(p / (1 - p))


a2, b2 = fit_platt([logit(p) for p, _ in cal_pairs], [y for _, y in cal_pairs])
recal = [(_sigmoid(a2 * logit(p) + b2), y) for p, y in ver_pairs]
print("prob-platt", a2, b2, metrics(recal))
