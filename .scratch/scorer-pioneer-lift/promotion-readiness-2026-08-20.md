# Verified session-gold promotion readiness (unpaid)

**Verdict:** `promotion_readiness_unpaid`
**Session gold:** `False` · **Production parity:** `False`
**Scaffold:** `D:\aiand-router\data\verified_ids_scaffold.json` (valid=True, n=500)
**Serve candidate (shadow):** `D:\aiand-router\data\scorer-hard-logistic.json`

> Does **not** flip `TRAINED_PATH=trained`. Paid HTTP requires operator budget approval.
> Prototype-ready (demo bar): `True` · Production parity: `False` · Remote scale ready: `False`

## Resolve floor paths (local_image_farm vs remote_eval)

- Preferred scale path: **`remote_eval_auth_pending`**
- `local_image_farm`: scale_ready=False (disk_blocked_no_mass_pull)
- `remote_eval`: scale_ready=False (auth_pending_modal_or_sb_cli); adapter `scripts/swe_eval_cmd.py --backend modal|sb-cli`
- Modal: configured=False (toml=False, pkg=True)
- sb-cli: configured=False (cli=False, key=False)
- Disk-light doc: `D:\aiand-router\.scratch\scorer-pioneer-lift\disk-light-parity-path-2026-08-20.md`

## Live filectx sessions (tiny-n canary)

- path: `D:\aiand-router\data\verified_session_filectx_all.jsonl`
- unique=12 · session_gold=10 (floor 300; below_floor=True)

## Session-joined cost sample

- doc: `D:\aiand-router\.scratch\scorer-pioneer-lift\session-joined-cost-sample-2026-08-20.md`
- session_joined=True · n_joinable≈10 · joined rcd≈-0.00162
- verdict `bounded_check_only` — Live join works after gateway restart; sample n≪300 — not promotion evidence

## Local replay proxy (not session gold)

- `local_replay_gate_pass`: **True**
- n=89 gateway success-gold proxy
- trained success: 0.11235955056179775
- rules success: 0.02247191011235955
- rules_cost_delta: 0.0006868617977528091
- savings_vs_most_expensive: 0.0008993840449438203
- parity_blockers: `not_spec_floors, eval_n=89_below_verified_floor_300, rules_cost_delta_not_negative, ece_equal_mass_waived_small_n, no_session_gold_promotion_gate`

## Runbook §(a) gate checklist

- **quality_session_gold** — `not_started`: session gold (tests_passed / resolve) >= rules - 0.01 absolute — requires live Verified session gold (tests_passed / patch resolve), not gateway proxy
- **quality_escalate** — `not_started`: per-request escalate rate >= rules - 0.01 absolute — requires live Verified session gold (tests_passed / patch resolve), not gateway proxy
- **cost_rules_delta** — `proxy_fail`: rules_cost_delta < 0 (trained - rules list-price USD; equal -> no promote) — ship serve gateway proxy rules_cost_delta=0.000687 (need < 0 at promotion scale)
- **calibration_bss** — `proxy_pass`: Brier skill score (BSS) > 0 on selected hops — gateway proxy BSS=0.000631 on n=89 (not flywheel hops)
- **calibration_ece_width** — `proxy_pass`: equal-width ECE (M=10) <= 0.03 — gateway proxy equal-width ECE=0.006877
- **calibration_ece_mass** — `waived_small_n`: equal-mass ECE (M=10) <= 0.03 when n_selected >= 150 — equal-mass ECE=0.143 waived (n=89 < 150)
- **floor_session_gold_n** — `scaffold_only_remote_auth_pending`: n >= 300 session-gold tasks (primary split n=500); resolve via local_image_farm OR remote_eval (Modal/sb-cli/ephemeral) — ids scaffold n=500 meets primary split; session_gold=false — need paid dual-policy + resolve (auth Modal/sb-cli first); live_session_gold=10/300; local_image_farm=disk_blocked_no_mass_pull; remote_eval=auth_pending_modal_or_sb_cli

## Budget estimate (list-price)

- n_instances: 500
- enabled models: 9
- shadow dual-policy session gate (est.): **$5.06**
- dense all-models upper bound (est.): $13.01
- shadow_dual_policy_session_gate_est_usd is a turn-loop router/auto estimate (not train gold --dense). dense_* is runbook upper-bound if every model ran per instance.

## Dual-policy run plan

### unpaid · refresh_ids_scaffold

```powershell
$env:PYTHONPATH='src'
python -m aiand_router.lite_runner --ids-only --bench verified --n 500 --out D:/aiand-router/data/verified_ids_scaffold.json
```

### unpaid · promotion_readiness

```powershell
$env:PYTHONPATH='src'
python -m aiand_router.promotion_gate --scaffold D:/aiand-router/data/verified_ids_scaffold.json --artifact D:/aiand-router/data/scorer-hard-logistic.json --models D:/aiand-router/config/models.yaml --gold data/gold-verified.jsonl
```

### unpaid · local_replay_proxy

```powershell
$env:PYTHONPATH='src'
python -m aiand_router.replay_report --gold data/gold-verified.jsonl --artifact D:/aiand-router/data/scorer-hard-logistic.json --models D:/aiand-router/config/models.yaml
```

### unpaid · bounded_dual_policy_fixture

```powershell
$env:PYTHONPATH='src'
python scripts/run_lite_comparison.py
```
- harness-proxy only; verdict bounded_check_only

### unpaid · modal_auth_probe

```powershell
$env:PYTHONPATH='src'
python scripts/swe_eval_cmd.py --backend modal --instance django__django-11099 --patch data/_gold_django_11099.patch
```
- Expect not_available/modal_not_configured until `modal token new`. No local docker pull.

### human_auth · modal_token_new

```powershell
$env:PYTHONPATH='src'
pip install modal 'swebench[modal]'
modal token new
# then re-run modal_auth_probe
```
- 3-step auth: install → token new → unpaid gold-patch probe

### paid_requires_budget · start_gateway_shadow

```powershell
$env:PYTHONPATH='src'
# PowerShell:
$env:PYTHONPATH='src'
$env:TRAINED_PATH='shadow'
$env:SCORER_PATH='data/scorer-hard-logistic.json'
uvicorn aiand_router.app:app --app-dir src --host 127.0.0.1 --port 8000
```

### paid_requires_budget · verified_session_smoke

```powershell
$env:PYTHONPATH='src'
python -m aiand_router.verified_runner --limit 2 --scaffold D:/aiand-router/data/verified_ids_scaffold.json --gateway http://127.0.0.1:8000 --out data/verified_session_smoke.jsonl
```
- Prefer local images + git filectx for edit; set SWE_EVAL_BACKEND=modal for resolve once auth'd

### paid_requires_budget · verified_session_gate

```powershell
$env:PYTHONPATH='src'
python -m aiand_router.verified_runner --scaffold D:/aiand-router/data/verified_ids_scaffold.json --gateway http://127.0.0.1:8000 --out data/verified_session_results.jsonl
```
- Primary split n=500; remote_eval floor preferred on this host

### paid_requires_budget · gate_check_eval

```powershell
$env:PYTHONPATH='src'
python -m aiand_router.eval --gate --log data/requests.jsonl --sessions data/verified_session_results.jsonl
```

### unpaid · verified_session_dry_run

```powershell
$env:PYTHONPATH='src'
python -m aiand_router.verified_runner --dry-run --limit 500 --scaffold D:/aiand-router/data/verified_ids_scaffold.json
```

## Code / plumbing gaps

- trained session-gold quality bar needs dual-policy session rows (keep TRAINED_PATH=shadow for demo)
- full n=500 Verified session gate prefers remote_eval (Modal/sb-cli); local_image_farm disk-blocked here
- prototype demo kit: .scratch/scorer-pioneer-lift/prototype-demo-2026-08-20.md

**Ready for paid session gate (scaffold + local replay only):** `True`