"""Assert-based QA for aiand_router.metrics calibration gate metrics.

Run: python scripts/check_metrics.py

Covers:
  (a) perfectly-calibrated synthetic rows -> both ECE <= 0.03, BSS > 0
  (b) constant p=0.5 on balanced data -> BSS <= 0.01;
      miscalibrated p=0.9 true rate 0.1 -> ECE > 0.03
  (c) malformed input raises ValueError
  adversarial: stale_state (call each metric twice, assert identical)
  adversarial: flaky_tests (fixed seeds only)
"""

from __future__ import annotations

import json
import random
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aiand_router import metrics  # noqa: E402


def make_calibrated(n: int = 20000, seed: int = 42) -> list[tuple[float, int]]:
    """Perfectly calibrated: p ~ U(0,1), y ~ Bernoulli(p)."""
    rng = random.Random(seed)
    rows: list[tuple[float, int]] = []
    for _ in range(n):
        p = rng.random()
        y = 1 if rng.random() < p else 0
        rows.append((p, y))
    return rows


def make_constant_balanced(n: int = 20000, seed: int = 99) -> list[tuple[float, int]]:
    """Constant predictor p=0.5 on balanced data (y ~ Bernoulli(0.5))."""
    rng = random.Random(seed)
    return [(0.5, 1 if rng.random() < 0.5 else 0) for _ in range(n)]


def make_miscalibrated(n: int = 20000, seed: int = 7) -> list[tuple[float, int]]:
    """Miscalibrated: p=0.9 while true rate is 0.1."""
    rng = random.Random(seed)
    return [(0.9, 1 if rng.random() < 0.1 else 0) for _ in range(n)]


def check_calibrated() -> str:
    rows = make_calibrated()
    ew = metrics.ece_equal_width(rows)
    em = metrics.ece_equal_mass(rows)
    bss = metrics.brier_skill_score(rows)
    bs = metrics.brier_score(rows)
    assert ew <= 0.03, f"(a) calibrated ece_equal_width={ew:.4f} > 0.03"
    assert em <= 0.03, f"(a) calibrated ece_equal_mass={em:.4f} > 0.03"
    assert bss > 0, f"(a) calibrated bss={bss:.4f} <= 0"
    return f"(a) calibrated: ece_w={ew:.4f} ece_m={em:.4f} brier={bs:.4f} bss={bss:.4f} PASS"


def check_constant() -> str:
    rows = make_constant_balanced()
    bss = metrics.brier_skill_score(rows)
    assert bss <= 0.01, f"(b) constant bss={bss:.4f} > 0.01"
    return f"(b) constant p=0.5: bss={bss:.4f} PASS"


def check_miscalibrated() -> str:
    rows = make_miscalibrated()
    ew = metrics.ece_equal_width(rows)
    em = metrics.ece_equal_mass(rows)
    mce = metrics.mce(rows)
    assert ew > 0.03, f"(b) miscalibrated ece_equal_width={ew:.4f} <= 0.03"
    assert em > 0.03, f"(b) miscalibrated ece_equal_mass={em:.4f} <= 0.03"
    assert mce > 0.03, f"(b) miscalibrated mce={mce:.4f} <= 0.03"
    return f"(b) miscalibrated p=0.9/rate=0.1: ece_w={ew:.4f} ece_m={em:.4f} mce={mce:.4f} PASS"


def check_malformed() -> str:
    cases: list[tuple[str, list]] = [
        ("empty", []),
        ("p>1", [(1.5, 0)]),
        ("p<0", [(-0.1, 1)]),
        ("y=2", [(0.5, 2)]),
        ("y=-1", [(0.5, -1)]),
        ("y=0.5", [(0.5, 0.5)]),
        ("p=nan", [(float("nan"), 0)]),
        ("p=inf", [(float("inf"), 0)]),
        ("not_a_pair", [(0.5,)]),
        ("p_is_str", [("0.5", 0)]),
    ]
    for label, bad in cases:
        raised = False
        try:
            metrics.brier_score(bad)
        except ValueError:
            raised = True
        assert raised, f"(c) malformed ({label}): expected ValueError, got none"
    return f"(c) malformed input: {len(cases)} cases all raised ValueError PASS"


def check_stale_state() -> str:
    """Call each metric twice on the same rows; results must be identical."""
    rows = make_calibrated(n=500, seed=123)
    fns = [
        ("brier_score", metrics.brier_score),
        ("brier_skill_score", metrics.brier_skill_score),
        ("ece_equal_width", metrics.ece_equal_width),
        ("ece_equal_mass", metrics.ece_equal_mass),
        ("mce", metrics.mce),
        ("reliability_table", metrics.reliability_table),
        ("reliability", lambda r: metrics.reliability(r, M=10)),
    ]
    for name, fn in fns:
        r1 = fn(rows)
        r2 = fn(rows)
        assert r1 == r2, f"stale_state {name}: second call returned different result"
    return f"adversarial stale_state: {len(fns)} metrics identical on re-call PASS"


def check_reliability_json() -> str:
    """write_reliability_json produces valid JSON with expected keys."""
    rows = make_calibrated(n=500, seed=456)
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "rel.json"
        metrics.write_reliability_json(rows, path)
        data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, list), "reliability json: expected list"
    assert len(data) > 0, "reliability json: empty table"
    required = {"bin_lo", "bin_hi", "mean_pred", "obs_rate", "count"}
    for row in data:
        assert required <= set(row), f"reliability json: missing keys in {set(row)}"
        assert row["count"] > 0, "reliability json: empty bin in table"
        assert 0.0 <= row["bin_lo"] <= row["bin_hi"] <= 1.0
    return f"adversarial write_reliability_json: {len(data)} bins, round-trip PASS"


def check_reliability_report() -> str:
    """reliability() returns a dict with all expected keys."""
    rows = make_calibrated(n=1000, seed=789)
    rep = metrics.reliability(rows, M=15)
    expected = {"n", "brier_score", "brier_skill_score", "ece_equal_width",
                "ece_equal_mass", "mce", "bins"}
    assert expected <= set(rep), f"reliability: missing keys {expected - set(rep)}"
    assert rep["n"] == 1000
    assert isinstance(rep["bins"], list)
    return f"reliability(M=15): n={rep['n']} keys={sorted(rep.keys())} PASS"


def main() -> int:
    results = [
        check_calibrated(),
        check_constant(),
        check_miscalibrated(),
        check_malformed(),
        check_stale_state(),
        check_reliability_json(),
        check_reliability_report(),
    ]
    for r in results:
        print(r)
    print(f"\nAll {len(results)} checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
