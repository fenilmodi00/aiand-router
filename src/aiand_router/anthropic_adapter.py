from __future__ import annotations

import json
import time
from typing import Any, AsyncIterator

from .router import Decision


class SessionTracker:
    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}

    def record(
        self,
        session_id: str,
        *,
        model_id: str,
        baseline_id: str,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,
        savings_usd: float,
    ) -> None:
        if not session_id:
            return
        entry = self._sessions.setdefault(
            session_id,
            {
                "session_id": session_id,
                "created_at": time.time(),
                "updated_at": time.time(),
                "total_requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "spend_usd": 0.0,
                "savings_usd": 0.0,
                "baseline_model": baseline_id or "deepseek-ai/deepseek-v4-pro",
                "models_used": {},
            },
        )
        entry["updated_at"] = time.time()
        entry["total_requests"] += 1
        entry["input_tokens"] += tokens_in
        entry["output_tokens"] += tokens_out
        entry["spend_usd"] = round(entry["spend_usd"] + cost_usd, 6)
        entry["savings_usd"] = round(entry["savings_usd"] + savings_usd, 6)
        if baseline_id:
            entry["baseline_model"] = baseline_id
        entry["models_used"][model_id] = entry["models_used"].get(model_id, 0) + 1

    def get(self, session_id: str) -> dict[str, Any]:
        if session_id in self._sessions:
            data = dict(self._sessions[session_id])
            data["found"] = True
            return data
        return {
            "found": False,
            "session_id": session_id,
            "savings_usd": 0.0,
            "total_requests": 0,
            "spend_usd": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "baseline_model": "deepseek-ai/deepseek-v4-pro",
            "models_used": {},
        }


def anthropic_to_openai(body: dict[str, Any]) -> dict[str, Any]:
    """Convert Anthropic messages request to OpenAI chat completions body."""
    messages: list[dict[str, Any]] = []

    # System prompt
    sys = body.get("system")
    if sys:
        if isinstance(sys, str) and sys.strip():
            messages.append({"role": "system", "content": sys.strip()})
        elif isinstance(sys, list):
            texts = [
                b.get("text", "")
                for b in sys
                if isinstance(b, dict) and b.get("type") == "text"
            ]
            if texts:
                messages.append({"role": "system", "content": "\n".join(texts)})

    for msg in body.get("messages") or []:
        role = msg.get("role", "user")
        content = msg.get("content")
        if isinstance(content, str):
            messages.append({"role": role, "content": content})
        elif isinstance(content, list):
            text_parts = []
            tool_calls = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                b_type = block.get("type")
                if b_type == "text":
                    text_parts.append(block.get("text", ""))
                elif b_type == "tool_use":
                    inp = block.get("input", {})
                    inp_str = json.dumps(inp) if isinstance(inp, dict) else str(inp or "{}")
                    tool_calls.append(
                        {
                            "id": block.get("id", f"call_{len(tool_calls)}"),
                            "type": "function",
                            "function": {
                                "name": block.get("name", ""),
                                "arguments": inp_str,
                            },
                        }
                    )
                elif b_type == "tool_result":
                    res_content = block.get("content", "")
                    if isinstance(res_content, list):
                        res_content = " ".join(
                            p.get("text", "") for p in res_content if isinstance(p, dict)
                        )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": block.get("tool_use_id", ""),
                            "content": str(res_content),
                        }
                    )
            if text_parts or tool_calls:
                m_obj: dict[str, Any] = {"role": role}
                if text_parts:
                    m_obj["content"] = "\n".join(text_parts)
                if tool_calls:
                    m_obj["tool_calls"] = tool_calls
                messages.append(m_obj)

    openai_body: dict[str, Any] = {
        "model": body.get("model", "router/auto"),
        "messages": messages,
        "stream": bool(body.get("stream")),
    }
    if "temperature" in body:
        openai_body["temperature"] = body["temperature"]
    if "top_p" in body:
        openai_body["top_p"] = body["top_p"]
    if "max_tokens" in body:
        openai_body["max_tokens"] = body["max_tokens"]

    # Convert tools
    if body.get("tools"):
        openai_tools = []
        for t in body["tools"]:
            if isinstance(t, dict):
                openai_tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": t.get("name", ""),
                            "description": t.get("description", ""),
                            "parameters": t.get("input_schema", {}),
                        },
                    }
                )
        if openai_tools:
            openai_body["tools"] = openai_tools

    return openai_body


def openai_to_anthropic_response(
    result_json: dict[str, Any],
    requested_model: str,
    decision: Decision,
    tok_in: int,
    tok_out: int,
) -> dict[str, Any]:
    """Convert OpenAI completions response to Anthropic messages payload."""
    choices = result_json.get("choices") or [{}]
    first = choices[0] if choices else {}
    msg = first.get("message") or {}
    finish = first.get("finish_reason", "stop")

    stop_reason = "end_turn"
    if finish == "length":
        stop_reason = "max_tokens"
    elif finish == "tool_calls" or msg.get("tool_calls"):
        stop_reason = "tool_use"

    content_blocks: list[dict[str, Any]] = []
    if msg.get("content"):
        content_blocks.append({"type": "text", "text": msg["content"]})
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function") or {}
        fn_args = {}
        try:
            fn_args = json.loads(fn.get("arguments") or "{}")
        except Exception:
            fn_args = {"raw": fn.get("arguments")}
        content_blocks.append(
            {
                "type": "tool_use",
                "id": tc.get("id", f"call_{len(content_blocks)}"),
                "name": fn.get("name", ""),
                "input": fn_args,
            }
        )

    msg_id = result_json.get("id") or f"msg_{int(time.time()*1000)}"
    return {
        "id": msg_id if msg_id.startswith("msg_") else f"msg_{msg_id}",
        "type": "message",
        "role": "assistant",
        "model": requested_model,
        "content": content_blocks,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": tok_in,
            "output_tokens": tok_out,
        },
        "pioneer_routed_model": decision.model.id,
        "pioneer_savings": decision.savings_usd or 0.0,
    }


async def stream_openai_to_anthropic_sse(
    openai_stream_generator: AsyncIterator[bytes | str],
    requested_model: str,
    decision: Decision,
    tok_in: int,
) -> AsyncIterator[bytes]:
    """Generator converting OpenAI SSE chunks to Anthropic SSE events."""
    msg_id = f"msg_{int(time.time()*1000)}"

    start_event = {
        "type": "message_start",
        "message": {
            "id": msg_id,
            "type": "message",
            "role": "assistant",
            "model": requested_model,
            "content": [],
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {"input_tokens": tok_in, "output_tokens": 0},
        },
        "pioneer_routed_model": decision.model.id,
        "pioneer_savings": decision.savings_usd or 0.0,
    }
    yield f"event: message_start\ndata: {json.dumps(start_event)}\n\n".encode("utf-8")

    block_started = False
    tok_out = 0

    async for chunk in openai_stream_generator:
        text_chunk = chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk)
        for line in text_chunk.splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            data_str = line.removeprefix("data:").strip()
            if not data_str or data_str == "[DONE]":
                continue
            try:
                data = json.loads(data_str)
                delta = ((data.get("choices") or [{}])[0].get("delta") or {})
                content = delta.get("content")
                if content:
                    if not block_started:
                        block_start = {
                            "type": "content_block_start",
                            "index": 0,
                            "content_block": {"type": "text", "text": ""},
                        }
                        yield f"event: content_block_start\ndata: {json.dumps(block_start)}\n\n".encode("utf-8")
                        block_started = True

                    tok_out += max(1, len(content) // 4)
                    block_delta = {
                        "type": "content_block_delta",
                        "index": 0,
                        "delta": {"type": "text_delta", "text": content},
                    }
                    yield f"event: content_block_delta\ndata: {json.dumps(block_delta)}\n\n".encode("utf-8")
            except Exception:
                continue

    if block_started:
        block_stop = {"type": "content_block_stop", "index": 0}
        yield f"event: content_block_stop\ndata: {json.dumps(block_stop)}\n\n".encode("utf-8")

    msg_delta = {
        "type": "message_delta",
        "delta": {"stop_reason": "end_turn", "stop_sequence": None},
        "usage": {"output_tokens": tok_out},
    }
    yield f"event: message_delta\ndata: {json.dumps(msg_delta)}\n\n".encode("utf-8")

    yield f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n".encode("utf-8")
