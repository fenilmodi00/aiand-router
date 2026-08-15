#!/usr/bin/env python3
"""Assert-first QA for `python -m aiand_router.pool ingest --profile spec --fixture-dir`.

Runs the ingest on local fixtures (no network, no aiand credits), then asserts:
  1. Known SWE-bench Verified instance_ids are absent from the output rows.
  2. collision_dropped count > 0 is printed.
  3. stratum_histogram line is printed with bin=/phase=/tools= axes.
  4. malformed line count > 0 is printed (corrupt JSONL line in fixture).
  5. license_dropped count > 0 is printed (GPL-licensed rebench row).
  6. Re-run produces identical output (idempotent / cancel_resume).
  7. Output file is atomically replaced, not appended (stale_state).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
if not Path(PY).exists():
    PY = sys.executable
FIXTURE = ROOT / "tests" / "fixtures" / "pool_spec"
VERIFIED_IDS = ["django__django-11099", "astropy__astropy-12907"]
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src")}


def _run_ingest(out_path: Path) -> str:
    cmd = [
        PY, "-m", "aiand_router.pool", "ingest",
        "--profile", "spec",
        "--fixture-dir", str(FIXTURE),
        "--out", str(out_path),
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=str(ROOT), env=ENV, timeout=60
    )
    if result.returncode != 0:
        print(f"FAIL: ingest exited {result.returncode}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return result.stdout


def _read_out(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> int:
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        out1 = Path(tmp) / "ingest1.jsonl"
        stdout1 = _run_ingest(out1)
        rows1 = _read_out(out1)

        # 1. Verified ids absent from output rows
        out_ids = {str(r.get("instance_id") or "").lower() for r in rows1}
        for vid in VERIFIED_IDS:
            if vid in out_ids:
                failures.append(f"FAIL: {vid} should be absent but is in output rows")

        # 2. collision_dropped > 0
        if "collision_dropped=0" in stdout1 or "collision_dropped=" not in stdout1:
            failures.append("FAIL: collision_dropped should be > 0")
        else:
            for line in stdout1.splitlines():
                if "collision_dropped=" in line:
                    val = int(line.split("collision_dropped=")[1].split()[0])
                    if val <= 0:
                        failures.append(f"FAIL: collision_dropped={val} should be > 0")
                    break

        # 3. histogram with bin=/phase=/tools= axes
        if "stratum_histogram:" not in stdout1:
            failures.append("FAIL: stratum_histogram: line missing")
        if "bin=" not in stdout1:
            failures.append("FAIL: bin= axis missing from histogram")
        if "phase=" not in stdout1:
            failures.append("FAIL: phase= axis missing from histogram")
        if "tools=" not in stdout1:
            failures.append("FAIL: tools= axis missing from histogram")

        # 4. malformed > 0
        if "malformed=" not in stdout1:
            failures.append("FAIL: malformed= count missing from output")
        else:
            for line in stdout1.splitlines():
                if "malformed=" in line:
                    val = int(line.split("malformed=")[1].split()[0])
                    if val <= 0:
                        failures.append(f"FAIL: malformed={val} should be > 0")
                    break

        # 5. license_dropped > 0
        if "license_dropped=" not in stdout1:
            failures.append("FAIL: license_dropped= count missing from output")
        else:
            for line in stdout1.splitlines():
                if "license_dropped=" in line:
                    val = int(line.split("license_dropped=")[1].split()[0])
                    if val <= 0:
                        failures.append(f"FAIL: license_dropped={val} should be > 0")
                    break

        # 6. idempotent re-run (cancel_resume)
        out2 = Path(tmp) / "ingest2.jsonl"
        stdout2 = _run_ingest(out2)
        rows2 = _read_out(out2)
        if stdout1 != stdout2:
            failures.append("FAIL: re-run stdout differs (not idempotent)")
        if len(rows1) != len(rows2):
            failures.append(
                f"FAIL: re-run row count differs ({len(rows1)} vs {len(rows2)})"
            )
        ids1 = sorted(r.get("instance_id", "") for r in rows1)
        ids2 = sorted(r.get("instance_id", "") for r in rows2)
        if ids1 != ids2:
            failures.append("FAIL: re-run instance_ids differ")

        # 7. stale_state: same --out path re-run does not append-duplicate
        out3 = Path(tmp) / "ingest_reuse.jsonl"
        _run_ingest(out3)
        _run_ingest(out3)
        rows3 = _read_out(out3)
        if len(rows3) != len(rows1):
            failures.append(
                f"FAIL: re-run on same --out path changed row count "
                f"({len(rows3)} vs {len(rows1)}) — append-duplication"
            )

    # BFCL cap: bfcl rows in output must be <= 15% of pre-cap total.
    # Pre-cap total = post-cap total + dropped bfcl. We verify the cap fired
    # by checking bfcl rows < bfcl fixture rows (6) when total is small.
    n_bfcl = sum(1 for r in rows1 if r.get("source") == "bfcl")
    bfcl_fixture = len(_read_out(FIXTURE / "bfcl.jsonl"))
    if bfcl_fixture > 0 and n_bfcl > int((len(rows1) + (bfcl_fixture - n_bfcl)) * 0.15):
        failures.append(
            f"FAIL: bfcl rows {n_bfcl} exceed 15% cap of pre-cap total"
        )

    # prompt_injection: no eval/exec in source
    pool_src = (ROOT / "src" / "aiand_router" / "pool.py").read_text(encoding="utf-8")
    for danger in ("eval(", "exec(", "os.system", "subprocess.call"):
        if danger in pool_src:
            failures.append(f"FAIL: {danger} found in pool.py source")

    print(f"rows={len(rows1)} bfcl={n_bfcl}")
    print(f"stdout:\n{stdout1}")

    if failures:
        for f in failures:
            print(f, file=sys.stderr)
        return 1

    print("ALL ASSERTIONS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
