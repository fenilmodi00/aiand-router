# Production Handoff Runbook

Status: **proposal-grade** — enough for the aiand team to staff, budget, and implement a production trained router. Not a hackathon demo spec and not a runbook for aiand's multi-tenant control plane.

Language follows `CONTEXT.md` vocabulary (**promotion gate**, **flywheel**, **flywheel log**, **calibrated P(success)**, **eligible set**, **named savings baseline**, **scorer**, **drift canary**, **shadow**). Do not invent synonyms.

Spec: [`.scratch/trained-router/spec.md`](../.scratch/trained-router/spec.md). This repo's prototype is `$15` smoke only; production spend is on aiand infra.

---

## (a) Full Verified(500) Promotion Gate

### What this is

The **promotion gate** is the explicit eval that must say the trained router beats the rules router on quality, cost, and calibration before trained may leave shadow. This is **not** the bounded check (task 18's `lite_runner` on SWE-bench Lite, capped at 50 instances). This is the full gate on **SWE-bench Verified**.

### Dataset pin

- **Primary:** `princeton-nlp/SWE-bench_Verified`, test split, 500 instances.
- **Proxy until Verified is run:** SWE-bench Lite (300 instances). Lite is a cheaper proxy **until** Verified is run, not a substitute after.
- **Canary only:** Terminal-Bench (80-89 instances). Do not train on it; n is too small to pass/fail ECE alone.
- **Never train, calibrate, or threshold-tune on** any SWE-bench family split, Terminal-Bench, or Multi-SWE-bench. These are **eval-only dumps**.

### Pass bars (all must hold, gate at medium only)

Promote out of shadow only if **all** hold on a frozen promotion split unused for train, calibrator, or threshold/max_regret fit:

1. **Quality (1 pp):** session gold (`tests_passed` / SWE resolve) and per-request escalate rate, each >= rules - 0.01 absolute. Session gold worse cannot be rescued by escalate-only.
2. **Cost:** total list-price USD **rules cost delta < 0** (trained - rules; not called savings). Equal -> no promote. No minimum %.
3. **Calibration:** Brier skill score (BSS) > 0; dual ECE <= 0.03 (equal-width M=10 **and** equal-mass M=10); reliability diagram attached. Report M=15 + MCE; do not gate on them alone.
4. **Floor:** n >= 300 session-gold tasks. ECE/Brier use hops inside those sessions.

### How to run the gate

The gate runs every eligible model on every Verified instance through the gateway, collects session gold (tests_passed / patch resolve), and compares trained vs rules on the four bars.

**Step 1 — Generate Verified query set:**

```bash
python scripts/gen_verified_queries.py
```

This emits `datasets/verified-queries.jsonl` with checkable outcomes (expected substrings, pytest verify, JSON validity). Each row has `prompt`, `phase`, `hint_bin`, `needs_tools`, and optional `expected` / `verify_pytest` / `module` / `tests`.

**Step 2 — Run dense gold on the Verified split (every eligible model):**

```bash
set AIAND_TRAIN=1
python -m aiand_router.train gold --queries datasets/verified-queries.jsonl --out data/verified_gold.jsonl --dense --exclude data/dense_cal.jsonl
```

`--dense` runs every eligible model per query (not sparse anchors). `--exclude` keeps the calibrator slice disjoint. The gate reads `success_gold` from each row (no escalate + valid tools/JSON if required).

**Step 3 — Fit the candidate scorer (if not already fitted):**

```bash
set AIAND_TRAIN=1
python -m aiand_router.train fit --gold data/gold.jsonl --silver data/silver.jsonl --out data/scorer.candidate.json
```

Use `--gbdt` only if logistic transfer fails (Spearman(train, eval) > 0 first):

```bash
set AIAND_TRAIN=1
python -m aiand_router.train fit --gold data/gold.jsonl --silver data/silver.jsonl --out data/scorer.candidate.json --gbdt
```

**Step 4 — Retune medium on the threshold-tuning split (v1 bootstrap):**

```bash
python -m aiand_router.train retune --dense data/threshold_tune.jsonl --scorer data/scorer.candidate.json
```

This prints the `trained_effort:` YAML fragment (or `do-not-promote`). Medium only; other rungs are Pioneer offsets.

**Step 5 — Shadow at fitted medium, then gate-check:**

```bash
python -m aiand_router.retrain --plan-only
```

This runs fit -> cal-report -> retune (if available) -> write `data/scorer.candidate.json` + `data/retrain_report.md` -> gate-check. Prints `gate_check: shadow-ready` or `gate_check: do-not-promote`. Never sets `TRAINED_PATH=trained`.

**Step 6 — Run the Verified session gate:**

Run the lite_runner (or a future `verified_runner`) against the gateway in shadow mode, collecting session gold:

```bash
python -m aiand_router.lite_runner --n 500 --gateway http://127.0.0.1:8000 --out data/verified_results.jsonl
```

Then compare trained vs rules on the four bars using the eval module:

```bash
python -m aiand_router.eval
```

The eval command prints costs and models from the request log and will not invent a savings percentage. Promote only if all four bars hold.

### Cost estimate formula

The gate runs every eligible model on n=500 instances. Per-instance cost depends on the eligible set and token counts.

**Per-completion cost** (one model, one instance):

```
cost = (prompt_tokens / 1_000_000) * input_price + (completion_tokens / 1_000_000) * output_price
```

Using the `0.4 * input_or_cached + 0.6 * output` blend and ~800 output tokens per completion (flashlight-style turn loop), the per-model-per-instance cost at current README list prices:

| Model | Input $/1M | Output $/1M | Est. cost per completion (~800 out) |
| --- | ---: | ---: | ---: |
| `deepseek-ai/deepseek-v4-flash` | $0.15 | $0.25 | ~$0.0002 |
| `qwen/qwen3.6-27b` | $0.32 | $3.20 | ~$0.0019 |
| `motif-technologies/motif-3` | $0.50 | $2.00 | ~$0.0012 |
| `moonshotai/kimi-k2.7-code` | $0.75 | $3.50 | ~$0.0021 |
| `deepseek-ai/deepseek-v4-pro` | $1.00 | $2.50 | ~$0.0015 |
| `zai-org/glm-5.2` | $1.00 | $4.00 | ~$0.0024 |
| `moonshotai/kimi-k3` | $3.00 | $12.50 | ~$0.0073 |

**Total gate cost** = n_instances (500) x n_eligible_models x per_completion_cost.

With the measured trio (Qwen 3.6 27B, Kimi K2.7 Code, DeepSeek V4 Pro) + Flash as sparse anchors:

```
500 x 4 models x ~$0.0014 avg = ~$2.80
```

With the full eligible set including K3 and GLM 5.2 (7 models):

```
500 x 7 models x ~$0.0024 avg = ~$8.40
```

This is the promotion gate only — disjoint from train, calibrator, and threshold-tuning spend. The spec spend band (candidate runs, not teacher) is low hundreds to low thousands USD at current list prices.

### State

- This is the **promotion gate**, not the bounded check (task 18's `lite_runner` on Lite, capped at 50).
- Gate at **medium** only. Other rungs are diagnostic / ship defaults until fitted.
- Failed gate -> keep what was live before that attempt. No live A/B.
- Lite (300) is OK as a cheaper proxy **until** Verified is run, not a substitute after.

---

## (b) aiand-infra Flywheel Log Store

### What this is

The **flywheel log** is the append-only JSONL-compatible store on **aiand infra** for production serve rows. It is the same Decision contract as the live hop. This repo's `data/requests.jsonl` is the **prototype only** — production runs on aiand infra, not this checkout.

### JSONL contract fields

Every row is written by `append_jsonl` (adds `ts`) + `_jsonl_row` (base + conditional fields) + call-site extras. The full field set:

| Field | Source | Description |
| --- | --- | --- |
| `ts` | `append_jsonl` | UTC ISO timestamp, added first on every row |
| `phase` | `_jsonl_row` base | Agent phase (`discover`, `plan`, `edit`, `tool`, `debug`, `summarize`, or Draft alias) |
| `selected` | `_jsonl_row` base | Model id that served this hop (rules pick in shadow) |
| `reason` | `_jsonl_row` base | Prose reason (rules path; dropped on trained path) |
| `candidates` | `_jsonl_row` base | Comma-separated eligible model ids |
| `path` | `_jsonl_row` base | `rules`, `trained`, or `shadow` |
| `requested` | call-site extra | Original requested model (`router/auto`) |
| `stream` | call-site extra | Whether this was a streaming request |
| `tokens_in` | call-site extra | Prompt token count |
| `tokens_out` | call-site extra | Completion token count |
| `cost_usd` | call-site extra | Realized list-price USD from actual tokens |
| `latency_ms` | call-site extra | End-to-end latency in milliseconds |
| `status` | call-site extra | HTTP status code |
| `cache_hit` | call-site extra | Whether the response came from request cache |
| `tool_valid` | call-site extra | Whether tool calls were valid (if tools required) |
| `json_valid` | call-site extra | Whether JSON output was valid (if JSON required) |
| `trained_selected` | `_jsonl_row` conditional | What the trained hop would have picked (shadow only) |
| `trained_confidence` | `_jsonl_row` conditional | Calibrated P(success) of the trained pick (shadow only) |
| `confidence` | `_jsonl_row` conditional | Calibrated P(success) of the selected hop |
| `complexity_bin` | `_jsonl_row` conditional | `trivial`, `standard`, `hard`, or `frontier` |
| `p_success` | `_jsonl_row` conditional | Map of eligible id -> calibrated P(success) |
| `rule` | `_jsonl_row` conditional | `threshold`, `max_regret`, or `fallback_declined` |
| `reason_codes` | `_jsonl_row` conditional | Short diagnostic tags (`bin:...`, `pick:...`, `scorer_down`, `retrain_drift`) |
| `max_regret` | `_jsonl_row` conditional | Max allowed P(success) gap from top survivor |
| `threshold` | `_jsonl_row` base | Minimum P(success) to be pickable on trained path |
| `baseline_model_id` | `_jsonl_row` conditional | `most_expensive_eligible` id for this request |
| `savings_usd` | `_jsonl_row` conditional | Baseline cost - selected cost (>= 0 by construction) |
| `rules_cost_delta_usd` | `_jsonl_row` conditional | Trained - rules cost on same request (shadow/promotion only; not called savings) |
| `effort` | `_jsonl_row` conditional | `low`, `medium`, `high`, or `max` |
| `escalated_from` | call-site extra | Model id that was escalated from (if escalated) |
| `tests_passed` | call-site extra | Flashlight test outcome (if available) |
| `patch_applied` | call-site extra | Flashlight patch outcome (if available) |
| `wire` | call-site extra | Wire format (`anthropic_messages`) if non-OpenAI |

### Retention

- Rows kept **at least until the next full retrain and its gate**.
- A **drift canary** trip triggers a full retrain; old rows are archived after the replacement gates.
- Retrain reads the aiand-infra store, not this repo's `data/requests.jsonl`.

### Redaction

- No API keys in JSONL. `_jsonl_row` does not include `AIAND_API_KEY` or `ROUTER_API_KEY`.
- The replay page never renders API keys.
- Prompt/body retention is aiand policy, not this spec.

### Store

- **aiand infra**, not this repo's `data/requests.jsonl` (prototype only).
- aiand picks object store vs existing request log; spec does not pin a vendor.
- No second flywheel file. Same JSONL row for every `path` (`rules`, `trained`, `shadow`), plus flashlight outcomes and explore cells.

### Drift canary (monitor only)

The drift canary reads the flywheel log and trips a retrain signal when quality degrades:

```bash
python scripts/check_canary.py
```

Trip conditions (promotion-gate definitions on serve hops):
- Escalate rate > 1 pp worse than rules.
- BSS <= 0.
- Either ECE > 0.03.

Window: n >= 300 production hops **and** 7 days, whichever later (both must be met). On trip: `path=rules`, reason_code `retrain_drift`, shadow the candidate. Operator runs full retrain (shadow + Verified gate) before trained returns.

---

## (c) Embed Ablation Execution

### What this is

An optional offline **training embed** ablation. **Features-only is the valid ship** and the serve hop. This ablation tests whether adding embedding-model vectors as extra student train features improves held-out success-gold metrics.

### Training embed

- **Model:** Nebius `Qwen/Qwen3-Embedding-8B` (prefer 0.6B or MRL <= 256-d if available).
- **Offline only.** Never on the serve hop. No live embed.
- Not a production hard dependency. MiniLM / 0.6B stay off the serve path.

### Keep-iff gate

Keep embedding vectors **only if** held-out **success-gold** (not silver, not threshold-tuning split):

1. **Brier is strictly better** than the features-only student.
2. **ECE is not worse** than the features-only student.

Both must hold. If either fails, discard the vectors and ship features-only.

### If kept: distill into features-only hop

If the embed ablation wins, **distill into the features-only hop**. The serve hop stays features-only — no live embed forward. The distilled student carries the embed signal as feature weights.

### Commands

**Step 1 — Fit features-only baseline scorer:**

```bash
set AIAND_TRAIN=1
python -m aiand_router.train fit --gold data/gold.jsonl --silver data/silver.jsonl --out data/scorer_features_only.json
```

**Step 2 — Fit GBDT variant (if logistic transfer fails):**

```bash
set AIAND_TRAIN=1
python -m aiand_router.train fit --gold data/gold.jsonl --silver data/silver.jsonl --out data/scorer_gbdt.json --gbdt
```

**Step 3 — Generate training-embed vectors (offline, Nebius):**

Fetch embedding vectors for each training query from Nebius `Qwen/Qwen3-Embedding-8B` (or 0.6B / MRL <= 256-d). Cache vectors keyed by prompt hash. These are extra student train features only.

**Step 4 — Fit embed-augmented scorer:**

Add cached training-embed vectors as extra feature columns to the student, then fit:

```bash
set AIAND_TRAIN=1
python -m aiand_router.train fit --gold data/gold_embed.jsonl --silver data/silver.jsonl --out data/scorer_embed.json
```

**Step 5 — Compare on held-out success gold:**

Run calibration metrics on the dense gold slice (not silver, not threshold-tuning split, not promotion):

```bash
python -m aiand_router.retrain --plan-only
```

Check `data/retrain_report.md` for BSS and ECE. If embed Brier is strictly better AND ECE is not worse vs features-only, keep vectors and distill into the features-only hop. Else discard.

### State

- Features-only is the default training recipe and the serve hop.
- A tiny feature->latent MLP still counts as features-only.
- No live embed on the serve hop. No chat teacher on the hop.
- Rec B (bilinear / MIRT / feature->latent MLP as the shipped hop) is not a spec door. Reopen only if Rec A fails the promotion gate.

---

## (d) K3 Dense-Gold Onboarding

### What this is

New catalog ids stay **rules-only / prior-only** for live trained P(success) until a **dense gold slice including that id** reaches n >= 300. This section documents onboarding `moonshotai/kimi-k3` (K3) from silver-only to measured P(success).

### Steps

**Step 1 — Add K3 to eligible anchors for the dense gold slice.**

K3 is gated behind `x-routing-effort: max` (premium floor). For the dense gold slice, include K3 in the eligible set so every query runs K3. The sparse-train anchors (Flash + measured trio) stay unchanged; K3 enters via the dense slice + flywheel.

**Step 2 — Run dense gold n >= 300 with K3 included.**

```bash
set AIAND_TRAIN=1
python -m aiand_router.train gold --queries data/dense_queries.jsonl --out data/dense_gold_k3.jsonl --dense --exclude data/dense_cal.jsonl
```

`--dense` runs every eligible model per query (including K3). `--exclude` keeps the calibrator slice disjoint. Each row gets `success_gold` (no escalate + valid tools/JSON if required).

**Step 3 — Refit scorer with K3 gold cells.**

```bash
set AIAND_TRAIN=1
python -m aiand_router.train fit --gold data/dense_gold_k3.jsonl --silver data/silver.jsonl --out data/scorer.json
```

K3's P(success) is now trained from observed gold cells, not teacher silver.

**Step 4 — K3 P(success) becomes measured (not silver-only).**

After refit, `score_eligible` returns K3's calibrated P(success) from the logistic/GBDT head + Platt/isotonic, trained on real gold. The artifact's `p_success` table for K3 is backed by observed outcomes.

**Step 5 — Update artifact label from `k3_prior: silver_only` to `k3_prior: measured`.**

The scorer artifact (`data/scorer.json`) includes a `k3_prior` field. After onboarding, update it to `measured` to signal that K3's P(success) is calibrated from real gold, not teacher silver.

### Cost estimate

K3 at README list prices: $3.00 / 1M input, $0.50 / 1M cached input, $12.50 / 1M output.

**Per-completion cost** (n=300, ~800 output tokens):

```
cost_per_completion = (prompt_tokens / 1_000_000) * 3.00 + (800 / 1_000_000) * 12.50
```

At ~1500 prompt tokens:

```
cost_per_completion = (1500 / 1_000_000) * 3.00 + (800 / 1_000_000) * 12.50
                    = 0.0045 + 0.0100
                    = $0.0145
```

**Total K3 dense-gold cost** = n_instances (300) x per_completion_cost:

```
300 x $0.0145 = ~$4.35
```

This is significant — K3 is the most expensive model in the catalog ($12.50/1M output). Budget accordingly.

### After onboarding

- K3's P(success) is calibrated from real gold, not teacher silver.
- K3 may appear in the trained hop's `p_success` map with a measured value.
- Shadow may log K3's prior with a reason_code during onboarding; live trained pick unsticks only after the dense slice reaches n >= 300 and the scorer is refit.
- K3 is today's ceiling **when eligible** (the named savings baseline), not a pinned id.

### Full retrain after K3 onboarding

After K3 is onboarded, a full retrain follows the standard cadence:

```bash
python -m aiand_router.retrain --plan-only
```

Then shadow at fitted medium, run the Verified gate (section a), and promote only if all bars hold. Freeze live fitted medium until the next full retrain.
