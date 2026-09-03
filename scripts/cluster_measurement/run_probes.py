#!/usr/bin/env python3
"""Paid probe runner for cluster-routing calibration (v0.79).

Reads prompt matrices from /root/router-measurements/matrices/<tier>.jsonl,
POSTs each prompt to https://api.aiand.com/v1/chat/completions, and appends
one JSON record per call to /root/router-measurements/responses/<tier>/<model>.jsonl.

Usage:
    python3 scripts/cluster_measurement/run_probes.py            # all tiers, all models
    python3 scripts/cluster_measurement/run_probes.py --tier hard
    python3 scripts/cluster_measurement/run_probes.py --dry-run  # list models + 1-token call each

Stdlib only. Streamed requests (stream: true + stream_options.include_usage)
for accurate token accounting; usage falls back to a chars/4 estimate.
Aborts launching new calls if projected total spend exceeds BUDGET_CAP_USD.
"""
import argparse
import json
import math
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

API_BASE = "https://api.aiand.com/v1"
ENV_FILE = "/root/aiand-router/.env.local"
MEAS_DIR = "/root/router-measurements"
TIERS = ["hard", "medium", "bfcl", "routerarena"]

MODELS = {
    # model id: (output_usd_per_1k, reasoning_effort)
    "zai-org/glm-5.3": (0.004, "low"),
    "deepseek-ai/deepseek-v4-flash": (0.00025, "none"),
    "moonshotai/kimi-k2.7-code": (0.0035, "high"),
    "moonshotai/kimi-k3": (0.0125, "low"),
    "motif-technologies/motif-3": (0.002, "none"),
    "qwen/qwen3.8-27b": (0.003, "none"),
}

INPUT_USD_PER_1K = {
    "zai-org/glm-5.3": 0.001,
    "deepseek-ai/deepseek-v4-flash": 0.00015,
    "moonshotai/kimi-k2.7-code": 0.00075,
    "moonshotai/kimi-k3": 0.003,
    "motif-technologies/motif-3": 0.0005,
    "qwen/qwen3.8-27b": 0.0004,
}

BUDGET_CAP_USD = 70.0
WORKERS_PER_MODEL = 6
TIMEOUT_SECS = 600
MAX_RETRIES = 6

# Models with mandatory reasoning that burns the token cap before content
REASONING_MODELS = {"zai-org/glm-5.3", "moonshotai/kimi-k2.7-code", "moonshotai/kimi-k3"}


def load_api_key():
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line.startswith("AIAND_API_TEST_KEY="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("AIAND_API_TEST_KEY not found in " + ENV_FILE)


class Spend:
    """Thread-safe cumulative spend tracker with worst-case projection."""

    def __init__(self, remaining_by_key):
        # remaining_by_key: {(tier, model): (remaining_calls, max_tokens)}
        self.lock = threading.Lock()
        self.spent_usd = 0.0
        self.remaining = dict(remaining_by_key)

    def record_and_consume(self, tier, model, prompt_tokens, completion_tokens):
        out_price = MODELS[model][0] / 1000.0
        in_price = INPUT_USD_PER_1K[model] / 1000.0
        with self.lock:
            self.spent_usd += prompt_tokens * in_price + completion_tokens * out_price
            rem = self.remaining.get((tier, model))
            if rem:
                self.remaining[(tier, model)] = (max(0, rem[0] - 1), rem[1])
            proj = sum(n * mt * (MODELS[m][0] / 1000.0) for (t, m), (n, mt) in self.remaining.items())
            return self.spent_usd, proj


def sse_stream_call(api_key, model, effort, prompt, max_tokens, tools=None):
    """One streamed chat completion. Returns (text, finish_reason, usage|None)."""
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if effort:
        body["reasoning_effort"] = effort
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        API_BASE + "/chat/completions",
        data=data,
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            # Cloudflare fronts the API and 403s urllib's default "Python-urllib" UA
            "User-Agent": "cluster-measurement/0.79",
        },
        method="POST",
    )
    text_parts = []
    tool_parts = []
    finish_reason = None
    usage = None
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECS) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if chunk.get("usage"):
                usage = chunk["usage"]
            for choice in chunk.get("choices", []):
                delta = choice.get("delta") or {}
                if delta.get("content"):
                    text_parts.append(delta["content"])
                # Accumulate streamed tool-call fragments (BFCL rows): the
                # API may answer with tool_calls instead of content. Fragments
                # share an index; arguments arrive as incremental strings.
                for tc in delta.get("tool_calls") or []:
                    while len(tool_parts) <= tc.get("index", 0):
                        tool_parts.append({"id": "", "name": "", "args": []})
                    slot = tool_parts[tc["index"]]
                    if tc.get("id"):
                        slot["id"] += tc["id"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        slot["name"] += fn["name"]
                    if fn.get("arguments"):
                        slot["args"].append(fn["arguments"])
                if choice.get("finish_reason"):
                    finish_reason = choice["finish_reason"]
    tool_calls = None
    if tool_parts:
        tool_calls = [
            {"name": t["name"], "arguments": "".join(t["args"])}
            for t in tool_parts if t["name"] or t["args"]
        ]
    # Tool-call answers replace content for grading; keep both in the record.
    text = "".join(text_parts)
    if tool_calls:
        text = json.dumps(tool_calls)
    return text, finish_reason, usage


def call_with_retry(api_key, model, effort, prompt, max_tokens, tools=None):
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            return sse_stream_call(api_key, model, effort, prompt, max_tokens, tools=tools)
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}: {e.read(200).decode('utf-8', 'replace')}"
            if e.code == 429 or e.code >= 500:
                time.sleep(min(60, 2 ** attempt * 2))
                continue
            raise RuntimeError(last_err)
        except Exception as e:  # transport errors: retry
            last_err = repr(e)
            time.sleep(min(60, 2 ** attempt * 2))
    raise RuntimeError(f"retries exhausted: {last_err}")


def model_file(model):
    """Slug for response file names: moonshotai/kimi-k3 -> moonshotai_kimi-k3."""
    return model.replace("/", "_")


def load_done_ids(path):
    done = set()
    if not os.path.exists(path):
        return done
    with open(path) as f:
        for line in f:
            try:
                done.add(json.loads(line)["id"])
            except Exception:
                continue
    return done


def run_tier(tier, api_key, spend, only_model=None):
    matrix_path = f"{MEAS_DIR}/matrices/{tier}.jsonl"
    if not os.path.exists(matrix_path):
        print(f"[{tier}] matrix missing, skipping")
        return
    rows = []
    with open(matrix_path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    out_dir = f"{MEAS_DIR}/responses/{tier}"
    os.makedirs(out_dir, exist_ok=True)

    for model, (_, effort) in MODELS.items():
        if only_model and model != only_model:
            continue
        out_path = f"{out_dir}/{model_file(model)}.jsonl"
        done = load_done_ids(out_path)
        pending = [r for r in rows if r["id"] not in done]
        print(f"[{tier}] {model}: {len(pending)} to run ({len(done)} already done)", flush=True)
        if not pending:
            continue

        write_lock = threading.Lock()

        def work(row):
            try:
                tools = (row.get("scoring") or {}).get("functions")
                if tools:
                    # The API requires OpenAI's wrapper shape; BFCL's raw
                    # function objects are rejected with HTTP 400.
                    tools = [{"type": "function", "function": f} for f in tools]
                cap = row["max_tokens"]
                if model in REASONING_MODELS and tier == "hard":
                    # Reasoning models burn the entire cap on invisible reasoning
                    # tokens at hard-tier caps (root-measured: 6000 reasoning, 0
                    # content); raise the cap so they can emit an answer.
                    cap = max(cap, 6000)
                text, finish, usage = call_with_retry(api_key, model, effort, row["prompt"], cap, tools=tools)
                completion_tokens = usage.get("completion_tokens") if usage else None
                if completion_tokens is None:
                    completion_tokens = max(1, math.ceil(len(text) / 4))
                prompt_tokens = usage.get("prompt_tokens") if usage else math.ceil(len(row["prompt"]) / 4)
                rec = {
                    "id": row["id"],
                    "model": model,
                    "prompt_id": row["id"],
                    "max_tokens": cap,
                    "response_text": text,
                    "finish_reason": finish,
                    "usage": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                    },
                    "error": None,
                }
            except Exception as e:
                rec = {
                    "id": row["id"],
                    "model": model,
                    "prompt_id": row["id"],
                    "max_tokens": cap,
                    "response_text": "",
                    "finish_reason": None,
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0},
                    "error": str(e)[:500],
                }
            with open(out_path, "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            spent, proj = spend.record_and_consume(tier, model, rec["usage"]["prompt_tokens"], rec["usage"]["completion_tokens"])
            return rec, spent, proj

        with ThreadPoolExecutor(max_workers=WORKERS_PER_MODEL) as pool:
            for rec, spent, proj in pool.map(work, pending):
                if rec["error"]:
                    print(f"  [{tier}] {model} {rec['id']}: ERROR {rec['error'][:120]}", flush=True)
                if proj + spent > BUDGET_CAP_USD:
                    print(
                        f"BUDGET GUARD: spent ${spent:.2f}, projected remaining ${proj:.2f} "
                        f"-> total ${spent + proj:.2f} exceeds ${BUDGET_CAP_USD:.0f}. Pausing.",
                        flush=True,
                    )
                    pool.shutdown(wait=False, cancel_futures=True)
                    return


def dry_run(api_key):
    for model, (_, effort) in MODELS.items():
        try:
            text, finish, usage = sse_stream_call(api_key, model, effort, "Say OK.", 1)
            print(f"{model}: OK finish={finish} usage={usage} text={text[:40]!r}", flush=True)
        except Exception as e:
            print(f"{model}: FAIL {e}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", choices=TIERS)
    ap.add_argument("--model")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    api_key = load_api_key()

    if args.dry_run:
        dry_run(api_key)
        return

    tiers = [args.tier] if args.tier else TIERS
    remaining = {}
    for tier in tiers:
        path = f"{MEAS_DIR}/matrices/{tier}.jsonl"
        if not os.path.exists(path):
            continue
        with open(path) as f:
            rows = [json.loads(l) for l in f if l.strip()]
        done_any = 0
        for model in MODELS:
            done = load_done_ids(f"{MEAS_DIR}/responses/{tier}/{model_file(model)}.jsonl")
            remaining[(tier, model)] = (max(0, len(rows) - len(done)), max((r["max_tokens"] for r in rows), default=0))
            done_any += len(done)
    # Startup worst-case projection
    proj = sum(n * mt * (MODELS[m][0] / 1000.0) for (t, m), (n, mt) in remaining.items())
    print(f"Startup worst-case projected output spend (all calls at max_tokens): ${proj:.2f}", flush=True)

    spend = Spend(remaining)
    for tier in tiers:
        run_tier(tier, api_key, spend, only_model=args.model)
    print(f"Done. Total spend: ${spend.spent_usd:.2f}", flush=True)


if __name__ == "__main__":
    main()
