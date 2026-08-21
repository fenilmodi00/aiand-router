"""Hop Orchestrator: one Decision pick for every wire adapter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .learn import learned_enabled, learned_select_from_eligible
from .router import (
    VIRTUAL_MODELS,
    Decision,
    EligibleSet,
    Model,
    build_eligible_set,
    estimate_cost,
    select_from_eligible,
)
from .scorer import (
    apply_trained_path,
    cascade_select_from_eligible,
    trained_select_from_eligible,
)


@dataclass
class HopResult:
    decision: Decision
    sticky_hit: bool
    tip_msg: str | None = None
    pinned: bool = False


@dataclass(frozen=True)
class PathRequest:
    cfg: dict[str, Any]
    catalog: list[Model]
    by_id: dict[str, Model]
    phase: str
    effort: str
    tokens: int
    pick_kwargs: dict[str, Any]
    prompt_text: str
    scorer_artifact: dict[str, Any] | None
    hop_path: str


class PathPolicy(Protocol):
    """Pick a Decision from a shared Eligible set."""

    def pick(self, eligible: EligibleSet, req: PathRequest) -> Decision:
        ...


class RulesPathPolicy:
    """Pioneer select_model over the Eligible set."""

    def pick(self, eligible: EligibleSet, req: PathRequest) -> Decision:
        return select_from_eligible(
            req.cfg,
            eligible,
            phase=req.phase,
            effort=req.effort,
            tokens=req.tokens,
            catalog=req.catalog,
            multi_turn=bool(req.pick_kwargs.get("multi_turn", True)),
        )


class LearnedStubPathPolicy:
    """Learned stub over the Eligible set."""

    def pick(self, eligible: EligibleSet, req: PathRequest) -> Decision:
        return learned_select_from_eligible(
            req.cfg, eligible, phase=req.phase, catalog=req.catalog
        )


class ScorerPathPolicy:
    """Scorer cascade (path=off) or trained/shadow via apply_trained_path."""

    def __init__(self, base: PathPolicy) -> None:
        self._base = base

    def pick(self, eligible: EligibleSet, req: PathRequest) -> Decision:
        needs_tools = bool(req.pick_kwargs.get("needs_tools"))
        allowed = req.pick_kwargs.get("allowed")
        if req.hop_path == "off":
            if req.scorer_artifact is not None:
                cascade = cascade_select_from_eligible(
                    req.cfg,
                    eligible,
                    req.scorer_artifact,
                    phase=req.phase,
                    needs_tools=needs_tools,
                    tokens=req.tokens,
                    effort=req.effort,
                    allowed=allowed,
                    text=req.prompt_text,
                )
                if cascade is not None:
                    return cascade
            return self._base.pick(eligible, req)

        rules = self._base.pick(eligible, req)
        trained = None
        if req.scorer_artifact is not None:
            trained = trained_select_from_eligible(
                req.cfg,
                eligible,
                req.scorer_artifact,
                phase=req.phase,
                needs_tools=needs_tools,
                tokens=req.tokens,
                effort=req.effort,
                catalog=req.catalog,
                text=req.prompt_text,
            )
        return apply_trained_path(
            req.hop_path, rules, trained, tokens=req.tokens, by_id=req.by_id
        )


def _base_policy(hop_path: str, flag_path: Path) -> PathPolicy:
    if hop_path == "off" and learned_enabled(flag_path):
        return LearnedStubPathPolicy()
    return RulesPathPolicy()


def _path_policy(
    hop_path: str, flag_path: Path, scorer_artifact: dict[str, Any] | None
) -> PathPolicy:
    base = _base_policy(hop_path, flag_path)
    if hop_path != "off" or scorer_artifact is not None:
        return ScorerPathPolicy(base)
    return base


class ConversationSticky:
    """Reuse the auto-route pick within a conversation key."""

    def __init__(self, by_id: dict[str, Model]) -> None:
        self._by_id = by_id
        self._route: dict[tuple[str, str, str, str], str] = {}

    def apply(
        self,
        decision: Decision,
        *,
        session_id: str,
        effort: str,
        allowed: set[str] | None,
        pinned: bool,
        req_hop_path: str,
    ) -> bool:
        if pinned or not session_id:
            return False
        key = (session_id, effort, ",".join(sorted(allowed or ())), req_hop_path)
        prev = self._route.get(key)
        if prev and prev in self._by_id and (allowed is None or prev in allowed):
            if prev != decision.model.id:
                decision.model = self._by_id[prev]
                # Fresh score's savings belong to a different pick; avoid lying
                # in X-Router-Savings-Usd until post-call recompute.
                decision.savings_usd = None
            codes = list(decision.reason_codes or [])
            if "conversation_sticky" not in codes:
                codes.append("conversation_sticky")
            decision.reason_codes = codes
            return True
        self._route[key] = decision.model.id
        return False


def route_hop(
    *,
    requested: str,
    phase: str,
    effort: str,
    req_hop_path: str,
    select_cfg: dict[str, Any],
    models: list[Model],
    by_id: dict[str, Model],
    pick_kwargs: dict[str, Any],
    prompt_text: str,
    tokens: int,
    scorer_artifact: dict[str, Any] | None,
    flag_path: Path,
    session_id: str,
    allowed: set[str] | None,
    sticky: ConversationSticky,
    with_pin_tip: bool = False,
) -> HopResult:
    """Pick via shared Eligible set + PathPolicy, then conversation sticky.

    Wire adapters translate body/headers only; path policy lives here.
    """
    tip_msg: str | None = None
    pinned = requested not in VIRTUAL_MODELS and requested in by_id
    eligible = build_eligible_set(select_cfg, models, **pick_kwargs)
    req = PathRequest(
        cfg=select_cfg,
        catalog=models,
        by_id=by_id,
        phase=phase,
        effort=effort,
        tokens=tokens,
        pick_kwargs=pick_kwargs,
        prompt_text=prompt_text,
        scorer_artifact=scorer_artifact,
        hop_path=req_hop_path,
    )
    if pinned:
        decision_model = by_id[requested]
        decision = Decision(
            model=decision_model,
            phase=phase,
            threshold=0,
            reason=f"client pinned {requested}",
            candidates=[requested],
        )
        if with_pin_tip:
            auto_dec = RulesPathPolicy().pick(eligible, req)
            if auto_dec.model.unit_cost < decision_model.unit_cost:
                pot_savings = max(
                    0.0,
                    estimate_cost(decision_model, tokens, 800)
                    - estimate_cost(auto_dec.model, tokens, 800),
                )
                tip_msg = (
                    f"Using router/auto would have saved ${pot_savings:.4f} "
                    f"(routed to {auto_dec.model.id})"
                )
    else:
        policy = _path_policy(req_hop_path, flag_path, scorer_artifact)
        decision = policy.pick(eligible, req)
        decision.effort = effort

    sticky_hit = sticky.apply(
        decision,
        session_id=session_id,
        effort=effort,
        allowed=allowed,
        pinned=pinned,
        req_hop_path=req_hop_path,
    )
    return HopResult(
        decision=decision,
        sticky_hit=sticky_hit,
        tip_msg=tip_msg,
        pinned=pinned,
    )
