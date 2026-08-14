"""Opt-in offline teacher / gold / fit. Refuses unless AIAND_TRAIN=1."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

import httpx

from .cache import RequestCache, request_cache_key
from .provider import HttpAiandProvider
from .router import (
    SpendLog,
    estimate_cost,
    estimate_tokens,
    load_config,
    load_models,
    Model,
)
from .scorer import BINS, featurize

_TEACHER_SYS = (
    "Label this coding-agent request for a model router. Do not solve the task. "
    "complexity_bin must be one of trivial, standard, hard, frontier. "
    "trivial=rename/typo/lookup; standard=localized implement/fix; "
    "hard=multi-file/ambiguous/debug; frontier=novel/huge/adversarial. "
    "p_success maps each catalog model id to P(that model would succeed) in [0,1]. "
    "Catalog ids: {ids}. label_confidence in [0,1]."
)

OPT_IN_ENV = "AIAND_TRAIN"
CHEAP_TEACHER = "motif-technologies/motif-3"
ESCALATE_TEACHER = "zai-org/glm-5.2"
BINS = {"trivial", "standard", "hard", "frontier"}
EXCLUDED_PREFIXES = ("qwen/", "moonshotai/", "deepseek-ai/")
TEACHER_LIMIT = 1000
SPARSE_LIMIT = 200
DENSE_LIMIT = 100
MEASURED_TRIO = (
    "qwen/qwen3.6-27b",
    "moonshotai/kimi-k2.7-code",
    "deepseek-ai/deepseek-v4-pro",
)
FLASH = "deepseek-ai/deepseek-v4-flash"
K3 = "moonshotai/kimi-k3"

_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "teacher_label",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "complexity_bin": {"type": "string", "enum": sorted(BINS)},
                "label_confidence": {"type": "number"},
                "p_success": {"type": "object", "additionalProperties": {"type": "number"}},
                "bloom_level": {"type": "integer"},
            },
            "required": ["complexity_bin", "p_success"],
            "additionalProperties": False,
        },
    },
}


def _refuse() -> int:
    print(
        f"refusing: set {OPT_IN_ENV}=1 to run paid teacher/gold/fit. Not for CI.",
        file=sys.stderr,
    )
    return 2


def _read_queries(path: Path, limit: int) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
        if len(rows) >= limit:
            break
    return rows


def _messages(row: dict[str, Any]) -> list[dict[str, Any]]:
    if row.get("messages"):
        return list(row["messages"])
    return [{"role": "user", "content": str(row.get("prompt") or "")}]


def _parse_label(payload: dict[str, Any]) -> dict[str, Any] | None:
    message = (((payload.get("json") or {}).get("choices") or [{}])[0].get("message") or {})
    raw = message.get("content")
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    bin_ = data.get("complexity_bin")
    pmap = data.get("p_success")
    if bin_ not in BINS or not isinstance(pmap, dict):
        return None
    out = {
        "complexity_bin": bin_,
        "label_confidence": float(data.get("label_confidence") or 0),
        "p_success": {k: float(v) for k, v in pmap.items()},
    }
    if "bloom_level" in data:
        out["bloom_level"] = data["bloom_level"]
    return out


async def _complete(
    provider: Any,
    body: dict[str, Any],
    *,
    cache: RequestCache,
    spend: SpendLog,
    models_by_id: dict[str, Model],
) -> dict[str, Any]:
    ck = request_cache_key(body, body["model"])
    hit = cache.get(ck)
    if hit is not None:
        return {"status": 200, "json": hit, "cache_hit": True}
    if spend.total() >= spend.limit_usd:
        return {"status": 429, "json": {"error": {"message": "budget"}}}
    try:
        result = await provider.complete(body)
    except httpx.TimeoutException:
        return {"status": 408, "json": {"error": {"message": "upstream timeout"}}}
    payload = result.get("json") or {}
    usage = payload.get("usage") or {}
    model = models_by_id.get(body["model"])
    if model is not None:
        spend.add(
            estimate_cost(
                model,
                int(usage.get("prompt_tokens") or 0),
                int(usage.get("completion_tokens") or 0),
            )
        )
    return result


async def _teacher_call(
    provider: Any,
    model_id: str,
    messages: list[dict[str, Any]],
    *,
    cache: RequestCache,
    spend: SpendLog,
    models_by_id: dict[str, Model],
) -> dict[str, Any] | None:
    ids = ", ".join(sorted(models_by_id))
    body = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": _TEACHER_SYS.format(ids=ids)},
            *messages,
        ],
        "temperature": 0,
        "response_format": _SCHEMA,
        "max_tokens": 512,
    }
    result = await _complete(provider, body, cache=cache, spend=spend, models_by_id=models_by_id)
    parsed = _parse_label(result)
    if parsed:
        cache.put(request_cache_key(body, body["model"]), result.get("json") or {})
        return parsed
    result = await _complete(provider, body, cache=cache, spend=spend, models_by_id=models_by_id)
    parsed = _parse_label(result)
    if parsed:
        cache.put(request_cache_key(body, body["model"]), result.get("json") or {})
    return parsed


async def run_teacher(
    queries: list[dict[str, Any]],
    out: Path,
    *,
    provider: Any,
    spend: SpendLog,
    cache: RequestCache,
    models_by_id: dict[str, Model],
) -> None:
    rows: list[dict[str, Any]] = []
    escalated = 0
    cap = max(1, int(len(queries) * 0.25))
    if any(tid.startswith(prefix) for tid in (CHEAP_TEACHER, ESCALATE_TEACHER) for prefix in EXCLUDED_PREFIXES):
        raise ValueError("teacher ids must exclude measured-trio and fallback providers")
    for q in queries:
        messages = _messages(q)
        label = await _teacher_call(
            provider, CHEAP_TEACHER, messages, cache=cache, spend=spend, models_by_id=models_by_id
        )
        parse_fail = label is None
        needs_esc = True
        if label is not None:
            needs_esc = (
                label["complexity_bin"] in {"hard", "frontier"}
                or float(label["label_confidence"]) < 0.60
            )
        # parse-fail always escalates; 25% cap is quality-only (hard/frontier / low confidence)
        if needs_esc and (parse_fail or escalated < cap):
            esc = await _teacher_call(
                provider, ESCALATE_TEACHER, messages, cache=cache, spend=spend, models_by_id=models_by_id
            )
            if not parse_fail:
                escalated += 1
            if esc:
                label = esc
        if not label:
            rows.append({"prompt": _prompt_of(messages), "unlabeled": True})
            if spend.total() >= spend.limit_usd:
                break
            continue
        row = {
            "prompt": _prompt_of(messages),
            "complexity_bin": label["complexity_bin"],
            "p_success": label["p_success"],
            "teacher": CHEAP_TEACHER,
            "tokens": estimate_tokens(messages),
            "needs_tools": bool(q.get("needs_tools")),
            "phase": str(q.get("phase") or "plan"),
        }
        if "bloom_level" in label:
            row["bloom_level"] = label["bloom_level"]
        rows.append(row)
        if len(rows) % 10 == 0:
            print(
                f"teacher {len(rows)}/{len(queries)} spend={spend.total():.4f}",
                flush=True,
            )
    labeled = sum(1 for r in rows if not r.get("unlabeled"))
    print(
        f"teacher done labeled={labeled} unlabeled={len(rows) - labeled} "
        f"spend={spend.total():.4f} -> {out}",
        flush=True,
    )
    out.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


SPARSE_ANCHORS = (FLASH, *MEASURED_TRIO)


async def run_gold(
    queries: list[dict[str, Any]],
    out: Path,
    *,
    provider: Any,
    spend: SpendLog,
    cache: RequestCache,
    models_by_id: dict[str, Model],
    dense: bool = False,
) -> None:
    ids = list(SPARSE_ANCHORS)
    if dense:
        ids = [i for i in models_by_id if i != K3 and models_by_id[i].enabled]
    rows = []
    for q in queries:
        messages = _messages(q)
        for model_id in ids:
            if model_id not in models_by_id or model_id == K3:
                continue
            body = {"model": model_id, "messages": messages, "max_tokens": 512, "temperature": 0}
            result = await _complete(
                provider, body, cache=cache, spend=spend, models_by_id=models_by_id
            )
            if result.get("status") == 429:
                break
            if result.get("status", 200) < 400 and result.get("json"):
                cache.put(request_cache_key(body, model_id), result["json"])
            status = result.get("status", 200)
            message = (((result.get("json") or {}).get("choices") or [{}])[0].get("message") or {})
            success = status < 400 and bool(message.get("content") or message.get("tool_calls"))
            rows.append(
                {
                    "prompt": _prompt_of(messages),
                    "model_id": model_id,
                    "success": success,
                    "unobserved": False,
                    "tokens": estimate_tokens(messages),
                    "needs_tools": bool(q.get("needs_tools")),
                    "phase": str(q.get("phase") or "plan"),
                }
            )
            if spend.total() >= spend.limit_usd:
                break
        if spend.total() >= spend.limit_usd:
            break
        if len(rows) % 20 == 0:
            print(f"gold {len(rows)} cells spend={spend.total():.4f}", flush=True)
    print(f"gold done cells={len(rows)} spend={spend.total():.4f} -> {out}", flush=True)
    out.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _prompt_of(messages: list[dict[str, Any]]) -> str:
    last = messages[-1] if messages else {}
    content = last.get("content")
    return content if isinstance(content, str) else str(content or "")


def _row_x(row: dict[str, Any]) -> list[float]:
    messages = row.get("messages") or [{"role": "user", "content": row.get("prompt") or ""}]
    tokens = int(row.get("tokens") or estimate_tokens(messages))
    return featurize(str(row.get("phase") or "plan"), bool(row.get("needs_tools")), tokens)


def _fit_binary(xs: list[list[float]], ys: list[float], steps: int = 80, lr: float = 0.35) -> list[float]:
    dim = len(xs[0])
    w = [0.0] * dim
    n = max(1, len(xs))
    for _ in range(steps):
        grad = [0.0] * dim
        for x, y in zip(xs, ys):
            z = sum(w[i] * x[i] for i in range(dim))
            z = max(-30.0, min(30.0, z))
            err = (1.0 / (1.0 + math.exp(-z))) - y
            for i in range(dim):
                grad[i] += err * x[i]
        for i in range(dim):
            w[i] -= lr * grad[i] / n
    return w


def _fit_platt(zs: list[float], ys: list[float]) -> tuple[float, float]:
    if len(zs) < 2:
        return 1.0, 0.0
    a, b = 1.0, 0.0
    n = len(zs)
    for _ in range(60):
        ga = gb = 0.0
        for z, y in zip(zs, ys):
            p = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, a * z + b))))
            err = p - y
            ga += err * z
            gb += err
        a -= 0.2 * ga / n
        b -= 0.2 * gb / n
    return a, b


def fit_scorer(gold_path: Path, silver_path: Path | None, out: Path) -> None:
    gold = [
        json.loads(line)
        for line in gold_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    silver = []
    if silver_path and silver_path.exists():
        silver = [
            json.loads(line)
            for line in silver_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    gold_cells = {(str(r.get("prompt")), r["model_id"]) for r in gold if not r.get("unobserved") and "model_id" in r}
    gold_ids = {mid for _, mid in gold_cells}
    by_model_x: dict[str, list[list[float]]] = {mid: [] for mid in gold_ids}
    by_model_y: dict[str, list[float]] = {mid: [] for mid in gold_ids}
    for row in gold:
        if row.get("unobserved") or "model_id" not in row:
            continue
        mid = row["model_id"]
        by_model_x[mid].append(_row_x(row))
        by_model_y[mid].append(1.0 if row.get("success") else 0.0)
    for row in silver:
        if row.get("unlabeled"):
            continue
        x = _row_x(row)
        prompt = str(row.get("prompt") or "")
        for mid, p in (row.get("p_success") or {}).items():
            if mid not in gold_ids:
                continue
            if (prompt, mid) in gold_cells:
                continue
            by_model_x[mid].append(x)
            by_model_y[mid].append(float(p))
    weights = {}
    zs_all: list[float] = []
    ys_all: list[float] = []
    for mid, xs in by_model_x.items():
        if not xs:
            continue
        w = _fit_binary(xs, by_model_y[mid])
        weights[mid] = w
        n_gold = sum(1 for r in gold if r.get("model_id") == mid and not r.get("unobserved"))
        for x, y in zip(xs[:n_gold], by_model_y[mid][:n_gold]):
            zs_all.append(sum(w[i] * x[i] for i in range(len(w))))
            ys_all.append(y)
    a, b = _fit_platt(zs_all, ys_all)
    bin_xs: list[list[float]] = []
    bin_ys: dict[str, list[float]] = {bn: [] for bn in BINS}
    for row in silver:
        if row.get("unlabeled") or row.get("complexity_bin") not in BINS:
            continue
        x = _row_x(row)
        bin_xs.append(x)
        for bn in BINS:
            bin_ys[bn].append(1.0 if row["complexity_bin"] == bn else 0.0)
    bin_weights = {bn: _fit_binary(bin_xs, bin_ys[bn]) for bn in BINS} if bin_xs else {}
    p_success = {}
    for mid in gold_ids:
        gold_ys = [
            1.0 if r.get("success") else 0.0
            for r in gold
            if r.get("model_id") == mid and not r.get("unobserved")
        ]
        if gold_ys:
            p_success[mid] = sum(gold_ys) / len(gold_ys)
    bins = [str(r.get("complexity_bin")) for r in silver if r.get("complexity_bin") in BINS]
    bin_ = max(set(bins), key=bins.count) if bins else "standard"
    artifact = {
        "not_spec_floors": True,
        "complexity_bin": bin_,
        "p_success": p_success,
        "weights": weights,
        "bin_weights": bin_weights,
        "platt": {"a": a, "b": b},
        "n_gold": len(gold),
        "n_silver": len(silver),
    }
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")


def main(
    argv: list[str] | None = None,
    *,
    provider: Any | None = None,
    spend: SpendLog | None = None,
    cache_dir: Path | None = None,
    models_path: Path | None = None,
) -> int:
    if os.getenv(OPT_IN_ENV) != "1":
        return _refuse()
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("teacher")
    t.add_argument("--queries", required=True)
    t.add_argument("--out", required=True)
    t.add_argument("--limit", type=int, default=TEACHER_LIMIT)
    g = sub.add_parser("gold")
    g.add_argument("--queries", required=True)
    g.add_argument("--out", required=True)
    g.add_argument("--limit", type=int, default=None)
    g.add_argument("--dense", action="store_true")
    f = sub.add_parser("fit")
    f.add_argument("--gold", required=True)
    f.add_argument("--silver")
    f.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[2]
    cfg = load_config(models_path or root / "config" / "models.yaml")
    models = load_models(cfg)
    by_id = {m.id: m for m in models}
    spend_log = spend or SpendLog(root / "data" / "spend.txt", float(os.getenv("BUDGET_LIMIT_USD", "15")))
    cache = RequestCache(cache_dir or root / "data" / "cache")
    key = os.getenv("AIAND_API_KEY", "")
    base = os.getenv("AIAND_BASE_URL", "https://api.aiand.com/v1")
    upstream = provider or HttpAiandProvider(base, key)

    if args.cmd == "fit":
        fit_scorer(Path(args.gold), Path(args.silver) if args.silver else None, Path(args.out))
        return 0
    if args.cmd == "gold":
        limit = args.limit if args.limit is not None else (DENSE_LIMIT if args.dense else SPARSE_LIMIT)
    else:
        limit = args.limit
    queries = _read_queries(Path(args.queries), limit)
    if args.cmd == "teacher":
        asyncio.run(
            run_teacher(
                queries,
                Path(args.out),
                provider=upstream,
                spend=spend_log,
                cache=cache,
                models_by_id=by_id,
            )
        )
        return 0
    asyncio.run(
        run_gold(
            queries,
            Path(args.out),
            provider=upstream,
            spend=spend_log,
            cache=cache,
            models_by_id=by_id,
            dense=bool(getattr(args, "dense", False)),
        )
    )
    return 0


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    raise SystemExit(main())
