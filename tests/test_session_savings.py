import pytest
from fastapi.testclient import TestClient

from aiand_router.app import create_app
from aiand_router.router import SpendLog
from tests.test_anthropic_messages import FakeProvider


def test_session_savings_tracking(tmp_path):
    app = create_app(
        provider=FakeProvider("turn completed"),
        router_key="secret",
        aiand_key="fake-aiand",
        spend=SpendLog(tmp_path / "spend.txt", 10.0),
        log_path=tmp_path / "requests.jsonl",
        cache_dir=tmp_path / "cache",
    )
    client = TestClient(app)

    # 1. Send first request with session ID
    client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer secret", "x-session-id": "sess_abc123"},
        json={"model": "router/auto", "messages": [{"role": "user", "content": "step 1"}]},
    )

    # 2. Send second request with same session ID
    client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer secret", "x-session-id": "sess_abc123"},
        json={"model": "router/auto", "messages": [{"role": "user", "content": "step 2"}]},
    )

    # 3. Query session savings endpoint
    res = client.get(
        "/v1/session-savings/sess_abc123",
        headers={"Authorization": "Bearer secret"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["found"] is True
    assert data["session_id"] == "sess_abc123"
    assert data["total_requests"] == 2
    assert data["input_tokens"] > 0
    assert "savings_usd" in data

    # 4. Codex alias endpoint
    res_codex = client.get(
        "/codex/session-savings/sess_abc123",
        headers={"x-api-key": "secret"},
    )
    assert res_codex.status_code == 200
    assert res_codex.json()["found"] is True


def test_router_tip_on_pinned_expensive_model(tmp_path):
    app = create_app(
        provider=FakeProvider("direct response"),
        router_key="secret",
        aiand_key="fake-aiand",
        spend=SpendLog(tmp_path / "spend.txt", 10.0),
        log_path=tmp_path / "requests.jsonl",
    )
    client = TestClient(app)

    # Pin expensive model (kimi-k3 or deepseek-v4-pro)
    res = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer secret"},
        json={"model": "moonshotai/kimi-k3", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert res.status_code == 200
    assert "x-router-tip" in res.headers or "x-pioneer-router-tip" in res.headers
