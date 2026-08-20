"""QA audit for T14 threshold-tune gold run."""
import json, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
tune = ROOT / "data" / "tune.jsonl"
sparse = ROOT / "data" / "gold_sparse.jsonl"
dense = ROOT / "data" / "gold_dense.jsonl"
spend_f = ROOT / "data" / "spend.txt"

rows = []
if tune.exists():
    for line in tune.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))

spend_now = float(spend_f.read_text().strip()) if spend_f.exists() else 0
# T13 ended at this spend baseline (from data/spend.txt after dense gold)
spend_before = 11.392172
delta = spend_now - spend_before

k3 = "moonshotai/kimi-k3"
k3_count = sum(1 for r in rows if r.get("model_id") == k3)

per_model = {}
for r in rows:
    mid = r.get("model_id", "?")
    per_model[mid] = per_model.get(mid, 0) + 1

prompts_tune = {r.get("prompt", "") for r in rows}
sparse_prompts = set()
if sparse.exists():
    for line in sparse.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            sparse_prompts.add(r.get("prompt", ""))
dense_prompts = set()
if dense.exists():
    for line in dense.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            dense_prompts.add(r.get("prompt", ""))
overlap_sparse = prompts_tune & sparse_prompts
overlap_dense = prompts_tune & dense_prompts

PASS = 0; FAIL = 0; WARN = 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"  PASS: {name}")
    else:
        FAIL += 1; print(f"  FAIL: {name} {detail}")

def warn(name, cond, detail=""):
    global WARN
    if cond:
        print(f"  OK:   {name}")
    else:
        WARN += 1; print(f"  WARN: {name} {detail}")

check("tune row count > 0", len(rows) > 0, f"(count={len(rows)})")
check("zero K3 rows", k3_count == 0, f"(k3_count={k3_count})")
check("spend delta <= $4", delta <= 4.0, f"(delta=${delta:.4f})")
# Tune uses anchors-only deviation from dense-every-model spec
check("4 anchor models present", len(per_model) == 4, f"(models={list(per_model.keys())})")
min_cnt = min(per_model.values()) if per_model else 0
max_cnt = max(per_model.values()) if per_model else 0
check("per-model counts balanced", max_cnt - min_cnt <= 10, f"(min={min_cnt}, max={max_cnt})")
check("~300 unique queries", 280 <= len(prompts_tune) <= 320, f"(queries={len(prompts_tune)})")
warn("no prompt overlap with sparse gold", len(overlap_sparse) == 0, f"(overlap={len(overlap_sparse)})")
warn("no prompt overlap with dense gold", len(overlap_dense) == 0, f"(overlap={len(overlap_dense)})")
observed = [r for r in rows if not r.get("unobserved", False)]
n_tier = sum(1 for r in observed if r.get("success_tier"))
check("success_tier recorded for observed rows", n_tier == len(observed), f"(tiered={n_tier}, observed={len(observed)})")

print(f"\nrows={len(rows)} unique_queries={len(prompts_tune)} observed={len(observed)} k3={k3_count} delta=${delta:.4f}")
print("per-model:")
for mid, cnt in sorted(per_model.items(), key=lambda x: -x[1]):
    print(f"  {mid}: {cnt}")
print(f"\nSummary: {PASS} passed, {WARN} warnings, {FAIL} failed")
sys.exit(1 if FAIL else 0)
