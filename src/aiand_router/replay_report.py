"""Offline replay report over frozen gold JSONL + Scorer artifact + rules picker."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

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
VERIFIED_N_FLOOR = 300
SPARSE_N_FLOOR = 4000
BUDGET = 1_000_000.0
EFFORT = "medium"
# Equal-mass ECE with m=10 on n≈90 selected hops has a high noise floor when
# within-selected P has few distinct levels (oracle phase rates still ECE_m≈0.19).
# Keep equal-width + Brier skill; report equal-mass but do not gate on it below this n.
SMALL_N_ECE_MASS = 150


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


def _brier(pairs: list[tuple[float, float]]) -> float:
    if not pairs:
        return 0.0
    return sum((p - y) ** 2 for p, y in pairs) / len(pairs)


def _brier_skill(pairs: list[tuple[float, float]]) -> float:
    if not pairs:
        return 0.0
    ybar = sum(y for _, y in pairs) / len(pairs)
    bs_ref = sum((ybar - y) ** 2 for _, y in pairs) / len(pairs)
    if bs_ref == 0.0:
        return 0.0
    return 1.0 - _brier(pairs) / bs_ref


def _ece_equal_width(pairs: list[tuple[float, float]], m: int = 10) -> float:
    if not pairs:
        return 0.0
    bins: list[list[tuple[float, float]]] = [[] for _ in range(m)]
    for p, y in pairs:
        bins[min(int(p * m), m - 1)].append((p, y))
    n = len(pairs)
    return sum(
        (len(b) / n) * abs(sum(y for _, y in b) / len(b) - sum(p for p, _ in b) / len(b))
        for b in bins
        if b
    )


def _ece_equal_mass(pairs: list[tuple[float, float]], m: int = 10) -> float:
    if not pairs:
        return 0.0
    ordered = sorted(pairs, key=lambda py: py[0])
    n = len(ordered)
    m = min(m, n)
    ece = 0.0
    for i in range(m):
        b = ordered[i * n // m : (i + 1) * n // m]
        if not b:
            continue
        acc = sum(y for _, y in b) / len(b)
        conf = sum(p for p, _ in b) / len(b)
        ece += (len(b) / n) * abs(acc - conf)
    return ece


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
    oracle_picks: list[tuple[Model | None, dict[str, Any]]] = []
    disagree = 0
    rules_ne_cheapest = 0
    auc_pairs: list[tuple[float, int]] = []
    spreads: list[float] = []
    selected: list[tuple[float, float]] = []

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
        rules_picks.append((rules.model, item))
        trained_picks.append((trained.model, item))
        flash_picks.append((_pick_flash(cfg, eligible), item))
        cheapest_picks.append((cheapest, item))
        strong_picks.append((_pick_strong(eligible), item))
        oracle_picks.append((_pick_oracle(eligible, success, item["prompt"]), item))
        if rules.model.id != trained.model.id:
            disagree += 1
        if rules.model and cheapest and rules.model.id != cheapest.id:
            rules_ne_cheapest += 1

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
    }
    out = {
        "n_prompts": n,
        "n_selected": len(selected),
        "gold_is_holdout": True,
        "policies": policies,
        "disagreement_rate": (disagree / n) if n else 0.0,
        "rank_auc": _rank_auc(auc_pairs),
        "mean_p_spread": (sum(spreads) / len(spreads)) if spreads else 0.0,
        "brier": _brier(selected),
        "brier_skill": _brier_skill(selected),
        "ece_equal_width": _ece_equal_width(selected),
        "ece_equal_mass": _ece_equal_mass(selected),
        "rules_cost_delta": policies["trained"]["list_price_cost"]
        - policies["rules"]["list_price_cost"],
        "rules_ne_cheapest_rate": (rules_ne_cheapest / n) if n else 0.0,
    }
    return apply_replay_gate(out)


def replay_gate_pass(report: dict[str, Any]) -> bool:
    """Transfer bars from primary report; cost bar from cost_slice when present."""
    trained_s = report["policies"]["trained"]["success_rate"]
    rules_s = report["policies"]["rules"]["success_rate"]
    always_cheapest = report["policies"].get(
        "always_cheapest", report["policies"]["always_flash"]
    )
    cost_delta = report["rules_cost_delta"]
    cost = report.get("cost_slice")
    if isinstance(cost, dict):
        # Judge cost vs rules on the cost-meaningful bootstrap, not H3 verified.
        if float(cost.get("rules_ne_cheapest_rate") or 0.0) <= 0.0:
            return False
        cost_delta = float(cost["rules_cost_delta"])
    n_cal = int(report.get("n_selected") or report.get("n_prompts") or 10**9)
    ece_mass_ok = report["ece_equal_mass"] <= 0.03 or n_cal < SMALL_N_ECE_MASS
    return (
        report["rank_auc"] >= 0.65
        and report["mean_p_spread"] >= 0.10
        and report["brier_skill"] > 0
        and report["ece_equal_width"] <= 0.03
        and ece_mass_ok
        and trained_s >= rules_s - 0.01
        and cost_delta < 0
        and report["policies"]["trained"] != always_cheapest
    )


def apply_replay_gate(report: dict[str, Any]) -> dict[str, Any]:
    """Failing any bar keeps shadow and not_spec_floors. Never stamps Verified or flips path."""
    out = dict(report)
    n_cal = int(out.get("n_selected") or out.get("n_prompts") or 10**9)
    out["ece_equal_mass_gated"] = n_cal >= SMALL_N_ECE_MASS
    out["replay_gate_pass"] = replay_gate_pass(out)
    out["path"] = "shadow"
    out["not_spec_floors"] = True
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
            "Disjoint bootstrap holdout where rules may disagree with cheapest-eligible. "
            "Judge cost_delta here; do not rewrite verified bars. Unused for fit."
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
    print(f"path={report['path']}")
    print("not_spec_floors", report["not_spec_floors"])
    if args.cost_gold:
        print(
            "cost_slice rules_ne_cheapest_rate",
            report["cost_slice"]["rules_ne_cheapest_rate"],
        )
        print(
            "cost_slice rules_cost_delta",
            report["cost_slice"]["rules_cost_delta"],
        )
    if artifact.get("gbdt"):
        print(
            "prefer_logistic=true use --artifact data/scorer-logistic.json "
            "until train-eval spearman > 0"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
