# Multi-SWE-RL trigger

Type: grilling
Status: resolved
Blocked by: 16
Part of: [Production trained coding router](../map.md)

## Question

When (if ever) does the spec **add Multi-SWE-RL** (or a similar multilingual task dump) to bootstrap, and what **numeric trigger** on production flywheel makes non-Python “material”?

[Bootstrap dump set](16-bootstrap-dump-set.md) already froze Multi-SWE-RL as **not v1-required** (Python-first). Research: 4,723 RL instances / 7 langs, CC0 + ByteDance IP + upstream licenses; Multi-SWE-bench is eval (1,632), not a train matrix. [note](../research/bootstrap-datasets.md).

HITL — do not resolve without the human.

## Answer

**v1 stays Python-first.** Multi-SWE-RL is **not** a v1 required dump.

**Trigger:** in the **drift canary** window (n≥300 hops or 7 days, whichever later), if **≥20%** of hops are **non-Python**, the spec requires Multi-SWE-RL on the **next full retrain**. Operator starts ingest (no auto-pull). Unknown-language hops do **not** count as non-Python.

**Python hop:** `.py` / `.pyi` / `.pyw`, or `pyproject.toml` / `requirements*.txt` / `setup.py` / `Pipfile`, or logged `lang`/`language` ∈ {`python`, `py`}. Markdown/JSON/YAML/lockfiles alone are unknown. Mixed-repo with ≥1 Python source file = Python. No live language-id model.

**What adds:** Multi-SWE-RL **tasks** as bootstrap (parse + relabel; teacher + gold recipe unchanged). Smith stays required. Does **not** change the promotion gate (Verified). SWE-rebench-V2 stays extra optional, not this trigger’s substitute.

**Eval-only:** **Multi-SWE-bench** (1,632 human-validated). Collision-filter `instance_id` / problem hash vs that bench, same pattern as smith vs SWE-bench family.

**License:** diligence gate (HF card + ByteDance IP caveat + listed upstream licenses), same posture as gym/r2e. Drop instances legal review forbids. If the dump is blocked, do **not** ingest; trigger stays up until an allowed multilingual dump exists. Do not silently swap to rebench-V2.

Detail: [Bootstrap dump set](16-bootstrap-dump-set.md) · [note](../research/bootstrap-datasets.md).

Rejected: 5/10% or any-hop trigger, flywheel-only (no dump), train on Multi-SWE-bench, both-dumps-required, second promotion corpus, swap smith %, eval-only diversity, majority-ext / teacher-only / live lang-id, ingest-without-review, hard-require rebench-V2, trigger-logs-only.

## Comments

- Graduated from map fog. v1 dump membership is frozen; the follow-on trigger is not.
- Grill round 1 (all recs): **Q1 A** ≥20% non-Python hops in drift-canary window; operator starts ingest. **Q2 A** Multi-SWE-RL required on next full retrain; Multi-SWE-bench eval-only + collision filter; rebench-V2 stays extra optional. **Q3 A** bootstrap only; smith stays; Verified gate unchanged.
- Grill round 2 (all recs): **Q4 A** ext/path/`lang` tag; unknown ≠ non-Python; mixed with a `.py` = Python. **Q5 A** legal diligence then ingest; no silent dump swap.
