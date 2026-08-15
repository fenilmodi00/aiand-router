"""Drift canary for the trained router.

Monitors data/requests.jsonl and trips a retrain signal when quality degrades.
Spec: .scratch/trained-router/spec.md - Catalog drift and retrain.

Trip conditions (promotion-gate definitions on serve hops):
  - escalate rate >1pp worse than rules
  - BSS <= 0
  - either ECE > 0.03

Window: n>=300 hops AND 7 days, whichever later (both must be met).
Output: data/drift_status.json {tripped, reasons[], window}
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .metrics import brier_skill_score, ece_equal_width, ece_equal_mass

MIN_ROWS = 300
MIN_DAYS = 7
ESCALATE_DELTA = 0.01  # 1 percentage point
ECE_LIMIT = 0.03


def _default_log_path() -> Path:
    return Path(os.getenv("REQUESTS_LOG", "data/requests.jsonl"))


def _default_status_path() -> Path:
    return Path(os.getenv("DRIFT_STATUS", "data/drift_status.json"))


def _parse_ts(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def _is_escalated(row: dict[str, Any]) -> bool:
    return "escalated_from" in row


def _success_gold(row: dict[str, Any]) -> int | None:
    """Return 1 (success), 0 (failure), or None (unobserved).

    Success gold: no escalate, and valid tools/JSON if required.
    Missing is unobserved, not failure.
    """
    status = row.get("status")
    if status is None:
        return None
    if _is_escalated(row):
        return 0
    if row.get("tool_valid") is False:
        return 0
    if row.get("json_valid") is False:
        return 0
    if isinstance(status, (int, float)) and status >= 400:
        return 0
    return 1


def _load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def check_drift(
    rows: list[dict[str, Any]] | None = None,
    *,
    log_path: Path | None = None,
) -> dict[str, Any]:
    """Run the drift canary. Returns {tripped, reasons, window}."""
    if rows is None:
        rows = _load_rows(log_path or _default_log_path())

    if len(rows) < MIN_ROWS:
        return {"tripped": False, "reasons": [], "window": {"n_rows": len(rows), "n_days": 0.0}}

    # Parse timestamps and sort chronologically
    parsed: list[tuple[datetime, dict[str, Any]]] = []
    for r in rows:
        ts = _parse_ts(r.get("ts", ""))
        if ts is not None:
            parsed.append((ts, r))

    if len(parsed) < MIN_ROWS:
        return {"tripped": False, "reasons": [], "window": {"n_rows": len(rows), "n_days": 0.0}}

    parsed.sort(key=lambda x: x[0])
    newest = parsed[-1][0]
    oldest = parsed[0][0]
    total_days = (newest - oldest).total_seconds() / 86400.0

    if total_days < MIN_DAYS:
        return {
            "tripped": False,
            "reasons": [],
            "window": {"n_rows": len(rows), "n_days": round(total_days, 2)},
        }

    # Window: last 300 rows OR last 7 days, whichever gives MORE rows
    sorted_rows = [r for _, r in parsed]
    last_300 = sorted_rows[-MIN_ROWS:]
    cutoff = newest - timedelta(days=MIN_DAYS)
    last_7d = [r for ts, r in parsed if ts >= cutoff]
    window = last_300 if len(last_300) >= len(last_7d) else last_7d

    # Window span (from data, not wall clock)
    w_ts = [t for t in (_parse_ts(r.get("ts", "")) for r in window) if t is not None]
    w_days = (max(w_ts) - min(w_ts)).total_seconds() / 86400.0

    reasons: list[str] = []

    # --- Trip 1: escalate rate (trained > rules + 1pp) ---
    trained_rows = [r for r in window if r.get("path") in {"trained", "shadow"}]
    rules_rows = [r for r in window if r.get("path") == "rules"]

    if trained_rows and rules_rows:
        t_esc = sum(1 for r in trained_rows if _is_escalated(r)) / len(trained_rows)
        r_esc = sum(1 for r in rules_rows if _is_escalated(r)) / len(rules_rows)
        if t_esc > r_esc + ESCALATE_DELTA:
            reasons.append(f"escalate_rate: trained={t_esc:.4f} rules={r_esc:.4f}")

    # --- Trip 2 & 3: BSS and ECE on (trained_confidence, success_gold) pairs ---
    py_pairs: list[tuple[float, float]] = []
    for r in trained_rows:
        p = r.get("trained_confidence")
        if p is None:
            continue
        y = _success_gold(r)
        if y is None:
            continue
        py_pairs.append((float(p), float(y)))

    if py_pairs:
        try:
            bss = brier_skill_score(py_pairs)
            if bss <= 0:
                reasons.append(f"bss_le0: {bss:.4f}")
        except ValueError:
            pass
        try:
            ece_w = ece_equal_width(py_pairs, M=10)
            if ece_w > ECE_LIMIT:
                reasons.append(f"ece_width: {ece_w:.4f}")
        except ValueError:
            pass
        try:
            ece_m = ece_equal_mass(py_pairs, M=10)
            if ece_m > ECE_LIMIT:
                reasons.append(f"ece_mass: {ece_m:.4f}")
        except ValueError:
            pass

    return {
        "tripped": len(reasons) > 0,
        "reasons": reasons,
        "window": {"n_rows": len(window), "n_days": round(w_days, 2)},
    }


def write_status(
    result: dict[str, Any] | None = None,
    *,
    status_path: Path | None = None,
) -> dict[str, Any]:
    """Run canary and write drift_status.json. Returns the result dict."""
    if result is None:
        result = check_drift()
    path = status_path or _default_status_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


# Cached read for app.py hot path
_cache_path: Path | None = None
_cache_mtime: float = -1.0
_cache_tripped: bool = False


def is_tripped(status_path: Path | None = None) -> bool:
    """Read drift_status.json and return whether canary is tripped.

    Cached by (path, mtime) so the app hot path avoids re-reading on every hop.
    """
    global _cache_path, _cache_mtime, _cache_tripped
    path = status_path or _default_status_path()
    try:
        mtime = path.stat().st_mtime
    except OSError:
        _cache_path = path
        _cache_mtime = -1.0
        _cache_tripped = False
        return False
    if path == _cache_path and mtime == _cache_mtime:
        return _cache_tripped
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        _cache_tripped = bool(data.get("tripped"))
    except (json.JSONDecodeError, OSError):
        _cache_tripped = False
    _cache_path = path
    _cache_mtime = mtime
    return _cache_tripped
