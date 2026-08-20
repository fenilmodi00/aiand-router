#!/usr/bin/env python
"""Self-contained shadow run: starts uvicorn in a thread, sends traffic, audits JSONL.

Usage:
    python scripts/run_shadow.py

Sets TRAINED_PATH=shadow BEFORE importing the app, starts uvicorn programmatically
in a background thread, sends 160 requests (semaphore(5)), stops the server, and
writes data/shadow_audit.json.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import time
from pathlib import Path

# CRITICAL: Set env vars BEFORE any aiand_router imports.
ROOT = Path(__file__).resolve().parent.parent
os.environ["TRAINED_PATH"] = "shadow"
os.environ["BUDGET_LIMIT_USD"] = "14.09"
os.environ["SCORER_PATH"] = str(ROOT / "data" / "scorer.json")
sys.path.insert(0, str(ROOT / "src"))

import httpx  # noqa: E402

# --- Traffic constants (from scripts/shadow_traffic.py) ---
PHASES = ["discover", "plan", "edit", "debug", "summarize", "tool"]
EFFORTS = ["low", "medium", "high", "max"]
PROMPTS = [
    "Write a Python function to reverse a string.",
    "Explain what a closure is in JavaScript.",
    "Fix this bug: TypeError: cannot read property 'map' of undefined.",
    "Write a SQL query to find the top 5 customers by total order value.",
    "Refactor this function to use async/await instead of callbacks.",
    "Write a regex to validate an email address.",
    "Explain the difference between let, const, and var in JavaScript.",
    "Write a unit test for a function that checks if a number is prime.",
    "Debug: my Docker container exits immediately with code 137.",
    "Write a TypeScript interface for a User with name, email, and roles.",
    "Explain how garbage collection works in Python.",
    "Write a function to merge two sorted arrays.",
    "Fix: KeyError: 'user_id' when processing webhook payload.",
    "Write a curl command to POST JSON with an Authorization header.",
    "Explain the CAP theorem and when it matters.",
    "Write a Python decorator that logs function execution time.",
    "How do I prevent SQL injection in a Node.js Express app?",
    "Write a GitLab CI job to run pytest on every push.",
    "Explain what eventual consistency means.",
    "Write a function to parse a CSV file without using pandas.",
    "Fix: ImportError: cannot import name 'Literal' from 'typing'.",
    "Write a Dockerfile for a Python FastAPI app.",
    "Explain the difference between processes and threads.",
    "Write a shell script to find and kill a process by port number.",
    "How does HTTPS handshake work? Explain step by step.",
    "Write a Rust function to read a file line by line.",
    "Fix: CORS error when calling API from React frontend.",
    "Write a Kubernetes manifest for a Deployment with 3 replicas.",
    "Explain what a context manager is in Python.",
    "Write a function to deep clone an object in JavaScript.",
]

SPEND_PATH = ROOT / "data" / "spend.txt"
LOG_PATH = ROOT / "data" / "requests.jsonl"
AUDIT_PATH = ROOT / "data" / "shadow_audit.json"
BASE_URL = "http://127.0.0.1:8000"
TRAFFIC_COUNT = 160


def load_router_key() -> str:
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("ROUTER_API_KEY="):
                return line.split("=", 1)[1].strip()
    return os.getenv("ROUTER_API_KEY", "change-me")


def read_spend() -> float:
    return float(SPEND_PATH.read_text(encoding="utf-8").strip()) if SPEND_PATH.exists() else 0.0


def count_jsonl_lines() -> int:
    if not LOG_PATH.exists():
        return 0
    return sum(1 for line in LOG_PATH.read_text(encoding="utf-8").splitlines() if line.strip())


def restore_if_archived(spend_before: float, lines_before: int) -> None:
    """Handle gateway archive: restore spend/requests if reset on startup."""
    current_spend = read_spend()
    if current_spend < spend_before:
        SPEND_PATH.write_text(f"{spend_before}\n", encoding="utf-8")
        print(f"  Restored spend.txt: {current_spend} -> {spend_before}")

    current_lines = count_jsonl_lines()
    if current_lines < lines_before:
        archive_dir = ROOT / "data" / "archive"
        if archive_dir.exists():
            for stamp_dir in sorted(archive_dir.iterdir(), reverse=True):
                archived_log = stamp_dir / "requests.jsonl"
                if archived_log.exists():
                    archived_content = archived_log.read_text(encoding="utf-8")
                    current_content = LOG_PATH.read_text(encoding="utf-8") if LOG_PATH.exists() else ""
                    LOG_PATH.write_text(archived_content + current_content, encoding="utf-8")
                    print(f"  Restored requests.jsonl from {archived_log}")
                    break


async def send_one(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    idx: int,
    api_key: str,
) -> dict:
    phase = PHASES[idx % len(PHASES)]
    effort = EFFORTS[idx % len(EFFORTS)]
    prompt = PROMPTS[idx % len(PROMPTS)]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "x-agent-phase": phase,
        "x-routing-effort": effort,
    }
    body = {
        "model": "router/auto",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 50,
    }
    url = f"{BASE_URL}/v1/chat/completions"

    async with sem:
        for attempt in range(2):
            try:
                resp = await client.post(url, json=body, headers=headers, timeout=60)
                status = resp.status_code
                if status < 400 or attempt == 1:
                    return {"idx": idx, "status": status, "ok": status < 400}
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                if attempt == 1:
                    return {"idx": idx, "status": 0, "ok": False, "error": str(exc)}
                await asyncio.sleep(1)
        return {"idx": idx, "status": 0, "ok": False, "error": "exhausted retries"}


async def wait_for_server(client: httpx.AsyncClient) -> bool:
    for _ in range(30):
        try:
            r = await client.get(f"{BASE_URL}/health", timeout=5)
            if r.status_code == 200:
                return True
        except (httpx.TimeoutException, httpx.ConnectError):
            pass
        await asyncio.sleep(1)
    return False


async def send_traffic(api_key: str) -> list[dict]:
    sem = asyncio.Semaphore(5)
    async with httpx.AsyncClient() as client:
        if not await wait_for_server(client):
            print("ERROR: server not reachable after 30s", file=sys.stderr)
            return []
        tasks = [send_one(client, sem, i, api_key) for i in range(TRAFFIC_COUNT)]
        return await asyncio.gather(*tasks)


def audit_jsonl(lines_before: int, spend_before: float, spend_after: float) -> dict:
    new_rows: list[dict] = []
    if LOG_PATH.exists():
        all_lines = [l for l in LOG_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
        for line in all_lines[lines_before:]:
            try:
                new_rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    shadow_rows = [r for r in new_rows if r.get("path") == "shadow"]
    scorer_down_rows = [r for r in new_rows if "scorer_down" in (r.get("reason_codes") or [])]
    rows_with_all_fields = [
        r for r in shadow_rows
        if r.get("trained_selected") is not None
        and r.get("trained_confidence") is not None
        and r.get("rules_cost_delta_usd") is not None
    ]
    fallback_declined = [r for r in shadow_rows if r.get("rule") == "fallback_declined"]
    deltas = [
        r["rules_cost_delta_usd"]
        for r in shadow_rows
        if r.get("rules_cost_delta_usd") is not None
    ]

    spend_delta = round(spend_after - spend_before, 6)
    return {
        "spend_before": spend_before,
        "spend_after": spend_after,
        "spend_delta": spend_delta,
        "new_rows_total": len(new_rows),
        "shadow_rows": len(shadow_rows),
        "scorer_down_rows": len(scorer_down_rows),
        "rows_with_all_fields": len(rows_with_all_fields),
        "fallback_declined_rows": len(fallback_declined),
        "fallback_declined_rate": round(len(fallback_declined) / max(1, len(shadow_rows)), 4),
        "rules_cost_delta_usd": {
            "count": len(deltas),
            "min": min(deltas) if deltas else None,
            "max": max(deltas) if deltas else None,
            "mean": round(sum(deltas) / len(deltas), 6) if deltas else None,
        },
        "pass": (
            len(shadow_rows) >= 100
            and len(scorer_down_rows) == 0
            and spend_delta <= 2.0
        ),
    }


def main() -> int:
    api_key = load_router_key()

    spend_before = read_spend()
    lines_before = count_jsonl_lines()
    print(f"Spend before: ${spend_before:.6f} | Lines before: {lines_before}")

    import uvicorn

    config = uvicorn.Config(
        app="aiand_router.app:app",
        host="127.0.0.1",
        port=8000,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    try:
        # Wait for server, then handle potential archive reset
        time.sleep(2)
        restore_if_archived(spend_before, lines_before)

        print(f"Sending {TRAFFIC_COUNT} requests (semaphore=5)...")
        t0 = time.perf_counter()
        results = asyncio.run(send_traffic(api_key))
        elapsed = time.perf_counter() - t0
        ok = sum(1 for r in results if r.get("ok"))
        fail = sum(1 for r in results if not r.get("ok"))
        print(f"Traffic: {ok} ok, {fail} failed in {elapsed:.1f}s")
    finally:
        server.should_exit = True
        thread.join(timeout=10)

    spend_after = read_spend()
    audit = audit_jsonl(lines_before, spend_before, spend_after)
    AUDIT_PATH.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit, indent=2))
    return 0 if audit["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
