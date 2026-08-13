"""Opt-in streamed tool-call through the gateway. Not a CI job."""

from __future__ import annotations

import argparse
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()


def main(argv: list[str] | None = None) -> int:
    if os.getenv("AIAND_SMOKE") != "1":
        print(
            "refusing: this talks to aiand through the gateway. "
            "Start the server, then set AIAND_SMOKE=1 and re-run. Not for CI.",
            file=sys.stderr,
        )
        return 2
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.getenv("ROUTER_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--api-key", default=os.getenv("ROUTER_API_KEY", "change-me"))
    args = parser.parse_args(argv)
    body = {
        "model": "router/auto",
        "stream": True,
        "messages": [{"role": "user", "content": "Call list_files on . then stop."}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                    },
                },
            }
        ],
    }
    with httpx.stream(
        "POST",
        f"{args.base_url.rstrip('/')}/v1/chat/completions",
        headers={"Authorization": f"Bearer {args.api_key}", "x-agent-phase": "discover"},
        json=body,
        timeout=120.0,
    ) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
