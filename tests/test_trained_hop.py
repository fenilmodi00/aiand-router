from __future__ import annotations

import json
from pathlib import Path

from aiand_router.app import create_app
from aiand_router.router import SpendLog
from fastapi.testclient import TestClient

from tests.test_gateway import AUTH, CHAT, FakeProvider

FLASH = "deepseek-ai/deepseek-v4-flash"
PRO = "deepseek-ai/deepseek-v4-pro"


def _write_scorer(tmp_path: Path, p_success: dict[str, float], *, bin: str = "standard") -> Path:
    path = tmp_path / "scorer.json"
    path.write_text(
        json.dumps(
            {
                "not_spec_floors": True,
                "complexity_bin": bin,
                "p_success": p_success,
            }
        ),
        encoding="utf-8",
    )
    return path


def _client(tmp_path: Path, *, trained_path: str | None = None, scorer_path: Path | None = None, **kwargs):
    provider = kwargs.pop("provider", None) or FakeProvider()
    cache_dir = kwargs.pop("cache_dir", tmp_path / "cache")
    spend = SpendLog(tmp_path / "spend.txt", 15)
    app = create_app(
        provider=provider,
        spend=spend,
        log_path=tmp_path / "requests.jsonl",
        router_key="secret",
        budget=15,
        cache_dir=cache_dir,
        trained_path=trained_path,
        scorer_path=scorer_path,
        **kwargs,
    )
    return TestClient(app), provider


def _tiny_catalog(tmp_path: Path) -> Path:
    path = tmp_path / "models.yaml"
    path.write_text(
        """
fallback_model: cheap/ok
phase_threshold: {summarize: 0, plan: 0, edit: 0, tool: 0, debug: 0, discover: 0}
premium_aa_floor: 99
models:
  - id: cheap/ok
    enabled: true
    input_per_1m: 0.1
    output_per_1m: 0.1
    context_window: 100000
    supports_tools: true
    aa_index: 50
    aa_source: test
    measured_on: test
  - id: mid/ok
    enabled: true
    input_per_1m: 1
    output_per_1m: 1
    context_window: 100000
    supports_tools: true
    aa_index: 50
    aa_source: test
    measured_on: test
  - id: dear/ok
    enabled: true
    input_per_1m: 10
    output_per_1m: 10
    context_window: 100000
    supports_tools: true
    aa_index: 50
    aa_source: test
    measured_on: test
  - id: cheap/no-tools
    enabled: true
    input_per_1m: 0.05
    output_per_1m: 0.05
    context_window: 100000
    supports_tools: false
    aa_index: 50
    aa_source: test
    measured_on: test
""",
        encoding="utf-8",
    )
    return path


def _last_row(tmp_path: Path) -> dict:
    lines = (tmp_path / "requests.jsonl").read_text(encoding="utf-8").strip().splitlines()
    return json.loads(lines[-1])


def test_shadow_serves_rules_pick_and_records_trained_would(tmp_path):
    scorer = _write_scorer(tmp_path, {PRO: 0.95, FLASH: 0.40})
    client, provider = _client(tmp_path, scorer_path=scorer)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert response.status_code == 200
    assert provider.calls[0]["model"] == FLASH
    assert response.headers["x-router-model"] == FLASH
    assert response.headers["x-router-path"] == "shadow"
    assert response.headers["x-router-trained-would"] == PRO
    row = _last_row(tmp_path)
    assert row["path"] == "shadow"
    assert row["selected"] == FLASH
    assert row["trained_selected"] == PRO


def test_invalid_trained_path_is_shadow(tmp_path):
    scorer = _write_scorer(tmp_path, {PRO: 0.95, FLASH: 0.40})
    client, provider = _client(tmp_path, trained_path="nope", scorer_path=scorer)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert response.status_code == 200
    assert response.headers["x-router-path"] == "shadow"
    assert provider.calls[0]["model"] == FLASH
    assert response.headers["x-router-trained-would"] == PRO


def test_off_keeps_rules_reason_header(tmp_path):
    scorer = _write_scorer(tmp_path, {PRO: 0.95, FLASH: 0.40})
    client, _ = _client(tmp_path, trained_path="off", scorer_path=scorer)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert response.status_code == 200
    assert response.headers["x-router-model"] == FLASH
    assert "score=" in response.headers["x-router-reason"]
    assert "x-router-path" not in response.headers
    assert "x-router-trained-would" not in response.headers


def test_pinned_id_bypasses_auto_select_on_shadow(tmp_path):
    scorer = _write_scorer(tmp_path, {PRO: 0.95, FLASH: 0.40})
    client, provider = _client(tmp_path, scorer_path=scorer)
    response = client.post(
        "/v1/chat/completions",
        json={**CHAT, "model": "moonshotai/kimi-k2.7-code"},
        headers=AUTH,
    )
    assert response.status_code == 200
    assert provider.calls[0]["model"] == "moonshotai/kimi-k2.7-code"
    assert response.headers["x-router-model"] == "moonshotai/kimi-k2.7-code"
    assert "pinned" in response.headers["x-router-reason"]


def test_shadow_keeps_streaming_tools_and_missing_phase(tmp_path):
    scorer = _write_scorer(tmp_path, {PRO: 0.95, FLASH: 0.40})

    async def sse():
        yield b'data: {"choices":[{"delta":{"content":"hi"},"index":0}]}\n\n'
        yield b"data: [DONE]\n\n"

    provider = FakeProvider([{"status": 200, "stream": sse()}])
    client, _ = _client(tmp_path, scorer_path=scorer, provider=provider)
    tools = [{"type": "function", "function": {"name": "read", "parameters": {"type": "object"}}}]
    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={**CHAT, "stream": True, "tools": tools},
        headers=AUTH,
    ) as streamed:
        assert streamed.status_code == 200
        assert streamed.headers["x-router-path"] == "shadow"
        assert b"[DONE]" in b"".join(streamed.iter_bytes())

    client, provider2 = _client(tmp_path, scorer_path=scorer)
    missing_phase = client.post("/v1/chat/completions", json=CHAT, headers=AUTH)
    assert missing_phase.status_code == 200
    assert provider2.calls[0]["model"]
    assert missing_phase.headers["x-router-path"] == "shadow"


def test_learned_wins_does_not_hijack_shadow(tmp_path):
    scorer = _write_scorer(tmp_path, {PRO: 0.95, FLASH: 0.40})
    flag = tmp_path / "learned_wins.json"
    flag.write_text(json.dumps({"winner": "learned"}), encoding="utf-8")
    client, provider = _client(tmp_path, scorer_path=scorer, learned_flag=flag)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert response.status_code == 200
    assert provider.calls[0]["model"] == FLASH
    assert response.headers["x-router-path"] == "shadow"
    assert "learned" not in (response.headers.get("x-router-reason") or "").lower()


def test_shadow_jsonl_redaction_still_strips_secrets(tmp_path):
    scorer = _write_scorer(tmp_path, {PRO: 0.95, FLASH: 0.40})
    client, _ = _client(tmp_path, scorer_path=scorer)
    client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    log = tmp_path / "requests.jsonl"
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows[-1]["api_key"] = "sk-secret"
    log.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    events = client.get("/replay/events")
    assert events.status_code == 200
    blob = json.dumps(events.json())
    assert "sk-secret" not in blob
    assert "api_key" not in blob
    assert events.json()[-1]["path"] == "shadow"


def test_trained_serves_cheapest_above_bar(tmp_path):
    yaml_path = _tiny_catalog(tmp_path)
    scorer = _write_scorer(tmp_path, {"cheap/ok": 0.85, "mid/ok": 0.90, "dear/ok": 0.91})
    client, provider = _client(
        tmp_path, trained_path="trained", scorer_path=scorer, config_path=yaml_path
    )
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert response.status_code == 200
    assert provider.calls[0]["model"] == "cheap/ok"
    assert response.headers["x-router-model"] == "cheap/ok"
    assert response.headers["x-router-path"] == "trained"
    assert "x-router-reason" not in response.headers
    assert response.headers["x-router-confidence"] == "0.85"
    assert response.headers["x-router-complexity-bin"] == "standard"
    assert "rules_cost_delta_usd" in _last_row(tmp_path)
    assert _last_row(tmp_path)["path"] == "trained"


def test_trained_headers_match_decision_contract(tmp_path):
    yaml_path = _tiny_catalog(tmp_path)
    scorer = _write_scorer(tmp_path, {"cheap/ok": 0.85, "mid/ok": 0.90, "dear/ok": 0.91})
    client, _ = _client(tmp_path, trained_path="trained", scorer_path=scorer, config_path=yaml_path)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    h = response.headers
    for key in (
        "x-router-model",
        "x-router-phase",
        "x-router-effort",
        "x-router-complexity-bin",
        "x-router-confidence",
        "x-router-rule",
        "x-router-path",
        "x-router-baseline-model",
        "x-router-savings-usd",
        "x-router-reason-codes",
        "x-router-candidates",
        "x-router-threshold",
    ):
        assert key in h
    assert "x-router-bloom" not in h
    assert h["x-router-baseline-model"] == "dear/ok"
    assert h["x-router-rule"] == "threshold"


def test_low_effort_still_uses_scorer(tmp_path):
    yaml_path = _tiny_catalog(tmp_path)
    scorer = _write_scorer(tmp_path, {"cheap/ok": 0.01, "mid/ok": 0.90, "dear/ok": 0.91})
    client, provider = _client(
        tmp_path, trained_path="trained", scorer_path=scorer, config_path=yaml_path
    )
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize", "x-routing-effort": "low"},
    )
    assert response.status_code == 200
    assert provider.calls[0]["model"] == "mid/ok"


def test_max_effort_is_still_cheapest_above_bar(tmp_path):
    yaml_path = tmp_path / "models.yaml"
    yaml_path.write_text(
        """
fallback_model: cheap/ok
phase_threshold: {summarize: 0}
premium_aa_floor: 40
models:
  - id: cheap/ok
    enabled: true
    input_per_1m: 0.1
    output_per_1m: 0.1
    context_window: 100000
    supports_tools: true
    aa_index: 50
    aa_source: test
    measured_on: test
  - id: dear/ok
    enabled: true
    input_per_1m: 10
    output_per_1m: 10
    context_window: 100000
    supports_tools: true
    aa_index: 60
    aa_source: test
    measured_on: test
""",
        encoding="utf-8",
    )
    scorer = _write_scorer(tmp_path, {"cheap/ok": 0.97, "dear/ok": 0.99})
    client, provider = _client(
        tmp_path, trained_path="trained", scorer_path=scorer, config_path=yaml_path
    )
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize", "x-routing-effort": "max"},
    )
    assert response.status_code == 200
    assert provider.calls[0]["model"] == "cheap/ok"
    assert response.headers["x-router-model"] == "cheap/ok"


def test_effort_header_changes_threshold_and_max_regret(tmp_path):
    yaml_path = _tiny_catalog(tmp_path)
    scorer = _write_scorer(tmp_path, {"cheap/ok": 0.55, "mid/ok": 0.80, "dear/ok": 0.80})
    client, _ = _client(tmp_path, trained_path="trained", scorer_path=scorer, config_path=yaml_path)
    low = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize", "x-routing-effort": "low"},
    )
    high = client.post(
        "/v1/chat/completions",
        json={**CHAT, "messages": [{"role": "user", "content": "ping2"}]},
        headers={**AUTH, "x-agent-phase": "summarize", "x-routing-effort": "high"},
    )
    assert low.headers["x-router-model"] == "cheap/ok"
    assert high.headers["x-router-model"] == "mid/ok"
    assert low.headers["x-router-threshold"] != high.headers["x-router-threshold"]


def test_max_regret_skips_cheap_model_too_far_behind(tmp_path):
    yaml_path = _tiny_catalog(tmp_path)
    scorer = _write_scorer(tmp_path, {"cheap/ok": 0.40, "mid/ok": 0.85, "dear/ok": 0.90})
    client, provider = _client(
        tmp_path, trained_path="trained", scorer_path=scorer, config_path=yaml_path
    )
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert provider.calls[0]["model"] == "mid/ok"
    assert response.headers["x-router-rule"] == "max_regret"


def test_threshold_skips_cheapest_below_bar(tmp_path):
    yaml_path = _tiny_catalog(tmp_path)
    scorer = _write_scorer(tmp_path, {"cheap/ok": 0.05, "mid/ok": 0.85, "dear/ok": 0.90})
    client, provider = _client(
        tmp_path, trained_path="trained", scorer_path=scorer, config_path=yaml_path
    )
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert provider.calls[0]["model"] == "mid/ok"
    assert response.headers["x-router-rule"] == "threshold"


def test_fallback_declined_returns_configured_fallback(tmp_path):
    yaml_path = _tiny_catalog(tmp_path)
    scorer = _write_scorer(tmp_path, {"cheap/ok": 0.02, "mid/ok": 0.03, "dear/ok": 0.04})
    client, provider = _client(
        tmp_path, trained_path="trained", scorer_path=scorer, config_path=yaml_path
    )
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert response.status_code == 200
    assert provider.calls[0]["model"] == "cheap/ok"
    assert response.headers["x-router-rule"] == "fallback_declined"


def test_missing_scorer_serves_rules_with_scorer_down(tmp_path):
    client, provider = _client(tmp_path, trained_path="trained", scorer_path=tmp_path / "missing.json")
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert response.status_code == 200
    assert provider.calls[0]["model"] == FLASH
    assert response.headers["x-router-path"] == "rules"
    assert response.headers["x-router-reason"]
    assert "scorer_down" in (response.headers.get("x-router-reason-codes") or "")
    assert "x-router-confidence" not in response.headers
    flag = tmp_path / "learned_wins.json"
    flag.write_text(json.dumps({"winner": "learned"}), encoding="utf-8")
    client, provider = _client(
        tmp_path,
        trained_path="trained",
        scorer_path=tmp_path / "missing.json",
        learned_flag=flag,
        cache_dir=tmp_path / "cache-learned",
    )
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert "learned" not in response.headers.get("x-router-reason", "").lower()
    assert provider.calls[0]["model"] == FLASH


def test_tools_exclude_no_tools_from_candidates_and_p_success(tmp_path):
    yaml_path = _tiny_catalog(tmp_path)
    scorer = _write_scorer(
        tmp_path,
        {"cheap/ok": 0.85, "mid/ok": 0.90, "dear/ok": 0.91, "cheap/no-tools": 0.99},
    )
    client, provider = _client(
        tmp_path, trained_path="trained", scorer_path=scorer, config_path=yaml_path
    )
    body = {
        **CHAT,
        "tools": [{"type": "function", "function": {"name": "read", "parameters": {}}}],
    }
    response = client.post("/v1/chat/completions", json=body, headers={**AUTH, "x-agent-phase": "edit"})
    assert provider.calls[0]["model"] != "cheap/no-tools"
    assert "cheap/no-tools" not in response.headers["x-router-candidates"]
    row = _last_row(tmp_path)
    assert "cheap/no-tools" not in row["p_success"]
    assert "cheap/no-tools" not in row["candidates"]


def test_allow_list_without_k3_does_not_use_k3_as_savings_baseline(tmp_path):
    scorer = _write_scorer(tmp_path, {FLASH: 0.85, PRO: 0.90})
    client, _ = _client(tmp_path, trained_path="trained", scorer_path=scorer)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={
            **AUTH,
            "x-agent-phase": "summarize",
            "x-allowed-models": f"{FLASH},{PRO}",
        },
    )
    assert response.headers["x-router-baseline-model"] == PRO
    assert "kimi-k3" not in response.headers["x-router-baseline-model"]
    row = _last_row(tmp_path)
    assert row["baseline_model_id"] == PRO
    assert "savings" not in json.dumps({k: v for k, v in row.items() if "delta" in k})


def test_shadow_logs_rules_cost_delta_not_named_savings(tmp_path):
    scorer = _write_scorer(tmp_path, {PRO: 0.95, FLASH: 0.40})
    client, _ = _client(tmp_path, scorer_path=scorer)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert response.headers["x-router-trained-would"] == PRO
    row = _last_row(tmp_path)
    assert row["path"] == "shadow"
    assert "rules_cost_delta_usd" in row
    assert row["rules_cost_delta_usd"] != row.get("savings_usd")


def test_learned_wins_does_not_hijack_trained(tmp_path):
    yaml_path = _tiny_catalog(tmp_path)
    scorer = _write_scorer(tmp_path, {"cheap/ok": 0.85, "mid/ok": 0.90, "dear/ok": 0.91})
    flag = tmp_path / "learned_wins.json"
    flag.write_text(json.dumps({"winner": "learned"}), encoding="utf-8")
    client, provider = _client(
        tmp_path,
        trained_path="trained",
        scorer_path=scorer,
        config_path=yaml_path,
        learned_flag=flag,
    )
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert provider.calls[0]["model"] == "cheap/ok"
    assert response.headers["x-router-path"] == "trained"
    assert "learned" not in (response.headers.get("x-router-reason") or "").lower()


def test_fitted_artifact_serves_trained_and_corrupt_is_scorer_down(tmp_path):
    yaml_path = _tiny_catalog(tmp_path)
    artifact = tmp_path / "scorer.json"
    artifact.write_text(
        json.dumps(
            {
                "not_spec_floors": True,
                "complexity_bin": "trivial",
                "p_success": {"cheap/ok": 0.8, "mid/ok": 0.9, "dear/ok": 0.91},
            }
        ),
        encoding="utf-8",
    )
    client, provider = _client(
        tmp_path, trained_path="trained", scorer_path=artifact, config_path=yaml_path
    )
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert provider.calls[0]["model"] == "cheap/ok"
    assert response.headers["x-router-complexity-bin"] == "trivial"
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    client, provider = _client(
        tmp_path,
        trained_path="trained",
        scorer_path=bad,
        config_path=yaml_path,
        cache_dir=tmp_path / "cache-bad",
    )
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert response.headers["x-router-path"] == "rules"
    assert "scorer_down" in (response.headers.get("x-router-reason-codes") or "")


def test_shadow_loads_rec_a_and_predicts_bin_without_hint_bin(tmp_path):
    """Fitted Rec A artifact loads on shadow; complexity bin from request features, not hint_bin."""
    from aiand_router.scorer import BINS, FAMILIES

    yaml_path = _tiny_catalog(tmp_path)
    obs = 3 + 4 + len(FAMILIES)
    full = obs + len(BINS)
    zeros = [0.0] * full
    obs_z = [0.0] * obs
    fam_summarize = 3 + 4 + list(FAMILIES).index("summarize")
    frontier = list(obs_z)
    frontier[fam_summarize] = 8.0
    artifact = tmp_path / "scorer.json"
    artifact.write_text(
        json.dumps(
            {
                "not_spec_floors": True,
                "complexity_bin": "trivial",
                "weights": {"cheap/ok": zeros, "mid/ok": zeros, "dear/ok": zeros},
                "intercepts": {"cheap/ok": -1.0, "mid/ok": 0.5, "dear/ok": 1.5},
                "p_success": {"cheap/ok": 0.3, "mid/ok": 0.6, "dear/ok": 0.9},
                "bin_weights": {
                    "trivial": obs_z,
                    "standard": obs_z,
                    "hard": obs_z,
                    "frontier": frontier,
                },
                "platt": {"a": 1.0, "b": 0.0},
            }
        ),
        encoding="utf-8",
    )
    client, provider = _client(tmp_path, scorer_path=artifact, config_path=yaml_path)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert response.status_code == 200
    assert response.headers["x-router-path"] == "shadow"
    assert provider.calls[0]["model"] == "cheap/ok"
    assert response.headers["x-router-complexity-bin"] == "frontier"
    assert "x-router-trained-would" in response.headers
    row = _last_row(tmp_path)
    assert row["path"] == "shadow"
    assert row["complexity_bin"] == "frontier"
