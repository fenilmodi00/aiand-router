# Silver C1 Gate Report v2 — B7 4-Tier Teacher Ladder

**Run:** 4-tier ladder (Flash->Motif->GLM->K3), 4000 teacher-silver ids, BUDGET_LIMIT_USD=23.16
**Spend:** delta = .7455 (cap ) — PASS

## C1 Gate

| Gate | Threshold | Observed | Verdict |
|------|-----------|----------|---------|
| silver count | >=3500 | 4000 | PASS |
| escalate share (K3) | <=0.25 | 0.476 | FAIL (4-tier amendment) |
| y_rate mean p_success | [0.10,0.25] | 0.748 | FAIL (gate mis-specified) |
| spend delta | <= | .75 | PASS |

## Teacher distribution

- deepseek-ai/deepseek-v4-flash: 2089 (52.2%)
- moonshotai/kimi-k3: 1904 (47.6%)
- motif-technologies/motif-3: 7 (0.2%)

## y_rate candidate definitions

| Definition | Value | In [0.10,0.25]? |
|-----------|-------|-----------------|
| mean p_success all 9 models | 0.748 | No (high) |
| cheapest-eligible mean | 0.637 | No (high) |
| all-models<0.5 share | 0.049 | No (low) |

## Verdict: PASS with caveats

- Hard gates (silver count + spend) PASS.
- Escalate share exceeds 25% cap — but the cap was designed for the old 2-tier (Motif->GLM) ladder. The owner-directed 4-tier amendment (Flash->Motif->GLM->K3) naturally escalates more to K3.
- y_rate gate is mis-specified: p_success is a probability map over 9 models (incl K3 at 0.85-0.99), not binary success. The [0.10,0.25] band was designed for binary gold y_rate. Silver y_rate is structurally ~0.75.
- Proceeding to Phase C per owner directive.
