#!/usr/bin/env python
"""Assert-first QA for aiand_router.lite_runner.

Fixture with 3 canned instances (at least one resolving, at least one not).
Runs runner with --fixture; asserts output JSONL shape, cap, label_type.
Adversarial: cancel_resume, malformed_input, stale_state, flaky_tests,
prompt_injection. Others N/A.

Run: .venv\\Scripts\\python.exe scripts/check_lite_runner.py
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aiand_router.lite_runner import (  # noqa: E402
    CAP,
    _load_fixture,
    fetch_lite_ids,
    main,
)

FIXTURE = [
    {
        "instance_id": "test__resolve-001",
        "module": "fix.py",
        "tests": "from fix import fix\n\ndef test_fix():\n    assert fix() == 42\n",
        "patch": "def fix():\n    return 42\n",
    },
    {
        "instance_id": "test__fail-002",
        "module": "broken.py",
        "tests": "from broken import broken\n\ndef test_broken():\n    assert broken() == 42\n",
        "patch": "def broken():\n    return 0\n",
    },
    {
        "instance_id": "test__resolve-003",
        "module": "clamp.py",
        "tests": (
            "from clamp import clamp\n\n"
            "def test_lo():\n    assert clamp(-1, 0, 10) == 0\n\n"
            "def test_hi():\n    assert clamp(11, 0, 10) == 10\n"
        ),
        "patch": (
            "def clamp(n, lo, hi):\n"
            "    if n < lo:\n        return lo\n"
            "    if n > hi:\n        return hi\n"
            "    return n\n"
        ),
    },
]

EXPECTED_IDS = ["test__resolve-001", "test__fail-002", "test__resolve-003"]
EXPECTED_RESOLVED = {"test__resolve-001": True, "test__fail-002": False, "test__resolve-003": True}


def _check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}: {detail}")
    assert condition, f"ASSERTION FAILED: {name}: {detail}"


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main_qa() -> int:
    print("=" * 60)
    print("lite_runner QA — fixture mode")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        fixture_path = tmp / "fixture.json"
        out_path = tmp / "lite_results.jsonl"
        fixture_path.write_text(json.dumps(FIXTURE, indent=2), encoding="utf-8")

        # --- Main: 3-instance fixture, n=10 -> 3 rows ---
        print("\n[main] 3-instance fixture, n=10 -> 3 rows")
        main(["--fixture", str(fixture_path), "--out", str(out_path), "--n", "10"])
        rows = _read_jsonl(out_path)
        _check("row_count", len(rows) == 3, f"expected 3, got {len(rows)}")
        ids_out = [r["instance_id"] for r in rows]
        _check("instance_ids", ids_out == EXPECTED_IDS, f"got {ids_out}")
        for r in rows:
            _check(
                f"resolved_{r['instance_id']}",
                r["resolved"] == EXPECTED_RESOLVED[r["instance_id"]],
                f"expected {EXPECTED_RESOLVED[r['instance_id']]}, got {r['resolved']}",
            )
            _check(
                f"label_type_{r['instance_id']}",
                r["label_type"] == "harness_proxy",
                f"got {r['label_type']}",
            )

        # --- Cap constant ---
        print("\n[cap] CAP constant exists and equals 50")
        _check("cap_is_50", CAP == 50, f"CAP={CAP}")

        # --- n > cap clamped ---
        print("\n[cap] n=100 > cap -> clamped, stderr warns")
        err_buf = io.StringIO()
        with redirect_stderr(err_buf):
            main(["--fixture", str(fixture_path), "--out", str(out_path), "--n", "100"])
        _check("clamp_warns", "clamping" in err_buf.getvalue(), err_buf.getvalue().strip())
        rows2 = _read_jsonl(out_path)
        _check("clamp_rows", len(rows2) == 3, f"expected 3, got {len(rows2)}")

        # --- cancel_resume: warm cache, same ids, no refetch ---
        print("\n[cancel_resume] warm id-cache -> same ids, no refetch")
        cache_dir = tmp / "lite_cache"
        cache_file = cache_dir / "lite_ids.json"
        pinned = [f"inst-{i:04d}" for i in range(50)]
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(pinned), encoding="utf-8")
        mtime_before = os.stat(cache_file).st_mtime_ns
        fetched = fetch_lite_ids(n=5, cap=50, cache_dir=str(cache_dir))
        mtime_after = os.stat(cache_file).st_mtime_ns
        _check("cache_ids", fetched == pinned[:5], f"got {fetched}")
        _check(
            "no_refetch",
            mtime_before == mtime_after,
            f"mtime {'unchanged' if mtime_before == mtime_after else 'changed'}",
        )

        # --- malformed_input: row missing instance_id ---
        print("\n[malformed_input] fixture row missing instance_id -> clear error")
        bad_fixture = tmp / "bad_fixture.json"
        bad_fixture.write_text(
            json.dumps([{"module": "x.py", "patch": "", "tests": ""}]), encoding="utf-8"
        )
        try:
            _load_fixture(str(bad_fixture))
            _check("malformed_raises", False, "no error raised")
        except ValueError as e:
            _check("malformed_raises", "row 0" in str(e), str(e))

        # --- stale_state: two runs, no append-duplication ---
        print("\n[stale_state] two runs -> no append-duplication")
        main(["--fixture", str(fixture_path), "--out", str(out_path), "--n", "10"])
        main(["--fixture", str(fixture_path), "--out", str(out_path), "--n", "10"])
        rows3 = _read_jsonl(out_path)
        _check("no_duplication", len(rows3) == 3, f"expected 3, got {len(rows3)}")

        # --- flaky_tests: two runs, same resolved booleans ---
        print("\n[flaky_tests] two runs -> same resolved booleans")
        main(["--fixture", str(fixture_path), "--out", str(out_path), "--n", "10"])
        run_a = _read_jsonl(out_path)
        main(["--fixture", str(fixture_path), "--out", str(out_path), "--n", "10"])
        run_b = _read_jsonl(out_path)
        for a, b in zip(run_a, run_b):
            _check(
                f"flaky_{a['instance_id']}",
                a["resolved"] == b["resolved"],
                f"run_a={a['resolved']} run_b={b['resolved']}",
            )

        # --- prompt_injection: patch text is data, not executed outside sandbox ---
        print("\n[prompt_injection] patch text is data, never outside sandbox")
        inject_fixture = tmp / "inject_fixture.json"
        inject_fixture.write_text(
            json.dumps(
                [
                    {
                        "instance_id": "test__inject-005",
                        "module": "inject.py",
                        "tests": "from inject import val\n\ndef test_val():\n    assert val == 42\n",
                        "patch": (
                            "val = 42\n"
                            "with open('marker_injection.txt', 'w') as f:\n"
                            "    f.write('injected')\n"
                        ),
                    }
                ]
            ),
            encoding="utf-8",
        )
        inject_out = tmp / "inject_results.jsonl"
        marker = Path.cwd() / "marker_injection.txt"
        if marker.exists():
            marker.unlink()
        main(["--fixture", str(inject_fixture), "--out", str(inject_out), "--n", "10"])
        _check("no_marker_outside_sandbox", not marker.exists(), "marker file created outside sandbox")
        if marker.exists():
            marker.unlink()
        inject_rows = _read_jsonl(inject_out)
        _check("inject_resolved", inject_rows[0]["resolved"] is True, "patch should resolve")
        _check("inject_label", inject_rows[0]["label_type"] == "harness_proxy", inject_rows[0]["label_type"])

    # --- Adversarial: others N/A ---
    print("\n[adversarial] others N/A:")
    print("  - budget_overflow: N/A (fixture mode, no credits)")
    print("  - gateway_down: N/A (fixture mode, no HTTP)")
    print("  - concurrent_writes: N/A (single-threaded runner)")
    print("  - partial_fetch: N/A (fixture mode, no HF fetch)")

    print("\n" + "=" * 60)
    print("ALL ASSERTIONS PASSED")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main_qa())
