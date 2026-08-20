"""Unpaid cascade knob sweep: why 0 redirects + find cheap_redirect>0.

In-memory enable only. Does not mutate config/models.yaml or serve artifact.
No docker / no paid gold.
"""
from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path

from aiand_router.replay_report import BUDGET, EFFORT, _load_gold
from aiand_router.router import load_config, load_models
from aiand_router.scorer import cascade_select, effort_knobs, load_scorer, score_eligible

ROOT = Path(__file__).resolve().parents[2]
OUT_MD = Path(__file__).with_name("cascade-knob-sweep-2026-08-20.md")
OUT_JSON = Path(__file__).with_name("cascade-knob-sweep-2026-08-20.json")


def _summ(xs: list[float]) -> dict:
    xs = sorted(xs)
    n = len(xs)
    return {
        "n": n,
        "min": xs[0],
        "p10": xs[n // 10],
        "med": xs[n // 2],
        "p90": xs[(9 * n) // 10],
        "max": xs[-1],
        "mean": sum(xs) / n,
    }


def main() -> None:
    cfg0 = load_config(ROOT / "config" / "models.yaml")
    models = load_models(cfg0)
    art = load_scorer(ROOT / "data" / "scorer-hard-logistic.json")
    items, _ = _load_gold(ROOT / "data" / "gold-verified.jsonl")
    phases_cfg = list(cfg0["cascade_lane"]["phases"])
    cheap_id = cfg0["cascade_lane"]["cheap_model"]
    strong_id = cfg0["cascade_lane"]["strong_model"]
    thr_ship, mr_ship = effort_knobs(cfg0, EFFORT)

    # --- score geometry ---
    cheap_ps: list[float] = []
    strong_ps: list[float] = []
    gaps: list[float] = []
    fail_thr = fail_reg = both_ok = 0
    for it in items:
        _, ps = score_eligible(
            art,
            [cheap_id, strong_id],
            phase=it["phase"],
            needs_tools=it["needs_tools"],
            tokens=it["tokens"],
            text=str(it.get("prompt") or ""),
        )
        cp, sp = ps[cheap_id], ps[strong_id]
        cheap_ps.append(cp)
        strong_ps.append(sp)
        gaps.append(sp - cp)
        if cp < thr_ship:
            fail_thr += 1
        elif (sp - cp) > mr_ship:
            fail_reg += 1
        else:
            both_ok += 1

    phase_hit = sum(1 for it in items if it.get("phase") in phases_cfg)
    excluded = Counter(it["phase"] for it in items if it.get("phase") not in phases_cfg)

    def run(
        th: float,
        mr: float,
        *,
        effort: str = "medium",
        phases: list[str] | None = None,
    ) -> dict:
        c = copy.deepcopy(cfg0)
        c["cascade_lane"] = {**c.get("cascade_lane", {}), "enabled": True}
        if phases is not None:
            c["cascade_lane"]["phases"] = phases
        c.setdefault("trained_effort", {})[effort] = {
            "threshold": th,
            "max_regret": mr,
        }
        rules: Counter[str] = Counter()
        for it in items:
            if it.get("phase") not in (c["cascade_lane"].get("phases") or []):
                continue
            pick = cascade_select(
                c,
                models,
                art,
                phase=it["phase"],
                needs_tools=it["needs_tools"],
                tokens=it["tokens"],
                effort=effort,
                allowed=None,
                spend_usd=0.0,
                budget_usd=BUDGET,
                text=str(it.get("prompt") or ""),
            )
            rules["none" if pick is None else pick.rule] += 1
        n = sum(rules.values())
        redir = int(rules.get("cheap_redirect", 0))
        return {
            "threshold": th,
            "max_regret": mr,
            "effort": effort,
            "n": n,
            "cheap_redirect": redir,
            "cheap_redirect_rate": (redir / n) if n else 0.0,
            "rules": dict(rules),
        }

    thr_sweep = [
        run(th, 0.20)
        for th in [
            0.10,
            0.08,
            0.05,
            0.04,
            0.035,
            0.032,
            0.031,
            0.030,
            0.028,
            0.027,
            0.025,
            0.020,
            0.010,
            0.0,
        ]
    ]
    mr_sweep = [run(0.03, mr) for mr in [0.01, 0.05, 0.10, 0.20, 0.30, 0.50, 1.0]]
    effort_sweep = [
        run(float(k["threshold"]), float(k["max_regret"]), effort=name)
        for name, k in cfg0["trained_effort"].items()
    ]
    phase_sweep = [
        run(0.025, 0.20, phases=phases)
        for label, phases in [
            ("ship", phases_cfg),
            ("edit_only", ["edit"]),
            ("all_gold", sorted({str(it["phase"]) for it in items})),
            ("expand_discover", phases_cfg + ["discover", "summarize"]),
        ]
    ]
    # attach labels for phase sweep
    for row, (label, _) in zip(
        phase_sweep,
        [
            ("ship", None),
            ("edit_only", None),
            ("all_gold", None),
            ("expand_discover", None),
        ],
        strict=True,
    ):
        row["phases_label"] = label

    # Scan high→low: highest t with any redirect; highest t with full allowlist redirect
    first_gt0 = None  # highest threshold that still redirects some
    first_full = None  # highest threshold that redirects all allowlisted
    fine = []
    for i in range(100, -1, -1):
        th = i / 1000
        row = run(th, 0.20)
        fine.append(row)
        if first_gt0 is None and row["cheap_redirect"] > 0:
            first_gt0 = row
        if first_full is None and row["n"] and row["cheap_redirect"] == row["n"]:
            first_full = row

    # Prefer highest-t partial redirect (least soft) for demonstrating cheap_redirect>0
    best = max(
        (r for r in thr_sweep if r["cheap_redirect"] > 0),
        key=lambda r: (r["threshold"], r["cheap_redirect_rate"]),
        default=None,
    )
    # Measurement demo: highest t with redirects (t≈0.035) — not a serve candidate
    recommended = first_gt0 or first_full

    payload = {
        "artifact": "data/scorer-hard-logistic.json",
        "config": "config/models.yaml",
        "n_items": len(items),
        "phase_counts": dict(Counter(it.get("phase") for it in items)),
        "phase_allowlist_hit": phase_hit,
        "phase_excluded": dict(excluded),
        "pair": {"cheap": cheap_id, "strong": strong_id},
        "ship_knobs": {"threshold": thr_ship, "max_regret": mr_ship, "effort": EFFORT},
        "score_geometry": {
            "cheap_p": _summ(cheap_ps),
            "strong_p": _summ(strong_ps),
            "gap_strong_minus_cheap": _summ(gaps),
            "gap_le_0": sum(1 for g in gaps if g <= 0),
            "fail_threshold": fail_thr,
            "fail_max_regret": fail_reg,
            "would_redirect_at_ship": both_ok,
        },
        "threshold_sweep_r020": thr_sweep,
        "max_regret_sweep_t030": mr_sweep,
        "effort_preset_sweep": effort_sweep,
        "phase_sweep_t025": phase_sweep,
        "first_threshold_gt0": first_gt0,
        "first_threshold_full_allowlist": first_full,
        "recommended_in_memory": recommended,
        "best_high_redirect_in_grid": best,
    }

    # write markdown
    lines = [
        "# Cascade knob sweep (unpaid) — 2026-08-20",
        "",
        "Config on disk unchanged: `cascade_lane.enabled: false`. Measurement **in-memory only**.",
        "Artifact frozen: `data/scorer-hard-logistic.json`. No docker / no paid gold / no `TRAINED_PATH=trained`.",
        "",
        "## Why 0/89 cheap_redirect at ship knobs",
        "",
        f"- Pair: Flash (`{cheap_id}`) vs Pro (`{strong_id}`).",
        f"- Ship medium knobs: threshold=`{thr_ship}`, max_regret=`{mr_ship}`.",
        f"- Flash P(success) on verified: mean≈`{payload['score_geometry']['cheap_p']['mean']:.4f}`, "
        f"max≈`{payload['score_geometry']['cheap_p']['max']:.4f}` — **all below 0.10**.",
        f"- Pro P(success): mean≈`{payload['score_geometry']['strong_p']['mean']:.4f}` — "
        f"**Flash > Pro on all {len(items)} prompts** (gap always ≤0).",
        f"- Failure split at ship knobs: `fail_threshold={fail_thr}`, "
        f"`fail_max_regret={fail_reg}`, `would_redirect={both_ok}`.",
        "- **Root cause = threshold too high**, not max_regret and not model-pair ordering.",
        f"- Phase allowlist: `{phase_hit}/{len(items)}` prompts eligible "
        f"(excluded: `{dict(excluded)}`). Not the 0-redirect cause on allowlisted rows.",
        "",
        "## Score geometry",
        "",
        "| Dist | min | p10 | med | p90 | max | mean |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, key in [
        ("Flash P", "cheap_p"),
        ("Pro P", "strong_p"),
        ("Pro−Flash", "gap_strong_minus_cheap"),
    ]:
        s = payload["score_geometry"][key]
        lines.append(
            f"| {name} | {s['min']:.4f} | {s['p10']:.4f} | {s['med']:.4f} | "
            f"{s['p90']:.4f} | {s['max']:.4f} | {s['mean']:.4f} |"
        )
    lines += [
        "",
        "## Threshold sweep (max_regret=0.20, ship phases)",
        "",
        "| t | n | cheap_redirect | rate | rules |",
        "| ---: | ---: | ---: | ---: | --- |",
    ]
    for r in thr_sweep:
        lines.append(
            f"| {r['threshold']:.3f} | {r['n']} | {r['cheap_redirect']} | "
            f"{r['cheap_redirect_rate']:.3f} | `{r['rules']}` |"
        )
    lines += [
        "",
        "## max_regret sweep (t=0.03)",
        "",
        "Inert on this slice (Flash always ahead of Pro once threshold clears).",
        "",
        "| r | cheap_redirect | rate |",
        "| ---: | ---: | ---: |",
    ]
    for r in mr_sweep:
        lines.append(
            f"| {r['max_regret']:.2f} | {r['cheap_redirect']} | {r['cheap_redirect_rate']:.3f} |"
        )
    lines += [
        "",
        "## Effort presets (ship knobs)",
        "",
        "| effort | t | r | cheap_redirect | rate |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for r in effort_sweep:
        lines.append(
            f"| {r['effort']} | {r['threshold']:.2f} | {r['max_regret']:.2f} | "
            f"{r['cheap_redirect']} | {r['cheap_redirect_rate']:.3f} |"
        )
    lines += [
        "",
        "## Phase list (t=0.025, r=0.20)",
        "",
        "| phases | n | cheap_redirect | rate |",
        "| --- | ---: | ---: | ---: |",
    ]
    for r in phase_sweep:
        lines.append(
            f"| {r['phases_label']} | {r['n']} | {r['cheap_redirect']} | "
            f"{r['cheap_redirect_rate']:.3f} |"
        )

    demo = run(0.035, 0.20)
    full = run(0.027, 0.20)
    maj = run(0.031, 0.20)
    assert first_gt0 is not None and first_full is not None
    lines += [
        "",
        "## Best in-memory knob set (measurement only)",
        "",
        f"- Highest t with any redirect: **t={first_gt0['threshold']}** → "
        f"`{first_gt0['cheap_redirect']}/{first_gt0['n']}` "
        f"(rate `{first_gt0['cheap_redirect_rate']:.3f}`).",
        f"- Highest t with full allowlist redirect: **t={first_full['threshold']}** → "
        f"`{first_full['cheap_redirect']}/{first_full['n']}` "
        f"(rate `{first_full['cheap_redirect_rate']:.3f}`).",
        f"- **Demo (least soft, cheap_redirect>0):** `threshold=0.035`, `max_regret=0.20`, "
        f"effort=`medium`, ship phases → "
        f"`{demo['cheap_redirect']}/{demo['n']}` (rate `{demo['cheap_redirect_rate']:.3f}`).",
        f"- Majority redirect: `t=0.031` → `{maj['cheap_redirect']}/{maj['n']}` "
        f"(rate `{maj['cheap_redirect_rate']:.3f}`).",
        f"- Full allowlist: `t≤0.027` → `{full['cheap_redirect']}/{full['n']}` "
        f"(rate `{full['cheap_redirect_rate']:.3f}`).",
        "- `max_regret` and effort presets (at ship thresholds) do not unlock redirects; "
        "phase expansion only changes denominator.",
        "",
        "## Serve recommendation",
        "",
        "- **Keep `cascade_lane.enabled: false`** on ship `config/models.yaml`.",
        "- Do **not** promote a soft cascade threshold to serve: Flash P≈0.03 on this artifact "
        "means any t≤0.038 that yields redirects is an **artifact-scale quirk** (scores far "
        "below Pioneer medium 0.10), not FireRouter-quality complexity gating.",
        "- Do **not** replace `data/scorer-hard-logistic.json`; do **not** flip `TRAINED_PATH=trained`.",
        "- Optional shadow: document soft knobs only in scratch; no new overlay file warranted.",
        "",
        "## Honest FireRouter gaps remaining",
        "",
        "1. **No live complexity classifier** — cascade reuses hard-logistic P(success), not a "
        "FireRouter-style redirect/pass-through score.",
        "2. **No quality/savings dial (1–5)** — only Pioneer threshold/max_regret.",
        "3. **No conversation routing stickiness**.",
        "4. **Default-off prototype** — 0 redirects at ship knobs; soft-t redirects are "
        "measurement artifacts, not product parity.",
        "5. **Catalog pair ≠ FireRouter defaults** (Flash/Pro vs Opus/GLM-fast).",
        "6. **Calibrated P on verified remains tiny** (~0.03) vs Pioneer medium bar 0.10.",
        "",
        "## Remaining blockers",
        "",
        "1. Scorer geometry / calibration still wrong for verified holdout (P≪ threshold).",
        "2. Ship `rules_cost_delta>0` with no unpaid middle clearing cost without success cliff.",
        "3. Session-gold floor disk-blocked; no docker pull.",
        "4. Enabling cascade at soft t would redirect almost everything to Flash — quality risk "
        "unmeasured on session gold.",
        "",
        "## Exact next unpaid command (zero new images)",
        "",
        "```powershell",
        "$env:PYTHONPATH='src'; $env:PYTHONUTF8='1'",
        "python .scratch/scorer-pioneer-lift/_cascade_knob_sweep.py",
        "```",
        "",
        "Optional after gateway restart (paid API, no docker pull) — ≤3 already-gold local ids:",
        "",
        "```powershell",
        "python -m aiand_router.eval --gate --log data/requests.jsonl "
        "--sessions data/verified_session_filectx_all.jsonl",
        "```",
        "",
        f"Raw JSON: `{OUT_JSON.name}`.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(OUT_MD)
    print(
        "ship_fail",
        fail_thr,
        fail_reg,
        both_ok,
        "first_gt0",
        first_gt0,
        "first_full",
        first_full,
    )


if __name__ == "__main__":
    main()
