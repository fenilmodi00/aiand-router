# Prototype demo kit — routing approach works with enough compute (2026-08-20)

**New success bar (reframed):** honestly claim a **prototype/demo** — *with enough compute (Modal/remote eval + paid gold), this routing approach works.*  
**Not required for this stop:** local ~1TB image farm, `TRAINED_PATH=trained`, or Fireworks/Pioneer **production** parity.

**Verdict under new bar:** **MET (prototype-ready).** Production parity remains **incomplete**.

---

## Prototype claim (use this wording)

The AIand scorer router is a **runnable shadow prototype**: Mix1 hard-logistic transfers on frozen verified holdout (replay gate pass; trained proxy succ ≫ rules), live session-gold harness works on the 12 local images (**10/12**), session-id cost join and conversation stickiness are wired, and disk-light resolve is already behind `SWE_EVAL_BACKEND=modal|sb-cli`. With Modal (or sb-cli) auth plus paid dual-policy gold at scale, the same path extends to runbook §(a) floors without retaining a local image farm. This is **not** a claim of production parity, serve flip, or FireRouter-class cascade savings.

---

## What we proved (evidence pointers)

| Piece | Status | Where |
| --- | --- | --- |
| Research / strategy (FireRouter + Pioneer + debate) | **Complete** | `.scratch/trained-router/research/scorer-router-fireworks-pioneer-debate.md` |
| Shadow serve candidate | **Frozen** | `data/scorer-hard-logistic.json` + `config/models.yaml` (`path=shadow`) |
| Cost overlay (shadow-only clear of rcd) | **Experiment** | `data/scorer-hard-logistic-cost-overlay.json` + `config/models.cost-overlay-t015.yaml` |
| Session gold path | **10/12** local | `data/verified_session_filectx_all.jsonl` |
| Session-joined cost | **Sample** (`n_joinable=10`, joined rcd≈−0.00162) | `session-joined-cost-sample-2026-08-20.md` |
| Stickiness | **Gateway present** | `firerouter-stickiness-2026-08-20.md`; `tests/test_conversation_sticky.py` |
| Disk-light remote resolve adapter | **Wired** | `scripts/swe_eval_cmd.py` (`--backend modal\|sb-cli\|local`); `disk-light-parity-path-2026-08-20.md` |
| Lite / bounded fixture | **Proxy only** | `data/bounded_gate_report.md`; `python scripts/run_lite_comparison.py` |
| Promotion readiness (floors labeled) | **Scaffold** | `python -m aiand_router.promotion_gate` — distinguishes `local_image_farm` vs `remote_eval` |

---

## What we do **NOT** claim

- Fireworks or Pioneer **capability / production** parity
- `TRAINED_PATH=trained` or replacing the serve candidate
- Ship serve `rules_cost_delta < 0` (overlay clears only as shadow; −2.2 pp proxy succ)
- Floor n≥300 session gold (10/12 canary only)
- FireRouter cascade product (0 redirects at ship knobs)
- That Modal auth is done on this host (probe → `modal_not_configured`)

---

## Modal / sb-cli status (this host, 2026-08-20)

| Backend | Status | Probe JSON reason |
| --- | --- | --- |
| Modal | Client installed; **no** `~/.modal.toml`; `token_id` null | `modal_not_configured` |
| sb-cli | Not installed; no `SWEBENCH_API_KEY` | `sb_cli_missing` |

### Human auth checklist (3 steps — Modal preferred)

1. **Install:** `pip install modal 'swebench[modal]'`
2. **Login (interactive once):** `modal token new` → writes `~/.modal.toml`
3. **Unpaid smoke (no local pull):**

```powershell
cd D:\aiand-router
$env:PYTHONPATH='src'; $env:PYTHONUTF8='1'
python scripts/swe_eval_cmd.py --backend modal --instance django__django-11099 --patch data/_gold_django_11099.patch
# Expect real resolved bool after auth; until then: not_available / modal_not_configured
```

---

## How to demo (unpaid, runnable now)

Keep process `TRAINED_PATH=shadow` even if `.env` says `trained`.

```powershell
cd D:\aiand-router
$env:PYTHONPATH='src'; $env:PYTHONUTF8='1'
$env:TRAINED_PATH='shadow'

# 1) Shadow replay vs rules (proxy)
python -m aiand_router.replay_report --gold data/gold-verified.jsonl --artifact data/scorer-hard-logistic.json --models config/models.yaml

# 2) Optional overlay contrast (shadow-only; do not promote)
python -m aiand_router.replay_report --gold data/gold-verified.jsonl --artifact data/scorer-hard-logistic-cost-overlay.json --models config/models.cost-overlay-t015.yaml

# 3) Live tiny-n session gate (no pull)
python -m aiand_router.eval --gate --log data/requests.jsonl --sessions data/verified_session_filectx_all.jsonl

# 4) Promotion readiness + floor path labels
python -m aiand_router.promotion_gate --json

# 5) Modal probe (honest not_available until auth)
python scripts/swe_eval_cmd.py --backend modal --instance django__django-11099 --patch data/_gold_django_11099.patch

# 6) Stickiness unit tests
python -m pytest tests/test_conversation_sticky.py tests/test_promotion_gate.py -q
```

Optional gateway (paid hops only if you send traffic):

```powershell
$env:PYTHONPATH='src'; $env:TRAINED_PATH='shadow'; $env:SCORER_PATH='data/scorer-hard-logistic.json'
uvicorn aiand_router.app:app --app-dir src --host 127.0.0.1 --port 8000
```

---

## What compute unlocks next (paid OK; no mass local pulls)

1. **Modal auth** (above) → gold-patch smoke → wire `SWE_EVAL_CMD` with `SWE_EVAL_BACKEND=modal`.
2. **Paid dual-policy Verified sessions** toward n≥300 **resolved remotely**; edit context from local-12 docker_cp + git `repo_cache`.
3. Re-gate with joined session_id cost; only then discuss serve/overlay promotion or `TRAINED_PATH=trained`.

Do **not** mass-`docker pull` on this host.

---

## Serve freeze (unchanged)

- Artifact: `data/scorer-hard-logistic.json`
- Path: **shadow**
- Overlay t=0.15: experiment only
- Cascade: `enabled: false`
- **Do not flip** `TRAINED_PATH=trained` for this prototype stop

---

## Related

- Completion audit: `completion-audit-2026-08-20.md` (prototype-ready vs production-parity incomplete)
- Disk-light path: `disk-light-parity-path-2026-08-20.md`
- Unpaid next: `unpaid-next-path-2026-08-20.md`
- Operator handoff: `operator-handoff-2026-08-20.md`
