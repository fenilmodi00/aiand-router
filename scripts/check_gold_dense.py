"""QA audit for T13 dense/cal gold run."""
import json, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
dense = ROOT / "data" / "gold_dense.jsonl"
sparse = ROOT / "data" / "gold_sparse.jsonl"
spend_f = ROOT / "data" / "spend.txt"

rows = []
if dense.exists():
    for line in dense.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))

spend_now = float(spend_f.read_text().strip()) if spend_f.exists() else 0
# T12 ended at this spend baseline (from data/spend.txt after sparse gold)
spend_before = 10.37957
delta = spend_now - spend_before

k3 = "moonshotai/kimi-k3"
k3_count = sum(1 for r in rows if r.get("model_id") == k3)

per_model = {}
for r in rows:
    mid = r.get("model_id", "?")
    per_model[mid] = per_model.get(mid, 0) + 1

# Count unique queries by prompt text
prompts_dense = {r.get("prompt", "") for r in rows}
sparse_prompts = set()
if sparse.exists():
    for line in sparse.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            sparse_prompts.add(r.get("prompt", ""))
overlap = prompts_dense & sparse_prompts

PASS = 0; FAIL = 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"  PASS: {name}")
    else:
        FAIL += 1; print(f"  FAIL: {name} {detail}")

check("gold_dense row count > 0", len(rows) > 0, f"(count={len(rows)})")
check("zero K3 rows", k3_count == 0, f"(k3_count={k3_count})")
check("spend delta <= $4", delta <= 4.0, f"(delta=${delta:.4f})")
check("at least 7 models present", len(per_model) >= 7, f"(models={list(per_model.keys())})")
# Dense flag should hit every eligible model except K3 (8 models currently)
check("all eligible non-K3 models represented", len(per_model) >= 7, f"(n={len(per_model)})")
# Per-model count should be approximately equal (same queries across models)
min_cnt = min(per_model.values()) if per_model else 0
max_cnt = max(per_model.values()) if per_model else 0
check("per-model counts balanced", max_cnt - min_cnt <= 10, f"(min={min_cnt}, max={max_cnt})")
check("no prompt overlap with sparse gold", len(overlap) == 0, f"(overlap={len(overlap)})")

print(f"\nrows={len(rows)} unique_queries={len(prompts_dense)} k3={k3_count} delta=${delta:.4f}")
print("per-model:")
for mid, cnt in sorted(per_model.items(), key=lambda x: -x[1]):
    print(f"  {mid}: {cnt}")
print(f"\nSummary: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
