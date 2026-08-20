from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from .metrics import (
    ECE_MAX,
    QUALITY_TOLERANCE,
    VERIFIED_N_FLOOR,
    brier_skill_score,
    ece_equal_mass,
    ece_equal_width,
    ece_mass_is_gated,
)
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


def _labeled_bool(val: Any) -> bool | None:
    if val is True:
        return True
    if val is False:
        return False
    return None


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


def _read_log_rows(log_path: Path) -> list[dict[str, Any]]:
    if not log_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("kind") == "outcome" or row.get("cache_hit"):
            continue
        rows.append(row)
    return rows


def _read_session_rows(session_path: Path | None) -> list[dict[str, Any]]:
    if session_path is None or not session_path.exists():
        return []
    return [
        json.loads(line)
        for line in session_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _session_gold_ids(sessions: list[dict[str, Any]]) -> set[str]:
    """Ids from session_gold rows (session_id and/or instance_id)."""
    ids: set[str] = set()
    for s in sessions:
        if not s.get("session_gold"):
            continue
        for key in ("session_id", "instance_id"):
            val = s.get(key)
            if val:
                ids.add(str(val))
    return ids


def _hop_joins_session_gold(hop_session_id: str, gold_ids: set[str]) -> bool:
    """Match exact session_id or verified_runner cf suffix (`id::cf-trained`)."""
    if hop_session_id in gold_ids:
        return True
    if "::" in hop_session_id:
        base = hop_session_id.split("::", 1)[0]
        if base in gold_ids:
            return True
    return False


def _mean_rules_cost_delta(hops: list[dict[str, Any]]) -> float | None:
    deltas = [
        float(r["rules_cost_delta_usd"])
        for r in hops
        if r.get("rules_cost_delta_usd") is not None
    ]
    if not deltas:
        return None
    return sum(deltas) / len(deltas)


def promotion_gate_verdict(
    log_path: Path,
    *,
    session_path: Path | None = None,
    n_floor: int = VERIFIED_N_FLOOR,
) -> dict[str, Any]:
    """Runbook §(a) four-bar gate from gateway request log + optional session JSONL."""
    hops = _read_log_rows(log_path)
    sessions = _read_session_rows(session_path)
    shadow_hops = [r for r in hops if r.get("path") == "shadow"]
    cost_pool = shadow_hops or hops

    n_sessions = len(sessions)
    if not n_sessions:
        session_ids = {
            str(r.get("session_id"))
            for r in shadow_hops
            if r.get("session_id")
        }
        n_sessions = len(session_ids)

    rules_vals = [
        _labeled_bool((s.get("policies") or {}).get("rules", {}).get("resolved"))
        for s in sessions
    ]
    labeled_rules = [v for v in rules_vals if v is not None]
    rules_resolved = sum(1 for v in labeled_rules if v)
    trained_rows = [
        s for s in sessions if isinstance((s.get("policies") or {}).get("trained"), dict)
    ]
    trained_vals = [
        _labeled_bool((s.get("policies") or {}).get("trained", {}).get("resolved"))
        for s in trained_rows
    ]
    labeled_trained = [v for v in trained_vals if v is not None]
    trained_resolved = sum(1 for v in labeled_trained if v)
    unlabeled_n = sum(1 for v in rules_vals if v is None)
    rules_rate = (rules_resolved / len(labeled_rules)) if labeled_rules else None
    # 0.0 is valid when dual-policy rows have labeled resolved=false.
    # resolved=null (needs_swe_eval) is unlabeled — rate stays None, not 0.0.
    trained_rate = (
        (trained_resolved / len(labeled_trained)) if labeled_trained else None
    )

    hop_n = len(shadow_hops) or len(hops)
    escalate_hops = sum(1 for r in (shadow_hops or hops) if r.get("escalated_from"))
    escalate_rate = (escalate_hops / hop_n) if hop_n else None

    gold_ids = _session_gold_ids(sessions)
    hops_with_sid = [r for r in cost_pool if r.get("session_id")]
    joinable = [
        r
        for r in hops_with_sid
        if _hop_joins_session_gold(str(r["session_id"]), gold_ids)
    ]
    if gold_ids and hops_with_sid:
        # Prefer attributable hops when the log carries session_id.
        cost_hops = joinable
        session_joined = bool(joinable)
        if joinable:
            cost_detail = (
                f"session-gold–joined mean hop delta "
                f"(n_joinable={len(joinable)} / n_with_session_id={len(hops_with_sid)})"
            )
        else:
            cost_detail = (
                "no request-log hops join to session-gold session_ids "
                f"(n_with_session_id={len(hops_with_sid)})"
            )
    elif gold_ids and not hops_with_sid:
        # Historical logs omit session_id — report mixed mean honestly.
        cost_hops = cost_pool
        session_joined = False
        cost_detail = (
            "mixed-log mean; historical hops lack session_id — not attributable "
            "to session-gold (new gateway sessions will join)"
        )
    else:
        cost_hops = cost_pool
        session_joined = False
        cost_detail = "trained - rules list-price USD from shadow log (mean hop delta)"

    rules_cost_delta = _mean_rules_cost_delta(cost_hops)

    cal_rows: list[tuple[float, float]] = []
    for row in shadow_hops or hops:
        conf = row.get("trained_confidence")
        if conf is None:
            conf = row.get("confidence")
        if conf is None:
            continue
        if row.get("tests_passed") is None:
            continue
        cal_rows.append((float(conf), 1.0 if row.get("tests_passed") else 0.0))

    bss = brier_skill_score(cal_rows) if cal_rows else None
    ece_w = ece_equal_width(cal_rows) if cal_rows else None
    ece_m = ece_equal_mass(cal_rows) if cal_rows else None
    ece_mass_gated = bool(cal_rows and ece_mass_is_gated(len(cal_rows)))

    live_session_gold = any(s.get("session_gold") for s in sessions)
    floor_ok = n_sessions >= n_floor
    quality_rules_ok = rules_rate is not None and rules_rate >= 0.0
    quality_trained_ok = (
        trained_rate is not None and rules_rate is not None
        and trained_rate >= rules_rate - QUALITY_TOLERANCE
    )
    quality_escalate_ok = escalate_rate is not None  # baseline compare needs rules-only run
    cost_ok = rules_cost_delta is not None and rules_cost_delta < 0.0
    cal_bss_ok = bss is not None and bss > 0.0
    cal_ece_w_ok = ece_w is not None and ece_w <= ECE_MAX
    cal_ece_m_ok = (
        not ece_mass_gated
        or (ece_m is not None and ece_m <= ECE_MAX)
    )

    bars = {
        "quality_session_gold": {
            "pass": quality_trained_ok if trained_rate is not None else None,
            "rules_resolve_rate": rules_rate,
            "trained_resolve_rate": trained_rate,
            "detail": (
                "session rows unlabeled (needs_swe_eval); not a 0% resolve"
                if trained_rows and trained_rate is None and unlabeled_n
                else (
                    "trained session gold requires dual-policy session rows or trained serve pass"
                    if trained_rate is None
                    else f"trained {trained_rate:.4f} vs rules {rules_rate:.4f} (tol {QUALITY_TOLERANCE})"
                )
            ),
        },
        "quality_escalate": {
            "pass": quality_escalate_ok,
            "escalate_rate": escalate_rate,
            "detail": "per-hop escalate rate from request log (rules baseline compare at scale)",
        },
        "cost_rules_delta": {
            "pass": cost_ok,
            "rules_cost_delta": rules_cost_delta,
            "session_joined": session_joined,
            "n_joinable_hops": len(joinable),
            "n_hops_with_session_id": len(hops_with_sid),
            "n_session_gold_ids": len(gold_ids),
            "detail": cost_detail,
        },
        "calibration_bss": {
            "pass": cal_bss_ok,
            "brier_skill": bss,
            "n_calibration_hops": len(cal_rows),
        },
        "calibration_ece_width": {
            "pass": cal_ece_w_ok,
            "ece_equal_width": ece_w,
        },
        "calibration_ece_mass": {
            "pass": cal_ece_m_ok if ece_mass_gated else None,
            "ece_equal_mass": ece_m,
            "waived_small_n": not ece_mass_gated,
        },
        "floor_session_gold_n": {
            "pass": floor_ok,
            "n_sessions": n_sessions,
            "floor": n_floor,
        },
    }

    promotable = all(
        bar.get("pass") is True
        for bar in bars.values()
        if bar.get("pass") is not None
    ) and trained_rate is not None

    if n_sessions < n_floor or not live_session_gold:
        verdict = "bounded_check_only"
    elif promotable:
        verdict = "promotion_gate_pass"
    else:
        verdict = "promotion_gate_fail"

    return {
        "verdict": verdict,
        "session_gold": live_session_gold,
        "production_parity": False,
        "promotion_gate_started": bool(hops or sessions),
        "n_sessions": n_sessions,
        "n_unlabeled_sessions": unlabeled_n if sessions else 0,
        "n_shadow_hops": len(shadow_hops),
        "bars": bars,
        "do_not_flip_trained_path": True,
        "log_path": str(log_path),
        "session_path": str(session_path) if session_path else None,
    }


def format_gate_verdict(report: dict[str, Any]) -> str:
    lines = [
        "# Verified session-gold promotion gate (§(a))",
        "",
        f"**Verdict:** `{report.get('verdict')}`",
        f"**Session gold:** `{report.get('session_gold')}` · "
        f"**n_sessions:** {report.get('n_sessions')}",
        f"**Log:** `{report.get('log_path')}`",
        "",
        "> Does **not** flip `TRAINED_PATH=trained`. Promote only if all bars pass at n≥300.",
        "",
        "## Bars",
        "",
    ]
    for bar_id, bar in (report.get("bars") or {}).items():
        status = bar.get("pass")
        label = "pass" if status is True else ("fail" if status is False else "waived/not_started")
        lines.append(f"- **{bar_id}** — `{label}` — {bar}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", default="change-me")
    parser.add_argument("--log", default=str(ROOT / "data" / "requests.jsonl"))
    parser.add_argument(
        "--sessions",
        default=None,
        help="Verified session results JSONL from verified_runner",
    )
    parser.add_argument(
        "--gate",
        action="store_true",
        help="Print runbook §(a) four-bar gate verdict from log (+ optional --sessions)",
    )
    parser.add_argument("--run-tasks", action="store_true", help="Execute config/tasks.yaml baselines")
    args = parser.parse_args(argv)

    if args.gate:
        report = promotion_gate_verdict(
            Path(args.log),
            session_path=Path(args.sessions) if args.sessions else None,
        )
        print(format_gate_verdict(report))
        print(json.dumps(report, indent=2))
        return 0

    if not args.run_tasks:
        report = report_from_log(Path(args.log))
        print(json.dumps(report, indent=2))
        spec = load_tasks()
        print("stubbed (not executed):", ", ".join(spec["baselines"]["stubbed"]))
        return 0

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
