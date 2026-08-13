from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

PHASES = ("discover", "plan", "edit", "tool", "debug", "summarize")
VIRTUAL_MODELS = {"router/auto", "aiand-router", "auto"}

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
    aa_index: float | None
    aa_source: str
    measured_on: str
    measured_success: float | None

    @property
    def quality(self) -> float:
        if self.measured_success is not None:
            return self.measured_success * 100
        return float(self.aa_index or 0)

    @property
    def unit_cost(self) -> float:
        return self.input_per_1m * 0.4 + self.output_per_1m * 0.6


@dataclass
class Decision:
    model: Model
    phase: str
    threshold: float
    reason: str
    candidates: list[str]


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
                aa_index=row.get("aa_index"),
                aa_source=row.get("aa_source", "unknown"),
                measured_on=row.get("measured_on", "unknown"),
                measured_success=row.get("measured_success"),
            )
        )
    return out


def estimate_tokens(messages: list[dict[str, Any]]) -> int:
    return max(1, len(json.dumps(messages, default=str)) // 4)


def detect_phase(headers: dict[str, str], body: dict[str, Any]) -> str:
    raw = (headers.get("x-agent-phase") or "").strip().lower()
    if raw in PHASES:
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
) -> Decision:
    thresholds = cfg.get("phase_threshold") or {}
    threshold = float(thresholds.get(phase, 40))
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
        if tokens > m.context_window:
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

    if not eligible:
        fallback_id = cfg.get("fallback_model")
        fallback = next((m for m in models if m.id == fallback_id), models[0])
        return Decision(
            model=fallback,
            phase=phase,
            threshold=threshold,
            reason=f"no eligible model for phase={phase} threshold={threshold}; fallback {fallback.id}",
            candidates=[],
        )

    eligible.sort(key=lambda m: (m.unit_cost, -m.quality))
    chosen = eligible[0]
    return Decision(
        model=chosen,
        phase=phase,
        threshold=threshold,
        reason=(
            f"phase={phase} bar={threshold} picked {chosen.id} "
            f"(aa={chosen.quality:g}, ${chosen.unit_cost:.2f}/1M blend) "
            f"source={chosen.aa_source}/{chosen.measured_on}"
        ),
        candidates=[m.id for m in eligible],
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
    return (prompt_tokens / 1_000_000) * model.input_per_1m + (
        completion_tokens / 1_000_000
    ) * model.output_per_1m


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
