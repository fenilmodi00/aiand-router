"""Unpaid diagnosis: rules_cost_delta drivers + threshold/max_regret sweep.

Does not mutate serve candidate. Eval-only on gold-verified.
"""

from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path

from aiand_router.replay_report import (
    BUDGET,
    COMPLETION_TOKENS,
    EFFORT,
    _brier,
    _brier_skill,
    _ece_equal_mass,
    _ece_equal_width,
    _eligible,
    _load_gold,
    _pick_cheapest,
    _pick_flash,
    _pick_most_expensive,
    _policy_stats,
    _rank_auc,
    apply_replay_gate,
    replay_report,
)
from aiand_router.router import estimate_cost, load_config, load_models, select_model
from aiand_router.scorer import load_scorer, score_eligible, trained_select

ROOT = Path(__file__).resolve().parents[2]
GOLD = ROOT / "data" / "gold-verified.jsonl"
ART = ROOT / "data" / "scorer-hard-logistic.json"
CFG = ROOT / "config" / "models.yaml"
OUT = Path(__file__).with_name("rules-cost-delta-diagnosis-2026-08-20.md")


def short(mid: str) -> str:
    return mid.split("/")[-1]


def eval_knobs(cfg, models, artifact, items, success, th: float, mr: float):
    cfg2 = copy.deepcopy(cfg)
    cfg2.setdefault("trained_effort", {})["medium"] = {
        "threshold": th,
        "max_regret": mr,
    }
    rules_picks = []
    trained_picks = []
    flash_picks = []
    cheap_picks = []
    expensive_picks = []
    hop_savings = []
    selected = []
    spreads = []
    auc_pairs = []
    disagree = 0
    for item in items:
        eligible = _eligible(cfg2, models, item)
        text = str(item.get("prompt") or "")
        kw = dict(
            phase=item["phase"],
            needs_tools=item["needs_tools"],
            tokens=item["tokens"],
            effort=EFFORT,
            allowed=None,
            spend_usd=0.0,
            budget_usd=BUDGET,
            text=text,
        )
        rules = select_model(cfg2, models, **{k: v for k, v in kw.items() if k != "text"})
        trained = trained_select(cfg2, models, artifact, **kw)
        if rules.model.id != trained.model.id:
            disagree += 1
        rules_picks.append((rules.model, item))
        trained_picks.append((trained.model, item))
        flash_picks.append((_pick_flash(cfg2, eligible), item))
        cheap_picks.append((_pick_cheapest(eligible), item))
        expensive = _pick_most_expensive(eligible)
        expensive_picks.append((expensive, item))
        tr_c = estimate_cost(trained.model, item["tokens"], COMPLETION_TOKENS)
        if expensive is not None:
            hop_savings.append(
                max(0.0, estimate_cost(expensive, item["tokens"], COMPLETION_TOKENS) - tr_c)
            )
        _, ps = score_eligible(
            artifact,
            [m.id for m in eligible],
            phase=item["phase"],
            needs_tools=item["needs_tools"],
            tokens=item["tokens"],
            text=text,
        )
        if len(ps) >= 2:
            spreads.append(max(ps.values()) - min(ps.values()))
        for m in eligible:
            key = (item["prompt"], m.id)
            if key in success and m.id in ps:
                auc_pairs.append((float(ps[m.id]), 1 if success[key] else 0))
        y = success.get((item["prompt"], trained.model.id))
        if trained.confidence is not None and y is not None:
            selected.append((float(trained.confidence), 1.0 if y else 0.0))
    n = len(items)
    report = {
        "n_prompts": n,
        "n_selected": len(selected),
        "policies": {
            "rules": _policy_stats(rules_picks, success),
            "trained": _policy_stats(trained_picks, success),
            "always_flash": _policy_stats(flash_picks, success),
            "always_cheapest": _policy_stats(cheap_picks, success),
            "always_most_expensive": _policy_stats(expensive_picks, success),
        },
        "disagreement_rate": (disagree / n) if n else 0.0,
        "rank_auc": _rank_auc(auc_pairs),
        "mean_p_spread": (sum(spreads) / len(spreads)) if spreads else 0.0,
        "brier": _brier(selected),
        "brier_skill": _brier_skill(selected),
        "ece_equal_width": _ece_equal_width(selected),
        "ece_equal_mass": _ece_equal_mass(selected),
        "savings_vs_most_expensive": (sum(hop_savings) / len(hop_savings))
        if hop_savings
        else 0.0,
    }
    report["rules_cost_delta"] = (
        report["policies"]["trained"]["list_price_cost"]
        - report["policies"]["rules"]["list_price_cost"]
    )
    return apply_replay_gate(report)


def main() -> None:
    cfg = load_config(CFG)
    models = load_models(cfg)
    artifact = load_scorer(ART)
    items, success = _load_gold(GOLD)

    base = replay_report(GOLD, artifact, models, cfg)
    lines: list[str] = []
    lines.append("# rules_cost_delta diagnosis — scorer-hard-logistic (2026-08-20)")
    lines.append("")
    lines.append("Unpaid eval-only on `data/gold-verified.jsonl`. Serve candidate not mutated.")
    lines.append("")
    lines.append("## Baseline (ship medium 0.10 / 0.20)")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    for k in (
        "replay_gate_pass",
        "rules_cost_delta",
        "rules_cost_delta_where_rules_ne_cheapest",
        "savings_vs_most_expensive",
        "rank_auc",
        "brier_skill",
        "mean_p_spread",
        "ece_equal_width",
        "disagreement_rate",
    ):
        lines.append(f"| `{k}` | `{base[k]}` |")
    lines.append(
        f"| trained success / cost | `{base['policies']['trained']['success_rate']:.4f}` / "
        f"`{base['policies']['trained']['list_price_cost']:.6f}` |"
    )
    lines.append(
        f"| rules success / cost | `{base['policies']['rules']['success_rate']:.4f}` / "
        f"`{base['policies']['rules']['list_price_cost']:.6f}` |"
    )

    rows = []
    pair_counts: Counter[tuple[str, str]] = Counter()
    rule_counts: Counter[str] = Counter()
    for item in items:
        eligible = _eligible(cfg, models, item)
        text = str(item.get("prompt") or "")
        kw = dict(
            phase=item["phase"],
            needs_tools=item["needs_tools"],
            tokens=item["tokens"],
            effort=EFFORT,
            allowed=None,
            spend_usd=0.0,
            budget_usd=BUDGET,
            text=text,
        )
        rules = select_model(cfg, models, **{k: v for k, v in kw.items() if k != "text"})
        trained = trained_select(cfg, models, artifact, **kw)
        ru_c = estimate_cost(rules.model, item["tokens"], COMPLETION_TOKENS)
        tr_c = estimate_cost(trained.model, item["tokens"], COMPLETION_TOKENS)
        d = tr_c - ru_c
        pair = (short(rules.model.id), short(trained.model.id))
        pair_counts[pair] += 1
        rule_counts[str(trained.rule or "none")] += 1
        rows.append(
            {
                "rules": rules.model.id,
                "trained": trained.model.id,
                "delta": d,
                "ru_c": ru_c,
                "tr_c": tr_c,
                "rule": trained.rule,
                "y_tr": success.get((item["prompt"], trained.model.id)),
                "y_ru": success.get((item["prompt"], rules.model.id)),
                "phase": item["phase"],
                "tokens": item["tokens"],
                "p": dict(trained.p_success or {}),
                "conf": trained.confidence,
            }
        )

    delta_pos = [r for r in rows if r["delta"] > 1e-12]
    delta_neg = [r for r in rows if r["delta"] < -1e-12]
    delta_zero = len(rows) - len(delta_pos) - len(delta_neg)
    sum_all = sum(r["delta"] for r in rows)
    sum_pos = sum(r["delta"] for r in delta_pos)
    sum_neg = sum(r["delta"] for r in delta_neg)

    lines.append("")
    lines.append("## Where trained is more expensive")
    lines.append("")
    lines.append(
        f"- n={len(rows)}; same-cost={delta_zero}; trained_more_expensive={len(delta_pos)}; "
        f"trained_cheaper={len(delta_neg)}"
    )
    lines.append(
        f"- mean Δ = `{sum_all / len(rows):+.6f}` (= rules_cost_delta); "
        f"positive mass `{sum_pos:+.6f}`; negative mass `{sum_neg:+.6f}`"
    )
    lines.append(f"- trained pick rules: `{dict(rule_counts)}`")
    lines.append("")
    lines.append("### Pair counts (rules → trained)")
    lines.append("")
    lines.append("| rules | trained | n | mean Δ | sum Δ |")
    lines.append("| --- | --- | ---: | ---: | ---: |")
    for (a, b), c in pair_counts.most_common():
        ds = [r["delta"] for r in rows if short(r["rules"]) == a and short(r["trained"]) == b]
        lines.append(
            f"| `{a}` | `{b}` | {c} | `{sum(ds)/len(ds):+.6f}` | `{sum(ds):+.6f}` |"
        )

    lines.append("")
    lines.append("### Concentration of positive Δ")
    lines.append("")
    pos_sorted = sorted((r["delta"] for r in delta_pos), reverse=True)
    lines.append("| top-k | sum Δ | % of positive mass |")
    lines.append("| ---: | ---: | ---: |")
    for k in [1, 3, 5, 10, 20, len(pos_sorted)]:
        if k > len(pos_sorted) or k < 1:
            continue
        cum = sum(pos_sorted[:k])
        lines.append(f"| {k} | `{cum:.6f}` | `{100 * cum / sum_pos:.1f}%` |")

    lines.append("")
    lines.append("### Top cost regressions")
    lines.append("")
    lines.append("| Δ | rules | trained | rule | y_tr | y_ru | conf |")
    lines.append("| ---: | --- | --- | --- | --- | --- | ---: |")
    for r in sorted(delta_pos, key=lambda x: -x["delta"])[:15]:
        lines.append(
            f"| `{r['delta']:+.6f}` | `{short(r['rules'])}` | `{short(r['trained'])}` | "
            f"`{r['rule']}` | `{r['y_tr']}` | `{r['y_ru']}` | `{float(r['conf'] or 0):.3f}` |"
        )

    n_pos = len(delta_pos)
    tr_wins = sum(1 for r in delta_pos if r["y_tr"])
    ru_wins = sum(1 for r in delta_pos if r["y_ru"])
    both = sum(1 for r in delta_pos if r["y_tr"] and r["y_ru"])
    neither = sum(1 for r in delta_pos if not r["y_tr"] and not r["y_ru"])
    tr_only = sum(1 for r in delta_pos if r["y_tr"] and not r["y_ru"])
    lines.append("")
    lines.append("### Quality on cost-regression hops")
    lines.append("")
    lines.append(
        f"n_pos={n_pos}; trained_success={tr_wins}; rules_success={ru_wins}; "
        f"both={both}; neither={neither}; trained_only={tr_only}"
    )

    # Model mix
    lines.append("")
    lines.append("### Selected model mix")
    lines.append("")
    tr_mix = Counter(short(r["trained"]) for r in rows)
    ru_mix = Counter(short(r["rules"]) for r in rows)
    lines.append("| model | rules n | trained n |")
    lines.append("| --- | ---: | ---: |")
    for mid in sorted(set(tr_mix) | set(ru_mix)):
        lines.append(f"| `{mid}` | {ru_mix[mid]} | {tr_mix[mid]} |")

    # Sweep
    lines.append("")
    lines.append("## Unpaid threshold / max_regret sweep")
    lines.append("")
    lines.append(
        "Override only `trained_effort.medium` on the frozen artifact. "
        "No retune on gold-verified. Gate = `apply_replay_gate`."
    )
    lines.append("")
    candidates = []
    for th in [0.05, 0.08, 0.10, 0.12, 0.15, 0.18, 0.20, 0.25, 0.30, 0.40, 0.50, 0.60]:
        for mr in [0.03, 0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.25, 0.30]:
            g = eval_knobs(cfg, models, artifact, items, success, th, mr)
            candidates.append((th, mr, g))

    ship = eval_knobs(cfg, models, artifact, items, success, 0.10, 0.20)
    lines.append(
        f"Ship ref: pass=`{ship['replay_gate_pass']}` rcd=`{ship['rules_cost_delta']:+.6f}` "
        f"auc=`{ship['rank_auc']:.4f}` bss=`{ship['brier_skill']:.6f}` "
        f"spread=`{ship['mean_p_spread']:.4f}` tr=`{ship['policies']['trained']['success_rate']:.4f}`"
    )
    lines.append("")

    passers = [(th, mr, g) for th, mr, g in candidates if g["replay_gate_pass"]]
    cheap_pass = [x for x in passers if x[2]["rules_cost_delta"] <= 0]
    lines.append(
        f"Grid size={len(candidates)}; gate_pass={len(passers)}; "
        f"gate_pass ∧ rcd≤0 = **{len(cheap_pass)}**"
    )
    lines.append("")

    if cheap_pass:
        lines.append("### Safe unpaid cost fixes (gate pass + rcd≤0)")
        lines.append("")
        lines.append("| t | r | rcd | auc | bss | spread | tr_success | savings |")
        lines.append("| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
        cheap_pass.sort(key=lambda x: x[2]["rules_cost_delta"])
        for th, mr, g in cheap_pass[:15]:
            lines.append(
                f"| {th:.2f} | {mr:.2f} | `{g['rules_cost_delta']:+.6f}` | "
                f"`{g['rank_auc']:.4f}` | `{g['brier_skill']:.6f}` | "
                f"`{g['mean_p_spread']:.4f}` | `{g['policies']['trained']['success_rate']:.4f}` | "
                f"`{g['savings_vs_most_expensive']:.6f}` |"
            )
    else:
        lines.append(
            "**No unpaid knob pair on this grid keeps `replay_gate_pass` and "
            "`rules_cost_delta ≤ 0`.**"
        )
        lines.append("")
        lines.append("### Best gate-pass by lowest rcd")
        lines.append("")
        lines.append("| t | r | rcd | auc | bss | spread | tr_success | ece_w |")
        lines.append("| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
        passers.sort(key=lambda x: x[2]["rules_cost_delta"])
        for th, mr, g in passers[:12]:
            lines.append(
                f"| {th:.2f} | {mr:.2f} | `{g['rules_cost_delta']:+.6f}` | "
                f"`{g['rank_auc']:.4f}` | `{g['brier_skill']:.6f}` | "
                f"`{g['mean_p_spread']:.4f}` | `{g['policies']['trained']['success_rate']:.4f}` | "
                f"`{g['ece_equal_width']:.4f}` |"
            )

    lines.append("")
    lines.append("### Lowest rcd overall (may fail gate)")
    lines.append("")
    lines.append("| t | r | pass | rcd | auc | bss | spread | tr_success |")
    lines.append("| ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |")
    by_rcd = sorted(candidates, key=lambda x: x[2]["rules_cost_delta"])
    for th, mr, g in by_rcd[:12]:
        lines.append(
            f"| {th:.2f} | {mr:.2f} | `{g['replay_gate_pass']}` | "
            f"`{g['rules_cost_delta']:+.6f}` | `{g['rank_auc']:.4f}` | "
            f"`{g['brier_skill']:.6f}` | `{g['mean_p_spread']:.4f}` | "
            f"`{g['policies']['trained']['success_rate']:.4f}` |"
        )

    # Verdict
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    if cheap_pass:
        th, mr, g = cheap_pass[0]
        lines.append(
            f"Safe unpaid overlay candidate exists: medium `threshold={th:.2f}` "
            f"`max_regret={mr:.2f}` with rcd=`{g['rules_cost_delta']:+.6f}` "
            f"and gate pass. Prefer shadow experiment artifact / config overlay; "
            f"do not overwrite serve candidate until all binding gates improve."
        )
    else:
        best = passers[0] if passers else by_rcd[0]
        th, mr, g = best
        lines.append(
            "Cost cannot be fixed unpaid via threshold/max_regret on this artifact "
            "without either failing `replay_gate_pass` or leaving `rules_cost_delta > 0`. "
            f"Best gate-pass rcd remains `{g['rules_cost_delta']:+.6f}` at t={th:.2f}/r={mr:.2f}."
        )
        lines.append("")
        lines.append(
            "Implication: the cost gap is structural to pick mix under ship knobs "
            "(trained spends into Kimi / Pro more often than rules), not a small "
            "knob miss. Next unpaid path: session-gold promotion scaffolding / "
            "non-pool label strategy — not more blind paid gym_alt/smith draws."
        )

    text = "\n".join(lines) + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(text.encode("ascii", errors="replace").decode("ascii"))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
