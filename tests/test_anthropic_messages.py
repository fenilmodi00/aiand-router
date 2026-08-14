import json
import pytest
from fastapi.testclient import TestClient

from aiand_router.app import create_app
from aiand_router.router import Model, SpendLog


class FakeProvider:
    def __init__(self, reply: str = "Hello from AIand!"):
        self.reply = reply

    async def complete(self, body: dict):
        if body.get("stream"):
            async def gen():
                chunk = {
                    "id": "chatcmpl-stream",
                    "choices": [{"delta": {"content": self.reply}, "index": 0}],
                }
                yield f"data: {json.dumps(chunk)}\n\n".encode("utf-8")
                yield b"data: [DONE]\n\n"

            return {"status": 200, "stream": gen()}
        return {
            "status": 200,
            "json": {
                "id": "chatcmpl-test",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": self.reply},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 15, "completion_tokens": 8},
            },
        }


def test_anthropic_messages_non_streaming(tmp_path):
    app = create_app(
        provider=FakeProvider("Here is your function"),
        router_key="secret",
        aiand_key="fake-aiand",
        spend=SpendLog(tmp_path / "spend.txt", 10.0),
        log_path=tmp_path / "requests.jsonl",
    )
    client = TestClient(app)

    payload = {
        "model": "router/auto",
        "system": "You are an expert coder.",
        "messages": [
            {"role": "user", "content": "Write a binary search function."}
        ],
        "max_tokens": 1000,
    }

    res = client.post(
        "/v1/messages",
        headers={"x-api-key": "secret", "anthropic-version": "2023-06-01"},
        json=payload,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "message"
    assert data["role"] == "assistant"
    assert len(data["content"]) == 1
    assert data["content"][0]["text"] == "Here is your function"
    assert data["stop_reason"] == "end_turn"
    assert "pioneer_routed_model" in data
    assert res.headers.get("x-router-model") is not None


def test_anthropic_messages_streaming(tmp_path):
    app = create_app(
        provider=FakeProvider("Streaming code chunk"),
        router_key="secret",
        aiand_key="fake-aiand",
        spend=SpendLog(tmp_path / "spend.txt", 10.0),
        log_path=tmp_path / "requests.jsonl",
    )
    client = TestClient(app)

    payload = {
        "model": "router/auto",
        "messages": [{"role": "user", "content": "hello"}],
        "stream": True,
    }

    res = client.post(
        "/v1/messages",
        headers={"Authorization": "Bearer secret"},
        json=payload,
    )
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["content-type"]
    text = res.text
    assert "event: message_start" in text
    assert "event: content_block_delta" in text
    assert "event: message_delta" in text
    assert "event: message_stop" in text
