# Effort tier threshold and max_regret

Type: grilling
Status: resolved
Blocked by: 08
Part of: [Production trained coding router](../map.md)

## Question

What numeric **threshold** and **max_regret** does the spec freeze per effort (`low | medium | high | max`) for the trained pick?

Standing preference: effort headers only retune those two knobs; trained pick is cheapest-above-bar, not max weighted score. No `xhigh` unless the team asks. Pioneer publishes example presets (e.g. high ≈ 0.20 / 0.15) but we do not copy them blindly — ours must match **calibrated** P(success) on this catalog.

[Promotion gate numeric bars](08-promotion-gate-numeric-bars.md) froze *whether trained may leave shadow*, not the live operating points. Do not relitigate the gate here.

HITL — do not resolve without the human.

## Answer

Unfitted **ship defaults** + mandatory retune. Pioneer **names** (no `xhigh`); do not relabel Pioneer-high onto AIand-medium. Default effort stays **`medium`**. Units are calibrated P(success), never AA points — do not reuse rules `max_regret: 8`.

| effort | threshold | max_regret |
| --- | --- | --- |
| `low` | 0.05 | 0.30 |
| `medium` (default) | 0.10 | 0.20 |
| `high` | 0.20 | 0.15 |
| `max` | 0.60 | 0.03 |

Label: not measured on aiand. `low` still uses the scorer (tiny floor, wide regret). `max` is still cheapest-above-bar among the same eligible set as rules (premium floor still lets K3 in); publish the max row even when today’s catalog often leaves only K3.

**Retune (before shadow):** disjoint **threshold-tuning split** (not train, not calibrator, not promotion). Always search: minimize list-price USD s.t. session gold **and** escalate each ≥ rules − 1 pp. Initialize at ship defaults; keep them if they win. Fit **medium only**. Other rungs = Pioneer offsets from medium `(0.10, 0.20)`:

| rung | Δ threshold | Δ max_regret |
| --- | --- | --- |
| `low` | −0.05 | +0.10 |
| `high` | +0.10 | −0.05 |
| `max` | +0.50 | −0.17 |

Clamp \(t,r \in [0,1]\), then walk to restore \(t_\text{low} \le t_\text{med} \le t_\text{high} \le t_\text{max}\) and \(r_\text{low} \ge r_\text{med} \ge r_\text{high} \ge r_\text{max}\). Fitted numbers are **runtime config**, not a spec edit. If fitted medium cannot meet the constraint → do not promote.

**Order:** train → calibrate → retune medium → **shadow at fitted medium** → promotion gate (**medium only**; other rungs diagnostic / ship defaults until fitted) → live.

**Wire:** `x-routing-effort` only. YAML `trained_effort:` (or equivalent), namespaced away from rules `max_regret`. No raw `x-routing-threshold` / `x-routing-max-regret`.

Glossary: **Threshold**, **Max regret**, **Rules max regret**.

Rejected: forever-fixed copy, procedure-only with no ship table, Pioneer-high as AIand-medium, scorer-off low, special-case strongest-on-max, fit-all-four, gate-all-rungs, shadow-before-retune, per-request numeric overrides.

## Comments

- Graduated from map fog after [Promotion gate numeric bars](08-promotion-gate-numeric-bars.md). Gate is session gold + escalate ≤1 pp worse, rules cost delta < 0, BSS \(>0\), ECE \(\le 0.03\) on Verified/Lite (TB canary). Threshold/max_regret still need per-effort numbers for the serving policy.
- Grill: Q1–Q10 all take the recs (ship defaults + retune; Pioneer-named table; scorer-on low; cheapest-above-bar max; fit medium + offsets; gate at medium; exact Pioneer deltas; effort header only; retune → shadow → gate; always search, fitted = runtime config; glossary terms).
- [Threshold-tuning split](19-threshold-tuning-split.md) owns retune **y**: success gold + bootstrap resolve on a third bootstrap dense n≥300 split. This ticket’s “session gold” in the search line means that bootstrap resolve, not Verified/Lite session gold. Answer body unchanged.
