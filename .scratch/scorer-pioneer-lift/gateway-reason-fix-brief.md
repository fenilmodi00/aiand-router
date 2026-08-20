# Fix: restore `x-router-reason` on gateway hops

Spec: existing `POST /v1/chat/completions` seams stay green. Fresh suite after `8bb2677`: **123 passed, 7 failed**. All 7 are `tests/test_gateway.py` `KeyError: 'x-router-reason'`.

Failing tests:
- test_summarize_phase_forwards_flash_on_pioneer_score
- test_learned_router_stays_dark_after_comparison
- test_security_review_phase_is_first_class
- test_max_regret_picks_stronger_when_cheap_is_far_behind
- test_pioneer_score_beats_a_cheaper_weaker_model
- test_summarize_picks_highest_pioneer_score
- test_draft_phase_planning_is_first_class

Do not weaken the tests. Restore the Decision-contract header on the rules hop (and shadow if that path is hit). `test_trained_hop.py` must stay green.

Likely files: `src/aiand_router/app.py` and/or `src/aiand_router/scorer.py` (`apply_trained_path`). Do not rewrite the gateway. Do not flip `TRAINED_PATH`.

TDD: run one failing test first (red), fix, then all 7 + `tests/test_trained_hop.py`. Commit. Report to `.scratch/scorer-pioneer-lift/gateway-reason-fix-report.md`.
