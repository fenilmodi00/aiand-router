from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from aiand_router.app import create_app
from aiand_router.console import aiand_origin
from aiand_router.router import SpendLog
from fastapi.testclient import TestClient

AUTH = {"Authorization": "Bearer secret"}
AIAND_KEY = "sk-aiand-test-key"
FLASH = "deepseek-ai/deepseek-v4-flash"
PRO = "deepseek-ai/deepseek-v4-pro"


class FakeProvider:
    async def complete(self, body: dict) -> dict:
        return {
            "status": 200,
            "json": {
                "id": "chatcmpl-fake",
                "choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        }


class FakeAiandHttp:
    def __init__(self, status: int = 200, payload: Any = None, exc: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self.status = status
        self.payload = payload if payload is not None else {"ok": True}
        self.exc = exc

    async def get(self, url: str, headers=None, params=None):
        self.calls.append({"url": url, "headers": dict(headers or {}), "params": dict(params or {})})
        if self.exc:
            raise self.exc
        return httpx.Response(self.status, json=self.payload)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _client(
    tmp_path,
    *,
    aiand_key: str | None = "",
    aiand_http=None,
    spend_usd: float = 1.25,
    budget: float = 15.0,
):
    spend = SpendLog(tmp_path / "spend.txt", budget)
    if spend_usd:
        spend.add(spend_usd)
    app = create_app(
        provider=FakeProvider(),
        spend=spend,
        log_path=tmp_path / "requests.jsonl",
        router_key="secret",
        budget=budget,
        cache_dir=tmp_path / "cache",
        aiand_key=aiand_key,
        aiand_base="https://api.aiand.com/v1",
        aiand_http=aiand_http,
    )
    return TestClient(app)


def test_aiand_origin_strips_v1():
    assert aiand_origin("https://api.aiand.com/v1") == "https://api.aiand.com"
    assert aiand_origin("https://api.aiand.com/v1/") == "https://api.aiand.com"
    assert aiand_origin("https://api.aiand.com") == "https://api.aiand.com"


def test_console_overview_requires_auth(tmp_path):
    client = _client(tmp_path)
    assert client.get("/v1/console/overview").status_code == 401
    assert client.get("/v1/console/inferences").status_code == 401
    assert client.get("/v1/console/upstream/summary").status_code == 401


def test_console_overview_empty_log_is_zeros(tmp_path):
    client = _client(tmp_path, aiand_key="")
    response = client.get("/v1/console/overview", headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert body["range"] == "30d"
    assert body["virtual_model"] == "router/auto"
    assert body["routed_requests"] == 0
    assert body["spend_usd"] == 1.25
    assert body["budget_usd"] == 15.0
    assert body["savings_usd"] == 0.0
    assert body["savings_pct"] == 0.0
    assert body["fallback_count"] == 0
    assert body["fallback_rate"] == 0.0
    assert body["cache_hits"] == 0
    assert body["aiand_key_set"] is False
    assert body["cost_routed_usd"] == 0.0
    assert body["cost_baseline_usd"] == 0.0
    assert len(body["candidates"]) == 9
    assert all(c["enabled"] is True for c in body["candidates"])
    assert {c["id"] for c in body["candidates"]} == {
        "qwen/qwen3.6-27b",
        FLASH,
        "google/gemma-4-31b-it",
        "openai/gpt-oss-120b",
        "moonshotai/kimi-k2.7-code",
        PRO,
        "zai-org/glm-5.2",
        "moonshotai/kimi-k3",
        "motif-technologies/motif-3",
    }
    assert body["candidate_mix"][0]["count"] == 0
    blob = json.dumps(body).lower()
    assert "sk-" not in blob
    assert "aiand_api_key" not in blob


def test_console_overview_skips_outcome_and_counts_hops(tmp_path):
    _write_jsonl(
        tmp_path / "requests.jsonl",
        [
            {"selected": FLASH, "phase": "plan", "cost_usd": 0.01, "cache_hit": True, "path": "rules"},
            {"kind": "outcome", "phase": "test", "tests_passed": False},
            {
                "selected": PRO,
                "phase": "debug",
                "cost_usd": 0.02,
                "savings_usd": 0.04,
                "reason": "score=1 ; escalated to " + PRO,
                "escalated_from": FLASH,
            },
        ],
    )
    client = _client(tmp_path, aiand_key=AIAND_KEY, spend_usd=0.5)
    body = client.get("/v1/console/overview?range=all", headers=AUTH).json()
    assert body["range"] == "all"
    assert body["routed_requests"] == 2
    assert body["cache_hits"] == 1
    assert body["fallback_count"] == 1
    assert body["fallback_rate"] == 0.5
    assert body["cost_routed_usd"] == 0.03
    assert body["savings_usd"] == 0.04
    assert body["cost_baseline_usd"] == 0.07
    assert abs(body["savings_pct"] - (100.0 * 0.04 / 0.07)) < 1e-9
    assert body["spend_usd"] == 0.5
    assert body["aiand_key_set"] is True
    mix = {row["id"]: row for row in body["candidate_mix"]}
    assert mix[FLASH]["count"] == 1
    assert mix[PRO]["count"] == 1
    assert mix[FLASH]["pct"] == 50.0


def test_console_overview_does_not_invent_savings_pct(tmp_path):
    _write_jsonl(
        tmp_path / "requests.jsonl",
        [{"selected": FLASH, "phase": "plan", "cost_usd": 1.0, "reason": "score=12"}],
    )
    body = _client(tmp_path).get("/v1/console/overview?range=all", headers=AUTH).json()
    assert body["cost_routed_usd"] == 1.0
    assert body["savings_usd"] == 0.0
    assert body["cost_baseline_usd"] == 1.0
    assert body["savings_pct"] == 0.0


def test_console_overview_range_filters_timestamped_rows(tmp_path):
    now = datetime.now(timezone.utc)
    _write_jsonl(
        tmp_path / "requests.jsonl",
        [
            {"ts": (now - timedelta(days=40)).isoformat(), "selected": FLASH, "phase": "plan", "cost_usd": 1},
            {"ts": now.isoformat(), "selected": PRO, "phase": "edit", "cost_usd": 2},
            {"selected": "qwen/qwen3.6-27b", "phase": "summarize", "cost_usd": 3},
        ],
    )
    client = _client(tmp_path)
    month = client.get("/v1/console/overview?range=30d", headers=AUTH).json()
    assert month["range"] == "30d"
    assert month["routed_requests"] == 2
    assert month["cost_routed_usd"] == 5.0
    day = client.get("/v1/console/overview?range=24h", headers=AUTH).json()
    assert day["routed_requests"] == 2
    everything = client.get("/v1/console/overview?range=all", headers=AUTH).json()
    assert everything["routed_requests"] == 3
    assert everything["cost_routed_usd"] == 6.0
    assert len(day["usage_buckets"]) == 24
    assert sum(b["requests"] for b in day["usage_buckets"]) == 1


def test_usage_buckets_include_hops_without_baseline_estimate(tmp_path):
    now = datetime.now(timezone.utc)
    _write_jsonl(
        tmp_path / "requests.jsonl",
        [
            {
                "ts": now.isoformat(),
                "selected": FLASH,
                "phase": "plan",
                "cost_usd": 0.02,
                "savings_usd": 0.08,
            },
            {
                "ts": now.isoformat(),
                "selected": PRO,
                "phase": "edit",
                "cost_usd": 0.05,
            },
            {
                "ts": now.isoformat(),
                "selected": FLASH,
                "phase": "debug",
                "cost_usd": 0.01,
                "cost_baseline": 0.09,
            },
        ],
    )
    body = _client(tmp_path).get("/v1/console/overview?range=24h", headers=AUTH).json()
    assert body["cost_routed_usd"] == 0.08
    buckets = body["usage_buckets"]
    assert len(buckets) == 24
    assert all("spend_usd" in b and "baseline_usd" in b for b in buckets)
    active = [b for b in buckets if b["requests"]]
    assert len(active) == 1
    assert active[0]["requests"] == 3
    # Actual spend always counted; hop without estimate contributes cost as its own baseline.
    assert active[0]["spend_usd"] == 0.08
    assert active[0]["baseline_usd"] == 0.24
    empty = next(b for b in buckets if b["requests"] == 0)
    assert empty["spend_usd"] == 0.0
    assert empty["baseline_usd"] == 0.0


def test_usage_buckets_empty_log_has_no_fake_spend(tmp_path):
    body = _client(tmp_path).get("/v1/console/overview?range=30d", headers=AUTH).json()
    assert body["usage_buckets"] == []
    assert body["cost_routed_usd"] == 0.0
    assert body["cost_baseline_usd"] == 0.0
    assert body["savings_pct"] == 0.0


def test_console_inferences_filters_redacts_and_keeps_nulls(tmp_path):
    now = datetime.now(timezone.utc).isoformat()
    _write_jsonl(
        tmp_path / "requests.jsonl",
        [
            {
                "ts": now,
                "selected": FLASH,
                "phase": "plan",
                "reason": "score=12",
                "tokens_in": 10,
                "tokens_out": 5,
                "latency_ms": 40,
                "status": 200,
                "cache_hit": False,
                "path": "rules",
                "cost_usd": 0.01,
                "api_key": AIAND_KEY,
                "authorization": "Bearer hunter2",
                "password": "hunter2",
            },
            {
                "ts": now,
                "selected": PRO,
                "phase": "debug",
                "reason": "escalated to pro",
                "tokens_in": 8,
                "tokens_out": 2,
                "latency_ms": 90,
                "status": 200,
                "ttft_ms": 12,
                "tests_passed": False,
            },
            {"kind": "outcome", "phase": "test", "tests_passed": True, "api_key": AIAND_KEY},
        ],
    )
    client = _client(tmp_path)
    all_rows = client.get("/v1/console/inferences?range=all", headers=AUTH).json()["data"]
    assert len(all_rows) == 2
    flash = next(r for r in all_rows if r["selected"] == FLASH)
    assert flash["ttft_ms"] is None
    assert flash["llmaj_score"] is None
    assert flash["tests_passed"] is None
    assert flash["ts"] == now
    pro = next(r for r in all_rows if r["selected"] == PRO)
    assert pro["ttft_ms"] == 12
    assert pro["tests_passed"] is False
    q = client.get("/v1/console/inferences?q=plan&range=all", headers=AUTH).json()["data"]
    assert [r["selected"] for r in q] == [FLASH]
    model = client.get(f"/v1/console/inferences?model={PRO}&range=all", headers=AUTH).json()["data"]
    assert [r["selected"] for r in model] == [PRO]
    blob = json.dumps(all_rows)
    assert AIAND_KEY not in blob
    assert "hunter2" not in blob
    assert "authorization" not in blob.lower()
    assert "password" not in blob.lower()
    assert "api_key" not in blob.lower()


def test_console_upstream_summary_strips_v1_and_uses_aiand_key(tmp_path):
    fake = FakeAiandHttp(payload={"range": "30d", "requests": 3, "cost_usd": 1.2})
    client = _client(tmp_path, aiand_key=AIAND_KEY, aiand_http=fake)
    response = client.get("/v1/console/upstream/summary?range=30d", headers=AUTH)
    assert response.status_code == 200
    assert response.json()["requests"] == 3
    assert fake.calls[0]["url"] == "https://api.aiand.com/analytics/summary"
    assert fake.calls[0]["params"] == {"range": "30d"}
    assert fake.calls[0]["headers"]["Authorization"] == f"Bearer {AIAND_KEY}"
    assert "secret" not in json.dumps(fake.calls[0]["headers"])


def test_console_upstream_metrics_and_logs_passthrough(tmp_path):
    fake = FakeAiandHttp(payload={"data": [{"id": "r1", "ttft_ms": 10}]})
    client = _client(tmp_path, aiand_key=AIAND_KEY, aiand_http=fake)
    metrics = client.get("/v1/console/upstream/metrics?range=24h", headers=AUTH)
    assert metrics.status_code == 200
    assert fake.calls[0]["url"] == "https://api.aiand.com/analytics/metrics"
    logs = client.get(
        "/v1/console/upstream/logs?range=24h&after=ts1&after_id=id1&errors=true&limit=10&drop=1",
        headers=AUTH,
    )
    assert logs.status_code == 200
    assert logs.json()["data"][0]["ttft_ms"] == 10
    assert fake.calls[1]["url"] == "https://api.aiand.com/logs"
    assert fake.calls[1]["params"] == {
        "range": "24h",
        "after": "ts1",
        "after_id": "id1",
        "errors": "true",
        "limit": "10",
    }


def test_console_upstream_missing_key_is_502_overview_still_works(tmp_path):
    _write_jsonl(
        tmp_path / "requests.jsonl",
        [{"selected": FLASH, "phase": "plan", "cost_usd": 0.01}],
    )
    client = _client(tmp_path, aiand_key="")
    failed = client.get("/v1/console/upstream/summary", headers=AUTH)
    assert failed.status_code == 502
    assert failed.json() == {"error": "AIAND_API_KEY is not set"}
    overview = client.get("/v1/console/overview?range=all", headers=AUTH)
    assert overview.status_code == 200
    assert overview.json()["routed_requests"] == 1
    assert overview.json()["aiand_key_set"] is False


def test_console_upstream_failure_is_502_without_key(tmp_path):
    fake = FakeAiandHttp(exc=httpx.ConnectError("boom"))
    client = _client(tmp_path, aiand_key=AIAND_KEY, aiand_http=fake)
    response = client.get("/v1/console/upstream/metrics", headers=AUTH)
    assert response.status_code == 502
    assert response.json() == {"error": "AIand upstream request failed"}
    blob = json.dumps(response.json())
    assert AIAND_KEY not in blob


def test_console_upstream_error_body_scrubs_aiand_key(tmp_path):
    fake = FakeAiandHttp(status=500, payload={"error": {"message": f"bad {AIAND_KEY}"}})
    client = _client(tmp_path, aiand_key=AIAND_KEY, aiand_http=fake)
    response = client.get("/v1/console/upstream/logs", headers=AUTH)
    assert response.status_code == 502
    assert AIAND_KEY not in json.dumps(response.json())
    assert "[redacted]" in response.json()["error"]


def test_live_hop_then_overview_and_inferences(tmp_path):
    client = _client(tmp_path, aiand_key="")
    chat = client.post(
        "/v1/chat/completions",
        json={"model": "router/auto", "messages": [{"role": "user", "content": "ping"}]},
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert chat.status_code == 200
    overview = client.get("/v1/console/overview?range=all", headers=AUTH).json()
    assert overview["routed_requests"] == 1
    rows = client.get("/v1/console/inferences?range=all", headers=AUTH).json()["data"]
    assert len(rows) == 1
    assert rows[0]["selected"]
    assert rows[0]["ts"]
    assert rows[0]["ttft_ms"] is None
    assert rows[0]["llmaj_score"] is None
