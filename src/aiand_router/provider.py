from __future__ import annotations

import json
from typing import Any

import httpx


class HttpAiandProvider:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    async def complete(self, body: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Aiand-Metrics": "true",
        }
        url = f"{self.base_url}/chat/completions"
        timeout = httpx.Timeout(120.0, connect=15.0)
        if body.get("stream"):
            client = httpx.AsyncClient(timeout=timeout)
            req = client.build_request("POST", url, json=body, headers=headers)
            resp = await client.send(req, stream=True)
            if resp.status_code >= 400:
                err = await resp.aread()
                await resp.aclose()
                await client.aclose()
                try:
                    parsed = json.loads(err)
                except json.JSONDecodeError:
                    parsed = {"error": {"message": err.decode("utf-8", "replace")}}
                return {"status": resp.status_code, "json": parsed}

            async def gen():
                try:
                    async for chunk in resp.aiter_bytes():
                        yield chunk
                finally:
                    await resp.aclose()
                    await client.aclose()

            return {"status": resp.status_code, "stream": gen()}

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=body, headers=headers)
            try:
                parsed = resp.json()
            except json.JSONDecodeError:
                parsed = {"error": {"message": resp.text}}
            return {"status": resp.status_code, "json": parsed}
