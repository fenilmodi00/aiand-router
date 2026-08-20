import json, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from aiand_router.scorer import load_scorer, score_eligible
from aiand_router.router import load_config, load_models

scorer_path = ROOT / "data" / "scorer.json"
cfg_path = ROOT / "config" / "models.yaml"

artifact = load_scorer(scorer_path)
cfg = load_config(cfg_path)
models = load_models(cfg)
eligible_ids = [m.id for m in models if m.enabled]

PASS = 0; FAIL = 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"  PASS: {name}")
    else:
        FAIL += 1; print(f"  FAIL: {name} {detail}")

check("scorer.json loads", artifact is not None)
check("not_spec_floors flag", artifact.get("not_spec_floors") is True)
check("calibrator present", "calibrator" in artifact and "mode" in artifact["calibrator"], f"(cal={artifact.get('calibrator')})")
check("n_gold present", isinstance(artifact.get("n_gold"), int), f"(n_gold={artifact.get('n_gold')})")
check("n_cal present", isinstance(artifact.get("n_cal"), int), f"(n_cal={artifact.get('n_cal')})")
check("n_silver present", isinstance(artifact.get("n_silver"), int), f"(n_silver={artifact.get('n_silver')})")

bin_, p_success = score_eligible(artifact, eligible_ids, phase="edit", needs_tools=True, tokens=500)
check("score_eligible returns a bin", bin_ in {"trivial","standard","hard","frontier"}, f"(bin={bin_})")
check("score_eligible returns p_success for all eligible", set(p_success.keys()) == set(eligible_ids), f"(got={len(p_success)}, want={len(eligible_ids)})")
all_in_range = all(0.0 <= v <= 1.0 for v in p_success.values())
check("all p_success in [0,1]", all_in_range, f"(range={min(p_success.values()) if p_success else None}-{max(p_success.values()) if p_success else None})")

# max effort scenario: K3 eligible (premium floor bypassed)
max_ids = [m.id for m in models if m.enabled]
bin_max, p_max = score_eligible(artifact, max_ids, phase="plan", needs_tools=False, tokens=200)
check("max-effort K3 has a score", "moonshotai/kimi-k3" in p_max, f"(keys={list(p_max.keys())})")
if "moonshotai/kimi-k3" in p_max:
    check("K3 p_success in [0,1]", 0.0 <= p_max["moonshotai/kimi-k3"] <= 1.0, f"(p={p_max['moonshotai/kimi-k3']})")

print(f"\nartifact n_gold={artifact.get('n_gold')} n_cal={artifact.get('n_cal')} n_silver={artifact.get('n_silver')} calibrator={artifact.get('calibrator',{}).get('mode')}")
print(f"bin={bin_} p_success samples:")
for mid, p in sorted(p_success.items(), key=lambda x: -x[1])[:8]:
    print(f"  {mid}: {p:.3f}")
print(f"\nSummary: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
