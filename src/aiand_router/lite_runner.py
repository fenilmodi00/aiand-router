"""Minimal SWE-bench-Lite session runner for the bounded gate.

Reuses train._pytest_verify for harness-proxy resolve. Flashlight-style turn
loop (discover -> plan -> edit -> debug -> summarize) through the gateway with
model router/auto. Fixture mode routes through a local stub gateway function
instead of HTTP, keeping the same code path surface.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

import httpx

from .train import _pytest_verify

ROOT = Path(__file__).resolve().parents[2]
CAP = 50  # hard cap on instance count

_TURNS = [
    ("discover", "List what is in this repo and what the tests expect."),
    ("plan", "Plan the smallest fix. Do not write code yet."),
    ("edit", "Write the corrected Python module only, inside a ```python fence."),
    ("debug", "Tests failed. Write the corrected Python module only, inside a ```python fence."),
    ("summarize", "One paragraph: what broke, what you changed."),
]


def fetch_lite_ids(
    n: int = 30, cap: int = CAP, cache_dir: str = "data/lite_cache"
) -> list[str]:
    """Deterministic first-N instance ids of SWE-bench_Lite, cached to disk."""
    n = min(n, cap)
    cache_path = Path(cache_dir) / "lite_ids.json"
    if cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if len(cached) >= n:
            return cached[:n]
    url = "https://datasets-server.huggingface.co/rows"
    params = {
        "dataset": "princeton-nlp/SWE-bench_Lite",
        "config": "default",
        "split": "test",
        "offset": 0,
        "length": n,
    }
    resp = httpx.get(url, params=params, timeout=30.0)
    resp.raise_for_status()
    ids = [row["row"]["instance_id"] for row in resp.json().get("rows", [])]
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(ids), encoding="utf-8")
    return ids[:n]


def _load_fixture(path: str) -> list[dict[str, Any]]:
    """Load fixture JSON; each row must have instance_id."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for i, row in enumerate(data):
        if "instance_id" not in row:
            raise ValueError(f"fixture row {i} missing instance_id")
    return data


def _fixture_gateway(row: dict[str, Any]) -> Callable[[str, str], str]:
    """Stub gateway: returns pre-baked patch for edit/debug, empty for others."""
    patch = row.get("patch", "")

    def _chat(phase: str, content: str) -> str:
        if phase in ("edit", "debug"):
            return f"```python\n{patch}\n```"
        return ""

    return _chat


def _http_gateway(client: httpx.Client, api_key: str) -> Callable[[str, str], str]:
    """HTTP gateway: calls /v1/chat/completions with router/auto."""

    def _chat(phase: str, content: str) -> str:
        resp = client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "x-agent-phase": phase},
            json={"model": "router/auto", "messages": [{"role": "user", "content": content}]},
        )
        resp.raise_for_status()
        return (
            ((resp.json().get("choices") or [{}])[0].get("message") or {}).get("content")
            or ""
        )

    return _chat


def _run_turn_loop(
    gateway_fn: Callable[[str, str], str], context: str, meta: dict[str, Any]
) -> bool:
    """Flashlight-style: discover -> plan -> edit -> debug -> summarize."""
    gateway_fn("discover", context + "\n\n" + _TURNS[0][1])
    gateway_fn("plan", context + "\n\n" + _TURNS[1][1])
    edit_text = gateway_fn("edit", context + "\n\n" + _TURNS[2][1])
    resolved = _pytest_verify(edit_text, meta)
    if not resolved:
        debug_text = gateway_fn("debug", context + "\n\n" + _TURNS[3][1])
        resolved = _pytest_verify(debug_text, meta)
    gateway_fn("summarize", context + "\n\n" + _TURNS[4][1])
    return bool(resolved)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Atomic JSONL write — overwrites, no append-duplication."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".jsonl.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    os.replace(tmp, path)


def run_slice(
    ids: list[str],
    gateway_url: str | None,
    out_path: str | Path,
    fixture: list[dict[str, Any]] | None = None,
) -> None:
    """For each instance: turn loop -> patch -> pytest-harness resolve -> JSONL row."""
    fixture_map = {r["instance_id"]: r for r in fixture} if fixture else {}
    client = (
        None
        if fixture
        else httpx.Client(base_url=(gateway_url or "").rstrip("/"), timeout=120.0)
    )
    rows: list[dict[str, Any]] = []
    for instance_id in ids:
        meta: dict[str, Any] = {"verify_pytest": True}
        if fixture:
            row = fixture_map.get(instance_id, {})
            meta["module"] = row.get("module", "fix.py")
            meta["tests"] = row.get("tests")
            gateway_fn = _fixture_gateway(row)
        else:
            assert client is not None
            gateway_fn = _http_gateway(client, "change-me")
        context = f"instance: {instance_id}"
        resolved = _run_turn_loop(gateway_fn, context, meta)
        rows.append(
            {
                "instance_id": instance_id,
                "resolved": resolved,
                "label_type": "harness_proxy",
            }
        )
        print(f"  {instance_id}: resolved={resolved}")
    if client:
        client.close()
    _write_jsonl(Path(out_path), rows)
    print(f"wrote {len(rows)} rows to {out_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=30)
    parser.add_argument("--fixture", default=None)
    parser.add_argument("--gateway", default="http://127.0.0.1:8000")
    parser.add_argument("--out", default=str(ROOT / "data" / "lite_results.jsonl"))
    args = parser.parse_args(argv)

    if args.n > CAP:
        print(f"clamping --n {args.n} to cap {CAP}", file=sys.stderr)
        args.n = CAP

    if args.fixture:
        fixture = _load_fixture(args.fixture)
        ids = [r["instance_id"] for r in fixture][: args.n]
        run_slice(ids, None, args.out, fixture=fixture)
    else:
        ids = fetch_lite_ids(n=args.n)
        run_slice(ids, args.gateway, args.out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
