# AIand Coding Router

Glossary for the coding-agent model router. Implementation lives elsewhere; this file is language only.

## Language

### Routing paths

**Rules router**:
The current selection policy: hard constraints, then a phase bar, then an effort pick (cheapest, Pioneer-style score, or strongest AA).
_Avoid_: the router (once both paths exist), heuristic router

**Trained router**:
A selection policy that emits a complexity bin, a calibrated P(success) per eligible candidate, and picks the cheapest model that clears threshold and max_regret.
_Avoid_: learned router, ML router, Pioneer clone

**Learned stub**:
The dark, untrained highest-AA module behind the same Decision interface.
_Avoid_: trained router, student, learned router (as if it were trained)

**Student**:
The tiny offline-trained hop head: complexity bin plus per-eligible P(success). At serve it is the **Scorer**.
_Avoid_: teacher, learned stub, trained router (the policy)

**Promotion gate**:
The explicit eval that must say the trained router beats the rules router on quality, cost, and calibration before trained may leave shadow.
_Avoid_: flipping learned on, A/B without a bar

### Scores and labels

**Calibrated P(success)**:
A 0–1 predicted chance that this candidate succeeds on this request, such that predicted rates match observed rates. Live **confidence** is this value for the selected model.
_Avoid_: AA index, Pioneer-style score, uncalibrated confidence

**Complexity bin**:
A query-only difficulty label: `trivial`, `standard`, `hard`, or `frontier`. Feature, reason_code, and train/eval stratum — not the pick.
_Avoid_: phase, Bloom level (live), empirical difficulty, complexity class

**Phase**:
A coding-agent step name (`plan`, `edit`, `debug`, …), from header or heuristics.
_Avoid_: complexity bin, task type, phase family (when you mean the alias)

**Phase family**:
The collapsed step used for phase bars and strata: `discover`, `plan`, `edit`, `tool`, `debug`, `summarize`. Raw phase aliases map into it.
_Avoid_: phase (the alias), complexity bin

**Success gold**:
The gateway-observable outcome after actually running a candidate: no escalate, and valid tools/JSON if required. Missing is unobserved, not failure.
_Avoid_: silver P(success), session gold, bootstrap resolve, teacher judgment, AA

**Gold matrix**:
The measured query × eligible-model table of success gold. A cell exists only if that candidate was actually run.
_Avoid_: silver P(success) table, teacher labels, catalog × query (when you mean eligible set)

**Dense gold slice**:
A held-out query set where every eligible model is run. Calibration, reliability, and new-model onboard — not the train corpus and not the threshold-tuning split.
_Avoid_: full matrix on all bootstrap dumps, 3×5 smoke, sparse gold, threshold-tuning split

**Threshold-tuning split**:
A held-out **bootstrap** query set, disjoint from train, the dense gold slice, and promotion, where every eligible model is run. Used only to fit medium threshold + max_regret at **v1**. Later refits use the production retune holdout.
_Avoid_: dense gold slice, sparse gold, promotion split, eval-only dump, production retune holdout, drift canary

**Sparse gold**:
Train queries where only the sparse-train anchors were run.
_Avoid_: dense gold slice, single-model gold

**Sparse-train anchors**:
Cheap + coding-mid + premium models always run on sparse-gold rows when eligible. Never a single model; not automatically the named savings baseline.
_Avoid_: full eligible set, K3-on-every-row, dense gold slice

**Stratum**:
A sampling cell: complexity bin × phase family × tools-present vs not.
_Avoid_: empirical difficulty, Bloom level, raw phase alias (as the stratum axis)

**Silver P(success)**:
A teacher’s query-only predicted probability per eligible model. Distillation prior on unobserved cells only — not calibration gold and not Zooter (response-RM distill).
_Avoid_: success gold, calibrated P(success) (until measured), Zooter

**Session gold**:
Harness or flashlight task outcome (`tests_passed` / patch / SWE resolve) on promotion-gate corpora or flashlight. Promotion-gate only — not the per-request training label and not bootstrap dump envs.
_Avoid_: success gold, silver P(success), bootstrap resolve

**Bootstrap resolve**:
Per-candidate test/harness outcome on an allowed bootstrap dump env (aiand completion vs F2P/P2P). Not the dump’s original teacher `resolved` bit.
_Avoid_: session gold, success gold, dump teacher resolved

**Production retune holdout**:
A held-out **flywheel** query set, disjoint from that retrain’s train and calibrator, where every eligible model is run. Used only to refit medium threshold + max_regret after a full retrain. Not the v1 bootstrap threshold-tuning split.
_Avoid_: threshold-tuning split, dense gold slice, drift canary, promotion split

**Shadow**:
Serving the rules router while logging what the trained router would have picked, with no live trained pick yet. Same JSONL row as the live hop (`path=shadow`).
_Avoid_: A/B, traffic canary (those send some live traffic to trained)

**Drift canary**:
A production monitor on serve hops: n≥300 or 7 days, whichever later. Trips a full retrain if escalate, BSS, or ECE miss the promotion-gate definitions. Never a train, cal, retune, or promotion-fit split.
_Avoid_: traffic canary, A/B, promotion gate, threshold-tuning split, production retune holdout

### Policy knobs

**Threshold**:
The minimum calibrated P(success) a survivor must clear to be pickable on the trained path.
_Avoid_: AA phase bar, Pioneer-style score cutoff, rules max regret

**Max regret**:
The maximum allowed gap in calibrated P(success) between the chosen model and the top survivor.
_Avoid_: rules max regret, Pioneer-style score gap, AA points

**Rules max regret**:
The maximum allowed Artificial Analysis index gap on the rules path (today 8 points). Not a probability.
_Avoid_: max regret, threshold

### Product

**Bootstrap dump**:
A public dataset ingested to parse traces and/or relabel tasks for the trained router. Not the flywheel and not an eval-only dump.
_Avoid_: eval-only dump, promotion-gate corpus, flywheel, flywheel log, 3×5 smoke

**Flywheel**:
Production serve data used to train later students: observed hop (+ escalate) plus a small explore. Missing cells stay unobserved, not failure.
_Avoid_: bootstrap dump, 3×5 smoke, eval-only dump

**Flywheel log**:
The append-only JSONL-compatible store on **aiand infra** for flywheel rows (same Decision contract as the live hop). This repo’s `data/requests.jsonl` is the prototype only.
_Avoid_: second shadow file, this checkout as production, bootstrap dump

**Eval-only dump**:
A public dataset forbidden from train, calibrator, and threshold/max_regret fit. Promotion-gate corpora, Terminal-Bench, and Multi-SWE-bench live here.
_Avoid_: bootstrap dump, traffic canary, hold-out row split (intra-dump)

**Proposal-grade spec**:
The artifact this effort is finding its way to: enough for the aiand team to staff, budget, and implement a production trained router, not a hosted multi-tenant control plane run from this repo.
_Avoid_: production deployment, hackathon demo spec

**Eligible set**:
The models that survive hard constraints (tools, context, budget, allow-list, premium floor, …) before any pick — rules or trained.
_Avoid_: candidate pool (when you mean post-constraint only), catalog (the full registry)

**Measured trio**:
The three catalog models in the demo/eval matrix: Qwen 3.6 27B, Kimi K2.7 Code, DeepSeek V4 Pro.
_Avoid_: eligible set, full catalog, teacher

**Teacher**:
An aiand-deployed chat model used offline to label complexity bins and silver P(success). It does not mint success gold and is not the live hop. Chosen by a catalog-relative policy, not one global id.
_Avoid_: student, scorer, live router, embedding model

**Cheap teacher**:
The first offline teacher in cheap-then-escalate: it labels every bootstrap row.
_Avoid_: fallback_model, live hop, Flash (unless the policy actually picks it)

**Escalate teacher**:
The stronger offline teacher that relabels a row when the cheap teacher is uncertain or the bin is `hard` / `frontier`.
_Avoid_: live escalate, success gold, Pro (unless the policy actually picks it)

**Scorer**:
The live trained-router student: features-only logistic or GBDT heads plus Platt/temperature. It emits a complexity bin and calibrated P(success) per eligible survivor. Not the pick.
_Avoid_: Rec A, Rec B, teacher, live embed, bilinear hop, feature model (as the whole router)

**Features-only**:
No embedding-model forward — the default training recipe, and this effort’s serve hop. A tiny feature→latent MLP still counts.
_Avoid_: Scorer (the hop student), Rec A, live embed, unembedded

**Training embed**:
An optional offline embedding model used only as extra student train features in an embed ablation. Prototype may call Nebius `Qwen/Qwen3-Embedding-8B` (prefer 0.6B or MRL ≤256-d). Not a production hard dependency and never on the serve hop.
_Avoid_: live embed, scorer, teacher, required embed

**Embed ablation**:
Same labels + cached training-embed vectors vs a features-only student. Keep vectors only if Brier is strictly better and ECE is not worse on held-out success gold; if they win, distill into the features-only hop.
_Avoid_: promotion gate (that is trained vs rules), live embed

**Live embed**:
An embedding-model forward on request text during the trained-router serve hop. This effort’s hop does not include one.
_Avoid_: training embed, scorer, MiniLM hop

### Cost

**Named savings baseline**:
The most expensive model still in this request’s eligible set (`most_expensive_eligible`), ranked by list-price unit cost. Every savings number is versus that model (id logged per request).
_Avoid_: always-K3, always-fallback, Opus, rules router

**Savings**:
Measured cost difference versus the named savings baseline. Never an invented percentage.
_Avoid_: savings % (unmeasured), rules cost delta

**Rules cost delta**:
Measured cost difference versus what the rules router would spend on the same request. Promotion gate and shadow only.
_Avoid_: savings

### Observability

**Path**:
Which policy served this hop: `rules`, `trained`, or `shadow`.
_Avoid_: A/B, mode (overloaded)

**Rule**:
Which trained-policy branch fired: `threshold`, `max_regret`, or `fallback_declined`.
_Avoid_: X-Router-Reason (prose), Pioneer score

**Reason codes**:
Short diagnostic tags on a Decision (`bin:…`, `pick:…`, `scorer_down`, …). Not the pick itself.
_Avoid_: prose reason blob
