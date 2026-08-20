# 09 — Real fail-to-pass execution as verified y

**What to build:** Score gold cells by applying the model patch/edit inside the SWE-smith Docker env and running named `FAIL_TO_PASS` tests — not soft `expected` match, not invented test bodies, not dump `resolved`.

**Blocked by:** Operator Linux + Docker (this Windows host cannot run it). Soft-y probes (03 H1/H2) already killed; do not start 04 until `geometry_pass`.

**Status:** stopped — infra missing on this machine. Spend this turn: **$0**. No soft-match remint.

- [x] Inventory dump fields for F2P (parquet vs compact checks)
- [x] Check local Docker / WSL / swebench / swesmith
- [x] Map probe pools → unique `image_name`s
- [ ] Wire gold y → execution result (fail-closed when tests can’t run)
- [ ] Unit tests with fake runner (no Docker in CI)
- [ ] Sparse paid probe n≈40 + geometry vs `data/gold-verified.jsonl`
- [ ] geometry_pass → continue 04→05→06

## Feasibility verdict

**Not runnable here.** Real F2P y requires Docker containers from SWE-smith. This host has:

| Prerequisite | This machine |
| --- | --- |
| Docker CLI / Desktop | **Absent** (`docker` not on PATH; no Docker Desktop install) |
| WSL2 Linux distro | **Absent** (`wsl -l` fails) |
| `swebench` / `swesmith` Python pkgs | **Absent** |
| Pre-pulled `jyangballin/swesmith.x86_64.*` images | **None** |
| Inline `verify_pytest` test bodies in dump | **None** (names only) |

SWE-smith owners state explicitly: Docker required; developed on **Ubuntu 22.04**; **no Windows/macOS support** ([README](https://github.com/SWE-bench/SWE-smith)).

Do **not** soft-threshold-game. Do **not** burn another flashlight/issue-fix soft-y matrix. Do **not** start 04.

## What the dump actually provides

### Tasks parquet (`data/_smith_tasks_parquet/`)

Schema (no `test_patch`, no `base_commit`):

- `instance_id`, `patch` (bug diff), `FAIL_TO_PASS`, `PASS_TO_PASS`
- **`image_name`** — e.g. `jyangballin/swesmith.x86_64.oauthlib_1776_oauthlib.1fd52536`
- `repo`, `problem_statement`

~59k rows, **222 unique images**. Probe pools already join: `pool-hard.jsonl` → **30** images; `pool-hard-h2.jsonl` → **31** images (0 miss).

### Compact checks (`data/smith-task-checks*.jsonl`)

Keys today: `instance_id`, `FAIL_TO_PASS`, `expected`, `prompt`, … — **`image_name` stripped**. Soft `expected` from gold-revert is what 03 scored; names-only F2P is already fail-closed in `_gold_label` when `expected` is absent.

### Official eval path (not invented)

```
# predictions JSONL: instance_id + patch (fix diff) + model_name_or_path
python -m swesmith.harness.eval \
  --dataset_path <task_insts.json> \
  --predictions_path <preds.jsonl> \
  --run_id <id>
# sanity: --predictions_path gold
```

Docs: [swesmith.com/guides/harnesses](https://swesmith.com/guides/harnesses/). Alternative API: `registry.get_from_inst(task).get_container(task)` then apply patch + run tests inside the container.

Gold y semantics (CONTEXT **bootstrap resolve**): aiand completion → extract/apply patch → F2P pass in dump env. Dump teacher `resolved` stays unused.

## Operator checklist (unlock F2P y)

Prefer a **Linux x86_64** box (or remote Ubuntu VM / CI runner). Hours of setup, not days of new product code — but **not** hours on this Windows laptop without Docker first.

1. **Host**
   - Ubuntu 22.04+ (preferred), or WSL2 Ubuntu **with** Docker Engine / Desktop Linux backend.
   - Disk: plan **≥100 GB** free for a probe (~30 images). Full 222-image set is much larger.
2. **Docker**
   - Install Docker Engine; `docker run hello-world` succeeds.
   - Confirm `docker pull jyangballin/swesmith.x86_64.oauthlib_1776_oauthlib.1fd52536` (or any pool image) works.
3. **Python harness**
   - Install SWE-smith from source per [installation](https://swesmith.com/getting_started/installation/) (brings eval harness).
   - Smoke: `python -m swesmith.harness.eval --dataset_path … --predictions_path gold --run_id sanity` on a tiny slice.
4. **Data join (repo change, small)**
   - Rebuild task-checks JSONL **keeping** `image_name` (+ optionally `PASS_TO_PASS`, `repo`).
   - Pool/gold meta must carry `image_name` so the runner can pull/start the right container.
5. **Gold wiring (after Docker works)**
   - Extract model **fix patch** from completion (unified diff or reconstruct from edit); fail-closed if unparseable.
   - Run F2P via harness/container; `success=true` only if named F2P tests pass.
   - Prefer F2P execution over soft `expected` when `image_name` present.
   - Unit tests: inject a fake runner; CI never needs Docker.
6. **Probe**
   - `AIAND_TRAIN=1`, `TRAIN_CONCURRENCY=10`, sparse n≈40 on verified-like pool.
   - Unpaid geometry vs `data/gold-verified.jsonl`.
   - Pass → 04→05→06; fail → stop with numbers (no soft remint).

## Lighter alternatives (honest)

| Idea | Verdict |
| --- | --- |
| Soft `expected` / threshold tweaks | **Rejected** — cannot get Flash > Pro; Probe D still best soft snapshot |
| Local pytest without Docker (clone repo + deps) | **Not lighter** — each image encodes a pinned env; SWE-smith exists because bare clone is brittle |
| Inline invent `tests=` bodies from F2P names | **Forbidden** — inventing test bodies |
| Already-downloaded images / in-repo swebench | **None** on this machine / in this repo |
| Modal / remote SWE-bench `--modal` | Possible later; still needs operator account + wiring; not available here today |
| Dump `resolved` as y | **Forbidden** |

## Spend

This turn: **$0** (no gold matrix). Cumulative soft probes remain as in issue 03 (~$4.11 through H2).

## Next agent turn (after operator unlocks Docker)

Implement fake-runner unit seam → real `swesmith.harness.eval` (or thin docker exec) → remint sparse with F2P y → geometry. Until then, stay stopped.
