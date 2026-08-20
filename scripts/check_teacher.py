import json, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
silver = ROOT / "data" / "silver.jsonl"
spend_f = ROOT / "data" / "spend.txt"
rows = []
if silver.exists():
    for line in silver.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
labeled = sum(1 for r in rows if r.get("p_success") and len(r.get("p_success", {})) > 0)
escalate = sum(1 for r in rows if r.get("teacher") and r.get("teacher") != "motif-technologies/motif-3")
share = escalate / len(rows) if rows else 0
spend_now = float(spend_f.read_text().strip()) if spend_f.exists() else 0
spend_before = 8.157082
delta = spend_now - spend_before
PASS = 0; FAIL = 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond: PASS += 1; print(f"  PASS: {name}")
    else: FAIL += 1; print(f"  FAIL: {name} {detail}")
check("silver row count > 0", len(rows) > 0, f"(count={len(rows)})")
check("labeled rows > 0", labeled > 0, f"(labeled={labeled})")
check("escalate share <= 25%", share <= 0.25, f"(share={share:.4f})")
check("spend delta <= $8", delta <= 8.0, f"(delta=${delta:.4f})")
print(f"\nrows={len(rows)} labeled={labeled} unlabeled={len(rows)-labeled} escalate={escalate} share={share:.4f} delta=${delta:.4f}")
print(f"Summary: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
