"""[DEBUG-gate06] train vs holdout geometry"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from aiand_router.replay_report import _eligible, _load_gold
from aiand_router.router import load_config, load_models
from aiand_router.scorer import load_scorer, score_eligible


def rates(path: str) -> dict[str, float]:
    rows = [
        json.loads(l)
        for l in Path(path).read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    ok: dict[str, int] = defaultdict(int)
    n: dict[str, int] = defaultdict(int)
    for r in rows:
        if "model_id" not in r or r.get("unobserved"):
            continue
        mid = r["model_id"]
        n[mid] += 1
        ok[mid] += int(bool(r.get("success")))
    return {m: ok[m] / n[m] for m in n}


def spearman_sign(a: dict[str, float], b: dict[str, float], ids: list[str]) -> float:
    conc = disc = 0
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            da = a[ids[i]] - a[ids[j]]
            db = b[ids[i]] - b[ids[j]]
            if da * db > 0:
                conc += 1
            elif da * db < 0:
                disc += 1
    return (conc - disc) / (conc + disc) if conc + disc else 0.0


def main() -> None:
    sp = rates("data/gold-sparse-400.jsonl")
    de = rates("data/gold-dense-100.jsonl")
    ve = rates("data/gold-verified.jsonl")
    ids = sorted(set(sp) & set(ve))
    print("[DEBUG-gate06] model sparse dense verified")
    for m in ids:
        print(f"  {m}: {sp[m]:.3f}  {de.get(m, float('nan')):.3f}  {ve[m]:.3f}")
    print("[DEBUG-gate06] spearman_sparse_vs_verified", spearman_sign(sp, ve, ids))
    print("[DEBUG-gate06] spearman_dense_vs_verified", spearman_sign(de, ve, ids))

    cfg = load_config(Path("config/models.yaml"))
    models = load_models(cfg)
    art = load_scorer(Path("data/scorer.json"))
    items, _ = _load_gold(Path("data/gold-verified.jsonl"))
    vals: dict[str, list[float]] = defaultdict(list)
    trio = {
        "deepseek-ai/deepseek-v4-flash",
        "moonshotai/kimi-k2.7-code",
        "qwen/qwen3.6-27b",
        "deepseek-ai/deepseek-v4-pro",
    }
    for item in items:
        el = _eligible(cfg, models, item)
        _, ps = score_eligible(
            art,
            [m.id for m in el],
            phase=item["phase"],
            needs_tools=item["needs_tools"],
            tokens=item["tokens"],
        )
        for mid, p in ps.items():
            if mid in trio:
                vals[mid].append(p)
    for mid, vs in vals.items():
        mu = sum(vs) / len(vs)
        var = sum((v - mu) ** 2 for v in vs) / len(vs)
        print(
            f"[DEBUG-gate06] P_var {mid}: mean={mu:.4f} std={var**0.5:.6f} "
            f"unique={len(set(round(v, 6) for v in vs))}"
        )


if __name__ == "__main__":
    main()
