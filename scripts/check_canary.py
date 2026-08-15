"""Assert-based QA for aiand_router.canary drift canary.

Run: python scripts/check_canary.py

Covers:
  (a) insufficient rows (< 300) -> not tripped
  (b) insufficient days (< 7) -> not tripped
  (c) healthy data -> not tripped (BSS > 0, ECE <= 0.03, low escalate)
  (d) escalate rate trip (trained > rules + 1pp)
  (e) BSS <= 0 trip (constant p=0.5 on balanced data)
  (f) ECE > 0.03 trip (p=0.9, true rate 0.5)
  (g) drift_status.json write + is_tripped read round-trip
  (h) is_tripped returns False on missing/corrupt file
  (i) window selection: last-300 vs last-7d gives MORE rows
"""

from __future__ import annotations

import json
import random
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aiand_router import canary  # noqa: E402

BASE = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
N = 3000  # per path, so 6000 total over 8 days


def _ts(hours: float) -> str:
    return (BASE + timedelta(hours=hours)).isoformat()


def _row(
    i: int,
    total: int,
    path: str = "rules",
    trained_confidence: float | None = None,
    escalated: bool = False,
    status: int = 200,
    tool_valid: bool | None = True,
    json_valid: bool | None = None,
    span_days: float = 8.0,
) -> dict:
    """Synthetic JSONL row. Evenly distributes `total` rows over `span_days`."""
    hours = i * (span_days * 24.0 / total)
    row: dict = {
        "ts": _ts(hours),
        "phase": "edit",
        "selected": "deepseek-ai/deepseek-v4-flash",
        "path": path,
        "status": status,
        "tool_valid": tool_valid,
        "json_valid": json_valid,
    }
    if trained_confidence is not None:
        row["trained_confidence"] = trained_confidence
    if escalated:
        row["escalated_from"] = "deepseek-ai/deepseek-v4-flash"
    return row


def _gen_calibrated(n: int = N, seed: int = 42) -> list[dict]:
    """n rules + n trained rows over 8 days. p ~ U(0,1), y ~ Bernoulli(p)."""
    rng = random.Random(seed)
    total = n * 2
    rows: list[dict] = []
    for i in range(total):
        if i % 2 == 0:
            rows.append(_row(i, total, path="rules"))
        else:
            p = rng.random()
            success = rng.random() < p
            rows.append(_row(
                i, total, path="shadow",
                trained_confidence=round(p, 6),
                tool_valid=success,
            ))
    rows.sort(key=lambda r: r["ts"])
    return rows


def _gen_escalate_trip(n: int = N, seed: int = 42) -> list[dict]:
    """Calibrated data but ~5% of trained failures have escalate, rules 0%."""
    rows = _gen_calibrated(n, seed)
    rng = random.Random(99)
    shadow_fail = [
        k for k, r in enumerate(rows)
        if r.get("path") == "shadow" and r.get("tool_valid") is False
    ]
    target = int(n * 0.05)
    chosen = rng.sample(shadow_fail, min(target, len(shadow_fail)))
    for k in chosen:
        rows[k]["escalated_from"] = "deepseek-ai/deepseek-v4-flash"
    return rows


def _gen_bss_trip(n: int = N) -> list[dict]:
    """Constant p=0.5 on balanced interleaved data -> BSS = 0."""
    total = n * 2
    rows: list[dict] = []
    for i in range(total):
        if i % 2 == 0:
            rows.append(_row(i, total, path="rules"))
        else:
            j = i // 2
            success = (j % 2) == 0
            rows.append(_row(
                i, total, path="shadow",
                trained_confidence=0.5,
                tool_valid=success,
            ))
    rows.sort(key=lambda r: r["ts"])
    return rows


def _gen_ece_trip(n: int = N) -> list[dict]:
    """p=0.9, true rate 0.5 -> ECE > 0.03 (and BSS < 0)."""
    total = n * 2
    rows: list[dict] = []
    for i in range(total):
        if i % 2 == 0:
            rows.append(_row(i, total, path="rules"))
        else:
            j = i // 2
            success = (j % 2) == 0
            rows.append(_row(
                i, total, path="shadow",
                trained_confidence=0.9,
                tool_valid=success,
            ))
    rows.sort(key=lambda r: r["ts"])
    return rows


def check_insufficient_rows() -> str:
    rows = [_row(i, 100, path="rules", span_days=8.0) for i in range(100)]
    result = canary.check_drift(rows)
    assert not result["tripped"], f"(a) insufficient rows: should not trip, got {result}"
    assert result["window"]["n_rows"] == 100
    return "(a) insufficient rows (<300): not tripped PASS"


def check_insufficient_days() -> str:
    rows = [_row(i, 300, path="rules", span_days=3.0) for i in range(300)]
    result = canary.check_drift(rows)
    assert not result["tripped"], f"(b) insufficient days: should not trip, got {result}"
    assert result["window"]["n_rows"] == 300
    return "(b) insufficient days (<7): not tripped PASS"


def check_healthy() -> str:
    rows = _gen_calibrated()
    result = canary.check_drift(rows)
    assert not result["tripped"], f"(c) healthy: should not trip, got {result}"
    assert result["window"]["n_rows"] >= 300
    assert result["window"]["n_days"] >= 7.0
    return f"(c) healthy: not tripped (n={result['window']['n_rows']}, d={result['window']['n_days']}) PASS"


def check_escalate_trip() -> str:
    rows = _gen_escalate_trip()
    result = canary.check_drift(rows)
    assert result["tripped"], f"(d) escalate trip: should trip, got {result}"
    assert any("escalate_rate" in r for r in result["reasons"]), \
        f"(d) escalate trip: no escalate_rate reason in {result['reasons']}"
    return f"(d) escalate trip: {result['reasons']} PASS"


def check_bss_trip() -> str:
    rows = _gen_bss_trip()
    result = canary.check_drift(rows)
    assert result["tripped"], f"(e) bss trip: should trip, got {result}"
    assert any("bss_le0" in r for r in result["reasons"]), \
        f"(e) bss trip: no bss_le0 reason in {result['reasons']}"
    return f"(e) bss trip: {result['reasons']} PASS"


def check_ece_trip() -> str:
    rows = _gen_ece_trip()
    result = canary.check_drift(rows)
    assert result["tripped"], f"(f) ece trip: should trip, got {result}"
    assert any("ece_width" in r or "ece_mass" in r for r in result["reasons"]), \
        f"(f) ece trip: no ece reason in {result['reasons']}"
    return f"(f) ece trip: {result['reasons']} PASS"


def check_write_and_read() -> str:
    with tempfile.TemporaryDirectory() as td:
        sp = Path(td) / "drift_status.json"
        canary.write_status(
            {"tripped": True, "reasons": ["test"], "window": {"n_rows": 300, "n_days": 7.5}},
            status_path=sp,
        )
        assert sp.exists(), "(g) write_status: file not created"
        data = json.loads(sp.read_text(encoding="utf-8"))
        assert data["tripped"] is True
        assert data["reasons"] == ["test"]
        assert data["window"]["n_rows"] == 300
        assert canary.is_tripped(status_path=sp) is True
        canary.write_status(
            {"tripped": False, "reasons": [], "window": {"n_rows": 300, "n_days": 7.5}},
            status_path=sp,
        )
        assert canary.is_tripped(status_path=sp) is False
    return "(g) write_status + is_tripped round-trip PASS"


def check_missing_and_corrupt() -> str:
    with tempfile.TemporaryDirectory() as td:
        sp = Path(td) / "nonexistent.json"
        assert canary.is_tripped(status_path=sp) is False, "(h) missing file: should be False"
        sp.write_text("{not valid json", encoding="utf-8")
        assert canary.is_tripped(status_path=sp) is False, "(h) corrupt file: should be False"
    return "(h) missing/corrupt file: is_tripped=False PASS"


def check_window_selection() -> str:
    """When >300 rows exist and last-7d has more rows than last-300, window picks the larger."""
    rows: list[dict] = []
    for i in range(500):
        path = "rules" if i % 2 == 0 else "shadow"
        p = 0.9 if i % 2 == 1 else None
        rows.append(_row(i, 500, path=path, trained_confidence=p, span_days=8.0))
    result = canary.check_drift(rows)
    assert result["window"]["n_rows"] > 300, \
        f"(i) window selection: expected >300 rows, got {result['window']['n_rows']}"
    return f"(i) window selection: n_rows={result['window']['n_rows']} (>300 from last-7d) PASS"


def main() -> int:
    results = [
        check_insufficient_rows(),
        check_insufficient_days(),
        check_healthy(),
        check_escalate_trip(),
        check_bss_trip(),
        check_ece_trip(),
        check_write_and_read(),
        check_missing_and_corrupt(),
        check_window_selection(),
    ]
    for r in results:
        print(r)
    print(f"\nAll {len(results)} checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
