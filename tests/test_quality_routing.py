"""Quality-first routing acceptance harness — 6 behavior assertions.

Drives the gateway via create_app + TestClient + FakeProvider, using fixture
scorer artifacts with explicit per-model p_success values. Each test overrides
TRAINED_PATH via monkeypatch to avoid .env interference (the repo .env sets
TRAINED_PATH=trained + SCORER_PATH=scorer-hard-logistic.json, which causes
31 pre-existing failures in test_gateway.py).

Assertions cover the trained-path behavior matrix:
  1. effort=max, frontier bin, only K3 clears t_max/r_max -> K3 served
  2. effort=max, frontier bin, cheaper survivor also clears and within r_max -> cheapest served
  3. Default effort (medium), K3 gated by premium floor -> absent from candidates
  4. effort=max, trivial bin, Flash within r_max of K3 -> Flash served (no K3 worship)
  5. Default effort, cheap model within max_regret of top -> cheapest served
  6. Nothing clears the bar -> fallback_declined, fallback model, HTTP 200
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aiand_router.app import create_app
from aiand_router.router import SpendLog
from fastapi.testclient import TestClient

AUTH = {"Authorization": "Bearer secret"}
CHAT = {"model": "router/auto", "messages": [{"role": "user", "content": "ping"}]}

K3 = "moonshotai/kimi-k3"
FLASH = "deepseek-ai/deepseek-v4-flash"
PRO = "deepseek-ai/deepseek-v4-pro"
GLM = "zai-org/glm-5.2"
K27 = "moonshotai/kimi-k2.7-code"
MOTIF = "motif-technologies/motif-3"
QWEN = "qwen/qwen3.6-27b"

# Custom config: premium_aa_floor=50 so Flash (aa=52) survives the premium
# floor at effort=max (threshold=max(phase_bar, 50)=50, floor check skipped).
# At effort=medium with phase_bar < 50, models with aa >= 50 are still gated.
_MAX_CFG = """
fallback_model: deepseek-ai/deepseek-v4-flash
premium_aa_floor: 50
max_regret: 8
phase_threshold: {summarize: 0, plan: 0, edit: 0, tool: 0, debug: 0, discover: 0}
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
  - id: zai-org/glm-5.2
    enabled: true
    input_per_1m: 1.00
    cached_input_per_1m: 0.30
    output_per_1m: 4.00
    context_window: 1048576
    supports_tools: true
    supports_json: true
    supports_streaming: true
    max_output_tokens: 16384
    aa_index: 53
    aa_source: test
    measured_on: test
  - id: moonshotai/kimi-k3
    enabled: true
    input_per_1m: 3.00
    cached_input_per_1m: 0.50
    output_per_1m: 12.50
    context_window: 1048576
    supports_tools: true
    supports_json: true
    supports_streaming: true
    max_output_tokens: 16384
    aa_index: 60
    aa_source: test
    measured_on: test
"""


class FakeProvider:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def complete(self, body: dict) -> dict:
        self.calls.append(dict(body))
        return {
            "status": 200,
            "json": {
                "id": "chatcmpl-fake",
                "choices": [
                    {"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        }


def _scorer(
    tmp_path: Path, p_success: dict[str, float], bin: str = "standard"
) -> Path:
    """Fixture scorer artifact with explicit per-model p_success values.

    Uses the raw p_success path (no weights/gbdt) so values are used directly
    without calibration. The calibrator key is included for format completeness.
    """
    artifact = {
        "calibrator": {"mode": "platt", "a": 1.0, "b": 0.0},
        "p_success": p_success,
        "complexity_bin": bin,
        "n_gold": 100,
        "n_cal": 50,
    }
    path = tmp_path / "scorer.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    return path


def _max_config(tmp_path: Path) -> Path:
    p = tmp_path / "models_max.yaml"
    p.write_text(_MAX_CFG, encoding="utf-8")
    return p


def _client(
    tmp_path: Path,
    scorer_path: Path,
    config_path: Path | None = None,
) -> tuple[TestClient, FakeProvider]:
    provider = FakeProvider()
    spend = SpendLog(tmp_path / "spend.txt", 15.0)
    app = create_app(
        provider=provider,
        spend=spend,
        log_path=tmp_path / "requests.jsonl",
        router_key="secret",
        budget=15.0,
        cache_dir=tmp_path / "cache",
        config_path=config_path,
        trained_path="trained",
        scorer_path=scorer_path,
    )
    return TestClient(app), provider


def _clean_env(monkeypatch):
    """Remove .env env vars so they don't interfere with explicit params."""
    monkeypatch.delenv("TRAINED_PATH", raising=False)
    monkeypatch.delenv("SCORER_PATH", raising=False)


# --------------------------------------------------------------------------- #
# 1. effort=max, frontier bin, only K3 clears t_max/r_max -> K3 served
# --------------------------------------------------------------------------- #
def test_max_effort_frontier_bin_only_k3_clears_bar(tmp_path, monkeypatch):
    _clean_env(monkeypatch)
    cfg = _max_config(tmp_path)
    scorer = _scorer(
        tmp_path,
        {K3: 0.95, FLASH: 0.50, PRO: 0.55, GLM: 0.55},
        bin="frontier",
    )
    client, provider = _client(tmp_path, scorer, config_path=cfg)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize", "x-routing-effort": "max"},
    )
    assert response.status_code == 200
    assert provider.calls[0]["model"] == K3
    assert response.headers["x-router-model"] == K3
    assert response.headers["x-router-path"] == "trained"
    assert response.headers["x-router-complexity-bin"] == "frontier"


# --------------------------------------------------------------------------- #
# 2. effort=max, frontier bin, cheaper survivor also clears and within r_max
#    -> cheapest survivor served (no unconditional K3 worship)
# --------------------------------------------------------------------------- #
def test_max_effort_frontier_bin_cheaper_survivor_within_regret(tmp_path, monkeypatch):
    _clean_env(monkeypatch)
    cfg = _max_config(tmp_path)
    scorer = _scorer(
        tmp_path,
        {K3: 0.95, FLASH: 0.93, PRO: 0.55, GLM: 0.55},
        bin="frontier",
    )
    client, provider = _client(tmp_path, scorer, config_path=cfg)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize", "x-routing-effort": "max"},
    )
    assert response.status_code == 200
    assert provider.calls[0]["model"] == FLASH
    assert response.headers["x-router-model"] == FLASH
    assert response.headers["x-router-path"] == "trained"


# --------------------------------------------------------------------------- #
# 3. Default effort (medium), K3 present in catalog but gated by premium floor
#    -> K3 absent from candidates/p_success keys entirely
# --------------------------------------------------------------------------- #
def test_default_effort_k3_absent_from_candidates(tmp_path, monkeypatch):
    _clean_env(monkeypatch)
    # Default config: premium_aa_floor=58, K3 aa=60 -> gated at effort=medium
    scorer = _scorer(
        tmp_path,
        {K3: 0.95, FLASH: 0.85, PRO: 0.90},
        bin="standard",
    )
    client, provider = _client(tmp_path, scorer)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert response.status_code == 200
    candidates = response.headers["x-router-candidates"]
    assert K3 not in candidates
    assert response.headers["x-router-path"] == "trained"


# --------------------------------------------------------------------------- #
# 4. effort=max, trivial bin, K3 and Flash both above t_max, Flash within r_max
#    -> Flash served (never select K3 when not needed)
# --------------------------------------------------------------------------- #
def test_max_effort_trivial_bin_flash_served_not_k3(tmp_path, monkeypatch):
    _clean_env(monkeypatch)
    cfg = _max_config(tmp_path)
    scorer = _scorer(
        tmp_path,
        {K3: 0.95, FLASH: 0.93, PRO: 0.55, GLM: 0.55},
        bin="trivial",
    )
    client, provider = _client(tmp_path, scorer, config_path=cfg)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize", "x-routing-effort": "max"},
    )
    assert response.status_code == 200
    assert provider.calls[0]["model"] == FLASH
    assert response.headers["x-router-model"] == FLASH
    assert response.headers["x-router-complexity-bin"] == "trivial"


# --------------------------------------------------------------------------- #
# 5. Default effort, cheap model clears threshold within max_regret of top
#    -> cheapest served (cost discipline)
# --------------------------------------------------------------------------- #
def test_default_effort_cheapest_within_regret_served(tmp_path, monkeypatch):
    _clean_env(monkeypatch)
    # Default config: premium_aa_floor=58, K3 gated at medium
    # effort=medium -> threshold=0.10, max_regret=0.20 (Pioneer ship defaults)
    # Pro=0.90 (top), Flash=0.85 (clears threshold directly, cheapest) -> Flash served
    scorer = _scorer(
        tmp_path,
        {FLASH: 0.85, PRO: 0.90, GLM: 0.08, K27: 0.07, MOTIF: 0.06, QWEN: 0.05},
        bin="standard",
    )
    client, provider = _client(tmp_path, scorer)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert response.status_code == 200
    assert provider.calls[0]["model"] == FLASH
    assert response.headers["x-router-model"] == FLASH
    assert response.headers["x-router-rule"] == "threshold"


# --------------------------------------------------------------------------- #
# 6. Nothing clears the bar -> fallback_declined, fallback model, HTTP 200
# --------------------------------------------------------------------------- #
def test_nothing_clears_bar_fallback_declined(tmp_path, monkeypatch):
    _clean_env(monkeypatch)
    # effort=medium -> threshold=0.10; all p_success below 0.10
    scorer = _scorer(
        tmp_path,
        {FLASH: 0.05, PRO: 0.08, GLM: 0.06},
        bin="standard",
    )
    client, provider = _client(tmp_path, scorer)
    response = client.post(
        "/v1/chat/completions",
        json=CHAT,
        headers={**AUTH, "x-agent-phase": "summarize"},
    )
    assert response.status_code == 200
    assert response.headers["x-router-rule"] == "fallback_declined"
    assert response.headers["x-router-model"] == FLASH
    assert response.headers["x-router-path"] == "trained"
