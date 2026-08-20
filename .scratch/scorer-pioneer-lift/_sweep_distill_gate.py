"""Unpaid joint sweep: distill knobs + post-hoc cal aiming at gate vs serve.

Targets: mean_p_spread>=0.10, ece_equal_width<=0.03, replay_gate_pass,
prefer rules_cost_delta<=0 and BSS > serve logistic.
"""

from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from aiand_router.replay_report import (  # noqa: E402
    BUDGET,
    COMPLETION_TOKENS,
    EFFORT,
    _brier_skill,
    _ece_equal_width,
    _eligible,
    _load_gold,
    _rank_auc,
    apply_replay_gate,
    replay_report,
)
from aiand_router.router import estimate_cost, load_config, load_models, select_model  # noqa: E402
from aiand_router.scorer import load_scorer, pick_cheapest_above_bar, score_eligible  # noqa: E402
from aiand_router.train import OPT_IN_ENV, main as train_main  # noqa: E402

GOLD_EVAL = ROOT / "data" / "gold-verified.jsonl"
MODELS = ROOT / "config" / "models.yaml"
SERVE = ROOT / "data" / "scorer-hard-logistic.json"
DISTILL = ROOT / "data" / "scorer-hard-bilinear-distill48-gymalt.json"
CAL = ROOT / "data" / "gold-dense-hard-cal-merged.jsonl"
GOLD_GYM = ROOT / "data" / "gold-sparse-hard-mix1-train-gym-alt-merged.jsonl"
GOLD_MIX1 = ROOT / "data" / "gold-sparse-hard-mix1-train.jsonl"
OUT_DIR = ROOT / "data" / "_sweep_distill"
META_OUT = ROOT / ".scratch" / "scorer-pioneer-lift" / "distill-gate-sweep-2026-08-20.json"


def _metrics(art: dict) -> dict:
    r = apply_replay_gate(replay_report(GOLD_EVAL, art, load_models(load_config(MODELS)), load_config(MODELS)))
    return {
        "pass": bool(r["replay_gate_pass"]),
        "auc": float(r["rank_auc"]),
        "bss": float(r["brier_skill"]),
        "ece": float(r["ece_equal_width"]),
        "spread": float(r["mean_p_spread"]),
        "rcd": float(r["rules_cost_delta"]),
        "succ": float(r["policies"]["trained"]["success_rate"]),
    }


def _fmt(tag: str, m: dict) -> str:
    return (
        f"{tag:48s} pass={m['pass']} auc={m['auc']:.3f} bss={m['bss']:+.4f} "
        f"ece={m['ece']:.3f} spread={m['spread']:.3f} rcd={m['rcd']:+.6f} "
        f"succ={m['succ']:.3f}"
    )


def _scale_factors(art: dict, scale: float) -> dict:
    out = copy.deepcopy(art)
    for row in (out.get("bilinear") or {}).get("models", {}).values():
        row["factor"] = [float(v) * scale for v in row["factor"]]
    return out


def _set_platt(art: dict, a: float, b: float) -> dict:
    out = copy.deepcopy(art)
    out["platt"] = {"a": a, "b": b}
    out["calibrator"] = {"mode": "platt", "a": a, "b": b}
    return out


def _temp_platt(art: dict, t: float) -> dict:
    """Temperature on calibrated logits: a' = a/T (T>1 softens)."""
    a, b = float(art["platt"]["a"]), float(art["platt"]["b"])
    return _set_platt(art, a / t, b)


def _blend_report(log: dict, bi: dict, w_bi: float, cfg, models, items, success) -> dict:
    thr = float(cfg.get("trained_effort", {}).get("medium", {}).get("threshold", 0.10))
    mr = float(cfg.get("trained_effort", {}).get("medium", {}).get("max_regret", 0.20))
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
            log, ids, phase=item["phase"], needs_tools=item["needs_tools"],
            tokens=item["tokens"], text=text,
        )
        _, ps_b = score_eligible(
            bi, ids, phase=item["phase"], needs_tools=item["needs_tools"],
            tokens=item["tokens"], text=text,
        )
        ps = {i: (1 - w_bi) * float(ps_l.get(i, 0.0)) + w_bi * float(ps_b.get(i, 0.0)) for i in ids}
        if len(ps) >= 2:
            vals = list(ps.values())
            spreads.append(max(vals) - min(vals))
        pick, _ = pick_cheapest_above_bar(elig, ps, threshold=thr, max_regret=mr)
        rules_dec = select_model(
            cfg, models, phase=item["phase"], needs_tools=item["needs_tools"],
            tokens=item["tokens"], effort=EFFORT, allowed=None, spend_usd=0.0, budget_usd=BUDGET,
        )
        trained_picks.append(pick)
        rules_picks.append(rules_dec.model)
        if pick is not None:
            y = 1.0 if success.get((item["prompt"], pick.id), False) else 0.0
            selected.append((float(ps[pick.id]), y))
        for mid, p in ps.items():
            pairs.append((float(p), 1 if success.get((item["prompt"], mid), False) else 0))
    n = max(1, len(items))
    tr_s = sum(
        1 for item, m in zip(items, trained_picks)
        if m and success.get((item["prompt"], m.id), False)
    ) / n
    ru_s = sum(
        1 for item, m in zip(items, rules_picks)
        if m and success.get((item["prompt"], m.id), False)
    ) / n
    tr_c = sum(
        estimate_cost(m, item["tokens"], COMPLETION_TOKENS)
        for item, m in zip(items, trained_picks) if m
    ) / n
    ru_c = sum(
        estimate_cost(m, item["tokens"], COMPLETION_TOKENS)
        for item, m in zip(items, rules_picks) if m
    ) / n
    spread = sum(spreads) / len(spreads) if spreads else 0.0
    auc = _rank_auc(pairs)
    bss = _brier_skill(selected)
    ece = _ece_equal_width(selected)
    gate = tr_s >= ru_s - 0.01 and auc >= 0.65 and spread >= 0.10 and bss > 0 and ece <= 0.03
    return {
        "pass": gate, "auc": auc, "bss": bss, "ece": ece, "spread": spread,
        "rcd": tr_c - ru_c, "succ": tr_s,
    }


def _fit_distill(
    gold: Path,
    out: Path,
    *,
    hash_dim: int,
    latent_dim: int = 0,
    ridge_l2: float = 0.05,
) -> dict | None:
    os.environ[OPT_IN_ENV] = "1"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    argv = [
        "fit",
        "--gold", str(gold),
        "--cal", str(CAL),
        "--out", str(out),
        "--bilinear",
        "--bilinear-distill-hash-dim", str(hash_dim),
        "--geometry-train", str(gold),
        "--geometry-eval", str(GOLD_EVAL),
    ]
    if latent_dim > 0:
        argv.extend(["--bilinear-distill-latent-dim", str(latent_dim)])
    if abs(ridge_l2 - 0.05) > 1e-12:
        argv.extend(["--bilinear-ridge-l2", str(ridge_l2)])
    rc = train_main(argv, provider=None, spend=None)
    if rc != 0:
        return None
    return json.loads(out.read_text(encoding="utf-8"))


def main() -> None:
    cfg = load_config(MODELS)
    models = load_models(cfg)
    items, success = _load_gold(GOLD_EVAL)
    serve = load_scorer(SERVE)
    bi = load_scorer(DISTILL)
    rows: list[dict] = []

    print("=== baselines ===")
    for tag, art in [("serve_logistic", serve), ("distill48_gymalt", bi)]:
        m = _metrics(art)
        print(_fmt(tag, m))
        rows.append({"tag": tag, **m})

    print("=== post-hoc temperature on distill ===")
    for t in [0.5, 0.7, 0.85, 1.0, 1.15, 1.3, 1.5, 2.0, 2.5]:
        m = _metrics(_temp_platt(bi, t))
        tag = f"temp={t:.2f}"
        print(_fmt(tag, m))
        rows.append({"tag": tag, **m})

    print("=== factor scale × temperature ===")
    for scale in [1.0, 1.25, 1.5, 1.75, 2.0, 2.5]:
        for t in [0.7, 1.0, 1.3, 1.7, 2.2]:
            art = _temp_platt(_scale_factors(bi, scale), t)
            m = _metrics(art)
            tag = f"scale={scale:.2f}_temp={t:.2f}"
            print(_fmt(tag, m))
            rows.append({"tag": tag, **m})

    print("=== platt a rescale (keep b) ===")
    a0, b0 = float(bi["platt"]["a"]), float(bi["platt"]["b"])
    for a_mult in [0.4, 0.6, 0.8, 1.0, 1.25, 1.5, 2.0]:
        m = _metrics(_set_platt(bi, a0 * a_mult, b0))
        tag = f"a_mult={a_mult:.2f}"
        print(_fmt(tag, m))
        rows.append({"tag": tag, **m})

    print("=== p-blend logistic + distill (and tempered distill) ===")
    for t in [1.0, 1.5]:
        bi_t = _temp_platt(bi, t) if t != 1.0 else bi
        for w in [0.0, 0.2, 0.35, 0.5, 0.65, 0.8, 1.0]:
            m = _blend_report(serve, bi_t, w, cfg, models, items, success)
            tag = f"blend_w={w:.2f}_temp={t:.1f}"
            print(_fmt(tag, m))
            rows.append({"tag": tag, **m})

    print("=== retrain distill grid ===")
    grid = [
        ("gymalt", GOLD_GYM, 32, 0, 0.05),
        ("gymalt", GOLD_GYM, 48, 0, 0.05),
        ("gymalt", GOLD_GYM, 48, 16, 0.05),
        ("gymalt", GOLD_GYM, 48, 24, 0.05),
        ("gymalt", GOLD_GYM, 48, 48, 0.05),
        ("gymalt", GOLD_GYM, 64, 24, 0.05),
        ("gymalt", GOLD_GYM, 64, 32, 0.1),
        ("gymalt", GOLD_GYM, 96, 32, 0.05),
        ("gymalt", GOLD_GYM, 48, 24, 0.02),
        ("gymalt", GOLD_GYM, 48, 24, 0.2),
        ("mix1", GOLD_MIX1, 48, 24, 0.05),
        ("mix1", GOLD_MIX1, 48, 0, 0.05),
        ("mix1", GOLD_MIX1, 64, 32, 0.1),
    ]
    for subset, gold, hdim, ldim, ridge in grid:
        name = f"fit_{subset}_h{hdim}_ld{ldim or 'def'}_r{ridge}"
        out = OUT_DIR / f"{name}.json"
        print(f"fitting {name} ...", flush=True)
        art = _fit_distill(gold, out, hash_dim=hdim, latent_dim=ldim, ridge_l2=ridge)
        if art is None:
            print(f"{name:48s} FIT_FAIL")
            rows.append({"tag": name, "pass": False, "fit_fail": True})
            continue
        m = _metrics(art)
        print(_fmt(name, m))
        rows.append({"tag": name, "path": str(out), **m})
        # Best-effort post-hoc temper on each retrain
        for t in [1.3, 1.7]:
            mt = _metrics(_temp_platt(art, t))
            tag = f"{name}_temp={t:.1f}"
            print(_fmt(tag, mt))
            rows.append({"tag": tag, "path": str(out), **mt})

    winners = [r for r in rows if r.get("pass")]
    near = sorted(
        [r for r in rows if not r.get("fit_fail")],
        key=lambda r: (
            0 if r.get("pass") else 1,
            abs(r.get("spread", 0) - 0.10) + abs(r.get("ece", 1) - 0.03),
            -r.get("bss", -99),
        ),
    )[:15]

    payload = {
        "serve_tag": "serve_logistic",
        "n_rows": len(rows),
        "n_pass": len(winners),
        "winners": winners,
        "near": near,
        "all": rows,
    }
    META_OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nwinners={len(winners)} wrote {META_OUT}")
    for w in winners[:10]:
        print(_fmt(w["tag"], w))


if __name__ == "__main__":
    main()
