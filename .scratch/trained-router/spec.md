# Production trained coding router

Status: **proposal-grade** — enough to staff, budget, and implement. Not a hackathon demo spec and not a runbook for aiand’s multi-tenant control plane.

This repo’s **implementable** hop (shadow default, $100 smoke fit, agents later): [`.scratch/trained-hop/spec.md`](../trained-hop/spec.md).

Language in this spec uses CONTEXT.md terms (**trained router**, **Scorer**, **success gold**, **bootstrap resolve**, **session gold**, **threshold-tuning split**, …). Do not invent synonyms.

---

## Go / no-go

**GO** — staff an **aiand-owned trained router** over the **aiand catalog only**: complexity bin → calibrated P(success) per eligible survivor → cheapest that clears threshold + max_regret. Rules stay default + scorer-down / decline fallback. **Shadow, then promote** only if the gate bars hold. Features-only Rec A hop, ~&lt;10ms in-process. No live embed. No invented savings %.

**NO-GO** — replace the rules router; Pioneer/FireRouter product clone; live chat LLM as the hop; hard-require Nebius (or any third-party embed); run the full gold matrix / retune / Verified gate **from this repo** (~$15 cap; 3×5 + teacher smoke only); invent a savings %.

**Do not promote** if fitted medium fails the retune constraint, or if any promotion-gate bar fails. Ship defaults are unfitted; they are not a reason to skip retune or shadow.

---

## What ships

A second **path** behind the same eligible set as rules:

1. Hard constraints (unchanged) → **eligible set**.
2. **Scorer** emits a **complexity bin** and calibrated **P(success)** per survivor.
3. Pick the **cheapest** survivor (list-price unit cost, same `0.4·input_or_cached + 0.6·output` blend as today) that clears **threshold** and **max_regret**.
4. Else **fallback_declined** → rules fallback model (today Qwen 3.6 27B), `path=rules`, reason_code `scorer_down` or decline.

Phase remains an optional hint. Rules fallback still uses phase bars. Bin does **not** pick and does **not** gate eligibility. Effort headers stay `low | medium | high | max` (no `xhigh` unless the team asks) and only retune threshold + max_regret.

Learned stub (`learn.py`, highest AA) is not the trained router. It stays a dark untrained module.

---

## Serving hop

**Scorer (Rec A only):** in-process, **features-only**, gateway features already on the hop + predicted complexity bin + per-survivor logistic **or** GBDT (implementer/eval choice) + Platt / temperature. Score survivors only. Independent heads vs shared trunk + model-id is unpinned. Feature columns are training/eval, not a production freeze.

Rec B (bilinear / MIRT / feature→latent MLP as the shipped hop) is **not a spec door**. Reopen only if Rec A fails the promotion gate. No live embed. No chat teacher on the hop.

Target added latency: ~&lt;10ms p50 in-process.

Wire: `x-routing-effort` only. YAML `trained_effort:` (or equivalent), namespaced away from rules `max_regret: 8`. No raw `x-routing-threshold` / `x-routing-max-regret`.

Default effort: **`medium`**.

---

## Effort table (ship defaults)

Unfitted. Label: not measured on aiand. Units = calibrated P(success), never AA points.

| effort | threshold | max_regret |
| --- | --- | --- |
| `low` | 0.05 | 0.30 |
| `medium` (default) | 0.10 | 0.20 |
| `high` | 0.20 | 0.15 |
| `max` | 0.60 | 0.03 |

`low` still uses the scorer (tiny floor, wide regret). `max` is still cheapest-above-bar on the **same eligible set as rules** (premium floor still lets K3 in). Publish the max row even when today’s catalog often leaves only K3.

**Retune medium before shadow** on the **threshold-tuning split** (below). Initialize at ship defaults; keep them if they win. Fit **medium only**. Other rungs = Pioneer offsets from medium `(0.10, 0.20)`:

| rung | Δ threshold | Δ max_regret |
| --- | --- | --- |
| `low` | −0.05 | +0.10 |
| `high` | +0.10 | −0.05 |
| `max` | +0.50 | −0.17 |

Clamp \(t,r \in [0,1]\), then walk to restore \(t_\text{low} \le t_\text{med} \le t_\text{high} \le t_\text{max}\) and \(r_\text{low} \ge r_\text{med} \ge r_\text{high} \ge r_\text{max}\). Fitted numbers are **runtime config**, not a spec edit. If fitted medium cannot meet the constraint → do not promote.

Search: minimize list-price USD s.t. **success gold** (escalate) **and** **bootstrap resolve** each ≥ rules − 1 pp. Never silver. Never Verified/Lite/TB **session gold**.

**Order:** train → calibrate → retune medium → **shadow at fitted medium** → promotion gate (**medium only**; other rungs diagnostic / ship defaults until fitted) → live.

Detail: [Effort tier threshold and max_regret](issues/17-effort-tier-threshold-max-regret.md) · [Threshold-tuning split](issues/19-threshold-tuning-split.md).

---

## Complexity bins

Query-only, teacher-labelable. Feature + `reason_codes` + train/eval **stratum** only.

| Bin | Boundary (messages + tool schemas + optional phase hint) |
| --- | --- |
| `trivial` | One-shot lookup / rename / format / comment / docstring; no repo reasoning. |
| `standard` | Localized implement / fix / test / tool call with a clear spec; one area of the code. |
| `hard` | Multi-file, ambiguous spec, debug-after-fail, security review, cross-cutting plan. Cheap models often fail. |
| `frontier` | Catalog-ceiling or still-may-fail: novel algorithm, huge ambiguous repo, SWE-Verified-class, adversarial. Not a model id. |

Same phase can sit in different bins. No fifth `debug_fail` bin. Bloom (`bloom_level`) is optional on the **offline teacher row only** — not a live reason_code, not in Decision headers.

**Stratum** = complexity bin × **phase family** × tools-present vs not. Phase family = `discover | plan | edit | tool | debug | summarize` (same collapse as rules bars). 4×6×2 = 48 cells. No 48-cell joint % table.

Detail: [Complexity bin taxonomy](issues/07-complexity-bin-taxonomy.md) · [Sparse-train n and stratum fractions](issues/18-sparse-train-n-and-stratum-fractions.md).

---

## Data and labels

### Success vs session vs silver vs bootstrap resolve

| Label | What | Used for |
| --- | --- | --- |
| **Success gold** | After an aiand run: no escalate, and valid tools/JSON if required. Missing ≠ 0. | Student (observed cells), calibrator, retune escalate bar, promotion ECE/Brier \(y\) |
| **Silver P(success)** | Teacher query-only \(p\) per eligible id. | Student regularizer on **unobserved** cells only |
| **Bootstrap resolve** | Aiand completion vs allowed-dump F2P/P2P (or dump harness). Not dump teacher `resolved`. | Retune session-level bar |
| **Session gold** | Verified/Lite / flashlight `tests_passed` / SWE resolve. | Promotion gate quality only |

Never calibrate, gate, or threshold-tune on silver. Never train / calibrate / retune on **eval-only dumps**.

### Bootstrap dumps

**Required** (parse + relabel; no dump has AIand phases or per-catalog success gold):

- SWE-smith trajectories, **`tool` split only** (MIT). Not the 5k SFT cut, not `xml`/`ticks`.
- SWE-smith **tasks** (MIT) as the relabel pool.
- **BFCL** (Apache-2.0) for tool-JSON only — never a promotion-gate corpus.

**Allowed, not required:** SWE-Gym OpenHands SFT+verifier and R2E-Gym SFT (Apache **repo**; HF cards undeclared — diligence note). Skip if legal review blocks; smith alone still ships.

**Named optional:** SWE-rebench **tasks** (CC-BY-4.0), filter per-instance `license_name`.

**Eval-only** (never train, calibrator, or threshold/max_regret fit): whole **SWE-bench family** + **Terminal-Bench** (do-not-train canary) + **Multi-SWE-bench** (1,632 human-validated). Verified/Lite remain the promotion-gate corpora.

**Out:** RouterBench / RouteLLM / RouterArena; HumanEval / MBPP / LiveCodeBench / RepoBench; NVIDIA SWE-Hero/Zero OpenHands dumps; OpenHands feedback; ToolBench.

**Hygiene:** drop bootstrap rows whose `instance_id` / problem hash matches the SWE-bench family **or Multi-SWE-bench**. This repo’s **3×5** is smoke, disjoint from bootstrap dumps and from the promotion split. Flywheel is not a public dump.

**Multi-SWE-RL follow-on (not v1):** if **≥20%** of hops in a drift-canary window are **non-Python** (ext/path/`lang` tag; unknown ≠ non-Python; mixed with a Python source file = Python), operator ingests Multi-SWE-RL **tasks** for the **next full retrain** after a diligence gate (ByteDance IP + upstream licenses; drop forbidden instances). Smith stays. Verified gate unchanged. Rebench-V2 stays extra optional, not an automatic substitute. If legal blocks the dump, do not ingest; trigger stays up.

Detail: [Bootstrap dump set](issues/16-bootstrap-dump-set.md) · [Multi-SWE-RL trigger](issues/21-multi-swe-rl-trigger.md) · [note](research/bootstrap-datasets.md).

### Teacher (offline only)

Cheap-then-escalate, catalog-relative **policy + example pins**. Not the live hop. Strict `json_schema`, temperature 0, cache like the gateway. Prices from `GET /v1/models`.

**Exclusion:** teacher providers ∉ labs of **measured trio ∪ live fallback**. Today: `qwen`, `moonshotai`, `deepseek-ai`. K3 is not a teacher.

**Cheap teacher:** highest AA among remaining models with `output_per_1m ≤ $2`. Fail a `json_schema` ping → drop that id and rerun.

**Escalate teacher:** highest AA among remaining ≠ cheap teacher. Fallback `zai-org/glm-5.1` if 5.2 is missing.

| Catalog | Cheap teacher | Escalate teacher |
| --- | --- | --- |
| This org (Motif present) | `motif-technologies/motif-3` | `zai-org/glm-5.2` |
| Public catalog, no Motif | `google/gemma-4-31b-it` | `zai-org/glm-5.2` |

Escalate when: bin `frontier` always; `hard` only if `label_confidence < 0.60` or AA-disagree (\(|p_\text{success} − \text{aa_index}/100| > 0.25\) on any eligible measured-trio ∪ Flash). Soft-cap **≤25%** (keep all frontier; sample extra `hard`). Invalid cheap output: retry once → escalate teacher → else **unlabeled** (missing, not fake bins/silver).

If the teacher advertises `reasoning_effort`, send the minimum (`low` if present). Do not feed completions into the bin/silver call. Pairwise judge is not v1-required.

**Budget:** spec = **few thousand** query-only rows. This repo = teacher **smoke ~100** (do not eat the $15 3×5 cap).

Detail: [Teacher model from aiand catalog](issues/10-teacher-model-from-aiand-catalog.md) · [Teacher labeling for multi-candidate success](issues/02-teacher-labeling-multi-candidate.md) · [note](research/teacher-labeling.md).

### Gold matrix (hybrid)

Not full N×Q, not sparse everywhere.

- **Dense gold slice** (held-out): every *eligible* model, **n≥300** stratified queries, one prod-like completion (gateway cache). Calibrator + reliability + **new-model onboard**. 3×5 stays smoke, disjoint. Not the threshold-tuning split.
- **Sparse gold** (train): **n = 4000** queries (floor **n ≥ 3000** if SWE-bench collision filter shrinks the pool) × **sparse-train anchors** = Flash + measured trio when eligible (≤16k completions). Never a single model. Optional gym/r2e/rebench may **add**, not cut smith. K3 / Motif / Gemma / GLM / GPT-OSS only here via dense slice + flywheel (optional thin `hard|frontier`×tools K3 probe **≤5%** of n, not v1-required).
- **Flywheel:** observed hop (+ escalate) + small 2–3 explore. Missing cell ≠ 0.
- **Eligible set only**, not the full catalog.

**Sparse-train margins** (independent; ±5 pp OK; leftover after floors fills these; oversampling hard/frontier vs dump mass):

| Axis | Targets |
| --- | --- |
| bin | trivial 15% / standard 40% / hard 30% / frontier 15% |
| tools | present 75% / absent 25% |
| phase family | edit 30% / tool 25% / plan 15% / debug 15% / discover 10% / summarize 5% |

Occupied-stratum **floor ≥ 20**. Empty cells stay empty (no synthetic queries). If an occupied cell has &lt;20 available after labeling, take all of them.

**Dump mix (sparse train):** primary = smith `tool` traj steps. **BFCL ≤ 15%** of n (tool-JSON only). Tasks dump = teacher/relabel pool unless traj pool &lt; n≥3000 after collision filter.

**Spec spend band** (candidate runs, not teacher): dense n≥300 × eligible + sparse thousands × 4 anchors + second dense threshold-tuning slice + per-cell dump harness — low hundreds to low thousands USD at current list prices. **This repo does not run it.**

Detail: [Gold matrix sampling](issues/13-gold-matrix-sampling.md) · [Sparse-train n and stratum fractions](issues/18-sparse-train-n-and-stratum-fractions.md).

### Threshold-tuning split

Third held-out bootstrap split, **dense** (every eligible), **n≥300** SWE-like with **bootstrap resolve**. Disjoint from sparse-train, dense gold slice, 3×5, and promotion. Not flywheel.

Source: smith `tool` + smith tasks; gym/r2e/rebench only if ingested; collision-filter vs SWE-bench family. BFCL may be extra tools rows only — not required, does not count toward n≥300. Same stratum **axes** as the rest of the map; no retune-only tilt; do not copy sparse-train margin % onto this split.

One prod-like completion per cell + dump F2P/P2P (or dump harness). Dump teacher `resolved` is not y.

Detail: [Threshold-tuning split](issues/19-threshold-tuning-split.md).

### Student training target

**Gold + query-only silver regularizer** — not gold-only, not silver-only, not Zooter. Same recipe for bootstrap and flywheel.

- Observed cells: `success_gold` only (BCE/Brier). Gold wins if silver disagrees.
- Unobserved cells: silver as a small KL/MSE prior. Skip cells with neither (don’t impute 0). Retrain batch includes a teacher pass.
- Complexity-bin head stays teacher bins. λ is a train hyperparam (small regularizer, gold dominates).

Detail: [Student training target](issues/14-student-training-target.md).

### Optional embed ablation (offline only)

**Features-only is the valid ship** and the serve hop. Optional offline **training embed** ablation: Qwen3-0.6B or 8B MRL ≤256-d (Nebius 8B ok in a prototype; **no production hard-require**). Keep vectors iff held-out **success-gold** Brier is strictly better **and** ECE is not worse; if they win, **distill into the features-only hop**. No live embed. MiniLM / 0.6B stay off the serve path.

Detail: [Keep embeddings in the training recipe?](issues/11-keep-embeddings-in-training-recipe.md) · [Tiny local embed on the live hop?](issues/12-tiny-local-embed-on-live-hop.md) · [note](research/qwen3-embedding.md).

---

## Calibration

Held-out **measured** dense gold slice only (not silver, not threshold-tuning split, not promotion).

- Platt if \(n_\text{cal} \lesssim 1000\), else isotonic.
- Gate metrics (selection-conditioned, on promotion hops): Brier skill \(>0\); equal-width ECE \(M=10\) **and** equal-mass ECE \(\le 0.03\); reliability diagram attached. Report \(M=15\) + MCE; do not gate on them alone.
- \(\hat p\) = P(success) of the **selected** hop; calibration \(y\) = **success gold**.

Detail: [Calibration for router P(success)](issues/03-calibration-for-router-p-success.md) · [note](research/calibration.md) · [Promotion gate numeric bars](issues/08-promotion-gate-numeric-bars.md).

---

## Shadow and promotion

**Shadow required** before any live trained pick. Same JSONL row: `path=shadow`, `selected` = rules pick, plus `trained_selected` / `trained_confidence`, `rules_cost_delta_usd` (trained − rules; **not** called savings). No second shadow file.

Promote out of shadow only if **all** hold on a frozen promotion split unused for train, calibrator, or threshold/max_regret:

1. **Quality (1 pp):** **session gold** and per-request escalate rate, each ≥ rules − 0.01 absolute. Session gold worse cannot be rescued by escalate-only.
2. **Cost:** total list-price USD **rules cost delta &lt; 0**. Equal → no promote. Not called savings. No minimum %.
3. **Calibration:** BSS \(>0\); dual ECE \(\le 0.03\) as above; reliability diagram.
4. **Split:** primary **SWE-bench Verified (500)**; Lite (300) OK as cheaper proxy **until** Verified is run, not a substitute after. Floor **n ≥ 300** session-gold tasks. **Terminal-Bench (80–89) = canary only** (do not train; n too small to pass/fail ECE alone). ECE/Brier use hops inside those sessions.

Gate at **medium** only.

---

## Observability

**Slim headers (ex-ante) + full JSONL (ex-post).** Prototype: [observability-decision-contract.html](prototypes/observability-decision-contract.html).

Trained-path headers: `X-Router-Model`, `Phase`, `Effort`, `Complexity-Bin`, `Confidence` (= winner P(success); omit if scorer down), `Rule` (`threshold` | `max_regret` | `fallback_declined`), `Path` (`rules` | `trained` | `shadow`), `Baseline-Model`, `Savings-Usd` (estimate), `Reason-Codes`, `Candidates` (eligible ids), `Threshold`, optional `Escalated-From` / `Trained-Would` (shadow only). Drop prose `X-Router-Reason` on the trained path; rules path may keep it.

JSONL: all header fields plus `p_success` map for every eligible id, `max_regret`, realized `savings_usd` + `cost_usd` from actual tokens, `baseline_name: most_expensive_eligible`. Stream: estimate on headers at start; realized row when usage lands.

**Flywheel log (production):** that same JSONL (every `path`, plus flashlight outcomes and explore cells) as an append-only log on **aiand infra**. They pick object store vs existing request log; spec does not pin a vendor. Prototype is `data/requests.jsonl`. Keep at least until the next full retrain and its gate: contract fields, success gold, Rec A features. Secrets redacted (`redact_keys`). Prompt/body retention is aiand policy. Retrain reads **their** store. No second flywheel file.

Scorer down: `path=rules`, `rule=fallback_declined`, reason_code `scorer_down`, no fake confidence.

No dashboard / playground / session-savings API requirement.

Detail: [Observability Decision contract](issues/09-observability-decision-contract.md) · [Flywheel log store](issues/22-flywheel-log-store.md).

---

## Cost language

**Named savings baseline** = `most_expensive_eligible` (same unit-cost blend). Log `baseline_model_id` every time. Savings = baseline cost − selected cost; ≥ 0 by construction. K3 is today’s ceiling **when eligible**, not a pinned id.

**Rules cost delta** = trained − rules on the same request. Promotion gate and shadow only. Not savings. Never invent a %.

Detail: [Named savings baseline](issues/06-named-savings-baseline.md).

---

## Catalog drift and retrain

New catalog ids stay **rules-only / prior-only** for live trained P(success) until a **dense gold slice including that id** reaches n≥300. Silver may train the student head; it does not unstick live trained pick. Shadow may log the prior with a reason_code.

**Full retrain** (event + operator; no calendar, no every-N-hops): (i) that onboard bar, (ii) **drift canary** trip, or (iii) operator. Retrain batch includes a teacher pass.

**Drift canary** (monitor only): n≥300 production hops or 7 days, whichever later. Trip if escalate rate is >1 pp worse than rules, or BSS≤0, or either ECE>0.03 (promotion definitions, serve hops, not Verified).

**\(t,r\):** freeze live fitted medium until a full retrain. Then train → cal → retune on a **production retune holdout** (n≥300 dense flywheel, disjoint from that train/cal; y = success gold / escalate ≥ rules − 1 pp; never Verified/Lite/TB) → shadow → Verified gate (medium) → live. Bootstrap **threshold-tuning split** is v1 only. Miss the 1 pp retune bar → do not ship that retrain.

**During replacement:** drift trip → `path=rules`, reason_code `retrain_drift`, shadow the candidate. Operator / new-id (no drift) → keep previous trained until the replacement gates. Failed gate → keep what was live before that attempt. No live A/B.

Detail: [Retrain cadence and threshold refit](issues/20-retrain-cadence-and-threshold-refit.md).

---

## This repo vs production

| | This repo (prototype) | Production spec |
| --- | --- | --- |
| Rules gateway | Ships | Stays default + fallback |
| Teacher | Smoke ~100 query-only | Few thousand query-only |
| Gold matrix / retune / Verified | 3×5 smoke only | Full hybrid + threshold-tuning n≥300 + Verified gate |
| Learned stub | Dark unless 3×5 beats rules (`DESIGN.md`) | Not the trained path |
| Trained path | Shadow smoke only if staffed here | Shadow → gate → live |
| Control plane / **flywheel log** | `data/requests.jsonl` prototype | Aiand infra (JSONL-compatible; they pick the store) |

Soft `BUDGET_LIMIT_USD` here is **$15**. Do not run sparse-train or threshold-tuning spend against it.

---

## Staffing sketch (production)

1. Ingest required dumps + collision filter; teacher schema ping + cheap-then-escalate labels.
2. Sparse gold n=4000 × Flash+trio; dense gold slice n≥300 × eligible.
3. Train Scorer (features-only default; optional embed ablation offline).
4. Calibrate on dense slice (Platt / isotonic).
5. Threshold-tuning split n≥300 + bootstrap resolve; retune medium; offsets for other rungs.
6. Shadow at fitted medium (observability contract); production **flywheel log** on aiand infra from this point.
7. Promotion gate on Verified (Lite proxy until Verified); TB canary.
8. Live trained pick if all bars hold; new ids wait for dense onboard.
9. Drift canary in production; on trip, rules immediately and full retrain (shadow + Verified) before trained returns.

---

## Out of scope

- Full Pioneer clone: dashboard, Routing Playground, session-savings API, Anthropic Messages, OpenAI Responses, versioned `auto_v*`, FireConnect-style installer, six-harness matrix, router-only credits.
- FireRouter BYOK / `x-routing-preference` 1–5 / Opus pass-through.
- Cursor, K8s, Modal-hosting the catalog, inventing a savings %.
- Replacing the rules router.
- Live aiand chat model as the routing hop.
- Hard-requiring Nebius (or any third-party embed).
- Operating aiand’s multi-tenant production infra from this repo.
- Rec B as a v1 hop; live embed; `xhigh`; per-request numeric threshold overrides.
- RouterBench-class non-agent priors; Multi-SWE-RL as v1-required.

---

## Decision index

Map: [`map.md`](map.md). Research notes: [`research/`](research/). Prototype: [`prototypes/observability-decision-contract.html`](prototypes/observability-decision-contract.html).

| Topic | Ticket |
| --- | --- |
| Scorer hop / Rec A | [01](issues/01-scorer-architectures-under-10ms.md) · [15](issues/15-scorer-shape-rec-a-vs-b.md) · [12](issues/12-tiny-local-embed-on-live-hop.md) |
| Teacher + silver | [02](issues/02-teacher-labeling-multi-candidate.md) · [10](issues/10-teacher-model-from-aiand-catalog.md) |
| Calibration + gate | [03](issues/03-calibration-for-router-p-success.md) · [08](issues/08-promotion-gate-numeric-bars.md) |
| Dumps | [04](issues/04-bootstrap-coding-agent-datasets.md) · [16](issues/16-bootstrap-dump-set.md) · [21](issues/21-multi-swe-rl-trigger.md) |
| Embed ablation | [05](issues/05-qwen3-embedding-training-features.md) · [11](issues/11-keep-embeddings-in-training-recipe.md) |
| Savings vs rules delta | [06](issues/06-named-savings-baseline.md) |
| Bins | [07](issues/07-complexity-bin-taxonomy.md) |
| Observability + flywheel log | [09](issues/09-observability-decision-contract.md) · [22](issues/22-flywheel-log-store.md) |
| Gold matrix + student | [13](issues/13-gold-matrix-sampling.md) · [14](issues/14-student-training-target.md) · [18](issues/18-sparse-train-n-and-stratum-fractions.md) |
| Effort + retune + retrain | [17](issues/17-effort-tier-threshold-max-regret.md) · [19](issues/19-threshold-tuning-split.md) · [20](issues/20-retrain-cadence-and-threshold-refit.md) |
