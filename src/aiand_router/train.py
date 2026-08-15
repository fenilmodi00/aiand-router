"""Opt-in offline teacher / gold / fit. Refuses unless AIAND_TRAIN=1."""

from __future__ import annotations

import argparse
import asyncio
import difflib
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx

from .cache import RequestCache, request_cache_key
from .provider import HttpAiandProvider
from .pool import run_pool, sample_stratum
from .router import (
    SpendLog,
    _text,
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
    _gbdt_z,
    featurize,
    featurize_observable,
    load_scorer,
    pick_cheapest_above_bar,
    score_eligible,
)

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
SPARSE_LIMIT = 400
DENSE_LIMIT = 100
MEASURED_TRIO = (
    "qwen/qwen3.6-27b",
    "moonshotai/kimi-k2.7-code",
    "deepseek-ai/deepseek-v4-pro",
)
FLASH = "deepseek-ai/deepseek-v4-flash"
K3 = "moonshotai/kimi-k3"
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
    path: Path, limit: int, exclude: set[str] | None = None
) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    if exclude:
        rows = [q for q in rows if _prompt_of(_messages(q)) not in exclude]
    if limit >= len(rows):
        return rows
    return sample_stratum(rows, limit, seed=0)


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
    if any(tid.startswith(prefix) for tid in (CHEAP_TEACHER, ESCALATE_TEACHER) for prefix in EXCLUDED_PREFIXES):
        raise ValueError("teacher ids must exclude measured-trio and fallback providers")
    spend._async_lock = asyncio.Lock()
    cap = max(1, int(len(queries) * 0.25))
    escalated = 0
    esc_lock = asyncio.Lock()
    sem = asyncio.Semaphore(_concurrency())

    async def one(q: dict[str, Any]) -> dict[str, Any]:
        nonlocal escalated
        async with sem:
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
            do_esc = False
            async with esc_lock:
                if needs_esc and (parse_fail or escalated < cap):
                    do_esc = True
                    if not parse_fail:
                        escalated += 1
            if do_esc:
                esc = await _teacher_call(
                    provider, ESCALATE_TEACHER, messages, cache=cache, spend=spend, models_by_id=models_by_id
                )
                if esc:
                    label = esc
            if not label:
                return {"prompt": _prompt_of(messages), "unlabeled": True}
            row = {
                "prompt": _prompt_of(messages),
                "complexity_bin": label["complexity_bin"],
                "p_success": label["p_success"],
                "teacher": CHEAP_TEACHER,
                "tokens": estimate_tokens(messages),
                "needs_tools": bool(q.get("needs_tools")),
                "phase": str(q.get("phase") or "plan"),
                "hint_bin": str(q.get("hint_bin") or "standard"),
            }
            if "bloom_level" in label:
                row["bloom_level"] = label["bloom_level"]
            return row

    rows: list[dict[str, Any]] = []
    for coro in asyncio.as_completed([one(q) for q in queries]):
        rows.append(await coro)
        if len(rows) % 10 == 0:
            out.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
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


def _gold_ids(q: dict[str, Any], models_by_id: dict[str, Model], *, dense: bool) -> list[str]:
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


def _strip_fences(text: str) -> str:
    t = text.strip()
    if "```" not in t:
        return t
    inner = t.split("```", 2)[1]
    if inner.startswith(("json", "python", "yaml")):
        inner = inner.split("\n", 1)[-1] if "\n" in inner else inner[3:]
    return inner.strip()


def _pytest_verify(text: str, meta: dict[str, Any]) -> bool | None:
    if not meta.get("verify_pytest"):
        return None
    module = str(meta.get("module") or "fix.py")
    tests = meta.get("tests")
    if not tests or "```" not in text:
        return False
    inner = text.split("```", 2)[1]
    if inner.startswith("python"):
        inner = inner[len("python") :].lstrip("\n")
    code = inner.strip()
    if not code:
        return False
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / module).write_text(code + "\n", encoding="utf-8")
        test_name = f"test_{Path(module).stem}.py"
        (root / test_name).write_text(str(tests).strip() + "\n", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--noconftest", "-o", f"testpaths={root}"],
            cwd=root,
            capture_output=True,
            text=True,
        )
        return proc.returncode == 0


_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_IDENT_STOP = frozenset(
    {
        "self",
        "return",
        "None",
        "True",
        "False",
        "if",
        "else",
        "elif",
        "for",
        "while",
        "def",
        "class",
        "import",
        "from",
        "and",
        "or",
        "not",
        "in",
        "is",
        "with",
        "as",
        "try",
        "except",
        "raise",
        "pass",
        "break",
        "continue",
        "lambda",
        "yield",
        "async",
        "await",
        "str",
        "int",
        "list",
        "dict",
        "set",
        "tuple",
        "Any",
        "Optional",
        "len",
        "print",
    }
)
# Soft expected vs gold-revert: near-exact line, or high edit + full identifier overlap.
_SOFT_NEAR_RATIO = 0.92
_SOFT_EDIT_RATIO = 0.85


def _code_idents(text: str) -> set[str]:
    return {
        t
        for t in _IDENT_RE.findall(text)
        if t not in _IDENT_STOP and len(t) > 1
    }


def _norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _best_line_ratio(expected: str, hay: str) -> float:
    en = _norm_ws(expected)
    if not en:
        return 0.0
    best = 0.0
    for line in hay.splitlines():
        line = _norm_ws(line)
        if len(line) < 8:
            continue
        best = max(best, difflib.SequenceMatcher(None, en, line).ratio())
    return best


def _expected_match(expected: str, hay: str) -> bool:
    """Verified soft-y: exact / ws-normalized substring, else edit + identifier overlap.

    Does not invent schemas. Partial near-misses can succeed; unrelated keyword spam cannot
    (requires full non-trivial identifier overlap when below near-exact).
    """
    exp = str(expected)
    if not exp or not hay:
        return False
    if exp in hay or _norm_ws(exp) in _norm_ws(hay):
        return True
    best = _best_line_ratio(exp, hay)
    if best >= _SOFT_NEAR_RATIO:
        return True
    ei = _code_idents(exp)
    if len(ei) < 2:
        return False
    ov = len(ei & _code_idents(hay)) / len(ei)
    return best >= _SOFT_EDIT_RATIO and ov >= 1.0


def _label_haystack(message: dict[str, Any]) -> str:
    """Content, tool args, and reasoning_content (Probe D soft-y).

    Kimi often finishes length with empty content but gold line in reasoning; content-only
    zeros Kimi and inverts Spearman vs holdout. Soft thresholds stay fixed — do not game them.
    """
    parts: list[str] = []
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        parts.append(content.strip())
    reasoning = message.get("reasoning_content")
    if isinstance(reasoning, str) and reasoning.strip():
        parts.append(reasoning.strip())
    for tc in message.get("tool_calls") or []:
        if not isinstance(tc, dict):
            continue
        fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
        args = fn.get("arguments") if fn else tc.get("arguments")
        if isinstance(args, dict):
            args = json.dumps(args)
        if args:
            parts.append(str(args))
    return "\n".join(parts)


def _gold_label(
    message: dict[str, Any],
    prompt: str,
    choice: dict[str, Any],
    *,
    meta: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    """Return (success, tier). verified > proxy > weak."""
    meta = meta or {}
    content = message.get("content")
    text = content.strip() if isinstance(content, str) else ""
    hay = _label_haystack(message)
    pytest_ok = _pytest_verify(text, meta)
    if pytest_ok is not None:
        return pytest_ok, "verified"
    expected = meta.get("expected")
    if expected is not None:
        return _expected_match(str(expected), hay), "verified"
    schema = meta.get("json_schema") or meta.get("schema")
    if schema is not None:
        body = _strip_fences(text) if text else hay
        try:
            obj = json.loads(body if body else "")
        except json.JSONDecodeError:
            return False, "verified"
        req = schema.get("required") or [] if isinstance(schema, dict) else []
        if req and (not isinstance(obj, dict) or any(k not in obj for k in req)):
            return False, "verified"
        return True, "verified"
    tests = meta.get("tests")
    if meta.get("FAIL_TO_PASS") or (isinstance(tests, list) and tests):
        return False, "verified"
    if message.get("tool_calls"):
        return True, "proxy"
    if meta.get("needs_tools"):
        return False, "proxy"
    finish = str(choice.get("finish_reason") or "")
    if finish == "length" and not text:
        return False, "weak"
    if not text:
        return False, "weak"
    pl = prompt.lower()
    body = _strip_fences(text)
    used_proxy = False
    if any(k in pl for k in ("reply with json", "json_schema", "valid json", "json only")):
        used_proxy = True
        try:
            json.loads(body)
        except json.JSONDecodeError:
            return False, "proxy"
    elif "json object" in pl and ("return" in pl or "parse" in pl):
        used_proxy = True
        if "{" in body:
            try:
                json.loads(body[body.index("{") : body.rindex("}") + 1])
            except (json.JSONDecodeError, ValueError):
                return False, "proxy"
    for pat in (
        r"reply with the single word (\w+)",
        r"reply with only (\w+)",
        r"respond with only (\w+)",
        r"single word (\w+)",
    ):
        m = re.search(pat, pl, re.I)
        if m:
            used_proxy = True
            if body.lower().split()[0] != m.group(1).lower():
                return False, "proxy"
    m = re.search(r"(?:must contain|include the (?:string|substring)) [`'\"]?([^`'\".\n]+)", pl, re.I)
    if m:
        used_proxy = True
        if m.group(1).lower() not in text.lower():
            return False, "proxy"
    m = re.search(r"typo ['\"](\w+)['\"] to ['\"](\w+)['\"]", pl, re.I)
    if m:
        used_proxy = True
        wrong, right = m.group(1).lower(), m.group(2).lower()
        if wrong in text.lower() or right not in text.lower():
            return False, "proxy"
    if "yaml snippet" in pl or "write a yaml" in pl:
        used_proxy = True
        if ":" not in body or body.lstrip().startswith("{"):
            return False, "proxy"
    return True, "proxy" if used_proxy else "weak"


def _gold_success(
    message: dict[str, Any],
    prompt: str,
    choice: dict[str, Any],
    *,
    meta: dict[str, Any] | None = None,
) -> bool:
    return _gold_label(message, prompt, choice, meta=meta)[0]


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
    jobs: list[tuple[list[dict[str, Any]], str, dict[str, Any]]] = []
    for q in queries:
        messages = _messages(q)
        for model_id in _gold_ids(q, models_by_id, dense=dense):
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


def _row_x_observable(row: dict[str, Any]) -> list[float]:
    messages = row.get("messages") or [{"role": "user", "content": row.get("prompt") or ""}]
    tokens = int(row.get("tokens") or estimate_tokens(messages))
    return featurize_observable(str(row.get("phase") or "plan"), bool(row.get("needs_tools")), tokens)


def _row_x(row: dict[str, Any]) -> list[float]:
    messages = row.get("messages") or [{"role": "user", "content": row.get("prompt") or ""}]
    tokens = int(row.get("tokens") or estimate_tokens(messages))
    hint = str(row.get("hint_bin") or row.get("complexity_bin") or "standard")
    text = str(row.get("prompt") or "")
    if not text and messages:
        text = "\n".join(_text(m.get("content")) for m in messages if isinstance(m, dict))
    return featurize(str(row.get("phase") or "plan"), bool(row.get("needs_tools")), tokens, hint, text=text)


def _logit(p: float) -> float:
    p = max(1e-6, min(1.0 - 1e-6, p))
    return math.log(p / (1.0 - p))


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


def _fit_binary_intercept(
    xs: list[list[float]], ys: list[float], intercept: float, steps: int = 80, lr: float = 0.35
) -> list[float]:
    dim = len(xs[0])
    w = [0.0] * dim
    n = max(1, len(xs))
    for _ in range(steps):
        grad = [0.0] * dim
        for x, y in zip(xs, ys):
            z = intercept + sum(w[i] * x[i] for i in range(dim))
            z = max(-30.0, min(30.0, z))
            err = (1.0 / (1.0 + math.exp(-z))) - y
            for i in range(1, dim):
                grad[i] += err * x[i]
        for i in range(1, dim):
            w[i] -= lr * grad[i] / n
    return w


GBDT_TREES = 24
GBDT_LR = 0.1


def _fit_stump(xs: list[list[float]], resid: list[float]) -> dict[str, float]:
    n = len(xs)
    dim = len(xs[0]) if xs else 0
    best: tuple[float, int, float, float, float] | None = None
    for j in range(1, dim):
        vals = sorted({x[j] for x in xs})
        if len(vals) < 2:
            continue
        for k in range(len(vals) - 1):
            thr = 0.5 * (vals[k] + vals[k + 1])
            left_s = left_n = right_s = right_n = 0.0
            for x, r in zip(xs, resid):
                if x[j] <= thr:
                    left_s += r
                    left_n += 1
                else:
                    right_s += r
                    right_n += 1
            if left_n == 0 or right_n == 0:
                continue
            left, right = left_s / left_n, right_s / right_n
            sse = 0.0
            for x, r in zip(xs, resid):
                pred = left if x[j] <= thr else right
                sse += (r - pred) ** 2
            if best is None or sse < best[0]:
                best = (sse, j, thr, left, right)
    if best is None:
        mean = (sum(resid) / n) if n else 0.0
        return {"feature": 0, "threshold": 0.0, "left": mean, "right": mean}
    return {"feature": best[1], "threshold": best[2], "left": best[3], "right": best[4]}


def _fit_gbdt(
    xs: list[list[float]],
    ys: list[float],
    intercept: float,
    n_trees: int = GBDT_TREES,
    lr: float = GBDT_LR,
) -> dict[str, Any]:
    z = [intercept] * len(xs)
    trees: list[dict[str, float]] = []
    for _ in range(n_trees):
        p = [1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, zi)))) for zi in z]
        resid = [y - pi for y, pi in zip(ys, p)]
        stump = _fit_stump(xs, resid)
        stump["left"] = float(stump["left"]) * lr
        stump["right"] = float(stump["right"]) * lr
        trees.append(stump)
        j = int(stump["feature"])
        thr = float(stump["threshold"])
        for i, x in enumerate(xs):
            z[i] += stump["left"] if (j < len(x) and x[j] <= thr) else stump["right"]
    return {"intercept": intercept, "trees": trees}


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


def _fit_isotonic(zs: list[float], ys: list[float]) -> list[list[float]]:
    """Pure-Python PAVA (Pool Adjacent Violators).

    Returns a monotone step table ``[[z, p], ...]`` suitable for JSON.
    Each entry is ``[max_z_of_block, pooled_mean]``; p is non-decreasing.
    Lookup: first entry where ``z_q <= boundary`` wins; clamp to last.
    """
    if len(zs) != len(ys):
        raise ValueError("zs and ys must have equal length")
    if not zs:
        raise ValueError("cannot fit isotonic on empty (z, y) lists")
    pairs = sorted(zip(zs, ys), key=lambda p: p[0])
    # blocks: [sum_y, count, max_z]
    blocks: list[list[float]] = []
    for z, y in pairs:
        blocks.append([y, 1, z])
        while len(blocks) >= 2 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
            blocks[-2][0] += blocks[-1][0]
            blocks[-2][1] += blocks[-1][1]
            blocks[-2][2] = blocks[-1][2]
            blocks.pop()
    return [[b[2], b[0] / b[1]] for b in blocks]


CAL_FRAC = 0.2


def _split_cal_prompts(prompts: list[str], frac: float = CAL_FRAC) -> tuple[set[str], set[str]]:
    """Hold out a sorted tail of unique prompts as the gold cal slice."""
    uniq = sorted({p for p in prompts if p})
    if len(uniq) < 2:
        return set(uniq), set()
    n_cal = max(1, int(round(len(uniq) * frac)))
    cal = set(uniq[-n_cal:])
    return set(uniq) - cal, cal


def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _observed_gold(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if not r.get("unobserved") and "model_id" in r]


def fit_scorer(
    gold_path: Path,
    silver_path: Path | None,
    out: Path,
    cal_path: Path | None = None,
    gbdt: bool = False,
) -> None:
    gold = _jsonl_rows(gold_path)
    silver = _jsonl_rows(silver_path) if silver_path and silver_path.exists() else []
    observed = _observed_gold(gold)
    cal_file = _observed_gold(_jsonl_rows(cal_path)) if cal_path and cal_path.exists() else []
    tagged_cal = [r for r in observed if r.get("dense")]
    tagged_train = [r for r in observed if not r.get("dense")]
    if cal_file:
        train_gold = tagged_train
        cal_gold = cal_file
    elif tagged_cal:
        train_gold = tagged_train
        cal_gold = tagged_cal
    else:
        train_prompts, cal_prompts = _split_cal_prompts(
            [str(r.get("prompt") or "") for r in observed]
        )
        train_gold = [r for r in observed if str(r.get("prompt") or "") in train_prompts]
        cal_gold = [r for r in observed if str(r.get("prompt") or "") in cal_prompts]
    observed = train_gold + cal_gold
    gold_cells = {(str(r.get("prompt")), r["model_id"]) for r in observed}
    gold_ids = {mid for _, mid in gold_cells}
    by_model_x: dict[str, list[list[float]]] = {mid: [] for mid in gold_ids}
    by_model_y: dict[str, list[float]] = {mid: [] for mid in gold_ids}
    train_counts: dict[str, int] = {mid: 0 for mid in gold_ids}
    for row in train_gold:
        mid = row["model_id"]
        by_model_x[mid].append(_row_x(row))
        by_model_y[mid].append(1.0 if row.get("success") else 0.0)
        train_counts[mid] += 1
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
    weights: dict[str, list[float]] = {}
    intercepts = {}
    gbdt_heads: dict[str, dict[str, Any]] = {}
    for mid, xs in by_model_x.items():
        n_train = train_counts[mid]
        if n_train == 0 or not xs:
            continue
        gold_ys = by_model_y[mid][:n_train]
        rate = sum(gold_ys) / len(gold_ys) if gold_ys else 0.5
        ic = _logit(rate)
        intercepts[mid] = ic
        if gbdt:
            gbdt_heads[mid] = _fit_gbdt(xs, by_model_y[mid], ic)
        else:
            weights[mid] = _fit_binary_intercept(xs, by_model_y[mid], ic)
    zs_cal: list[float] = []
    ys_cal: list[float] = []
    for row in cal_gold:
        mid = row["model_id"]
        x = _row_x(row)
        if gbdt:
            head = gbdt_heads.get(mid)
            if not head:
                continue
            zs_cal.append(_gbdt_z(head, x))
        else:
            w = weights.get(mid)
            if not w:
                continue
            ic = intercepts[mid]
            zs_cal.append(ic + sum(w[i] * x[i] for i in range(len(w))))
        ys_cal.append(1.0 if row.get("success") else 0.0)
    n_cal = len(zs_cal)
    if n_cal <= 1000:
        a, b = _fit_platt(zs_cal, ys_cal)
        calibrator: dict[str, Any] = {"mode": "platt", "a": a, "b": b}
    else:
        table = _fit_isotonic(zs_cal, ys_cal)
        calibrator = {"mode": "isotonic", "table": table}
        a, b = 1.0, 0.0
    bin_xs: list[list[float]] = []
    bin_ys: dict[str, list[float]] = {bn: [] for bn in BINS}
    for row in silver:
        if row.get("unlabeled") or row.get("complexity_bin") not in BINS:
            continue
        x = _row_x_observable(row)
        bin_xs.append(x)
        for bn in BINS:
            bin_ys[bn].append(1.0 if row["complexity_bin"] == bn else 0.0)
    bin_weights = {bn: _fit_binary(bin_xs, bin_ys[bn]) for bn in BINS} if bin_xs else {}
    p_success = {}
    for mid in gold_ids:
        gold_ys = [1.0 if r.get("success") else 0.0 for r in observed if r["model_id"] == mid]
        if gold_ys:
            p_success[mid] = sum(gold_ys) / len(gold_ys)
    bins = [str(r.get("complexity_bin")) for r in silver if r.get("complexity_bin") in BINS]
    bin_ = max(set(bins), key=bins.count) if bins else "standard"
    artifact: dict[str, Any] = {
        "not_spec_floors": True,
        "complexity_bin": bin_,
        "p_success": p_success,
        "weights": weights,
        "intercepts": intercepts,
        "bin_weights": bin_weights,
        "platt": {"a": a, "b": b},
        "calibrator": calibrator,
        "n_gold": len(gold),
        "n_cal": len(cal_gold),
        "n_silver": len(silver),
    }
    if gbdt:
        artifact["gbdt"] = gbdt_heads
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")


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
    is_offline = argv[:1] in (["pool"], ["retune"])
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
        help="Verified-like prompt family filter (default flashlight; issue was H2 kill)",
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
    t = sub.add_parser("teacher")
    t.add_argument("--queries", required=True)
    t.add_argument("--out", required=True)
    t.add_argument("--limit", type=int, default=TEACHER_LIMIT)
    g = sub.add_parser("gold")
    g.add_argument("--queries", required=True)
    g.add_argument("--out", required=True)
    g.add_argument("--limit", type=int, default=None)
    g.add_argument("--dense", action="store_true")
    g.add_argument("--exclude")
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
    args = parser.parse_args(argv)
    if args.cmd == "pool":
        return run_pool(args)
    if args.cmd == "retune":
        root = Path(__file__).resolve().parents[2]
        result = run_retune(
            Path(args.dense),
            scorer_path=Path(args.scorer) if args.scorer else None,
            models_path=Path(args.models) if args.models else models_path,
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
        fit_scorer(
            Path(args.gold),
            Path(args.silver) if args.silver else None,
            Path(args.out),
            Path(args.cal) if args.cal else None,
            gbdt=bool(args.gbdt),
        )
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
        limit = args.limit if args.limit is not None else (DENSE_LIMIT if args.dense else SPARSE_LIMIT)
    else:
        limit = args.limit
    blocked: set[str] = set()
    if getattr(args, "exclude", None):
        blocked = {str(r.get("prompt") or "") for r in _jsonl_rows(Path(args.exclude))}
    queries = _read_queries(Path(args.queries), limit, exclude=blocked or None)
    if args.cmd == "gold" and args.dense and not queries:
        print("refusing: --dense --exclude left no queries to run", file=sys.stderr)
        return 2
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
