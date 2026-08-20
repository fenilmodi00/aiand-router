# Scorer Router vs Fireworks/Pioneer — Research & Debate Synthesis

**Fetched:** 2026-08-20. Primary sources only for external claims (official docs, papers, owner GitHub). Codebase claims cite file:line. Prior research in `.scratch/trained-router/research/` informed URL discovery but is not used as evidence.

---

## Executive Summary

**Fireworks FireRouter** and **Pioneer Model Router** solve the same product problem—route coding-agent traffic to cheaper models when safe—but with **different architectures and honesty about calibration**. FireRouter is a **binary cascade** (redirect to open model vs pass-through to closed-source) with a 1–5 quality/savings dial; it does **not** publish per-candidate calibrated P(success). Pioneer matches aiand’s **Pioneer-shaped policy** (complexity → per-model calibrated P(success) → cheapest above threshold + max_regret) but publishes **no calibration method, ECE, or training recipe**.

aiand-router’s **routing logic is correct** (`tests/test_quality_routing.py` passes on fixture artifacts). Failures are **end-to-end**: (1) **label/geometry mismatch**—sparse train gold (~39% success, long prompts, inverted model order) vs verified holdout (~7%, short prompts, Kimi≫Flash); Spearman(train, eval) = **−0.6** per `geometry.py` and `gate-fail-diagnosis.md`; (2) **feature representation ceiling**—~20-dim regex/token features cannot express query×model interaction; GBDT stumps collapse on short prompts; (3) **gating/threshold coupling**—retune on easy `tune.jsonl` landed medium **threshold=0.83** while calibration corpus diverges from promotion holdout; `rules_cost_delta < 0` is **structurally impossible** when rules ≡ Flash ≡ cheapest on 89/89 verified prompts.

**Winning strategy:** Keep Pioneer-shaped policy and features-only hop latency. **Do not promote** `bootstrap_partial` artifacts. Run a **geometry-gated gold phase** on verified-like difficulty (short prompts, full eligible matrix incl. K3 when budget allows) until Spearman(train, eval) **> 0**; add **offline-distilled query latent** (EmbedLLM/IRT-style bilinear head, no live 8B embed); **retune thresholds only on splits whose y distribution matches promotion holdout**; gate promotion on **Verified session gold + savings vs `most_expensive_eligible`**, with calibration as **BSS + equal-width ECE** until flywheel n≥1,500 for equal-mass ECE.

---

## How Fireworks Router Works (with citations)

### Product shape: binary redirect vs pass-through

FireRouter is a **managed routing service** on the Fireworks inference API. Request `model: "firerouter"` (or slash-delimited slugs like `firerouter/kimi-k3/glm-5p2-fast` for up to eight models). FireRouter **scores each turn** and picks one of two paths ([overview](https://docs.fireworks.ai/ecosystem/firerouter/overview)):

| Path | When | What runs | Billing |
| --- | --- | --- | --- |
| **Redirect** | Simple / low-complexity | Fireworks open model (default pair: GLM 5.2 Fast) | Fireworks `fw_...` key |
| **Pass-through** | Hard reasoning, judgment, long context | Closed-source model (default: Claude Opus 5) | Provider BYOK (`x-anthropic-api-key`) |

Default routing pair (subject to change; research preview): pass-through = **Claude Opus 5**, redirect = **GLM 5.2 Fast** (`glm-5p2-fast`) ([overview](https://docs.fireworks.ai/ecosystem/firerouter/overview)).

### Scoring and policy knobs

- **Per-request scoring:** “FireRouter **scores each request** to `firerouter`” and routes ([routing preferences](https://docs.fireworks.ai/ecosystem/firerouter/routing-preferences)).
- **Not multi-candidate P(success):** Policy is redirect **or** pass-through, not cheapest-above-bar over N catalog models with per-model probabilities.
- **Quality/savings dial:** `x-routing-preference` integer **1–5** (1 = max-intelligence → favor pass-through; 5 = max-savings → favor redirect). Default **3 = balanced** when header omitted ([routing preferences](https://docs.fireworks.ai/ecosystem/firerouter/routing-preferences)).
- **Conversation caching:** “FireRouter **caches routing decision within a conversation**” — preference changes may take a few turns ([routing preferences](https://docs.fireworks.ai/ecosystem/firerouter/routing-preferences)).
- **Multi-model slugs:** First model in slug is primary; FireRouter **ranks alternatives per request** among listed models ([overview](https://docs.fireworks.ai/ecosystem/firerouter/overview)).

### Features, labels, calibration, gates (documented absences)

| Topic | FireRouter documentation |
| --- | --- |
| **Features** | Not documented. Only “complexity” implied by redirect vs pass-through behavior. |
| **Labels** | Not documented. No success gold, session resolve, or no-escalate definition. |
| **Calibration** | **No** P(success), ECE, Brier, Platt/isotonic. Scoring method unpublished. |
| **Threshold tuning** | Preference levels 1–5 only; no threshold/max_regret grid. |
| **Shadow / promotion** | Research preview; no bounded gate or drift canary documented. |
| **BYOK** | Fireworks key required; Anthropic key required for default pass-through ([authentication](https://docs.fireworks.ai/ecosystem/firerouter/authentication)). |

### Architectural takeaway for aiand

FireRouter parity is **not** “fit per-model logistic on regex features.” It is closer to **HybridLLM / FrugalGPT cascade** or **Azure prompt routing** (quality band within a pool)—a **complexity classifier + cost-aware dispatch**, optionally with conversation stickiness. aiand’s Pioneer-shaped scorer is **strictly richer** than FireRouter’s default binary path; matching FireRouter **cost** may require a simpler cascade lane, while matching **Pioneer** requires fixing the scorer pipeline below.

---

## How Pioneer Router Works (with citations)

### Product contract (documented; internals not)

Pioneer Model Router is a **coding-only**, **low-latency** router that ([router concepts](https://docs.pioneer.ai/concepts/router)):

1. **Reads messages** and classifies **task complexity** (e.g. trivial lookup vs multi-file refactor).
2. Produces a **calibrated success probability for each candidate model** on this task (0–1 = predicted likelihood of succeeding).
3. Selects the **cheapest model** whose score clears configured **threshold** and **max_regret**.
4. **Falls back gracefully** if no candidate clears the bar or router is unreachable.

This is **the same policy shape** as aiand’s `pick_cheapest_above_bar` in `scorer.py:251–271`.

### Policy parameters (first-party)

| Knob | Default (high tier) | Meaning |
| --- | --- | --- |
| **threshold** | 0.20 | Minimum **calibrated** P(success) to be selectable |
| **max_regret** | 0.15 | Max gap in P(success) between chosen model and top survivor |

Effort presets (threshold, max_regret) — Pioneer documents five tiers; aiand ships four (`xhigh` out of scope):

| Tier | Threshold | Max regret |
| --- | --- | --- |
| low | 0.05 | 0.30 |
| medium | 0.10 | 0.20 |
| high | 0.20 | 0.15 |
| xhigh | 0.35 | 0.08 |
| max | 0.60 | 0.03 |

([router concepts](https://docs.pioneer.ai/concepts/router))

Observability: selected model, **confidence** (= winner P(success)), **rule** (`threshold` | `max_regret` | `fallback_declined`), savings vs most expensive candidate ([router concepts](https://docs.pioneer.ai/concepts/router)).

### Features, labels, calibration, gates (documented absences)

| Topic | Pioneer documentation |
| --- | --- |
| **Scorer architecture** | **Not documented** (no embed, no model size, no latency ms). |
| **Calibration method** | Claims “calibrated success probability”; **no** ECE, Brier, Platt, isotonic, or cal-set size. |
| **Training data** | “Trained on coding tasks” only. |
| **Success label** | Implied from “succeeding on this task”; no gateway vs session distinction. |
| **Promotion gate** | Dashboard monitoring at [agent.pioneer.ai/routers](https://agent.pioneer.ai/routers); no published numeric bars. |
| **Candidate pool** | Nemotron, DeepSeek V4 Flash, GLM 5.2, Claude Haiku/Sonnet/Opus 5, GPT-5.5/5.6; allowlist supported ([router concepts](https://docs.pioneer.ai/concepts/router)). |

### Architectural takeaway for aiand

Pioneer parity = **policy + observability + coding-only scope**, not copying undocumented internals. aiand already implements the documented contract (`router.py` eligible set, `scorer.py` pick, `app.py` headers). Gap is **scorer quality** (discriminative, calibrated P(success) that transfers to hard hops), not missing threshold/max_regret machinery.

---

## What We're Doing Wrong (code-evidence + external evidence)

### 1. Label geometry is inverted and distribution-shifted

**Evidence:**

- `fit_scorer` trains on sparse gold + silver regularizer on unobserved cells only (`train.py:895–943`). Silver fills with teacher P(success), not measured outcomes.
- K3 gets **silver-only prior** (`train.py:998–1006`); no K3 gold at $50 budget (plan invariant 4).
- `_gold_label` uses gateway proxy tiers (`verified > proxy > weak`); dump `resolved` is not y (`train.py:539–622`). Session gold (F2P/P2P) is promotion-only per `CONTEXT.md`.
- `geometry.py` defines hard-band y ≈ 0.07–0.22 vs dense-easy ≈ 0.39 (`geometry.py:22–25`).
- `gate-fail-diagnosis.md`: sparse vs verified model-rate **Spearman −0.6**; train ranks Pro≫Qwen≈Flash≫Kimi; holdout ranks **Kimi≫Flash=Qwen≫Pro(0)**.

**External:** No public dataset provides per-aiand-catalog no-escalate matrix (`.scratch/trained-router/research/bootstrap-datasets.md` §Snapshot). RouterBench ([arXiv:2403.12031](https://arxiv.org/abs/2403.12031)) has multi-model outcomes but wrong domain (single-shot QA/MBPP, not agent hops).

**Symptom:** Replay on `gold-verified.jsonl` (89 prompts): rank AUC **0.295** (logistic) / **0.261** (GBDT), Brier skill **negative**, dual ECE **~0.15–0.52** (`.scratch/scorer-pioneer-lift/task-06-or-07-report.md`, `gate-fail-diagnosis.md`).

### 2. Feature representation cannot express coding-agent routing signal

**Evidence:**

- `featurize()` uses intercept, tools, `log1p(tokens)`, token bins, complexity-bin one-hots, five regex cues — **phase deliberately omitted** from P(success) head (`scorer.py:91–113`).
- GBDT stumps split only on `log1p(tokens) ≥ ~4.8`; verified holdout tokens 13–62 → **all stumps take left leaf** → constant P(success) (`gate-fail-diagnosis.md` §Extra finding).
- GBDT lift **worsened** all metrics vs logistic (same report).

**External:** Shnitzer et al. ([arXiv:2309.15789](https://arxiv.org/abs/2309.15789)) use **embedding + per-model binary classifier**. EmbedLLM ([arXiv:2410.02223](https://arxiv.org/abs/2410.02223)) and IRT-Router ([arXiv:2506.01048](https://arxiv.org/abs/2506.01048)) require query×model interaction. HybridLLM’s 36ms DeBERTa router ([arXiv:2404.14618](https://arxiv.org/abs/2404.14618)) shows transformer-scale features — excluded from live hop but sets an upper bound on expressivity.

### 3. Calibration passes in-cal, fails on holdout (and equal-mass is honest)

**Evidence:**

- Pioneer plan F4: BSS **0.404 PASS**, equal-width ECE **0.013 PASS**, equal-mass ECE **0.034 FAIL** (bar 0.03) — `bootstrap_partial` shortfall (`.omo/plans/pioneer-capacity.md` F4).
- Isotonic on dense cal n≈2,400 (`train.py:976–981`); cal mean y ~39% vs verified ~7% (`gate-fail-diagnosis.md` H1).
- Selected mean P ≈ 0.60 vs mean y ≈ 0.08 on verified holdout.

**External:** Nixon et al. ([arXiv:1904.01685](https://arxiv.org/abs/1904.01685)) — equal-mass ECE more sensitive at low n. UCCI ([arXiv:2605.18796](https://arxiv.org/abs/2605.18796)) — “calibrate first, threshold second” on held-out cal; Opportunity Is Not Realizability ([arXiv:2608.08265](https://arxiv.org/abs/2608.08265)) — poorly calibrated cheap models poison confidence-gated routing (Table 16: TinyLlama ECE 0.273).

### 4. Threshold retune optimizes on the wrong split and compensates for bad scores

**Evidence:**

- `trained_effort` in `config/models.yaml:16–21`: medium **threshold=0.83**, max **threshold=1.00** vs Pioneer ship defaults 0.10/0.60 (`scorer.py:21–26`).
- `run_retune` grid-searches (t, r) on tune split minimizing cost subject to resolve ≥ rules − 1pp (`train.py:1133–1330`).
- Tune split was **anchors-only** with `not_spec_floors` deviation (pioneer-capacity plan task 14).
- Flash P(success) never below 0.60 on verified; threshold admits all survivors → always-cheapest (`gate-fail-diagnosis.md` H2).

### 5. Promotion gate includes structurally unreachable bars

**Evidence:**

- `rules_cost_delta < 0` required; on verified holdout rules picks **Flash on 89/89** and Flash is global cheapest → delta **0.0** (`gate-fail-diagnosis.md` H3).
- `tests/test_quality_routing.py` passes with **injected raw p_success** bypassing calibration — behavior matrix validates policy, not fitted artifact.
- Rank AUC floor 0.65 on n=89 with inverted train geometry: ceiling ~0.60 without verified leak (`gate-fail-diagnosis.md` §Root cause).

### 6. What is actually working

- Routing policy implementation matches Pioneer docs: eligible set (`router.py:234–290`), premium floor, `pick_cheapest_above_bar` (`scorer.py:251–271`), shadow/trained paths (`scorer.py:355–402`).
- Calibration **machinery** (Platt/isotonic auto-select, metrics module, drift canary) is spec-complete per pioneer-capacity plan Phase A.
- BSS > 0 on dense cal proves the pipeline can produce **some** calibrated signal — it does not **transfer**.

---

## What Won't Work

| Approach | Why it fails at aiand budget/scale |
| --- | --- |
| **More silver / teacher-only labels** | Teacher P(success) ≠ measured catalog outcomes; silver regularizer on unobserved cells cannot fix inverted Spearman when gold marginals disagree with holdout. |
| **GBDT / deeper trees on current features** | Empirically **worse** on verified holdout; stumps collapse to length splits that do not fire on short promotion prompts. |
| **Live 8B embed on hop** | Qwen3-Embedding-8B ([HF card](https://huggingface.co/Qwen/Qwen3-Embedding-8B)) cannot meet ~10ms in-process; violates spec serve hop. |
| **Chat-LLM-as-router** (RouteLLM causal 8B) | ~24ms+ inferred; violates no-chat-on-hop; RouteLLM ([arXiv:2406.18665](https://arxiv.org/abs/2406.18665)). |
| **FrugalGPT / AutoMix cascade** | Post-generation scoring; live hop includes chat models ([arXiv:2305.05176](https://arxiv.org/abs/2305.05176), [arXiv:2310.12963](https://arxiv.org/abs/2310.12963)). |
| **Train on SWE-bench Verified / Terminal-Bench** | Eval-only / canary; contamination or explicit do-not-train canary (Terminal-Bench). |
| **RouterBench / RouteLLM weights as coding router** | Wrong task shape (single-shot QA, pairwise prefs); no agent phases or no-escalate labels. |
| **Lower ECE bar to pass bootstrap_partial** | Hides miscalibration on selection-conditioned hops; does not improve quality or cost vs rules. |
| **Promote because bounded Lite n=30 passed** | Harness-proxy `resolved` ≠ Verified gate; plan labels `bounded_check_only`. |
| **Impute missing gold cells as 0** | Spec forbids; plan invariant 7. |
| **Relax premium floor for K3** | Locked behavior; task 7 premium-floor-aware matrix. |
| **Temperature scaling across independent per-model logits** | Does not fix wrong ranking among candidates (Guo et al. [ICML 2017](https://proceedings.mlr.press/v70/guo17a.html)); binary P(success) needs Platt/isotonic per head. |
| **Fine medium-threshold “middle” cost overlay** | Dense unpaid grid: no gate∧`rcd≤0` with succ closer to ship 0.112 than overlay 0.090; BSS fails t≈0.141–0.145 (`.scratch/scorer-pioneer-lift/fine-cost-frontier-2026-08-20.md`). |
| **Cascade soft-threshold as FireRouter** | Ship knobs → 0 cheap redirects; soft in-memory t unlocks redirects as artifact quirk, not FireRouter product (`.scratch/scorer-pioneer-lift/cascade-knob-sweep-2026-08-20.md`). Keep `cascade_lane.enabled: false`. |
| **gym_alt / smith order-mix + offline winner-mix preflight** | Seed-16 class-quota and gym-alt-seed2 winner-mix projections passed unpaid then paid geometry failed (seed2: 32/32 all-fail). Do not blind-pay those recipes. |
| **Hash-teacher bilinear distill jointly beating serve** | Cost-win distill fails P-spread+ECE; gate-pass ld18 keeps ship `rcd`. XOR under unpaid knobs (`.scratch/scorer-pioneer-lift/distill-gate-recovery-2026-08-20.md`). |
| **gym-alt-seed1 merge logistic refit as serve** | Combined geometry passes; replay P-spread regresses below 0.10. |

---

## GitHub Repos & Blogs

| Repo / URL | Why it matters |
| --- | --- |
| [lm-sys/RouteLLM](https://github.com/lm-sys/RouteLLM) | Production MF/BERT/causal routers; throughput tables; preference-threshold routing. Apache-2.0. |
| [withmartian/routerbench](https://github.com/withmartian/routerbench) | **405k+ multi-model outcomes**; KNN/MLP baseline code; defines predictive routing evaluation. |
| [Mercidaiha/IRT-Router](https://github.com/Mercidaiha/IRT-Router) | ACL'25 MIRT/NIRT; explicit P(success) logistic; training data format for query×model cells. |
| [RouteWorks/RouterArena](https://github.com/RouteWorks/RouterArena) | Router latency benchmark (~14ms MIRT-BERT); eval-only 8,400 queries. |
| [fw-ai/fireconnect](https://github.com/fw-ai/fireconnect) | FireRouter harness integration; routing preference wiring. |
| [SWE-bench/SWE-smith](https://github.com/SWE-bench/SWE-smith) | Largest official SWE-agent trajectory bootstrap; tool split for proxy labels. |
| [SWE-Gym/SWE-Gym](https://github.com/SWE-Gym/SWE-Gym) | Executable envs + OpenHands SFT/verifier trajectories. |
| [ShishirPatil/gorilla (BFCL)](https://github.com/ShishirPatil/gorilla) | Tool-JSON validity gold for (a)-type labels. |
| [ulab-uiuc/LLMRouter](https://github.com/ulab-uiuc/LLMRouter) | Unified router taxonomy (embedding, MF, GNN, cascade) — [arXiv:2608.06867](https://arxiv.org/html/2608.06867v1). |

**Primary blogs (owner-first-party, used sparingly):**

| URL | Note |
| --- | --- |
| [LMSYS RouteLLM blog](https://www.lmsys.org/blog/2024-07-01-routellm/) | RouteLLM launch; points to paper/GitHub — not used for calibration claims. |
| [Martian RouterBench post](https://withmartian.com/post/introducing-routerbench) | Dataset scale announcement; cite paper/HF for numbers. |

**Do not treat as evidence:** Pioneer/FireRouter internals blog posts, DeepWiki summaries, third-party “how Pioneer works” articles.

---

## Subagent Debate

### Advocate A — Data/label hypothesis

**Thesis:** Failure is fundamentally **wrong y at wrong scale**: partial easy proxy-labeled matrix vs hard session-shaped holdout.

**Strongest points:**

1. **Spearman −0.6** between sparse-train and verified model rates — labels teach anti-correlated model ordering (`gate-fail-diagnosis.md`, `geometry.py:70–79`).
2. Calibration **passes on dense cal, collapses on verified** — covariate + label shift, not broken pick logic.
3. Artifact honestly labeled `bootstrap_partial`, `k3_prior: silver_only`, `not_spec_floors` — system designed to fail closed until dense measured cells exist.

**Proposed fix:** ~1–2k verified-like prompts × full eligible set (~8–12k gold cells), y in hard band; K3 dense n≥300 before K3 claims; $150–300 incremental gold or flywheel to n≥300 session tasks.

**Weaknesses conceded:** `rules_cost_delta < 0` not fixable by labels alone when rules ≡ cheapest; proxy-vs-session y gap may persist without session-aligned gold.

### Advocate B — Architecture hypothesis

**Thesis:** **~20-dim regex/token features** cannot represent query-conditional per-model success; GBDT worsening proves representation ceiling.

**Strongest points:**

1. GBDT lift degraded every metric (AUC 0.261, Brier skill −3.8) — more capacity on same features hurt.
2. **100% stumps on `log1p(tokens)`** thresholds that never fire on verified (0/89 long prompts).
3. Retune to **0.83–1.00** = optimizer rejecting non-discriminative scores, not successful tuning.

**Proposed fix:** Rec B-lite — frozen model factors + tiny query MLP (EmbedLLM/IRT-style); offline distillation from Qwen3/MiniLM embeddings; reintroduce **phase family** into query trunk; keep hop <10ms.

**Weaknesses conceded:** Without hard gold, better architecture may not fix Spearman; Pioneer internals unknown.

### Advocate C — Evaluation/gating hypothesis

**Thesis:** Failures are **promotion/gating**, not routing logic; matrix tests pass with fixture p_success.

**Strongest points:**

1. **F4:** equal-mass ECE failed by **0.004** on same rows where BSS and equal-width passed — noise at bootstrap n.
2. **Replay gate impossible:** trained ≡ rules ≡ cheapest → `rules_cost_delta = 0`; AUC floor unreachable without leak.
3. **Test vs artifact divergence:** six behavior tests pass; fitted scorer fails calibration + discrimination on verified.

**Proposed fix:** Tiered gates — shadow (behavior), bounded (Lite, report-only ECE), Verified promotion (session gold, cost vs baseline); waive equal-mass ECE until n≥1,500; never retune on `not_spec_floors` splits; block retune when cal vs holdout base rate diverges >10pp.

**Weaknesses conceded:** Easing bars without fixing scores does not create quality; high threshold reflects real overconfidence.

### Synthesis & Winning Strategy

**Weight of evidence:** All three advocates are **partially correct**; the failure is **multi-causal** with a clear ordering:

```
1. Labels/geometry (A) — binding until Spearman(train, eval) > 0
2. Features/architecture (B) — binding for query-conditional ranking even after some gold fixes
3. Gating/evaluation (C) — binding for operator decision-making; several bars are ill-posed today
```

**A alone** cannot fix cost_delta when rules ≡ cheapest. **B alone** cannot fix inverted model marginals from easy proxy y. **C alone** would promote a miscalibrated router if bars are lowered without (A)+(B).

**Winning composite strategy (Pioneer parity, FireRouter-class savings where rules ≠ cheapest):**

| Phase | Action | Exit criterion |
| --- | --- | --- |
| **0 — Hold shadow** | No `TRAINED_PATH=trained` on `bootstrap_partial` | Already enforced (plan F7) |
| **1 — Geometry lock** | `python -m aiand_router.geometry` before every fit | `kill_spearman` false; y in hard band; holdout-like order |
| **2 — Hard gold** | Verified-like pool: short tokens, full eligible matrix, session-aligned y where harness exists | Spearman > 0; sparse refit; logistic default (no GBDT until rho > 0) |
| **3 — Scorer v2** | Distilled bilinear/IRT head: gateway features + phase + frozen model factors; optional offline embed ablation → distill | Replay rank AUC ≥ 0.65 on frozen verified **after** phase 2; P-spread ≥ 0.10 |
| **4 — Calibrate on matched corpus** | Dense cal from **same difficulty band** as promotion; isotonic only when n_cal > 1000 **and** base rates within 10pp of holdout | BSS > 0; equal-width ECE ≤ 0.03; equal-mass reported, gated only at n ≥ 1,500 |
| **5 — Retune on honest split** | Production retune holdout or tune split with **every eligible model** per query; bootstrap/session resolve y | Medium (t, r) satisfies resolve ≥ rules − 1pp; thresholds remain Pioneer-scale (0.05–0.60), not 0.83+ |
| **6 — Promotion** | SWE-bench Verified n=500 session gold; cost vs `most_expensive_eligible`; shadow ≥100 hops | Quality ≥ rules − 1pp; savings measured; calibration on flywheel window |

**FireRouter lesson:** Offer optional **binary cascade lane** (cheap open vs premium pass-through) for users who do not need full catalog P(success) — but **do not replace** Pioneer-shaped scorer; it is aiand’s differentiator.

**Pioneer lesson:** Ship **confidence + rule + savings vs expensive eligible** observability (already in spec); do not block on equal-mass ECE at bootstrap n competitors never publish.

**Mix1 status (2026-08-20, unpaid):** Bilinear probe lost to logistic on frozen verified replay (AUC 0.635 / BSS<0 / always-Flash vs logistic AUC 0.754 / BSS>0 / ECE_w 0.007). Replay cost bar is now savings vs `most_expensive_eligible`; logistic `replay_gate_pass=true` on n=89 with `path=shadow` / `not_spec_floors` — **not Pioneer parity**, not a live flip. Silver-regularized Mix1 logistic collapsed. Serve `data/scorer-hard-logistic.json` until bilinear beats it.

---

## Remaining blockers (live numbers, 2026-08-20 unpaid continuation)

Not Pioneer parity. Not FireRouter parity. `TRAINED_PATH` stays shadow.

1. **Retune n floor:** Mix1-like holdout is **172 rows / 43 prompts** (`data/gold-sparse-hard-mix1-retune.jsonl` = 12 Mix1 prompts + 31 Mix2-disjoint). CLI `train retune` **refused** (`need >= 300`). Ship knobs kept: medium **0.10 / 0.20**. Train slice `data/gold-sparse-hard-mix1-train.jsonl` (28 prompts, 112 rows) still `geometry_pass=true` vs verified (Spearman **1.0**, y **0.170**). No second geometry-passing gold file. Do not retune on `tune.jsonl`.

2. **Session gold / Lite:** Unpaid Lite fixture n=**30**, harness-proxy resolve **20/30 (66.7%)**, path-independent — **cannot** measure quality vs rules. Spec floor n≥300. Verdict **`bounded_check_only`**. No live Lite HTTP (credits).

3. **Verified replay (logistic Mix1, n=89):** `replay_gate_pass=true`; trained success **0.112** vs rules **0.022**; AUC **0.754**; BSS **0.00063**; ECE_w **0.0069**; ECE_m **0.143** waived (n<150); `savings_vs_most_expensive` **0.000899**; `rules_cost_delta` **+0.000687** (trained costlier than rules — not savings). Disagreement **1.0**.

4. **Bilinear:** Mix1-only still loses. Unpaid distill on Mix1-train∪gym-alt-seed1 (`scorer-hard-bilinear-distill48-gymalt.json`) clears rcd and beats BSS/success but fails P-spread+ECE_w — still do not serve.

5. **Silver+Mix1:** `data/scorer-hard-logistic-mix1.json` collapsed — do not serve.

6. **K3:** silver-only prior; no K3 gold; premium floor locked below `effort=max`.

7. **Conversation stickiness:** present behind existing `x-session-id` / `session_id` / `prompt-cache-key` (`X-Router-Conversation-Sticky` + `conversation_sticky`; tests expanded 2026-08-20). Gaps: process-local only, still re-scores every turn, no preference dial / delayed migration — see `.scratch/scorer-pioneer-lift/firerouter-stickiness-2026-08-20.md`. Not a FireRouter quality match.

8. **Promotion:** Verified n=500 session gold still required. Equal-mass ECE gated only at n≥150 selected hops. Do not set `TRAINED_PATH=trained`.

---

## Concrete Next Steps for aiand-router

1. **Unpaid gym_alt path (done 2026-08-20):** SWE-Gym tasks → flashlight/expected pool via `python -m aiand_router.pool ingest --profile gym_alt` and `train pool --gym-tasks …`. Artifacts: `data/pool-hard-gym-alt-n40.jsonl`, ranking doc `.scratch/scorer-pioneer-lift/unpaid-next-path-2026-08-20.md`. Smith-family paid expansion stays blocked.

2. **Hard-y gold probe on gym_alt (paid, opt-in only):** Label `data/pool-hard-gym-alt-n40.jsonl` with strict y; kill if Spearman ≤ 0 or y outside hard band. Do **not** re-run smith order-conservative / kimi-targeted recipes.

3. **Verified session gold (2026-08-20):** Docker + `SWE_EVAL_CMD` unpaid gold-patch probe **works** (`django-11099` → `resolved: true`). Live flashlight emits/extracts unified diffs + enriched context (FAIL_TO_PASS, guessed target paths) but **still fails `git apply`** without file bytes — ceiling documented in `.scratch/scorer-pioneer-lift/docker-swe-eval-status-2026-08-20.md`. Next unpaid: shallow `docker cp` / sparse checkout of `likely_target_files` into edit prompts (never gold patch). Do not treat n=1 smokes as promotion evidence.

4. **Revert serve artifact to logistic** until Spearman > 0; stop serving length-stump GBDT on shadow (`docs/runbook-production.md:61`). *(Already on `data/scorer-hard-logistic.json`.)*

5. **Implement Rec B-lite head:** frozen catalog model factors + 32–128d query MLP — only after a second geometry-passing batch or clear logistic plateau with transfer.

6. **Fix retune split discipline:** Do not apply thresholds from `not_spec_floors` tune.jsonl to production; require cal/holdout base-rate match; reset `trained_effort` toward Pioneer offsets once scorer discriminates.

7. **Repair promotion gate semantics:** Measure cost vs **`most_expensive_eligible`** for savings; use `rules_cost_delta` only where rules ≠ cheapest; add `bounded_check_only` for Lite; defer rank AUC gate until train/holdout geometry aligned.

8. **K3 onboarding path:** Dense gold n≥300 including K3 before claiming max-effort K3 routing (plan task 19d); until then silver-only prior is shadow-only honest behavior.

9. **Flywheel contract:** Ship JSONL to aiand infra per runbook; drift canary trips retrain when production BSS/ECE/escalate miss — closes equal-mass ECE at scale.

---

## Sources

### Official product docs

- FireRouter overview: https://docs.fireworks.ai/ecosystem/firerouter/overview
- FireRouter routing preferences: https://docs.fireworks.ai/ecosystem/firerouter/routing-preferences
- FireRouter authentication: https://docs.fireworks.ai/ecosystem/firerouter/authentication
- Pioneer Model Router: https://docs.pioneer.ai/concepts/router
- Azure Model Router how-it-works: https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-router-how-it-works

### Papers (routing + calibration)

- Shnitzer et al., LLM routing with benchmark datasets: https://arxiv.org/abs/2309.15789
- Hu et al., RouterBench: https://arxiv.org/abs/2403.12031
- Ong et al., RouteLLM: https://arxiv.org/abs/2406.18665
- Ding et al., HybridLLM: https://arxiv.org/abs/2404.14618
- Zhuang et al., EmbedLLM: https://arxiv.org/abs/2410.02223
- Song et al., IRT-Router (ACL 2025): https://arxiv.org/abs/2506.01048
- Kotte, UCCI cascade routing: https://arxiv.org/abs/2605.18796
- Shihab et al., Opportunity Is Not Realizability: https://arxiv.org/abs/2608.08265
- Guo et al., calibration / temperature scaling: https://proceedings.mlr.press/v70/guo17a.html
- Nixon et al., adaptive ECE: https://arxiv.org/abs/1904.01685
- LLMRouter survey: https://arxiv.org/html/2608.06867v1
- RouterArena: https://arxiv.org/abs/2510.00202

### Codebase (aiand-router)

- Scorer featurize / pick: `src/aiand_router/scorer.py:62–271`
- Eligible set / premium floor: `src/aiand_router/router.py:234–290`
- Fit / silver / K3 prior: `src/aiand_router/train.py:539–622`, `895–1024`
- Retune grid: `src/aiand_router/train.py:1133–1330`
- Replay gate bars: `src/aiand_router/replay_report.py:20–28`, `184+`
- Geometry lock: `src/aiand_router/geometry.py:19–79`
- Behavior matrix tests: `tests/test_quality_routing.py:1–317`
- Retuned thresholds: `config/models.yaml:16–21`
- Gate diagnosis: `.scratch/scorer-pioneer-lift/gate-fail-diagnosis.md`
- Pioneer capacity plan F4/F7: `.omo/plans/pioneer-capacity.md:191–195`

### Prior internal research (for continuity)

- Bootstrap datasets: `.scratch/trained-router/research/bootstrap-datasets.md`
- Calibration gate research: `.scratch/trained-router/research/calibration.md`
- Scorer architectures: `.scratch/trained-router/research/scorer-architectures.md`
- Product spec: `.scratch/trained-router/spec.md`
