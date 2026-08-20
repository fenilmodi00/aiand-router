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
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

import httpx

from .gold_label import _pytest_verify

ROOT = Path(__file__).resolve().parents[2]
CAP = 50  # hard cap on instance count

_TURNS = [
    ("discover", "List what is in this repo and what the tests expect."),
    ("plan", "Plan the smallest fix. Do not write code yet."),
    ("edit", "Write the corrected Python module only, inside a ```python fence."),
    ("debug", "Tests failed. Write the corrected Python module only, inside a ```python fence."),
    ("summarize", "One paragraph: what broke, what you changed."),
]

# Gold diffs must never enter the model prompt (SWE-bench `patch` / `test_patch`).

_FILE_EXT = (
    r"py|js|ts|tsx|jsx|rb|go|java|c|cc|cpp|h|hpp|rs|cs"
)
_FILE_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_/.\\-])"
    r"((?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\."
    rf"(?:{_FILE_EXT}))",
    re.IGNORECASE,
)
# Explicit paths inside GitHub blob URLs (lookbehind blocks slash-prefixed paths).
_GITHUB_BLOB_PATH_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/"
    r"(?P<owner>[^/\s]+)/(?P<repo>[^/\s]+)/blob/[^/\s]+/"
    rf"(?P<path>[A-Za-z0-9_./+-]+\.(?:{_FILE_EXT}))",
    re.IGNORECASE,
)
_MODULE_HINT_RE = re.compile(
    r"\b(?:in|file|module|package)\s+"
    r"([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){1,})",
    re.IGNORECASE,
)


def fail_to_pass_list(val: Any) -> list[str]:
    """Parse SWE-bench FAIL_TO_PASS (list or JSON string) into test-nodeid strings."""
    if val is None or val == "":
        return []
    if isinstance(val, list):
        return [str(x) for x in val if str(x).strip()]
    if isinstance(val, str):
        text = val.strip()
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                return [text]
            if isinstance(parsed, list):
                return [str(x) for x in parsed if str(x).strip()]
        return [text]
    return [str(val)]


def _module_to_repo_path(module: str, repo: str | None) -> str:
    """Map dotted module (e.g. contrib.auth.validators) → repo-relative .py path."""
    parts = [p for p in module.split(".") if p]
    path = "/".join(parts) + ".py"
    if not repo:
        return path
    top = str(repo).strip().split("/")[-1]
    if top and parts and parts[0] != top:
        return f"{top}/{path}"
    return path


# Junk / distractor paths often scraped from problem prose (curator + runtime).
_BAD_TARGET_PATH_RE = re.compile(
    r"(^|/)"
    r"(?:manage\.py|settings/py\.py|models/py\.py|self/|Field/|View/|Engine/|"
    r"Query/|Axes/|FigureCanvasBase/|OffsetBox/|MigrationAutodetector/|"
    r"ProductMetaData/|custom_lookups/|RelatedFieldListFilter\.py)"
    r"|^(?:a|b)/"
    r"|site-packages/"
    r"|/\.venv/"
    r"|\.css(?:\.|$)"
    r"|/css/"
)


def _normalize_repo_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


_OLD_F2P_RE = re.compile(
    r"\((?P<mod>[a-z][a-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+)\)\s*$"
)


def _dotted_mod_to_test_path(mod: str) -> str | None:
    """Map ``servers.tests`` / ``test_utils.tests`` → ``tests/.../*.py`` (never gold)."""
    parts = [p for p in mod.split(".") if p]
    if len(parts) < 2:
        return None
    # Drop trailing CamelCase test class segment if present (OverrideSettingsTests).
    if parts and re.match(r"^[A-Z]", parts[-1]):
        parts = parts[:-1]
    if len(parts) < 2:
        return None
    return "tests/" + "/".join(parts) + ".py"


def paths_from_fail_to_pass(val: Any) -> list[str]:
    """Map FAIL_TO_PASS nodeids → repo-relative test .py paths (never gold).

    Supports modern ``path/to/test.py::Class::test`` and legacy
    ``test_name (package.module.Class)`` nodeids.
    """
    out: list[str] = []
    seen: set[str] = set()
    for node in fail_to_pass_list(val):
        raw = str(node).strip()
        if not raw:
            continue
        path = ""
        head = raw.split("::", 1)[0].strip()
        if head.endswith(".py"):
            path = _normalize_repo_path(head)
        else:
            m = _OLD_F2P_RE.search(raw)
            if m:
                mapped = _dotted_mod_to_test_path(m.group("mod"))
                if mapped:
                    path = _normalize_repo_path(mapped)
        if not path.endswith(".py") or path in seen:
            continue
        seen.add(path)
        out.append(path)
    return out


def _is_test_path(path: str) -> bool:
    """True for project tests/ or framework django/test/ paths (edit distractors)."""
    p = _normalize_repo_path(path)
    if p.startswith("tests/") or "/tests/" in p:
        return True
    if p.startswith("django/test/") or p.startswith("django/tests/"):
        return True
    return False


def plausible_target_paths(paths: list[str], repo: str | None) -> list[str]:
    """Drop junk / out-of-tree guesses; keep repo-rooted or tests/src/lib paths."""
    top = (repo or "").strip().split("/")[-1].lower() if repo else ""
    good: list[str] = []
    seen: set[str] = set()
    for raw in paths:
        p = _normalize_repo_path(str(raw))
        if not p or p in seen:
            continue
        if not p.endswith(".py"):
            continue
        if p.endswith("/py.py") or p.endswith(".py.py"):
            continue
        if _BAD_TARGET_PATH_RE.search(p):
            continue
        if p.count("/") < 1:
            continue
        if p.startswith(("a/", "b/")):
            continue
        if top and not (
            p.startswith(f"{top}/")
            or p.startswith("tests/")
            or p.startswith("src/")
            or p.startswith("lib/")
        ):
            continue
        parts = p.split("/")
        if any(re.match(r"^[A-Z][A-Za-z0-9]+$", seg) for seg in parts[:-1]):
            continue
        seen.add(p)
        good.append(p)
    return good


def _f2p_related(path: str, f2p_paths: list[str]) -> bool:
    """True when path is a FAIL_TO_PASS test file or shares a package prefix."""
    p = _normalize_repo_path(path)
    for fp in f2p_paths:
        if p == fp:
            return True
        # tests/migrations/test_executor.py ↔ django/db/migrations/executor.py
        fp_parts = [x for x in fp.split("/") if x and x != "tests"]
        p_parts = [x for x in p.split("/") if x and x != "tests"]
        if len(fp_parts) >= 2 and len(p_parts) >= 2:
            # shared parent dir name (migrations, auth, …) in both
            fp_dirs = {x for x in fp_parts[:-1] if not x.startswith("test")}
            p_dirs = {x for x in p_parts[:-1] if not x.startswith("test")}
            if fp_dirs & p_dirs:
                return True
        stem = Path(fp).stem
        if stem.startswith("test_"):
            stem = stem[5:]
        if stem and stem in p and ("/" + stem + ".py" in "/" + p or p.endswith("/" + stem + ".py")):
            return True
    return False


# Django settings tokens in issue prose often mean conf/global_settings.py.
_SETTINGS_HINT_RE = re.compile(
    r"\b(?:"
    r"FILE_UPLOAD_[A-Z0-9_]+|"
    r"[A-Z][A-Z0-9_]{2,}_(?:PERMISSIONS|DIRS|ROOT|URL|BACKENDS|MIDDLEWARE|HANDLERS)"
    r")\b"
)


def guess_target_paths(row: dict[str, Any], *, limit: int = 2) -> list[str]:
    """Infer likely edit paths from unpaid instance text only (never gold patch).

    Prefers FAIL_TO_PASS–related **primary** (non-test) paths over test files and
    problem-statement distractors; filters junk via ``plausible_target_paths``.
    Uses explicit paths, GitHub blob URLs, module phrases, and legacy F2P
    nodeids. Does not read ``patch`` / ``test_patch``. Default limit is 2 so
    docker-cp / edit prompts stay focused (fewer mixed-file malformed hunks).
    """
    texts = [
        str(row.get("problem_statement") or ""),
        str(row.get("hints_text") or ""),
    ]
    repo = row.get("repo")
    repo_s = str(repo).strip() if repo else ""
    repo_owner = repo_s.split("/")[0].lower() if "/" in repo_s else ""
    repo_name = repo_s.split("/")[-1].lower() if repo_s else ""
    f2p_paths = paths_from_fail_to_pass(row.get("FAIL_TO_PASS"))
    same_repo_blobs: list[str] = []
    other_blobs: list[str] = []
    prose_paths: list[str] = []

    for text in texts:
        for match in _GITHUB_BLOB_PATH_RE.finditer(text):
            path = match.group("path")
            owner = (match.group("owner") or "").lower()
            rname = (match.group("repo") or "").lower()
            if repo_owner and repo_name and owner == repo_owner and rname == repo_name:
                same_repo_blobs.append(path)
            else:
                other_blobs.append(path)
        for match in _FILE_PATH_RE.finditer(text):
            prose_paths.append(match.group(1))
        for match in _MODULE_HINT_RE.finditer(text):
            prose_paths.append(
                _module_to_repo_path(match.group(1), str(repo) if repo else None)
            )
        if repo_name == "django" and _SETTINGS_HINT_RE.search(text):
            prose_paths.append("django/conf/global_settings.py")

    # Rank: F2P-related primary → other primary → F2P tests → other tests →
    # third-party. Never lead with test/framework paths when a related primary
    # exists (logged apply fails often mix test hunks into production files).
    ranked: list[str] = []
    seen: set[str] = set()

    def _extend(candidates: list[str]) -> None:
        for raw in candidates:
            p = _normalize_repo_path(raw)
            if not p or p in seen:
                continue
            seen.add(p)
            ranked.append(p)

    pool = same_repo_blobs + prose_paths
    related_primary = [
        p for p in pool if not _is_test_path(p) and _f2p_related(p, f2p_paths)
    ]
    other_primary = [p for p in pool if not _is_test_path(p)]
    related_tests = [
        p for p in pool if _is_test_path(p) and _f2p_related(p, f2p_paths)
    ]
    other_tests = [p for p in pool if _is_test_path(p)]

    _extend(related_primary)
    _extend(other_primary)
    _extend(f2p_paths)
    _extend(related_tests)
    _extend(other_tests)
    _extend(other_blobs)

    filtered = plausible_target_paths(ranked, str(repo) if repo else None)
    # When any primary path exists, drop test/framework paths from the edit set —
    # logged apply fails often patch tests badly after the production hunk lands
    # (e.g. 10914: global_settings ok, tests/test_utils hunk FAILED).
    primaries = [p for p in filtered if not _is_test_path(p)]
    if primaries:
        filtered = primaries[: max(0, limit)]
    else:
        filtered = filtered[: max(0, limit)]
    # FAIL_TO_PASS test paths can be the best docker-cp signal even when they
    # fail the "primary source" heuristic; keep them if still plausible-or-tests.
    if not filtered and f2p_paths:
        filtered = plausible_target_paths(f2p_paths, str(repo) if repo else None)[
            : max(0, limit)
        ]
    return filtered


def instance_turn_context(row: dict[str, Any]) -> str:
    """Flashlight turn context from SWE-bench instance fields. Never includes gold diffs."""
    iid = str(row.get("instance_id") or "")
    parts = [f"instance: {iid}"] if iid else []
    repo = row.get("repo")
    if repo:
        parts.append(f"repo: {repo}")
    version = row.get("version")
    if version:
        parts.append(f"version: {version}")
    commit = row.get("base_commit")
    if commit:
        parts.append(f"base_commit: {commit}")
    problem = str(row.get("problem_statement") or "").strip()
    if problem:
        parts.append("problem_statement:\n" + problem)
    hints = str(row.get("hints_text") or "").strip()
    if hints:
        parts.append("hints:\n" + hints)
    f2p = fail_to_pass_list(row.get("FAIL_TO_PASS"))
    if f2p:
        parts.append("FAIL_TO_PASS tests (must pass after the fix):\n" + "\n".join(f2p))
    # Prefer exact docker-cp'd paths so the edit prompt matches copied bytes.
    file_map = row.get("target_file_contents")
    copied_paths: list[str] = []
    if isinstance(file_map, dict) and file_map:
        copied_paths = [str(k) for k, v in file_map.items() if str(v).strip()]
    targets = copied_paths or guess_target_paths(row)
    if targets:
        parts.append(
            "likely_target_files (patch against these paths; do not invent other paths):\n"
            + "\n".join(targets)
        )
    # Optional real file bytes (docker_cp / git / tests). Never gold patch.
    if copied_paths:
        from .docker_file_context import format_file_contents

        block = format_file_contents(
            {str(k): str(v) for k, v in file_map.items() if str(v).strip()}
        )
        if block:
            parts.append(block)
    return "\n\n".join(parts) if parts else f"instance: {iid}"


def fetch_bench_ids(
    bench: str,
    n: int = 30,
    cap: int | None = None,
    cache_dir: str = "data/lite_cache",
) -> list[str]:
    """Deterministic first-N instance ids from Lite or Verified (HF free; no aiand credits)."""
    bench = bench.lower().strip()
    if bench in {"lite", "swe-bench-lite", "swe_lite"}:
        dataset = "princeton-nlp/SWE-bench_Lite"
        cache_name = "lite_ids.json"
        hard_cap = CAP if cap is None else cap
    elif bench in {"verified", "swe-bench-verified", "swe_verified"}:
        dataset = "SWE-bench/SWE-bench_Verified"
        cache_name = "verified_ids.json"
        # Unpaid id scaffold may request promotion-scale n; live HTTP still clamped by CAP.
        hard_cap = 500 if cap is None else cap
    else:
        raise ValueError(f"unknown bench {bench!r}; use lite|verified")
    n = min(n, hard_cap)
    cache_path = Path(cache_dir) / cache_name
    ids: list[str] = []
    if cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if len(cached) >= n:
            return cached[:n]
        ids = list(cached)
    url = "https://datasets-server.huggingface.co/rows"
    length = 100
    offset = len(ids)
    while len(ids) < n:
        params = {
            "dataset": dataset,
            "config": "default",
            "split": "test",
            "offset": offset,
            "length": min(length, n - len(ids)),
        }
        resp = httpx.get(url, params=params, timeout=30.0)
        resp.raise_for_status()
        batch = [row["row"]["instance_id"] for row in resp.json().get("rows", [])]
        if not batch:
            break
        ids.extend(batch)
        offset += len(batch)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(ids), encoding="utf-8")
    return ids[:n]


def fetch_lite_ids(
    n: int = 30, cap: int = CAP, cache_dir: str = "data/lite_cache"
) -> list[str]:
    """Deterministic first-N instance ids of SWE-bench_Lite, cached to disk."""
    return fetch_bench_ids("lite", n=n, cap=cap, cache_dir=cache_dir)


def fetch_bench_rows(
    bench: str,
    n: int = 500,
    cap: int | None = None,
    cache_dir: str = "data/lite_cache",
) -> list[dict[str, Any]]:
    """Full SWE-bench rows (problem_statement, FAIL_TO_PASS, …) from HF, cached JSONL.

    Unpaid datasets-server only. Gold `patch` / `test_patch` may be present on disk
    but must not be sent to the model (see instance_turn_context).
    """
    bench = bench.lower().strip()
    if bench in {"lite", "swe-bench-lite", "swe_lite"}:
        dataset = "princeton-nlp/SWE-bench_Lite"
        cache_name = "lite_rows.jsonl"
        hard_cap = CAP if cap is None else cap
    elif bench in {"verified", "swe-bench-verified", "swe_verified"}:
        dataset = "SWE-bench/SWE-bench_Verified"
        cache_name = "verified_rows.jsonl"
        hard_cap = 500 if cap is None else cap
    else:
        raise ValueError(f"unknown bench {bench!r}; use lite|verified")
    n = min(n, hard_cap)
    cache_path = Path(cache_dir) / cache_name
    rows: list[dict[str, Any]] = []
    if cache_path.exists():
        for line in cache_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
        if len(rows) >= n:
            return rows[:n]
    url = "https://datasets-server.huggingface.co/rows"
    length = 100
    offset = len(rows)
    while len(rows) < n:
        params = {
            "dataset": dataset,
            "config": "default",
            "split": "test",
            "offset": offset,
            "length": min(length, n - len(rows)),
        }
        resp = httpx.get(url, params=params, timeout=30.0)
        resp.raise_for_status()
        batch = []
        for item in resp.json().get("rows", []):
            row = item.get("row", item) if isinstance(item, dict) else {}
            if isinstance(row, dict):
                batch.append(row)
        if not batch:
            break
        rows.extend(batch)
        offset += len(batch)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
    )
    return rows[:n]


def write_ids_scaffold(
    ids: list[str],
    *,
    bench: str,
    out_path: Path,
) -> dict[str, Any]:
    """Write unpaid id-list scaffold for session-gold promotion plumbing (no HTTP runs)."""
    summary = {
        "verdict": "ids_scaffold_only",
        "bench": bench,
        "n": len(ids),
        "session_gold": False,
        "production_parity": False,
        "paid_http_required": True,
        "note": (
            "HF datasets-server id fetch only. Live flashlight/session resolve "
            "still requires gateway credits and a real harness."
        ),
        "instance_ids": ids,
    }
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def _validate_fixture_row(row: dict[str, Any], index: int) -> dict[str, Any]:
    if "instance_id" not in row:
        raise ValueError(f"fixture row {index} missing instance_id")
    policies = row.get("policies")
    if policies is None:
        return row
    if not isinstance(policies, dict) or not policies:
        raise ValueError(f"fixture row {index} has empty or invalid policies")
    for name, policy in policies.items():
        if not isinstance(policy, dict):
            raise ValueError(f"fixture row {index} policy {name!r} must be an object")
    return row


def _load_fixture(path: str) -> list[dict[str, Any]]:
    """Load fixture JSON; each row must have instance_id."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [_validate_fixture_row(row, i) for i, row in enumerate(data)]


def _fixture_gateway(row: dict[str, Any]) -> Callable[[str, str], str]:
    """Stub gateway: returns pre-baked patch for edit/debug, empty for others."""
    patch = row.get("patch", "")

    def _chat(phase: str, content: str) -> str:
        if phase in ("edit", "debug"):
            return f"```python\n{patch}\n```"
        return ""

    return _chat


def _merge_policy_row(row: dict[str, Any], policy_row: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(row)
    merged.pop("policies", None)
    for key, value in policy_row.items():
        merged[key] = value
    return merged


def _run_fixture_policy(policy_row: dict[str, Any]) -> bool:
    meta: dict[str, Any] = {"verify_pytest": True}
    meta["module"] = policy_row.get("module", "fix.py")
    meta["tests"] = policy_row.get("tests")
    gateway_fn = _fixture_gateway(policy_row)
    context = instance_turn_context(policy_row)
    return _run_turn_loop(gateway_fn, context, meta)


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


def summarize_comparison(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize fixture_replay dual-policy JSONL rows (rules vs trained).

    Honest labels only: harness_proxy / bounded_check_only. Does not claim
    session gold or production parity.
    """
    comparison_rows = [
        r for r in rows if r.get("comparison_mode") == "fixture_replay" and isinstance(r.get("policies"), dict)
    ]
    n = len(comparison_rows)
    policy_names = ("rules", "trained")
    counts = {name: 0 for name in policy_names}
    both_pass = both_fail = rules_only = trained_only = 0
    for row in comparison_rows:
        policies = row["policies"]
        resolved = {
            name: bool((policies.get(name) or {}).get("resolved")) for name in policy_names
        }
        for name in policy_names:
            if resolved[name]:
                counts[name] += 1
        if resolved["rules"] and resolved["trained"]:
            both_pass += 1
        elif not resolved["rules"] and not resolved["trained"]:
            both_fail += 1
        elif resolved["rules"]:
            rules_only += 1
        else:
            trained_only += 1

    def _rate(k: int) -> float | None:
        return (k / n) if n else None

    return {
        "verdict": "bounded_check_only",
        "label_type": "harness_proxy",
        "comparison_mode": "fixture_replay",
        "n": n,
        "rules_resolved": counts["rules"],
        "trained_resolved": counts["trained"],
        "rules_resolve_rate": _rate(counts["rules"]),
        "trained_resolve_rate": _rate(counts["trained"]),
        "delta_pp": (
            None
            if n == 0
            else round(100.0 * (counts["trained"] - counts["rules"]) / n, 1)
        ),
        "both_pass": both_pass,
        "both_fail": both_fail,
        "rules_only": rules_only,
        "trained_only": trained_only,
        "production_parity": False,
        "session_gold": False,
    }


def format_comparison_report(summary: dict[str, Any], *, fixture_path: str | None = None) -> str:
    """Markdown report for an unpaid synthetic dual-policy Lite comparison."""
    n = int(summary.get("n") or 0)
    rules_n = int(summary.get("rules_resolved") or 0)
    trained_n = int(summary.get("trained_resolved") or 0)
    rules_rate = summary.get("rules_resolve_rate")
    trained_rate = summary.get("trained_resolve_rate")
    delta = summary.get("delta_pp")
    fixture_line = f"- Fixture: `{fixture_path}`\n" if fixture_path else ""

    def _pct(rate: float | None, k: int) -> str:
        if rate is None:
            return "n/a"
        return f"{k}/{n} ({100.0 * rate:.1f}%)"

    return (
        "# Lite dual-policy comparison (synthetic)\n\n"
        f"**Verdict**: `{summary.get('verdict', 'bounded_check_only')}`\n\n"
        f"{fixture_line}"
        f"- `label_type`: `{summary.get('label_type', 'harness_proxy')}`\n"
        f"- `comparison_mode`: `{summary.get('comparison_mode', 'fixture_replay')}`\n"
        f"- n={n} (<< session-gold floor 300)\n\n"
        "## Resolve rates (harness-proxy)\n\n"
        f"- rules: **{_pct(rules_rate, rules_n)}**\n"
        f"- trained: **{_pct(trained_rate, trained_n)}**\n"
        f"- trained − rules: **{delta if delta is not None else 'n/a'} pp** "
        "(synthetic fixture delta only)\n\n"
        "## Contingency\n\n"
        f"- both pass: {summary.get('both_pass', 0)}\n"
        f"- both fail: {summary.get('both_fail', 0)}\n"
        f"- rules only: {summary.get('rules_only', 0)}\n"
        f"- trained only: {summary.get('trained_only', 0)}\n\n"
        "## Honesty\n\n"
        "- `production_parity=false` — not SWE-bench Lite/Verified session gold.\n"
        "- Patches are hand-authored dual-policy fixtures, not live gateway routes.\n"
        "- Does **not** justify flipping `TRAINED_PATH`.\n"
    )


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
        if fixture:
            row = fixture_map.get(instance_id, {})
            policies = row.get("policies")
            if policies:
                results: dict[str, dict[str, Any]] = {}
                for name, policy_row in policies.items():
                    merged = _merge_policy_row(row, policy_row)
                    results[name] = {"resolved": _run_fixture_policy(merged)}
                rows.append(
                    {
                        "instance_id": instance_id,
                        "label_type": "harness_proxy",
                        "comparison_mode": "fixture_replay",
                        "policies": results,
                    }
                )
                print(
                    "  "
                    + instance_id
                    + ": "
                    + ", ".join(f"{name}={data['resolved']}" for name, data in results.items())
                )
                continue
            resolved = _run_fixture_policy(row)
        else:
            assert client is not None
            gateway_fn = _http_gateway(client, "change-me")
            context = f"instance: {instance_id}"
            resolved = _run_turn_loop(gateway_fn, context, {"verify_pytest": True})
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
    parser.add_argument(
        "--bench",
        default="lite",
        choices=("lite", "verified"),
        help="HF bench for id fetch (default lite). verified is unpaid scaffold only.",
    )
    parser.add_argument(
        "--ids-only",
        action="store_true",
        help=(
            "Unpaid: fetch/cache instance ids and write a JSON scaffold. "
            "No gateway HTTP. Does not claim session gold."
        ),
    )
    parser.add_argument(
        "--promotion-readiness",
        action="store_true",
        help=(
            "Unpaid: validate Verified ids scaffold + print runbook §(a) gate checklist "
            "and dual-policy run plan (no HTTP)."
        ),
    )
    args = parser.parse_args(argv)

    if args.promotion_readiness:
        from .promotion_gate import main as promotion_main

        out = Path(args.out)
        if out.suffix == ".jsonl":
            out = out.with_suffix(".json")
        promo_argv = [
            "--scaffold",
            str(out),
            "--artifact",
            str(ROOT / "data" / "scorer-hard-logistic.json"),
        ]
        return promotion_main(promo_argv)

    if args.ids_only:
        ids = fetch_bench_ids(args.bench, n=args.n)
        out = Path(args.out)
        if out.suffix == ".jsonl":
            out = out.with_suffix(".json")
        summary = write_ids_scaffold(ids, bench=args.bench, out_path=out)
        print(
            f"ids_scaffold bench={summary['bench']} n={summary['n']} -> {out} "
            f"(session_gold=false; paid HTTP still required)",
            flush=True,
        )
        return 0

    if args.n > CAP:
        print(f"clamping --n {args.n} to cap {CAP}", file=sys.stderr)
        args.n = CAP

    if args.fixture:
        fixture = _load_fixture(args.fixture)
        ids = [r["instance_id"] for r in fixture][: args.n]
        run_slice(ids, None, args.out, fixture=fixture)
    else:
        if args.bench != "lite":
            print(
                "refusing: live HTTP path is Lite-only; use --ids-only for Verified scaffold",
                file=sys.stderr,
            )
            return 2
        ids = fetch_lite_ids(n=args.n)
        run_slice(ids, args.gateway, args.out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
