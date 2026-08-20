# Session-joined cost sample (2026-08-20)

**Unpaid-first stickiness done first; this is the optional paid sample (≤3 local already-gold ids, no pulls).**

## Gateway

- Restarted uvicorn on current `src` with **process** `TRAINED_PATH=shadow` (do not trust `.env` `TRAINED_PATH=trained`).
- `SCORER_PATH=data/scorer-hard-logistic.json`, `UPSTREAM_TIMEOUT_S=300`.
- `BUDGET_LIMIT_USD = spend + 15` (~30.76).
- `session_id` logging confirmed on hops.

## Paid sample (2 of 3 named locals; 11099 already joined earlier)

| instance | session_gold | rules | trained | file_context |
| --- | --- | --- | --- | --- |
| `django__django-10880` | true | false | false | docker_cp |
| `django__django-11880` | true | true | true | docker_cp |

- Out: `data/verified_session_joined_sample.jsonl`
- Ids file: `data/verified_ids_session_joined_sample.jsonl`
- Spend: **15.758414 → 15.767137** (Δ **+$0.008723**)
- No docker pull.

## `eval --gate` (sessions = `verified_session_filectx_all.jsonl`)

| Field | Before sample | After sample |
| --- | ---: | ---: |
| `session_joined` | true | true |
| `n_joinable_hops` | 1 | **10** |
| `n_hops_with_session_id` | 1 | **12** |
| `rules_cost_delta` (joined) | −0.001922 | **−0.001622** |
| verdict | `bounded_check_only` | `bounded_check_only` |

Still failing: cal BSS/ECE_w, floor n=12≪300. **`do_not_flip_trained_path: true`**.

## Serve

Unchanged: `data/scorer-hard-logistic.json` shadow. Goal **not** complete.
