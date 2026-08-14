from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
import httpx

from .anthropic_adapter import (
    SessionTracker,
    anthropic_to_openai,
    openai_to_anthropic_response,
    stream_openai_to_anthropic_sse,
)
from .cache import RequestCache, request_cache_key
from .console import (
    LOG_QUERY_KEYS,
    aiand_origin,
    inferences_payload,
    overview_payload,
    proxy_aiand,
    redact as _redact,
)
from .learn import learned_enabled, learned_select
from .provider import HttpAiandProvider
from .scorer import apply_trained_path, load_scorer, parse_trained_path, trained_select
from .router import (
    DEBUG_PHASES,
    VIRTUAL_MODELS,
    Decision,
    SpendLog,
    append_jsonl,
    detect_phase,
    estimate_cost,
    estimate_tokens,
    json_content_valid,
    load_config,
    load_models,
    select_model,
    stronger_than,
    tool_calls_valid,
    wants_json,
)

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]


def _key_fingerprint(api_key: str) -> str:
    if not api_key:
        return "nokey"
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]


def rotate_local_data_if_key_changed(
    *,
    data_dir: Path,
    api_key: str,
    log_path: Path,
    spend_path: Path,
    cache_dir: Path,
) -> str:
    """When AIAND_API_KEY changes, archive prior hop log/spend/cache so the UI is not stale."""
    fp = _key_fingerprint(api_key)
    marker = data_dir / ".aiand_key_fp"
    data_dir.mkdir(parents=True, exist_ok=True)
    prev = marker.read_text(encoding="utf-8").strip() if marker.exists() else ""
    if prev == fp:
        return fp
    if prev:
        stamp = prev
        archive = data_dir / "archive" / stamp
        archive.mkdir(parents=True, exist_ok=True)
        for src in (log_path, spend_path):
            if src.exists() and src.resolve().is_relative_to(data_dir.resolve()):
                dest = archive / src.name
                if dest.exists():
                    dest.unlink()
                shutil.move(str(src), str(dest))
        if cache_dir.exists() and cache_dir.resolve().is_relative_to(data_dir.resolve()):
            dest_cache = archive / "cache"
            if dest_cache.exists():
                shutil.rmtree(dest_cache)
            shutil.move(str(cache_dir), str(dest_cache))
    marker.write_text(fp + "\n", encoding="utf-8")
    return fp


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
    trained_path: str | None = None,
    scorer_path: Path | None = None,
    aiand_http: Any | None = None,
) -> FastAPI:
    cfg = load_config(config_path or ROOT / "config" / "models.yaml")
    models = load_models(cfg)
    by_id = {m.id: m for m in models}
    key = aiand_key if aiand_key is not None else os.getenv("AIAND_API_KEY", "")
    base = (aiand_base or os.getenv("AIAND_BASE_URL", "https://api.aiand.com/v1")).rstrip("/")
    token = router_key if router_key is not None else os.getenv("ROUTER_API_KEY", "change-me")
    limit = float(budget if budget is not None else os.getenv("BUDGET_LIMIT_USD", "15"))
    data_dir = ROOT / "data"
    default_log = data_dir / "requests.jsonl"
    default_spend = data_dir / "spend.txt"
    default_cache = data_dir / "cache"
    # Only rotate default local paths — tests pass explicit tmp paths and must not archive.
    if log_path is None and spend is None and cache_dir is None:
        key_fp = rotate_local_data_if_key_changed(
            data_dir=data_dir,
            api_key=key,
            log_path=default_log,
            spend_path=default_spend,
            cache_dir=default_cache,
        )
    else:
        key_fp = _key_fingerprint(key)
    spend_log = spend or SpendLog(default_spend, limit)
    log = log_path or default_log
    cache = RequestCache(cache_dir or default_cache)
    timeout_s = float(cfg.get("upstream_timeout_s") or os.getenv("UPSTREAM_TIMEOUT_S") or 120)
    token_cap = int(cfg.get("max_tokens_limit") or os.getenv("MAX_TOKENS_LIMIT") or 0)
    redact_keys = [
        str(k).lower()
        for k in (
            cfg.get("redact_keys")
            or ["key", "authorization", "token", "secret"]
        )
    ]
    upstream = provider or HttpAiandProvider(base, key, timeout_s=timeout_s)
    last_outcome: dict[str, Any] = {}
    replay_html = (Path(__file__).with_name("replay.html")).read_text(encoding="utf-8")
    flag_path = learned_flag or ROOT / "data" / "learned_wins.json"
    hop_path = parse_trained_path(
        trained_path if trained_path is not None else os.getenv("TRAINED_PATH")
    )
    scorer_file = scorer_path or Path(os.getenv("SCORER_PATH") or ROOT / "data" / "scorer.json")
    scorer_artifact = load_scorer(scorer_file)

    session_tracker = SessionTracker()

    app = FastAPI(title="AIand Coding Router", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def _check_auth(authorization: str | None = None, x_api_key: str | None = None) -> None:
        sent = ""
        if authorization and authorization.startswith("Bearer "):
            sent = authorization.removeprefix("Bearer ").strip()
        elif x_api_key:
            sent = x_api_key.strip()
        if not sent:
            raise HTTPException(401, "missing bearer token or x-api-key")
        if sent != token:
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
                    "display_name": m.display_name,
                    "input_per_1m": m.input_per_1m,
                    "output_per_1m": m.output_per_1m,
                }
            )
        return {"object": "list", "data": data}

    @app.get("/v1/console/overview")
    def console_overview(
        range: str = "30d",
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        _check_auth(authorization)
        return overview_payload(
            log_path=log,
            models=models,
            spend_usd=spend_log.total(),
            budget_usd=limit,
            aiand_key_set=bool(key),
            range_key=range,
            redact_keys=redact_keys,
            virtual_model=str(cfg.get("virtual_model") or "router/auto"),
        )

    @app.get("/v1/console/inferences")
    def console_inferences(
        q: str = "",
        model: str = "",
        range: str = "30d",
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        _check_auth(authorization)
        return inferences_payload(
            log_path=log,
            q=q,
            model=model,
            range_key=range,
            redact_keys=redact_keys,
        )

    @app.get("/v1/console/upstream/summary")
    async def console_upstream_summary(
        range: str = "30d",
        authorization: str | None = Header(default=None),
    ):
        _check_auth(authorization)
        return await proxy_aiand(
            origin=aiand_origin(base),
            api_key=key,
            path="/analytics/summary",
            params={"range": range},
            client=aiand_http,
        )

    @app.get("/v1/console/upstream/metrics")
    async def console_upstream_metrics(
        range: str = "30d",
        authorization: str | None = Header(default=None),
    ):
        _check_auth(authorization)
        return await proxy_aiand(
            origin=aiand_origin(base),
            api_key=key,
            path="/analytics/metrics",
            params={"range": range},
            client=aiand_http,
        )

    @app.get("/v1/console/upstream/logs")
    async def console_upstream_logs(
        request: Request,
        authorization: str | None = Header(default=None),
    ):
        _check_auth(authorization)
        params = {k: request.query_params[k] for k in LOG_QUERY_KEYS if k in request.query_params}
        return await proxy_aiand(
            origin=aiand_origin(base),
            api_key=key,
            path="/logs",
            params=params,
            client=aiand_http,
        )

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
            rows.append(_redact(json.loads(line), redact_keys))
        return rows

    @app.get("/codex/session-savings/{session_id}")
    @app.get("/v1/session-savings/{session_id}")
    def get_session_savings(
        session_id: str,
        authorization: str | None = Header(default=None),
        x_api_key: str | None = Header(default=None, alias="x-api-key"),
    ) -> dict[str, Any]:
        _check_auth(authorization, x_api_key)
        return session_tracker.get(session_id)

    @app.post("/v1/chat/completions")
    async def chat_completions(
        request: Request,
        authorization: str | None = Header(default=None),
        x_api_key: str | None = Header(default=None, alias="x-api-key"),
    ):
        _check_auth(authorization, x_api_key)

        body = await request.json()
        headers = {k.lower(): v for k, v in request.headers.items()}
        effort = (headers.get("x-routing-effort") or "medium").lower()
        allowed_raw = headers.get("x-allowed-models") or ""
        allowed = {x.strip() for x in allowed_raw.split(",") if x.strip()} or None

        requested = body.get("model") or "router/auto"
        phase = detect_phase(headers, body, last_outcome)
        tokens = estimate_tokens(body.get("messages") or [])
        needs_tools = bool(body.get("tools"))
        needs_json = wants_json(body)
        req_max = body.get("max_tokens") or body.get("max_completion_tokens")
        req_max_i = int(req_max) if req_max is not None else None
        if token_cap and req_max_i is not None and req_max_i > token_cap:
            raise HTTPException(400, f"max_tokens {req_max_i} exceeds limit {token_cap}")

        select_cfg = cfg
        if phase in DEBUG_PHASES and last_outcome.get("tests_passed") is False:
            select_cfg = dict(cfg)
            thresholds = dict(cfg.get("phase_threshold") or {})
            bump = float(cfg.get("debug_fail_threshold") or 53)
            for name in DEBUG_PHASES:
                thresholds[name] = bump
            select_cfg["phase_threshold"] = thresholds
        pick_kwargs = dict(
            phase=phase,
            needs_tools=needs_tools,
            tokens=tokens,
            effort=effort,
            allowed=allowed,
            spend_usd=spend_log.total(),
            budget_usd=limit,
            needs_json=needs_json,
            streaming=bool(body.get("stream")),
            max_tokens=req_max_i,
            latency_limit_ms=_latency_limit(cfg, headers),
        )

        tip_msg: str | None = None
        if requested not in VIRTUAL_MODELS and requested in by_id:
            decision_model = by_id[requested]
            decision = Decision(
                model=decision_model,
                phase=phase,
                threshold=0,
                reason=f"client pinned {requested}",
                candidates=[requested],
            )
            # Calculate what auto-routing would have chosen
            auto_dec = select_model(select_cfg, models, **pick_kwargs)
            if auto_dec.model.unit_cost < decision_model.unit_cost:
                pot_savings = max(
                    0.0,
                    estimate_cost(decision_model, tokens, 800)
                    - estimate_cost(auto_dec.model, tokens, 800),
                )
                tip_msg = f"Using router/auto would have saved ${pot_savings:.4f} (routed to {auto_dec.model.id})"
        else:
            use_learned = hop_path == "off" and learned_enabled(flag_path)
            picker = learned_select if use_learned else select_model
            decision = picker(select_cfg, models, **pick_kwargs)
            decision.effort = effort
            if hop_path != "off":
                trained = None
                if scorer_artifact is not None:
                    trained = trained_select(select_cfg, models, scorer_artifact, **pick_kwargs)
                decision = apply_trained_path(
                    hop_path, decision, trained, tokens=tokens, by_id=by_id
                )

        meta = _router_headers(decision)
        if tip_msg:
            meta["X-Router-Tip"] = tip_msg
            meta["X-Pioneer-Router-Tip"] = tip_msg

        streaming = bool(body.get("stream"))
        session_id = (
            headers.get("x-session-id")
            or headers.get("session_id")
            or headers.get("prompt-cache-key")
            or headers.get("prompt_cache_key")
            or ""
        )
        ck = request_cache_key(body, decision.model.id, key_fp)
        if not streaming:
            cached = cache.get(ck)
            if cached is not None:
                if session_id:
                    session_tracker.record(
                        session_id,
                        model_id=decision.model.id,
                        baseline_id=decision.baseline_model_id or "",
                        tokens_in=tokens,
                        tokens_out=0,
                        cost_usd=0.0,
                        savings_usd=decision.savings_usd or 0.0,
                    )
                append_jsonl(
                    log,
                    _jsonl_row(
                        decision,
                        requested=requested,
                        stream=False,
                        tokens_in=0,
                        tokens_out=0,
                        cost_usd=0.0,
                        latency_ms=0,
                        status=200,
                        cache_hit=True,
                    ),
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
        if _should_escalate(result, needs_json=needs_json) and effort != "low":
            nxt = stronger_than(models, decision.model)
            if nxt:
                meta["X-Router-Escalated-From"] = decision.model.id
                meta["X-Router-Model"] = nxt.id
                decision.reason += f" ; escalated to {nxt.id}"
                if decision.path not in {"shadow", "trained"}:
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
        message = (((result.get("json") or {}).get("choices") or [{}])[0].get("message") or {})
        tok_in = usage.get("prompt_tokens", tokens)
        tok_out = usage.get("completion_tokens", 0)
        if decision.baseline_model_id and decision.baseline_model_id in by_id:
            decision.savings_usd = round(
                max(0.0, estimate_cost(by_id[decision.baseline_model_id], tok_in, tok_out) - cost),
                6,
            )

        # Track session savings if session ID provided
        if session_id:
            session_tracker.record(
                session_id,
                model_id=decision.model.id,
                baseline_id=decision.baseline_model_id or "",
                tokens_in=tok_in,
                tokens_out=tok_out,
                cost_usd=cost,
                savings_usd=decision.savings_usd or 0.0,
            )

        row = _jsonl_row(
            decision,
            requested=requested,
            stream=streaming,
            tokens_in=tok_in,
            tokens_out=tok_out,
            cost_usd=round(cost, 6),
            latency_ms=latency_ms,
            status=result.get("status"),
            cache_hit=False,
            tool_valid=tool_calls_valid(message),
            json_valid=json_content_valid(message) if needs_json else None,
        )
        if last_outcome:
            row["tests_passed"] = last_outcome.get("tests_passed")
            row["patch_applied"] = last_outcome.get("patch_applied")
        if "X-Router-Escalated-From" in meta:
            row["escalated_from"] = meta["X-Router-Escalated-From"]
        append_jsonl(log, row)

        if result.get("stream"):
            return StreamingResponse(
                result["stream"],
                media_type="text/event-stream",
                headers=meta,
            )
        if result.get("status", 200) >= 400:
            return JSONResponse(result["json"], status_code=result["status"], headers=meta)
        payload = dict(result["json"])
        payload["model"] = requested
        cache.put(ck, payload)
        return JSONResponse(payload, headers=meta)

    @app.post("/v1/messages")
    async def anthropic_messages(
        request: Request,
        authorization: str | None = Header(default=None),
        x_api_key: str | None = Header(default=None, alias="x-api-key"),
    ):
        """Anthropic Messages API wire compatibility (for Claude Code & Claude Desktop)."""
        _check_auth(authorization, x_api_key)

        anthropic_body = await request.json()
        headers = {k.lower(): v for k, v in request.headers.items()}
        openai_body = anthropic_to_openai(anthropic_body)

        requested = anthropic_body.get("model") or "router/auto"
        effort = (headers.get("x-routing-effort") or "medium").lower()
        allowed_raw = headers.get("x-allowed-models") or ""
        allowed = {x.strip() for x in allowed_raw.split(",") if x.strip()} or None

        phase = detect_phase(headers, openai_body, last_outcome)
        tokens = estimate_tokens(openai_body.get("messages") or [])
        needs_tools = bool(openai_body.get("tools"))
        needs_json = wants_json(openai_body)
        req_max = openai_body.get("max_tokens")
        req_max_i = int(req_max) if req_max is not None else None

        select_cfg = cfg
        if phase in DEBUG_PHASES and last_outcome.get("tests_passed") is False:
            select_cfg = dict(cfg)
            thresholds = dict(cfg.get("phase_threshold") or {})
            bump = float(cfg.get("debug_fail_threshold") or 53)
            for name in DEBUG_PHASES:
                thresholds[name] = bump
            select_cfg["phase_threshold"] = thresholds
        pick_kwargs = dict(
            phase=phase,
            needs_tools=needs_tools,
            tokens=tokens,
            effort=effort,
            allowed=allowed,
            spend_usd=spend_log.total(),
            budget_usd=limit,
            needs_json=needs_json,
            streaming=bool(openai_body.get("stream")),
            max_tokens=req_max_i,
            latency_limit_ms=_latency_limit(cfg, headers),
        )

        if requested not in VIRTUAL_MODELS and requested in by_id:
            decision = Decision(
                model=by_id[requested],
                phase=phase,
                threshold=0,
                reason=f"client pinned {requested}",
                candidates=[requested],
            )
        else:
            use_learned = hop_path == "off" and learned_enabled(flag_path)
            picker = learned_select if use_learned else select_model
            decision = picker(select_cfg, models, **pick_kwargs)
            decision.effort = effort
            if hop_path != "off":
                trained = None
                if scorer_artifact is not None:
                    trained = trained_select(select_cfg, models, scorer_artifact, **pick_kwargs)
                decision = apply_trained_path(
                    hop_path, decision, trained, tokens=tokens, by_id=by_id
                )

        meta = _router_headers(decision)
        meta["pioneer_routed_model"] = decision.model.id
        meta["pioneer_savings"] = str(decision.savings_usd or 0.0)

        if provider is None and not key:
            raise HTTPException(500, "AIAND_API_KEY is not set")
        if spend_log.total() >= limit:
            raise HTTPException(429, f"budget limit ${limit} reached")

        upstream_body = {k: v for k, v in openai_body.items() if k != "model"}
        upstream_body["model"] = decision.model.id
        streaming = bool(openai_body.get("stream"))
        if streaming:
            upstream_body.setdefault("stream_options", {})
            if isinstance(upstream_body["stream_options"], dict):
                upstream_body["stream_options"].setdefault("include_usage", True)

        t0 = time.perf_counter()
        result = await _call_provider(upstream, upstream_body)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        usage = _usage(result)
        cost = estimate_cost(
            decision.model,
            usage.get("prompt_tokens", tokens),
            usage.get("completion_tokens", 0),
        )
        spend_log.add(cost)
        tok_in = usage.get("prompt_tokens", tokens)
        tok_out = usage.get("completion_tokens", 0)
        if decision.baseline_model_id and decision.baseline_model_id in by_id:
            decision.savings_usd = round(
                max(0.0, estimate_cost(by_id[decision.baseline_model_id], tok_in, tok_out) - cost),
                6,
            )

        session_id = (
            headers.get("x-session-id")
            or headers.get("session_id")
            or headers.get("prompt-cache-key")
            or headers.get("prompt_cache_key")
            or ""
        )
        if session_id:
            session_tracker.record(
                session_id,
                model_id=decision.model.id,
                baseline_id=decision.baseline_model_id or "",
                tokens_in=tok_in,
                tokens_out=tok_out,
                cost_usd=cost,
                savings_usd=decision.savings_usd or 0.0,
            )

        row = _jsonl_row(
            decision,
            requested=requested,
            stream=streaming,
            tokens_in=tok_in,
            tokens_out=tok_out,
            cost_usd=round(cost, 6),
            latency_ms=latency_ms,
            status=result.get("status"),
            cache_hit=False,
            wire="anthropic_messages",
        )
        append_jsonl(log, row)

        if streaming and result.get("stream"):
            return StreamingResponse(
                stream_openai_to_anthropic_sse(result["stream"], requested, decision, tok_in),
                media_type="text/event-stream",
                headers=meta,
            )

        anthropic_resp = openai_to_anthropic_response(
            result.get("json") or {}, requested, decision, tok_in, tok_out
        )
        return JSONResponse(anthropic_resp, headers=meta)

    @app.post("/v1/responses")
    async def responses_api(
        request: Request,
        authorization: str | None = Header(default=None),
        x_api_key: str | None = Header(default=None, alias="x-api-key"),
    ):
        """OpenAI Responses API wire compatibility (for Codex CLI)."""
        _check_auth(authorization, x_api_key)
        body = await request.json()
        
        # Convert Responses format prompt/input to chat messages if needed
        chat_body = dict(body)
        if "input" in body and "messages" not in body:
            inp = body["input"]
            msgs = [{"role": "user", "content": inp if isinstance(inp, str) else json.dumps(inp)}]
            chat_body["messages"] = msgs
            chat_body.pop("input", None)

        req_mock = Request(
            scope={
                "type": "http",
                "method": "POST",
                "headers": request.headers.raw,
            }
        )
        # Call chat completions logic internally
        resp = await chat_completions(request, authorization, x_api_key)
        return resp

    return app


def _router_headers(decision: Decision) -> dict[str, str]:
    if decision.path in {"shadow", "trained"}:
        meta = {
            "X-Router-Phase": decision.phase,
            "X-Router-Model": decision.model.id,
            "X-Router-Effort": decision.effort,
            "X-Router-Path": decision.path,
            "X-Router-Threshold": str(decision.threshold),
            "X-Router-Candidates": ",".join(decision.candidates),
        }
        if decision.complexity_bin:
            meta["X-Router-Complexity-Bin"] = decision.complexity_bin
        if decision.confidence is not None:
            meta["X-Router-Confidence"] = str(decision.confidence)
        if decision.rule:
            meta["X-Router-Rule"] = decision.rule
        if decision.baseline_model_id:
            meta["X-Router-Baseline-Model"] = decision.baseline_model_id
        if decision.savings_usd is not None:
            meta["X-Router-Savings-Usd"] = str(decision.savings_usd)
        if decision.reason_codes:
            meta["X-Router-Reason-Codes"] = ",".join(decision.reason_codes)
        if decision.path == "shadow" and decision.trained_selected:
            meta["X-Router-Trained-Would"] = decision.trained_selected
        return meta
    meta = {
        "X-Router-Phase": decision.phase,
        "X-Router-Model": decision.model.id,
        "X-Router-Reason": decision.reason,
        "X-Router-Threshold": str(decision.threshold),
        "X-Router-Candidates": ",".join(decision.candidates),
    }
    if decision.reason_codes:
        meta["X-Router-Reason-Codes"] = ",".join(decision.reason_codes)
    if "scorer_down" in (decision.reason_codes or []):
        meta["X-Router-Path"] = "rules"
        if decision.rule:
            meta["X-Router-Rule"] = decision.rule
    return meta


def _jsonl_row(decision: Decision, **extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "phase": decision.phase,
        "selected": decision.model.id,
        "reason": decision.reason,
        "candidates": decision.candidates,
        "path": decision.path,
        **extra,
    }
    if decision.trained_selected:
        row["trained_selected"] = decision.trained_selected
    if decision.trained_confidence is not None:
        row["trained_confidence"] = decision.trained_confidence
    if decision.confidence is not None:
        row["confidence"] = decision.confidence
    if decision.complexity_bin:
        row["complexity_bin"] = decision.complexity_bin
    if decision.p_success is not None:
        row["p_success"] = decision.p_success
    if decision.rule:
        row["rule"] = decision.rule
    if decision.reason_codes:
        row["reason_codes"] = decision.reason_codes
    if decision.max_regret is not None:
        row["max_regret"] = decision.max_regret
    row["threshold"] = decision.threshold
    if decision.baseline_model_id:
        row["baseline_model_id"] = decision.baseline_model_id
    if decision.savings_usd is not None:
        row["savings_usd"] = decision.savings_usd
    if decision.rules_cost_delta_usd is not None:
        row["rules_cost_delta_usd"] = decision.rules_cost_delta_usd
    if decision.effort:
        row["effort"] = decision.effort
    return row


def _should_escalate(result: dict[str, Any], *, needs_json: bool = False) -> bool:
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
    if not tool_calls_valid(message):
        return True
    if needs_json and not json_content_valid(message):
        return True
    return False


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


def _latency_limit(cfg: dict[str, Any], headers: dict[str, str]) -> float | None:
    raw = headers.get("x-latency-limit") or cfg.get("latency_limit_ms") or os.getenv("LATENCY_LIMIT_MS")
    if raw in (None, "", 0, "0"):
        return None
    try:
        limit = float(raw)
    except (TypeError, ValueError):
        return None
    return limit if limit > 0 else None
