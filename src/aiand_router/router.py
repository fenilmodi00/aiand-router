from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

SHORT_PHASES = ("discover", "plan", "edit", "tool", "debug", "summarize")
DRAFT_PHASES = (
    "intent",
    "repository_discovery",
    "repository_summary",
    "planning",
    "code_generation",
    "code_edit",
    "tool_call",
    "test_execution",
    "test_failure_analysis",
    "debugging",
    "refactoring",
    "security_review",
    "final_summary",
)
PHASES = SHORT_PHASES + DRAFT_PHASES
VIRTUAL_MODELS = {"router/auto", "aiand-router", "auto"}
PHASE_FAMILY = {
    "discover": "discover",
    "repository_discovery": "discover",
    "repository_summary": "discover",
    "plan": "plan",
    "intent": "plan",
    "planning": "plan",
    "edit": "edit",
    "code_generation": "edit",
    "code_edit": "edit",
    "refactoring": "edit",
    "tool": "tool",
    "tool_call": "tool",
    "test_execution": "tool",
    "debug": "debug",
    "debugging": "debug",
    "test_failure_analysis": "debug",
    "summarize": "summarize",
    "final_summary": "summarize",
    "security_review": "plan",
}
DEBUG_PHASES = {"debug", "debugging", "test_failure_analysis"}

_TOOL_PHASE = {
    "read": "discover",
    "read_file": "discover",
    "glob": "discover",
    "grep": "discover",
    "list": "discover",
    "list_dir": "discover",
    "search": "discover",
    "write": "edit",
    "write_file": "edit",
    "str_replace": "edit",
    "apply_patch": "edit",
    "edit": "edit",
    "bash": "tool",
    "shell": "tool",
    "run": "tool",
}


@dataclass(frozen=True)
class Model:
    id: str
    display_name: str
    enabled: bool
    input_per_1m: float
    output_per_1m: float
    context_window: int
    supports_tools: bool
    supports_json: bool
    supports_streaming: bool
    max_output_tokens: int | None
    cached_input_per_1m: float | None
    aa_index: float | None
    aa_source: str
    measured_on: str
    measured_success: float | None
    latency_ms: float
    health: float
    priors: dict[str, float] | None

    @property
    def quality(self) -> float:
        if self.measured_success is not None:
            return self.measured_success * 100
        return float(self.aa_index or 0)

    @property
    def unit_cost(self) -> float:
        inp = self.cached_input_per_1m if self.cached_input_per_1m is not None else self.input_per_1m
        return inp * 0.4 + self.output_per_1m * 0.6


@dataclass
class Decision:
    model: Model
    phase: str
    threshold: float
    reason: str
    candidates: list[str]
    effort: str = "medium"
    path: str = "rules"
    rule: str | None = None
    complexity_bin: str | None = None
    confidence: float | None = None
    p_success: dict[str, float] | None = None
    max_regret: float | None = None
    reason_codes: list[str] | None = None
    baseline_model_id: str | None = None
    trained_selected: str | None = None
    trained_confidence: float | None = None
    savings_usd: float | None = None
    rules_cost_delta_usd: float | None = None


def load_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_models(cfg: dict[str, Any]) -> list[Model]:
    out = []
    for row in cfg["models"]:
        out.append(
            Model(
                id=row["id"],
                display_name=row.get("display_name", row["id"]),
                enabled=bool(row.get("enabled", True)),
                input_per_1m=float(row.get("input_per_1m") or 0),
                output_per_1m=float(row.get("output_per_1m") or 0),
                context_window=int(row.get("context_window") or 0),
                supports_tools=bool(row.get("supports_tools", True)),
                supports_json=bool(row.get("supports_json", True)),
                supports_streaming=bool(row.get("supports_streaming", True)),
                max_output_tokens=row.get("max_output_tokens"),
                cached_input_per_1m=(
                    float(row["cached_input_per_1m"]) if row.get("cached_input_per_1m") is not None else None
                ),
                aa_index=row.get("aa_index"),
                aa_source=row.get("aa_source", "unknown"),
                measured_on=row.get("measured_on", "unknown"),
                measured_success=row.get("measured_success"),
                latency_ms=float(row.get("latency_ms") or 800),
                health=float(row.get("health") or 1.0),
                priors=row.get("priors"),
            )
        )
    return out


def estimate_tokens(messages: list[dict[str, Any]]) -> int:
    return max(1, len(json.dumps(messages, default=str)) // 4)


def detect_phase(
    headers: dict[str, str],
    body: dict[str, Any],
    last_outcome: dict[str, Any] | None = None,
) -> str:
    raw = (headers.get("x-agent-phase") or "").strip().lower()
    if raw in PHASES:
        if last_outcome and last_outcome.get("tests_passed") is False:
            if raw in {"tool", "debug"}:
                return "debug"
            if raw in {"tool_call", "test_execution", "debugging", "test_failure_analysis"}:
                return "test_failure_analysis"
        if raw in {"tool", "tool_call", "test_execution"}:
            blob = _text((body.get("messages") or [{}])[-1].get("content")).lower()
            if re.search(r"\b(failed|error|traceback|assertionerror|pytest|not ok)\b", blob):
                return "debug" if raw == "tool" else "test_failure_analysis"
        return raw

    tools = body.get("tools") or []
    names = []
    for t in tools:
        fn = t.get("function") or {}
        names.append((fn.get("name") or t.get("name") or "").lower())

    messages = body.get("messages") or []
    last_tools = []
    last_text = ""
    for msg in reversed(messages):
        role = msg.get("role")
        if role == "tool":
            last_tools.append(str(msg.get("content") or ""))
            continue
        if role == "assistant" and msg.get("tool_calls"):
            for call in msg["tool_calls"]:
                names.append(((call.get("function") or {}).get("name") or "").lower())
            break
        if role == "user":
            last_text = _text(msg.get("content"))
            break

    blob = "\n".join(last_tools[-3:] + [last_text]).lower()
    if re.search(r"\b(failed|error|traceback|assertionerror|pytest|not ok)\b", blob):
        return "debug"
    if re.search(r"\b(summariz|tl;dr|what did we)\b", last_text.lower()):
        return "summarize"
    if re.search(r"\b(plan|architect|design)\b", last_text.lower()) and not names:
        return "plan"

    for name in names:
        if name in _TOOL_PHASE:
            return _TOOL_PHASE[name]
        if "test" in name:
            return "debug"

    if tools:
        return "edit"
    return "plan"


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    return ""


def eligible_models(
    cfg: dict[str, Any],
    models: list[Model],
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
) -> tuple[float, list[Model]]:
    threshold = _phase_bar(cfg, phase)
    if effort == "low":
        threshold = 0
    elif effort == "high":
        threshold = max(threshold, 50)
    elif effort == "max":
        threshold = max(threshold, float(cfg.get("premium_aa_floor") or 58))

    premium_floor = float(cfg.get("premium_aa_floor") or 58)
    remaining = budget_usd - spend_usd
    eligible: list[Model] = []
    for m in models:
        if not m.enabled:
            continue
        if allowed and m.id not in allowed:
            continue
        if needs_tools and not m.supports_tools:
            continue
        if needs_json and not m.supports_json:
            continue
        if streaming and not m.supports_streaming:
            continue
        if tokens > m.context_window:
            continue
        if max_tokens is not None and m.max_output_tokens and max_tokens > int(m.max_output_tokens):
            continue
        if latency_limit_ms and m.latency_ms > latency_limit_ms:
            continue
        if m.aa_index is None:
            continue
        if m.quality < threshold:
            continue
        if m.quality >= premium_floor and effort != "max" and threshold < premium_floor:
            continue
        est = (tokens / 1_000_000) * m.input_per_1m + (800 / 1_000_000) * m.output_per_1m
        if est > remaining and m.unit_cost > 0:
            continue
        eligible.append(m)
    return threshold, eligible


def fallback_decision(
    cfg: dict[str, Any], models: list[Model], phase: str, threshold: float, *, learned: bool = False
) -> Decision:
    fallback_id = cfg.get("fallback_model")
    fallback = next((m for m in models if m.id == fallback_id), models[0])
    prefix = "learned fallback" if learned else f"no eligible model for phase={phase} threshold={threshold}; fallback"
    return Decision(
        model=fallback,
        phase=phase,
        threshold=threshold,
        reason=f"{prefix} {fallback.id}",
        candidates=[],
    )


def select_model(
    cfg: dict[str, Any],
    models: list[Model],
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
    threshold, eligible = eligible_models(
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
    if not eligible:
        decision = fallback_decision(cfg, models, phase, threshold)
        stamp_baseline(decision, [decision.model], tokens)
        return decision
    max_regret = 0.0 if effort == "low" else float(cfg.get("max_regret") or 0)
    best = max(eligible, key=lambda m: m.quality)
    if max_regret > 0 and threshold >= 50:
        floor = best.quality - max_regret
        close = [m for m in eligible if m.quality >= floor]
        if close:
            eligible = close
            best = max(eligible, key=lambda m: m.quality)
    scores = {m.id: pioneer_score(m, phase, eligible) for m in eligible}
    if effort == "low":
        eligible.sort(key=lambda m: (m.unit_cost, -m.quality))
    elif effort == "max":
        eligible.sort(key=lambda m: (-m.quality, -scores[m.id], m.unit_cost))
    else:
        eligible.sort(key=lambda m: (-scores[m.id], -m.quality, m.unit_cost))
    chosen = eligible[0]
    score = scores[chosen.id]
    regret = best.quality - chosen.quality
    decision = Decision(
        model=chosen,
        phase=phase,
        threshold=threshold,
        reason=(
            f"phase={phase} bar={threshold} score={score:.2f} regret={regret:g} "
            f"picked {chosen.id} (aa={chosen.quality:g}, ${chosen.unit_cost:.2f}/1M blend) "
            f"source={chosen.aa_source}/{chosen.measured_on}"
        ),
        candidates=[m.id for m in eligible],
    )
    stamp_baseline(decision, eligible, tokens)
    return decision


def stamp_baseline(decision: Decision, eligible: list[Model], tokens: int) -> None:
    """Named savings baseline = most expensive eligible model (list unit cost)."""
    if not eligible:
        return
    baseline = max(eligible, key=lambda m: m.unit_cost)
    decision.baseline_model_id = baseline.id
    est_sel = estimate_cost(decision.model, tokens, 800)
    est_base = estimate_cost(baseline, tokens, 800)
    decision.savings_usd = round(max(0.0, est_base - est_sel), 6)


def _phase_bar(cfg: dict[str, Any], phase: str) -> float:
    thresholds = cfg.get("phase_threshold") or {}
    if phase in thresholds:
        return float(thresholds[phase])
    family = PHASE_FAMILY.get(phase)
    if family and family in thresholds:
        return float(thresholds[family])
    return 40.0


def predicted_success(model: Model) -> float:
    return model.quality / 100.0


def capability_match(model: Model, phase: str) -> float:
    priors = model.priors or {}
    if phase in priors:
        return float(priors[phase])
    family = PHASE_FAMILY.get(phase)
    if family and family in priors:
        return float(priors[family])
    return predicted_success(model)


def pioneer_score(model: Model, phase: str, eligible: list[Model]) -> float:
    ps = predicted_success(model)
    cap = capability_match(model, phase)
    tool_rel = 1.0 if model.supports_tools else 0.5
    lat = 1.0 / (1.0 + model.latency_ms / 1000.0)
    costs = [m.unit_cost for m in eligible] or [1.0]
    max_c = max(costs) or 1.0
    norm_c = 0.0 if max_c == 0 else model.unit_cost / max_c
    return (
        0.40 * ps
        + 0.20 * cap
        + 0.15 * tool_rel
        + 0.10 * lat
        + 0.10 * model.health
        - 0.05 * norm_c
    )


def stronger_than(models: list[Model], current: Model) -> Model | None:
    better = [m for m in models if m.enabled and m.quality > current.quality]
    if not better:
        return None
    better.sort(key=lambda m: (m.quality, m.unit_cost))
    return better[0]


class SpendLog:
    def __init__(self, path: Path, limit_usd: float) -> None:
        self.path = path
        self.limit_usd = limit_usd
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("0\n", encoding="utf-8")

    def total(self) -> float:
        try:
            return float(self.path.read_text(encoding="utf-8").strip() or 0)
        except ValueError:
            return 0.0

    def add(self, usd: float) -> None:
        self.path.write_text(f"{self.total() + usd:.6f}\n", encoding="utf-8")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": datetime.now(timezone.utc).isoformat(), **row}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")


def estimate_cost(model: Model, prompt_tokens: int, completion_tokens: int) -> float:
    inp = model.cached_input_per_1m if model.cached_input_per_1m is not None else model.input_per_1m
    return (prompt_tokens / 1_000_000) * inp + (completion_tokens / 1_000_000) * model.output_per_1m


def wants_json(body: dict[str, Any]) -> bool:
    fmt = body.get("response_format") or {}
    return isinstance(fmt, dict) and fmt.get("type") in {"json_object", "json_schema"}


def json_content_valid(message: dict[str, Any] | None) -> bool:
    if not message:
        return False
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        return False
    try:
        json.loads(content)
    except json.JSONDecodeError:
        return False
    return True


def tool_calls_valid(message: dict[str, Any] | None) -> bool:
    if not message:
        return True
    calls = message.get("tool_calls") or []
    for call in calls:
        raw = (call.get("function") or {}).get("arguments")
        if raw in (None, ""):
            return False
        try:
            json.loads(raw)
        except json.JSONDecodeError:
            return False
    return True
