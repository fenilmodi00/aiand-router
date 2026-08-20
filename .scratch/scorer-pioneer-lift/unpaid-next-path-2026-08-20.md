# Unpaid next-path ranking — after completion audit (2026-08-20)

**Prototype bar (reframed):** `prototype-demo-2026-08-20.md` — **MET** without local farm / TRAINED flip. Production parity still incomplete.

**Disk-light parity path (2026-08-20):** see `disk-light-parity-path-2026-08-20.md` — reach §(a) spirit via Modal/sb-cli or ephemeral `cache_level=env`+`clean` **without** a local ~300×4GB image farm. **Remote adapter wired:** `SWE_EVAL_BACKEND=modal|sb-cli|local` in `scripts/swe_eval_cmd.py`. **Auth probe:** Modal → `modal_not_configured` (no `~/.modal.toml`); sb-cli → `sb_cli_missing`. Human: install → `modal token new` → gold-patch smoke.

**Serve candidate unchanged:** `data/scorer-hard-logistic.json` + ship `config/models.yaml` (shadow; `local_replay_gate_pass=true`; `production_parity=false`; ship `rules_cost_delta=+0.000687`).

**Cost overlay (shadow experiment only):** `data/scorer-hard-logistic-cost-overlay.json` + `config/models.cost-overlay-t015.yaml` → `rules_cost_delta=-0.000688`, gate still pass. Does **not** replace serve.

**Session-gold (local-12):** **10/12** in `data/verified_session_filectx_all.jsonl`. Gate `bounded_check_only`. Floor n≥300 **disk-blocked** (no unused local images; **NO docker pull**). Remaining misses 12754/13512 — skip paid retries unless unpaid fix is ready.

**Edit file context without pulls:** git shallow fallback (`git_file_context.py` → `data/repo_cache/`) supplies `likely_target_files` when eval image missing. Prefer local docker_cp for the 12. **Resolve:** local still image-bound; remote via `SWE_EVAL_BACKEND=modal|sb-cli` (auth pending on this host).

**Cascade fixture (unpaid):** at ship knobs **0 redirects** (Flash P≈0.03 ≪ t=0.10). Soft in-memory `t=0.035` → **2/70**. Default-off stays — soft-t ≠ FireRouter. Report: `cascade-knob-sweep-2026-08-20.md`.

**Disk reclaim (safe):** removed `hello-world` only (~26 kB). All 12 `sweb.eval` preserved. Negligible GB freed; do not prune sweb layers.

**No commits. No `TRAINED_PATH` flip.**

---

## Falsified paths (must not re-run)

| Path | Why dead |
| --- | --- |
| Fine cost frontier “middle” overlay | No gate∧rcd≤0 with succ closer to 0.112 than 0.090; BSS kills t≈0.141–0.145 (`fine-cost-frontier-2026-08-20.md`) |
| Cascade soft-t promote | Redirects appear only with artifact-quirk thresholds; not FireRouter (`cascade-knob-sweep-2026-08-20.md`) |
| gym_alt order-mix / winner-mix paid probes | seed2: 32/32 all-fail vs offline projection; geometry fail |
| smith seeds 11–16 / order-conservative / kimi-targeted | Standalone geometry fail |
| Hash-teacher distill XOR | Cost-win fails gate; gate-pass (ld18) keeps ship rcd — no joint serve beat (`distill-gate-recovery-2026-08-20.md`) |
| gym-alt-seed1 merge logistic refit | Replay P-spread fail |
| Easy gold / GBDT / silver+Mix1 / live-hash bilinear serve | Documented regressions |
| Docker pull on this host | Disk full; inventory = 12 eval images only |

---

## Ranked honest unpaid-next options

### 1. Session-joined rcd after gateway restart — **done (sample)**

Gateway restarted on current src (`TRAINED_PATH=shadow` process override). Live join: `session_joined=true`, `n_joinable_hops=10`, joined `rules_cost_delta≈-0.00162`. Sample: `.scratch/scorer-pioneer-lift/session-joined-cost-sample-2026-08-20.md`. Stickiness: `.scratch/scorer-pioneer-lift/firerouter-stickiness-2026-08-20.md`. Still `bounded_check_only` (n≪300).

### 2. Session-gold scale — **local resolve disk-blocked; remote backend wired (auth pending)**

Local inventory exhausted for **resolve**. Further `docker pull` forbidden on this host. Git fallback unblocks **edit** file bytes. Prefer **Modal / sb-cli** via:

```powershell
$env:SWE_EVAL_BACKEND='modal'   # or 'sb-cli' + $env:SWEBENCH_API_KEY
$env:SWE_EVAL_CMD='python scripts/swe_eval_cmd.py --instance {instance_id} --patch {patch_file}'
```

Without `~/.modal.toml` / `SWEBENCH_API_KEY` → honest `not_available` (no fake gold). Full recipes: `disk-light-parity-path-2026-08-20.md` §4. Never delete the 12 `sweb.eval` images.

### 3. Cost vs rules — overlay stays shadow-only (**fine frontier falsified**)

| | ship | overlay t=0.15 |
| --- | ---: | ---: |
| `rules_cost_delta` | +0.000687 | −0.000688 |
| trained success | 0.112 | 0.090 |
| gate | pass | pass |

Do **not** promote overlay. Do **not** add t=0.148 overlay (no succ gain vs 0.15).

### 4. Cascade seam — knobs swept; still not parity (**done unpaid**)

Keep `cascade_lane.enabled: false`. No more soft-t churn as a parity path.

### 5. Hard-gold (paid later, not now)

Need a **new** unpaid recipe before any paid gold — not blind smith/gym_alt order-mix. Optional later unpaid: true offline **neural** embed teacher (hash path XOR-exhausted).

### Explicitly not next

- Docker pull / new SWE eval images on this host.
- Paid retries on 12754/13512 without unpaid fix.
- smith / gym_alt blind paid train gold.
- `TRAINED_PATH=trained`.
- Replacing serve with overlay, bilinear distill, or cascade-on.

---

## Remaining blockers to parity

1. **Disk-blocked session-gold floor** — 10/12 local vs n≥300.
2. **Ship `rules_cost_delta>0`** — fine frontier falsified; overlay clears only as shadow (−2.2pp proxy success).
3. **Calibration at scale** — ECE_m waived; live-log BSS/ECE_w fail on small cal n.
4. **No merge-safe second hard-gold batch.**
5. **Cascade not a measured FireRouter product.**
6. **`TRAINED_PATH=trained` correctly blocked.**
7. **Live joined rcd** — sample landed (`n_joinable=10`); still tiny vs promotion; cal bars fail.

## Exact suggested next step

**Prototype demo (unpaid):** see `prototype-demo-2026-08-20.md`.

**Scale unlock (human auth, then paid OK; zero new local images):**

```powershell
pip install modal 'swebench[modal]'
modal token new
cd D:\aiand-router
$env:PYTHONPATH='src'; $env:PYTHONUTF8='1'
python scripts/swe_eval_cmd.py --backend modal --instance django__django-11099 --patch data/_gold_django_11099.patch
```

**Paid after auth:** dual-policy Verified + `SWE_EVAL_BACKEND=modal` toward n≥300. Prefer local-12 docker_cp + git filectx for edit. No mass pulls; no gym_alt/smith blind gold; no TRAINED flip until promotion evidence.
