# Cascade knob sweep (unpaid) — 2026-08-20

Config on disk unchanged: `cascade_lane.enabled: false`. Measurement **in-memory only**.
Artifact frozen: `data/scorer-hard-logistic.json`. No docker / no paid gold / no `TRAINED_PATH=trained`.

## Why 0/89 cheap_redirect at ship knobs

- Pair: Flash (`deepseek-ai/deepseek-v4-flash`) vs Pro (`deepseek-ai/deepseek-v4-pro`).
- Ship medium knobs: threshold=`0.1`, max_regret=`0.2`.
- Flash P(success) on verified: mean≈`0.0311`, max≈`0.0383` — **all below 0.10**.
- Pro P(success): mean≈`0.0250` — **Flash > Pro on all 89 prompts** (gap always ≤0).
- Failure split at ship knobs: `fail_threshold=89`, `fail_max_regret=0`, `would_redirect=0`.
- **Root cause = threshold too high**, not max_regret and not model-pair ordering.
- Phase allowlist: `70/89` prompts eligible (excluded: `{'discover': 17, 'summarize': 2}`). Not the 0-redirect cause on allowlisted rows.

## Score geometry

| Dist | min | p10 | med | p90 | max | mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Flash P | 0.0272 | 0.0273 | 0.0319 | 0.0320 | 0.0383 | 0.0311 |
| Pro P | 0.0225 | 0.0225 | 0.0253 | 0.0254 | 0.0343 | 0.0250 |
| Pro−Flash | -0.0066 | -0.0066 | -0.0066 | -0.0048 | -0.0022 | -0.0061 |

## Threshold sweep (max_regret=0.20, ship phases)

| t | n | cheap_redirect | rate | rules |
| ---: | ---: | ---: | ---: | --- |
| 0.100 | 70 | 0 | 0.000 | `{'strong_pass_through': 70}` |
| 0.080 | 70 | 0 | 0.000 | `{'strong_pass_through': 70}` |
| 0.050 | 70 | 0 | 0.000 | `{'strong_pass_through': 70}` |
| 0.040 | 70 | 0 | 0.000 | `{'strong_pass_through': 70}` |
| 0.035 | 70 | 2 | 0.029 | `{'strong_pass_through': 68, 'cheap_redirect': 2}` |
| 0.032 | 70 | 5 | 0.071 | `{'strong_pass_through': 65, 'cheap_redirect': 5}` |
| 0.031 | 70 | 51 | 0.729 | `{'cheap_redirect': 51, 'strong_pass_through': 19}` |
| 0.030 | 70 | 51 | 0.729 | `{'cheap_redirect': 51, 'strong_pass_through': 19}` |
| 0.028 | 70 | 54 | 0.771 | `{'cheap_redirect': 54, 'strong_pass_through': 16}` |
| 0.027 | 70 | 70 | 1.000 | `{'cheap_redirect': 70}` |
| 0.025 | 70 | 70 | 1.000 | `{'cheap_redirect': 70}` |
| 0.020 | 70 | 70 | 1.000 | `{'cheap_redirect': 70}` |
| 0.010 | 70 | 70 | 1.000 | `{'cheap_redirect': 70}` |
| 0.000 | 70 | 70 | 1.000 | `{'cheap_redirect': 70}` |

## max_regret sweep (t=0.03)

Inert on this slice (Flash always ahead of Pro once threshold clears).

| r | cheap_redirect | rate |
| ---: | ---: | ---: |
| 0.01 | 51 | 0.729 |
| 0.05 | 51 | 0.729 |
| 0.10 | 51 | 0.729 |
| 0.20 | 51 | 0.729 |
| 0.30 | 51 | 0.729 |
| 0.50 | 51 | 0.729 |
| 1.00 | 51 | 0.729 |

## Effort presets (ship knobs)

| effort | t | r | cheap_redirect | rate |
| --- | ---: | ---: | ---: | ---: |
| low | 0.05 | 0.30 | 0 | 0.000 |
| medium | 0.10 | 0.20 | 0 | 0.000 |
| high | 0.20 | 0.15 | 0 | 0.000 |
| max | 0.60 | 0.03 | 0 | 0.000 |

## Phase list (t=0.025, r=0.20)

| phases | n | cheap_redirect | rate |
| --- | ---: | ---: | ---: |
| ship | 70 | 70 | 1.000 |
| edit_only | 52 | 52 | 1.000 |
| all_gold | 89 | 89 | 1.000 |
| expand_discover | 89 | 89 | 1.000 |

## Best in-memory knob set (measurement only)

- Highest t with any redirect: **t=0.038** → `2/70` (rate `0.029`).
- Highest t with full allowlist redirect: **t=0.027** → `70/70` (rate `1.000`).
- **Demo (least soft, cheap_redirect>0):** `threshold=0.035`, `max_regret=0.20`, effort=`medium`, ship phases → `2/70` (rate `0.029`).
- Majority redirect: `t=0.031` → `51/70` (rate `0.729`).
- Full allowlist: `t≤0.027` → `70/70` (rate `1.000`).
- `max_regret` and effort presets (at ship thresholds) do not unlock redirects; phase expansion only changes denominator.

## Serve recommendation

- **Keep `cascade_lane.enabled: false`** on ship `config/models.yaml`.
- Do **not** promote a soft cascade threshold to serve: Flash P≈0.03 on this artifact means any t≤0.038 that yields redirects is an **artifact-scale quirk** (scores far below Pioneer medium 0.10), not FireRouter-quality complexity gating.
- Do **not** replace `data/scorer-hard-logistic.json`; do **not** flip `TRAINED_PATH=trained`.
- Optional shadow: document soft knobs only in scratch; no new overlay file warranted.

## Honest FireRouter gaps remaining

1. **No live complexity classifier** — cascade reuses hard-logistic P(success), not a FireRouter-style redirect/pass-through score.
2. **No quality/savings dial (1–5)** — only Pioneer threshold/max_regret.
3. **Conversation stickiness is gateway-only** (see `firerouter-stickiness-2026-08-20.md`); cascade still lacks FireRouter product stickiness integration.
4. **Default-off prototype** — 0 redirects at ship knobs; soft-t redirects are measurement artifacts, not product parity.
5. **Catalog pair ≠ FireRouter defaults** (Flash/Pro vs Opus/GLM-fast).
6. **Calibrated P on verified remains tiny** (~0.03) vs Pioneer medium bar 0.10.

## Remaining blockers

1. Scorer geometry / calibration still wrong for verified holdout (P≪ threshold).
2. Ship `rules_cost_delta>0` with no unpaid middle clearing cost without success cliff.
3. Session-gold floor disk-blocked; no docker pull.
4. Enabling cascade at soft t would redirect almost everything to Flash — quality risk unmeasured on session gold.

## Exact next unpaid command (zero new images)

```powershell
$env:PYTHONPATH='src'; $env:PYTHONUTF8='1'
python .scratch/scorer-pioneer-lift/_cascade_knob_sweep.py
```

Optional after gateway restart (paid API, no docker pull) — ≤3 already-gold local ids:

```powershell
python -m aiand_router.eval --gate --log data/requests.jsonl --sessions data/verified_session_filectx_all.jsonl
```

Raw JSON: `cascade-knob-sweep-2026-08-20.json`.
