"""Offline replay report over frozen gold JSONL + Scorer artifact + rules picker."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from .metrics import (
    ECE_MAX,
    QUALITY_TOLERANCE,
    VERIFIED_N_FLOOR,
    brier_score,
    brier_skill_score,
    bss_passes,
    ece_equal_mass,
    ece_equal_width,
    ece_mass_is_gated,
    ece_mass_passes,
    ece_passes,
)
from .router import (
    Model,
    eligible_models,
    estimate_cost,
    load_config,
    load_models,
    select_model,
)
from .scorer import load_scorer, score_eligible, trained_select

COMPLETION_TOKENS = 800
SPARSE_N_FLOOR = 4000
BUDGET = 1_000_000.0
EFFORT = "medium"


def _load_gold(path: Path) -> tuple[list[dict[str, Any]], dict[tuple[str, str], bool]]:
    rows = [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    prompts: dict[str, dict[str, Any]] = {}
    success: dict[tuple[str, str], bool] = {}
    for row in rows:
        prompt = str(row["prompt"])
        prompts[prompt] = {
            "prompt": prompt,
            "phase": str(row.get("phase") or "plan"),
            "needs_tools": bool(row.get("needs_tools")),
            "tokens": int(row.get("tokens") or 100),
            "hint_bin": str(row.get("hint_bin") or "standard"),
        }
        if "model_id" in row and not row.get("unobserved"):
            success[(prompt, str(row["model_id"]))] = bool(row["success"])
    return list(prompts.values()), success


def assert_not_production_floors(
    gold_path: Path, artifact: dict[str, Any] | None = None
) -> None:
    """Fail if a unit test points replay at Verified n≥300 or staffed promotion bars."""
    items, _ = _load_gold(Path(gold_path))
    if len(items) >= VERIFIED_N_FLOOR:
        raise AssertionError("replay unit tests cannot use production floors (Verified n≥300)")
    if artifact is None:
        return
    if artifact.get("not_spec_floors") is False:
        raise AssertionError("replay unit tests cannot use staffed promotion bars")
    if int(artifact.get("n_gold") or 0) >= SPARSE_N_FLOOR:
        raise AssertionError("replay unit tests cannot use production floors (sparse n=4000)")


def _eligible(cfg: dict[str, Any], models: list[Model], item: dict[str, Any]) -> list[Model]:
    _, eligible = eligible_models(
        cfg,
        models,
        phase=item["phase"],
        needs_tools=item["needs_tools"],
        tokens=item["tokens"],
        effort=EFFORT,
        allowed=None,
        spend_usd=0.0,
        budget_usd=BUDGET,
    )
    return eligible


def _pick_flash(cfg: dict[str, Any], eligible: list[Model]) -> Model | None:
    fid = cfg.get("fallback_model")
    for m in eligible:
        if m.id == fid:
            return m
    return min(eligible, key=lambda m: m.unit_cost) if eligible else None


def _pick_cheapest(eligible: list[Model]) -> Model | None:
    return min(eligible, key=lambda m: m.unit_cost) if eligible else None


def _pick_strong(eligible: list[Model]) -> Model | None:
    return max(eligible, key=lambda m: (m.quality, m.unit_cost)) if eligible else None


def _pick_most_expensive(eligible: list[Model]) -> Model | None:
    return max(eligible, key=lambda m: m.unit_cost) if eligible else None


def _pick_oracle(
    eligible: list[Model], success: dict[tuple[str, str], bool], prompt: str
) -> Model | None:
    winners = [m for m in eligible if success.get((prompt, m.id))]
    return min(winners, key=lambda m: m.unit_cost) if winners else None


def _policy_stats(
    picks: list[tuple[Model | None, dict[str, Any]]],
    success: dict[tuple[str, str], bool],
) -> dict[str, float]:
    observed: list[bool] = []
    costs: list[float] = []
    for model, item in picks:
        if model is None:
            costs.append(0.0)
            observed.append(False)
            continue
        costs.append(estimate_cost(model, item["tokens"], COMPLETION_TOKENS))
        y = success.get((item["prompt"], model.id))
        if y is not None:
            observed.append(y)
    n = len(picks)
    return {
        "success_rate": (sum(observed) / len(observed)) if observed else 0.0,
        "list_price_cost": (sum(costs) / n) if n else 0.0,
    }


def _rank_auc(pairs: list[tuple[float, int]]) -> float:
    pos = [s for s, y in pairs if y == 1]
    neg = [s for s, y in pairs if y == 0]
    if not pos or not neg:
        return 0.5
    wins = sum(1.0 if p > n else 0.5 if p == n else 0.0 for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def _selected_cal(pairs: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    """Brier / BSS / dual ECE via metrics.py. Empty selected -> zeros (no raise)."""
    if not pairs:
        return 0.0, 0.0, 0.0, 0.0
    return (
        brier_score(pairs),
        brier_skill_score(pairs),
        ece_equal_width(pairs),
        ece_equal_mass(pairs),
    )


def replay_report(
    gold_path: Path,
    artifact: dict[str, Any],
    models: list[Model],
    cfg: dict[str, Any],
    holdout_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    items, success = _load_gold(Path(gold_path))
    if holdout_ids is not None:
        wanted = set(holdout_ids)
        items = [it for it in items if it["prompt"] in wanted]

    rules_picks: list[tuple[Model | None, dict[str, Any]]] = []
    trained_picks: list[tuple[Model | None, dict[str, Any]]] = []
    flash_picks: list[tuple[Model | None, dict[str, Any]]] = []
    cheapest_picks: list[tuple[Model | None, dict[str, Any]]] = []
    strong_picks: list[tuple[Model | None, dict[str, Any]]] = []
    expensive_picks: list[tuple[Model | None, dict[str, Any]]] = []
    oracle_picks: list[tuple[Model | None, dict[str, Any]]] = []
    disagree = 0
    rules_ne_cheapest = 0
    auc_pairs: list[tuple[float, int]] = []
    spreads: list[float] = []
    selected: list[tuple[float, float]] = []
    hop_savings: list[float] = []
    meaningful_cost_deltas: list[float] = []

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
        cheapest = _pick_cheapest(eligible)
        expensive = _pick_most_expensive(eligible)
        rules_picks.append((rules.model, item))
        trained_picks.append((trained.model, item))
        flash_picks.append((_pick_flash(cfg, eligible), item))
        cheapest_picks.append((cheapest, item))
        strong_picks.append((_pick_strong(eligible), item))
        expensive_picks.append((expensive, item))
        oracle_picks.append((_pick_oracle(eligible, success, item["prompt"]), item))
        if rules.model.id != trained.model.id:
            disagree += 1
        tr_cost = estimate_cost(trained.model, item["tokens"], COMPLETION_TOKENS)
        if expensive is not None:
            exp_cost = estimate_cost(expensive, item["tokens"], COMPLETION_TOKENS)
            hop_savings.append(max(0.0, exp_cost - tr_cost))
        if rules.model and cheapest and rules.model.id != cheapest.id:
            rules_ne_cheapest += 1
            ru_cost = estimate_cost(rules.model, item["tokens"], COMPLETION_TOKENS)
            meaningful_cost_deltas.append(tr_cost - ru_cost)

        ids = [m.id for m in eligible if (item["prompt"], m.id) in success]
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
        for mid in ids:
            if mid not in ps:
                continue
            auc_pairs.append((float(ps[mid]), 1 if success[(item["prompt"], mid)] else 0))
        y = success.get((item["prompt"], trained.model.id))
        if trained.confidence is not None and y is not None:
            selected.append((float(trained.confidence), 1.0 if y else 0.0))

    n = len(items)
    policies = {
        "rules": _policy_stats(rules_picks, success),
        "trained": _policy_stats(trained_picks, success),
        "oracle": _policy_stats(oracle_picks, success),
        "always_flash": _policy_stats(flash_picks, success),
        "always_cheapest": _policy_stats(cheapest_picks, success),
        "always_strong": _policy_stats(strong_picks, success),
        "always_most_expensive": _policy_stats(expensive_picks, success),
    }
    brier, brier_skill, ece_w, ece_m = _selected_cal(selected)
    out = {
        "n_prompts": n,
        "n_selected": len(selected),
        "gold_is_holdout": True,
        "policies": policies,
        "disagreement_rate": (disagree / n) if n else 0.0,
        "rank_auc": _rank_auc(auc_pairs),
        "mean_p_spread": (sum(spreads) / len(spreads)) if spreads else 0.0,
        "brier": brier,
        "brier_skill": brier_skill,
        "ece_equal_width": ece_w,
        "ece_equal_mass": ece_m,
        "rules_cost_delta": policies["trained"]["list_price_cost"]
        - policies["rules"]["list_price_cost"],
        "rules_ne_cheapest_rate": (rules_ne_cheapest / n) if n else 0.0,
        "rules_cost_delta_where_rules_ne_cheapest": (
            (sum(meaningful_cost_deltas) / len(meaningful_cost_deltas))
            if meaningful_cost_deltas
            else None
        ),
        "savings_vs_most_expensive": (sum(hop_savings) / len(hop_savings))
        if hop_savings
        else 0.0,
    }
    return apply_replay_gate(out)


def _cost_src(report: dict[str, Any]) -> dict[str, Any]:
    cost = report.get("cost_slice")
    return cost if isinstance(cost, dict) else report


def _always_cheap_without_quality(report: dict[str, Any]) -> bool:
    """Fail trained ≡ always-cheapest/Flash unless cheapest also matches quality."""
    trained = report["policies"]["trained"]
    cheap = report["policies"].get("always_cheapest", report["policies"]["always_flash"])
    flash = report["policies"]["always_flash"]
    if trained != cheap and trained != flash:
        return False
    rules_s = report["policies"]["rules"]["success_rate"]
    cheap_s = cheap["success_rate"]
    if cheap_s < rules_s - QUALITY_TOLERANCE:
        return True
    strong = report["policies"].get("always_strong")
    if strong and strong["success_rate"] > cheap_s + QUALITY_TOLERANCE:
        return True
    return False


def _cost_ok(report: dict[str, Any]) -> bool:
    """Savings vs most_expensive_eligible. rules_cost_delta is reported, never named savings."""
    src = _cost_src(report)
    return float(src.get("savings_vs_most_expensive") or 0.0) > 0.0


def parity_blockers(report: dict[str, Any]) -> list[str]:
    """Production parity gaps even when shadow-local replay_gate_pass is true."""
    blockers: list[str] = []
    if report.get("not_spec_floors", True):
        blockers.append("not_spec_floors")
    n_prompts = int(report.get("n_prompts") or 0)
    if n_prompts < VERIFIED_N_FLOOR:
        blockers.append(f"eval_n={n_prompts}_below_verified_floor_{VERIFIED_N_FLOOR}")
    if float(report.get("rules_cost_delta") or 0.0) >= 0.0:
        blockers.append("rules_cost_delta_not_negative")
    ece_mass = float(report.get("ece_equal_mass") or 0.0)
    if report.get("ece_equal_mass_gated") and ece_mass > ECE_MAX:
        blockers.append("ece_equal_mass_above_bar")
    elif not report.get("ece_equal_mass_gated") and ece_mass > ECE_MAX:
        blockers.append("ece_equal_mass_waived_small_n")
    blockers.append("no_session_gold_promotion_gate")
    return blockers


def parity_posture(report: dict[str, Any]) -> dict[str, Any]:
    """Separate shadow-local replay pass from production parity."""
    local_pass = bool(report.get("replay_gate_pass"))
    return {
        "local_replay_gate_pass": local_pass,
        "production_parity": False,
        "promotion_tier": "shadow_local_pass" if local_pass else "shadow_local_fail",
        "parity_blockers": parity_blockers(report),
    }


def replay_gate_pass(report: dict[str, Any]) -> bool:
    """Transfer bars from primary report; Pioneer cost from cost_slice when present."""
    trained_s = report["policies"]["trained"]["success_rate"]
    rules_s = report["policies"]["rules"]["success_rate"]
    n_cal = int(report.get("n_selected") or report.get("n_prompts") or 10**9)
    return (
        report["rank_auc"] >= 0.65
        and report["mean_p_spread"] >= 0.10
        and bss_passes(float(report["brier_skill"]))
        and ece_passes(float(report["ece_equal_width"]))
        and ece_mass_passes(float(report["ece_equal_mass"]), n_selected=n_cal)
        and trained_s >= rules_s - QUALITY_TOLERANCE
        and _cost_ok(report)
        and not _always_cheap_without_quality(report)
    )


def apply_replay_gate(report: dict[str, Any]) -> dict[str, Any]:
    """Failing any bar keeps shadow and not_spec_floors. Never stamps Verified or flips path."""
    out = dict(report)
    n_cal = int(out.get("n_selected") or out.get("n_prompts") or 10**9)
    out["ece_equal_mass_gated"] = ece_mass_is_gated(n_cal)
    out["replay_gate_pass"] = replay_gate_pass(out)
    out["path"] = "shadow"
    out["not_spec_floors"] = True
    out.update(parity_posture(out))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline replay report (no live provider)")
    parser.add_argument(
        "--gold",
        required=True,
        help=(
            "Eval-only holdout gold JSONL (typically frozen verified). Unused for train/cal; "
            "passing mixed gold contaminates the gate. No hash split."
        ),
    )
    parser.add_argument(
        "--cost-gold",
        help=(
            "Disjoint bootstrap holdout for Pioneer cost (savings vs most_expensive_eligible). "
            "rules_cost_delta is reported only where rules ≠ cheapest. Unused for fit."
        ),
    )
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--models", default="config/models.yaml")
    args = parser.parse_args(argv)
    cfg = load_config(Path(args.models))
    artifact = load_scorer(Path(args.artifact))
    if artifact is None:
        return 2
    report = replay_report(Path(args.gold), artifact, load_models(cfg), cfg)
    if args.cost_gold:
        report["cost_slice"] = replay_report(
            Path(args.cost_gold), artifact, load_models(cfg), cfg
        )
        # Re-stamp gate so cost bars use cost_slice (transfer bars stay on --gold).
        report = apply_replay_gate(report)
    print(json.dumps(report, indent=2))
    print("replay_gate_pass", report["replay_gate_pass"])
    print("local_replay_gate_pass", report.get("local_replay_gate_pass"))
    print("production_parity", report.get("production_parity"))
    print("promotion_tier", report.get("promotion_tier"))
    print(f"path={report['path']}")
    print("not_spec_floors", report["not_spec_floors"])
    blockers = report.get("parity_blockers") or []
    if blockers:
        print("parity_blockers", ",".join(blockers))
    print("savings_vs_most_expensive", report.get("savings_vs_most_expensive"))
    print(
        "rules_cost_delta_where_rules_ne_cheapest",
        report.get("rules_cost_delta_where_rules_ne_cheapest"),
    )
    if args.cost_gold:
        print(
            "cost_slice rules_ne_cheapest_rate",
            report["cost_slice"]["rules_ne_cheapest_rate"],
        )
        print(
            "cost_slice rules_cost_delta",
            report["cost_slice"]["rules_cost_delta"],
        )
        print(
            "cost_slice savings_vs_most_expensive",
            report["cost_slice"].get("savings_vs_most_expensive"),
        )
    if artifact.get("gbdt"):
        print(
            "prefer_logistic=true use --artifact data/scorer-logistic.json "
            "until train-eval spearman > 0"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
