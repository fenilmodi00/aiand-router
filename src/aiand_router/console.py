from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi.responses import JSONResponse

from .router import Model

RANGES: dict[str, timedelta | None] = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "all": None,
}
LOG_QUERY_KEYS = ("range", "after", "after_id", "errors", "limit")


def normalize_range(raw: str | None) -> str:
    key = (raw or "30d").strip().lower()
    return key if key in RANGES else "30d"


def aiand_origin(base_url: str) -> str:
    url = (base_url or "https://api.aiand.com/v1").rstrip("/")
    if url.endswith("/v1"):
        url = url[: -len("/v1")]
    return url.rstrip("/")


def redact(row: dict[str, Any], keys: list[str] | None = None) -> dict[str, Any]:
    keys = [k.lower() for k in (keys or ["key", "authorization", "token", "secret"])]
    substr = {"key", "secret", "authorization", "password"} & set(keys)
    out = {}
    for k, v in row.items():
        lk = k.lower()
        if lk in keys:
            continue
        if any(s in lk for s in substr):
            continue
        out[k] = v
    return out


def parse_ts(row: dict[str, Any]) -> datetime | None:
    raw = row.get("ts")
    if raw in (None, ""):
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def is_hop(row: dict[str, Any]) -> bool:
    return row.get("kind") != "outcome"


def is_fallback(row: dict[str, Any]) -> bool:
    if row.get("escalated_from"):
        return True
    return "escalated" in str(row.get("reason") or "").lower()


def load_hops(log_path: Path, redact_keys: list[str]) -> list[dict[str, Any]]:
    if not log_path.exists():
        return []
    hops: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict) or not is_hop(row):
            continue
        hops.append(redact(row, redact_keys))
    return hops


def row_in_range(row: dict[str, Any], range_key: str, now: datetime) -> bool:
    delta = RANGES.get(range_key, RANGES["30d"])
    if delta is None:
        return True
    ts = parse_ts(row)
    if ts is None:
        return True
    return ts >= now - delta


def overview_payload(
    *,
    log_path: Path,
    models: list[Model],
    spend_usd: float,
    budget_usd: float,
    aiand_key_set: bool,
    range_key: str,
    redact_keys: list[str],
    virtual_model: str = "router/auto",
) -> dict[str, Any]:
    range_key = normalize_range(range_key)
    now = datetime.now(timezone.utc)
    hops = [h for h in load_hops(log_path, redact_keys) if row_in_range(h, range_key, now)]
    enabled = [m for m in models if m.enabled]
    names = {m.id: m.display_name for m in models}

    routed = len(hops)
    cost_routed = sum(float(h.get("cost_usd") or 0) for h in hops)
    savings = sum(float(h.get("savings_usd") or 0) for h in hops)
    cost_baseline = cost_routed + savings
    fallback_count = sum(1 for h in hops if is_fallback(h))
    cache_hits = sum(1 for h in hops if h.get("cache_hit"))

    counts: dict[str, int] = {}
    for h in hops:
        mid = str(h.get("selected") or "")
        if mid:
            counts[mid] = counts.get(mid, 0) + 1

    mix: list[dict[str, Any]] = []
    seen: set[str] = set()
    for m in enabled:
        c = counts.get(m.id, 0)
        mix.append(
            {
                "id": m.id,
                "display_name": m.display_name,
                "count": c,
                "pct": (100.0 * c / routed) if routed else 0.0,
            }
        )
        seen.add(m.id)
    for mid, c in counts.items():
        if mid in seen:
            continue
        mix.append(
            {
                "id": mid,
                "display_name": names.get(mid, mid),
                "count": c,
                "pct": (100.0 * c / routed) if routed else 0.0,
            }
        )

    input_tokens = sum(int(h.get("tokens_in") or 0) for h in hops)
    output_tokens = sum(int(h.get("tokens_out") or 0) for h in hops)

    return {
        "range": range_key,
        "virtual_model": virtual_model,
        "routed_requests": routed,
        "spend_usd": spend_usd,
        "budget_usd": budget_usd,
        "savings_usd": round(savings, 6),
        "savings_pct": (100.0 * savings / cost_baseline) if cost_baseline else 0.0,
        "fallback_count": fallback_count,
        "fallback_rate": (fallback_count / routed) if routed else 0.0,
        "cache_hits": cache_hits,
        "aiand_key_set": bool(aiand_key_set),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "candidates": [
            {"id": m.id, "display_name": m.display_name, "enabled": True} for m in enabled
        ],
        "candidate_mix": mix,
        "usage_buckets": _usage_buckets(hops, range_key, now),
        "cost_routed_usd": round(cost_routed, 6),
        "cost_baseline_usd": round(cost_baseline, 6),
    }


def inferences_payload(
    *,
    log_path: Path,
    q: str,
    model: str,
    range_key: str,
    redact_keys: list[str],
) -> dict[str, Any]:
    range_key = normalize_range(range_key)
    now = datetime.now(timezone.utc)
    needle = (q or "").strip().lower()
    model = (model or "").strip()
    data: list[dict[str, Any]] = []
    for h in load_hops(log_path, redact_keys):
        if not row_in_range(h, range_key, now):
            continue
        if model and h.get("selected") != model:
            continue
        if needle:
            blob = " ".join(str(h.get(k) or "") for k in ("selected", "phase", "reason")).lower()
            if needle not in blob:
                continue
        data.append(_inference_row(h))
    data.reverse()
    return {"data": data}


def _inference_row(h: dict[str, Any]) -> dict[str, Any]:
    return {
        "ts": h.get("ts"),
        "selected": h.get("selected"),
        "phase": h.get("phase"),
        "tokens_in": int(h.get("tokens_in") or 0),
        "tokens_out": int(h.get("tokens_out") or 0),
        "latency_ms": int(h.get("latency_ms") or 0),
        "status": int(h.get("status") or 0),
        "cache_hit": bool(h.get("cache_hit")),
        "path": h.get("path") or "rules",
        "cost_usd": float(h.get("cost_usd") or 0),
        "savings_usd": float(h.get("savings_usd") or 0) if h.get("savings_usd") is not None else None,
        "baseline_model_id": h.get("baseline_model_id"),
        "rule": h.get("rule"),
        "escalated_from": h.get("escalated_from"),
        "ttft_ms": h["ttft_ms"] if h.get("ttft_ms") is not None else None,
        "llmaj_score": h["llmaj_score"] if h.get("llmaj_score") is not None else None,
        "tests_passed": h.get("tests_passed"),
    }


def _hop_baseline(h: dict[str, Any]) -> float | None:
    if h.get("savings_usd") is not None:
        return float(h.get("cost_usd") or 0) + float(h.get("savings_usd") or 0)
    if h.get("cost_baseline") is not None:
        return float(h["cost_baseline"])
    return None


def _bucket_spend(rows: list[dict[str, Any]]) -> tuple[float, float]:
    """Always count actual hop cost; baseline falls back to cost when unknown (0 savings)."""
    spend = 0.0
    baseline = 0.0
    for h in rows:
        cost = float(h.get("cost_usd") or 0)
        spend += cost
        b = _hop_baseline(h)
        baseline += b if b is not None else cost
    return round(spend, 6), round(baseline, 6)


def _usage_buckets(hops: list[dict[str, Any]], range_key: str, now: datetime) -> list[dict[str, Any]]:
    dated = [(ts, h) for h in hops if (ts := parse_ts(h)) is not None]
    if not dated:
        return []
    if range_key == "24h":
        step = timedelta(hours=1)
        start = (now - timedelta(hours=23)).replace(minute=0, second=0, microsecond=0)
        n = 24
    elif range_key == "7d":
        step = timedelta(days=1)
        start = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
        n = 7
    elif range_key == "30d":
        step = timedelta(days=1)
        start = (now - timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)
        n = 30
    else:
        step = timedelta(days=1)
        times = [t for t, _ in dated]
        start = min(times).astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        end = max(times).astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        n = min(int((end - start) / step) + 1, 366)
    buckets = []
    for i in range(n):
        t0 = start + step * i
        t1 = t0 + step
        rows = [h for t, h in dated if t0 <= t < t1]
        by_model: dict[str, int] = {}
        for h in rows:
            mid = str(h.get("selected") or "unknown")
            by_model[mid] = by_model.get(mid, 0) + 1
        spend_usd, baseline_usd = _bucket_spend(rows)
        buckets.append(
            {
                "ts": t0.isoformat(),
                "requests": len(rows),
                "by_model": by_model,
                "spend_usd": spend_usd,
                "baseline_usd": baseline_usd,
            }
        )
    return buckets


def _scrub(text: str, secret: str) -> str:
    if not secret:
        return text
    return text.replace(secret, "[redacted]")


def _error_message(payload: Any, status: int, secret: str) -> str:
    if isinstance(payload, dict):
        err = payload.get("error")
        if isinstance(err, dict):
            msg = err.get("message") or str(err)
        elif isinstance(err, str) and err:
            msg = err
        else:
            msg = str(payload.get("message") or f"AIand upstream returned {status}")
    else:
        msg = f"AIand upstream returned {status}"
    return _scrub(str(msg), secret)


async def proxy_aiand(
    *,
    origin: str,
    api_key: str,
    path: str,
    params: dict[str, Any] | None = None,
    client: Any | None = None,
) -> Any:
    if not api_key:
        return JSONResponse({"error": "AIAND_API_KEY is not set"}, status_code=502)
    url = f"{origin.rstrip('/')}{path}"
    headers = {"Authorization": f"Bearer {api_key}"}
    query = {k: v for k, v in (params or {}).items() if v not in (None, "")}
    try:
        if client is not None:
            resp = await client.get(url, headers=headers, params=query)
        else:
            async with httpx.AsyncClient(timeout=30.0) as http:
                resp = await http.get(url, headers=headers, params=query)
    except httpx.HTTPError:
        return JSONResponse({"error": "AIand upstream request failed"}, status_code=502)
    try:
        payload = resp.json()
    except json.JSONDecodeError:
        text = _scrub(getattr(resp, "text", "") or "", api_key)
        return JSONResponse(
            {"error": text or "AIand upstream returned non-JSON"},
            status_code=502,
        )
    if resp.status_code >= 400:
        return JSONResponse(
            {"error": _error_message(payload, resp.status_code, api_key)},
            status_code=502,
        )
    blob = json.dumps(payload)
    if api_key and api_key in blob:
        payload = json.loads(blob.replace(api_key, "[redacted]"))
    return payload
