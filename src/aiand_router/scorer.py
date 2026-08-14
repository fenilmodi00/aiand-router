"""Features-only Scorer + cheapest-above-bar pick. Fixture JSON is enough for v1."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .router import (
    PHASE_FAMILY,
    Decision,
    Model,
    eligible_models,
    estimate_cost,
    fallback_decision,
    stamp_baseline,
)

SHIP_EFFORT = {
    "low": {"threshold": 0.05, "max_regret": 0.30},
    "medium": {"threshold": 0.10, "max_regret": 0.20},
    "high": {"threshold": 0.20, "max_regret": 0.15},
    "max": {"threshold": 0.60, "max_regret": 0.03},
}
FAMILIES = ("discover", "plan", "edit", "tool", "debug", "summarize")
BINS = ("trivial", "standard", "hard", "frontier")


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
    if not isinstance(data, dict):
        return None
    if "p_success" not in data and "weights" not in data:
        return None
    return data


def featurize(phase: str, needs_tools: bool, tokens: int) -> list[float]:
    fam = PHASE_FAMILY.get(phase, "plan")
    return [
        1.0,
        1.0 if needs_tools else 0.0,
        math.log1p(max(0, tokens)),
        *[1.0 if fam == f else 0.0 for f in FAMILIES],
    ]


def _sigmoid(z: float) -> float:
    z = max(-30.0, min(30.0, z))
    return 1.0 / (1.0 + math.exp(-z))


def _dot(w: list[float], x: list[float]) -> float:
    n = min(len(w), len(x))
    return sum(float(w[i]) * x[i] for i in range(n))


def score_eligible(
    artifact: dict[str, Any],
    eligible_ids: list[str],
    *,
    phase: str = "plan",
    needs_tools: bool = False,
    tokens: int = 1,
) -> tuple[str, dict[str, float]]:
    weights = artifact.get("weights")
    if isinstance(weights, dict) and weights:
        x = featurize(phase, needs_tools, tokens)
        bin_w = artifact.get("bin_weights") or {}
        bin_ = max(BINS, key=lambda b: _dot(list(bin_w.get(b) or []), x))
        platt = artifact.get("platt") or {}
        a = float(platt.get("a", 1.0))
        b = float(platt.get("b", 0.0))
        p_success = {}
        for i in eligible_ids:
            w = weights.get(i)
            if not w:
                continue
            p_success[i] = _sigmoid(a * _dot([float(v) for v in w], x) + b)
        return bin_, p_success
    raw = artifact.get("p_success") or {}
    p_success = {i: float(raw[i]) for i in eligible_ids if i in raw}
    bin_ = str(artifact.get("complexity_bin") or "standard")
    if bin_ not in BINS:
        bin_ = "standard"
    return bin_, p_success


def effort_knobs(cfg: dict[str, Any], effort: str) -> tuple[float, float]:
    table = cfg.get("trained_effort") or SHIP_EFFORT
    row = table.get(effort) if effort in SHIP_EFFORT else None
    if not row:
        row = table.get("medium") or SHIP_EFFORT["medium"]
    return float(row["threshold"]), float(row["max_regret"])


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
    bin_, p_success = score_eligible(
        artifact,
        [m.id for m in eligible],
        phase=phase,
        needs_tools=needs_tools,
        tokens=tokens,
    )
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
        fb.reason_codes = [f"bin:{bin_}", f"decline:{rule}"]
        fb.candidates = [m.id for m in eligible]
        stamp_baseline(fb, eligible, tokens)
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
    stamp_baseline(decision, eligible, tokens)
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


