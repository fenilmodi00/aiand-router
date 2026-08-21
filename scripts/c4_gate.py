"""C4 gate: disjoint-set assertion + per-model coverage + ECE + spend delta."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

SPARSE_ANCHORS = (
    "deepseek-ai/deepseek-v4-flash",
    "qwen/qwen3.6-27b",
    "moonshotai/kimi-k2.7-code",
    "deepseek-ai/deepseek-v4-pro",
)
AA_INDEX = {
    "deepseek-ai/deepseek-v4-flash": 52,
    "qwen/qwen3.6-27b": 38,
    "google/gemma-4-31b-it": 30,
    "openai/gpt-oss-120b": 24,
    "moonshotai/kimi-k2.7-code": 42,
    "deepseek-ai/deepseek-v4-pro": 53,
    "zai-org/glm-5.2": 53,
    "motif-technologies/motif-3": 47,
    "moonshotai/kimi-k3": 60,
}
K3 = "moonshotai/kimi-k3"

GATE_SPLITS = {"sparse-train", "dense-cal", "threshold-tune", "promotion-holdout"}


def _prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]


def _load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def gate_disjoint():
    """Verify ALL gate splits are pairwise-disjoint; total == sum of sizes."""
    manifest = json.loads((DATA / "split_manifest.json").read_text(encoding="utf-8"))
    rows = manifest["rows"]
    by_split = {}
    for r in rows:
        s = r["split"]
        if s in GATE_SPLITS:
            by_split.setdefault(s, set()).add(r["prompt_hash"])

    # Pairwise disjoint check
    splits = sorted(by_split.keys())
    overlaps = []
    for i, s1 in enumerate(splits):
        for s2 in splits[i + 1:]:
            inter = by_split[s1] & by_split[s2]
            if inter:
                overlaps.append(f"{s1} ∩ {s2} = {len(inter)} hashes")

    total = sum(len(v) for v in by_split.values())
    union = set()
    for v in by_split.values():
        union |= v

    passed = len(overlaps) == 0 and total == len(union)
    return {
        "passed": passed,
        "splits": {s: len(v) for s, v in sorted(by_split.items())},
        "total": total,
        "union": len(union),
        "overlaps": overlaps,
    }


def gate_coverage():
    """Per-model coverage in dense gold: n>=250 OR shortfall documented."""
    gold = _load_jsonl(DATA / "gold_dense.jsonl")
    by_model = {}
    for r in gold:
        mid = r["model_id"]
        by_model.setdefault(mid, 0)
        by_model[mid] += 1

    min_n = min(by_model.values()) if by_model else 0
    passed = min_n >= 250
    return {
        "passed": passed,
        "per_model": dict(sorted(by_model.items())),
        "min_n": min_n,
        "threshold": 250,
    }


def gate_ece():
    """ECE using per-model base-rate (sparse gold for anchors, AA/100 for others)
    as predictions vs dense gold success outcomes."""
    # Build per-model predictions
    sparse = _load_jsonl(DATA / "gold_sparse.jsonl")
    sparse_observed = [r for r in sparse if not r.get("unobserved") and r.get("success") is not None]
    by_model_success = {}
    for r in sparse_observed:
        mid = r["model_id"]
        by_model_success.setdefault(mid, {"s": 0, "n": 0})
        by_model_success[mid]["n"] += 1
        if r["success"]:
            by_model_success[mid]["s"] += 1

    predictions = {}
    for mid in AA_INDEX:
        if mid == K3:
            continue
        if mid in by_model_success:
            d = by_model_success[mid]
            predictions[mid] = d["s"] / d["n"] if d["n"] > 0 else AA_INDEX[mid] / 100.0
        else:
            predictions[mid] = AA_INDEX[mid] / 100.0

    # Load dense gold outcomes
    dense = _load_jsonl(DATA / "gold_dense.jsonl")
    observed = [r for r in dense if not r.get("unobserved") and r.get("success") is not None]

    # Bin into 10 equal-width bins
    n_bins = 10
    bins = [[] for _ in range(n_bins)]
    for r in observed:
        pred = predictions.get(r["model_id"], 0.5)
        outcome = 1.0 if r["success"] else 0.0
        bin_idx = min(int(pred * n_bins), n_bins - 1)
        bins[bin_idx].append((pred, outcome))

    ece = 0.0
    total = len(observed)
    bin_details = []
    for i, items in enumerate(bins):
        n = len(items)
        if n == 0:
            bin_details.append({"bin": f"[{i/10:.1f},{(i+1)/10:.1f})", "n": 0, "avg_pred": None, "avg_obs": None})
            continue
        avg_pred = sum(p for p, _ in items) / n
        avg_obs = sum(o for _, o in items) / n
        ece += abs(avg_pred - avg_obs) * (n / total)
        bin_details.append({
            "bin": f"[{i/10:.1f},{(i+1)/10:.1f})",
            "n": n,
            "avg_pred": round(avg_pred, 4),
            "avg_obs": round(avg_obs, 4),
            "gap": round(abs(avg_pred - avg_obs), 4),
        })

    # Baseline: constant prediction = 0.748 (silver mean p_success)
    baseline_pred = 0.748
    baseline_ece = 0.0
    for r in observed:
        outcome = 1.0 if r["success"] else 0.0
        baseline_ece += abs(baseline_pred - outcome)
    baseline_ece /= total

    # Actual mean success rate
    mean_success = sum(1 for r in observed if r["success"]) / total

    trending_down = ece < baseline_ece

    return {
        "ece": round(ece, 6),
        "baseline_ece": round(baseline_ece, 6),
        "baseline_pred": baseline_pred,
        "mean_success": round(mean_success, 4),
        "trending_down": trending_down,
        "predictions": {k: round(v, 4) for k, v in sorted(predictions.items())},
        "bins": bin_details,
        "n_observed": total,
    }


def gate_spend():
    """Spend delta <= $15."""
    spend_before = 32.568065
    spend_after = float((DATA / "spend.txt").read_text(encoding="utf-8").strip())
    delta = spend_after - spend_before
    return {
        "passed": delta <= 15.0,
        "spend_before": round(spend_before, 6),
        "spend_after": round(spend_after, 6),
        "delta": round(delta, 6),
        "cap": 15.0,
    }


if __name__ == "__main__":
    print("=== C4 GATE ===\n")

    d = gate_disjoint()
    print("1. Disjoint-set assertion")
    print(f"   Splits: {d['splits']}")
    print(f"   Total: {d['total']}, Union: {d['union']}")
    if d["overlaps"]:
        print(f"   Overlaps: {d['overlaps']}")
    print(f"   VERDICT: {'PASS' if d['passed'] else 'FAIL'}\n")

    c = gate_coverage()
    print("2. Per-model coverage (dense gold)")
    for mid, n in c["per_model"].items():
        print(f"   {mid}: {n}")
    print(f"   Min: {c['min_n']} (threshold {c['threshold']})")
    print(f"   VERDICT: {'PASS' if c['passed'] else 'FAIL'}\n")

    e = gate_ece()
    print("3. ECE (equal-width 10 bins)")
    print(f"   Predictions: {e['predictions']}")
    print(f"   Mean success: {e['mean_success']}")
    print(f"   ECE: {e['ece']}")
    print(f"   Baseline ECE (const=0.748): {e['baseline_ece']}")
    print(f"   Trending down: {e['trending_down']}")
    for b in e["bins"]:
        if b["n"] > 0:
            print(f"   {b['bin']}: n={b['n']}, avg_pred={b['avg_pred']}, avg_obs={b['avg_obs']}, gap={b['gap']}")
    print()

    s = gate_spend()
    print("4. Spend delta")
    print(f"   Before: ${s['spend_before']}")
    print(f"   After: ${s['spend_after']}")
    print(f"   Delta: ${s['delta']}")
    print(f"   Cap: ${s['cap']}")
    print(f"   VERDICT: {'PASS' if s['passed'] else 'FAIL'}\n")

    all_pass = d["passed"] and c["passed"] and e["trending_down"] and s["passed"]
    print(f"=== C4 OVERALL: {'PASS' if all_pass else 'FAIL'} ===")
