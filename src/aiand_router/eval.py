from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from .router import VIRTUAL_MODELS

ROOT = Path(__file__).resolve().parents[2]


def load_tasks(path: Path | None = None) -> dict[str, Any]:
    return yaml.safe_load((path or ROOT / "config" / "tasks.yaml").read_text(encoding="utf-8"))


def run_eval(client: Any, api_key: str, spec: dict[str, Any], log_path: Path | None = None) -> dict[str, Any]:
    before = _hit_count(log_path)
    executed = spec["baselines"]["executed"]
    for cfg in executed.values():
        for task in spec["tasks"]:
            headers = {"Authorization": f"Bearer {api_key}"}
            if cfg["model"] == "router/auto":
                headers["x-agent-phase"] = task["phase"]
            response = client.post(
                "/v1/chat/completions",
                headers=headers,
                json={
                    "model": cfg["model"],
                    "messages": [{"role": "user", "content": task["prompt"]}],
                },
            )
            response.raise_for_status()
    return {
        "executed": list(executed),
        "stubbed": list(spec["baselines"]["stubbed"]),
        "cache_hits": _hit_count(log_path) - before,
    }


def report_from_log(log_path: Path) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for line in log_path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("kind") == "outcome" or row.get("cache_hit"):
            continue
        requested = row.get("requested")
        if requested == "deepseek-ai/deepseek-v4-pro":
            groups["premium"].append(row)
        elif requested == "moonshotai/kimi-k2.7-code":
            groups["kimi"].append(row)
        elif requested in VIRTUAL_MODELS:
            groups["adaptive"].append(row)
    baselines = {}
    for name, rows in groups.items():
        models = list(dict.fromkeys(r["selected"] for r in rows if r.get("selected")))
        baselines[name] = {
            "tasks": len(rows),
            "resolved": sum(1 for r in rows if _resolved(r)),
            "cost_usd": round(sum(float(r.get("cost_usd") or 0) for r in rows), 6),
            "latency_ms": sum(int(r.get("latency_ms") or 0) for r in rows),
            "models": models,
        }
    return {
        "baselines": baselines,
        "quality_note": "AA Intelligence Index scores are public priors (measured_on: not_aiand). Costs and models here are from the request log.",
    }


def _resolved(row: dict[str, Any]) -> bool:
    if int(row.get("status") or 0) != 200:
        return False
    reason = str(row.get("reason") or "").lower()
    if row.get("escalated_from") or "escalated" in reason:
        return False
    if row.get("tests_passed") is False:
        return False
    if not row.get("cache_hit") and int(row.get("tokens_out") or 0) == 0:
        return False
    return True


def _hit_count(log_path: Path | None) -> int:
    if log_path is None or not log_path.exists():
        return 0
    return sum(
        1
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line).get("cache_hit")
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", default="change-me")
    parser.add_argument("--log", default=str(ROOT / "data" / "requests.jsonl"))
    args = parser.parse_args(argv)
    import httpx

    spec = load_tasks()
    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=120.0) as client:
        run_eval(client, args.api_key, spec, Path(args.log))
    report = report_from_log(Path(args.log))
    print(json.dumps(report, indent=2))
    print("stubbed (not executed):", ", ".join(spec["baselines"]["stubbed"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
