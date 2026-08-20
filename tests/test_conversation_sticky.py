"""FireRouter-style conversation stickiness behind existing session headers."""

from __future__ import annotations

from fastapi.testclient import TestClient

from aiand_router.app import create_app
from aiand_router.router import SpendLog
from tests.test_anthropic_messages import FakeProvider

AUTH = {"Authorization": "Bearer secret"}
CHAT = {"model": "router/auto", "messages": [{"role": "user", "content": "ping"}]}


def _client(tmp_path):
    app = create_app(
        provider=FakeProvider("ok"),
        router_key="secret",
        aiand_key="fake-aiand",
        spend=SpendLog(tmp_path / "spend.txt", 10.0),
        log_path=tmp_path / "requests.jsonl",
        cache_dir=tmp_path / "cache",
        trained_path="shadow",
    )
    return TestClient(app)


def test_second_turn_sticks_on_x_session_id(tmp_path):
    client = _client(tmp_path)
    headers = {**AUTH, "x-session-id": "conv-1"}
    first = client.post("/v1/chat/completions", headers=headers, json=CHAT)
    second = client.post(
        "/v1/chat/completions",
        headers=headers,
        json={"model": "router/auto", "messages": [{"role": "user", "content": "pong"}]},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert "x-router-conversation-sticky" not in first.headers
    assert second.headers.get("x-router-conversation-sticky") == "1"
    assert second.headers["x-router-model"] == first.headers["x-router-model"]
    assert "conversation_sticky" in (second.headers.get("x-router-reason-codes") or "")


def test_session_id_and_prompt_cache_key_aliases(tmp_path):
    client = _client(tmp_path)
    first = client.post(
        "/v1/chat/completions",
        headers={**AUTH, "session_id": "alias-1"},
        json=CHAT,
    )
    second = client.post(
        "/v1/chat/completions",
        headers={**AUTH, "prompt-cache-key": "alias-1"},
        json={"model": "router/auto", "messages": [{"role": "user", "content": "pong"}]},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.headers.get("x-router-conversation-sticky") == "1"
    assert second.headers["x-router-model"] == first.headers["x-router-model"]


def test_anthropic_messages_sticks(tmp_path):
    client = _client(tmp_path)
    headers = {
        "x-api-key": "secret",
        "anthropic-version": "2023-06-01",
        "x-session-id": "anth-1",
    }
    body = {
        "model": "router/auto",
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 64,
    }
    first = client.post("/v1/messages", headers=headers, json=body)
    second = client.post(
        "/v1/messages",
        headers=headers,
        json={
            "model": "router/auto",
            "messages": [{"role": "user", "content": "pong"}],
            "max_tokens": 64,
        },
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.headers.get("x-router-conversation-sticky") == "1"
    assert second.headers["x-router-model"] == first.headers["x-router-model"]
    assert second.json().get("pioneer_routed_model") == first.headers["x-router-model"]


def test_effort_change_does_not_stick(tmp_path):
    client = _client(tmp_path)
    first = client.post(
        "/v1/chat/completions",
        headers={**AUTH, "x-session-id": "conv-2", "x-routing-effort": "medium"},
        json=CHAT,
    )
    second = client.post(
        "/v1/chat/completions",
        headers={**AUTH, "x-session-id": "conv-2", "x-routing-effort": "high"},
        json=CHAT,
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert "x-router-conversation-sticky" not in second.headers


def test_allowlist_change_does_not_stick(tmp_path):
    client = _client(tmp_path)
    mid = "deepseek-ai/deepseek-v4-flash"
    first = client.post(
        "/v1/chat/completions",
        headers={**AUTH, "x-session-id": "conv-allow", "x-allowed-models": mid},
        json=CHAT,
    )
    second = client.post(
        "/v1/chat/completions",
        headers={
            **AUTH,
            "x-session-id": "conv-allow",
            "x-allowed-models": "deepseek-ai/deepseek-v4-pro",
        },
        json=CHAT,
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert "x-router-conversation-sticky" not in second.headers
    assert second.headers["x-router-model"] == "deepseek-ai/deepseek-v4-pro"


def test_hop_path_change_does_not_stick(tmp_path):
    client = _client(tmp_path)
    first = client.post(
        "/v1/chat/completions",
        headers={**AUTH, "x-session-id": "conv-hop", "x-router-hop-path": "shadow"},
        json=CHAT,
    )
    second = client.post(
        "/v1/chat/completions",
        headers={**AUTH, "x-session-id": "conv-hop", "x-router-hop-path": "off"},
        json=CHAT,
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert "x-router-conversation-sticky" not in second.headers


def test_pinned_model_skips_stickiness(tmp_path):
    client = _client(tmp_path)
    headers = {**AUTH, "x-session-id": "conv-3"}
    pinned = {
        "model": "deepseek-ai/deepseek-v4-pro",
        "messages": [{"role": "user", "content": "pin"}],
    }
    first = client.post("/v1/chat/completions", headers=headers, json=pinned)
    second = client.post("/v1/chat/completions", headers=headers, json=pinned)
    assert first.status_code == 200
    assert second.status_code == 200
    assert "x-router-conversation-sticky" not in first.headers
    assert "x-router-conversation-sticky" not in second.headers


def test_no_session_header_does_not_stick(tmp_path):
    client = _client(tmp_path)
    first = client.post("/v1/chat/completions", headers=AUTH, json=CHAT)
    second = client.post(
        "/v1/chat/completions",
        headers=AUTH,
        json={"model": "router/auto", "messages": [{"role": "user", "content": "pong"}]},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert "x-router-conversation-sticky" not in first.headers
    assert "x-router-conversation-sticky" not in second.headers
