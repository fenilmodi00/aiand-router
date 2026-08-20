# Disk-light path to Pioneer/Fireworks parity (2026-08-20)

**Constraint:** no ~300×4GB local SWE-bench image farm on this host (~1TB). No `TRAINED_PATH=trained` flip. No mass `docker pull`.

**Local authority:** `prototype-demo-2026-08-20.md` (reframed prototype bar), `completion-audit-2026-08-20.md`, `operator-handoff-2026-08-20.md`, `unpaid-next-path-2026-08-20.md`, research debate `../trained-router/research/scorer-router-fireworks-pioneer-debate.md`.

**Auth probe (2026-08-20):** Modal client present, **`~/.modal.toml` missing** → unpaid smoke returns `modal_not_configured`. sb-cli missing / no `SWEBENCH_API_KEY`.

**External method:** Tavily dynamic-search (raw → `.scratch/scorer-pioneer-lift/tavily-disk-light-parity-raw-2026-08-20.json`; extracts → `tavily-disk-light-extract-2026-08-20.json`).

---

## 1. Current position (research vs capability)

| Layer | Closeness | Evidence |
| --- | --- | --- |
| Research / strategy | **Done** | FireRouter + Pioneer primary docs; debate phases 0–6; falsified-path catalog live |
| Local shadow serve | **Strong proxy** | `data/scorer-hard-logistic.json`; replay gate pass; succ 0.112 vs rules 0.022 on n=89; ship `rcd=+0.000687`; overlay t=0.15 shadow-only |
| Session-gold harness | **Proven path, tiny n** | filectx + `SWE_EVAL_CMD` → **10/12** local `session_gold`; git file-context unblocks edit bytes without images; **resolve still image- or remote-bound** |
| Product parity | **Far** | No promotion pass; cascade 0 redirects at ship knobs; hash distill XOR; gym_alt/smith falsified; floor n≥300 **disk-blocked** |

**Verdict:** research/diagnosis ≈ complete; capability parity **must not be claimed**. The binding gap is **session-gold at promotion floor**, not “missing FireRouter docs.”

---

## 2. Why a full local image farm is unnecessary (and §(a) spirit)

### Runbook §(a) spirit (not the literal farm)

From `docs/runbook-production.md` §(a):

1. Quality on **session gold** (SWE resolve / tests_passed) vs rules (≥ −1 pp)
2. Cost: `rules_cost_delta < 0`
3. Calibration: BSS > 0; dual ECE ≤ 0.03 (at adequate n)
4. Floor: **n ≥ 300 session-gold tasks** (primary dataset Verified 500)

Spirit = **honest harness-resolved outcomes at scale**, not “retain every `sweb.eval` layer on the laptop.” Flashlight / harness-proxy / Lite fixtures remain `bounded_check_only` and are explicitly **not** substitutes after Verified is in scope.

### Official SWE-bench: keep ≠ evaluate

- **Docker is required for local harness consistency**, but you need not keep instance images: FAQ recommends `--cache_level=env` and `--clean=True` so instance images are **removed after use** (slower runs, less disk). ([SWE-bench FAQ — disk space](https://www.swebench.com/SWE-bench/faq))
- Cache levels documented: `none | base | env | instance`. Default `env` balances speed vs disk; use lower cache + `--clean` when space-bound. ([Evaluation guide — controlling cache](https://www.swebench.com/SWE-bench/guides/evaluation), [Docker setup](https://www.swebench.com/SWE-bench/guides/docker_setup))
- Authors still warn resource intensity (order of **≥120GB free** if you cache aggressively). ([Docker setup](https://www.swebench.com/SWE-bench/guides/docker_setup), [SWE-bench GitHub](https://github.com/swe-bench/SWE-bench))
- **Myth check:** “300×4GB ≈ 1TB resident” overstates shared layers. Epoch measures original Verified unique layers ≈ **189 GiB**, optimized public registry ≈ **30 GiB** for all 500 Verified images — still large for *this* host, but **not** a 1TB permanent farm requirement if you use ephemeral/cache_env/clean or cloud. ([Epoch — SWE-bench Docker](https://epoch.ai/latest/swebench-docker))

### Cloud / remote resolve (no local farm)

- Official FAQ: cloud via **Modal** (`swebench.harness.modal_eval.run_modal.run_modal_evaluation`). ([FAQ — cloud](https://www.swebench.com/SWE-bench/faq), [Evaluation guide — Modal](https://www.swebench.com/SWE-bench/guides/evaluation))
- **sb-cli** submits predictions to the SWE-bench API (“All on the cloud”). ([sb-cli overview](https://www.swebench.com/sb-cli), [user guide](https://www.swebench.com/sb-cli/user-guide), [swe-bench/sb-cli](https://github.com/swe-bench/sb-cli))
- Third-party remote upload evals (e.g. moatless / SWE-bench-docker upload path) exist as alternate remote runners. ([aorwall/SWE-bench-docker](https://github.com/aorwall/SWE-bench-docker))

### How FireRouter / Pioneer-class routers evaluate (no docker farm in docs)

- **FireRouter:** binary redirect vs pass-through + 1–5 preference; **no** published SWE-bench image farm, session-gold recipe, or ECE. ([overview](https://docs.fireworks.ai/ecosystem/firerouter/overview), [routing preferences](https://docs.fireworks.ai/ecosystem/firerouter/routing-preferences))
- **Pioneer:** documented policy = complexity → calibrated P(success) → cheapest above threshold/max_regret; **no** published calibration method or Verified docker gate. ([Pioneer router concepts](https://docs.pioneer.ai/concepts/router))
- Open router eval culture uses **preference / multi-model outcome benches** (RouteLLM, RouterBench) — useful for **intermediate** quality/cost claims, **not** a drop-in for runbook session gold. ([RouteLLM](https://github.com/lm-sys/routellm), [RouterBench intro](https://withmartian.com/post/introducing-routerbench), [arxiv RouteLLM](https://arxiv.org/html/2406.18665v4))

### Minimum substitute evidence that still honors §(a) spirit

Acceptable **without** retaining ~300 local images:

| Must have | Acceptable substitute |
| --- | --- |
| Session resolve y | Real harness resolve via **Modal / sb-cli / ephemeral local** (`cache_level=env`+`clean`), joined to dual-policy sessions |
| n ≥ 300 | Same floor; source of resolve may be remote; do not lower floor to “fit disk” |
| Quality / cost / cal bars | Same bars on `session_gold` rows; proxy replay stays labeled shadow / `not_spec_floors` |
| Edit context | Already: git shallow `repo_cache` when image missing (resolve still needs harness) |

**Not** acceptable as promotion: Lite fixture, gateway-gold-only proxy, `--mock-resolved`, n=12 local, overlay-only rcd clear.

---

## 3. Ranked options from *this* position → goal (no 1TB disk)

### Rank 1 — Remote session resolve (sb-cli or Modal) wired into `SWE_EVAL_CMD`

**What:** Keep local flashlight + git/docker_cp file context; replace local `run_evaluation` with cloud submit/poll that returns `resolved` for the patch.

**Why ranked #1:** Matches official SWE-bench cloud paths; leaves the 12 local images untouched; scales toward n≥300 without host disk growth.

**Cost:** Modal/API compute + existing LLM gold spend; no local GiB.

**Risks:** Auth/API quotas; latency; need honest join into `verified_session_*.jsonl` / `eval --gate`.

**Sources:** [FAQ Modal](https://www.swebench.com/SWE-bench/faq), [Evaluation guide cloud](https://www.swebench.com/SWE-bench/guides/evaluation), [sb-cli](https://www.swebench.com/sb-cli).

### Rank 2 — Ephemeral local harness on a throwaway VM (not this Windows host)

**What:** Cloud VM (≥120GB Docker disk or Epoch ~30GiB Verified registry), run with `--cache_level=env --clean=True` (or pull Epoch optimized registry then prune), stream reports back; delete VM/images after.

**Why:** Closest mechanical match to today’s `scripts/swe_eval_cmd.py`; still zero permanent farm on the laptop.

**Sources:** [FAQ disk / clean](https://www.swebench.com/SWE-bench/faq), [Epoch optimized images](https://epoch.ai/latest/swebench-docker), [Docker setup 120GB](https://www.swebench.com/SWE-bench/guides/docker_setup).

### Rank 3 — Streaming local eval on this host (env+clean only, tiny concurrency)

**What:** Reuse existing hook with harness flags that drop instance images after each id; **no** inventory growth beyond transient layers.

**Why lower:** This host is already disk-blocked; even env+clean may OOM disk mid-pull; only viable after reclaim or smaller batches with proven free space.

**Sources:** same FAQ/cache docs.

### Rank 4 — Stratified Verified sample + remote fill (staffed floor waiver ≠ code waiver)

**What:** Operator-staffed path: random/pathready stratified ids to n=300 **resolved remotely**, keep local 10/12 as canary continuity.

**Why:** Meets floor without “all 500 images local”; still needs remote resolve for most ids.

### Rank 5 — Intermediate proxy ladder (RouterBench / RouteLLM-style / frozen verified replay)

**What:** Continue unpaid replay + optional preference/router benches for research claims.

**Why last for *parity*:** Already strong locally; **cannot** satisfy §(a) session floor. Use only to avoid paid thrash while remote resolve is wired.

**Sources:** [RouteLLM](https://github.com/lm-sys/routellm), [RouterBench](https://withmartian.com/post/introducing-routerbench).

### Explicitly out of rank (falsified / blocked here)

- Mass `docker pull` on this host
- smith / gym_alt blind gold, hash distill XOR, cascade soft-t as FireRouter, fine cost “middle” overlay
- Promoting overlay / bilinear / `TRAINED_PATH=trained` from n=12

---

## 4. Recommended next 1–2 steps (no new mass pulls)

### Unpaid (do first)

1. Restart gateway so new hops log `session_id`.
2. Re-gate existing local sessions; optional ≤3 already-gold dual-policy smokes (**no pull**) for `session_joined` rcd.

```powershell
$env:PYTHONPATH='src'; $env:PYTHONUTF8='1'
python -m aiand_router.eval --gate --log data/requests.jsonl --sessions data/verified_session_filectx_all.jsonl
```

### Remote resolve adapter (unpaid, wired 2026-08-20)

`scripts/swe_eval_cmd.py` now selects backend via `SWE_EVAL_BACKEND` / `--backend`:

| Value | Behavior | Auth |
| --- | --- | --- |
| `local` (default) | Docker + `swebench.harness.run_evaluation` | `docker info` + `pip install swebench` |
| `modal` | Same harness with `--modal true` (no local image farm) | `pip install modal 'swebench[modal]'` + `modal token new` → `~/.modal.toml` |
| `sb-cli` | `sb-cli submit swe-bench_verified test` | `pip install sb-cli` + `SWEBENCH_API_KEY` |

Missing auth → honest `{"resolved": null, "status": "not_available", "reason": "modal_not_configured"|"sb_cli_not_configured"|...}`. No fake resolves. Serve stays `data/scorer-hard-logistic.json`.

#### Human Modal auth checklist (3 steps)

1. `pip install modal 'swebench[modal]'`
2. `modal token new` → writes `~/.modal.toml` (browser once)
3. Unpaid gold-patch smoke (below). Success = JSON with real `resolved` bool. Failure until auth = `not_available` / `modal_not_configured`.

#### Exact PowerShell — Modal (preferred disk-light)

```powershell
cd D:\aiand-router
pip install modal 'swebench[modal]'
modal token new   # writes ~/.modal.toml; one-time browser auth
$env:PYTHONPATH='src'; $env:PYTHONUTF8='1'
$env:SWE_EVAL_BACKEND='modal'
$env:SWE_EVAL_CMD='python scripts/swe_eval_cmd.py --instance {instance_id} --patch {patch_file}'
# Unpaid probe (no local pull):
python scripts/swe_eval_cmd.py --backend modal --instance django__django-11099 --patch data/_gold_django_11099.patch
# Without token: expect not_available / modal_not_configured
```

#### Exact PowerShell — sb-cli

```powershell
cd D:\aiand-router
pip install sb-cli
sb-cli gen-api-key you@example.com
# verify via email code, then:
$env:SWEBENCH_API_KEY='...'
$env:PYTHONPATH='src'; $env:PYTHONUTF8='1'
$env:SWE_EVAL_BACKEND='sb-cli'
$env:SWE_EVAL_CMD='python scripts/swe_eval_cmd.py --instance {instance_id} --patch {patch_file}'
python scripts/swe_eval_cmd.py --backend sb-cli --instance django__django-11099 --patch data/_gold_django_11099.patch
# Without key: expect not_available / sb_cli_not_configured
```

Edit context stays git/docker_cp on what we have; resolve goes remote. **Do not** mass-pull `sweb.eval` on this host.

### Paid (only after remote auth smoke)

Budget for Modal/sb-cli compute + dual-policy Verified sessions toward **n≥300 session_gold**, still zero permanent local images. Do **not** spend on gym_alt/smith gold or 12754/13512 retries without unpaid patch fix.

---

## 5. What still cannot be claimed

- Pioneer or Fireworks **capability parity**
- Promotion readiness / `TRAINED_PATH=trained`
- Ship serve `rules_cost_delta < 0` (overlay clears only as shadow, −2.2 pp succ)
- FireRouter-equivalent cascade (0 redirects at ship knobs; soft-t ≠ product)
- That git file-context alone produces session gold (resolve remains harness-bound)
- That n=10/12 or Lite/`bounded_check_only` meets §(a)
- That competitors secretly require a local 1TB image farm (docs do not support that)

---

## Serve freeze (unchanged)

- Artifact: `data/scorer-hard-logistic.json`
- Path: shadow
- Overlay t=0.15: experiment only
- Cascade: `enabled: false`

## Related local docs

- Completion audit: `completion-audit-2026-08-20.md`
- Operator handoff: `operator-handoff-2026-08-20.md`
- Unpaid next: `unpaid-next-path-2026-08-20.md`
- Promotion readiness: `promotion-readiness-2026-08-20.md`
- Research debate: `../trained-router/research/scorer-router-fireworks-pioneer-debate.md`
