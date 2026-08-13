# Flywheel log store

Type: grilling
Status: resolved
Blocked by: 09
Part of: [Production trained coding router](../map.md)

## Question

Where does **production flywheel** live, and what **row contract** must it keep so retrain can read it?

Standing preference: aiand infra, not this repo. [Observability Decision contract](09-observability-decision-contract.md) froze JSONL fields (same row as the live hop, including shadow). This ticket freezes **store + ownership**, not a new Decision schema. Out of scope: operating their multi-tenant control plane from this checkout.

HITL — do not resolve without the human.

## Answer

**Aiand infra, JSONL-compatible append log. They pick the bucket/stream. This repo does not host production flywheel.**

**Store:** object store or their existing request log — spec does **not** pin S3 vs GCS vs ClickHouse. Prototype remains `data/requests.jsonl`. Operating their multi-tenant control plane from this checkout stays out of scope. Tenancy (per-org vs shared) is theirs.

**Rows:** the live-hop JSONL from [Observability Decision contract](09-observability-decision-contract.md) — every `path` (`rules` / `trained` / `shadow`), flashlight outcomes when present, explore gold cells. Success gold on the row. **No second `flywheel.jsonl`.** Missing explore ≠ 0.

**Retention (minimum):** until the next full retrain **and** its promotion gate. Must keep Decision contract fields, success gold, and Rec A **features**. Secrets redacted (`redact_keys`, same as this gateway). Prompt/body retention is **aiand policy** (teacher pass on flywheel needs text; this spec does not archive it). Retrain jobs read **their** store.

Glossary: **Flywheel**, **Flywheel log**.

Rejected: pin S3/GCS/Postgres, this checkout as production, trained-path-only, separate thinner flywheel file, full prompts in this repo, drop prompts (would block teacher-on-retrain).

## Comments

- Graduated from map fog after the proposal-grade spec. Contract exists; location/ownership does not.
- Grill (all recs): **Q1 A** JSONL-compatible append log on aiand infra; they pick the store; this repo is prototype only. **Q2 A** same live-hop JSONL, all paths, no second file. **Q3 A** keep until next retrain+gate: contract + success gold + Rec A features; secrets redacted; prompt retention is aiand policy.
