"""Opt-in offline teacher / gold / fit. Refuses unless AIAND_TRAIN=1."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

from .cache import RequestCache, request_cache_key
from .provider import HttpAiandProvider
from .pool import (
    MANIFEST_VALID_SPLITS,
    load_split_manifest,
    run_pool,
    sample_stratum,
    validate_split_manifest,
)
from .router import (
    SpendLog,
    eligible_models,
    estimate_cost,
    estimate_tokens,
    load_config,
    load_models,
    Model,
    select_model,
)
from .scorer import (
    BINS,
    load_scorer,
    pick_cheapest_above_bar,
    score_eligible,
)
from .fit import GEOMETRY_OVERRIDE_ENV, _geometry_gate, _jsonl_rows, fit_scorer
from .gold_label import _gold_label

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
TEACHER_LIMIT = 1000
SPARSE_LIMIT = 400
DENSE_LIMIT = 100
MEASURED_TRIO = (
    "qwen/qwen3.6-27b",
    "moonshotai/kimi-k2.7-code",
    "deepseek-ai/deepseek-v4-pro",
)
FLASH = "deepseek-ai/deepseek-v4-flash"
K3 = "moonshotai/kimi-k3"
TEACHER_LADDER = [FLASH, CHEAP_TEACHER, ESCALATE_TEACHER, K3]
# Catalog min published effort (GET /v1/models). Omit → upstream default (Qwen defaults high).
MIN_REASONING_EFFORT = {
    FLASH: "none",
    "qwen/qwen3.6-27b": "none",
    "deepseek-ai/deepseek-v4-pro": "none",
    "google/gemma-4-31b-it": "none",
    ESCALATE_TEACHER: "none",
    CHEAP_TEACHER: "low",
    "openai/gpt-oss-120b": "low",
    # high = catalog min; pair with GOLD_REASONING_MAX_TOKENS so content can finish after reasoning.
    "moonshotai/kimi-k2.7-code": "high",
    K3: "low",
}
GOLD_MAX_TOKENS = 1024
GOLD_REASONING_MAX_TOKENS = 4096

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


def _read_queries(
    path: Path,
    limit: int,
    exclude: set[str] | None = None,
    exclude_ids: set[str] | None = None,
    seed: int = 0,
) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    if exclude or exclude_ids:
        blocked_p = exclude or set()
        blocked_i = {x.lower() for x in (exclude_ids or set()) if x}
        filtered = []
        for q in rows:
            if _prompt_of(_messages(q)) in blocked_p:
                continue
            iid = str(q.get("instance_id") or "").lower()
            if iid and iid in blocked_i:
                continue
            filtered.append(q)
        rows = filtered
    if limit >= len(rows):
        return rows
    return sample_stratum(rows, limit, seed=seed)


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
        lock = getattr(spend, "_async_lock", None)
        if lock is None:
            lock = asyncio.Lock()
            spend._async_lock = lock
        async with lock:
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
    max_completion_tokens: int = 1024,
) -> dict[str, Any] | None:
    ids = ", ".join(sorted(models_by_id))
    body: dict[str, Any] = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": _TEACHER_SYS.format(ids=ids)},
            *messages,
        ],
        "temperature": 0,
        "response_format": _SCHEMA,
        "max_completion_tokens": max_completion_tokens,
    }
    effort = MIN_REASONING_EFFORT.get(model_id)
    if effort:
        body["reasoning_effort"] = effort
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


def _concurrency() -> int:
    return max(1, int(os.getenv("TRAIN_CONCURRENCY", "16")))


async def run_teacher(
    queries: list[dict[str, Any]],
    out: Path,
    *,
    provider: Any,
    spend: SpendLog,
    cache: RequestCache,
    models_by_id: dict[str, Model],
) -> None:
    spend._async_lock = asyncio.Lock()
    sem = asyncio.Semaphore(_concurrency())
    existing: list[dict[str, Any]] = []
    labeled_prompts: set[str] = set()
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
                if not r.get("unlabeled"):
                    existing.append(r)
                    labeled_prompts.add(r.get("prompt", ""))
            except json.JSONDecodeError:
                pass
    pending = [q for q in queries if _prompt_of(_messages(q)) not in labeled_prompts]
    if not pending:
        print(f"teacher: all {len(queries)} queries already labeled, skipping", flush=True)
        return
    print(f"teacher: {len(pending)}/{len(queries)} pending ({len(existing)} cached)", flush=True)

    async def one(q: dict[str, Any]) -> dict[str, Any]:
        async with sem:
            messages = _messages(q)
            label = None
            teacher_used = None
            for tier_model in TEACHER_LADDER:
                tier_label = await _teacher_call(
                    provider, tier_model, messages, cache=cache, spend=spend, models_by_id=models_by_id
                )
                if tier_label is not None:
                    teacher_used = tier_model
                    confidence = float(tier_label["label_confidence"])
                    complexity = tier_label["complexity_bin"]
                    if confidence >= 0.60 and complexity not in {"hard", "frontier"}:
                        label = tier_label
                        break
                    if tier_model == TEACHER_LADDER[-1]:
                        label = tier_label
                        break
                    label = tier_label
            if not label:
                return {"prompt": _prompt_of(messages), "unlabeled": True}
            row = {
                "prompt": _prompt_of(messages),
                "complexity_bin": label["complexity_bin"],
                "p_success": label["p_success"],
                "teacher": teacher_used or TEACHER_LADDER[0],
                "tokens": estimate_tokens(messages),
                "needs_tools": bool(q.get("needs_tools")),
                "phase": str(q.get("phase") or "plan"),
                "hint_bin": str(q.get("hint_bin") or "standard"),
            }
            if "bloom_level" in label:
                row["bloom_level"] = label["bloom_level"]
            return row

    rows: list[dict[str, Any]] = list(existing)
    for coro in asyncio.as_completed([one(q) for q in pending]):
        rows.append(await coro)
        if (len(rows) - len(existing)) % 10 == 0:
            out.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
            print(
                f"teacher {len(rows) - len(existing)}/{len(pending)} total={len(rows)} spend={spend.total():.4f}",
                flush=True,
            )
    labeled = sum(1 for r in rows if not r.get("unlabeled"))
    print(
        f"teacher done labeled={labeled} unlabeled={len(rows) - labeled} "
        f"spend={spend.total():.4f} -> {out}",
        flush=True,
    )
    # GLM salvage for parse failures (Motif truncation etc.)
    by_prompt = {_prompt_of(_messages(q)): q for q in queries}
    salvaged = 0
    for i, row in enumerate(rows):
        if not row.get("unlabeled"):
            continue
        q = by_prompt.get(row["prompt"])
        if not q:
            continue
        label = await _teacher_call(
            provider,
            ESCALATE_TEACHER,
            _messages(q),
            cache=cache,
            spend=spend,
            models_by_id=models_by_id,
        )
        if not label:
            continue
        rows[i] = {
            "prompt": row["prompt"],
            "complexity_bin": label["complexity_bin"],
            "p_success": label["p_success"],
            "teacher": ESCALATE_TEACHER,
            "tokens": estimate_tokens(_messages(q)),
            "needs_tools": bool(q.get("needs_tools")),
            "phase": str(q.get("phase") or "plan"),
            "hint_bin": str(q.get("hint_bin") or "standard"),
        }
        salvaged += 1
    if salvaged:
        labeled = sum(1 for r in rows if not r.get("unlabeled"))
        print(f"teacher salvage +{salvaged} labeled={labeled} spend={spend.total():.4f}", flush=True)
    out.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


SPARSE_ANCHORS = (FLASH, *MEASURED_TRIO)


def _gold_ids(
    q: dict[str, Any], models_by_id: dict[str, Model], *, dense: bool, include_k3: bool = False
) -> list[str]:
    if include_k3:
        m = models_by_id.get(K3)
        if m is None or not m.enabled:
            return []
        if q.get("needs_tools") and not m.supports_tools:
            return []
        return [K3]
    ids = list(SPARSE_ANCHORS)
    if dense:
        ids = [i for i in models_by_id if i != K3 and models_by_id[i].enabled]
    out = []
    for model_id in ids:
        m = models_by_id.get(model_id)
        if m is None or not m.enabled or model_id == K3:
            continue
        if q.get("needs_tools") and not m.supports_tools:
            continue
        out.append(model_id)
    return out


def _gold_body(
    model_id: str, messages: list[dict[str, Any]], *, needs_tools: bool = False
) -> dict[str, Any]:
    effort = MIN_REASONING_EFFORT.get(model_id)
    max_tokens = GOLD_REASONING_MAX_TOKENS if effort and effort != "none" else GOLD_MAX_TOKENS
    body: dict[str, Any] = {
        "model": model_id,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0,
    }
    if effort:
        body["reasoning_effort"] = effort
    if needs_tools:
        body["tools"] = [{"type": "function", "function": {"name": "read", "parameters": {}}}]
    return body




async def run_gold(
    queries: list[dict[str, Any]],
    out: Path,
    *,
    provider: Any,
    spend: SpendLog,
    cache: RequestCache,
    models_by_id: dict[str, Model],
    dense: bool = False,
    include_k3: bool = False,
) -> None:
    jobs: list[tuple[list[dict[str, Any]], str, dict[str, Any]]] = []
    for q in queries:
        messages = _messages(q)
        for model_id in _gold_ids(q, models_by_id, dense=dense, include_k3=include_k3):
            jobs.append((messages, model_id, q))
    spend._async_lock = asyncio.Lock()
    sem = asyncio.Semaphore(_concurrency())

    async def one(
        messages: list[dict[str, Any]], model_id: str, q: dict[str, Any]
    ) -> dict[str, Any]:
        async with sem:
            body = _gold_body(model_id, messages, needs_tools=bool(q.get("needs_tools")))
            result = await _complete(
                provider, body, cache=cache, spend=spend, models_by_id=models_by_id
            )
            status = result.get("status", 200)
            if status == 429:
                row = {
                    "prompt": _prompt_of(messages),
                    "model_id": model_id,
                    "unobserved": True,
                    "tokens": estimate_tokens(messages),
                    "needs_tools": bool(q.get("needs_tools")),
                    "phase": str(q.get("phase") or "plan"),
                    "hint_bin": str(q.get("hint_bin") or "standard"),
                }
                if dense:
                    row["dense"] = True
                if q.get("instance_id"):
                    row["instance_id"] = q["instance_id"]
                return row
            if status < 400 and result.get("json"):
                cache.put(request_cache_key(body, model_id), result["json"])
            choice = ((result.get("json") or {}).get("choices") or [{}])[0]
            message = choice.get("message") or {}
            success, tier = _gold_label(message, _prompt_of(messages), choice, meta=q)
            success = status < 400 and success
            row = {
                "prompt": _prompt_of(messages),
                "model_id": model_id,
                "success": success,
                "success_tier": tier,
                "unobserved": False,
                "tokens": estimate_tokens(messages),
                "needs_tools": bool(q.get("needs_tools")),
                "phase": str(q.get("phase") or "plan"),
                "hint_bin": str(q.get("hint_bin") or "standard"),
            }
            if dense:
                row["dense"] = True
            if q.get("instance_id"):
                row["instance_id"] = q["instance_id"]
            return row

    rows: list[dict[str, Any]] = []
    for coro in asyncio.as_completed([one(*j) for j in jobs]):
        rows.append(await coro)
        if len(rows) % 20 == 0:
            out.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
            print(f"gold {len(rows)} cells spend={spend.total():.4f}", flush=True)
    print(f"gold done cells={len(rows)} spend={spend.total():.4f} -> {out}", flush=True)
    out.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _prompt_of(messages: list[dict[str, Any]]) -> str:
    last = messages[-1] if messages else {}
    content = last.get("content")
    return content if isinstance(content, str) else str(content or "")


def _prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]


def _manifest_prompt_of_row(row: dict[str, Any]) -> str:
    return _prompt_of(_messages(row))


def _load_manifest_map(manifest_path: Path | None = None) -> dict[str, str]:
    p = Path(manifest_path) if manifest_path else Path("data/split_manifest.json")
    data = load_split_manifest(p)
    return validate_split_manifest(data)


def _resolve_manifest_path(
    queries_path: Path | None, manifest_path: Path | None
) -> Path | None:
    """Explicit path wins; else the manifest beside the queries file; else repo default.

    Ad-hoc query files away from data/ have no pool manifest — strict
    pool-disjointness does not apply to them (intra-batch duplicates still do).
    """
    if manifest_path is not None:
        return manifest_path
    if queries_path is not None:
        sibling = queries_path.parent / "split_manifest.json"
        return sibling if sibling.exists() else None
    default = Path("data/split_manifest.json")
    return default if default.exists() else None


def _guard_manifest_for_queries(
    queries: list[dict[str, Any]],
    *,
    allowed_splits: set[str] | None = None,
    manifest_path: Path | None = None,
    queries_path: Path | None = None,
) -> None:
    p = _resolve_manifest_path(queries_path, manifest_path)
    m = _load_manifest_map(p) if p is not None else None
    if m is None:
        print(
            "split_manifest_overlap: no split manifest beside "
            f"{queries_path}; pool-disjointness guard limited to duplicate ids",
            flush=True,
        )
    seen: set[str] = set()
    for q in queries:
        prompt = _manifest_prompt_of_row(q)
        h = _prompt_hash(prompt)
        if h in seen:
            raise ValueError(f"split_manifest_overlap: double-assigned query hash {h}")
        seen.add(h)
        if m is None:
            continue
        if h not in m:
            iid = q.get("instance_id") or q.get("id") or "?"
            raise ValueError(f"split_manifest_overlap: absent id {iid!r} hash {h}")
        if allowed_splits is not None and m[h] not in allowed_splits:
            raise ValueError(
                f"split_manifest_overlap: query hash {h} split {m[h]!r} not in allowed {allowed_splits}"
            )



def _query_map(queries_path: Path) -> dict[str, dict[str, Any]]:
    qmap: dict[str, dict[str, Any]] = {}
    paths = [queries_path, queries_path.parent / "verified-queries.jsonl"]
    for path in paths:
        if path.exists():
            for q in _read_queries(path, 10_000):
                qmap[_prompt_of(_messages(q))] = q
    return qmap


def relabel_gold(
    gold_path: Path,
    queries_path: Path,
    out: Path,
    *,
    cache: RequestCache,
    models_by_id: dict[str, Model],
) -> None:
    """Re-score gold success from cache using current _gold_success (no paid calls)."""
    qmap = _query_map(queries_path)
    rows = [
        json.loads(line)
        for line in gold_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    changed = 0
    for row in rows:
        if row.get("unobserved") or "model_id" not in row:
            continue
        q = qmap.get(row["prompt"], {})
        messages = _messages(q) if q else [{"role": "user", "content": row["prompt"]}]
        body = _gold_body(row["model_id"], messages, needs_tools=bool(q.get("needs_tools")))
        hit = cache.get(request_cache_key(body, row["model_id"]))
        if not hit:
            continue
        choice = (hit.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        ok, tier = _gold_label(message, row["prompt"], choice, meta=q)
        if ok != row.get("success") or tier != row.get("success_tier"):
            changed += 1
        row["success"] = ok
        row["success_tier"] = tier
    out.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    rate = sum(r["success"] for r in rows if not r.get("unobserved")) / max(
        1, sum(1 for r in rows if not r.get("unobserved"))
    )
    print(f"relabel changed={changed} success_rate={rate:.4f} -> {out}", flush=True)


async def run_salvage_silver(
    silver_path: Path,
    queries_path: Path,
    *,
    provider: Any,
    spend: SpendLog,
    cache: RequestCache,
    models_by_id: dict[str, Model],
) -> None:
    rows = [
        json.loads(line)
        for line in silver_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    qmap = {_prompt_of(_messages(q)): q for q in _read_queries(queries_path, 10_000)}
    spend._async_lock = asyncio.Lock()
    sem = asyncio.Semaphore(_concurrency())
    salvaged = 0

    async def one(i: int) -> None:
        nonlocal salvaged
        row = rows[i]
        if not row.get("unlabeled"):
            return
        q = qmap.get(row["prompt"])
        if not q:
            return
        async with sem:
            label = await _teacher_call(
                provider,
                ESCALATE_TEACHER,
                _messages(q),
                cache=cache,
                spend=spend,
                models_by_id=models_by_id,
                max_completion_tokens=2048,
            )
        if not label:
            return
        rows[i] = {
            "prompt": row["prompt"],
            "complexity_bin": label["complexity_bin"],
            "p_success": label["p_success"],
            "teacher": ESCALATE_TEACHER,
            "tokens": row.get("tokens") or estimate_tokens(_messages(q)),
            "needs_tools": bool(q.get("needs_tools")),
            "phase": str(q.get("phase") or "plan"),
            "hint_bin": str(q.get("hint_bin") or "standard"),
        }
        salvaged += 1

    await asyncio.gather(*[one(i) for i in range(len(rows))])
    silver_path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    labeled = sum(1 for r in rows if not r.get("unlabeled"))
    print(f"salvage +{salvaged} labeled={labeled} spend={spend.total():.4f}", flush=True)


def run_retune(
    dense_path: Path,
    scorer_path: Path | None = None,
    models_path: Path | None = None,
    init: str = "grid",
) -> str:
    """Search (threshold, max_regret) on a held-out tune split.

    Loads dense gold rows (n >= 300), runs a grid search over threshold
    [0, 1] step 0.01 and max_regret [0, 0.2] step 0.01, and picks the
    (t, r) that minimizes total list USD subject to:

        resolve_rate   >= rules_resolve_rate   - 0.01
        escalate_rate  >= rules_escalate_rate  - 0.01

    where escalate_rate = 1 - resolve_rate (trained pick failed or declined).

    Fits **medium only**; derives low/high/max via Pioneer offsets
    dt(-0.05, +0.10) / (+0.10, -0.05) / (+0.50, -0.17), clamped to [0, 1],
    then walked to restore t_low <= t_med <= t_high <= t_max and
    r_low >= r_med >= r_high >= r_max.

    Returns the ``trained_effort:`` YAML fragment, or ``"do-not-promote"``
    if no (t, r) satisfies the constraints.
    """
    rows = _jsonl_rows(dense_path)
    if len(rows) < 300:
        raise ValueError(f"tune split has {len(rows)} rows; need >= 300")

    root = Path(__file__).resolve().parents[2]
    cfg = load_config(models_path or root / "config" / "models.yaml")
    models = load_models(cfg)
    by_id = {m.id: m for m in models}

    scorer_file = scorer_path or Path(
        os.getenv("SCORER_PATH") or str(root / "data" / "scorer.json")
    )
    artifact = load_scorer(scorer_file)
    if artifact is None:
        return "do-not-promote"

    # Group rows by prompt -> per-query dense gold
    queries: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        prompt = str(row.get("prompt") or "")
        if not prompt:
            continue
        queries.setdefault(prompt, []).append(row)

    if not queries:
        return "do-not-promote"

    # Pre-compute per-query data (score_eligible is independent of t, r)
    per_query: list[dict[str, Any]] = []
    for prompt, qrows in queries.items():
        first = qrows[0]
        phase = str(first.get("phase") or "plan")
        needs_tools = bool(first.get("needs_tools"))
        tokens = int(first.get("tokens") or 500)

        gold: dict[str, bool] = {}
        for r in qrows:
            mid = r.get("model_id")
            if mid and mid in by_id:
                gold[mid] = bool(r.get("success"))

        if not gold:
            continue

        _, eligible = eligible_models(
            cfg,
            models,
            phase=phase,
            needs_tools=needs_tools,
            tokens=tokens,
            effort="medium",
            allowed=None,
            spend_usd=0.0,
            budget_usd=1e18,
        )
        eligible_ids = [m.id for m in eligible]

        eligible_gold = {mid: gold[mid] for mid in eligible_ids if mid in gold}
        if not eligible_gold:
            continue

        rules_decision = select_model(
            cfg,
            models,
            phase=phase,
            needs_tools=needs_tools,
            tokens=tokens,
            effort="medium",
            allowed=None,
            spend_usd=0.0,
            budget_usd=1e18,
        )
        rules_model_id = rules_decision.model.id
        rules_success = gold.get(rules_model_id, False)
        rules_cost = estimate_cost(rules_decision.model, tokens, 800)

        _, p_success = score_eligible(
            artifact,
            eligible_ids,
            phase=phase,
            needs_tools=needs_tools,
            tokens=tokens,
            text=prompt,
        )
        scored_eligible = [m for m in eligible if m.id in p_success]

        per_query.append(
            {
                "eligible": scored_eligible,
                "p_success": p_success,
                "gold": eligible_gold,
                "rules_success": rules_success,
                "rules_cost": rules_cost,
                "tokens": tokens,
            }
        )

    if not per_query:
        return "do-not-promote"

    n_queries = len(per_query)

    # Rules baseline
    rules_resolve = sum(1 for q in per_query if q["rules_success"]) / n_queries
    rules_escalate = 1.0 - rules_resolve

    if init not in ("grid", "quantile"):
        raise ValueError("init must be 'grid' or 'quantile'")
    if init == "quantile":
        vals = sorted(float(v) for v in (artifact.get("p_success") or {}).values())
        if vals:
            q_points = [vals[min(len(vals) - 1, int(round(q * (len(vals) - 1))))] for q in (0.1, 0.3, 0.5, 0.7, 0.9)]
            _quantile_init_thresholds = [max(0.0, min(1.0, float(v))) for v in q_points]
        else:
            _quantile_init_thresholds = [0.5]
        # Quantile initializes the search grid before exhaustive scan (exhaustive still covers [0,1] step 0.01).

    # Grid search: threshold [0, 1] step 0.01, max_regret [0, 0.2] step 0.01
    best_cost = float("inf")
    best_t: float | None = None
    best_r: float | None = None

    for t_i in range(101):
        t = t_i / 100.0
        for r_i in range(21):
            r = r_i / 100.0
            total_cost = 0.0
            n_resolve = 0

            for q in per_query:
                chosen, _ = pick_cheapest_above_bar(
                    q["eligible"],
                    q["p_success"],
                    threshold=t,
                    max_regret=r,
                )
                if chosen is None:
                    total_cost += q["rules_cost"]
                else:
                    total_cost += estimate_cost(chosen, q["tokens"], 800)
                    if q["gold"].get(chosen.id, False):
                        n_resolve += 1

            resolve_rate = n_resolve / n_queries
            escalate_rate = 1.0 - resolve_rate

            if resolve_rate < rules_resolve - 0.01:
                continue
            if escalate_rate < rules_escalate - 0.01:
                continue

            if total_cost < best_cost:
                best_cost = total_cost
                best_t = t
                best_r = r

    if best_t is None:
        return "do-not-promote"

    # Pioneer offsets: derive low/high/max from medium
    t_med, r_med = best_t, best_r
    t_low = max(0.0, min(1.0, t_med - 0.05))
    r_low = max(0.0, min(1.0, r_med + 0.10))
    t_high = max(0.0, min(1.0, t_med + 0.10))
    r_high = max(0.0, min(1.0, r_med - 0.05))
    t_max = max(0.0, min(1.0, t_med + 0.50))
    r_max = max(0.0, min(1.0, r_med - 0.17))

    # Walk to restore ordering
    t_low = min(t_low, t_med)
    t_high = max(t_high, t_med)
    t_max = max(t_max, t_high)
    r_low = max(r_low, r_med)
    r_high = min(r_high, r_med)
    r_max = min(r_max, r_high)

    lines = ["trained_effort:"]
    for name, t_val, r_val in [
        ("low", t_low, r_low),
        ("medium", t_med, r_med),
        ("high", t_high, r_high),
        ("max", t_max, r_max),
    ]:
        lines.append(f"  {name}: {{threshold: {t_val:.2f}, max_regret: {r_val:.2f}}}")

    return "\n".join(lines) + "\n"


def main(
    argv: list[str] | None = None,
    *,
    provider: Any | None = None,
    spend: SpendLog | None = None,
    cache_dir: Path | None = None,
    models_path: Path | None = None,
) -> int:
    argv = list(argv) if argv is not None else sys.argv[1:]
    is_offline = argv[:1] in (["pool"], ["retune"]) or any(x in ("-h", "--help") for x in argv)
    if not is_offline and os.getenv(OPT_IN_ENV) != "1":
        return _refuse()
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pool")
    p.add_argument(
        "--smith",
        help=(
            "SWE-smith-trajectories tool-split JSONL (messages + tool_calls + "
            "instance_id/traj_id). Not datasets/train-queries.jsonl. Export: "
            "load_dataset('SWE-bench/SWE-smith-trajectories', split='tool')"
            ".to_json('data/smith-tool.jsonl')"
        ),
    )
    p.add_argument("--bfcl")
    p.add_argument("--gym")
    p.add_argument("--r2e")
    p.add_argument(
        "--tasks",
        help=(
            "SWE-smith tasks JSONL joined by instance_id. Copies FAIL_TO_PASS and "
            "expected from reverting the bug patch. Not Verified/Lite/TB; dump "
            "resolved is never y. Never invents json_schema."
        ),
    )
    p.add_argument(
        "--gym-tasks",
        help=(
            "SWE-Gym (or smith-shaped) *task* JSONL as primary pool source when "
            "smith traj family is exhausted. Builds flashlight/issue rows via "
            "gold-revert expected — no traj dump required. Unpaid ingest: "
            "`python -m aiand_router.pool ingest --profile gym_alt`."
        ),
    )
    p.add_argument("--eval", nargs="*", default=[])
    p.add_argument("--out", required=True)
    p.add_argument("--n", type=int, default=4000)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument(
        "--verified-like",
        action="store_true",
        help=(
            "Prefer short + hard/frontier with copied expected/schema/tests; "
            "refuse an empty hard-check mix (proxy-only tools cannot dominate). "
            "Never invent json_schema from the word json. Not Verified eval"
        ),
    )
    p.add_argument(
        "--verified-like-max-tokens",
        type=int,
        default=450,
        help="Max prompt tokens for verified-like flashlight/issue rows (mix length knob)",
    )
    p.add_argument(
        "--prompt-family",
        choices=("flashlight", "issue", "any"),
        default="flashlight",
        help=(
            "Verified-like prompt family. Default flashlight keeps hunk-restore "
            "plus dump-copied expected/schema/tests (family other). Pass issue|any "
            "explicitly; issue-fix was H2 kill. Mix1 also needs --near-miss-lo/hi."
        ),
    )
    p.add_argument("--min-expected-len", type=int, default=0)
    p.add_argument("--max-expected-len", type=int, default=0)
    p.add_argument(
        "--near-miss-lo",
        type=float,
        default=0.0,
        help="Min buggy↔expected line ratio (prefer small-fix flashlights when set)",
    )
    p.add_argument(
        "--near-miss-hi",
        type=float,
        default=1.0,
        help="Max buggy↔expected line ratio (exclude near-identical / too-easy)",
    )
    p.add_argument(
        "--max-fail-to-pass",
        type=int,
        default=0,
        help="Drop queries with more FAIL_TO_PASS tests than this (0 = no cap). Mix1 p90 is 4.",
    )
    t = sub.add_parser("teacher")
    t.add_argument("--queries", required=True)
    t.add_argument("--out", required=True)
    t.add_argument("--limit", type=int, default=TEACHER_LIMIT)
    t.add_argument(
        "--split",
        choices=sorted(MANIFEST_VALID_SPLITS),
        default=None,
        help="manifest split to filter queries (teacher-silver|sparse-train|dense-cal|threshold-tune|promotion-holdout); filters BEFORE guard",
    )
    g = sub.add_parser("gold")
    g.add_argument("--queries", required=True)
    g.add_argument("--out", required=True)
    g.add_argument("--limit", type=int, default=None)
    g.add_argument("--dense", action="store_true")
    g.add_argument(
        "--include-k3",
        action="store_true",
        help="Include K3 in the dense gold slice (default off; K3 stays excluded from sparse/dense).",
    )
    g.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="JSONL of already-labeled queries/gold (repeatable). Drops matching prompt or instance_id.",
    )
    g.add_argument("--seed", type=int, default=0, help="Stratum sample seed after --exclude")
    g.add_argument(
        "--split",
        choices=sorted(MANIFEST_VALID_SPLITS),
        default=None,
        help="manifest split to filter queries (teacher-silver|sparse-train|dense-cal|threshold-tune|promotion-holdout); filters BEFORE guard",
    )
    f = sub.add_parser("fit")
    f.add_argument("--gold", required=True)
    f.add_argument("--cal")
    f.add_argument("--silver")
    f.add_argument("--out", required=True)
    f.add_argument(
        "--gbdt",
        action="store_true",
        help=(
            "One stump GBDT after logistic fails transfer; length stumps collapse on short "
            "prompts. Prefer logistic until Spearman(train, eval) > 0."
        ),
    )
    f.add_argument(
        "--bilinear",
        action="store_true",
        help=(
            "EmbedLLM/IRT-lite head: shared query projection + frozen per-model factors. "
            "Features-only at serve time; no live embed."
        ),
    )
    f.add_argument(
        "--bilinear-hash-dim",
        type=int,
        default=0,
        help=(
            "Append hashing-trick text latent of this dim to the live bilinear trunk "
            "(features-only; not a neural embed). Ignored when --bilinear-distill-hash-dim>0."
        ),
    )
    f.add_argument(
        "--bilinear-distill-hash-dim",
        type=int,
        default=0,
        help=(
            "Offline distill: fit teacher bilinear on hash_dim trunk, ridge-map base "
            "features -> teacher query latent; serve with hash_dim=0 (no live hash)."
        ),
    )
    f.add_argument(
        "--bilinear-hash-seed",
        type=int,
        default=17,
        help="Deterministic seed for hashing-trick buckets",
    )
    f.add_argument(
        "--bilinear-distill-latent-dim",
        type=int,
        default=0,
        help=(
            "Teacher latent dim for offline distill (default min(32, teacher_feat_dim)). "
            "Requires --bilinear-distill-hash-dim>0."
        ),
    )
    f.add_argument(
        "--bilinear-ridge-l2",
        type=float,
        default=0.05,
        help="Ridge L2 for student←teacher query map (distill only).",
    )
    f.add_argument(
        "--geometry-train",
        help="Train/sparse gold JSONL for geometry gate (blocks fit when geometry_pass=false)",
    )
    f.add_argument("--geometry-cal", help="Optional dense/cal gold for geometry report")
    f.add_argument(
        "--geometry-eval",
        help="Eval-only holdout gold for geometry gate (required with --geometry-train)",
    )
    f.add_argument(
        "--noise-alpha",
        type=float,
        default=0.0,
        help="Gaussian noise std on numeric features before fitting heads (default 0.0 = off; pure-Python, no embedding dep)",
    )
    f.add_argument(
        "--calibrator",
        choices=("auto", "platt", "isotonic"),
        default="auto",
        help="Calibrator mode: auto=isotonic iff n_cal>1000 else Platt; platt=force; isotonic=force (errors if n_cal<=1000)",
    )
    r = sub.add_parser("relabel")
    r.add_argument("--gold", required=True)
    r.add_argument("--queries", required=True)
    r.add_argument("--out", required=True)
    s = sub.add_parser("salvage")
    s.add_argument("--silver", required=True)
    s.add_argument("--queries", required=True)
    rt = sub.add_parser("retune")
    rt.add_argument("--dense", required=True)
    rt.add_argument("--scorer")
    rt.add_argument("--models")
    rt.add_argument(
        "--init",
        choices=("grid", "quantile"),
        default="grid",
        help="Threshold grid init: grid=exhaustive scan (default), quantile=quantile-initialized before exhaustive scan",
    )
    args = parser.parse_args(argv)
    if args.cmd == "pool":
        return run_pool(args)
    if args.cmd == "retune":
        root = Path(__file__).resolve().parents[2]
        result = run_retune(
            Path(args.dense),
            scorer_path=Path(args.scorer) if args.scorer else None,
            models_path=Path(args.models) if args.models else models_path,
            init=str(args.init or "grid"),
        )
        print(result, end="")
        return 0

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
        geo_report: dict[str, Any] | None = None
        if args.geometry_train or args.geometry_eval:
            if not args.geometry_train or not args.geometry_eval:
                print(
                    "refusing: --geometry-train and --geometry-eval must be set together",
                    file=sys.stderr,
                )
                return 2
            blocked, geo_report = _geometry_gate(
                Path(args.geometry_train),
                Path(args.geometry_eval),
                Path(args.geometry_cal) if args.geometry_cal else None,
            )
            if blocked:
                print(
                    json.dumps(
                        {
                            "geometry_pass": False,
                            "kill": geo_report.get("kill"),
                            "recommended_artifact": geo_report.get("recommended_artifact"),
                        },
                        indent=2,
                    ),
                    file=sys.stderr,
                )
                print(
                    f"refusing fit: geometry_pass=false "
                    f"(set {GEOMETRY_OVERRIDE_ENV}=1 to override)",
                    file=sys.stderr,
                )
                return 2
        if args.gbdt and args.bilinear:
            print("refusing: choose at most one of --gbdt and --bilinear", file=sys.stderr)
            return 2
        if (args.bilinear_hash_dim or args.bilinear_distill_hash_dim) and not args.bilinear:
            print(
                "refusing: --bilinear-hash-dim / --bilinear-distill-hash-dim require --bilinear",
                file=sys.stderr,
            )
            return 2
        if int(args.bilinear_distill_latent_dim or 0) > 0 and not (
            args.bilinear and int(args.bilinear_distill_hash_dim or 0) > 0
        ):
            print(
                "refusing: --bilinear-distill-latent-dim requires --bilinear "
                "and --bilinear-distill-hash-dim>0",
                file=sys.stderr,
            )
            return 2
        fit_scorer(
            Path(args.gold),
            Path(args.silver) if args.silver else None,
            Path(args.out),
            Path(args.cal) if args.cal else None,
            gbdt=bool(args.gbdt),
            bilinear=bool(args.bilinear),
            geometry_report_out=geo_report,
            bilinear_hash_dim=int(args.bilinear_hash_dim or 0),
            bilinear_distill_hash_dim=int(args.bilinear_distill_hash_dim or 0),
            bilinear_hash_seed=int(args.bilinear_hash_seed or 17),
            bilinear_distill_latent_dim=int(args.bilinear_distill_latent_dim or 0),
            bilinear_ridge_l2=float(args.bilinear_ridge_l2),
            noise_alpha=float(args.noise_alpha or 0.0),
            calibrator=str(args.calibrator or "auto"),
        )
        if geo_report:
            print("recommended_artifact", geo_report.get("recommended_artifact"))
        return 0
    if args.cmd == "relabel":
        relabel_gold(
            Path(args.gold),
            Path(args.queries),
            Path(args.out),
            cache=cache,
            models_by_id=by_id,
        )
        return 0
    if args.cmd == "salvage":
        asyncio.run(
            run_salvage_silver(
                Path(args.silver),
                Path(args.queries),
                provider=upstream,
                spend=spend_log,
                cache=cache,
                models_by_id=by_id,
            )
        )
        return 0
    if args.cmd == "gold":
        if args.dense and not args.exclude:
            print("refusing: --dense requires --exclude so the cal slice stays disjoint", file=sys.stderr)
            return 2
        if getattr(args, "include_k3", False) and not args.dense:
            print("refusing: --include-k3 requires --dense (K3 is a dense-only slice)", file=sys.stderr)
            return 2
        limit = args.limit if args.limit is not None else (DENSE_LIMIT if args.dense else SPARSE_LIMIT)
    else:
        limit = args.limit
    blocked: set[str] = set()
    blocked_ids: set[str] = set()
    for ep in getattr(args, "exclude", None) or []:
        for r in _jsonl_rows(Path(ep)):
            prompt = str(r.get("prompt") or "")
            if prompt:
                blocked.add(prompt)
            iid = str(r.get("instance_id") or "").lower()
            if iid:
                blocked_ids.add(iid)
    gold_seed = int(getattr(args, "seed", 0) or 0) if args.cmd == "gold" else 0
    queries = _read_queries(
        Path(args.queries),
        limit,
        exclude=blocked or None,
        exclude_ids=blocked_ids or None,
        seed=gold_seed,
    )
    split = getattr(args, "split", None)
    if split is not None:
        if split not in MANIFEST_VALID_SPLITS:
            raise ValueError(f"split_manifest_overlap: unknown split {split!r}")
        manifest_map = _load_manifest_map(_resolve_manifest_path(Path(args.queries), None))
        all_queries = _read_queries(
            Path(args.queries),
            100000,
            exclude=blocked or None,
            exclude_ids=blocked_ids or None,
            seed=gold_seed,
        )
        filtered: list[dict[str, Any]] = []
        for q in all_queries:
            h = _prompt_hash(_manifest_prompt_of_row(q))
            if manifest_map.get(h) == split:
                filtered.append(q)
        queries = filtered[:limit]
        if args.cmd == "gold" and getattr(args, "dense", False) and not queries:
            print("refusing: --dense --exclude left no queries to run", file=sys.stderr)
            return 2
        _guard_manifest_for_queries(
            queries,
            allowed_splits={split},
            queries_path=Path(args.queries),
        )
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
                include_k3=bool(getattr(args, "include_k3", False)),
            )
        )
        return 0
    if args.cmd == "gold" and args.dense and not queries:
        print("refusing: --dense --exclude left no queries to run", file=sys.stderr)
        return 2
    if args.cmd == "teacher":
        _guard_manifest_for_queries(
            queries,
            allowed_splits={"teacher-silver"},
            queries_path=Path(args.queries),
        )
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
    if args.cmd == "gold":
        _guard_manifest_for_queries(
            queries,
            allowed_splits={"dense-cal"} if args.dense else {"sparse-train"},
            queries_path=Path(args.queries),
        )
    asyncio.run(
        run_gold(
            queries,
            Path(args.out),
            provider=upstream,
            spend=spend_log,
            cache=cache,
            models_by_id=by_id,
            dense=bool(getattr(args, "dense", False)),
            include_k3=bool(getattr(args, "include_k3", False)),
        )
    )
    return 0


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    raise SystemExit(main())
