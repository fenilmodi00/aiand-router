"""Merge batch5 into verified_session_filectx_all.jsonl and print local-12 summary."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sources = [
    ROOT / "data" / "verified_session_filectx_all.jsonl",
    ROOT / "data" / "verified_session_filectx_batch5.jsonl",
]
by: dict[str, dict] = {}
order: list[str] = []
for src in sources:
    if not src.exists():
        continue
    for line in src.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        iid = str(r.get("instance_id") or "")
        if not iid:
            continue
        prev = by.get(iid)
        if prev is None:
            by[iid] = r
            order.append(iid)
            continue
        if r.get("session_gold") and not prev.get("session_gold"):
            by[iid] = r
        elif r.get("session_gold") == prev.get("session_gold"):
            by[iid] = r

out = ROOT / "data" / "verified_session_filectx_all.jsonl"
out.write_text(
    "\n".join(json.dumps(by[i], ensure_ascii=False) for i in order) + "\n",
    encoding="utf-8",
)

local12 = [
    "django__django-10880",
    "django__django-10914",
    "django__django-11066",
    "django__django-11099",
    "django__django-11532",
    "django__django-11880",
    "django__django-12754",
    "django__django-13512",
    "django__django-13786",
    "django__django-14011",
    "django__django-14140",
    "django__django-15252",
]
gold = [i for i in local12 if by.get(i, {}).get("session_gold")]
miss = [i for i in local12 if not by.get(i, {}).get("session_gold")]
print("unique", len(by), "local12_gold", len(gold))
print("gold_ids", gold)
print("still_miss", miss)
for i in local12:
    r = by.get(i, {})
    pol = (r.get("policies") or {}).get("rules") or {}
    print(
        f"{i}: gold={r.get('session_gold')} label={r.get('label_type')} "
        f"fctx={r.get('file_context_source')} reason={pol.get('swe_eval_reason')}"
    )

import os

proc = subprocess.run(
    [
        sys.executable,
        "-m",
        "aiand_router.eval",
        "--gate",
        "--log",
        str(ROOT / "data" / "requests.jsonl"),
        "--sessions",
        str(out),
    ],
    cwd=str(ROOT),
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
    env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
)
print("--- eval gate ---")
print(proc.stdout[-2000:] if proc.stdout else "")
print(proc.stderr[-1000:] if proc.stderr else "")
print("gate_exit", proc.returncode)
print("spend", (ROOT / "data" / "spend.txt").read_text(encoding="utf-8").strip())
