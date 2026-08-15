"""Multi-SWE-RL non-Python hop share monitor.

Per-hop language guess from file extensions in payload/messages, path hints, or an
explicit ``lang``/``language`` tag. Unknown is NOT non-Python; a mixed hop that
includes any Python source file counts as Python. See
``.scratch/trained-router/spec.md`` (Multi-SWE-RL / catalog drift) and
``.scratch/trained-router/issues/21-multi-swe-rl-trigger.md``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# File extension -> language. cpp/c/cc/h all map to cpp.
EXT_TO_LANG: dict[str, str] = {
    "py": "python",
    "pyi": "python",
    "pyw": "python",
    "js": "javascript",
    "ts": "typescript",
    "tsx": "tsx",
    "jsx": "jsx",
    "java": "java",
    "go": "go",
    "rs": "rust",
    "c": "cpp",
    "cpp": "cpp",
    "cc": "cpp",
    "h": "cpp",
    "rb": "ruby",
    "php": "php",
    "cs": "csharp",
    "swift": "swift",
    "kt": "kotlin",
}

# Explicit lang/language tag values -> language.
LANG_TAG_TO_LANG: dict[str, str] = {
    "python": "python",
    "py": "python",
    "javascript": "javascript",
    "js": "javascript",
    "typescript": "typescript",
    "ts": "typescript",
    "tsx": "tsx",
    "jsx": "jsx",
    "java": "java",
    "go": "go",
    "golang": "go",
    "rust": "rust",
    "rs": "rust",
    "c": "cpp",
    "cpp": "cpp",
    "c++": "cpp",
    "ruby": "ruby",
    "rb": "ruby",
    "php": "php",
    "cs": "csharp",
    "csharp": "csharp",
    "swift": "swift",
    "kt": "kotlin",
    "kotlin": "kotlin",
}

_EXT_RE = re.compile(r"\.([A-Za-z0-9]+)\b")


def _iter_strings(value: Any):
    """Yield every string inside a nested dict/list structure."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _iter_strings(v)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_strings(item)


def _extensions_in_text(text: str) -> set[str]:
    """Language names for every file extension found in a string."""
    found: set[str] = set()
    for m in _EXT_RE.finditer(text):
        found.add(EXT_TO_LANG.get(m.group(1).lower(), "unknown"))
    return found


def guess_languages(row: dict) -> set[str]:
    """Language signals for a hop row: explicit lang tag + file extensions."""
    langs: set[str] = set()
    if isinstance(row, dict):
        for key in ("lang", "language"):
            value = row.get(key)
            if isinstance(value, str):
                langs.add(LANG_TAG_TO_LANG.get(value.strip().lower(), "unknown"))
        for text in _iter_strings(row):
            langs.update(_extensions_in_text(text))
    return langs or {"unknown"}


def hop_is_python(row: dict) -> bool | None:
    """True if any Python signal; None if only unknown; False otherwise."""
    langs = guess_languages(row)
    if "python" in langs:
        return True
    if langs == {"unknown"}:
        return None
    return False


def non_python_share(rows) -> float:
    """Share of non-Python among determinable rows (unknown excluded from both)."""
    total = 0
    non_py = 0
    for row in rows:
        verdict = hop_is_python(row)
        if verdict is None:
            continue
        total += 1
        if not verdict:
            non_py += 1
    return non_py / total if total else 0.0


def evaluate(
    rows,
    threshold: float = 0.20,
    out_path: str = "data/multi_swe_rl_status.json",
) -> dict:
    """Write the Multi-SWE-RL ingest recommendation. Deterministic, no timestamps."""
    share = non_python_share(rows)
    n_determinable = sum(1 for row in rows if hop_is_python(row) is not None)
    status = {
        "recommend_ingest": share >= threshold,
        "share": share,
        "n_determinable": n_determinable,
        "threshold": threshold,
    }
    if n_determinable > 0:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return status
