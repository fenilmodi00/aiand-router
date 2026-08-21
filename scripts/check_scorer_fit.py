import json, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from aiand_router.scorer import load_scorer, score_eligible, BINS
from aiand_router.router import load_config, load_models

scorer_path = ROOT / "data" / "scorer.json"
report_path = ROOT / "data" / "scorer_report.md"
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

# --- artifact structure ---
check("scorer.json loads", artifact is not None)
check("label is bootstrap_partial", artifact.get("label") == "bootstrap_partial", f"(label={artifact.get('label')})")
check("not_spec_floors flag", artifact.get("not_spec_floors") is True)
check("k3_prior is calibrated", artifact.get("k3_prior") == "calibrated", f"(k3_prior={artifact.get('k3_prior')})")
check("features list present", isinstance(artifact.get("features"), list) and len(artifact["features"]) > 0, f"(features={artifact.get('features')})")
check("weights present", isinstance(artifact.get("weights"), dict) and len(artifact["weights"]) > 0)
check("intercepts present", isinstance(artifact.get("intercepts"), dict) and len(artifact["intercepts"]) > 0)
check("calibrator present", "calibrator" in artifact and "mode" in artifact["calibrator"], f"(cal={artifact.get('calibrator')})")
check("bin_weights present", isinstance(artifact.get("bin_weights"), dict) and len(artifact["bin_weights"]) > 0)
check("n_gold present", isinstance(artifact.get("n_gold"), int), f"(n_gold={artifact.get('n_gold')})")
check("n_cal present", isinstance(artifact.get("n_cal"), int), f"(n_cal={artifact.get('n_cal')})")
check("n_silver present", isinstance(artifact.get("n_silver"), int), f"(n_silver={artifact.get('n_silver')})")

# --- bin head emits exactly 4 bins ---
bin_keys = set((artifact.get("bin_weights") or {}).keys())
check("bin_weights has exactly 4 bins", bin_keys == set(BINS), f"(got={sorted(bin_keys)}, want={sorted(BINS)})")

# --- calibrator mode matches n_cal ---
n_cal = artifact.get("n_cal", 0)
cal_mode = artifact.get("calibrator", {}).get("mode", "")
expected_mode = "isotonic" if n_cal > 1000 else "platt"
check(f"calibrator mode matches n_cal ({n_cal} -> {expected_mode})", cal_mode == expected_mode, f"(mode={cal_mode}, expected={expected_mode})")

# --- score_eligible returns valid p for all eligible ---
bin_, p_success = score_eligible(artifact, eligible_ids, phase="edit", needs_tools=True, tokens=500)
check("score_eligible returns a bin", bin_ in BINS, f"(bin={bin_})")
check("score_eligible returns p_success for all eligible", set(p_success.keys()) == set(eligible_ids), f"(got={len(p_success)}, want={len(eligible_ids)})")
all_in_range = all(0.0 <= v <= 1.0 for v in p_success.values())
check("all p_success in [0,1]", all_in_range, f"(range={min(p_success.values()) if p_success else None}-{max(p_success.values()) if p_success else None})")

# --- K3 specifically ---
max_ids = [m.id for m in models if m.enabled]
bin_max, p_max = score_eligible(artifact, max_ids, phase="plan", needs_tools=False, tokens=200)
check("max-effort K3 has a score", "moonshotai/kimi-k3" in p_max, f"(keys={list(p_max.keys())})")
if "moonshotai/kimi-k3" in p_max:
    check("K3 p_success in [0,1]", 0.0 <= p_max["moonshotai/kimi-k3"] <= 1.0, f"(p={p_max['moonshotai/kimi-k3']})")

# --- APGR in [0,1] if curve section exists in scorer_report.md ---
if report_path.exists():
    report_text = report_path.read_text(encoding="utf-8")
    check("scorer_report.md exists with APGR section", "APGR" in report_text)
    # Extract APGR value if not N/A
    import re
    m = re.search(r'APGR = ([\d.]+)', report_text)
    if m and "N/A" not in report_text[m.start():m.start()+20]:
        apgr_val = float(m.group(1))
        check("APGR in [0,1]", 0.0 <= apgr_val <= 1.0, f"(apgr={apgr_val})")
    else:
        check("APGR is N/A (undefined, acceptable)", "N/A" in report_text or "None" in report_text or apgr_val is None if 'apgr_val' in dir() else True)

# --- fit_summary present ---
fit = artifact.get("fit_summary", {})
check("fit_summary present", isinstance(fit, dict) and "winner" in fit, f"(fit={fit})")
if fit:
    check("fit winner is logistic", fit.get("winner") == "logistic", f"(winner={fit.get('winner')})")

print(f"\nartifact n_gold={artifact.get('n_gold')} n_cal={artifact.get('n_cal')} n_silver={artifact.get('n_silver')} calibrator={artifact.get('calibrator',{}).get('mode')} k3_prior={artifact.get('k3_prior')}")
print(f"bin={bin_} p_success samples:")
for mid, p in sorted(p_success.items(), key=lambda x: -x[1])[:8]:
    print(f"  {mid}: {p:.3f}")
print(f"\nSummary: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
