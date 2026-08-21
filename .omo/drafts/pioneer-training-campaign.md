# Draft — pioneer-training-campaign

## State

- intent: clear
- review_required: false (CLEAR route; high-accuracy review will be OFFERED at handoff, not auto-run)
- status: awaiting-approval
- team_mode: UNAVAILABLE (no team_* tools in session). Degraded adversarial roster authorized: metis + momus + oracle via native task tool. User informed how to enable full roster.

## Request (verbatim intent)

Full plan for a training campaign that: (1) uses ONLY the ai& provider, (2) spends in <=$15 tranches with a right/wrong checkpoint after each to save cost, (3) leverages lm-sys/RouteLLM methodology + Arize fireworks-cost-benchmark methodology, (4) may extend this repo or create new code where needed, (5) after training completes, wraps execution in a Cursor `/goal`-style long-lived objective. Budget cap ~$200 credits.

## Decisions adopted (defaults announced in brief)

- D1: EXTEND this repo (`src/aiand_router/`), no new repo. Rationale: pipeline, collision guards, gates, tests all exist; new repo duplicates them.
- D2: `/goal` interpretation = operational wrapper for the worker session (objective text + per-tranche evidence), zero new code.
- D3: Hard cap $200; tranches <=$15 enforced via BUDGET_LIMIT_USD env per run (code default $15 untouched).
- D4: Embedding-dependent RouteLLM pieces (MF router, SW ranking) deferred behind the EXISTING embed-ablation gate (keep iff Brier strictly better AND ECE not worse); free borrows (APGR curve, decontamination pattern, noise regularization) land now.
- D5 (added post-approval): cache-aware cost estimates for multi-turn ranking — Fireworks' cache-hit-rate lesson applied via ai&'s own cached-in catalog prices; ranking-only, billing stays list-price; plan Phase A task 4.

## Research receipts

- Librarian ses_fdd60a277ffeodxO3AqWyi4Q3C: RouteLLM @0b64fda layout verified. Borrow now: evals/evaluate.py APGR+AUC cost-quality curve; evals/find_contaminated.py embedding-decontamination pattern; matrix_factorization/train_matrix_factorization.py Gaussian-noise augmentation trick; calibrate_threshold.py quantile split. Defer: MF/SW/BERT router heads (embedding dep). Not borrowable: N-model eligible set, calibration (ours stronger), shadow/gate (ours has it).
- Oracle probe (.scratch/oracle_ceiling_probe.py): current ceiling 46.2% without K3 gold; K3 = 0 rows.
- data/retrain_report.md: last fit n_gold=40 -> BSS -0.065 FAIL. docs/runbook-production.md: gate bars + Lite-300 proxy path. docs/prototype-to-pioneer-proposal-2026-08-21.md: staged $50/$200 plan this campaign restructures into $15 tranches.

## Tranche skeleton (to be expanded into todos after approval)

- T0 $0 code-only pre-flight: strata manifest assertion + spend accounting clarification + RouteLLM APGR port
- T1..T6 $15 each: teacher -> sparse 2k -> dense/cal 600 -> dense/cal 1000+isotonic -> K3 slice A -> K3 slice B (n>=300)
- T7+: gate runs (Lite-300 proxy then Verified-500) + retrain iterations from remaining cap
- Checkpoint after EVERY tranche: named go/no-go metric; fail = stop and diagnose, never roll into next tranche

## Approval gate

Presented brief: YES (this turn). Waiting for explicit user okay to write .omo/plans/pioneer-training-campaign.md.
