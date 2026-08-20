"""Unpaid train vs cal vs eval gold geometry. Eval dumps are never fit y."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# Sparse-train anchors (same catalog ids as train.SPARSE_ANCHORS).
FLASH = "deepseek-ai/deepseek-v4-flash"
QWEN = "qwen/qwen3.6-27b"
KIMI = "moonshotai/kimi-k2.7-code"
PRO = "deepseek-ai/deepseek-v4-pro"
HOLDOUT_ORDER_IDS = (FLASH, QWEN, KIMI, PRO)

LOG1P_LONG = 4.8
LOG1P_SHORT = 4.14

# Hard-band y on observed cells; dense-easy is the prior dense-cal ~0.39.
Y_HARD_LO = 0.07
Y_HARD_HI = 0.22
Y_DENSE_EASY = 0.39
# Flash ≈ Qwen on holdout (verified rates equal). Allow 3 pp so n≈40 one-cell
# noise (1/40=0.025) does not kill an otherwise holdout-like order (hard-transfer Mix1;
# documented in issues/03 — not soft-threshold gaming).
FLASH_QWEN_APPROX = 0.03


def _load_gold(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _observed(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if "model_id" in r and not r.get("unobserved") and "success" in r]


def _n_unobserved(rows: list[dict[str, Any]]) -> int:
    return sum(1 for r in rows if r.get("unobserved"))


def per_id_rates(rows: list[dict[str, Any]]) -> dict[str, float]:
    hits: dict[str, list[float]] = defaultdict(list)
    for r in _observed(rows):
        hits[str(r["model_id"])].append(1.0 if r["success"] else 0.0)
    return {mid: sum(ys) / len(ys) for mid, ys in hits.items() if ys}


def y_rate(rows: list[dict[str, Any]]) -> float:
    ys = [1.0 if r["success"] else 0.0 for r in _observed(rows)]
    return (sum(ys) / len(ys)) if ys else 0.0


def y_in_hard_band(y: float) -> bool:
    return Y_HARD_LO <= y <= Y_HARD_HI


def y_is_dense_easy(y: float) -> bool:
    """True when y is closer to dense-easy (~0.39) than to the hard-band midpoint."""
    hard_mid = (Y_HARD_LO + Y_HARD_HI) / 2.0
    return abs(y - Y_DENSE_EASY) < abs(y - hard_mid)


WINNER_PATTERNS = (
    "kimi-only",
    "all-four",
    "all-fail",
    "flash+qwen+kimi",
    "qwen-without-flash",
    "flash-without-pro",
    "flash+pro",
    "other",
)


def classify_winner_pattern(success_by_model: dict[str, bool]) -> str:
    """Per-prompt success set → winner pattern (labeled gold only)."""
    success = {mid for mid, ok in success_by_model.items() if ok}
    if success == {KIMI}:
        return "kimi-only"
    if success == set(HOLDOUT_ORDER_IDS):
        return "all-four"
    if not success:
        return "all-fail"
    if success == {FLASH, QWEN, KIMI}:
        return "flash+qwen+kimi"
    if QWEN in success and FLASH not in success:
        return "qwen-without-flash"
    if FLASH in success and PRO not in success:
        return "flash-without-pro"
    if FLASH in success and PRO in success:
        return "flash+pro"
    return "other"


def group_gold_by_prompt(rows: list[dict[str, Any]]) -> dict[str, dict[str, bool]]:
    """prompt → model_id → success for observed anchor cells."""
    out: dict[str, dict[str, bool]] = defaultdict(dict)
    for r in _observed(rows):
        out[str(r["prompt"])][str(r["model_id"])] = bool(r["success"])
    return out


def winner_pattern_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Count prompts with full anchor coverage by winner pattern."""
    counts: dict[str, int] = {p: 0 for p in WINNER_PATTERNS}
    for oc in group_gold_by_prompt(rows).values():
        if not all(mid in oc for mid in HOLDOUT_ORDER_IDS):
            continue
        pat = classify_winner_pattern({mid: oc[mid] for mid in HOLDOUT_ORDER_IDS})
        counts[pat] = counts.get(pat, 0) + 1
    return counts


def winner_diagnosis_row(
    label: str,
    rows: list[dict[str, Any]],
    *,
    eval_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """One row for operator winner-pattern tables (Mix1 vs seed vs verified)."""
    by_prompt = group_gold_by_prompt(rows)
    full = [oc for oc in by_prompt.values() if all(mid in oc for mid in HOLDOUT_ORDER_IDS)]
    rates = per_id_rates(rows)
    patterns = winner_pattern_counts(rows)
    n = len(full)
    out: dict[str, Any] = {
        "label": label,
        "prompts": n,
        "y_rate": round(y_rate(rows), 4),
        "flash": round(rates.get(FLASH, 0.0), 4),
        "qwen": round(rates.get(QWEN, 0.0), 4),
        "kimi": round(rates.get(KIMI, 0.0), 4),
        "pro": round(rates.get(PRO, 0.0), 4),
        "holdout_like_order": holdout_like_order(rates),
        **{p.replace("+", "_"): patterns.get(p, 0) for p in WINNER_PATTERNS},
    }
    if eval_rows is not None:
        geo = geometry_from_rows(rows, eval_rows)
        out["spearman"] = round(float(geo["spearman_train_eval"]), 4)
        out["geometry_pass"] = bool(geo["geometry_pass"])
    return out


def winner_diagnosis_table(
    slices: list[tuple[str, Path | list[dict[str, Any]]]],
    *,
    eval_path: Path | None = None,
) -> list[dict[str, Any]]:
    eval_rows = _load_gold(eval_path) if eval_path is not None else None
    table: list[dict[str, Any]] = []
    for label, src in slices:
        rows = _load_gold(src) if isinstance(src, Path) else src
        table.append(
            winner_diagnosis_row(
                label,
                rows,
                eval_rows=eval_rows if label != "verified" else None,
            )
        )
    return table


def holdout_like_order(rates: dict[str, float]) -> bool:
    """Kimi ≫ Flash ≈ Qwen ≫ Pro on per-id success rates."""
    if not all(mid in rates for mid in HOLDOUT_ORDER_IDS):
        return False
    flash, qwen, kimi, pro = (rates[mid] for mid in HOLDOUT_ORDER_IDS)
    return (
        kimi > flash
        and kimi > qwen
        and abs(flash - qwen) <= FLASH_QWEN_APPROX
        and flash > pro
        and qwen > pro
    )


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
    obs = _observed(rows)
    fracs = token_fracs(rows)
    return {
        "per_id": per_id_rates(rows),
        "y_rate": y_rate(rows),
        "observed_n": len(obs),
        "unobserved_n": _n_unobserved(rows),
        "frac_log1p_gt_4_8": fracs["frac_log1p_gt_4_8"],
        "frac_log1p_le_4_14": fracs["frac_log1p_le_4_14"],
    }


def _gold_cell_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("prompt") or ""), str(row.get("model_id") or ""))


def concat_gold(
    base_rows: list[dict[str, Any]], extra_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Append extra cells; first prompt+model_id wins."""
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for r in list(base_rows) + list(extra_rows):
        k = _gold_cell_key(r)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def write_gold(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def geometry_from_rows(
    train_rows: list[dict[str, Any]],
    eval_rows: list[dict[str, Any]],
    cal_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    train = slice_stats(train_rows)
    ev = slice_stats(eval_rows)
    ids = sorted(set(train["per_id"]) & set(ev["per_id"]))
    rho = spearman([train["per_id"][i] for i in ids], [ev["per_id"][i] for i in ids])
    train_y = float(train["y_rate"])
    kill_spearman = rho <= 0
    kill_y_empty = train["observed_n"] == 0 or train_y == 0.0
    kill_y_easy = y_is_dense_easy(train_y)
    kill = kill_spearman or kill_y_empty or kill_y_easy
    order_ok = holdout_like_order(train["per_id"])
    hard_ok = y_in_hard_band(train_y)
    geometry_pass = (rho > 0) and hard_ok and order_ok
    prefer_logistic = not (rho > 0)
    out: dict[str, Any] = {
        "train": train,
        "eval": ev,
        "spearman_train_eval": rho,
        "kill_spearman": kill_spearman,
        "kill_y_empty": kill_y_empty,
        "kill_y_easy": kill_y_easy,
        "kill": kill,
        "y_in_hard_band": hard_ok,
        "holdout_like_order": order_ok,
        "geometry_pass": geometry_pass,
        "prefer_logistic": prefer_logistic,
        "eval_is_fit_gold": False,
        "recommended_artifact": (
            "data/scorer-logistic.json" if prefer_logistic else "data/scorer.json"
        ),
    }
    if cal_rows is not None:
        out["cal"] = slice_stats(cal_rows)
    return out


def geometry_report(
    train_path: Path,
    eval_path: Path,
    cal_path: Path | None = None,
) -> dict[str, Any]:
    return geometry_from_rows(
        _load_gold(train_path),
        _load_gold(eval_path),
        _load_gold(cal_path) if cal_path is not None else None,
    )


def merge_gold_if_geometry(
    base_path: Path,
    extra_path: Path,
    eval_path: Path,
    out_path: Path,
) -> dict[str, Any]:
    """Write base+extra to out_path only when new gold and combined pass geometry.

    Standalone ``extra`` must pass ``geometry_pass`` vs eval; combined-only pass is
    insufficient (seed-14 standalone fail + combined train merge pass regressed replay).
    Does not overwrite out_path on fail. Unpaid; never trains.
    """
    eval_rows = _load_gold(eval_path)
    extra_rows = _load_gold(extra_path)
    standalone = geometry_from_rows(extra_rows, eval_rows)
    combined = concat_gold(_load_gold(base_path), extra_rows)
    report = geometry_from_rows(combined, eval_rows)
    report["standalone"] = {
        "geometry_pass": standalone["geometry_pass"],
        "holdout_like_order": standalone["holdout_like_order"],
        "y_rate": standalone["train"]["y_rate"],
        "spearman_train_eval": standalone["spearman_train_eval"],
        "n": len(extra_rows),
    }
    report["standalone_geometry_pass"] = standalone["geometry_pass"]
    report["merged_n"] = len(combined)
    report["wrote"] = False
    report["out"] = str(out_path)
    if not standalone["geometry_pass"]:
        report["refused"] = "standalone_geometry_pass=false"
        return report
    if not report.get("geometry_pass"):
        report["refused"] = "combined_geometry_pass=false"
        return report
    write_gold(combined, out_path)
    report["wrote"] = True
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Unpaid geometry: per-id rates, Spearman(train, eval), y-rate on observed cells, "
            "kill/pass flags. --eval is eval-only (not fit y). Kill if Spearman <= 0, "
            "train y empty, or y dense-easy (~0.39). Pass needs Spearman > 0, hard-band y, "
            "holdout-like order. Prefer logistic until Spearman > 0."
        )
    )
    parser.add_argument("--train", required=True, help="Train/sparse gold JSONL")
    parser.add_argument("--cal", help="Dense/cal gold JSONL")
    parser.add_argument(
        "--eval",
        required=True,
        help="Eval-only holdout gold JSONL (not fit y; typically frozen verified)",
    )
    parser.add_argument(
        "--merge",
        help="Extra gold JSONL; concatenate onto --train and write --out only if geometry_pass",
    )
    parser.add_argument("--out", help="Combined gold path (required with --merge)")
    args = parser.parse_args(argv)
    if args.merge or args.out:
        if not args.merge or not args.out:
            print("refusing: --merge and --out must be set together", file=sys.stderr)
            return 2
        report = merge_gold_if_geometry(
            Path(args.train),
            Path(args.merge),
            Path(args.eval),
            Path(args.out),
        )
    else:
        report = geometry_report(
            Path(args.train),
            Path(args.eval),
            Path(args.cal) if args.cal else None,
        )
    print(json.dumps(report, indent=2))
    print("kill", report["kill"])
    print("geometry_pass", report["geometry_pass"])
    print("kill_spearman", report["kill_spearman"])
    print("kill_y_empty", report["kill_y_empty"])
    print("kill_y_easy", report["kill_y_easy"])
    print("holdout_like_order", report["holdout_like_order"])
    print("prefer_logistic", report["prefer_logistic"])
    print("recommended_artifact", report["recommended_artifact"])
    if args.merge:
        print("wrote", report.get("wrote"))
        print("merged_n", report.get("merged_n"))
        if not report.get("wrote"):
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
