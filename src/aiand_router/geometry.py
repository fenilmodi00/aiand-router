"""Unpaid train vs cal vs eval gold geometry. Eval dumps are never fit y."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


LOG1P_LONG = 4.8
LOG1P_SHORT = 4.14


def _load_gold(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _observed(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if "model_id" in r and not r.get("unobserved") and "success" in r]


def per_id_rates(rows: list[dict[str, Any]]) -> dict[str, float]:
    hits: dict[str, list[float]] = defaultdict(list)
    for r in _observed(rows):
        hits[str(r["model_id"])].append(1.0 if r["success"] else 0.0)
    return {mid: sum(ys) / len(ys) for mid, ys in hits.items() if ys}


def y_rate(rows: list[dict[str, Any]]) -> float:
    ys = [1.0 if r["success"] else 0.0 for r in _observed(rows)]
    return (sum(ys) / len(ys)) if ys else 0.0


def _log1p_tokens(rows: list[dict[str, Any]]) -> list[float]:
    seen: dict[str, int] = {}
    for r in rows:
        prompt = str(r.get("prompt") or "")
        if prompt in seen:
            continue
        seen[prompt] = int(r.get("tokens") or 0)
    return [math.log1p(max(0, t)) for t in seen.values()] if seen else []


def token_fracs(rows: list[dict[str, Any]]) -> dict[str, float]:
    vals = _log1p_tokens(rows)
    n = len(vals)
    if not n:
        return {"frac_log1p_gt_4_8": 0.0, "frac_log1p_le_4_14": 0.0}
    return {
        "frac_log1p_gt_4_8": sum(1 for v in vals if v > LOG1P_LONG) / n,
        "frac_log1p_le_4_14": sum(1 for v in vals if v <= LOG1P_SHORT) / n,
    }


def _ranks(xs: list[float]) -> list[float]:
    n = len(xs)
    order = sorted(range(n), key=lambda i: xs[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2 or len(xs) != len(ys):
        return 0.0
    rx, ry = _ranks(xs), _ranks(ys)
    mx = sum(rx) / len(rx)
    my = sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx)
    dy = sum((b - my) ** 2 for b in ry)
    if dx == 0.0 or dy == 0.0:
        return 0.0
    return num / math.sqrt(dx * dy)


def slice_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fracs = token_fracs(rows)
    return {
        "per_id": per_id_rates(rows),
        "y_rate": y_rate(rows),
        "frac_log1p_gt_4_8": fracs["frac_log1p_gt_4_8"],
        "frac_log1p_le_4_14": fracs["frac_log1p_le_4_14"],
    }


def geometry_report(
    train_path: Path,
    eval_path: Path,
    cal_path: Path | None = None,
) -> dict[str, Any]:
    train_rows = _load_gold(train_path)
    eval_rows = _load_gold(eval_path)
    train = slice_stats(train_rows)
    ev = slice_stats(eval_rows)
    ids = sorted(set(train["per_id"]) & set(ev["per_id"]))
    rho = spearman([train["per_id"][i] for i in ids], [ev["per_id"][i] for i in ids])
    kill = rho < 0
    prefer_logistic = not (rho > 0)
    out: dict[str, Any] = {
        "train": train,
        "eval": ev,
        "spearman_train_eval": rho,
        "kill_spearman": kill,
        "prefer_logistic": prefer_logistic,
        "eval_is_fit_gold": False,
        "recommended_artifact": (
            "data/scorer-logistic.json" if prefer_logistic else "data/scorer.json"
        ),
    }
    if cal_path is not None:
        out["cal"] = slice_stats(_load_gold(cal_path))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Unpaid geometry lock: per-id rates, Spearman(train, eval), token histograms. "
            "--eval is eval-only (not fit y). Prefer logistic until Spearman > 0."
        )
    )
    parser.add_argument("--train", required=True, help="Train/sparse gold JSONL")
    parser.add_argument("--cal", help="Dense/cal gold JSONL")
    parser.add_argument(
        "--eval",
        required=True,
        help="Eval-only holdout gold JSONL (not fit y; typically frozen verified)",
    )
    args = parser.parse_args(argv)
    report = geometry_report(
        Path(args.train),
        Path(args.eval),
        Path(args.cal) if args.cal else None,
    )
    print(json.dumps(report, indent=2))
    print("kill_spearman", report["kill_spearman"])
    print("prefer_logistic", report["prefer_logistic"])
    print("recommended_artifact", report["recommended_artifact"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
