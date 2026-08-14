from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def request_cache_key(body: dict[str, Any], model_id: str, key_fp: str = "") -> str:
    messages = body.get("messages") or []
    payload = {
        "prompt": [m for m in messages if m.get("role") != "system"],
        "model": model_id,
        "system": [m for m in messages if m.get("role") == "system"],
        "tools": body.get("tools"),
        "temperature": body.get("temperature"),
        "max_tokens": body.get("max_tokens") or body.get("max_completion_tokens"),
        "key_fp": key_fp or "",
    }
    if body.get("reasoning_effort"):
        payload["reasoning_effort"] = body["reasoning_effort"]
    blob = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class RequestCache:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> dict[str, Any] | None:
        path = self.directory / f"{key}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def put(self, key: str, payload: dict[str, Any]) -> None:
        (self.directory / f"{key}.json").write_text(
            json.dumps(payload, default=str), encoding="utf-8"
        )
