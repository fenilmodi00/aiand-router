"""Features-only Scorer + cheapest-above-bar pick. Fixture JSON is enough for v1."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .router import Decision, Model, eligible_models, fallback_decision, estimate_cost

SHIP_EFFORT = {
    "low": {"threshold": 0.05, "max_regret": 0.30},
    "medium": {"threshold": 0.10, "max_regret": 0.20},
    "high": {"threshold": 0.20, "max_regret": 0.15},
    "max": {"threshold": 0.60, "max_regret": 0.03},
}


def parse_trained_path(raw: str | None) -> str:
    value = (raw or "shadow").strip().lower()
    return value if value in {"off", "shadow", "trained"} else "shadow"


def load_scorer(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or "p_success" not in data:
        return None
    return data


def effort_knobs(cfg: dict[str, Any], effort: str) -> tuple[float, float]:
    table = cfg.get("trained_effort") or SHIP_EFFORT
    row = table.get(effort) or table.get("medium") or SHIP_EFFORT["medium"]
    return float(row["threshold"]), float(row["max_regret"])


def score_eligible(artifact: dict[str, Any], eligible_ids: list[str]) -> tuple[str, dict[str, float]]:
    raw = artifact.get("p_success") or {}
    p_success = {i: float(raw[i]) for i in eligible_ids if i in raw}
    bin_ = str(artifact.get("complexity_bin") or "standard")
    if bin_ not in {"trivial", "standard", "hard", "frontier"}:
        bin_ = "standard"
    return bin_, p_success


def pick_cheapest_above_bar(
    eligible: list[Model],
    p_success: dict[str, float],
    *,
    threshold: float,
    max_regret: float,
) -> tuple[Model | None, str]:
    scored = [(m, p_success[m.id]) for m in eligible if m.id in p_success]
    if not scored:
        return None, "fallback_declined"
    top_p = max(p for _, p in scored)
    above = [(m, p) for m, p in scored if p >= threshold]
    if not above:
        return None, "fallback_declined"
    within = [(m, p) for m, p in above if (top_p - p) <= max_regret]
    if not within:
        return None, "fallback_declined"
    within.sort(key=lambda mp: (mp[0].unit_cost, -mp[1]))
    dropped_regret = any((top_p - p) > max_regret for _, p in above)
    rule = "max_regret" if dropped_regret else "threshold"
    return within[0][0], rule


def trained_select(
    cfg: dict[str, Any],
    models: list[Model],
    artifact: dict[str, Any],
    *,
    phase: str,
    needs_tools: bool,
    tokens: int,
    effort: str,
    allowed: set[str] | None,
    spend_usd: float,
    budget_usd: float,
    needs_json: bool = False,
    streaming: bool = False,
    max_tokens: int | None = None,
    latency_limit_ms: float | None = None,
) -> Decision:
    aa_bar, eligible = eligible_models(
        cfg,
        models,
        phase=phase,
        needs_tools=needs_tools,
        tokens=tokens,
        effort=effort,
        allowed=allowed,
        spend_usd=spend_usd,
        budget_usd=budget_usd,
        needs_json=needs_json,
        streaming=streaming,
        max_tokens=max_tokens,
        latency_limit_ms=latency_limit_ms,
    )
    t, regret = effort_knobs(cfg, effort)
    bin_, p_success = score_eligible(artifact, [m.id for m in eligible])
    chosen, rule = pick_cheapest_above_bar(eligible, p_success, threshold=t, max_regret=regret)
    if chosen is None:
        fb = fallback_decision(cfg, models, phase, aa_bar)
        fb.path = "trained"
        fb.effort = effort
        fb.rule = "fallback_declined"
        fb.complexity_bin = bin_
        fb.p_success = p_success
        fb.threshold = t
        fb.max_regret = regret
        fb.reason_codes = [f"bin:{bin_}", "decline:below_threshold"]
        fb.candidates = [m.id for m in eligible]
        _stamp_baseline(fb, eligible, tokens)
        return fb
    conf = p_success.get(chosen.id)
    codes = [f"bin:{bin_}", "pick:cheapest_above_bar"]
    if rule == "max_regret":
        codes.append("pick:cheapest_within_regret")
    decision = Decision(
        model=chosen,
        phase=phase,
        threshold=t,
        reason="",
        candidates=[m.id for m in eligible],
        effort=effort,
        path="trained",
        rule=rule,
        complexity_bin=bin_,
        confidence=conf,
        p_success=p_success,
        max_regret=regret,
        reason_codes=codes,
    )
    _stamp_baseline(decision, eligible, tokens)
    return decision


def apply_trained_path(
    hop_path: str,
    rules: Decision,
    trained: Decision | None,
    *,
    tokens: int,
    by_id: dict[str, Model] | None = None,
) -> Decision:
    if hop_path == "off":
        return rules
    if trained is None:
        rules.path = "rules"
        rules.rule = "fallback_declined"
        rules.reason_codes = ["scorer_down"]
        rules.confidence = None
        rules.complexity_bin = None
        return rules
    if hop_path == "trained":
        trained.path = "trained"
        trained.rules_cost_delta_usd = round(
            estimate_cost(trained.model, tokens, 800) - estimate_cost(rules.model, tokens, 800),
            6,
        )
        return trained
    rules.path = "shadow"
    rules.trained_selected = trained.model.id
    rules.trained_confidence = trained.confidence
    rules.complexity_bin = trained.complexity_bin
    rules.confidence = trained.confidence
    rules.rule = trained.rule
    rules.p_success = trained.p_success
    rules.threshold = trained.threshold
    rules.max_regret = trained.max_regret
    rules.reason_codes = list(trained.reason_codes or []) + ["shadow:rules_serving"]
    rules.baseline_model_id = trained.baseline_model_id
    rules.candidates = trained.candidates
    rules.effort = trained.effort
    if trained.baseline_model_id and by_id and trained.baseline_model_id in by_id:
        base = by_id[trained.baseline_model_id]
        rules.savings_usd = round(
            max(0.0, estimate_cost(base, tokens, 800) - estimate_cost(rules.model, tokens, 800)),
            6,
        )
    rules.rules_cost_delta_usd = round(
        estimate_cost(trained.model, tokens, 800) - estimate_cost(rules.model, tokens, 800),
        6,
    )
    return rules


def _stamp_baseline(decision: Decision, eligible: list[Model], tokens: int) -> None:
    if not eligible:
        return
    baseline = max(eligible, key=lambda m: m.unit_cost)
    decision.baseline_model_id = baseline.id
    est_sel = estimate_cost(decision.model, tokens, 800)
    est_base = estimate_cost(baseline, tokens, 800)
    decision.savings_usd = round(max(0.0, est_base - est_sel), 6)
