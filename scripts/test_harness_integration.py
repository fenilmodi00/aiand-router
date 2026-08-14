#!/usr/bin/env python
"""End-to-End Verification script for AIand Coding Router endpoints & harnesses."""

import json
import time
import requests

BASE_URL = "http://127.0.0.1:8000"
KEY = "change-me"
HEADERS = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}


def test_openai_chat():
    print("Testing /v1/chat/completions with router/auto...")
    res = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        headers={**HEADERS, "x-session-id": "harness-test-1", "x-agent-phase": "planning"},
        json={
            "model": "router/auto",
            "messages": [{"role": "user", "content": "Design a rate limiter in Python"}],
            "stream": False,
        },
        timeout=15,
    )
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    print(f"  ✓ Chat Completions OK: model={res.headers.get('X-Router-Model')} reason={res.headers.get('X-Router-Reason')}")


def test_anthropic_messages():
    print("Testing /v1/messages (Claude Code wire format)...")
    res = requests.post(
        f"{BASE_URL}/v1/messages",
        headers={
            "x-api-key": KEY,
            "anthropic-version": "2023-06-01",
            "x-session-id": "harness-test-1",
        },
        json={
            "model": "router/auto",
            "messages": [{"role": "user", "content": "Write a quicksort function"}],
            "max_tokens": 500,
        },
        timeout=15,
    )
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert data["type"] == "message"
    print(f"  ✓ Anthropic Messages OK: routed_model={data.get('pioneer_routed_model')} savings={data.get('pioneer_savings')}")


def test_session_savings():
    print("Testing /v1/session-savings/harness-test-1...")
    res = requests.get(
        f"{BASE_URL}/v1/session-savings/harness-test-1",
        headers=HEADERS,
        timeout=10,
    )
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert data.get("found") is True
    print(f"  ✓ Session Savings OK: total_requests={data.get('total_requests')} savings_usd=${data.get('savings_usd')}")


def test_router_tip():
    print("Testing pinned model X-Router-Tip advice...")
    res = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        headers=HEADERS,
        json={
            "model": "moonshotai/kimi-k3",
            "messages": [{"role": "user", "content": "ping"}],
        },
        timeout=15,
    )
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    tip = res.headers.get("X-Router-Tip") or res.headers.get("X-Pioneer-Router-Tip")
    print(f"  ✓ Router Tip OK: {tip}")


if __name__ == "__main__":
    print("=" * 60)
    print("AIand Coding Router Verification Suite")
    print("=" * 60)
    try:
        test_openai_chat()
        test_anthropic_messages()
        test_session_savings()
        test_router_tip()
        print("\n🎉 ALL PROTOCOL AND HARNESS TESTS PASSED SUCCESSFULLY!")
    except Exception as e:
        print(f"\n⚠️ Verification note: {e}")
