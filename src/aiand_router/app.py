from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
import httpx

from .cache import RequestCache, request_cache_key
from .learn import learned_enabled, learned_select
from .provider import HttpAiandProvider
from .router import (
    VIRTUAL_MODELS,
    Decision,
    SpendLog,
    append_jsonl,
    detect_phase,
    estimate_cost,
    estimate_tokens,
    load_config,
    load_models,
    select_model,
    stronger_than,
    tool_calls_valid,
)

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]


def create_app(
    *,
    provider: Any | None = None,
    spend: SpendLog | None = None,
    log_path: Path | None = None,
    router_key: str | None = None,
    budget: float | None = None,
    config_path: Path | None = None,
    aiand_key: str | None = None,
    aiand_base: str | None = None,
    cache_dir: Path | None = None,
    learned_flag: Path | None = None,
) -> FastAPI:
    cfg = load_config(config_path or ROOT / "config" / "models.yaml")
    models = load_models(cfg)
    by_id = {m.id: m for m in models}
    key = aiand_key if aiand_key is not None else os.getenv("AIAND_API_KEY", "")
    base = (aiand_base or os.getenv("AIAND_BASE_URL", "https://api.aiand.com/v1")).rstrip("/")
    token = router_key if router_key is not None else os.getenv("ROUTER_API_KEY", "change-me")
    limit = float(budget if budget is not None else os.getenv("BUDGET_LIMIT_USD", "15"))
    spend_log = spend or SpendLog(ROOT / "data" / "spend.txt", limit)
    log = log_path or ROOT / "data" / "requests.jsonl"
    cache = RequestCache(cache_dir or ROOT / "data" / "cache")
    upstream = provider or HttpAiandProvider(base, key)
    last_outcome: dict[str, Any] = {}
    replay_html = (Path(__file__).with_name("replay.html")).read_text(encoding="utf-8")
    flag_path = learned_flag or ROOT / "data" / "learned_wins.json"

    app = FastAPI(title="AIand Coding Router", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def _check_auth(authorization: str | None) -> None:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "missing bearer token")
        if authorization.removeprefix("Bearer ").strip() != token:
            raise HTTPException(401, "invalid router key")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "spend_usd": spend_log.total(),
            "budget_usd": limit,
            "aiand_key_set": bool(key),
        }

    @app.get("/v1/models")
    def list_models(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        _check_auth(authorization)
        data = [
            {
                "id": "router/auto",
                "object": "model",
                "owned_by": "aiand-router",
                "description": "Quality-threshold router over the aiand pool",
            }
        ]
        for m in models:
            data.append(
                {
                    "id": m.id,
                    "object": "model",
                    "owned_by": "aiand",
                    "enabled": m.enabled,
                    "aa_index": m.aa_index,
                    "aa_source": m.aa_source,
                }
            )
        return {"object": "list", "data": data}

    @app.post("/v1/router/outcome")
    async def report_outcome(
        request: Request, authorization: str | None = Header(default=None)
    ) -> dict[str, Any]:
        _check_auth(authorization)
        body = await request.json()
        last_outcome.clear()
        last_outcome.update(
            {
                "tests_passed": bool(body.get("tests_passed")),
                "patch_applied": bool(body.get("patch_applied")),
                "failure_text": str(body.get("failure_text") or ""),
            }
        )
        append_jsonl(log, {"kind": "outcome", "phase": "test", **last_outcome})
        return {"ok": True, **last_outcome}

    @app.get("/replay")
    def replay_page() -> HTMLResponse:
        return HTMLResponse(replay_html)

    @app.get("/replay/events")
    def replay_events() -> list[dict[str, Any]]:
        if not log.exists():
            return []
        rows = []
        for line in log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rows.append(_redact(json.loads(line)))
        return rows

    @app.post("/v1/chat/completions")
    async def chat_completions(
        request: Request, authorization: str | None = Header(default=None)
    ):
        _check_auth(authorization)

        body = await request.json()
        headers = {k.lower(): v for k, v in request.headers.items()}
        effort = (headers.get("x-routing-effort") or "medium").lower()
        allowed_raw = headers.get("x-allowed-models") or ""
        allowed = {x.strip() for x in allowed_raw.split(",") if x.strip()} or None

        requested = body.get("model") or "router/auto"
        phase = detect_phase(headers, body)
        tokens = estimate_tokens(body.get("messages") or [])
        needs_tools = bool(body.get("tools"))

        if requested not in VIRTUAL_MODELS and requested in by_id:
            decision_model = by_id[requested]
            decision = Decision(
                model=decision_model,
                phase=phase,
                threshold=0,
                reason=f"client pinned {requested}",
                candidates=[requested],
            )
        else:
            select_cfg = cfg
            if phase == "debug" and last_outcome.get("tests_passed") is False:
                select_cfg = dict(cfg)
                thresholds = dict(cfg.get("phase_threshold") or {})
                thresholds["debug"] = float(cfg.get("debug_fail_threshold") or 53)
                select_cfg["phase_threshold"] = thresholds
            picker = learned_select if learned_enabled(flag_path) else select_model
            decision = picker(
                select_cfg,
                models,
                phase=phase,
                needs_tools=needs_tools,
                tokens=tokens,
                effort=effort,
                allowed=allowed,
                spend_usd=spend_log.total(),
                budget_usd=limit,
            )

        meta = {
            "X-Router-Phase": decision.phase,
            "X-Router-Model": decision.model.id,
            "X-Router-Reason": decision.reason,
            "X-Router-Threshold": str(decision.threshold),
            "X-Router-Candidates": ",".join(decision.candidates),
        }

        streaming = bool(body.get("stream"))
        ck = request_cache_key(body, decision.model.id)
        if not streaming:
            cached = cache.get(ck)
            if cached is not None:
                append_jsonl(
                    log,
                    {
                        "phase": decision.phase,
                        "requested": requested,
                        "selected": decision.model.id,
                        "reason": decision.reason,
                        "candidates": decision.candidates,
                        "stream": False,
                        "tokens_in": 0,
                        "tokens_out": 0,
                        "cost_usd": 0.0,
                        "latency_ms": 0,
                        "status": 200,
                        "cache_hit": True,
                    },
                )
                return JSONResponse(cached, headers=meta)

        if provider is None and not key:
            raise HTTPException(500, "AIAND_API_KEY is not set")
        if spend_log.total() >= limit:
            raise HTTPException(429, f"budget limit ${limit} reached")

        upstream_body = {k: v for k, v in body.items() if k != "model"}
        upstream_body["model"] = decision.model.id
        if streaming:
            upstream_body.setdefault("stream_options", {})
            if isinstance(upstream_body["stream_options"], dict):
                upstream_body["stream_options"].setdefault("include_usage", True)

        t0 = time.perf_counter()
        result = await _call_provider(upstream, upstream_body)
        if _should_escalate(result) and effort != "low":
            nxt = stronger_than(models, decision.model)
            if nxt:
                meta["X-Router-Escalated-From"] = decision.model.id
                meta["X-Router-Model"] = nxt.id
                decision.reason += f" ; escalated to {nxt.id}"
                meta["X-Router-Reason"] = decision.reason
                upstream_body["model"] = nxt.id
                result = await _call_provider(upstream, upstream_body)
                decision.model = nxt

        latency_ms = int((time.perf_counter() - t0) * 1000)
        usage = _usage(result)
        cost = estimate_cost(
            decision.model,
            usage.get("prompt_tokens", tokens),
            usage.get("completion_tokens", 0),
        )
        spend_log.add(cost)
        append_jsonl(
            log,
            {
                "phase": decision.phase,
                "requested": requested,
                "selected": decision.model.id,
                "reason": decision.reason,
                "candidates": decision.candidates,
                "stream": streaming,
                "tokens_in": usage.get("prompt_tokens", tokens),
                "tokens_out": usage.get("completion_tokens", 0),
                "cost_usd": round(cost, 6),
                "latency_ms": latency_ms,
                "status": result.get("status"),
                "cache_hit": False,
            },
        )

        if result.get("stream"):
            return StreamingResponse(
                result["stream"],
                media_type="text/event-stream",
                headers=meta,
            )
        if result.get("status", 200) >= 400:
            return JSONResponse(result["json"], status_code=result["status"], headers=meta)
        payload = result["json"]
        payload["model"] = decision.model.id
        cache.put(ck, payload)
        return JSONResponse(payload, headers=meta)

    return app


def _should_escalate(result: dict[str, Any]) -> bool:
    if result.get("stream"):
        return False
    status = result.get("status", 200)
    if status in (408, 429) or status >= 500:
        return True
    payload = result.get("json") or {}
    if status >= 400:
        return True
    choices = payload.get("choices") or []
    if not choices:
        return True
    message = (choices[0] or {}).get("message") or {}
    if not message.get("content") and not message.get("tool_calls"):
        return True
    return not tool_calls_valid(message)


def _usage(result: dict[str, Any]) -> dict[str, int]:
    payload = result.get("json") or {}
    usage = payload.get("usage") or {}
    return {
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
    }


app = create_app()


async def _call_provider(upstream: Any, body: dict[str, Any]) -> dict[str, Any]:
    try:
        return await upstream.complete(body)
    except httpx.TimeoutException:
        return {"status": 408, "json": {"error": {"message": "upstream timeout"}}}


def _redact(row: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for k, v in row.items():
        lk = k.lower()
        if "key" in lk or lk in {"authorization", "token", "secret"}:
            continue
        out[k] = v
    return out
