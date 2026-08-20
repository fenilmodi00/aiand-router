# Goal completion audit — Pioneer/Fireworks routing approach (2026-08-20)

**Audited goal (reframed):** Produce a **prototype/demo** that honestly supports: *with enough compute (Modal/remote eval + paid gold), this routing approach works* — plus research/diagnosis of scorer failures and a winning strategy.  
**Not required for this stop:** local ~1TB image farm, `TRAINED_PATH=trained`, or full Fireworks/Pioneer **production** parity.

**Verdict under NEW bar:** **Prototype-ready — MET.** See `.scratch/scorer-pioneer-lift/prototype-demo-2026-08-20.md`.  
**Verdict under OLD production-parity bar:** **Incomplete** (do not claim).

**Evidence method:** Source-of-truth docs + runnable unpaid demo commands. No serve flip. Modal probe unpaid → `modal_not_configured`.

---

## Two bars (keep distinct)

| Bar | Status | Meaning |
| --- | --- | --- |
| **Research / strategy** | **Complete** | FireRouter + Pioneer primary docs; debate phases; falsified-path catalog |
| **Capability — prototype/demo** | **Ready** | Shadow serve + session-gold path + join/stickiness + remote resolve adapter; scalable with Modal/paid gold |
| **Capability — production parity** | **Incomplete** | No n≥300 session floor, ship rcd>0, no TRAINED flip, cascade ≠ FireRouter product |

---

## Objective themes (user requirements)

| Theme | Status | Evidence path | Notes |
| --- | --- | --- | --- |
| **Diagnose why scorer fails** | **Proven** | `gate-fail-diagnosis.md`, research §What We're Doing Wrong; Mix1 + hard-logistic | Geometry / feature / threshold coupling diagnosed |
| **Identify what won't work** | **Proven (catalog live)** | Research §What Won't Work; unpaid-next falsified table | Cost frontier, cascade soft-t, gym_alt, hash distill XOR |
| **Winning strategy + research + debate** | **Proven** | `../trained-router/research/scorer-router-fireworks-pioneer-debate.md` | Strategy actionable; scale execution is compute |
| **Router as capable as Fireworks/Pioneer (production)** | **Incomplete** | Floor, cost-vs-rules serve, cascade product | Explicitly **out of prototype stop** |
| **Prototype: approach works with enough compute** | **Proven / ready** | `prototype-demo-2026-08-20.md` | Modal auth is the human unlock for remote scale |

---

## Requirements checklist (detail)

| # | Requirement | Status | Evidence |
| --- | --- | --- | --- |
| **R1–R6** | Research, debate, diagnose, falsify, strategy | **Proven** | Research deliverable + falsified catalog |
| **R7–R13** | Pioneer-shaped policy, replay/geometry/merge, Mix1, hard-logistic shadow | **Proven** | `data/scorer-hard-logistic.json`; replay gate pass |
| **R14** | Trained beats rules on proxy success | **Proven** | succ 0.112 vs 0.022 on n=89 |
| **R15** | Cost vs rules on **serve** | **Incomplete on serve; overlay partial** | Ship +0.000687; overlay −0.000688 shadow-only |
| **R16** | Savings vs most expensive (proxy) | **Proven** on n=89 | |
| **R17–R19** | Dual ECE at scale; retune; second hard-gold | **Incomplete** | Not required for prototype stop |
| **R22** | Full Verified promotion floor | **Incomplete — disk-blocked locally; remote path wired** | 10/12 canary; Modal adapter ready |
| **R24** | `TRAINED_PATH=trained` | **Correctly not started** | Prototype stays shadow |
| **R25–R26** | Fireworks/Pioneer product parity | **Incomplete** | Out of prototype bar |
| **R29** | Session-joined cost logging | **Proven (code + sample)** | n_joinable=10; joined rcd≈−0.00162 |
| **R30** | Hash distill beats serve | **Contradicted (XOR)** | |
| **R31** | Prototype demo kit | **Proven** | `prototype-demo-2026-08-20.md` |
| **R32** | Disk-light remote resolve | **Wired; auth pending** | `SWE_EVAL_BACKEND=modal\|sb-cli` |

---

## Falsified paths catalog (update 2026-08-20)

| Path | Result | Evidence |
| --- | --- | --- |
| Easy-gold / GBDT serve | Replay fail | diagnosis docs |
| Blind smith / gym_alt order-mix | Geometry / projection fail | postmortems |
| Hash-teacher distill joint dominate | XOR exhausted | distill-gate-recovery |
| Soft cost-frontier middle overlay | BSS blocks | fine-cost-frontier |
| Cascade soft-t as FireRouter | Quirk ≠ product | cascade-knob-sweep |
| Mass docker pull on this host | Disk-blocked | inventory = 12 eval images |

---

## Status summary

### Proven (research + prototype machinery)

- Research + debate + winning strategy.
- Hard-logistic **shadow** replay pass; proxy succ ≫ rules.
- Session-gold **path** 10/12; session_id join sample; stickiness.
- Remote resolve adapter (`modal` / `sb-cli` / `local`) with honest `not_available`.
- Promotion readiness labels `local_image_farm` vs `remote_eval` floors.
- **Prototype demo kit packaged and runnable unpaid.**

### Incomplete (production parity only)

- Ship cost vs rules; ECE/retune at scale; second merge-safe hard gold.
- Session floor n≥300/500; Modal auth on this host; FireRouter cascade product.
- `TRAINED_PATH=trained` (correctly blocked).

---

## Research vs capability closeness

| Layer | Closeness |
| --- | --- |
| **Research / strategy** | **Done** |
| **Prototype / demo** | **Ready** — claim text in prototype-demo kit |
| **Local shadow serve** | Strong proxy; ship rcd>0; `not_spec_floors` |
| **Session-gold path** | Proven harness; ~2% of production floor |
| **Product parity** | Far — not this stop |

---

## What remains for **full** parity (not prototype)

1. Human: `modal token new` → remote gold-patch smoke.
2. Paid dual-policy + remote resolve toward n≥300.
3. Ship rcd≤0 or explicit overlay trade with session evidence.
4. Calibration at scale; operator sign-off before any TRAINED flip.
5. Optional FireRouter cascade product redesign.

---

## Serve status (freeze)

- Artifact: `data/scorer-hard-logistic.json`
- Path: **shadow**; do **not** flip `TRAINED_PATH=trained` for prototype stop
- Overlay t=0.15: shadow experiment only
- Cascade: `enabled: false`

## Exact next human command (scale unlock)

```powershell
pip install modal 'swebench[modal]'
modal token new
cd D:\aiand-router
$env:PYTHONPATH='src'; $env:PYTHONUTF8='1'
python scripts/swe_eval_cmd.py --backend modal --instance django__django-11099 --patch data/_gold_django_11099.patch
```

Demo (unpaid) commands: `prototype-demo-2026-08-20.md`.

---

## Related files

- **Prototype kit:** `prototype-demo-2026-08-20.md`
- Research: `.scratch/trained-router/research/scorer-router-fireworks-pioneer-debate.md`
- Disk-light: `disk-light-parity-path-2026-08-20.md`
- Unpaid next: `unpaid-next-path-2026-08-20.md`
- Serve: `data/scorer-hard-logistic.json`
