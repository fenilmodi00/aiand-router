"""Learned router behind the same Decision interface. Dark unless comparison wins."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .cache import RequestCache, request_cache_key
from .eval import load_tasks
from .router import Decision, Model, estimate_cost, load_config, load_models, select_model

ROOT = Path(__file__).resolve().parents[2]


def learned_select(
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
    # ponytail: untrained stub — highest AA among enabled; no embeddings.
    eligible = []
    for m in models:
        if not m.enabled or m.aa_index is None:
            continue
        if allowed and m.id not in allowed:
            continue
        if needs_tools and not m.supports_tools:
            continue
        if tokens > m.context_window:
            continue
        eligible.append(m)
    if not eligible:
        fallback = next((m for m in models if m.id == cfg.get("fallback_model")), models[0])
        return Decision(
            model=fallback,
            phase=phase,
            threshold=0,
            reason=f"learned fallback {fallback.id}",
            candidates=[],
        )
    eligible.sort(key=lambda m: (-m.quality, m.unit_cost))
    chosen = eligible[0]
    return Decision(
        model=chosen,
        phase=phase,
        threshold=0,
        reason=f"learned (untrained) picked {chosen.id} aa={chosen.quality:g}",
        candidates=[m.id for m in eligible],
    )


def compare_on_cache(
    spec: dict[str, Any],
    cache_dir: Path,
    flag_path: Path,
) -> dict[str, Any]:
    cfg = load_config(ROOT / "config" / "models.yaml")
    models = load_models(cfg)
    cache = RequestCache(cache_dir)
    held = spec["tasks"][len(spec["tasks"]) // 2 :]
    kwargs = dict(
        needs_tools=False,
        tokens=100,
        effort="medium",
        allowed=None,
        spend_usd=0.0,
        budget_usd=15.0,
    )
    rules_cost = 0.0
    learned_cost = 0.0
    rules_hits = 0
    learned_hits = 0
    for task in held:
        body = {"messages": [{"role": "user", "content": task["prompt"]}]}
        rules = select_model(cfg, models, phase=task["phase"], **kwargs)
        learned = learned_select(cfg, models, phase=task["phase"], **kwargs)
        r_hit = cache.get(request_cache_key(body, rules.model.id))
        l_hit = cache.get(request_cache_key(body, learned.model.id))
        if r_hit is not None:
            rules_hits += 1
            rules_cost += _cost_from_cached(rules.model, r_hit)
        if l_hit is not None:
            learned_hits += 1
            learned_cost += _cost_from_cached(learned.model, l_hit)
    covered = len(held)
    winner = (
        "learned"
        if learned_hits == covered and rules_hits == covered and learned_cost < rules_cost
        else "rules"
    )
    result = {
        "winner": winner,
        "held_out": [t["id"] for t in held],
        "rules_hits": rules_hits,
        "learned_hits": learned_hits,
        "rules_cost_usd": round(rules_cost, 6),
        "learned_cost_usd": round(learned_cost, 6),
        "cache_dir": str(cache_dir),
    }
    if winner == "learned":
        flag_path.write_text(json.dumps(result), encoding="utf-8")
    return result


def _cost_from_cached(model: Model, payload: dict[str, Any]) -> float:
    usage = payload.get("usage") or {}
    return estimate_cost(
        model, int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)
    )


def learned_enabled(flag_path: Path) -> bool:
    if not flag_path.exists():
        return False
    try:
        return json.loads(flag_path.read_text(encoding="utf-8")).get("winner") == "learned"
    except (json.JSONDecodeError, OSError):
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", default=str(ROOT / "data" / "cache"))
    parser.add_argument("--flag", default=str(ROOT / "data" / "learned_wins.json"))
    args = parser.parse_args(argv)
    result = compare_on_cache(load_tasks(), Path(args.cache), Path(args.flag))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
