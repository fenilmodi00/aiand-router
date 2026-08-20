# Docker + SWE_EVAL_CMD status (2026-08-20)

**Path chosen:** unlock Docker, install `swebench`, probe unpaid harness, then live Verified smoke with true `SWE_EVAL_CMD`.

**Serve candidate unchanged:** `data/scorer-hard-logistic.json` + `config/models.yaml`. No production flip of `TRAINED_PATH=trained` (gateway for smoke used `TRAINED_PATH=shadow`).

**Spend after filectx session_gold smoke:** `~$15.653121` (enrichment was `~$15.652567`; delta `~$0.000554`).

---

## What happened (earlier unpaid)

| Check | Result |
| --- | --- |
| `pip install swebench` | **ok** → `swebench==5.0.2` (Windows / Python 3.14) |
| `import swebench` | **pass** |
| `docker info` / `hello-world` | **pass** |
| Dataset fix | `scripts/swe_eval_cmd.py` → default `SWE-bench/SWE-bench_Verified` (+ `--dataset-name`) |
| Report parsing | Summary `{model}.{run_id}.json` **and** per-instance `report.json`; `error_ids` stay `not_available` (no fake fail) |
| Windows UTF-8 / CRLF | Without fix: `Path.write_text` → cp1252 crash **or** CRLF `eval.sh` (`pipefail\r`) → fake unresolved. Wrapper bootstrap forces UTF-8 + LF. |
| Image pull | `swebench/sweb.eval.x86_64.django_1776_django-11099:latest` **pulled** (~1.15 GB compressed → ~4.19 GB local) |
| Gold patch (unpaid probe only) | `data/_gold_django_11099.patch` from HF Verified (`django__django-11099`); **never** inject into live router turns |
| Unpaid gold-patch probe | **`resolved: true`**, `status: ok`, exit **0** |

### Probe JSON (canonical unpaid gold patch - success)

```json
{
  "resolved": true,
  "status": "ok",
  "source": "swebench.harness.run_evaluation",
  "instance_id": "django__django-11099",
  "dataset_name": "SWE-bench/SWE-bench_Verified",
  "report": ".../logs/run_evaluation/aiand_swe_eval/aiand-router/django__django-11099/report.json"
}
```

---

## Patch-format fix (code)

**Bug:** Verified flashlight edit/debug reused Lite `_TURNS` asking for ````python` module text; `SWE_EVAL_CMD` wrote that raw text as `model_patch` → apply fail → honest `needs_swe_eval`.

**Fix (minimal, in `src/aiand_router/verified_runner.py`):**

1. Verified-local `_VERIFIED_TURNS` ask for a **unified-diff git patch** inside a ````diff` fence (Lite unchanged).
2. `extract_unified_diff()` pulls ````diff` / ````patch` / raw `diff --git` bodies.
3. Pure ````python` → `patch_status=patch_not_unified_diff`, skip docker (no invalid patch to harness).
4. Unpaid unit tests in `tests/test_verified_runner.py` (extraction + prompt + skip-docker).

---

## Prompt enrichment (code, 2026-08-20)

**Goal:** give flashlight turns a fair chance at an **applyable** unified diff without injecting gold `patch` / `test_patch`.

**Changes:**

1. `guess_target_paths()` in `lite_runner.py` — from problem_statement/hints only: explicit `*.py` paths + phrases like `in contrib.auth.validators` mapped with `repo` → `django/contrib/auth/validators.py`.
2. `instance_turn_context()` adds `likely_target_files` when guessed; still includes repo/version/base_commit/problem/hints/FAIL_TO_PASS. **Never** gold.
3. Verified edit/debug instructions demand **exact hunk context** (no invent/duplicate lines) and name target paths when known (`verified_turn_instruction`).
4. Debug turn also runs when docker was attempted but unlabeled (`swe_eval_attempted`) — previously only `resolved is False` retried.
5. Unpaid tests: path guess, django-11099 dump context, debug-on-apply-fail.

**django-11099 evidence (analysis only):**

| Artifact | Apply? | Note |
| --- | --- | --- |
| Gold `data/_gold_django_11099.patch` | yes → `resolved: true` | `$` → `\Z` only; exact file context |
| Pre-enrich smoke model patch | **no** | invented duplicate `regex` lines |
| Enriched edit model patch (`data/_smoke_model_django_11099_enriched_edit.patch`) | **no** | correct path; wrong surrounding context |
| Summarize-turn extract (not used as edit) | applied → `resolved: false` | wrong semantics (`\A...\Z`); proves apply≠resolve |

**Verdict:** enrichment improves path targeting; **flashlight-without-file-bytes still cannot reliably invent applyable hunk context**.

---

## Docker-cp file context (code, 2026-08-20)

**Goal:** append real `likely_target_files` bytes from the local SWE eval image into Verified edit context (capped), without a full agent / checkout stack. **Never** gold.

**Module:** `src/aiand_router/docker_file_context.py`

1. Image name: `swebench/sweb.eval.x86_64.{instance_id with __ → _1776_}:latest`
2. `docker create` + `docker cp` from `/testbed/<path>` + `docker rm -f` (no container start)
3. Caps: ≤8 files, ≤400 lines each in prompt, ≤120KB raw; LF-normalized
4. `ensure_target_file_contents` caches on the instance; prefers local docker_cp; missing image → **git shallow fetch** of `repo`@`base_commit` into `data/repo_cache/` (`file_context_source=git`); both fail → `unavailable` + optional `file_context_error`
5. `instance_turn_context` renders `target_file_contents` as `file_contents:` blocks when present
6. `verified_runner._run_live_instance` attaches file context once per session; session row records `has_file_contents` + `file_context_source`
7. Disable all with `VERIFIED_FILE_CONTEXT=0`; disable git only with `VERIFIED_FILE_CONTEXT_GIT=0`

**Unpaid results:**

| Check | Result |
| --- | --- |
| Mocked docker create/cp/rm unit tests | **pass** |
| Real docker-cp smoke `validators.py` on django-11099 image | **pass** (685 bytes; `ASCIIUsernameValidator` + base `$` anchors) |
| CLI | `python -m aiand_router.docker_file_context --instance django__django-11099 --path django/contrib/auth/validators.py` |
| Artifact | `data/_docker_cp_django_11099_validators.json` |
| Combined unpaid | **42 passed** (`test_docker_file_context.py` + `test_verified_runner.py`) |

---

## Git file-context fallback (code, 2026-08-20 night)

**Goal:** supply Verified **edit** file bytes without downloading new 4GB `sweb.eval` images. **Resolve** via `SWE_EVAL_CMD` still needs a local image when present; without image, stay honest `needs_swe_eval`.

**Module:** `src/aiand_router/git_file_context.py` (wired from `docker_file_context.resolve_target_file_contents`)

1. Prefer `docker_cp` when the local eval image exists (preserve the 12 local images; **no pull**)
2. Else: `git init` + `git fetch --depth 1 origin <base_commit>` into `data/repo_cache/{owner}__{name}/`, then `git show <commit>:<path>`
3. Blob cache under `.../blobs/<commit>/<path>` so re-runs do not re-show/re-fetch
4. Caps unchanged (≤2 files, ≤120KB, prompt line cap); never gold `patch` / `test_patch`
5. Failures set `file_context_source=unavailable` + `file_context_error` (e.g. `git_fetch_failed:...`)

**Unpaid results:**

| Check | Result |
| --- | --- |
| Mocked git init/fetch/show + blob cache | **pass** |
| Prefer docker when image present (git not called) | **pass** |
| Git fallback when image missing | **pass** |
| Live git fetch `django@d26b242…` validators.py | **pass** (no docker pull; no LLM) |
| CLI | `python -m aiand_router.docker_file_context --instance django__django-11099 --repo django/django --base-commit d26b2424437dabeeca94d7900b37d2df4410da0c --path django/contrib/auth/validators.py --prefer-git --cache-dir data/repo_cache` |

**Does not unblock:** session-gold **resolve** floor (still image-bound), `TRAINED_PATH=trained`, serve-candidate replacement.

## Live Verified smoke #1 (pre-format-fix, limit 1)

| Item | Result |
| --- | --- |
| Instance | `django__django-11099` |
| `label_type` | **`needs_swe_eval`** (`session_gold: false`) |
| Cause | Format mismatch (python fence → invalid `model_patch`) |

Spend delta then: `+$0.001135` (`15.650197` → `15.651332`).

---

## Live Verified smoke #2 (post-format-fix, limit 1)

| Item | Result |
| --- | --- |
| Instance | `django__django-11099` (local image present) |
| `label_type` | **`needs_swe_eval`** (`session_gold: false`) |
| Format bug? | **No** — real ````diff`; docker ran |
| Why unlabeled | Harness **Patch Apply Failed** (bad hunk context) |

Spend: `15.651332` → `15.651502` (`+$0.00017`).

---

## Live Verified smoke #3 (post-prompt-enrichment, limit 1)

| Item | Result |
| --- | --- |
| Instance | `django__django-11099` |
| Gateway | shadow + `SCORER_PATH=data/scorer-hard-logistic.json` on `:8000` |
| Out | `data/verified_session_swe_smoke_enriched.jsonl` |
| Spend delta | **`+$0.001065`** (`15.651502` → `15.652567`) |
| `instance_fields.has_target_paths` | **true** |
| `label_type` | **`needs_swe_eval`** (`session_gold: false`) |
| Gold injection | **none** |
| Unpaid replay of edit patch | **Patch Apply Failed** (Hunk #1 FAILED at 1) → `not_available` |
| `eval --gate` | **`bounded_check_only`**, `do_not_flip_trained_path: true` |

---

## Live Verified smoke #4 (post docker-cp file context, limit 1)

| Item | Result |
| --- | --- |
| Instance | `django__django-11099` |
| Gateway | shadow + `SCORER_PATH=data/scorer-hard-logistic.json` on `:8000` |
| Out | `data/verified_session_swe_smoke_filectx.jsonl` |
| Spend delta | **`+$0.000554`** (`15.652567` → `15.653121`) |
| `instance_fields.has_target_paths` | **true** |
| `instance_fields.has_file_contents` | **true** |
| `file_context_source` | **`docker_cp`** |
| `label_type` | **`session_gold`** (`session_gold: true`) |
| Policies | rules **resolved=true**, trained **resolved=true** |
| Gold injection | **none** |
| `eval --gate` | **`bounded_check_only`** (session_gold bar pass at n=1; floor n≥300 fail; `do_not_flip_trained_path: true`) |

**First true live Verified session_gold** on flashlight turns: real file bytes from eval image → applyable model patch → SWE_EVAL_CMD resolve. Still not promotion-scale.

---

## Remaining blockers

1. **Scale:** n=1 / n=10 session_gold ≠ n≥300 promotion evidence (`floor_session_gold_n` fail). Cost/calibration bars also fail at this log size.
2. **Resolve coverage without local farm:** local `SWE_EVAL_CMD` still needs a `sweb.eval` image. **Disk-light path (2026-08-20):** `SWE_EVAL_BACKEND=modal|sb-cli` in `scripts/swe_eval_cmd.py` — no mass pull; auth required (`~/.modal.toml` or `SWEBENCH_API_KEY`). **Edit file context** already works via git shallow (`file_context_source=git`).
3. **Platform:** Windows needs `PYTHONUTF8=1` + LF bootstrap in `swe_eval_cmd.py` (local backend).
4. **Do not** flip production `TRAINED_PATH=trained` or inject gold patches into live turns. (Note: `.env` currently has `TRAINED_PATH=trained` — override to `shadow` when starting gateway.)

**True session_gold reachable unpaid?** Yes for docker harness (gold patch) **and** unpaid docker-cp of target files; remote Modal/sb-cli once auth is set.
**Edit context without pulls?** Yes via git `@base_commit` (unpaid).
**True session_gold on live flashlight turn?** **Yes on django-11099 n=1** with docker-cp file context + SWE_EVAL_CMD. Scale / remote-auth remain the blockers for floor n≥300.

---

## Exact PowerShell (repo root)

### 0a) Disk-light remote backends (no new local images)

```powershell
# Modal (preferred — images stay on Modal, not this host)
pip install modal 'swebench[modal]'
modal token new   # writes ~/.modal.toml
$env:PYTHONPATH='src'; $env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'
$env:SWE_EVAL_BACKEND='modal'
$env:SWE_EVAL_CMD='python scripts/swe_eval_cmd.py --instance {instance_id} --patch {patch_file}'
python scripts/swe_eval_cmd.py --backend modal --instance django__django-11099 --patch data/_gold_django_11099.patch
# Without token: {"resolved": null, "status": "not_available", "reason": "modal_not_configured"}

# sb-cli alternative
pip install sb-cli
sb-cli gen-api-key you@example.com   # then verify-api-key from email
$env:SWEBENCH_API_KEY='...'
$env:SWE_EVAL_BACKEND='sb-cli'
python scripts/swe_eval_cmd.py --backend sb-cli --instance django__django-11099 --patch data/_gold_django_11099.patch
# Without key: reason=sb_cli_not_configured
```

Unit tests (no network): `python -m pytest tests/test_swe_eval_cmd.py -q`

### 0) Confirm install + Docker + image (local backend only)

```powershell
python -c "import swebench; print('swebench ok')"
docker info
docker images swebench/sweb.eval.x86_64.django_1776_django-11099
```

### 1) Unpaid gold-patch probe (proven local)

```powershell
cd D:\aiand-router
$env:PYTHONPATH = 'src'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
# default backend=local
python scripts/swe_eval_cmd.py --instance django__django-11099 --patch data/_gold_django_11099.patch
# Expect: {"resolved": true, "status": "ok", ...}
```

### 2) Unpaid unit tests (patch extract / prompts / enrichment / docker-cp)

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/test_verified_runner.py tests/test_docker_file_context.py -q --tb=short
```

### 2b) Unpaid docker-cp CLI smoke (no LLM)

```powershell
$env:PYTHONPATH='src'
python -m aiand_router.docker_file_context --instance django__django-11099 --path django/contrib/auth/validators.py --out data/_docker_cp_django_11099_validators.json
# Expect: paths_copied includes validators.py; file_context_source=docker_cp
```

### 2c) Unpaid git file-context CLI smoke (no LLM, no docker pull)

```powershell
$env:PYTHONPATH='src'
python -m aiand_router.docker_file_context --instance django__django-11099 --repo django/django --base-commit d26b2424437dabeeca94d7900b37d2df4410da0c --path django/contrib/auth/validators.py --prefer-git --cache-dir data/repo_cache --out data/_git_fc_django_11099_validators.json
# Expect: file_context_source=git; ASCIIUsernameValidator + base $ anchors
```

### 3) Live Verified smoke (limit 1) — with file context + SWE_EVAL_CMD

```powershell
# Terminal 1 — shadow gateway (do NOT use .env TRAINED_PATH=trained)
$env:PYTHONPATH='src'
$env:TRAINED_PATH='shadow'
$env:SCORER_PATH='data/scorer-hard-logistic.json'
$env:UPSTREAM_TIMEOUT_S='300'
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
uvicorn aiand_router.app:app --app-dir src --host 127.0.0.1 --port 8000

# Terminal 2
$env:PYTHONPATH='src'
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$spend = [double](Get-Content data/spend.txt -Raw).Trim()
$env:BUDGET_LIMIT_USD = [string]($spend + 15)
$env:SWE_EVAL_CMD='python scripts/swe_eval_cmd.py --instance {instance_id} --patch {patch_file}'
Set-Content data/verified_swe_smoke_ids.json '["django__django-11099"]'
python scripts/run_verified_session.py --ids data/verified_swe_smoke_ids.json --limit 1 --out data/verified_session_swe_smoke_filectx.jsonl
python -m aiand_router.eval --gate --log data/requests.jsonl --sessions data/verified_session_swe_smoke_filectx.jsonl
```

### 4) Empty-patch availability (still not_available)

```powershell
$tmp = New-TemporaryFile; Set-Content -Path $tmp -Value ""
python scripts/swe_eval_cmd.py --instance django__django-11099 --patch $tmp
Remove-Item $tmp -Force
# Expect: not_available / empty_patch
```

### 5) Unpaid replay of enriched edit patch (apply fail)

```powershell
python scripts/swe_eval_cmd.py --instance django__django-11099 --patch data/_smoke_model_django_11099_enriched_edit.patch
# Expect: not_available / Patch Apply Failed
```

---

## Cascade

Not advanced. Seam remains default-off in `config/models.yaml`.

---

## Live Verified filectx batch n=4 (local images, 2026-08-20)

**Out:** `data/verified_session_filectx_batch.jsonl`
**Spend:** `15.653121 → 15.662449` (`+0.009328`). No new image pulls this run (10880/10914/11066 already local from prior agent).

| instance | session_gold | file_context | rules | trained |
| --- | --- | --- | --- | --- |
| django-11099 | true | docker_cp | true | true |
| django-10880 | true | unavailable | true | true |
| django-10914 | false | unavailable | null | null |
| django-11066 | false | unavailable | null | null |

**Rates:** session_gold 2/4; resolve 2/4 each policy; docker_cp 1/4 (path-guess miss on 3/4).
**`eval --gate`:** `bounded_check_only`; quality_session_gold pass on labeled (1.0/1.0); floor n≥300 fail; `do_not_flip_trained_path: true`.
**Serve candidate:** unchanged `data/scorer-hard-logistic.json`.
**Detail:** `.scratch/scorer-pioneer-lift/verified-filectx-batch-2026-08-20.md`.
---

## Scaled filectx dual-policy (n=4 of target 5) — 2026-08-20

**Serve candidate unchanged:** `data/scorer-hard-logistic.json` + `config/models.yaml`. Gateway override `TRAINED_PATH=shadow` (do not flip `.env` to trained).

### Instances / images

| instance_id | image | local vs pulled | size |
| --- | --- | --- | --- |
| django__django-11099 | swebench/sweb.eval.x86_64.django_1776_django-11099:latest | already local | 4.19GB |
| django__django-10880 | ...django-10880:latest | **pulled** | 4.18GB (~1.15GB content) |
| django__django-10914 | ...django-10914:latest | **pulled** | 4.19GB |
| django__django-11066 | ...django-11066:latest | **pulled** | 4.18GB |

Pull cap **3** additional images → max **4** instances with local eval images (not 5). Fifth candidate `django__django-11087` not pulled.

Ids: `data/verified_ids_filectx_n5.jsonl` (4 rows). Artifact: `data/verified_session_filectx_n5.jsonl`.

### Metrics

| metric | value |
| --- | --- |
| n_sessions | 4 |
| session_gold | **2/4 (0.50)** — 11099, 10880 |
| rules resolved | 2 true / 0 false / 2 null (needs_swe_eval) |
| trained resolved | 2 true / 0 false / 2 null |
| file_context_source | 11099=docker_cp; others=unavailable (no guessable target paths) |
| spend | 15.653121 → 15.662449 (**+$0.009328**) |
| eval --gate | bounded_check_only; session_gold=true; n_unlabeled_sessions=2; floor n>=300 fail; cost_rules_delta fail (+3.39e-05); BSS/ECE_w fail; ECE_mass waived_small_n |
| production_parity | false; do_not_flip_trained_path |

Labeled subset quality bar: rules/trained resolve rate **1.0** on the 2 session_gold rows (gate quality_session_gold pass).

### Notes

- Mid-run abort after 10914; resumed 11066 alone then merged.
- 10914/11066: SWE_EVAL attempted but unlabeled — honest needs_swe_eval.
- No gold patch injection. No n=300/500 this turn.

---

## Pathready filectx batch2 (2026-08-20)

**Out:** `data/verified_session_filectx_batch2.jsonl`  
**Ids:** `data/verified_ids_filectx_pathready.jsonl` (n=4)  
**Unpaid fix:** GitHub blob URL extraction in `guess_target_paths` (django-11066).  
**Pulls (≤2):** 12754, 15252.

| instance | session_gold | file_context | rules | trained |
| --- | --- | --- | --- | --- |
| django-12754 | false | docker_cp | null | null |
| django-15252 | false | docker_cp | null | null |
| django-11066 | true | docker_cp | true | true |
| django-11099 | true | docker_cp | true | true |

**Rates:** session_gold 2/4; docker_cp **4/4**; resolve 2/4 each policy.  
**Spend:** `15.662449 → 15.680592` (`+0.018143`).  
**Gate:** `bounded_check_only`; `do_not_flip_trained_path: true`.  
**Serve:** `data/scorer-hard-logistic.json`; gateway `TRAINED_PATH=shadow`.  
**Detail:** `.scratch/scorer-pioneer-lift/verified-filectx-batch2-2026-08-20.md`.

---

## Filectx batch3 (2026-08-20)

**Out:** `data/verified_session_filectx_batch3.jsonl`  
**Ids:** `data/verified_ids_filectx_batch3.jsonl` (n=3; pull-only — no unused local after excluding prior 6)  
**Unpaid:** diagnose 12754/15252 → apply/harness unlabeled (`filectx-12754-15252-diagnosis-2026-08-20.md`).  
**Pulls (≤3):** 14140, 11532, 11880.

| instance | session_gold | file_context | rules | trained |
| --- | --- | --- | --- | --- |
| django-14140 | true | docker_cp | false | false |
| django-11532 | false | docker_cp | null | null |
| django-11880 | true | docker_cp | true | true |

**Rates:** session_gold 2/3; docker_cp **3/3**.  
**Spend:** `15.680592 → 15.696931` (`+0.016339`).  
**Cumulative unique session_gold:** **5** (10880, 11066, 11099, 11880, 14140).  
**Gate:** `bounded_check_only`; `do_not_flip_trained_path: true`.  
**Serve:** `data/scorer-hard-logistic.json`; gateway `TRAINED_PATH=shadow`.  
**Detail:** `.scratch/scorer-pioneer-lift/verified-filectx-batch3-2026-08-20.md`.

---

## Session_id log join smoke (2026-08-20 evening)

**Why:** Historical `requests.jsonl` had `n_hops_with_session_id=0`. Restarted shadow gateway with current `app.py` (logs `session_id` on hops). `.env` still has `TRAINED_PATH=trained` — **process override** kept `shadow` only.

| Field | Value |
| --- | --- |
| Instance | `django__django-11099` (local image; **no pull**) |
| Out | `data/verified_session_swe_smoke_filectx_sessionid.jsonl` |
| Resolve | rules=true, trained=true, `session_gold=true`, `file_context_source=docker_cp` |
| Spend | `15.757069 → 15.757980` (Δ **+$0.000911**) |
| Gate | `bounded_check_only`; **`session_joined=true`** (`n_joinable_hops=1`, `n_hops_with_session_id=1`, `n_session_gold_ids=1`) |
| Serve | `SCORER_PATH=data/scorer-hard-logistic.json`; gateway **`TRAINED_PATH=shadow`** (no flip) |
| Log note | New hops carry `session_id` (e.g. `django__django-11099`); counterfactual trained hop uses `::cf-trained` suffix |

**Next (operator):** scale filectx only with local images + budget sign-off; keep serve shadow until n≥300 + cal bars green.
