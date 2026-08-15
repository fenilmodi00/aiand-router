#!/usr/bin/env python
"""QA for isotonic calibration (PAVA) alongside Platt in the trained-router path.

Assert-based, stdlib only. Run: python scripts/check_isotonic.py

Covers:
  (a) ECE(isotonic) <= ECE(platt) on a monotone synthetic (z, y) set.
  (b) Round-trip an isotonic artifact through load_scorer + score_eligible;
      assert all returned p in [0, 1].
  (c) n_cal=50 forced-Platt path: assert artifact calibrator mode == "platt".

Adversarial probes:
  (1) stale_state: fit, save, reload, score twice; assert identical outputs.
  (2) malformed_input: empty lists and out-of-order z into _fit_isotonic.
  (3) flaky_tests: fixed seeds and tolerances; no wall-clock dependence.
"""

from __future__ import annotations

import json
import math
import pathlib
import random
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from aiand_router.train import _fit_isotonic, _fit_platt, fit_scorer
from aiand_router.scorer import load_scorer, score_eligible, featurize, BINS

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} {detail}")


def ece(zs: list[float], ys: list[float], predict_fn, n_bins: int = 10) -> float:
    """Equal-width ECE over (z, y) pairs using predict_fn(z) -> p."""
    if not zs:
        return 0.0
    lo, hi = min(zs), max(zs)
    if hi <= lo:
        hi = lo + 1.0
    bins: list[list[tuple[float, float]]] = [[] for _ in range(n_bins)]
    for z, y in zip(zs, ys):
        idx = min(n_bins - 1, max(0, int((z - lo) / (hi - lo) * n_bins)))
        bins[idx].append((predict_fn(z), y))
    total = len(zs)
    ece_val = 0.0
    for b in bins:
        if not b:
            continue
        avg_p = sum(p for p, _ in b) / len(b)
        avg_y = sum(y for _, y in b) / len(b)
        ece_val += len(b) / total * abs(avg_p - avg_y)
    return ece_val


def _isotonic_predict(table: list[list[float]], z: float) -> float:
    if not table:
        return 0.5
    for boundary, p in table:
        if z <= boundary:
            return p
    return table[-1][1]


def _platt_predict(a: float, b: float, z: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, a * z + b))))


# ---------------------------------------------------------------------------
# Test (a): ECE(isotonic) <= ECE(platt) on monotone synthetic data
# ---------------------------------------------------------------------------
print("=== Test (a): ECE(isotonic) <= ECE(platt) on monotone synthetic ===")

rng = random.Random(42)
zs: list[float] = []
ys: list[float] = []
# Step function with noise: isotonic fits steps; Platt forces a sigmoid.
for _ in range(60):
    zs.append(rng.uniform(-3, -0.5))
    ys.append(0.0)
for _ in range(60):
    zs.append(rng.uniform(-0.5, 1.5))
    ys.append(1.0 if rng.random() < 0.3 else 0.0)
for _ in range(60):
    zs.append(rng.uniform(1.5, 3.5))
    ys.append(1.0 if rng.random() < 0.7 else 0.0)
for _ in range(60):
    zs.append(rng.uniform(3.5, 6))
    ys.append(1.0)

a, b = _fit_platt(zs, ys)
ece_platt = ece(zs, ys, lambda z: _platt_predict(a, b, z))

table = _fit_isotonic(zs, ys)
ece_isotonic = ece(zs, ys, lambda z: _isotonic_predict(table, z))

print(f"  ECE(platt)    = {ece_platt:.6f}")
print(f"  ECE(isotonic) = {ece_isotonic:.6f}")
check(
    "ECE(isotonic) <= ECE(platt)",
    ece_isotonic <= ece_platt + 1e-9,
    f"(iso={ece_isotonic:.6f} vs plat={ece_platt:.6f})",
)

# Verify table is monotonically non-decreasing in p
ps = [p for _, p in table]
check("isotonic table p is non-decreasing", all(ps[i] <= ps[i + 1] for i in range(len(ps) - 1)))

# ---------------------------------------------------------------------------
# Test (b): round-trip isotonic artifact through load_scorer + score_eligible
# ---------------------------------------------------------------------------
print("=== Test (b): round-trip isotonic artifact through load_scorer + score_eligible ===")

full = featurize("plan", False, 100, "standard", text="hello world")
artifact_b = {
    "not_spec_floors": True,
    "complexity_bin": "standard",
    "weights": {"m/test": full},
    "intercepts": {"m/test": 0.5},
    "bin_weights": {bn: [0.0] * len(full) for bn in BINS},
    "calibrator": {
        "mode": "isotonic",
        "table": [[-2.0, 0.1], [0.0, 0.3], [2.0, 0.7], [4.0, 0.95]],
    },
    "p_success": {"m/test": 0.5},
    "n_gold": 10,
    "n_cal": 2000,
    "n_silver": 0,
}

with tempfile.TemporaryDirectory() as td:
    artifact_path = pathlib.Path(td) / "scorer.json"
    artifact_path.write_text(json.dumps(artifact_b, indent=2), encoding="utf-8")
    loaded = load_scorer(artifact_path)
    check("load_scorer returns artifact", loaded is not None)
    if loaded:
        check(
            "calibrator mode is isotonic",
            loaded.get("calibrator", {}).get("mode") == "isotonic",
        )
        _, ps = score_eligible(
            loaded, ["m/test"], phase="plan", needs_tools=False, tokens=100
        )
        check("score_eligible returns m/test", "m/test" in ps)
        if "m/test" in ps:
            p = ps["m/test"]
            check("p in [0,1]", 0.0 <= p <= 1.0, f"(p={p})")

# ---------------------------------------------------------------------------
# Test (c): n_cal=50 forced-Platt path
# ---------------------------------------------------------------------------
print("=== Test (c): n_cal=50 forced-Platt path ===")

mid = "deepseek-ai/deepseek-v4-flash"
gold_rows = []
for i in range(40):
    gold_rows.append({
        "prompt": f"train prompt {i}",
        "model_id": mid,
        "success": True,
        "success_tier": "verified",
        "unobserved": False,
        "tokens": 10,
        "needs_tools": False,
        "phase": "edit",
        "hint_bin": "standard",
    })
for i in range(10):
    gold_rows.append({
        "prompt": f"zz cal prompt {i}",
        "model_id": mid,
        "success": i % 2 == 0,
        "success_tier": "verified",
        "unobserved": False,
        "tokens": 10,
        "needs_tools": False,
        "phase": "edit",
        "hint_bin": "standard",
    })

with tempfile.TemporaryDirectory() as td:
    gold_path = pathlib.Path(td) / "gold.jsonl"
    gold_path.write_text(
        "".join(json.dumps(r) + "\n" for r in gold_rows), encoding="utf-8"
    )
    out_path = pathlib.Path(td) / "scorer.json"
    fit_scorer(gold_path, None, out_path)
    artifact_c = json.loads(out_path.read_text(encoding="utf-8"))
    cal = artifact_c.get("calibrator", {})
    check("calibrator key present", "calibrator" in artifact_c)
    check(
        "calibrator mode == platt",
        cal.get("mode") == "platt",
        f"(mode={cal.get('mode')})",
    )
    check("n_cal <= 1000", artifact_c.get("n_cal", 9999) <= 1000)

# ---------------------------------------------------------------------------
# Adversarial (1): stale_state — fit, save, reload, score twice
# ---------------------------------------------------------------------------
print("=== Adversarial (1): stale_state ===")

with tempfile.TemporaryDirectory() as td:
    gold_path = pathlib.Path(td) / "gold.jsonl"
    gold_path.write_text(
        "".join(json.dumps(r) + "\n" for r in gold_rows), encoding="utf-8"
    )
    out_path = pathlib.Path(td) / "scorer.json"
    fit_scorer(gold_path, None, out_path)

    loaded1 = load_scorer(out_path)
    _, ps1 = score_eligible(
        loaded1, ["m/missing"], phase="plan", needs_tools=False, tokens=100
    )
    _, ps2 = score_eligible(
        loaded1, ["m/missing"], phase="plan", needs_tools=False, tokens=100
    )
    check("identical outputs across two score calls", ps1 == ps2)

    # Reload from disk and score again
    loaded2 = load_scorer(out_path)
    _, ps3 = score_eligible(
        loaded2, ["m/missing"], phase="plan", needs_tools=False, tokens=100
    )
    check("identical outputs across reload", ps1 == ps3)

# ---------------------------------------------------------------------------
# Adversarial (2): malformed_input — empty lists and out-of-order z
# ---------------------------------------------------------------------------
print("=== Adversarial (2): malformed_input ===")

empty_raised = False
try:
    _fit_isotonic([], [])
except ValueError:
    empty_raised = True
check("empty lists raise ValueError", empty_raised)

# Out-of-order z: PAVA sorts internally, must not crash
ooo_ok = True
try:
    t = _fit_isotonic([3.0, 1.0, 2.0], [1.0, 0.0, 1.0])
    # Table must be sorted by z and non-decreasing in p
    zs_t = [z for z, _ in t]
    check("out-of-order z: table sorted by z", zs_t == sorted(zs_t))
except Exception:
    ooo_ok = False
check("out-of-order z handled without crash", ooo_ok)

# Length mismatch
mismatch_raised = False
try:
    _fit_isotonic([1.0, 2.0], [1.0])
except ValueError:
    mismatch_raised = True
check("length mismatch raises ValueError", mismatch_raised)

# ---------------------------------------------------------------------------
# Adversarial (3): flaky_tests — fixed seeds and tolerances
# ---------------------------------------------------------------------------
print("=== Adversarial (3): flaky_tests ===")

# Re-run test (a) with same seed; ECE values must be identical
rng2 = random.Random(42)
zs2: list[float] = []
ys2: list[float] = []
for _ in range(60):
    zs2.append(rng2.uniform(-3, -0.5))
    ys2.append(0.0)
for _ in range(60):
    zs2.append(rng2.uniform(-0.5, 1.5))
    ys2.append(1.0 if rng2.random() < 0.3 else 0.0)
for _ in range(60):
    zs2.append(rng2.uniform(1.5, 3.5))
    ys2.append(1.0 if rng2.random() < 0.7 else 0.0)
for _ in range(60):
    zs2.append(rng2.uniform(3.5, 6))
    ys2.append(1.0)

a2, b2 = _fit_platt(zs2, ys2)
ece_platt2 = ece(zs2, ys2, lambda z: _platt_predict(a2, b2, z))
table2 = _fit_isotonic(zs2, ys2)
ece_isotonic2 = ece(zs2, ys2, lambda z: _isotonic_predict(table2, z))

check(
    "ECE(platt) deterministic across re-run",
    abs(ece_platt - ece_platt2) < 1e-12,
    f"({ece_platt:.12f} vs {ece_platt2:.12f})",
)
check(
    "ECE(isotonic) deterministic across re-run",
    abs(ece_isotonic - ece_isotonic2) < 1e-12,
    f"({ece_isotonic:.12f} vs {ece_isotonic2:.12f})",
)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"\n=== Summary: {PASS} passed, {FAIL} failed ===")
sys.exit(1 if FAIL else 0)
