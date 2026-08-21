"""C3 gate: cumulative count + trial logistic Brier + Spearman rho on sparse gold."""
import json
import math
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "src"))

from aiand_router.fit import (
    _jsonl_rows,
    _observed_gold,
    _row_x,
    _fit_binary_intercept,
    _logit,
    _split_cal_prompts,
)

GOLD = root / "data" / "gold_sparse.jsonl"
SPARSE_ANCHORS = [
    "deepseek-ai/deepseek-v4-flash",
    "qwen/qwen3.6-27b",
    "moonshotai/kimi-k2.7-code",
    "deepseek-ai/deepseek-v4-pro",
]


def _sigmoid(z: float) -> float:
    z = max(-30.0, min(30.0, z))
    return 1.0 / (1.0 + math.exp(-z))


def _spearman(ranks_a: list[float], ranks_b: list[float]) -> float:
    n = len(ranks_a)
    if n < 2:
        return 0.0
    mean_a = sum(ranks_a) / n
    mean_b = sum(ranks_b) / n
    num = sum((a - mean_a) * (b - mean_b) for a, b in zip(ranks_a, ranks_b))
    den_a = math.sqrt(sum((a - mean_a) ** 2 for a in ranks_a))
    den_b = math.sqrt(sum((b - mean_b) ** 2 for b in ranks_b))
    if den_a == 0 or den_b == 0:
        return 0.0
    return num / (den_a * den_b)


def _rank(values: list[float]) -> list[float]:
    """Average ranks (1-based) for ties."""
    indexed = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while j + 1 < len(indexed) and values[indexed[j + 1]] == values[indexed[i]]:
            j += 1
        avg_rank = (i + j) / 2 + 1  # 1-based average
        for k in range(i, j + 1):
            ranks[indexed[k]] = avg_rank
        i = j + 1
    return ranks


def main() -> None:
    rows = _jsonl_rows(GOLD)
    observed = _observed_gold(rows)
    prompts = sorted({str(r.get("prompt") or "") for r in observed})
    n_unique = len(prompts)

    # --- Gate 1: cumulative count ---
    count_pass = n_unique >= 1800

    # --- Gate 2: trial logistic Brier vs base-rate ---
    train_prompts, cal_prompts = _split_cal_prompts(prompts, frac=0.2)
    train_gold = [r for r in observed if str(r.get("prompt") or "") in train_prompts]
    cal_gold = [r for r in observed if str(r.get("prompt") or "") in cal_prompts]

    gold_ids = {r["model_id"] for r in observed}
    weights: dict[str, list[float]] = {}
    intercepts: dict[str, float] = {}

    for mid in gold_ids:
        xs = [_row_x(r) for r in train_gold if r["model_id"] == mid]
        ys = [1.0 if r.get("success") else 0.0 for r in train_gold if r["model_id"] == mid]
        if not xs:
            continue
        rate = sum(ys) / len(ys) if ys else 0.5
        ic = _logit(rate)
        intercepts[mid] = ic
        weights[mid] = _fit_binary_intercept(xs, ys, ic)

    # Brier on held-out
    brier_sum = 0.0
    brier_n = 0
    for r in cal_gold:
        mid = r["model_id"]
        w = weights.get(mid)
        if not w:
            continue
        ic = intercepts[mid]
        x = _row_x(r)
        z = ic + sum(w[i] * x[i] for i in range(len(w)))
        p = _sigmoid(z)
        y = 1.0 if r.get("success") else 0.0
        brier_sum += (p - y) ** 2
        brier_n += 1

    held_out_brier = brier_sum / brier_n if brier_n else 1.0

    # Base-rate Brier (predict mean)
    all_ys = [1.0 if r.get("success") else 0.0 for r in train_gold]
    mean_y = sum(all_ys) / len(all_ys) if all_ys else 0.5
    base_brier_sum = 0.0
    base_brier_n = 0
    for r in cal_gold:
        mid = r["model_id"]
        if mid not in weights:
            continue
        y = 1.0 if r.get("success") else 0.0
        base_brier_sum += (mean_y - y) ** 2
        base_brier_n += 1
    base_rate_brier = base_brier_sum / base_brier_n if base_brier_n else 1.0

    brier_pass = held_out_brier < base_rate_brier

    # --- Gate 3: Spearman rho (anchor win-rate ordering) ---
    # Split 50/50 by prompt
    mid_idx = len(prompts) // 2
    half_a_prompts = set(prompts[:mid_idx])
    half_b_prompts = set(prompts[mid_idx:])

    half_a = [r for r in observed if str(r.get("prompt") or "") in half_a_prompts]
    half_b = [r for r in observed if str(r.get("prompt") or "") in half_b_prompts]

    def win_rates(half: list[dict]) -> dict[str, float]:
        rates = {}
        for mid in SPARSE_ANCHORS:
            cells = [r for r in half if r["model_id"] == mid]
            if cells:
                rates[mid] = sum(1.0 for r in cells if r.get("success")) / len(cells)
            else:
                rates[mid] = 0.0
        return rates

    wr_a = win_rates(half_a)
    wr_b = win_rates(half_b)

    vals_a = [wr_a[mid] for mid in SPARSE_ANCHORS]
    vals_b = [wr_b[mid] for mid in SPARSE_ANCHORS]
    ranks_a = _rank(vals_a)
    ranks_b = _rank(vals_b)
    rho = _spearman(ranks_a, ranks_b)
    spearman_pass = rho > 0

    # --- Report ---
    report = {
        "gate": "C3",
        "cumulative_unique_queries": n_unique,
        "cumulative_rows": len(observed),
        "count_gate": {"threshold": 1800, "actual": n_unique, "pass": count_pass},
        "brier_gate": {
            "held_out_brier": round(held_out_brier, 6),
            "base_rate_brier": round(base_rate_brier, 6),
            "pass": brier_pass,
            "n_held_out": brier_n,
            "n_train": len(train_gold),
        },
        "spearman_gate": {
            "rho": round(rho, 6),
            "pass": spearman_pass,
            "win_rates_half_a": {mid: round(wr_a[mid], 4) for mid in SPARSE_ANCHORS},
            "win_rates_half_b": {mid: round(wr_b[mid], 4) for mid in SPARSE_ANCHORS},
            "ranks_a": [round(r, 2) for r in ranks_a],
            "ranks_b": [round(r, 2) for r in ranks_b],
        },
        "overall_pass": count_pass and brier_pass and spearman_pass,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
