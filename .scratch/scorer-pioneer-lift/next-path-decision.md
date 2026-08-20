# Next path after failed holdout gate

**Status:** decision (no code this turn; no `TRAINED_PATH` flip; no fake pass)  
**Date:** 2026-08-14  
**Evidence:** `gate-fail-diagnosis.md`, `gate-fail-hypotheses.md`, `operator-replay-run.md`, `task-06-or-07-report.md`, `spec.md`, `progress.md`, `CONTEXT.md`

## 1. Goal restated

Optimize for a **real trained router in shadow**, not a green `replay_gate_pass` on the current file.

A real router here means:

1. **Calibrated P(success)** — selected-hop P matches observed success on *hard* work (Brier skill > 0, dual ECE small). Dense-cal y ≈ 39% vs verified y ≈ 7% is the current mismatch (H1).
2. **Ranking that transfers** — on a query, model order should look like verified holdout (Kimi ≫ Flash = Qwen ≫ Pro(0)), not like sparse/GBDT (Pro ≫ Qwen ≈ Flash ≫ Kimi). Sparse↔verified model-rate Spearman is **−0.6**.
3. **Cheapest-above-bar that can beat rules on quality and cost** — disagreement that is not “always Flash,” quality at least rules − 1 pp, and *somewhere* trained list-price < rules.

The operator gate on `data/gold-verified.jsonl` is a **local** bar (`spec.md` Testing Decisions), not SWE-bench Verified promotion. Passing it by lowering bars, leaking the holdout into fit, or flipping `TRAINED_PATH` while the scorer still inverts ranking would be vanity. Serve stays **shadow**. Artifact stays `not_spec_floors`. Issue **07 is not taken**.

Hard facts this path must not wish away:

- Constant-rate AUC ceilings **without** verified-as-fit: sparse ≈ 0.40, dense ≈ 0.47, inverted-sparse ≈ 0.60 — all **< 0.65**. Only leaking verified *marginals* reaches ≈ 0.68 (forbidden as fit gold). Query-conditional GBDT cannot invent transfer when train order is anti-correlated with holdout (`gate-fail-diagnosis.md` root cause 1).
- Logistic that **did** leak verified rows via `gold-all` still only hit AUC **0.295** (`operator-replay-run.md` run 1). Row leak ≠ ranking.
- On 89/89 verified prompts, rules pick = Flash = global cheapest eligible → **`rules_cost_delta < 0` is impossible** (H3). Oracle success is 0.146 vs rules 0.079, but oracle *cost is higher* than rules (0.000205 vs 0.000202). Even a perfect cheapest-success policy cannot undercut always-Flash on this holdout.
- GBDT length stumps (`log1p(tokens)` ≳ 4.8) are dead on verified tokens 13–62; every stump takes the left leaf → intercept-only P, then easy-cal Platt → P ≈ 0.47–0.65, trained ≡ always-cheapest (H2 + extra finding).

## 2. Options

### Option A — Verified-like train/cal gold + dual shadow eval (chosen)

**What.** Rebuild **train and cal** success gold so difficulty and *model ranking* look like the frozen verified holdout, without using that holdout (or Lite / Terminal-Bench) as fit y. Keep `data/gold-verified.jsonl` eval-only. Restore **logistic** for shadow until trees have non-length features that fire on short prompts. Add a **second**, disjoint bootstrap holdout where rules sometimes pick non-Flash, so cost_delta is a real test rather than a structural zero.

Concretely (in-spec machinery already shipped): issue 01 pool (SWE-smith `tool` traj primary, BFCL ≤ 15%, collision-filter vs `--eval`); issue 02 y (verified metadata `expected` / JSON-schema / `tests_passed` overrides weak proxies; dump `resolved` is never y); issue 03 dense cal disjoint from sparse; Rec A logistic + cal-only Platt. New gold must carry **hard checks** on train queries (flashlight / expected / schema on *bootstrap* rows — not Verified bench as a train dump). Stop the recipe if a small probe still shows Spearman(train rates, verified rates) < 0.

**Why it might help.** Diagnosis “what would unblock” is exactly this: larger success-gold n with verified-like difficulty **in train/cal**, plus (for cost) a holdout where rules sometimes picks non-cheapest. Quality headroom on verified is real (oracle 14.6% vs 7.9%) if Flash P can fall below medium θ=0.10 on rows where Kimi is the survivor. Hard cal (~holdout-like 0.08–0.22 y, not 0.39) is what H1 says Brier/ECE need.

**Cost / risk.** Live gold spend (credits are sufficient per spec; still cache-first, opt-in `AIAND_TRAIN`). Probe can fail: smith trajs are *long* (sparse 333/400 have `log1p(tokens)>4.8`) while verified is *short and hard* — matching y-rate without matching length/ranking still will not transfer. Flashlight-on-bootstrap is allowed as a labeling harness (`spec.md` Out of Scope: Flashlight is not a product); attaching checks to pool rows is new data work.

**Clears AUC?** Possible **only if** train model order correlates with verified (Spearman ≫ 0) *and* some query-conditional signal exists. Intercepts alone max out ~0.60–0.68. Not guaranteed on the first probe.

**Clears `cost_delta < 0` on current verified file?** **No.** Nothing honest does (H3). Cost is judged on the new bootstrap slice.

**Out of Scope?** No, if Verified/Lite/TB stay out of fit, Rec B/live embed stay closed, dump `resolved` unused, K3 ungolded, no auto-flip.

### Option B — Rewrite gate bars only

**What.** e.g. `rules_cost_delta ≤ 0` when rules≡cheapest; lower AUC floor for n=89; call the logistic a pass.

**Why it might help.** H3 is a gate-definition bug on *this* file. Waiving cost_delta there is honest reporting.

**Cost / risk.** Zero spend. Zero ranking. Spec still requires Brier skill > 0 and AUC ≥ 0.65 for “shadow looks like a real router.” Current GBDT Brier skill −3.80, logistic −0.317, AUC 0.26–0.30. A waiver does not make cheapest-above-bar pick Kimi when Flash fails.

**Clears AUC / cost_delta?** Only by changing the test. Does not clear them as performance.

**Out of Scope?** Not listed as forbidden, but it is **gate vanity**. Do not take as the path. A later *narrow* waiver (cost_delta when rules≡cheapest **and** quality/oracle bars hold) can be a reporting footnote after Option A, not a substitute.

### Option C — Serve/feature hygiene only (no new gold)

**What.** Restore `data/scorer-logistic.json` as the shadow artifact; drop silver from z; diversify GBDT stumps off `log1p(tokens)`; Platt `b` shift / temperature so selected P ≈ 0.08.

**Why it might help.** GBDT *worsened* Brier/ECE vs logistic (run 2 vs run 1). H1: Platt `b`→−2.1 → ECE ≈ 0.003. Length-stump collapse is a real serve bug on short prompts.

**Cost / risk.** Cheap. H1 also: skill stays ≈ 0 after the level fix (no discrimination). H4 already falsified (hint_bin vs predicted bin, AUC stays 0.261). H5: geometry, not silver/GBDT mechanics alone — logistic still AUC 0.295. Diagnosis: none of these clear AUC ≥ 0.65 **and** cost_delta < 0 on current holdout.

**Clears AUC?** No (ceiling ≤ ~0.60 without new labels). **Cost_delta?** No (H3).

**Out of Scope?** No. Treat as **hygiene inside Option A**, not a standalone path.

### Option D — More n of the same sparse-400 / dense-100 recipe

**What.** Spend more on the current pool and y (easy dense ~39%, inverted ranking), maybe skip GBDT this time.

**Why it might help.** Issue 06 allowed “larger n **or** GBDT”; we took GBDT because unused labeled gold was gone. More cells can shrink intercept variance.

**Cost / risk.** Spend buys a tighter estimate of the **wrong** ranking (Spearman −0.6). Same AUC ceilings. Same easy-cal Platt.

**Clears AUC / cost_delta?** No.

**Out of Scope?** No — just wasted credits.

### Option E — Forbidden shortcuts (leak holdout, Rec B, flip 07)

**What.** Fit on `gold-verified.jsonl` / Lite / TB; open Rec B or live embed; second model zoo; `TRAINED_PATH=trained` while `replay_gate_pass` is false; manufacture cost_delta by catalog price or rules edits.

**Why it might help.** Verified marginals as constants ≈ 0.68 AUC. Rec B might add text signal. Flip would “ship.”

**Cost / risk.** Spec Out of Scope: training on Verified/Lite/TB; Rec B as shipped hop; live embed; automatic/unearned `TRAINED_PATH=trained`; claiming production Verified promotion. Run 1 already leaked verified rows and still failed AUC and cost_delta. Inverted ranking in production would send hard work to Pro (holdout y = 0).

**Clears AUC?** Marginal leak of *rates* might scrape 0.65; row leak did not. **Cost_delta?** Still no on this holdout (H3), unless the catalog/rules are gamed.

**Out of Scope?** **Yes.** Reject.

## 3. Comparison

| Option | Ranking / AUC | Calibration | `cost_delta < 0` on verified 89 | Real router? | Scope | Spend |
|---|---|---|---|---|---|---|
| **A. Hard train/cal gold + dual eval** | Only path that can raise the transfer ceiling | Hard cal fixes H1 | No on that file; **yes possible** on a rules≠Flash slice | **Yes — this is the job** | In spec if eval dumps stay out of fit | Probe then scale |
| B. Bar rewrite only | Unchanged (0.26–0.30) | Unchanged | By definition change only | No | Vanity | None |
| C. Hygiene only | Unchanged ceiling | Level-only (skill ≈ 0) | No | Stops the GBDT bleed | In spec | None |
| D. More easy n | Same Spearman −0.6 | Same easy cal | No | No | In spec, wasteful | High |
| E. Leak / Rec B / flip 07 | Fake or out of scope | Fake | No unless gamed | Harmful if Pro-ranked | **Forbidden** | Don’t |

## 4. Chosen option

**Option A — Rebuild train/cal success gold to verified-like difficulty and ranking; keep verified eval-only; restore logistic; add a cost-meaningful bootstrap shadow slice.**

It is the only option that attacks both hard blockers as *performance* problems:

1. **AUC / ranking:** the ceiling is a **label geometry** problem (H5), not a missing GBDT. New fit gold must correlate with verified model order. Frozen `gold-verified.jsonl` stays unused for train, cal, and threshold-tune (`CONTEXT.md` eval-only dump; `spec.md` stories 27, 93).
2. **Cost:** `rules_cost_delta < 0` cannot be earned on a holdout where rules ≡ cheapest (H3) and even oracle costs more. A second shadow slice where phase bars / bins make rules pick off-Flash is how cheapest-above-bar can demonstrate savings vs rules. That is new **eval data**, not a quieter bar.
3. **Calibration:** Platt on dense-cal y ≈ 0.39 cannot be the production calibrator for y ≈ 0.07 (H1). Cal slice must be hard and disjoint.
4. **Serve:** current GBDT is a length-stump intercept machine on short prompts. Logistic is less broken (AUC 0.295 vs 0.261, Brier skill −0.317 vs −3.80). Shadow should not keep serving the worse artifact. GBDT is allowed again only if logistic still fails *after* labels transfer and trees split on more than `log1p(tokens)`.

Option B does not make P(success) true. Option C does not make ranking transfer. Option D spends on the anti-correlated recipe. Option E is out of scope and already empirically weak (run 1).

Success for A is **not** “gate green this week.” It is: (i) Spearman(train rates, verified rates) > 0 on a probe; (ii) logistic replay on frozen verified moves AUC/Brier/ECE in the right direction without holdout leak; (iii) a bootstrap slice exists where disagreement can be cheaper than rules without a quality drop. The numeric gate in issue 05 can be re-run after those exist — including a possible *documented* cost_delta waiver **only** on files where rules≡cheapest, never as the first move.

## 5. What not to do

- **Do not flip `TRAINED_PATH` or take issue 07.** Gate is red; `apply_replay_gate` must stay non-auto (`spec.md` story 12; issue 07 needs-info).
- **Do not train, calibrate, or threshold-tune on Verified / Lite / Terminal-Bench**, including `gold-verified.jsonl` as fit y. Eval-only (`spec.md` Out of Scope; `CONTEXT.md`).
- **Do not fake a pass** (lower AUC floor, `cost_delta ≤ 0` as the whole plan, catalog price edits, rules tweaks to stop picking Flash).
- **Do not open Rec B, live embed, or a second zoo.** Issue 06 already used the one Rec A lift; Rec B closed.
- **Do not scale the current sparse/dense recipe** until a hard-y probe beats Spearman −0.6.
- **Do not keep GBDT as the shadow artifact** while every stump is a long-token split that verified never hits.
- **Do not use dump teacher `resolved` as success gold.** Aiand candidate run + issue-02 y only.
- **Do not gold K3.** Unchanged.
- **Do not treat Option C Platt-shift as skill.** ECE can go to ~0 with Brier skill ~0 — a constant base-rate scorer, which the spec already rejects.

## 6. Next implementation slices (tracer bullets)

No code in this decision turn. If A is approved, four sequential probes — stop at the first fail:

1. **Geometry lock (no spend).** Print sparse vs dense vs verified: per-id success rates, Spearman, token/`log1p` histograms, y base rates. Point shadow at the logistic copy until Spearman(train, verified) > 0. Confirms H5/H1 on disk; stops serving the collapsed GBDT.

2. **Hard-y probe (small spend).** Sample a small smith-pool slice (issue 01), attach verified-style checks on those **train** rows (`expected` / schema / flashlight `tests_passed` — not the frozen 89), run sparse gold (issue 02). **Kill criterion:** Spearman vs frozen verified still < 0, or y-rate stays dense-easy (~0.39). **Pass criterion:** Spearman vs frozen verified > 0 with the same order as holdout y (Kimi > Flash = Qwen > Pro) and overall y closer to ~0.07–0.22 than dense-cal ~0.39.

3. **Scale + logistic refit (only if 2 passes).** Sparse train + disjoint dense **hard** cal; `fit` logistic (no `--gbdt`); Platt on hard cal only; silver still unobserved-only. Replay **frozen** `gold-verified.jsonl`. Expect movement on AUC / Brier skill / ECE / P that is not always-Flash. **Do not expect** `rules_cost_delta < 0` on that file.

4. **Cost-meaningful shadow slice.** Disjoint bootstrap holdout (not Verified) where rules ≠ Flash on a non-trivial fraction (hard/frontier × phase bars). Replay there for cost_delta and quality vs rules. Only after 3+4 look like a router should anyone reopen issue 05 bar language (narrow H3 waiver) or issue 07.

## 7. Issue 07 stance

**Still not taken. Not legitimate yet.**

Issue 07 is a **manual** `TRAINED_PATH=trained` after a **passing** operator replay. It does not claim production Verified n≥300 (`issues/07-operator-flip-to-trained.md`).

It becomes legitimate when **all** of the following hold:

1. Frozen verified (or a later eval-only corpus of the same kind) shows **transfer**: holdout rank AUC ≥ 0.65, Brier skill > 0, dual ECE ≤ 0.03, trained success ≥ rules − 1 pp, trained ≠ always-cheapest — **without** that corpus in fit/cal/retune.
2. **Cost is a real comparison:** either `rules_cost_delta < 0` on a holdout where rules sometimes pick non-cheapest, **or** an explicit operator waiver *only* for files where rules≡global cheapest (H3), with quality still non-inferior and moving toward oracle — not a silent bar drop.
3. Artifact may still be `not_spec_floors`; production Verified promotion remains a later staffed bar.
4. Flip stays **manual**. `apply_replay_gate` never auto-flips.

Until then: shadow, `not_spec_floors`, no 07.

## 8. Status after Mix1 pass and seeds 11–16 failures (2026-08-20)

**Option A partially succeeded, scale path blocked.**

| Milestone | Status |
| --- | --- |
| Mix1 hard-y probe | **Pass** — `data/gold-sparse-hard-mix1.jsonl`, geometry_pass=true, Spearman 0.949 |
| Hard-logistic shadow candidate | **Pass local replay** — `data/scorer-hard-logistic.json`, `replay_gate_pass=true`, still `not_spec_floors` |
| Seeds 11–16 blind top-ups | **All fail** standalone geometry (only Mix1 passes) |
| Seed-16 order-conservative | Preflight class fractions **pass** → paid geometry **fail** (y 0.047, 26/32 all-fail) |
| Class-quota preflight | **Disproven** as geometry predictor (seed-16 falsification) |
| Retune n≥300 | **Refused** — no geometry-passing concat path without Mix1 overlap or bad seeds |
| Smith-pool paid expansion | **Dead** until new label source or materially different sampler |

**Do not:** run more blind paid probes from order-conservative, kimi-only-targeted, winner-stratified, or mix1like pools; merge seed-15/16; flip `TRAINED_PATH=trained`; claim parity from `replay_gate_pass=true`.

**Honest unpaid next paths (2026-08-20):**

1. **Replay parity posture** (implemented) — `replay_report` stamps `local_replay_gate_pass`, `production_parity=false`, `parity_blockers` so shadow-local pass ≠ production parity.
2. **Mix1-only retune** — document refusal honestly (`train retune` needs n≥300; Mix1 has 160 cells).
3. **Lite/session-gold dry-run** — expand fixture runner offline; no HTTP without credits.
4. **Smith gold expansion** — blocked; document until new label source appears.

**Update (later 2026-08-20 unpaid):** Smith expansion remains blocked. Chosen replacement pool family is **SWE-Gym `gym_alt`** (see `unpaid-next-path-2026-08-20.md`). Verified `--ids-only` scaffold is secondary plumbing only.