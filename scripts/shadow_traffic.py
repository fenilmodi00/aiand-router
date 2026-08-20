"""Shadow traffic generator: sends >=120 requests to the gateway in shadow mode.

Usage:
    python scripts/shadow_traffic.py [--url http://127.0.0.1:8000] [--count 120]

Reads ROUTER_API_KEY from .env. Max 5 concurrent requests via asyncio.Semaphore.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent

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


def load_router_key() -> str:
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("ROUTER_API_KEY="):
                return line.split("=", 1)[1].strip()
    return os.getenv("ROUTER_API_KEY", "change-me")


async def send_one(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    idx: int,
    api_key: str,
    base_url: str,
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
    url = f"{base_url}/v1/chat/completions"

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


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--count", type=int, default=120)
    args = parser.parse_args()

    api_key = load_router_key()

    async with httpx.AsyncClient() as client:
        for _ in range(30):
            try:
                r = await client.get(f"{args.url}/health", timeout=5)
                if r.status_code == 200:
                    break
            except (httpx.TimeoutException, httpx.ConnectError):
                pass
            await asyncio.sleep(1)
        else:
            print("ERROR: gateway not reachable after 30s", file=sys.stderr)
            return 1

        sem = asyncio.Semaphore(5)
        t0 = time.perf_counter()
        tasks = [send_one(client, sem, i, api_key, args.url) for i in range(args.count)]
        results = await asyncio.gather(*tasks)

    elapsed = time.perf_counter() - t0
    ok = sum(1 for r in results if r["ok"])
    fail = sum(1 for r in results if not r["ok"])
    print(f"Sent {args.count} requests in {elapsed:.1f}s — {ok} ok, {fail} failed")
    if fail:
        for r in results:
            if not r["ok"]:
                print(f"  fail idx={r['idx']} status={r['status']} err={r.get('error', '')}")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
