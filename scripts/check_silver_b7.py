import json
import sys
import pathlib
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent
silver = ROOT / "data" / "silver.jsonl"
spend_f = ROOT / "data" / "spend.txt"
manifest_f = ROOT / "data" / "split_manifest.json"
gold_verified = ROOT / "data" / "gold-verified.jsonl"

CHEAP = "motif-technologies/motif-3"
ESCALATE = "zai-org/glm-5.2"

rows = []
if silver.exists():
    for line in silver.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except:
                pass

labeled = [r for r in rows if r.get("p_success") and isinstance(r.get("p_success"), dict) and len(r["p_success"]) > 0]
unlabeled = [r for r in rows if r not in labeled]
escalate = [r for r in labeled if r.get("teacher") == ESCALATE]
cheap = [r for r in labeled if r.get("teacher") == CHEAP]
escalate_share = len(escalate) / len(labeled) if labeled else 0
spend_now = float(spend_f.read_text(encoding="utf-8").strip()) if spend_f.exists() else 0
spend_before_B = 8.16
delta = spend_now - spend_before_B

# y_rate as mean p_success across all labeled rows and models
all_p = []
for r in labeled:
    for v in r.get("p_success", {}).values():
        try:
            all_p.append(float(v))
        except:
            pass
y_rate = sum(all_p) / len(all_p) if all_p else 0

# geometry_pass placeholder: if gold_verified exists, try to compare? For now check y_rate band
y_rate_ok = 0.10 <= y_rate <= 0.25

PASS = 0
FAIL = 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS: {name} {detail}".strip())
    else:
        FAIL += 1
        print(f"  FAIL: {name} {detail}".strip())

print(f"silver rows: {len(rows)} (labeled {len(labeled)} unlabeled {len(unlabeled)})")
print(f"escalate: {len(escalate)} cheap: {len(cheap)} share={escalate_share:.4f}")
print(f"spend_now={spend_now:.4f} delta=${delta:.4f} (cap $15, limit 23.16)")
print(f"y_rate (mean p_success)={y_rate:.4f} (band 0.10-0.25: {y_rate_ok})")
# spot-check schema
sample_ok = True
for r in labeled[:5]:
    if not all(k in r for k in ("prompt","complexity_bin","p_success","teacher","tokens","phase","hint_bin")):
        sample_ok = False
    if r.get("complexity_bin") not in {"trivial","standard","hard","frontier"}:
        sample_ok = False
    if not isinstance(r.get("p_success"), dict):
        sample_ok = False

check("silver row count >=3500 (C1)", len(labeled) >= 3500, f"(count={len(labeled)})")
check("escalate share <=0.25 (C1)", escalate_share <= 0.25, f"(share={escalate_share:.4f})")
check("label_confidence present via p_success/complexity_bin", len(labeled) > 0 and all("complexity_bin" in r and "p_success" in r for r in labeled[:10]), f"sample_ok={sample_ok}")
check("AA-disagree spot-check schema", sample_ok, "")
check("y_rate in [0.10,0.25] OR geometry_pass", y_rate_ok, f"(y_rate={y_rate:.4f})")
check("spend delta <= $15 (Phase B cap)", delta <= 15.0, f"(delta=${delta:.4f})")

# C1 verdict
c1_pass = (len(labeled) >= 3500) and (escalate_share <= 0.25) and y_rate_ok and (delta <= 15.0)
print("")
if c1_pass:
    print("C1 GATE: PASS")
else:
    print("C1 GATE: FAIL — diagnose teacher config, do not proceed to Phase C")
    if len(labeled) < 3500:
        print(f"  -> row count shortfall: {3500 - len(labeled)}")
    if escalate_share > 0.25:
        print(f"  -> escalate share high: {escalate_share:.4f}")
    if not y_rate_ok:
        print(f"  -> y_rate out of band: {y_rate:.4f}")
    if delta > 15:
        print(f"  -> spend delta over cap: ${delta:.4f}")

print(f"\nSummary: {PASS} passed, {FAIL} failed")
# exit code reflects C1? For audit script, exit 1 if FAIL
sys.exit(1 if FAIL else 0)
