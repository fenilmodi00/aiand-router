"""QA audit for T12 sparse gold run."""
import json, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
gold = ROOT / "data" / "gold_sparse.jsonl"
spend_f = ROOT / "data" / "spend.txt"

rows = []
if gold.exists():
    for line in gold.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))

spend_now = float(spend_f.read_text().strip()) if spend_f.exists() else 0
spend_before = 8.714928
delta = spend_now - spend_before

k3 = "moonshotai/kimi-k3"
k3_count = sum(1 for r in rows if r.get("model_id") == k3)

anchors = {}
for r in rows:
    mid = r.get("model_id", "?")
    anchors[mid] = anchors.get(mid, 0) + 1

PASS = 0; FAIL = 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond: PASS += 1; print(f"  PASS: {name}")
    else: FAIL += 1; print(f"  FAIL: {name} {detail}")

check("gold_sparse row count > 0", len(rows) > 0, f"(count={len(rows)})")
check("zero K3 rows", k3_count == 0, f"(k3_count={k3_count})")
check("spend delta <= $22", delta <= 22.0, f"(delta=${delta:.4f})")
check("at least 2 anchors present", len(anchors) >= 2, f"(anchors={list(anchors.keys())})")
check("at least 500 cells", len(rows) >= 500, f"(cells={len(rows)})")

print(f"\nrows={len(rows)} k3={k3_count} delta=${delta:.4f}")
print("per-anchor:")
for mid, cnt in sorted(anchors.items(), key=lambda x: -x[1]):
    print(f"  {mid}: {cnt}")
print(f"\nSummary: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
