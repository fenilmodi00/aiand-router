"""Gold success labeling (verified / proxy / weak). Serve-path runners reuse _pytest_verify."""

from __future__ import annotations

import difflib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


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
