from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest
from aiand_router.app import create_app
from aiand_router.flashlight import ROOT as PROJECT_ROOT
from aiand_router.router import SpendLog
from fastapi.testclient import TestClient

AUTH = {"Authorization": "Bearer secret"}
CHAT = {"model": "router/auto", "messages": [{"role": "user", "content": "ping"}]}
CASC_CFG = """
fallback_model: deepseek-ai/deepseek-v4-flash
premium_aa_floor: 58
max_regret: 8
phase_threshold: {{summarize: 0, plan: 0, edit: 0, tool: 0, debug: 0, discover: 0}}
trained_effort:
  low: {{threshold: 0.05, max_regret: 0.30}}
  medium: {{threshold: 0.10, max_regret: 0.20}}
  high: {{threshold: 0.20, max_regret: 0.15}}
  max: {{threshold: 0.60, max_regret: 0.03}}
cascade_lane:
  enabled: {enabled}
  cheap_model: deepseek-ai/deepseek-v4-flash
  strong_model: deepseek-ai/deepseek-v4-pro
  phases: [plan]
models:
  - id: deepseek-ai/deepseek-v4-flash
    enabled: true
    input_per_1m: 0.15
    cached_input_per_1m: 0.08
    output_per_1m: 0.25
    context_window: 1048576
    supports_tools: true
    supports_json: true
    supports_streaming: true
    max_output_tokens: 16384
    aa_index: 52
    aa_source: test
    measured_on: test
  - id: deepseek-ai/deepseek-v4-pro
    enabled: true
    input_per_1m: 1.00
    cached_input_per_1m: 0.25
    output_per_1m: 2.50
    context_window: 1048576
    supports_tools: true
    supports_json: true
    supports_streaming: true
    max_output_tokens: 16384
    aa_index: 53
    aa_source: test
    measured_on: test
    priors:
      plan: 0.65
"""


@pytest.fixture(autouse=True)
def _rules_path_for_gateway_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    # Pin rules (not conftest shadow): reason header + pioneer_score picks.
    monkeypatch.setenv("TRAINED_PATH", "off")


class FakeProvider:
    def __init__(self, script: list[dict] | None = None) -> None:
        self.calls: list[dict] = []
        self._script = list(script or [])

    async def complete(self, body: dict) -> dict:
        self.calls.append(dict(body))
        if self._script:
            return self._script.pop(0)
        return _ok()


def _ok(content: str = "ok", tool_calls: list | None = None) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
        message["content"] = None
    return {
        "status": 200,
        "json": {
            "id": "chatcmpl-fake",
            "choices": [{"message": message, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
    }


def _client(tmp_path, provider=None, spend_usd=0.0, budget=15.0):
    provider = provider or FakeProvider()
    spend = SpendLog(tmp_path / "spend.txt", budget)
    if spend_usd:
        spend.add(spend_usd)
    app = create_app(
        provider=provider,
        spend=spend,
        log_path=tmp_path / "requests.jsonl",
        router_key="secret",
        budget=budget,
        cache_dir=tmp_path / "cache",
        trained_path="off",
        learned_flag=tmp_path / "learned_wins.json",
    )
    return TestClient(app), provider


def _scorer(tmp_path: Path, p_success: dict[str, float], bin: str = "standard") -> Path:
    path = tmp_path / "scorer.json"
    path.write_text(
        json.dumps(
            {
                "calibrator": {"mode": "platt", "a": 1.0, "b": 0.0},
                "p_success": p_success,
                "complexity_bin": bin,
            }
        ),
        encoding="utf-8",
    )
    return path


def _cascade_config(tmp_path: Path, *, enabled: bool) -> Path:
    path = tmp_path / "models.yaml"
    path.write_text(CASC_CFG.format(enabled=str(enabled).lower()), encoding="utf-8")
    return path


def test_missing_router_key_returns_401_without_calling_provider(tmp_path):
    client, provider = _client(tmp_path)
    response = client.post("/v1/chat/completions", json=CHAT)
    assert response.status_code == 401
    assert provider.calls == []


def test_wrong_router_key_returns_401_without_calling_provider(tmp_path):
    client, provider = _client(tmp_path)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={"Authorization": "Bearer nope"},
    )
    assert response.status_code == 401
    assert provider.calls == []


def test_budget_exhausted_returns_429_without_calling_provider(tmp_path):
    client, provider = _client(tmp_path, spend_usd=15.0, budget=15.0)
    response = client.post("/v1/chat/completions", json=CHAT, headers=AUTH)
    assert response.status_code == 429
    assert provider.calls == []


def test_summarize_phase_forwards_flash_on_pioneer_score(tmp_path):
    client, provider = _client(tmp_path)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert response.status_code == 200
    assert provider.calls[0]["model"] == "deepseek-ai/deepseek-v4-flash"
    assert response.headers["x-router-model"] == "deepseek-ai/deepseek-v4-flash"
    assert response.headers["x-router-phase"] == "summarize"
    assert "score=" in response.headers["x-router-reason"]


def test_plan_phase_does_not_forward_k3(tmp_path):
    client, provider = _client(tmp_path)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "plan"},
    )
    assert response.status_code == 200
    assert provider.calls[0]["model"] != "moonshotai/kimi-k3"
    assert "kimi-k3" not in response.headers["x-router-model"]


def test_disabled_cascade_lane_keeps_rules_pick(tmp_path):
    provider = FakeProvider()
    app = create_app(
        provider=provider,
        spend=SpendLog(tmp_path / "spend.txt", 15.0),
        log_path=tmp_path / "requests.jsonl",
        router_key="secret",
        budget=15.0,
        cache_dir=tmp_path / "cache",
        config_path=_cascade_config(tmp_path, enabled=False),
        trained_path="off",
        scorer_path=_scorer(
            tmp_path, {"deepseek-ai/deepseek-v4-flash": 0.85, "deepseek-ai/deepseek-v4-pro": 0.90}
        ),
    )
    client = TestClient(app)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "plan"},
    )
    assert response.status_code == 200
    assert provider.calls[0]["model"] == "deepseek-ai/deepseek-v4-flash"
    assert response.headers["x-router-model"] == "deepseek-ai/deepseek-v4-flash"
    assert response.headers.get("x-router-path") is None


def test_enabled_cascade_lane_redirects_to_cheap_model_on_rules_path(tmp_path):
    provider = FakeProvider()
    app = create_app(
        provider=provider,
        spend=SpendLog(tmp_path / "spend.txt", 15.0),
        log_path=tmp_path / "requests.jsonl",
        router_key="secret",
        budget=15.0,
        cache_dir=tmp_path / "cache",
        config_path=_cascade_config(tmp_path, enabled=True),
        trained_path="off",
        scorer_path=_scorer(
            tmp_path, {"deepseek-ai/deepseek-v4-flash": 0.85, "deepseek-ai/deepseek-v4-pro": 0.90}
        ),
    )
    client = TestClient(app)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "plan"},
    )
    assert response.status_code == 200
    assert provider.calls[0]["model"] == "deepseek-ai/deepseek-v4-flash"
    assert response.headers["x-router-model"] == "deepseek-ai/deepseek-v4-flash"
    assert response.headers["x-router-path"] == "cascade"
    assert response.headers["x-router-rule"] == "cheap_redirect"


def test_enabled_cascade_lane_is_ignored_outside_off_path(tmp_path):
    provider = FakeProvider()
    app = create_app(
        provider=provider,
        spend=SpendLog(tmp_path / "spend.txt", 15.0),
        log_path=tmp_path / "requests.jsonl",
        router_key="secret",
        budget=15.0,
        cache_dir=tmp_path / "cache",
        config_path=_cascade_config(tmp_path, enabled=True),
        trained_path="shadow",
        scorer_path=_scorer(
            tmp_path, {"deepseek-ai/deepseek-v4-flash": 0.85, "deepseek-ai/deepseek-v4-pro": 0.90}
        ),
    )
    client = TestClient(app)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "plan"},
    )
    assert response.status_code == 200
    assert response.headers["x-router-path"] == "shadow"
    assert response.headers["x-router-trained-would"] == "deepseek-ai/deepseek-v4-flash"


def test_max_effort_may_forward_k3(tmp_path):
    client, provider = _client(tmp_path)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize", "x-routing-effort": "max"},
    )
    assert response.status_code == 200
    assert provider.calls[0]["model"] == "moonshotai/kimi-k3"
    assert response.headers["x-router-model"] == "moonshotai/kimi-k3"


def test_pinned_registry_id_is_forwarded_unchanged(tmp_path):
    client, provider = _client(tmp_path)
    response = client.post(
        "/v1/chat/completions",
        json={**CHAT, "model": "moonshotai/kimi-k2.7-code"},
        headers=AUTH,
    )
    assert response.status_code == 200
    assert provider.calls[0]["model"] == "moonshotai/kimi-k2.7-code"
    assert response.headers["x-router-model"] == "moonshotai/kimi-k2.7-code"
    assert "pinned" in response.headers["x-router-reason"]


def test_tools_present_skips_models_without_tool_support(tmp_path):
    yaml_path = tmp_path / "models.yaml"
    yaml_path.write_text(
        """
fallback_model: cheap/no-tools
phase_threshold: {summarize: 0, plan: 0, edit: 0, tool: 0, debug: 0, discover: 0}
premium_aa_floor: 99
models:
  - id: cheap/no-tools
    enabled: true
    input_per_1m: 0
    output_per_1m: 0
    context_window: 100000
    supports_tools: false
    aa_index: 50
    aa_source: test
    measured_on: test
  - id: dear/with-tools
    enabled: true
    input_per_1m: 1
    output_per_1m: 1
    context_window: 100000
    supports_tools: true
    aa_index: 50
    aa_source: test
    measured_on: test
""",
        encoding="utf-8",
    )
    provider = FakeProvider()
    app = create_app(
        provider=provider,
        spend=SpendLog(tmp_path / "spend.txt", 15),
        log_path=tmp_path / "requests.jsonl",
        router_key="secret",
        budget=15,
        config_path=yaml_path,
        cache_dir=tmp_path / "cache",
    )
    client = TestClient(app)
    body = {
        **CHAT,
        "tools": [{"type": "function", "function": {"name": "read", "parameters": {}}}],
    }
    response = client.post("/v1/chat/completions", json=body, headers=AUTH)
    assert response.status_code == 200
    assert provider.calls[0]["model"] == "dear/with-tools"


def test_invalid_tool_json_escalates_once_to_higher_quality_model(tmp_path):
    bad = _ok(
        tool_calls=[
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "read", "arguments": "{not-json"},
            }
        ]
    )
    provider = FakeProvider([bad, _ok("repaired")])
    client, _ = _client(tmp_path, provider=provider)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert response.status_code == 200
    assert len(provider.calls) == 2
    assert provider.calls[0]["model"] == "deepseek-ai/deepseek-v4-flash"
    assert provider.calls[1]["model"] == "deepseek-ai/deepseek-v4-pro"
    assert response.headers["x-router-escalated-from"] == "deepseek-ai/deepseek-v4-flash"
    assert response.headers["x-router-model"] == "deepseek-ai/deepseek-v4-pro"


async def _sse():
    yield b'data: {"choices":[{"delta":{"content":"hi"},"index":0}]}\n\n'
    yield b"data: [DONE]\n\n"


def test_stream_is_sse_passthrough_without_second_upstream_call(tmp_path):
    provider = FakeProvider([{"status": 200, "stream": _sse()}])
    client, _ = _client(tmp_path, provider=provider)
    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={**CHAT, "stream": True},
        headers={**AUTH, "x-agent-phase": "summarize"},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = b"".join(response.iter_bytes())
    assert b"hi" in body
    assert b"[DONE]" in body
    assert len(provider.calls) == 1
    assert provider.calls[0]["stream"] is True


def test_jsonl_records_phase_selected_reason_and_cost(tmp_path):
    client, _ = _client(tmp_path)
    client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    rows = (tmp_path / "requests.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 1
    row = json.loads(rows[0])
    assert row["phase"] == "summarize"
    assert row["selected"] == "deepseek-ai/deepseek-v4-flash"
    assert "deepseek-ai/deepseek-v4-flash" in row["reason"]
    assert "cost_usd" in row
    assert row["cost_usd"] == 0.000002


def test_models_list_includes_router_auto(tmp_path):
    client, _ = _client(tmp_path)
    response = client.get("/v1/models", headers=AUTH)
    assert response.status_code == 200
    ids = [m["id"] for m in response.json()["data"]]
    assert "router/auto" in ids
    assert "qwen/qwen3.6-27b" in ids


def test_second_identical_call_is_served_from_cache(tmp_path):
    client, provider = _client(tmp_path)
    body = {**CHAT, "model": "moonshotai/kimi-k2.7-code"}
    first = client.post("/v1/chat/completions", json=body, headers=AUTH)
    spend_after_first = float((tmp_path / "spend.txt").read_text(encoding="utf-8").strip())
    second = client.post("/v1/chat/completions", json=body, headers=AUTH)
    spend_after_second = float((tmp_path / "spend.txt").read_text(encoding="utf-8").strip())
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["choices"][0]["message"]["content"] == "ok"
    assert len(provider.calls) == 1
    assert spend_after_first > 0
    assert spend_after_second == spend_after_first
    rows = [
        json.loads(line)
        for line in (tmp_path / "requests.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert rows[0].get("cache_hit") is not True
    assert rows[1]["cache_hit"] is True


def test_rules_hop_logs_baseline_and_savings(tmp_path):
    client, _ = _client(tmp_path)
    response = client.post("/v1/chat/completions", json=CHAT, headers={**AUTH, "x-agent-phase": "edit"})
    assert response.status_code == 200
    row = json.loads((tmp_path / "requests.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert row.get("baseline_model_id")
    assert "savings_usd" in row
    assert row["savings_usd"] >= 0
    assert row["cost_usd"] > 0


def test_request_cache_key_includes_api_key_fingerprint():
    from aiand_router.cache import request_cache_key

    body = {"messages": [{"role": "user", "content": "hi"}], "temperature": 0}
    a = request_cache_key(body, "m", "aaa")
    b = request_cache_key(body, "m", "bbb")
    c = request_cache_key(body, "m", "aaa")
    assert a != b
    assert a == c


def test_cache_misses_when_prompt_changes(tmp_path):
    client, provider = _client(tmp_path)
    headers = {**AUTH, "x-agent-phase": "summarize"}
    client.post("/v1/chat/completions", json=CHAT, headers=headers)
    other = {**CHAT, "messages": [{"role": "user", "content": "pong"}]}
    client.post("/v1/chat/completions", json=other, headers=headers)
    assert len(provider.calls) == 2


def test_cache_misses_when_a_key_field_changes(tmp_path):
    client, provider = _client(tmp_path)
    base = {
        **CHAT,
        "model": "moonshotai/kimi-k2.7-code",
        "temperature": 0,
        "max_tokens": 64,
        "messages": [
            {"role": "system", "content": "be brief"},
            {"role": "user", "content": "ping"},
        ],
        "tools": [{"type": "function", "function": {"name": "read", "parameters": {}}}],
    }
    client.post("/v1/chat/completions", json=base, headers=AUTH)
    variants = [
        {**base, "temperature": 1},
        {**base, "max_tokens": 128},
        {**base, "messages": [{"role": "system", "content": "be loud"}, {"role": "user", "content": "ping"}]},
        {**base, "tools": [{"type": "function", "function": {"name": "write", "parameters": {}}}]},
    ]
    for variant in variants:
        client.post("/v1/chat/completions", json=variant, headers=AUTH)
    assert len(provider.calls) == 1 + len(variants)


def test_failed_test_outcome_makes_debug_pick_a_stronger_model(tmp_path):
    client, provider = _client(tmp_path)
    edit = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "edit"},
    )
    outcome = client.post(
        "/v1/router/outcome",
        json={"tests_passed": False, "patch_applied": True, "failure_text": "AssertionError"},
        headers=AUTH,
    )
    debug = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "debug"},
    )
    assert outcome.status_code == 200
    # Coding-agent priors: pioneer_score already prefers Pro on edit.
    # debug_fail_threshold (53) still bars Flash (AA 52) after a failed test.
    assert edit.headers["x-router-model"] == "deepseek-ai/deepseek-v4-pro"
    assert debug.headers["x-router-model"] == "deepseek-ai/deepseek-v4-pro"
    assert debug.headers["x-router-model"] != "deepseek-ai/deepseek-v4-flash"
    assert provider.calls[0]["model"] == "deepseek-ai/deepseek-v4-pro"
    # Same prompt + Pro on both turns → debug is a cache hit, not a second upstream.


def test_replay_page_shows_phase_winner_reason_cost_and_hides_secrets(tmp_path):
    client, _ = _client(tmp_path)
    client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    client.post(
        "/v1/router/outcome",
        json={"tests_passed": False, "patch_applied": False, "failure_text": "boom"},
        headers=AUTH,
    )
    page = client.get("/replay")
    events = client.get("/replay/events")
    assert page.status_code == 200
    assert "text/html" in page.headers["content-type"]
    html = page.text
    assert "Ask the router" in html
    assert "secret" not in html.lower()
    assert "sk-" not in html
    assert "AIAND_API_KEY" not in html
    body = events.json()
    assert body[0]["phase"] == "summarize"
    assert body[0]["selected"] == "deepseek-ai/deepseek-v4-flash"
    assert "reason" in body[0]
    assert "cost_usd" in body[0]
    assert body[1]["tests_passed"] is False
    blob = json.dumps(body)
    assert "secret" not in blob.lower()
    assert "Bearer" not in blob


def test_flashlight_walks_phases_and_uses_stronger_model_after_test_fail(tmp_path):
    client, _ = _client(tmp_path)
    for phase in ("discover", "plan", "edit"):
        client.post("/v1/chat/completions", json=CHAT, headers={**AUTH, "x-agent-phase": phase})
    fail = client.post(
        "/v1/router/outcome",
        json={"tests_passed": False, "patch_applied": True, "failure_text": "AssertionError"},
        headers=AUTH,
    )
    debug = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "debug"},
    )
    ok = client.post(
        "/v1/router/outcome",
        json={"tests_passed": True, "patch_applied": True, "failure_text": ""},
        headers=AUTH,
    )
    summarize = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert fail.status_code == 200
    assert ok.status_code == 200
    assert debug.status_code == 200
    assert summarize.status_code == 200
    rows = [
        json.loads(line)
        for line in (tmp_path / "requests.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    phases = [r.get("phase") for r in rows]
    assert phases[:3] == ["discover", "plan", "edit"]
    assert "test" in phases
    assert "debug" in phases
    assert "summarize" in phases
    by_phase = {r["phase"]: r for r in rows if r.get("selected")}
    assert by_phase["edit"]["selected"] == "deepseek-ai/deepseek-v4-pro"
    assert by_phase["debug"]["selected"] == "deepseek-ai/deepseek-v4-pro"
    assert by_phase["debug"]["selected"] != "deepseek-ai/deepseek-v4-flash"
    assert by_phase["summarize"]["selected"] == "deepseek-ai/deepseek-v4-flash"
    assert any(r.get("tests_passed") is False for r in rows)
    assert any(r.get("tests_passed") is True for r in rows)


def test_eval_runs_three_baselines_on_five_tasks_and_rereads_log(tmp_path):
    from aiand_router.eval import load_tasks, report_from_log, run_eval

    client, provider = _client(tmp_path)
    spec = load_tasks(PROJECT_ROOT / "config" / "tasks.yaml")
    first = run_eval(client, "secret", spec, log_path=tmp_path / "requests.jsonl")
    calls_after_first = len(provider.calls)
    # 5 tasks × 3 baselines, but rules pick Pro on plan/edit/debug (same as
    # premium) so those three adaptive turns cache-hit → 12 unique upstream calls.
    assert calls_after_first == 12
    second = run_eval(client, "secret", spec, log_path=tmp_path / "requests.jsonl")
    assert len(provider.calls) == calls_after_first
    report = report_from_log(tmp_path / "requests.jsonl")
    assert set(report["baselines"]) == {"premium", "kimi", "adaptive"}
    for name in ("premium", "kimi"):
        row = report["baselines"][name]
        assert row["tasks"] == 5
        assert "cost_usd" in row
        assert "latency_ms" in row
        assert "models" in row
        assert "resolved" in row
    adaptive = report["baselines"]["adaptive"]
    assert adaptive["tasks"] == 2  # discover + summarize; rest cache-hit Pro
    assert "cost_usd" in adaptive
    assert "latency_ms" in adaptive
    assert "resolved" in adaptive
    assert report["baselines"]["premium"]["models"] == ["deepseek-ai/deepseek-v4-pro"]
    assert report["baselines"]["kimi"]["models"] == ["moonshotai/kimi-k2.7-code"]
    assert adaptive["models"] == ["deepseek-ai/deepseek-v4-flash"]
    assert "savings_pct" not in report
    assert first["stubbed"] == ["qwen-only", "flash-only", "glm-only", "random", "oracle"]
    assert first["cache_hits"] == 3
    assert second["cache_hits"] == 15
    assert "not_aiand" in report["quality_note"]


def test_eval_report_does_not_count_empty_or_escalated_as_resolved(tmp_path):
    from aiand_router.eval import report_from_log

    empty = _ok("")
    empty["json"]["choices"][0]["message"]["content"] = ""
    empty["json"]["usage"] = {"prompt_tokens": 10, "completion_tokens": 0}
    provider = FakeProvider([empty, _ok("repaired"), _ok("fine")])
    client, _ = _client(tmp_path, provider=provider)
    client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    client.post(
        "/v1/chat/completions",
        json={**CHAT, "model": "deepseek-ai/deepseek-v4-pro"},
        headers=AUTH,
    )
    report = report_from_log(tmp_path / "requests.jsonl")
    assert report["baselines"]["adaptive"]["tasks"] == 1
    assert report["baselines"]["adaptive"]["resolved"] == 0
    assert report["baselines"]["premium"]["tasks"] == 1
    assert report["baselines"]["premium"]["resolved"] == 1


def test_learned_router_stays_dark_after_comparison(tmp_path):
    from aiand_router.eval import load_tasks, run_eval

    client, _ = _client(tmp_path)
    spec = load_tasks(PROJECT_ROOT / "config" / "tasks.yaml")
    run_eval(client, "secret", spec, log_path=tmp_path / "requests.jsonl")
    flag = tmp_path / "learned_wins.json"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "aiand_router.learn",
            "--cache",
            str(tmp_path / "cache"),
            "--flag",
            str(flag),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "src")},
    )
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["winner"] == "rules"
    assert flag.exists() is False or json.loads(flag.read_text())["winner"] != "learned"
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert response.headers["x-router-model"] == "deepseek-ai/deepseek-v4-flash"
    assert "learned" not in response.headers["x-router-reason"].lower()


def test_learned_router_is_used_only_after_flag_says_it_won(tmp_path):
    flag = tmp_path / "learned_wins.json"
    flag.write_text(json.dumps({"winner": "learned"}), encoding="utf-8")
    provider = FakeProvider()
    app = create_app(
        provider=provider,
        spend=SpendLog(tmp_path / "spend.txt", 15),
        log_path=tmp_path / "requests.jsonl",
        router_key="secret",
        budget=15,
        cache_dir=tmp_path / "cache",
        learned_flag=flag,
        trained_path="off",
    )
    client = TestClient(app)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert response.status_code == 200
    assert provider.calls[0]["model"] != "moonshotai/kimi-k3"
    assert "learned" in response.headers["x-router-reason"].lower()


def test_learned_with_tools_skips_models_without_tool_support(tmp_path):
    yaml_path = tmp_path / "models.yaml"
    yaml_path.write_text(
        """
fallback_model: cheap/no-tools
phase_threshold: {summarize: 0, plan: 0, edit: 0, tool: 0, debug: 0, discover: 0}
premium_aa_floor: 99
models:
  - id: cheap/no-tools
    enabled: true
    input_per_1m: 0
    output_per_1m: 0
    context_window: 100000
    supports_tools: false
    aa_index: 90
    aa_source: test
    measured_on: test
  - id: dear/with-tools
    enabled: true
    input_per_1m: 1
    output_per_1m: 1
    context_window: 100000
    supports_tools: true
    aa_index: 50
    aa_source: test
    measured_on: test
""",
        encoding="utf-8",
    )
    flag = tmp_path / "learned_wins.json"
    flag.write_text(json.dumps({"winner": "learned"}), encoding="utf-8")
    provider = FakeProvider()
    app = create_app(
        provider=provider,
        spend=SpendLog(tmp_path / "spend.txt", 15),
        log_path=tmp_path / "requests.jsonl",
        router_key="secret",
        budget=15,
        config_path=yaml_path,
        cache_dir=tmp_path / "cache",
        learned_flag=flag,
        trained_path="off",
    )
    client = TestClient(app)
    body = {
        **CHAT,
        "tools": [{"type": "function", "function": {"name": "read", "parameters": {}}}],
    }
    response = client.post("/v1/chat/completions", json=body, headers=AUTH)
    assert response.status_code == 200
    assert provider.calls[0]["model"] == "dear/with-tools"
    assert "learned" in response.headers["x-router-reason"].lower()


def test_json_mode_skips_models_without_json_support(tmp_path):
    yaml_path = tmp_path / "models.yaml"
    yaml_path.write_text(
        """
fallback_model: cheap/no-json
phase_threshold: {summarize: 0, plan: 0, edit: 0, tool: 0, debug: 0, discover: 0}
premium_aa_floor: 99
models:
  - id: cheap/no-json
    enabled: true
    input_per_1m: 0
    output_per_1m: 0
    context_window: 100000
    supports_tools: true
    supports_json: false
    aa_index: 90
    aa_source: test
    measured_on: test
  - id: dear/with-json
    enabled: true
    input_per_1m: 1
    output_per_1m: 1
    context_window: 100000
    supports_tools: true
    supports_json: true
    aa_index: 50
    aa_source: test
    measured_on: test
""",
        encoding="utf-8",
    )
    provider = FakeProvider()
    app = create_app(
        provider=provider,
        spend=SpendLog(tmp_path / "spend.txt", 15),
        log_path=tmp_path / "requests.jsonl",
        router_key="secret",
        budget=15,
        config_path=yaml_path,
        cache_dir=tmp_path / "cache",
    )
    client = TestClient(app)
    body = {**CHAT, "response_format": {"type": "json_object"}}
    response = client.post("/v1/chat/completions", json=body, headers=AUTH)
    assert response.status_code == 200
    assert provider.calls[0]["model"] == "dear/with-json"


def test_invalid_json_content_escalates_once(tmp_path):
    bad = _ok("{not-json")
    provider = FakeProvider([bad, _ok('{"ok": true}')])
    client, _ = _client(tmp_path, provider=provider)
    response = client.post(
        "/v1/chat/completions",
        json={**CHAT, "response_format": {"type": "json_object"}},
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert response.status_code == 200
    assert len(provider.calls) == 2
    assert provider.calls[0]["model"] == "deepseek-ai/deepseek-v4-flash"
    assert provider.calls[1]["model"] == "deepseek-ai/deepseek-v4-pro"
    assert response.headers["x-router-escalated-from"] == "deepseek-ai/deepseek-v4-flash"
    rows = [
        json.loads(line)
        for line in (tmp_path / "requests.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert rows[-1].get("json_valid") is True


def test_max_tokens_above_cap_rejected_without_upstream(tmp_path):
    yaml_path = tmp_path / "models.yaml"
    yaml_path.write_text(
        (PROJECT_ROOT / "config" / "models.yaml").read_text(encoding="utf-8")
        + "\nmax_tokens_limit: 128\n",
        encoding="utf-8",
    )
    provider = FakeProvider()
    app = create_app(
        provider=provider,
        spend=SpendLog(tmp_path / "spend.txt", 15),
        log_path=tmp_path / "requests.jsonl",
        router_key="secret",
        budget=15,
        config_path=yaml_path,
        cache_dir=tmp_path / "cache",
    )
    client = TestClient(app)
    response = client.post(
        "/v1/chat/completions",
        json={**CHAT, "max_tokens": 9999},
        headers=AUTH,
    )
    assert response.status_code == 400
    assert provider.calls == []


def test_replay_redacts_configured_keys(tmp_path):
    log = tmp_path / "requests.jsonl"
    log.write_text(
        json.dumps(
            {
                "phase": "summarize",
                "selected": "qwen/qwen3.6-27b",
                "password": "hunter2",
                "tokens_in": 10,
                "tokens_out": 5,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    yaml_path = tmp_path / "models.yaml"
    yaml_path.write_text(
        (PROJECT_ROOT / "config" / "models.yaml").read_text(encoding="utf-8")
        + "\nredact_keys: [password, authorization, token, secret, key]\n",
        encoding="utf-8",
    )
    app = create_app(
        provider=FakeProvider(),
        spend=SpendLog(tmp_path / "spend.txt", 15),
        log_path=log,
        router_key="secret",
        budget=15,
        config_path=yaml_path,
        cache_dir=tmp_path / "cache",
    )
    events = TestClient(app).get("/replay/events")
    assert events.status_code == 200
    blob = json.dumps(events.json())
    assert "hunter2" not in blob
    assert "password" not in blob
    assert events.json()[0]["selected"] == "qwen/qwen3.6-27b"
    assert events.json()[0]["tokens_in"] == 10
    assert events.json()[0]["tokens_out"] == 5


def test_health_never_returns_provider_key(tmp_path):
    client, _ = _client(tmp_path)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert "aiand_key_set" in body
    blob = json.dumps(body).lower()
    assert "sk-" not in blob
    assert "aiand_api_key" not in blob


def test_max_output_drops_model_when_request_exceeds_it(tmp_path):
    yaml_path = tmp_path / "models.yaml"
    yaml_path.write_text(
        """
fallback_model: dear/big-out
phase_threshold: {summarize: 0, plan: 0, edit: 0, tool: 0, debug: 0, discover: 0}
premium_aa_floor: 99
models:
  - id: cheap/small-out
    enabled: true
    input_per_1m: 0
    output_per_1m: 0
    context_window: 100000
    max_output_tokens: 16
    supports_tools: true
    supports_json: true
    supports_streaming: true
    aa_index: 50
    aa_source: test
    measured_on: test
  - id: dear/big-out
    enabled: true
    input_per_1m: 1
    output_per_1m: 1
    context_window: 100000
    max_output_tokens: 128
    supports_tools: true
    supports_json: true
    supports_streaming: true
    aa_index: 50
    aa_source: test
    measured_on: test
""",
        encoding="utf-8",
    )
    provider = FakeProvider()
    app = create_app(
        provider=provider,
        spend=SpendLog(tmp_path / "spend.txt", 15),
        log_path=tmp_path / "requests.jsonl",
        router_key="secret",
        budget=15,
        config_path=yaml_path,
        cache_dir=tmp_path / "cache",
    )
    client = TestClient(app)
    response = client.post(
        "/v1/chat/completions",
        json={**CHAT, "max_tokens": 64},
        headers=AUTH,
    )
    assert response.status_code == 200
    assert provider.calls[0]["model"] == "dear/big-out"


def test_stream_skips_models_without_streaming(tmp_path):
    yaml_path = tmp_path / "models.yaml"
    yaml_path.write_text(
        """
fallback_model: dear/stream
phase_threshold: {summarize: 0, plan: 0, edit: 0, tool: 0, debug: 0, discover: 0}
premium_aa_floor: 99
models:
  - id: cheap/no-stream
    enabled: true
    input_per_1m: 0
    output_per_1m: 0
    context_window: 100000
    supports_tools: true
    supports_json: true
    supports_streaming: false
    aa_index: 90
    aa_source: test
    measured_on: test
  - id: dear/stream
    enabled: true
    input_per_1m: 1
    output_per_1m: 1
    context_window: 100000
    supports_tools: true
    supports_json: true
    supports_streaming: true
    aa_index: 50
    aa_source: test
    measured_on: test
""",
        encoding="utf-8",
    )

    async def sse():
        yield b'data: {"choices":[{"delta":{"content":"hi"},"index":0}]}\n\n'
        yield b"data: [DONE]\n\n"

    provider = FakeProvider([{"status": 200, "stream": sse()}])
    app = create_app(
        provider=provider,
        spend=SpendLog(tmp_path / "spend.txt", 15),
        log_path=tmp_path / "requests.jsonl",
        router_key="secret",
        budget=15,
        config_path=yaml_path,
        cache_dir=tmp_path / "cache",
    )
    client = TestClient(app)
    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={**CHAT, "stream": True},
        headers=AUTH,
    ) as response:
        assert response.status_code == 200
        b"".join(response.iter_bytes())
    assert provider.calls[0]["model"] == "dear/stream"


def test_models_list_includes_all_nine_and_motif_enabled(tmp_path):
    client, _ = _client(tmp_path)
    response = client.get("/v1/models", headers=AUTH)
    ids = [m["id"] for m in response.json()["data"]]
    assert "router/auto" in ids
    for mid in (
        "qwen/qwen3.6-27b",
        "deepseek-ai/deepseek-v4-flash",
        "google/gemma-4-31b-it",
        "openai/gpt-oss-120b",
        "moonshotai/kimi-k2.7-code",
        "deepseek-ai/deepseek-v4-pro",
        "zai-org/glm-5.2",
        "moonshotai/kimi-k3",
        "motif-technologies/motif-3",
    ):
        assert mid in ids
    motif = next(m for m in response.json()["data"] if m["id"] == "motif-technologies/motif-3")
    assert motif.get("enabled") is True


def test_models_list_includes_registry_prices(tmp_path):
    client, _ = _client(tmp_path)
    payload = client.get("/v1/models", headers=AUTH).json()["data"]
    auto = next(m for m in payload if m["id"] == "router/auto")
    assert "input_per_1m" not in auto
    assert auto["owned_by"] == "aiand-router"
    flash = next(m for m in payload if m["id"] == "deepseek-ai/deepseek-v4-flash")
    assert flash["display_name"] == "DeepSeek V4 Flash"
    assert flash["input_per_1m"] == 0.15
    assert flash["output_per_1m"] == 0.25


def test_cached_input_price_feeds_cost(tmp_path):
    yaml_path = tmp_path / "models.yaml"
    yaml_path.write_text(
        """
fallback_model: priced/cached
phase_threshold: {summarize: 0, plan: 0, edit: 0, tool: 0, debug: 0, discover: 0}
premium_aa_floor: 99
models:
  - id: priced/cached
    enabled: true
    input_per_1m: 100
    cached_input_per_1m: 0
    output_per_1m: 0
    context_window: 100000
    supports_tools: true
    supports_json: true
    aa_index: 50
    aa_source: test
    measured_on: test
""",
        encoding="utf-8",
    )
    provider = FakeProvider()
    app = create_app(
        provider=provider,
        spend=SpendLog(tmp_path / "spend.txt", 15),
        log_path=tmp_path / "requests.jsonl",
        router_key="secret",
        budget=15,
        config_path=yaml_path,
        cache_dir=tmp_path / "cache",
    )
    client = TestClient(app)
    response = client.post(
        "/v1/chat/completions",
        json={**CHAT, "model": "priced/cached"},
        headers=AUTH,
    )
    assert response.status_code == 200
    row = json.loads((tmp_path / "requests.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert row["cost_usd"] == 0.0


def test_security_review_phase_is_first_class(tmp_path):
    client, _ = _client(tmp_path)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "security_review"},
    )
    assert response.status_code == 200
    assert response.headers["x-router-phase"] == "security_review"
    assert "score=" in response.headers["x-router-reason"]


def test_max_regret_picks_stronger_when_cheap_is_far_behind(tmp_path):
    yaml_path = tmp_path / "models.yaml"
    yaml_path.write_text(
        """
fallback_model: cheap/weak
max_regret: 5
premium_aa_floor: 99
phase_threshold: {plan: 50, planning: 50, summarize: 0, edit: 0, tool: 0, debug: 0, discover: 0}
models:
  - id: cheap/weak
    enabled: true
    input_per_1m: 0
    output_per_1m: 0
    context_window: 100000
    supports_tools: true
    supports_json: true
    aa_index: 51
    aa_source: test
    measured_on: test
  - id: dear/strong
    enabled: true
    input_per_1m: 1
    output_per_1m: 1
    context_window: 100000
    supports_tools: true
    supports_json: true
    aa_index: 60
    aa_source: test
    measured_on: test
""",
        encoding="utf-8",
    )
    provider = FakeProvider()
    app = create_app(
        provider=provider,
        spend=SpendLog(tmp_path / "spend.txt", 15),
        log_path=tmp_path / "requests.jsonl",
        router_key="secret",
        budget=15,
        config_path=yaml_path,
        cache_dir=tmp_path / "cache",
    )
    client = TestClient(app)
    bumped = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "plan"},
    )
    cheap = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "plan", "x-routing-effort": "low"},
    )
    assert bumped.status_code == 200
    assert provider.calls[0]["model"] == "dear/strong"
    assert "score=" in bumped.headers["x-router-reason"]
    assert cheap.status_code == 200
    assert provider.calls[1]["model"] == "cheap/weak"


def test_pioneer_score_beats_a_cheaper_weaker_model(tmp_path):
    yaml_path = tmp_path / "models.yaml"
    yaml_path.write_text(
        """
fallback_model: cheap/weak
max_regret: 0
premium_aa_floor: 99
phase_threshold: {summarize: 0, plan: 0, edit: 0, tool: 0, debug: 0, discover: 0}
models:
  - id: cheap/weak
    enabled: true
    input_per_1m: 0
    output_per_1m: 0
    latency_ms: 4000
    context_window: 100000
    supports_tools: true
    supports_json: true
    aa_index: 40
    aa_source: test
    measured_on: test
  - id: dear/strong
    enabled: true
    input_per_1m: 1
    output_per_1m: 1
    latency_ms: 200
    context_window: 100000
    supports_tools: true
    supports_json: true
    aa_index: 55
    aa_source: test
    measured_on: test
""",
        encoding="utf-8",
    )
    provider = FakeProvider()
    app = create_app(
        provider=provider,
        spend=SpendLog(tmp_path / "spend.txt", 15),
        log_path=tmp_path / "requests.jsonl",
        router_key="secret",
        budget=15,
        config_path=yaml_path,
        cache_dir=tmp_path / "cache",
    )
    client = TestClient(app)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert response.status_code == 200
    assert provider.calls[0]["model"] == "dear/strong"
    assert "score=" in response.headers["x-router-reason"]


def test_latency_limit_drops_slow_model(tmp_path):
    yaml_path = tmp_path / "models.yaml"
    yaml_path.write_text(
        """
fallback_model: fast/ok
latency_limit_ms: 1000
premium_aa_floor: 99
phase_threshold: {summarize: 0, plan: 0, edit: 0, tool: 0, debug: 0, discover: 0}
models:
  - id: slow/smart
    enabled: true
    input_per_1m: 0
    output_per_1m: 0
    latency_ms: 5000
    context_window: 100000
    supports_tools: true
    supports_json: true
    aa_index: 90
    aa_source: test
    measured_on: test
  - id: fast/ok
    enabled: true
    input_per_1m: 1
    output_per_1m: 1
    latency_ms: 200
    context_window: 100000
    supports_tools: true
    supports_json: true
    aa_index: 40
    aa_source: test
    measured_on: test
""",
        encoding="utf-8",
    )
    provider = FakeProvider()
    app = create_app(
        provider=provider,
        spend=SpendLog(tmp_path / "spend.txt", 15),
        log_path=tmp_path / "requests.jsonl",
        router_key="secret",
        budget=15,
        config_path=yaml_path,
        cache_dir=tmp_path / "cache",
    )
    client = TestClient(app)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert response.status_code == 200
    assert provider.calls[0]["model"] == "fast/ok"
    headered = client.post(
        "/v1/chat/completions",
        json={**CHAT, "messages": [{"role": "user", "content": "pong"}]},
        headers={**AUTH, "x-agent-phase": "summarize", "x-latency-limit": "8000"},
    )
    assert headered.status_code == 200
    assert provider.calls[1]["model"] == "slow/smart"


def test_summarize_picks_highest_pioneer_score(tmp_path):
    client, provider = _client(tmp_path)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert response.status_code == 200
    assert provider.calls[0]["model"] == "deepseek-ai/deepseek-v4-flash"
    assert "score=" in response.headers["x-router-reason"]


def test_draft_phase_planning_is_first_class(tmp_path):
    client, provider = _client(tmp_path)
    response = client.post(
        "/v1/chat/completions",
        json={"model": "router/auto", "messages": [{"role": "user", "content": "summarize what we did"}]},
        headers={**AUTH, "x-agent-phase": "planning"},
    )
    assert response.status_code == 200
    assert response.headers["x-router-phase"] == "planning"
    assert provider.calls[0]["model"] != "moonshotai/kimi-k3"
    assert "score=" in response.headers["x-router-reason"]


def test_unknown_phase_header_is_ignored_not_error(tmp_path):
    client, _ = _client(tmp_path)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "spaceship"},
    )
    assert response.status_code == 200
    assert response.headers["x-router-phase"] in {
        "plan",
        "edit",
        "discover",
        "tool",
        "debug",
        "summarize",
        "planning",
        "code_edit",
        "repository_discovery",
    }


def test_auto_response_body_keeps_virtual_model_id(tmp_path):
    client, _ = _client(tmp_path)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert response.status_code == 200
    assert response.json()["model"] == "router/auto"
    assert response.headers["x-router-model"] == "deepseek-ai/deepseek-v4-flash"


def test_pinned_response_body_keeps_pinned_id(tmp_path):
    client, _ = _client(tmp_path)
    response = client.post(
        "/v1/chat/completions",
        json={**CHAT, "model": "moonshotai/kimi-k2.7-code"},
        headers=AUTH,
    )
    assert response.status_code == 200
    assert response.json()["model"] == "moonshotai/kimi-k2.7-code"
    assert response.headers["x-router-model"] == "moonshotai/kimi-k2.7-code"


def test_smoke_refuses_unless_opted_in(monkeypatch):
    monkeypatch.delenv("AIAND_SMOKE", raising=False)
    from aiand_router.smoke import main

    assert main([]) == 2


def test_timeout_escalates_once_to_a_stronger_model(tmp_path):
    class TimeoutThenOk(FakeProvider):
        async def complete(self, body: dict) -> dict:
            self.calls.append(dict(body))
            if len(self.calls) == 1:
                raise httpx.TimeoutException("upstream timeout")
            return _ok("recovered")

    provider = TimeoutThenOk()
    client, _ = _client(tmp_path, provider=provider)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert response.status_code == 200
    assert len(provider.calls) == 2
    assert provider.calls[0]["model"] == "deepseek-ai/deepseek-v4-flash"
    assert provider.calls[1]["model"] == "deepseek-ai/deepseek-v4-pro"
    assert response.headers["x-router-escalated-from"] == "deepseek-ai/deepseek-v4-flash"


