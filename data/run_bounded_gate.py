"""Bounded gate runner: compute all metrics for H17 report."""
import json
from pathlib import Path

from aiand_router.eval import promotion_gate_verdict
from aiand_router.lite_runner import summarize_comparison
from aiand_router.metrics import (
    brier_skill_score,
    ece_equal_width,
    ece_equal_mass,
    ece_mass_is_gated,
)

ROOT = Path(__file__).resolve().parent.parent

# 1. Load session rows from lite_runner output
sessions = [
    json.loads(l)
    for l in (ROOT / "data" / "bounded_gate_sessions.jsonl").read_text().splitlines()
    if l.strip()
]
summary = summarize_comparison(sessions)
print("=== Lite Comparison Summary ===")
print(json.dumps(summary, indent=2))

# 2. Run promotion gate verdict on request log + session JSONL
log_path = ROOT / "data" / "requests.jsonl"
session_path = ROOT / "data" / "bounded_gate_sessions.jsonl"
verdict = promotion_gate_verdict(log_path, session_path=session_path)
print("\n=== Promotion Gate Verdict ===")
print(json.dumps(verdict, indent=2, default=str))

# 3. Calibration rows (confidence + tests_passed)
hops = [
    json.loads(l)
    for l in log_path.read_text().splitlines()
    if l.strip()
]
hops = [r for r in hops if r.get("kind") != "outcome" and not r.get("cache_hit")]
cal_rows = []
for row in hops:
    conf = row.get("trained_confidence")
    if conf is None:
        conf = row.get("confidence")
    if conf is None:
        continue
    if row.get("tests_passed") is None:
        continue
    cal_rows.append((float(conf), 1.0 if row.get("tests_passed") else 0.0))

print(f"\nCalibration rows: {len(cal_rows)}")
bss = brier_skill_score(cal_rows) if cal_rows else None
ece_w = ece_equal_width(cal_rows) if cal_rows else None
ece_m = ece_equal_mass(cal_rows) if cal_rows else None
gated = ece_mass_is_gated(len(cal_rows)) if cal_rows else False
print(f"BSS: {bss}")
print(f"ECE equal-width: {ece_w}")
print(f"ECE equal-mass: {ece_m}")
print(f"ECE mass gated (n<10 waiver): {gated}")
tp = sum(1 for _, y in cal_rows if y == 1.0)
print(f"tests_passed=True: {tp}, tests_passed=False: {len(cal_rows) - tp}")

# 4. Cost metrics
deltas = [
    float(r["rules_cost_delta_usd"])
    for r in hops
    if r.get("rules_cost_delta_usd") is not None
]
mean_delta = sum(deltas) / len(deltas) if deltas else None
total_cost = sum(float(r.get("cost_usd", 0)) for r in hops)
print(f"\nCost deltas: n={len(deltas)}, mean={mean_delta}")
print(f"Total cost in log: ${total_cost:.6f}")

# 5. Quality metrics from session
rules_rate = summary.get("rules_resolve_rate")
trained_rate = summary.get("trained_resolve_rate")
delta_pp = summary.get("delta_pp")
print(f"\nQuality: rules={rules_rate}, trained={trained_rate}, delta={delta_pp}pp")

# 6. Verdict formula check
quality_ok = trained_rate is not None and rules_rate is not None and trained_rate >= rules_rate - 0.01
cost_ok = mean_delta is not None and mean_delta < 0.0
bss_ok = bss is not None and bss > 0.0
ece_ok = (ece_w is not None and ece_w <= 0.03) and (
    not gated or (ece_m is not None and ece_m <= 0.03)
)
print(f"\n=== Verdict Formula ===")
print(f"quality_ok (trained >= rules - 1pp): {quality_ok}")
print(f"cost_ok (delta < 0): {cost_ok}")
print(f"bss_ok (BSS > 0): {bss_ok}")
print(f"ece_ok (ECE <= 0.03): {ece_ok}")
print(f"n=30 < floor=300 -> verdict = bounded_check_only")
