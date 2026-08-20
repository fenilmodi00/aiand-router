"""Verified session-gold runner plumbing (runbook §(a)).

Runs flashlight-style turn loops against a live gateway in shadow mode, with
budget guards and ids from the Verified scaffold. Loads SWE-bench Verified
instance fields (problem_statement, hints, FAIL_TO_PASS, repo) into turns when
a dump/cache/HF row is available. Gateway request rows land in the gateway log;
this module writes per-instance session summaries for eval.

Honest resolve labels only:
- harness_proxy — local pytest when instance.tests is present
- session_gold — only when SWE_EVAL_CMD returns a bool (docker/eval hook)
- offline_gold — unpaid join via --offline-gold (not live SWE eval)
- needs_swe_eval — resolved=null (do not treat as measured 0%)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

import httpx

from dotenv import load_dotenv

from .docker_file_context import ensure_target_file_contents
from .lite_runner import (
    ROOT,
    _load_fixture,
    _merge_policy_row,
    _run_fixture_policy,
    _write_jsonl,
    fetch_bench_rows,
    fail_to_pass_list,
    guess_target_paths,
    instance_turn_context,
    write_ids_scaffold,
)
from .promotion_gate import VERIFIED_PRIMARY_N, estimate_gate_budget, load_ids_scaffold
from .router import SpendLog, load_config, load_models
from .train import _pytest_verify

VERIFIED_CAP = VERIFIED_PRIMARY_N
DEFAULT_SCAFFOLD = ROOT / "data" / "verified_ids_scaffold.json"
DEFAULT_SPEND = ROOT / "data" / "spend.txt"
DEFAULT_OUT = ROOT / "data" / "verified_session_results.jsonl"
DEFAULT_INSTANCES = ROOT / "data" / "dump_cache" / "swe_verified.jsonl"
DEFAULT_ROWS_CACHE = ROOT / "data" / "lite_cache"

GATEWAY_START_CMD = (
    "$env:PYTHONPATH='src'; $env:TRAINED_PATH='shadow'; "
    "$env:SCORER_PATH='data/scorer-hard-logistic.json'; "
    "uvicorn aiand_router.app:app --app-dir src --host 127.0.0.1 --port 8000"
)

SWE_EVAL_NOTE = (
    "true SWE-bench resolve requires docker eval of FAIL_TO_PASS in the repo "
    "(set SWE_EVAL_CMD with {instance_id} and {patch_file}); flashlight pytest "
    "has no test body for Verified instances"
)

# Verified sessions feed SWE_EVAL_CMD a model_patch; ask for unified diffs, not module text.
_EDIT_DIFF_BASE = (
    "Write a minimal unified-diff git patch that fixes the issue, inside a ```diff fence. "
    "Include diff --git / --- / +++ headers and @@ hunks against real repo paths. "
    "Every hunk body line MUST start with exactly one of: space (context), '+' (add), "
    "or '-' (remove). @@ old_count/new_count must equal the number of those lines. "
    "Copy context lines VERBATIM from file_contents — do not invent, reorder, or "
    "duplicate. Prefer one production file; do not paste test-file hunks into a "
    "production-file diff. Change only what FAIL_TO_PASS requires. Do not write a full module."
)
_DEBUG_DIFF_BASE = (
    "The previous patch failed to apply (often malformed hunks: missing leading "
    "space/+/- on a line, wrong @@ counts, or test content mixed into a production "
    "file). Write a corrected minimal unified-diff git patch only, inside a ```diff fence. "
    "Every hunk line starts with space, '+', or '-'; counts match; context from "
    "file_contents only; one production file preferred."
)
_VERIFIED_TURNS = [
    (
        "discover",
        "Using the instance fields above (repo, version, FAIL_TO_PASS, hints, problem "
        "statement, likely_target_files if present), list what the tests expect and which "
        "files are likely involved. Do not invent a gold patch.",
    ),
    (
        "plan",
        "Plan the smallest fix against the likely target files. Do not write code yet.",
    ),
    ("edit", _EDIT_DIFF_BASE),
    ("debug", _DEBUG_DIFF_BASE),
    ("summarize", "One paragraph: what broke, what you changed."),
]
_TURNS = _VERIFIED_TURNS



def _debug_instruction_with_harness_feedback(
    instance: dict[str, Any],
    prior_out: dict[str, Any] | None = None,
) -> str:
    """Debug turn text; append truncated prior swe_eval_detail when present."""
    base = verified_turn_instruction("debug", instance)
    if not prior_out:
        return base
    detail = str(prior_out.get("swe_eval_detail") or "").strip()
    reason = str(prior_out.get("swe_eval_reason") or "").strip()
    if not detail and not reason:
        return base
    # Keep token cost low: prefer apply/malformed lines, else tail of detail.
    lines = [ln for ln in detail.splitlines() if ln.strip()]
    keep = [
        ln
        for ln in lines
        if any(
            k in ln.lower()
            for k in (
                "patch apply",
                "malformed",
                "hunk #",
                "failed",
                "patching file",
                "rejects",
            )
        )
    ]
    snippet = "\n".join(keep[-12:] if keep else lines[-8:])
    if len(snippet) > 900:
        snippet = snippet[-900:]
    bits = []
    if reason:
        bits.append(f"reason={reason}")
    if snippet:
        bits.append(snippet)
    return (
        base
        + "\n\nPrior harness feedback (fix the patch; do not repeat the same "
        "malformed hunks or test-file edits):\n"
        + "\n".join(bits)
    )


def verified_turn_instruction(phase: str, instance: dict[str, Any] | None = None) -> str:
    """Phase instruction for Verified sessions; appends target paths when known."""
    base = dict(_VERIFIED_TURNS).get(phase) or ""
    if phase not in {"edit", "debug"} or not instance:
        return base
    # Prefer exact docker-cp keys so the model patches the copied files.
    file_map = instance.get("target_file_contents")
    if isinstance(file_map, dict) and file_map:
        targets = [str(k) for k, v in file_map.items() if str(v).strip()]
    else:
        targets = guess_target_paths(instance)
    if not targets:
        return base
    return (
        base
        + " Patch these path(s) explicitly: "
        + ", ".join(targets)
        + "."
    )

_DIFF_FENCE_RE = re.compile(
    r"```(?:diff|patch|udiff)\b[^\n]*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)
_PYTHON_FENCE_RE = re.compile(
    r"```(?:python|py)\b[^\n]*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)
_GENERIC_FENCE_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)


def looks_like_unified_diff(text: str) -> bool:
    """True when text looks like a git/unified patch (not a bare Python module)."""
    t = (text or "").strip()
    if not t:
        return False
    if t.startswith("diff --git ") or t.startswith("--- "):
        return True
    if "\ndiff --git " in t:
        return True
    if ("\n--- " in t or t.startswith("--- ")) and ("\n+++ " in t or "\n+++" in t):
        return True
    return False


_HUNK_HDR_RE = re.compile(
    r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@(.*)$"
)
_PROSE_LINE_RE = re.compile(
    r"^(?:thanks|here|note|hope|let me|i |this |the patch|sorry|please|"
    r"explanation|summary)\b",
    re.IGNORECASE,
)


def _looks_like_trailing_prose(line: str) -> bool:
    """True when a marker-less line is trailing chat prose, not code context."""
    s = line.strip()
    if not s:
        return False
    if _PROSE_LINE_RE.match(s):
        return True
    if s.endswith(("!", "?", ".")) and (" " in s or len(s) < 24):
        return True
    # Multi-word English without code punctuation
    if " " in s and not re.search(r"[=(){}[\]./\\:#]", s):
        return True
    return False


def normalize_unified_diff(patch: str) -> str:
    """Repair common model-patch malformations that cause Patch Apply Failed.

    - Strip trailing prose after the last diff line
    - Ensure hunk body lines start with space / + / - / \\
    - Recompute @@ old/new line counts from the body
    - Ensure a trailing newline

    Does not invent file paths or change +/-/context text beyond a missing
    leading marker. Never consults gold patches.
    """
    raw = (patch or "").replace("\r\n", "\n").replace("\r", "\n")
    if not raw.strip():
        return raw

    lines = raw.split("\n")
    # Drop leading prose before first diff header.
    start = 0
    for i, line in enumerate(lines):
        if line.startswith(("diff --git ", "--- ")):
            start = i
            break
    lines = lines[start:]

    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Stop at obvious trailing prose (no diff markers).
        if (
            out
            and line
            and not line.startswith(
                ("diff --git ", "--- ", "+++ ", "@@", " ", "+", "-", "\\")
            )
            and not line.startswith("index ")
            and not line.startswith("new file ")
            and not line.startswith("deleted file ")
            and not line.startswith("old mode ")
            and not line.startswith("new mode ")
            and not line.startswith("similarity ")
            and not line.startswith("rename ")
            and not line.startswith("copy ")
        ):
            break

        hm = _HUNK_HDR_RE.match(line)
        if hm:
            body: list[str] = []
            j = i + 1
            while j < len(lines):
                bl = lines[j]
                if bl.startswith(("diff --git ", "--- ", "+++ ", "@@")):
                    break
                if bl == "":
                    bl = " "
                elif not bl.startswith((" ", "+", "-", "\\")):
                    if _looks_like_trailing_prose(bl):
                        break
                    bl = " " + bl
                body.append(bl)
                j += 1
            while body and body[-1] in {"", " "}:
                body.pop()
            old_n = sum(
                1 for b in body if b.startswith((" ", "-")) and not b.startswith("\\")
            )
            new_n = sum(
                1 for b in body if b.startswith((" ", "+")) and not b.startswith("\\")
            )
            trail = hm.group(5) or ""
            out.append(f"@@ -{hm.group(1)},{old_n} +{hm.group(3)},{new_n} @@{trail}")
            out.extend(body)
            i = j
            continue

        out.append(line)
        i += 1

    text = "\n".join(out).rstrip("\n") + "\n"
    return text


def extract_unified_diff(text: str) -> tuple[str | None, str | None]:
    """Extract a unified-diff model_patch from model output.

    Returns ``(patch, None)`` or ``(None, reason)``. Does not invent a patch from
    fenced Python — that is not convertible without repo context. Applies
    ``normalize_unified_diff`` so common malformed hunks are less likely to
    fail ``patch`` apply.
    """
    raw = text or ""
    if not raw.strip():
        return None, "empty_patch"

    def _finish(body: str) -> tuple[str, None]:
        fixed = normalize_unified_diff(body)
        return (fixed if fixed.endswith("\n") else fixed + "\n"), None

    for body in _DIFF_FENCE_RE.findall(raw):
        body = body.strip("\n")
        if not body.strip():
            continue
        if looks_like_unified_diff(body) or "@@" in body:
            return _finish(body)

    stripped = raw.strip()
    if looks_like_unified_diff(stripped):
        # Prefer from first diff --git / --- header if prose wraps the patch.
        for marker in ("diff --git ", "--- "):
            idx = stripped.find(marker)
            if idx >= 0:
                return _finish(stripped[idx:])
        return _finish(stripped)

    for body in _GENERIC_FENCE_RE.findall(raw):
        body = body.strip("\n")
        if looks_like_unified_diff(body) or (
            "@@" in body and ("---" in body or "+++" in body)
        ):
            return _finish(body)

    if _PYTHON_FENCE_RE.search(raw):
        return None, "patch_not_unified_diff"

    return None, "patch_not_unified_diff"



def _router_api_key() -> str:
    return os.getenv("ROUTER_API_KEY", "change-me")


def _index_instance_rows(path: Path) -> dict[str, dict[str, Any]]:
    """Index JSON/JSONL dump rows by instance_id."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    rows: list[Any]
    if path.suffix == ".json" and not str(path).endswith(".jsonl"):
        data = json.loads(text)
        if isinstance(data, dict) and data.get("instance_id"):
            rows = [data]
        elif isinstance(data, dict):
            rows = list(data.get("instances") or data.get("rows") or [])
        elif isinstance(data, list):
            rows = data
        else:
            rows = []
    else:
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and row.get("instance_id"):
            out[str(row["instance_id"])] = row
    return out


def load_verified_instances(
    ids: list[str],
    *,
    dump_path: Path | None = None,
    cache_dir: Path | None = None,
    fetch: bool = True,
) -> dict[str, dict[str, Any]]:
    """Load SWE-bench Verified instance JSON by id from dump, cache, or unpaid HF.

    Does not use dump `resolved` or gold `patch` as session gold.
    """
    wanted = [str(i) for i in ids]
    found: dict[str, dict[str, Any]] = {}
    cache = Path(cache_dir) if cache_dir is not None else DEFAULT_ROWS_CACHE

    if dump_path is not None:
        found.update(_index_instance_rows(Path(dump_path)))
    else:
        found.update(_index_instance_rows(DEFAULT_INSTANCES))
        found.update(_index_instance_rows(cache / "verified_rows.jsonl"))

    missing = [i for i in wanted if i not in found]
    if missing and fetch:
        for row in fetch_bench_rows("verified", n=500, cache_dir=str(cache)):
            iid = str(row.get("instance_id") or "")
            if iid:
                found[iid] = row
    return {i: found[i] for i in wanted if i in found}


def load_offline_gold(path: Path) -> dict[str, dict[str, Any]]:
    """instance_id → gold row (`resolved` and/or `policies`). Not live SWE eval."""
    indexed = _index_instance_rows(Path(path))
    if indexed:
        return indexed
    text = Path(path).read_text(encoding="utf-8").strip()
    data = json.loads(text)
    if isinstance(data, dict) and not data.get("instance_id"):
        out: dict[str, dict[str, Any]] = {}
        for key, val in data.items():
            if isinstance(val, dict):
                out[str(key)] = val
            else:
                out[str(key)] = {"instance_id": str(key), "resolved": val}
        return out
    return {}


def instance_field_flags(instance: dict[str, Any]) -> dict[str, bool]:
    file_map = instance.get("target_file_contents")
    return {
        "has_problem_statement": bool(str(instance.get("problem_statement") or "").strip()),
        "has_hints": bool(str(instance.get("hints_text") or "").strip()),
        "has_fail_to_pass": bool(fail_to_pass_list(instance.get("FAIL_TO_PASS"))),
        "has_repo": bool(instance.get("repo")),
        "has_target_paths": bool(guess_target_paths(instance)),
        "has_file_contents": bool(isinstance(file_map, dict) and file_map),
        "has_pytest_tests": bool(instance.get("tests")),
    }


def verified_turn_context(instance: dict[str, Any]) -> str:
    """Instance turn context with optional docker_cp/git file excerpts (never gold)."""
    enriched = ensure_target_file_contents(instance)
    return instance_turn_context(enriched)


def _parse_swe_eval_payload(out: str) -> tuple[bool | None, dict[str, Any]]:
    """Map SWE_EVAL_CMD stdout → (resolved, meta). Meta may include reason/detail."""
    meta: dict[str, Any] = {}
    text = (out or "").strip()
    if not text:
        return None, meta
    last = text.splitlines()[-1].strip()
    low = last.lower()
    if low in {"true", "1", "resolved=true"}:
        return True, meta
    if low in {"false", "0", "resolved=false"}:
        return False, meta
    for candidate in (text, last):
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        for key in ("reason", "status", "failure_reason", "detail"):
            val = obj.get(key)
            if val is None or val == "":
                continue
            if key == "detail":
                meta[key] = str(val)[-800:]
            else:
                meta[key] = val
        status = str(obj.get("status") or "").lower()
        if status in {"not_available", "error", "skipped"}:
            if "reason" not in meta and status:
                meta["reason"] = status
            return None, meta
        if "resolved" not in obj:
            continue
        val = obj["resolved"]
        if val is None:
            return None, meta
        if isinstance(val, bool):
            return val, meta
        if isinstance(val, (int, float)) and val in (0, 1):
            return bool(val), meta
        if isinstance(val, str) and val.strip().lower() in {"true", "false"}:
            return val.strip().lower() == "true", meta
    return None, meta


def _parse_swe_eval_stdout(out: str) -> bool | None:
    """Map SWE_EVAL_CMD stdout → resolved bool, or None if unlabeled/unavailable.

    ``{\"resolved\": null, \"status\": \"not_available\"}`` must stay unlabeled
    (never bool(None) → False fake fail).
    """
    return _parse_swe_eval_payload(out)[0]


def _run_swe_eval_cmd(
    instance_id: str, patch_text: str
) -> tuple[bool | None, dict[str, Any]]:
    """Optional operator docker/eval hook. Unset → unlabeled (not a fake fail).

    SWE_EVAL_CMD is a format string with {instance_id} and {patch_file}.
    Stdout: true/false, or JSON {\"resolved\": bool|null}. Non-parse → None.
    Prefer: ``python scripts/swe_eval_cmd.py --instance {instance_id} --patch {patch_file}``

    Returns ``(resolved, meta)`` where meta may include ``reason`` / ``detail``
    from the hook JSON (apply/instance errors) for session-row diagnosis.
    """
    tmpl = os.getenv("SWE_EVAL_CMD")
    if not tmpl:
        return None, {}
    handle = tempfile.NamedTemporaryFile(
        "w", suffix=".patch", delete=False, encoding="utf-8"
    )
    try:
        handle.write(patch_text or "")
        handle.close()
        cmd = tmpl.format(instance_id=instance_id, patch_file=handle.name)
        proc = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=3600
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, {"reason": type(exc).__name__, "detail": str(exc)[-800:]}
    finally:
        Path(handle.name).unlink(missing_ok=True)
    resolved, meta = _parse_swe_eval_payload(proc.stdout or "")
    if resolved is None and not meta.get("reason"):
        err = (proc.stderr or "").strip()
        if err:
            meta = {**meta, "reason": meta.get("reason") or "swe_eval_stderr", "detail": err[-800:]}
    return resolved, meta


def _coerce_swe_eval_result(
    raw: bool | None | tuple[Any, ...],
) -> tuple[bool | None, dict[str, Any]]:
    """Accept legacy bool monkeypatches and new (resolved, meta) tuples."""
    if isinstance(raw, tuple):
        resolved = raw[0] if raw else None
        meta = raw[1] if len(raw) > 1 and isinstance(raw[1], dict) else {}
        return (None if resolved is None else bool(resolved)), meta
    if raw is None:
        return None, {}
    return bool(raw), {}


def decide_resolve(
    text: str,
    instance: dict[str, Any],
    *,
    gold: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Honest resolve label: pytest harness, SWE_EVAL_CMD, offline gold, or unlabeled."""
    instance_id = str(instance.get("instance_id") or "")
    if instance.get("tests"):
        meta: dict[str, Any] = {
            "verify_pytest": True,
            "module": instance.get("module") or "fix.py",
            "tests": instance["tests"],
        }
        return {
            "resolved": bool(_pytest_verify(text, meta)),
            "label_type": "harness_proxy",
            "session_gold": False,
        }
    # SWE_EVAL_CMD needs a unified-diff model_patch; skip docker on format mismatch.
    if os.getenv("SWE_EVAL_CMD"):
        patch, reason = extract_unified_diff(text)
        if patch is None:
            return {
                "resolved": None,
                "label_type": "needs_swe_eval",
                "session_gold": False,
                "patch_status": reason or "patch_not_unified_diff",
                "note": (
                    f"model output not a unified diff ({reason}); "
                    "skipped SWE_EVAL_CMD (no invalid patch to docker)"
                ),
            }
        swe, swe_meta = _coerce_swe_eval_result(_run_swe_eval_cmd(instance_id, patch))
        if swe is not None:
            out_ok: dict[str, Any] = {
                "resolved": bool(swe),
                "label_type": "session_gold",
                "session_gold": True,
            }
            if swe_meta.get("reason"):
                out_ok["swe_eval_reason"] = swe_meta["reason"]
            return out_ok
        # Extractable patch sent to docker but unlabeled (e.g. apply fail) —
        # mark so the runner can offer a debug turn.
        if gold is not None and gold.get("resolved") is not None:
            out_off: dict[str, Any] = {
                "resolved": bool(gold["resolved"]),
                "label_type": "offline_gold",
                "session_gold": False,
                "swe_eval_attempted": True,
                "note": "offline gold join; not live SWE-bench docker eval",
            }
            if swe_meta.get("reason"):
                out_off["swe_eval_reason"] = swe_meta["reason"]
            if swe_meta.get("detail"):
                out_off["swe_eval_detail"] = swe_meta["detail"]
            return out_off
        out_na: dict[str, Any] = {
            "resolved": None,
            "label_type": "needs_swe_eval",
            "session_gold": False,
            "swe_eval_attempted": True,
            "note": SWE_EVAL_NOTE,
        }
        if swe_meta.get("reason"):
            out_na["swe_eval_reason"] = swe_meta["reason"]
        if swe_meta.get("failure_reason"):
            out_na["swe_eval_failure_reason"] = swe_meta["failure_reason"]
        if swe_meta.get("detail"):
            out_na["swe_eval_detail"] = swe_meta["detail"]
        return out_na
    swe, swe_meta = _coerce_swe_eval_result(_run_swe_eval_cmd(instance_id, text))
    if swe is not None:
        return {
            "resolved": bool(swe),
            "label_type": "session_gold",
            "session_gold": True,
        }
    if gold is not None and gold.get("resolved") is not None:
        return {
            "resolved": bool(gold["resolved"]),
            "label_type": "offline_gold",
            "session_gold": False,
            "note": "offline gold join; not live SWE-bench docker eval",
        }
    out_fallback: dict[str, Any] = {
        "resolved": None,
        "label_type": "needs_swe_eval",
        "session_gold": False,
        "note": SWE_EVAL_NOTE,
    }
    if swe_meta.get("reason"):
        out_fallback["swe_eval_reason"] = swe_meta["reason"]
    if swe_meta.get("detail"):
        out_fallback["swe_eval_detail"] = swe_meta["detail"]
    return out_fallback


def _offline_session_row(
    instance_id: str,
    instance: dict[str, Any],
    gold: dict[str, Any] | None,
) -> dict[str, Any]:
    gold = gold or {}
    flags = instance_field_flags(instance)
    policies = gold.get("policies")
    if isinstance(policies, dict) and policies:
        out_pol: dict[str, Any] = {}
        for name, prow in policies.items():
            if isinstance(prow, dict) and "resolved" in prow:
                val = prow["resolved"]
                out_pol[name] = {
                    "resolved": None if val is None else bool(val),
                }
            else:
                out_pol[name] = {"resolved": None}
        return {
            "instance_id": instance_id,
            "session_id": instance_id,
            "label_type": "offline_gold",
            "comparison_mode": "offline_gold",
            "session_gold": False,
            "policies": out_pol,
            "turns": 0,
            "note": "offline gold join; not live SWE-bench docker eval",
            "instance_fields": flags,
        }
    flag = None if gold.get("resolved") is None else bool(gold.get("resolved"))
    return {
        "instance_id": instance_id,
        "session_id": instance_id,
        "label_type": "offline_gold",
        "comparison_mode": "offline_gold",
        "session_gold": False,
        "policies": {
            "rules": {"resolved": flag},
            "trained": {"resolved": flag, "counterfactual": False},
        },
        "turns": 0,
        "note": "instance-level offline gold (same label both policies; not a routing split)",
        "instance_fields": flags,
    }


class GatewayNotRunningError(RuntimeError):
    """Raised when the operator gateway is unreachable."""


class BudgetExceededError(RuntimeError):
    """Raised when spend.txt + estimate would exceed BUDGET_LIMIT_USD."""


def load_verified_ids(
    *,
    ids_path: Path | None = None,
    scaffold_path: Path | None = None,
) -> list[str]:
    """Load instance ids from --ids JSON/JSONL or Verified ids scaffold."""
    if ids_path is not None:
        path = Path(ids_path)
        text = path.read_text(encoding="utf-8").strip()
        if path.suffix == ".json":
            data = json.loads(text)
            if isinstance(data, dict) and "instance_ids" in data:
                ids = list(data["instance_ids"])
            elif isinstance(data, list):
                ids = [str(x) for x in data]
            else:
                raise ValueError(f"{path}: expected list or {{instance_ids: [...]}}")
        else:
            ids = []
            for line in text.splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                if isinstance(row, str):
                    ids.append(row)
                elif isinstance(row, dict) and row.get("instance_id"):
                    ids.append(str(row["instance_id"]))
                else:
                    raise ValueError(f"{path}: row missing instance_id")
        if not ids:
            raise ValueError(f"{path}: no instance ids found")
        return ids

    scaffold = load_ids_scaffold(scaffold_path or DEFAULT_SCAFFOLD)
    ids = scaffold.get("instance_ids")
    if not isinstance(ids, list) or not ids:
        raise ValueError(f"{scaffold_path or DEFAULT_SCAFFOLD}: missing instance_ids")
    return [str(x) for x in ids]


def budget_status(
    spend_path: Path | None = None,
    limit_usd: float | None = None,
) -> dict[str, Any]:
    path = spend_path or DEFAULT_SPEND
    limit = float(limit_usd if limit_usd is not None else os.getenv("BUDGET_LIMIT_USD", "15"))
    spend = SpendLog(path, limit)
    spent = spend.total()
    return {
        "spend_path": str(path),
        "spent_usd": round(spent, 6),
        "limit_usd": limit,
        "remaining_usd": round(max(0.0, limit - spent), 6),
    }


def assert_budget_headroom(
    *,
    n_instances: int,
    spend_path: Path | None = None,
    limit_usd: float | None = None,
    models_path: Path | None = None,
) -> dict[str, Any]:
    """Refuse when estimated shadow session spend exceeds remaining budget."""
    status = budget_status(spend_path=spend_path, limit_usd=limit_usd)
    cfg = load_config(models_path or ROOT / "config" / "models.yaml")
    models = load_models(cfg)
    est = estimate_gate_budget(n_instances=n_instances, models_cfg=models)
    per_instance = (
        float(est["shadow_dual_policy_session_gate_est_usd"]) / max(n_instances, 1)
    )
    needed = round(per_instance * n_instances, 4)
    remaining = float(status["remaining_usd"])
    out = {**status, "est_usd": needed, "est_per_instance_usd": round(per_instance, 4)}
    if needed > remaining + 1e-9:
        raise BudgetExceededError(
            f"budget headroom insufficient: need ~${needed:.2f} for n={n_instances} "
            f"but only ${remaining:.2f} remaining (spent ${status['spent_usd']:.2f} "
            f"of ${status['limit_usd']:.2f} cap; spend log {status['spend_path']})"
        )
    return out


def check_gateway(
    gateway_url: str,
    *,
    api_key: str = "change-me",
    client: httpx.Client | None = None,
) -> None:
    """Raise GatewayNotRunningError with startup command if gateway is down."""
    base = gateway_url.rstrip("/")
    owns = client is None
    if owns:
        client = httpx.Client(base_url=base, timeout=10.0)
    try:
        resp = client.get("/health")
        resp.raise_for_status()
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        raise GatewayNotRunningError(
            "Gateway not reachable at "
            f"{base!r}. Start shadow gateway first:\n\n"
            f"  {GATEWAY_START_CMD}\n"
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise GatewayNotRunningError(
            f"Gateway at {base!r} returned HTTP {exc.response.status_code}. "
            f"Expected /health 200. Start with:\n\n  {GATEWAY_START_CMD}\n"
        ) from exc
    finally:
        if owns and client is not None:
            client.close()


def _session_http_gateway(
    client: httpx.Client,
    api_key: str,
    session_id: str,
    *,
    hop_path: str | None = None,
) -> Callable[[str, str], str]:
    """HTTP gateway with x-session-id for hop grouping in the request log."""

    def _chat(phase: str, content: str) -> str:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "x-agent-phase": phase,
            "x-session-id": session_id,
        }
        if hop_path:
            headers["x-router-hop-path"] = hop_path
        resp = client.post(
            "/v1/chat/completions",
            headers=headers,
            json={"model": "router/auto", "messages": [{"role": "user", "content": content}]},
        )
        resp.raise_for_status()
        return (
            ((resp.json().get("choices") or [{}])[0].get("message") or {}).get("content")
            or ""
        )

    return _chat


def _report_outcome(client: httpx.Client, api_key: str, resolved: bool) -> None:
    client.post(
        "/v1/router/outcome",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "tests_passed": bool(resolved),
            "patch_applied": bool(resolved),
            "failure_text": "" if resolved else "pytest verify failed",
        },
    )


def _run_trained_counterfactual(
    client: httpx.Client,
    api_key: str,
    instance: dict[str, Any],
) -> dict[str, Any]:
    """Edit/debug resolve with trained serve via x-router-hop-path (shadow gateway stays)."""
    instance_id = str(instance.get("instance_id") or "")
    session_id = f"{instance_id}::cf-trained"
    gateway_fn = _session_http_gateway(client, api_key, session_id, hop_path="trained")
    # Prefer caller-enriched instance (cached docker-cp); else attach once.
    enriched = ensure_target_file_contents(instance)
    context = instance_turn_context(enriched)
    try:
        edit_text = gateway_fn(
            "edit", context + "\n\n" + verified_turn_instruction("edit", enriched)
        )
        out = decide_resolve(edit_text, enriched)
        if out.get("resolved") is False or out.get("swe_eval_attempted"):
            debug_text = gateway_fn(
                "debug",
                context
                + "\n\n"
                + _debug_instruction_with_harness_feedback(enriched, out),
            )
            out = decide_resolve(debug_text, enriched)
        out["counterfactual"] = True
        return out
    except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError) as exc:
        return {
            "resolved": None,
            "counterfactual": True,
            "error": type(exc).__name__,
            "label_type": "needs_swe_eval",
            "session_gold": False,
        }


def _run_live_instance(
    client: httpx.Client,
    api_key: str,
    instance: dict[str, Any],
) -> dict[str, Any]:
    instance_id = str(instance.get("instance_id") or "")
    session_id = instance_id
    gateway_fn = _session_http_gateway(client, api_key, session_id)
    enriched = ensure_target_file_contents(instance)
    context = instance_turn_context(enriched)
    flags = instance_field_flags(enriched)
    gateway_fn(
        "discover",
        context + "\n\n" + verified_turn_instruction("discover", enriched),
    )
    gateway_fn(
        "plan", context + "\n\n" + verified_turn_instruction("plan", enriched)
    )
    edit_text = gateway_fn(
        "edit", context + "\n\n" + verified_turn_instruction("edit", enriched)
    )
    rules_out = decide_resolve(edit_text, enriched)
    if rules_out.get("resolved") is False or rules_out.get("swe_eval_attempted"):
        debug_text = gateway_fn(
            "debug",
            context
            + "\n\n"
            + _debug_instruction_with_harness_feedback(enriched, rules_out),
        )
        rules_out = decide_resolve(debug_text, enriched)
    gateway_fn(
        "summarize",
        context + "\n\n" + verified_turn_instruction("summarize", enriched),
    )
    if rules_out.get("resolved") is True or rules_out.get("resolved") is False:
        _report_outcome(client, api_key, bool(rules_out["resolved"]))
    trained_out = _run_trained_counterfactual(client, api_key, enriched)
    session_gold = bool(
        rules_out.get("session_gold") or trained_out.get("session_gold")
    )
    label_type = (
        "session_gold"
        if session_gold
        else str(rules_out.get("label_type") or "needs_swe_eval")
    )
    return {
        "instance_id": instance_id,
        "session_id": session_id,
        "label_type": label_type,
        "comparison_mode": "shadow_dual_policy",
        "session_gold": session_gold,
        "policies": {
            "rules": {
                k: v
                for k, v in rules_out.items()
                if k not in {"session_gold"}
            },
            "trained": trained_out,
        },
        "turns": len(_TURNS),
        "instance_fields": flags,
        "file_context_source": enriched.get("file_context_source") or "unavailable",
        "note": rules_out.get("note") or SWE_EVAL_NOTE,
    }


def _run_fixture_instance(row: dict[str, Any]) -> dict[str, Any]:
    instance_id = str(row["instance_id"])
    policies = row.get("policies")
    if policies:
        results = {}
        for name, policy_row in policies.items():
            merged = _merge_policy_row(row, policy_row)
            results[name] = {"resolved": _run_fixture_policy(merged)}
        return {
            "instance_id": instance_id,
            "session_id": instance_id,
            "label_type": "harness_proxy",
            "comparison_mode": "fixture_replay",
            "session_gold": False,
            "policies": results,
            "turns": len(_TURNS),
        }
    resolved = _run_fixture_policy(row)
    return {
        "instance_id": instance_id,
        "session_id": instance_id,
        "label_type": "harness_proxy",
        "comparison_mode": "single_policy",
        "session_gold": False,
        "policies": {"rules": {"resolved": bool(resolved)}},
        "turns": len(_TURNS),
    }


def summarize_sessions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate session rows for operator visibility."""
    live = [r for r in rows if r.get("comparison_mode") == "shadow_dual_policy"]
    fixture = [r for r in rows if r.get("comparison_mode") == "fixture_replay"]
    offline = [r for r in rows if r.get("comparison_mode") == "offline_gold"]
    n = len(rows)

    def _labeled(val: Any) -> bool | None:
        if val is True:
            return True
        if val is False:
            return False
        return None

    rules_vals = [
        _labeled((r.get("policies") or {}).get("rules", {}).get("resolved"))
        for r in rows
    ]
    labeled_rules = [v for v in rules_vals if v is not None]
    trained_present = any((r.get("policies") or {}).get("trained") for r in rows)
    trained_vals = [
        _labeled((r.get("policies") or {}).get("trained", {}).get("resolved"))
        for r in rows
        if (r.get("policies") or {}).get("trained")
    ]
    labeled_trained = [v for v in trained_vals if v is not None]
    unlabeled = sum(1 for v in rules_vals if v is None)
    session_gold = any(r.get("session_gold") for r in rows)
    return {
        "verdict": "session_gate_partial" if live and session_gold else "bounded_check_only",
        "n": n,
        "live_shadow_sessions": len(live),
        "fixture_sessions": len(fixture),
        "offline_gold_sessions": len(offline),
        "rules_resolved": sum(1 for v in labeled_rules if v),
        "trained_resolved": (
            sum(1 for v in labeled_trained if v) if trained_present else None
        ),
        "rules_resolve_rate": (
            (sum(1 for v in labeled_rules if v) / len(labeled_rules))
            if labeled_rules
            else None
        ),
        "unlabeled": unlabeled,
        "session_gold": session_gold,
        "production_parity": False,
        "note": SWE_EVAL_NOTE if unlabeled else None,
    }


def run_verified_sessions(
    ids: list[str],
    *,
    gateway_url: str | None = None,
    api_key: str = "change-me",
    out_path: str | Path = DEFAULT_OUT,
    fixture: list[dict[str, Any]] | None = None,
    dry_run: bool = False,
    spend_path: Path | None = None,
    limit_usd: float | None = None,
    models_path: Path | None = None,
    client: httpx.Client | None = None,
    instances: dict[str, dict[str, Any]] | None = None,
    instances_path: Path | None = None,
    offline_gold: dict[str, dict[str, Any]] | None = None,
    fetch_instances: bool = False,
    cache_dir: Path | None = None,
) -> dict[str, Any]:
    """Run Verified instances (live shadow HTTP, unpaid fixture, or offline gold)."""
    n = len(ids)
    inst_map = instances
    if inst_map is None:
        inst_map = (
            {}
            if fixture
            else load_verified_instances(
                ids,
                dump_path=instances_path,
                cache_dir=cache_dir,
                fetch=fetch_instances,
            )
        )

    if dry_run:
        status = budget_status(spend_path=spend_path, limit_usd=limit_usd)
        cfg = load_config(models_path or ROOT / "config" / "models.yaml")
        models = load_models(cfg)
        est_all = estimate_gate_budget(n_instances=n, models_cfg=models)
        per_instance = (
            float(est_all["shadow_dual_policy_session_gate_est_usd"]) / max(n, 1)
        )
        needed = round(per_instance * n, 4)
        budget = {
            **status,
            "est_usd": needed,
            "est_per_instance_usd": round(per_instance, 4),
            "budget_blocked": needed > float(status["remaining_usd"]) + 1e-9,
        }
        if budget["budget_blocked"]:
            budget["budget_note"] = (
                f"need ~${needed:.2f} for n={n} but only ${status['remaining_usd']:.2f} remaining"
            )
        n_ps = sum(
            1
            for i in ids
            if str((inst_map.get(i) or {}).get("problem_statement") or "").strip()
        )
        return {
            "verdict": "dry_run",
            "n": n,
            "instance_ids": ids,
            "gateway": gateway_url,
            "gateway_start": GATEWAY_START_CMD,
            "budget": budget,
            "out_path": str(out_path),
            "session_gold": False,
            "production_parity": False,
            "instances_loaded": len(inst_map),
            "instances_with_problem_statement": n_ps,
            "note": (
                "No HTTP. Approve budget then rerun without --dry-run. "
                + SWE_EVAL_NOTE
            ),
        }

    rows: list[dict[str, Any]] = []
    if fixture:
        fixture_map = {r["instance_id"]: r for r in fixture}
        for instance_id in ids:
            row = fixture_map.get(instance_id, {"instance_id": instance_id})
            session_row = _run_fixture_instance(row)
            rows.append(session_row)
            pol = session_row.get("policies") or {}
            print(
                f"  {instance_id}: "
                + ", ".join(f"{k}={v.get('resolved')}" for k, v in pol.items()),
                flush=True,
            )
    elif offline_gold is not None:
        for instance_id in ids:
            inst = inst_map.get(instance_id) or {"instance_id": instance_id}
            session_row = _offline_session_row(
                instance_id, inst, offline_gold.get(instance_id)
            )
            rows.append(session_row)
            pol = session_row.get("policies") or {}
            print(
                f"  {instance_id}: "
                + ", ".join(f"{k}={v.get('resolved')}" for k, v in pol.items()),
                flush=True,
            )
    else:
        assert gateway_url
        budget = assert_budget_headroom(
            n_instances=n,
            spend_path=spend_path,
            limit_usd=limit_usd,
            models_path=models_path,
        )
        owns = client is None
        if owns:
            client = httpx.Client(base_url=gateway_url.rstrip("/"), timeout=300.0)
        try:
            check_gateway(gateway_url, api_key=api_key, client=client)
            for instance_id in ids:
                inst = inst_map.get(instance_id) or {"instance_id": instance_id}
                session_row = _run_live_instance(client, api_key, inst)
                rows.append(session_row)
                pol = session_row.get("policies") or {}
                print(
                    f"  {instance_id}: "
                    + ", ".join(f"{k}={v.get('resolved')}" for k, v in pol.items()),
                    flush=True,
                )
                _write_jsonl(Path(out_path), rows)
        finally:
            if owns and client is not None:
                client.close()
        _write_jsonl(Path(out_path), rows)
        summary = summarize_sessions(rows)
        summary["budget"] = budget
        summary["gateway"] = gateway_url
        summary["out_path"] = str(out_path)
        print(f"wrote {len(rows)} session rows to {out_path}", flush=True)
        return summary

    _write_jsonl(Path(out_path), rows)
    summary = summarize_sessions(rows)
    summary["out_path"] = str(out_path)
    print(f"wrote {len(rows)} session rows to {out_path}", flush=True)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verified session-gold runner (runbook §(a))")
    parser.add_argument("--ids", default=None, help="JSON/JSONL ids file (default: verified scaffold)")
    parser.add_argument(
        "--scaffold",
        default=str(DEFAULT_SCAFFOLD),
        help="Verified ids scaffold when --ids omitted",
    )
    parser.add_argument("--limit", type=int, default=None, help="Run first N ids only")
    parser.add_argument("--gateway", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", default=None, help="Router bearer token (default: ROUTER_API_KEY from .env)")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--fixture", default=None, help="Unpaid fixture replay (no HTTP)")
    parser.add_argument(
        "--instances",
        default=None,
        help="SWE-bench Verified JSON/JSONL dump (default: data/dump_cache/swe_verified.jsonl then HF cache)",
    )
    parser.add_argument(
        "--offline-gold",
        default=None,
        help="Unpaid instance_id→resolved JSON/JSONL join (no HTTP; not session gold)",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Do not download Verified rows from HuggingFace datasets-server",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print plan + budget guard only")
    parser.add_argument("--spend", default=str(DEFAULT_SPEND))
    parser.add_argument(
        "--budget-limit",
        type=float,
        default=None,
        help="Override BUDGET_LIMIT_USD (default env or 15)",
    )
    parser.add_argument("--models", default=str(ROOT / "config" / "models.yaml"))
    parser.add_argument(
        "--ids-only",
        action="store_true",
        help="Refresh Verified ids scaffold (unpaid HF fetch)",
    )
    load_dotenv()
    args = parser.parse_args(argv)

    if args.ids_only:
        from .lite_runner import fetch_bench_ids

        n = args.limit or VERIFIED_PRIMARY_N
        ids = fetch_bench_ids("verified", n=n)
        out = Path(args.scaffold)
        summary = write_ids_scaffold(ids, bench="verified", out_path=out)
        print(
            f"ids_scaffold bench={summary['bench']} n={summary['n']} -> {out} "
            f"(session_gold=false; live HTTP still required)",
            flush=True,
        )
        return 0

    ids = load_verified_ids(
        ids_path=Path(args.ids) if args.ids else None,
        scaffold_path=Path(args.scaffold),
    )
    # When an instances dump is given without --ids, prefer dump order (fixture smoke).
    if args.instances and not args.ids:
        dump_ids = list(_index_instance_rows(Path(args.instances)))
        if dump_ids:
            ids = dump_ids
    if args.limit is not None:
        ids = ids[: args.limit]

    if args.limit is not None and args.limit > VERIFIED_CAP and not args.fixture:
        print(f"clamping --limit {args.limit} to cap {VERIFIED_CAP}", file=sys.stderr)
        ids = ids[:VERIFIED_CAP]

    fixture = _load_fixture(args.fixture) if args.fixture else None
    if fixture:
        fixture_ids = {r["instance_id"] for r in fixture}
        ids = [i for i in ids if i in fixture_ids] or [r["instance_id"] for r in fixture][: len(ids)]

    gold = load_offline_gold(Path(args.offline_gold)) if args.offline_gold else None

    try:
        summary = run_verified_sessions(
            ids,
            api_key=args.api_key or _router_api_key(),
            gateway_url=(
                None
                if fixture or gold is not None or args.dry_run
                else args.gateway
            ),
            out_path=args.out,
            fixture=fixture,
            dry_run=args.dry_run,
            spend_path=Path(args.spend),
            limit_usd=args.budget_limit,
            models_path=Path(args.models),
            instances_path=Path(args.instances) if args.instances else None,
            offline_gold=gold,
            fetch_instances=not args.no_fetch,
        )
    except GatewayNotRunningError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except BudgetExceededError as exc:
        print(str(exc), file=sys.stderr)
        return 3

    if args.dry_run:
        print(json.dumps(summary, indent=2))
    else:
        print(
            f"verified sessions: n={summary.get('n')} "
            f"rules={summary.get('rules_resolved')} "
            f"verdict={summary.get('verdict')}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
