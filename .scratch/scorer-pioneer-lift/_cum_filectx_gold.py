"""Unpaid: cumulative session_gold across filectx session artifacts."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

FILES = [
    "verified_session_swe_smoke_filectx.jsonl",
    "verified_session_filectx_batch.jsonl",
    "verified_session_filectx_n5.jsonl",
    "verified_session_filectx_11066.jsonl",
    "verified_session_filectx_n5_remain.jsonl",
    "verified_session_filectx_batch2.jsonl",
    "verified_session_filectx_batch3.jsonl",
    "verified_session_filectx_batch4.jsonl",
]


def main() -> None:
    seen: dict[str, dict] = {}
    for name in FILES:
        path = DATA / name
        if not path.exists():
            print(f"missing {name}")
            continue
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            iid = str(r["instance_id"])
            gold = bool(r.get("session_gold"))
            rows.append((iid, gold, r.get("label_type"), r.get("file_context_source")))
            prev = seen.get(iid)
            if prev is None or (gold and not prev["gold"]):
                seen[iid] = {
                    "gold": gold,
                    "label": r.get("label_type"),
                    "fctx": r.get("file_context_source"),
                    "file": name,
                }
            elif gold == prev["gold"]:
                seen[iid]["file"] = name  # latest artifact
        g = sum(1 for _, gold, _, _ in rows if gold)
        print(f"{name}: n={len(rows)} gold={g}/{len(rows)}")
        for iid, gold, lt, fx in rows:
            print(f"  {iid} gold={gold} {lt} {fx}")

    ug = sum(1 for v in seen.values() if v["gold"])
    print(f"=== unique instances across filectx artifacts ===")
    print(f"unique={len(seen)} session_gold={ug}")
    for iid, v in sorted(seen.items()):
        print(f"  {iid} gold={v['gold']} {v['label']} via {v['file']}")


if __name__ == "__main__":
    main()
