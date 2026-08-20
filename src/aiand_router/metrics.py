"""Calibration gate metrics for the trained router.

Reused by eval, drift canary, replay, and promotion readiness. Stdlib-only.

Gate bars (runbook §(a) / .scratch/trained-router/spec.md, Calibration section):
  - Brier skill score > 0
  - equal-width ECE M=10 AND equal-mass ECE <= 0.03
  - reliability diagram attached
  - report M=15 + MCE; do not gate on them alone

Numeric bars live here so consumers cannot drift. Pass predicates for quality/cost
stay in promotion_gate / eval; this module owns calibration numbers + computation.

Rows are (p_success, y_success) pairs where p in [0, 1] and y in {0, 1}.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

Row = tuple[float, float]

# Runbook §(a) / promotion floors — single numeric source.
ECE_MAX = 0.03
BSS_PASS_MIN = 0.0  # require bss > this
QUALITY_TOLERANCE = 0.01
VERIFIED_N_FLOOR = 300
# Equal-mass ECE noise floor; report but do not gate below this n_selected.
SMALL_N_ECE_MASS = 150


def bss_passes(bss: float) -> bool:
    return bss > BSS_PASS_MIN


def ece_passes(ece: float) -> bool:
    return ece <= ECE_MAX


def ece_mass_is_gated(n_selected: int) -> bool:
    return n_selected >= SMALL_N_ECE_MASS


def ece_mass_passes(ece: float, *, n_selected: int) -> bool:
    """Equal-mass bar: waived when n_selected < SMALL_N_ECE_MASS."""
    if not ece_mass_is_gated(n_selected):
        return True
    return ece_passes(ece)


def _validate(rows: Sequence[Row]) -> tuple[list[float], list[int]]:
    """Parse rows into (ps, ys), rejecting invalid input."""
    if not rows:
        raise ValueError("rows must not be empty")
    ps: list[float] = []
    ys: list[int] = []
    for i, r in enumerate(rows):
        try:
            p, y = r  # type: ignore[misc]
        except (TypeError, ValueError):
            raise ValueError(f"row {i}: expected (p, y) pair, got {r!r}") from None
        if not isinstance(p, (int, float)) or isinstance(p, bool):
            raise ValueError(f"row {i}: p={p!r} is not a number")
        pf = float(p)
        if not (0.0 <= pf <= 1.0):
            raise ValueError(f"row {i}: p={pf!r} not in [0, 1]")
        if not isinstance(y, (int, float)) or isinstance(y, bool):
            raise ValueError(f"row {i}: y={y!r} not in {{0, 1}}")
        if y != 0 and y != 1:
            raise ValueError(f"row {i}: y={y!r} not in {{0, 1}}")
        yv = int(y)
        ps.append(pf)
        ys.append(yv)
    return ps, ys


# --- internal: operate on validated (ps, ys) ---


def _brier(ps: list[float], ys: list[int]) -> float:
    n = len(ps)
    return sum((p - y) ** 2 for p, y in zip(ps, ys)) / n


def _bss(ps: list[float], ys: list[int]) -> float:
    n = len(ps)
    bs = _brier(ps, ys)
    y_bar = sum(ys) / n
    bs_base = y_bar * (1.0 - y_bar)
    if bs_base == 0.0:
        return 0.0
    return 1.0 - bs / bs_base


def _bin_index(p: float, m: int) -> int:
    """Equal-width bin index in [0, m-1]. p=1.0 goes to last bin."""
    return min(int(p * m), m - 1)


def _ece_width(ps: list[float], ys: list[int], m: int) -> float:
    n = len(ps)
    bins: list[list[tuple[float, int]]] = [[] for _ in range(m)]
    for p, y in zip(ps, ys):
        bins[_bin_index(p, m)].append((p, y))
    ece = 0.0
    for b in bins:
        if not b:
            continue
        cnt = len(b)
        mean_pred = sum(p for p, _ in b) / cnt
        obs_rate = sum(y for _, y in b) / cnt
        ece += abs(mean_pred - obs_rate) * (cnt / n)
    return ece


def _ece_mass(ps: list[float], ys: list[int], m: int) -> float:
    n = len(ps)
    order = sorted(range(n), key=lambda i: ps[i])
    ece = 0.0
    for k in range(m):
        lo = k * n // m
        hi = (k + 1) * n // m
        if lo == hi:
            continue
        chunk = order[lo:hi]
        cnt = len(chunk)
        mean_pred = sum(ps[j] for j in chunk) / cnt
        obs_rate = sum(ys[j] for j in chunk) / cnt
        ece += abs(mean_pred - obs_rate) * (cnt / n)
    return ece


def _mce(ps: list[float], ys: list[int], m: int) -> float:
    n = len(ps)
    bins: list[list[tuple[float, int]]] = [[] for _ in range(m)]
    for p, y in zip(ps, ys):
        bins[_bin_index(p, m)].append((p, y))
    max_err = 0.0
    for b in bins:
        if not b:
            continue
        cnt = len(b)
        mean_pred = sum(p for p, _ in b) / cnt
        obs_rate = sum(y for _, y in b) / cnt
        max_err = max(max_err, abs(mean_pred - obs_rate))
    return max_err


def _rel_table(ps: list[float], ys: list[int], m: int) -> list[dict[str, Any]]:
    bins: list[list[tuple[float, int]]] = [[] for _ in range(m)]
    for p, y in zip(ps, ys):
        bins[_bin_index(p, m)].append((p, y))
    table: list[dict[str, Any]] = []
    for k, b in enumerate(bins):
        if not b:
            continue
        cnt = len(b)
        mean_pred = sum(p for p, _ in b) / cnt
        obs_rate = sum(y for _, y in b) / cnt
        table.append({
            "bin_lo": k / m,
            "bin_hi": (k + 1) / m,
            "mean_pred": mean_pred,
            "obs_rate": obs_rate,
            "count": cnt,
        })
    return table


# --- public API ---


def brier_score(rows: Sequence[Row]) -> float:
    ps, ys = _validate(rows)
    return _brier(ps, ys)


def brier_skill_score(rows: Sequence[Row]) -> float:
    ps, ys = _validate(rows)
    return _bss(ps, ys)


def ece_equal_width(rows: Sequence[Row], M: int = 10) -> float:
    ps, ys = _validate(rows)
    return _ece_width(ps, ys, M)


def ece_equal_mass(rows: Sequence[Row], M: int = 10) -> float:
    ps, ys = _validate(rows)
    return _ece_mass(ps, ys, M)


def mce(rows: Sequence[Row], M: int = 10) -> float:
    ps, ys = _validate(rows)
    return _mce(ps, ys, M)


def reliability_table(rows: Sequence[Row], M: int = 10) -> list[dict[str, Any]]:
    ps, ys = _validate(rows)
    return _rel_table(ps, ys, M)


def write_reliability_json(rows: Sequence[Row], path: str | Path) -> None:
    table = reliability_table(rows)
    Path(path).write_text(json.dumps(table, indent=2), encoding="utf-8")


def reliability(rows: Sequence[Row], M: int = 15) -> dict[str, Any]:
    """Full calibration report. M defaults to 15 per spec (report, not gate)."""
    ps, ys = _validate(rows)
    return {
        "n": len(ps),
        "brier_score": _brier(ps, ys),
        "brier_skill_score": _bss(ps, ys),
        "ece_equal_width": _ece_width(ps, ys, M),
        "ece_equal_mass": _ece_mass(ps, ys, M),
        "mce": _mce(ps, ys, M),
        "bins": _rel_table(ps, ys, M),
    }
