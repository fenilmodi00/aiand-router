# Calibration for router P(success)

Primary sources only. Findings for ticket `.scratch/trained-router/issues/03-calibration-for-router-p-success.md`. Do not invent Pioneer internals or savings percentages.

## Question

What does **calibrated P(success)** require in the literature — reliability diagrams, ECE, Brier, Platt scaling vs isotonic vs temperature scaling?

What production or academic **routers** actually document calibration (not merely a 0–1 score)? Pioneer claims “calibrated success probability” but does not describe the method — record the absence.

What is the **minimum eval** a promotion gate should demand so “beats rules” cannot pass a cheaper miscalibrated scorer? Preference: non-inferior quality (escalate rate and/or task success), strictly lower cost, **and** trustworthy calibration. No invented savings %.

---

## 1. What calibrated P(success) requires

### 1.1 Definition

A predicted probability is calibrated when predicted rates match observed rates. For binary success \(Y\in\{0,1\}\) and prediction \(\hat{p}\), perfect calibration is \(\mathbb{P}(Y=1\mid\hat{p}=p)=p\) for all \(p\in[0,1]\). ([Naeini, Cooper & Hauskrecht, AAAI 2015](https://doi.org/10.1609/aaai.v29i1.9602); [Guo, Pleiss, Sun & Weinberger, ICML 2017](https://proceedings.mlr.press/v70/guo17a.html), eq. 1.)

Guo’s operational reading: given 100 predictions each with confidence 0.8, about 80 should be correct. ([Guo et al. 2017](https://proceedings.mlr.press/v70/guo17a.html), §2.)

That is exactly what a Pioneer-style **threshold + max_regret** policy needs: a floor of 0.20 is only a quality bar if \(\hat{p}=0.20\) means ~20% observed success, not an arbitrary 0–1 score. ([Guo et al. 2017](https://proceedings.mlr.press/v70/guo17a.html), §1–2; Pioneer threshold semantics below, §2.1.)

Accuracy, ROC-AUC, or “confidence” without this frequency match is **not** calibration. Niculescu-Mizil & Caruana: “in many applications it is important to predict well calibrated probabilities; good accuracy or area under the ROC curve are not sufficient.” ([Niculescu-Mizil & Caruana, ICML 2005](https://www.cs.cornell.edu/~alexn/papers/calibration.icml05.crc.rev3.pdf), §1.)

Zadrozny & Elkan: when the decision threshold is example-dependent (cost-sensitive routing is this), ranking alone is not enough; you need the true conditional probability so \(\hat{p}\) can be compared to a numeric threshold. ([Zadrozny & Elkan, ICML 2001](https://cseweb.ucsd.edu/~elkan/calibrated.pdf), §1.)

Kumar, Liang & Ma: calibration alone is also not enough — a constant \(\hat{p}=\) base rate is perfectly calibrated and useless. Minimize mean-squared error (Brier) **subject to** a calibration budget. ([Kumar, Liang & Ma, NeurIPS 2019](https://arxiv.org/abs/1909.10155), §2.1.)

### 1.2 Reliability diagrams

On real data the true \(P(Y=1\mid\hat{p})\) is unknown. Visualize calibration with a **reliability diagram**: discretize \(\hat{p}\) into bins; plot mean predicted value vs observed positive fraction. Perfect calibration lies on the diagonal. ([DeGroot & Fienberg, *The Statistician* 32:12–22, 1983](https://doi.org/10.2307/2987588), as used by [Niculescu-Mizil & Caruana 2005](https://www.cs.cornell.edu/~alexn/papers/calibration.icml05.crc.rev3.pdf) §4 and [Naeini et al. 2015](https://pmc.ncbi.nlm.nih.gov/articles/PMC4410090/).)

Niculescu-Mizil & Caruana use **ten equal-width bins** \([0,0.1),\ldots,[0.9,1]\). ([Niculescu-Mizil & Caruana 2005](https://www.cs.cornell.edu/~alexn/papers/calibration.icml05.crc.rev3.pdf), §4.)

Guo et al. use \(M\) equal-width bins \(I_m=((m-1)/M, m/M]\), with per-bin accuracy \(\mathrm{acc}(B_m)\) and confidence \(\mathrm{conf}(B_m)\). A perfectly calibrated model has \(\mathrm{acc}(B_m)=\mathrm{conf}(B_m)\) for all \(m\). Reliability diagrams **do not show bin mass**, so they cannot alone say how many samples are calibrated. ([Guo et al. 2017](https://proceedings.mlr.press/v70/guo17a.html), §2.)

Naeini et al. call the same plot a reliability / calibration curve and treat closeness to the identity as the qualitative criterion. ([Naeini et al. 2015](https://pmc.ncbi.nlm.nih.gov/articles/PMC4410090/), Introduction + Figure 1.)

### 1.3 ECE and MCE

**Expected Calibration Error (ECE)** and **Maximum Calibration Error (MCE)** were introduced as scalar summaries of the reliability diagram. Predictions are sorted and partitioned into \(K\) bins (\(K=10\) in their experiments). ([Naeini et al. 2015](https://doi.org/10.1609/aaai.v29i1.9602); formula in [PMC4410090](https://pmc.ncbi.nlm.nih.gov/articles/PMC4410090/):)

\[
\mathrm{ECE}=\sum_{i=1}^{K} P(i)\cdot|o_i-e_i|,\qquad
\mathrm{MCE}=\max_{i}|o_i-e_i|
\]

where \(o_i\) is the observed positive fraction in bin \(i\), \(e_i\) is the mean predicted probability in that bin, and \(P(i)\) is the fraction of instances in the bin. Lower is better. ([Naeini et al. 2015](https://pmc.ncbi.nlm.nih.gov/articles/PMC4410090/), “Calibration Measures”.)

Guo et al. rewrite ECE with \(M\) equal-width bins as

\[
\mathrm{ECE}=\sum_{m=1}^{M}\frac{|B_m|}{n}\bigl|\mathrm{acc}(B_m)-\mathrm{conf}(B_m)\bigr|
\]

and MCE as the max absolute gap. They use ECE as the primary metric; Table 1 reports ECE with **\(M=15\)**. They recommend MCE when worst-case deviation matters (high-risk). ([Guo et al. 2017](https://proceedings.mlr.press/v70/guo17a.html), §2 eqs. 3–5, Table 1.)

After temperature scaling, Guo’s vision/NLP models often drop from ECE of several percent (sometimes 10–16% on CIFAR-100) to about **1–2%**. Uncalibrated “already good” datasets sit near ECE \(\le 1\%\). ([Guo et al. 2017](https://proceedings.mlr.press/v70/guo17a.html), Table 1 + §5.) This is a literature range, not a router promotion ceiling.

### 1.4 Brier score

Glenn W. Brier introduced a proper score for probability forecasts: mean squared difference between forecast probabilities and the observed one-hot outcome. For \(N\) forecasts and \(r\) classes,

\[
S=\frac{1}{N}\sum_{j=1}^{N}\sum_{i=1}^{r}(F_{ij}-E_{ij})^{2}
\]

where \(F_{ij}\) is the forecast probability for class \(i\) on case \(j\) and \(E_{ij}\in\{0,1\}\) indicates the realized class. Smaller is better. Binary range is \([0,2]\) in Brier’s original two-class form (precipitation vs not). ([Brier, *Monthly Weather Review* 78(1):1–3, 1950](https://doi.org/10.1175/1520-0493(1950)078<0001:VOFEIT>2.0.CO;2); formula quoted in NOAA WBTM ER-7, which cites Brier 1950.)

In ML binary calibration the same object is usually written \(\mathrm{MSE}=\mathbb{E}[(\hat{p}-Y)^{2}]\) (range \([0,1]\) for one class). ([Kumar et al. 2019](https://arxiv.org/abs/1909.10155), Def. 2.2; [Niculescu-Mizil & Caruana 2005](https://www.cs.cornell.edu/~alexn/papers/calibration.icml05.crc.rev3.pdf) report squared error and log-loss.)

Murphy decomposes the Brier / probability score into **uncertainty** (Brier of the sample base rate — irreducible), **reliability** (calibration: forecast frequencies vs observed frequencies), and **resolution** (ability to sort cases into groups with different outcome rates). ([Murphy, *J. Appl. Meteor.* 12:595–600, 1973](https://doi.org/10.1175/1520-0450(1973)012<0595:ANVPOT>2.0.CO;2).)

Kumar et al. note MSE = squared calibration error + a “sharpness” term: \(\mathrm{MSE}=0\) implies perfect calibration, but \(\mathrm{CE}=0\) does not imply low MSE. ([Kumar et al. 2019](https://arxiv.org/abs/1909.10155), §2.1.)

**Implication for a router gate:** ECE/reliability can pass a dummy that always emits the empirical success rate. Brier vs that climatological predictor is the resolution check. Both are required.

Negative log-likelihood / cross-entropy is the other standard proper score; Guo use NLL to fit temperature and as a secondary metric. ([Guo et al. 2017](https://proceedings.mlr.press/v70/guo17a.html), §2 eq. 6, §4.)

### 1.5 Post-hoc maps: Platt vs isotonic vs temperature scaling

All three are **post-processing** on a held-out set. Fitting on the same data used to train the scorer biases the map (perfect train ranking → a 0/1 step). Use an **independent calibration set**. ([Niculescu-Mizil & Caruana 2005](https://www.cs.cornell.edu/~alexn/papers/calibration.icml05.crc.rev3.pdf), §2.1; [Guo et al. 2017](https://proceedings.mlr.press/v70/guo17a.html), §4: train / validation / test from the same distribution; validation may be the hyperparameter set.)

| Method | Form | Assumptions | Data appetite | Changes ranking / argmax? |
| --- | --- | --- | --- | --- |
| **Platt scaling** | \(P(y=1\mid f)=1/(1+\exp(Af+B))\); \(A,B\) by max likelihood | Distortion is roughly **sigmoid** | Two parameters; works when calibration data is **scarce** | Monotonic in \(f\) (binary) |
| **Isotonic regression** | Any **monotone** piecewise-constant map (PAV / Barlow et al.) | Only monotonicity | More flexible → **overfits** when data is scarce | Monotonic; piecewise constant |
| **Temperature scaling** | Multiclass: \(\mathrm{softmax}(z/T)\), one scalar \(T>0\) fit by NLL | Miscalibration is approximately **a single temperature** on logits | One parameter; fastest | **Does not change** \(\arg\max\) (class prediction / accuracy unchanged) |
| **Histogram binning** | Equal-width or equal-mass bins; output empirical positive rate per bin | None beyond bin choice | Needs enough counts per bin | Can change predicted class in multiclass one-vs-all |

Sources: Platt sigmoid — ([Platt 1999, “Probabilistic Outputs for Support Vector Machines…”](https://users.cs.fiu.edu/~sjha/class2024/1999PlattScaling.pdf)); isotonic / PAV — ([Zadrozny & Elkan, KDD 2002](https://doi.org/10.1145/775047.775151), as described in [Niculescu-Mizil & Caruana 2005](https://www.cs.cornell.edu/~alexn/papers/calibration.icml05.crc.rev3.pdf) §2.2 Table 1); histogram binning — ([Zadrozny & Elkan, ICML 2001](https://cseweb.ucsd.edu/~elkan/calibrated.pdf); [Guo et al. 2017](https://proceedings.mlr.press/v70/guo17a.html) §4.1); temperature scaling — ([Guo et al. 2017](https://proceedings.mlr.press/v70/guo17a.html) §4.2 eq. 9).

**Platt vs isotonic (binary, the P(success) setting).** Niculescu-Mizil & Caruana: Platt is most effective when the reliability curve is sigmoid-shaped (boosting, SVMs). Isotonic can correct **any monotonic** distortion, at the cost of overfitting. Learning curves on 8 problems, calibration set size 32→8192: **below about 200–1000 cases, Platt beats isotonic**; at **≥1000**, isotonic is as good as or better. They trained models on 4000 cases and calibrated on independent **1000**. ([Niculescu-Mizil & Caruana 2005](https://www.cs.cornell.edu/~alexn/papers/calibration.icml05.crc.rev3.pdf), Abstract, §2, §4, §5, §7.)

Naeini et al.: Platt’s two-parameter sigmoid rarely matches the true distortion; histogram binning needs a chosen \(B\) and fixed edges; isotonic’s monotonicity is often violated in practice. They propose BBQ (Bayesian averaging over equal-frequency binnings) and show it statistically superior on ECE/MCE across 30 UCI/LibSVM sets. ([Naeini et al. 2015](https://pmc.ncbi.nlm.nih.gov/articles/PMC4410090/), Introduction + Empirical Results.)

**Temperature scaling (multiclass logits).** Guo et al.: modern nets are miscalibrated (depth, width, BatchNorm, weak weight decay). Temperature scaling — “a single-parameter variant of Platt Scaling” — was often the **best** ECE method on vision tasks, comparable on NLP, and does not change accuracy because \(T\) does not change \(\arg\max\). Vector/matrix scaling overfit when \(K\) is large. Binning methods improve ECE but usually lose to temperature scaling and can change class predictions. ([Guo et al. 2017](https://proceedings.mlr.press/v70/guo17a.html), Abstract, §4.2–§6, Figure 4, Table 1.)

**Router mapping.** Per-candidate binary P(success) is **binary calibration** → Platt or isotonic (or histogram / BBQ), not temperature scaling, unless the scorer is a **softmax over candidates**. Temperature scaling cannot fix a wrong ranking among candidates (argmax unchanged). It *can* change who clears a numeric threshold if you apply a shared \(T\) to independent logits, but that is still not a per-model success probability unless those logits were already \(P(\text{success}\mid\text{model})\).

UCCI (cascade routing, 2026) maps token-margin uncertainty to error probability with **isotonic regression**, then thresholds the calibrated score; they state threshold policies on calibrated error probability are cost-optimal under explicit assumptions, with isotonic ECE rate \(O(n^{-1/3})\). ([Kotte, arXiv:2605.18796](https://arxiv.org/abs/2605.18796), Abstract, §4–§5.)

### 1.6 ECE is not enough as a lone number

Nixon et al.: ECE has pathologies — fixed equal-width bins ignore density, typically only the **max-class** probability is scored, L1 vs L2 matters, and **rank-ordering of recalibration methods flips** with metric choices. They recommend **adaptive (equal-mass) binning** (ACE) and, when class count is high, thresholded ACE. ([Nixon, Dusenberry, Zhang, Jerfel & Tran, CVPRW 2019 / arXiv:1904.01685](https://arxiv.org/abs/1904.01685).)

Kumar et al.: plugin ECE **underestimates** true calibration error; using more bins uncovers higher error; continuous maps (Platt, temperature, isotonic) have **true CE that is unmeasurable** with finite bins (Example 3.2: binned CE can be 0 while true CE \(\ge 0.49\)). Histogram binning yields a measurable CE but needs \(O(B/\varepsilon^2)\) samples. They propose scaling-binning and a **debiased** CE estimator (sample complexity \(\sim\sqrt{B}\) instead of \(B\)). ([Kumar et al. 2019](https://arxiv.org/abs/1909.10155), Abstract, §1, §3 Example 3.2, §5.)

**Gate consequence:** report Brier (no binning) **and** ECE at two bin schemes (equal-width \(M=10\) as in Naeini/Niculescu-Mizil **and** equal-mass / ACE as in Nixon), plus the reliability diagram. Do not promote on a single ECE with one \(M\).

---

## 2. What routers actually document calibration

“Document calibration” here means: official docs or a paper that (a) treats the score as a **probability of correctness/success**, and (b) names a **method and/or metric** (reliability diagram, ECE, Brier, Platt, isotonic, temperature, histogram). A 0–1 score, “confidence,” or “predicted quality” without that is **not** documented calibration.

### 2.1 Pioneer Model Router — claim, no method

Pioneer’s router page states the router “produces a **calibrated success probability** for each model on this specific task,” scores models 0–1 as “predicted likelihood of succeeding,” uses that as **threshold**, and logs “the router’s calibrated success probability for the selected model.” Effort presets are numeric thresholds × max_regret (e.g. high: threshold 0.20, max_regret 0.15). ([https://docs.pioneer.ai/concepts/router.md](https://docs.pioneer.ai/concepts/router.md), fetched 2026-08-13.)

**Not documented** on that page (or elsewhere on the fetched router concept doc): ECE, Brier, reliability diagrams, Platt, isotonic, temperature scaling, histogram binning, calibration-set size, per-candidate vs selected-only evaluation, or any formula mapping logits → probability. Do **not** invent their internals. Record: **absence of method**.

### 2.2 FireRouter — no

FireRouter “scores each request independently” and chooses redirect (open model) vs pass-through (closed). No P(success), ECE, or calibration method. ([https://docs.fireworks.ai/ecosystem/firerouter/overview](https://docs.fireworks.ai/ecosystem/firerouter/overview), fetched 2026-08-13.)

### 2.3 Amazon Bedrock Intelligent Prompt Routing — predicted quality, not calibration metrics

Official userguide: the system “dynamically **predict[s] the response quality** of each model” and routes using `responseQualityDifference` vs a fallback. No ECE, Brier, reliability diagram, or post-hoc calibrator. Limitations: English-optimized; “can’t adjust routing decisions or responses based on application-specific performance data.” ([https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-routing.html](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-routing.html).)

### 2.4 Azure / Microsoft Foundry Model Router — quality bands, not ECE

Official concepts: a trained ML model “estimates which model in the pool delivers the best result.” Balanced mode: models within a “small quality range (for example, 1% to 2% compared with the highest-quality model)”; Cost mode: “5% to 6%.” How-it-works: “recalibrates its routing decisions” when the **model subset** changes — policy re-optimization, not probability calibration. No ECE, Brier, reliability diagram, Platt/isotonic/temperature. Eval how-to recommends LLM-as-judge quality + cost `1 - (router_cost / baseline_cost)` and “at least 100 prompts” for statistically reliable quality results; that is quality/cost eval, not calibration. ([https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-router](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-router); [how-it-works](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-router-how-it-works); [how-to](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/model-router).)

### 2.5 NVIDIA NemoClaw Model Router — predicted quality + tolerance, not ECE

Official NemoClaw docs: `tolerance` selects “the lowest-cost model whose **predicted quality** stays within the configured threshold.” `0.20` = “up to 20 percentage points below the best result.” Checkpoint + encoder named; no ECE, Brier, reliability, or calibrator. ([https://docs.nvidia.com/nemoclaw/user-guide/hermes/inference/hosted-inference/set-up-model-router](https://docs.nvidia.com/nemoclaw/user-guide/hermes/inference/hosted-inference/set-up-model-router).)

(NVIDIA’s *developer blog* on NeMo Switchyard describes residual-stream MLPs predicting “likelihood that each LLM will successfully complete the task”; that is a blog, not used here as a calibration method citation.)

### 2.6 OpenRouter Auto Router — market spend, not P(success)

OpenRouter Auto Router ranks by aggregate community **share of spend** for a classified task type, then applies `cost_tier`. Not a calibrated success probability. ([https://openrouter.ai/docs/guides/routing/routers/auto-router](https://openrouter.ai/docs/guides/routing/routers/auto-router), search snippet 2026-08-13; full fetch timed out — claim is only the documented spend-share mechanism.)

### 2.7 Martian Gateway — quality_constraint number, not calibration

Martian Aider integration exposes `routing_constraint.quality_constraint.numeric_value` (e.g. 0.1) as a “how strict the quality requirement is” dial. API reference does not define that number as a calibrated P(success) or name ECE/Platt/isotonic. ([https://docs.withmartian.com/integrations/aider](https://docs.withmartian.com/integrations/aider); [API reference](https://docs.withmartian.com/api-reference).)

### 2.8 Academic routers that emit 0–1 scores without calibration eval

**RouteLLM** (Ong et al., ICLR 2025): learns \(P_\theta(\mathrm{wins}\mid q)\) that a strong model beats a weak one (matrix factorization, BERT, causal LLM); threshold \(\alpha\) on that probability. Evaluation is quality–cost tradeoff vs preference labels, **not** ECE/Brier/reliability. ([RouteLLM PDF](https://proceedings.iclr.cc/paper_files/paper/2025/file/5503a7c69d48a2f86fc00b3dc09de686-Paper-Conference.pdf), §3–4.)

**RouterBench** (Hu et al., arXiv:2403.12031): 405k inference outcomes; KNN/MLP routers vs oracle; cascading “judge” score \(g\in[0,1]\) + threshold. No ECE/Brier/reliability protocol. ([https://arxiv.org/html/2403.12031](https://arxiv.org/html/2403.12031).)

UCCI’s related-work reading: **FrugalGPT** uses learned confidence thresholds **without imposing calibration** on the routing score; HybridLLM and RouteLLM likewise optimize quality–cost, not ECE. ([Kotte, arXiv:2605.18796](https://arxiv.org/abs/2605.18796), §2.)

### 2.9 Academic work that *does* document calibration for routing

**UCCI** — cascade (small → large) router: isotonic regression from token-margin uncertainty → error probability; threshold chosen by constrained cost minimization on a held-out validation set; test ECE **0.12 → 0.03** on 75k production NER queries (split 30% cal / 20% val / 50% test). Explicitly “calibrate first, threshold second.” ([Kotte, arXiv:2605.18796](https://arxiv.org/abs/2605.18796), Abstract, §4–§6.) This is a **cascade**, not a multi-candidate cheapest-above-threshold coding router, but it is the clearest published “router + ECE” primary source.

**Opportunity Is Not Realizability** (arXiv:2608.08265) — multi-LLM routing diagnostics: “Calibration quality is measured with **Brier score, log loss, expected calibration error with fixed bins, and adaptive-bin reliability plots**.” They also report per-model AUROC/AUPRC/Brier/ECE and show a confidence-gated router **cannot** use poorly calibrated cheap models as rescues (e.g. TinyLlama ECE 0.273 / 0.299). Temperature-scaled max-confidence is a post-inference selector, not a pre-answer router. Splits: 50/50 calibration vs test; thresholds only on calibration data. ([https://arxiv.org/html/2608.08265](https://arxiv.org/html/2608.08265), methods + Table 7 + Table 16.)

No production coding-router vendor doc reviewed here (Pioneer, FireRouter, Bedrock, Azure, NemoClaw, OpenRouter, Martian) publishes ECE, Brier, or a named calibrator.

---

## 3. Minimum promotion-gate calibration check

Standing preference (ticket 08, not invented here): non-inferior quality (escalate rate and/or task success), **strictly lower cost**, trustworthy calibration. **No invented savings %.**

### 3.1 Failure modes a gate must block

1. **Overconfident cheap scorer.** Inflated \(\hat{p}\) on cheap models clears threshold/max_regret; observed success and escalate rate look worse than rules. Classic miscalibration (Guo reliability gap; Naeini ECE). Pioneer-shaped policies are exactly Zadrozny–Elkan cost-sensitive thresholding: the threshold is only valid if \(\hat{p}\) is a true probability. ([Zadrozny & Elkan 2001](https://cseweb.ucsd.edu/~elkan/calibrated.pdf), §1; [Guo et al. 2017](https://proceedings.mlr.press/v70/guo17a.html), §2.)

2. **Constant base-rate dummy.** \(\hat{p}\equiv\bar{y}\) is perfectly calibrated (ECE ≈ 0) and has Brier = Murphy **uncertainty** \(\bar{y}(1-\bar{y})\), with **zero resolution**. It cannot route. ([Murphy 1973](https://doi.org/10.1175/1520-0450(1973)012<0595:ANVPOT>2.0.CO;2); [Kumar et al. 2019](https://arxiv.org/abs/1909.10155), §2.1 dog/cat example.)

3. **Train-set / threshold leakage.** Calibrator or operating threshold fit on the same labels used to claim “beats rules.” ([Niculescu-Mizil & Caruana 2005](https://www.cs.cornell.edu/~alexn/papers/calibration.icml05.crc.rev3.pdf), §2.1; UCCI 30/20/50 split; Opportunity 50/50 + thresholds only on calibration.)

4. **Aggregate-only ECE.** Cheap candidates the policy actually picks can be badly calibrated while overall ECE looks fine. Opportunity Is Not Realizability: high-ECE weak models poison confidence-gated routing. ([arXiv:2608.08265](https://arxiv.org/html/2608.08265), Table 16.)

5. **Single-binning ECE theater.** Nixon: method ranking flips with binning; Kumar: more bins → higher measured error; plugin ECE underestimates true CE. ([Nixon et al. 2019](https://arxiv.org/abs/1904.01685); [Kumar et al. 2019](https://arxiv.org/abs/1909.10155).)

### 3.2 Recommended minimum check (metric + how to compute)

Do this on a **frozen promotion split** that was not used to train the scorer, fit the calibrator, or choose threshold / max_regret.

**Labels.** Binary \(y_i\in\{0,1\}\): flashlight / harness **task success** when it exists (promotion gold); else per-request no-escalate (+ valid tools if tools were requested). Same definition for rules and trained. (Product language: CONTEXT.md “Success label”; not re-derived here.)

**Prediction under test.** \(\hat{p}_i\) = trained router’s P(success) for the **model the policy actually selected** (selection-conditioned). Optionally also report per-candidate ECE on models that receive ≥ some mass of selections (Opportunity per-model table).

**Artifact A — reliability diagram.** \(M=10\) equal-width bins as in Niculescu-Mizil / Naeini. Plot \(\mathrm{conf}(B_m)\) vs \(\mathrm{acc}(B_m)\). Require the diagram as a promotion artifact, not a slide optional. Pay special attention to bins covering the live effort thresholds (Pioneer-documented 0.05–0.60). ([Niculescu-Mizil & Caruana 2005](https://www.cs.cornell.edu/~alexn/papers/calibration.icml05.crc.rev3.pdf), §4; [Naeini et al. 2015](https://pmc.ncbi.nlm.nih.gov/articles/PMC4410090/); Pioneer [router.md](https://docs.pioneer.ai/concepts/router.md) threshold table.)

**Artifact B — ECE (two binnings) + MCE.**

- Equal-width ECE, \(M=10\) (Naeini default) **and** \(M=15\) (Guo Table 1), using Guo’s formula \(\sum_m (|B_m|/n)\,|\mathrm{acc}-\mathrm{conf}|\).
- Equal-mass / adaptive ECE (Nixon ACE), same \(M\), because threshold policies pile mass near the operating point.
- MCE = max bin gap (Naeini; Guo high-risk).

Do not freeze a numeric ECE ceiling in this research note (ticket 08 grilling). Literature working range after post-hoc calibration is **a few percentage points** (Guo often ≤2% after temperature scaling; UCCI reports 0.03 on NER). Issue 08 should pick a ceiling against a **declared baseline** (rules router if it emits a comparable 0–1, else climatology), not an invented universal constant.

**Artifact C — Brier + Brier skill (blocks the dummy).**

\[
\mathrm{BS}=\frac{1}{n}\sum_{i=1}^{n}(\hat{p}_i-y_i)^2,\qquad
\mathrm{BS}_{\mathrm{clim}}=\bar{y}(1-\bar{y}),\qquad
\mathrm{BSS}=1-\mathrm{BS}/\mathrm{BS}_{\mathrm{clim}}
\]

Require \(\mathrm{BSS}>0\) (strictly better than always predicting the promotion-split base rate). This is Murphy resolution under a reliability constraint: you cannot pass with ECE≈0 and no discrimination. ([Brier 1950](https://doi.org/10.1175/1520-0493(1950)078<0001:VOFEIT>2.0.CO;2); [Murphy 1973](https://doi.org/10.1175/1520-0450(1973)012<0595:ANVPOT>2.0.CO;2); [Kumar et al. 2019](https://arxiv.org/abs/1909.10155) Def. 2.2.)

Optional but cheap: log-loss \(\frac{1}{n}\sum_i[-\,y_i\log\hat{p}_i-(1-y_i)\log(1-\hat{p}_i)]\), the NLL Guo use. ([Guo et al. 2017](https://proceedings.mlr.press/v70/guo17a.html), eq. 6.)

**Calibrator fit (not the gate metric, but required hygiene).** Independent calibration split ≠ train ≠ promotion. If \(n_{\mathrm{cal}}\lt\sim 1000\), prefer **Platt** (2 params) or temperature (1 param, only if multiclass logits); if \(n_{\mathrm{cal}}\ge\sim 1000\) and the reliability curve is not a clean sigmoid, **isotonic** is justified. ([Niculescu-Mizil & Caruana 2005](https://www.cs.cornell.edu/~alexn/papers/calibration.icml05.crc.rev3.pdf), §5; [Guo et al. 2017](https://proceedings.mlr.press/v70/guo17a.html), §4.) UCCI used 22,500 calibration examples for isotonic on NER; that is one workload, not a minimum we must copy. ([Kotte 2026](https://arxiv.org/abs/2605.18796), §6.1.)

**Together with quality and cost (not calibration-only).** Non-inferior escalate rate and/or task success vs rules; **strictly lower** measured \(/\text{token}\) or \$ cost on the same promotion split. Do not publish a savings percentage without that measurement. Azure’s published eval pattern is the same shape: quality (judge or task) + cost ratio, ≥100 workload prompts for quality signal — still insufficient alone for calibration. ([Azure model-router how-to](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/model-router).)

### 3.3 One-line gate

**Promote only if, on a held-out promotion split: (1) task success and/or escalate rate non-inferior to rules, (2) cost strictly lower, (3) selection-conditioned Brier skill \(>0\), (4) equal-width \(M=10\) ECE and equal-mass ECE are at or below the pre-declared ceiling vs baseline, (5) reliability diagram attached.** That combination is what the cited literature uses to stop both a cheaper miscalibrated scorer and a calibrated constant.

---

## Sources

- Brier, G. W. (1950). Verification of forecasts expressed in terms of probability. *Monthly Weather Review* 78(1), 1–3. https://doi.org/10.1175/1520-0493(1950)078\<0001:VOFEIT\>2.0.CO;2
- Murphy, A. H. (1973). A new vector partition of the probability score. *Journal of Applied Meteorology* 12, 595–600. https://doi.org/10.1175/1520-0450(1973)012\<0595:ANVPOT\>2.0.CO;2
- DeGroot, M. H., & Fienberg, S. E. (1983). The comparison and evaluation of forecasters. *The Statistician* 32, 12–22. https://doi.org/10.2307/2987588
- Platt, J. (1999). Probabilistic outputs for support vector machines and comparisons to regularized likelihood methods. In *Advances in Large Margin Classifiers*. https://users.cs.fiu.edu/~sjha/class2024/1999PlattScaling.pdf
- Zadrozny, B., & Elkan, C. (2001). Obtaining calibrated probability estimates from decision trees and naive Bayesian classifiers. ICML. https://cseweb.ucsd.edu/~elkan/calibrated.pdf
- Zadrozny, B., & Elkan, C. (2002). Transforming classifier scores into accurate multiclass probability estimates. KDD. https://doi.org/10.1145/775047.775151
- Niculescu-Mizil, A., & Caruana, R. (2005). Predicting good probabilities with supervised learning. ICML. https://www.cs.cornell.edu/~alexn/papers/calibration.icml05.crc.rev3.pdf
- Naeini, M. P., Cooper, G. F., & Hauskrecht, M. (2015). Obtaining well calibrated probabilities using Bayesian binning. AAAI. https://doi.org/10.1609/aaai.v29i1.9602 https://pmc.ncbi.nlm.nih.gov/articles/PMC4410090/
- Guo, C., Pleiss, G., Sun, Y., & Weinberger, K. Q. (2017). On calibration of modern neural networks. ICML / PMLR 70. https://proceedings.mlr.press/v70/guo17a.html
- Nixon, J., Dusenberry, M. W., Zhang, L., Jerfel, G., & Tran, D. (2019). Measuring calibration in deep learning. arXiv:1904.01685. https://arxiv.org/abs/1904.01685
- Kumar, A., Liang, P., & Ma, T. (2019). Verified uncertainty calibration. NeurIPS. https://arxiv.org/abs/1909.10155
- Hu, Q., et al. (2024). RouterBench. arXiv:2403.12031. https://arxiv.org/html/2403.12031
- Ong, I., et al. (2025). RouteLLM. ICLR. https://proceedings.iclr.cc/paper_files/paper/2025/file/5503a7c69d48a2f86fc00b3dc09de686-Paper-Conference.pdf
- Kotte, V. (2026). UCCI: Calibrated uncertainty for cost-optimal LLM cascade routing. arXiv:2605.18796. https://arxiv.org/abs/2605.18796
- Opportunity Is Not Realizability (2026). arXiv:2608.08265. https://arxiv.org/html/2608.08265
- Pioneer Model Router. https://docs.pioneer.ai/concepts/router.md (fetched 2026-08-13)
- FireRouter overview. https://docs.fireworks.ai/ecosystem/firerouter/overview (fetched 2026-08-13)
- Amazon Bedrock intelligent prompt routing. https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-routing.html
- Azure / Foundry model router concepts, how-it-works, how-to. https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-router https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-router-how-it-works https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/model-router
- NVIDIA NemoClaw model router. https://docs.nvidia.com/nemoclaw/user-guide/hermes/inference/hosted-inference/set-up-model-router
- OpenRouter Auto Router. https://openrouter.ai/docs/guides/routing/routers/auto-router
- Martian Aider integration / API. https://docs.withmartian.com/integrations/aider https://docs.withmartian.com/api-reference
