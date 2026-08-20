# Fine cost–quality frontier — falsified (2026-08-20)

Unpaid verified replay only (`data/gold-verified.jsonl`, n=89). Artifact frozen: `data/scorer-hard-logistic.json`. No serve / `models.yaml` mutation. No docker pull.

**Script:** `.scratch/scorer-pioneer-lift/_finer_cost_frontier.py`  
**Raw grid:** `data/cost-frontier-fine-2026-08-20.json` (140 cells: 20 thresholds × 7 max_regret)

## Question

Is there an unpaid medium `{threshold, max_regret}` that clears `rules_cost_delta≤0` **and** keeps `replay_gate_pass` with trained success **closer to ship 0.112 than overlay 0.090**?

## Answer

**No.** Falsified on this holdout.

Replay hardcodes `EFFORT=medium`, so low/high/max per-effort knobs are **not** exercised here (documented, not swept).

`max_regret` ∈ {0.03…0.30} never changes the policy at any threshold on this slice (identical outcomes within each threshold).

## Frontier vs ship / overlay

| Point | t | r | gate | rcd | succ | n_sel | notes |
| --- | ---: | ---: | --- | ---: | ---: | ---: | --- |
| **Ship serve** | 0.10 | 0.20 | pass | **+0.000687** | **0.112** | 72 | quality-primary |
| Best partial cost (still rcd>0) | 0.135 | any | pass | +0.000570 | 0.101 | 68 | −1.1pp succ; cost not cleared |
| Attractive middle | 0.141–0.145 | any | **fail (BSS≤0)** | −0.00019…−0.00025 | **0.101** | 40–42 | rcd ok + better succ, **gate blocks** |
| First safe rcd≤0 | **0.148** | any | pass | −0.000658 | **0.090** | 26 | same succ as t=0.15 |
| **Existing overlay** | 0.15 | 0.20 | pass | **−0.000688** | **0.090** | 25 | shadow experiment |
| Over-tight | 0.16 | any | pass | −0.001243 | 0.079 | 6 | worse succ |

Ship → overlay success cliff is discrete on Kimi confidences: n_above drops 72→69→68→53→42→40→30→**26**→25. No continuous middle that is both gate-safe and rcd-safe with succ∈(0.090, 0.112).

## Mechanism

Raising medium threshold declines Kimi below the bar → Flash fallback. Cost clears only once enough Kimi hops fall off. The first gate-safe cut that clears rcd is at **t≈0.148** (26 Kimi kept), already at **succ=0.090**. Points with succ=0.101 and rcd≤0 sit in a **BSS valley** (selected-hop calibration flips negative).

## Serve recommendation

- **Keep ship serve:** `data/scorer-hard-logistic.json` + `config/models.yaml` (t=0.10). Do **not** promote overlay.
- **Keep existing shadow overlay** `config/models.cost-overlay-t015.yaml` (t=0.15). Optional note: t=0.148 is policy-equivalent on success and also gate-safe with slightly less negative rcd; **not worth a new overlay file** — does not move success toward 0.112.
- Do **not** flip `TRAINED_PATH=trained`.

## Remaining blockers (unchanged)

1. Ship `rules_cost_delta>0` with no unpaid middle that clears it without the 0.112→0.090 success hit (or BSS failure).
2. Session-gold floor disk-blocked (10/12 local; no pull).
3. Cascade at ship knobs still 0 redirects (threshold); soft-t redirects measured but not promoted — see `cascade-knob-sweep-2026-08-20.md`.
4. Live `session_joined` rcd needs gateway restart + new hops.

## Exact next unpaid command (zero new images)

```powershell
# Cascade knob sweep done (keep cascade_lane.enabled: false). Next: session_joined rcd after gateway restart.
$env:PYTHONPATH='src'; $env:PYTHONUTF8='1'
python -m aiand_router.eval --gate --log data/requests.jsonl --sessions data/verified_session_filectx_all.jsonl
# Re-run sweep only if needed:
# python .scratch/scorer-pioneer-lift/_cascade_knob_sweep.py
```
