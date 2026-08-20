"""Assert-based QA for docs/runbook-production.md.

Parses the runbook markdown, extracts every line that looks like a command
(`python -m ...` or `python scripts/...`), and verifies each referenced
module or script exists in the repo.

Run: python scripts/check_runbook.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "docs" / "runbook-production.md"
SRC = ROOT / "src"

# Matches: python -m aiand_router.train gold --queries ...
# or:     python scripts/gen_verified_queries.py
# or:     python -m aiand_router.retrain --plan-only
CMD_RE = re.compile(r"^\s*python\s+(-m\s+([\w.]+)|scripts/\S+\.py)")


def _extract_commands(text: str) -> list[tuple[str, str]]:
    """Return [(full_match, module_or_script_path), ...] from markdown."""
    commands: list[tuple[str, str]] = []
    for line in text.splitlines():
        m = CMD_RE.match(line)
        if not m:
            continue
        full = line.strip()
        if m.group(2):
            # python -m module.path
            commands.append((full, m.group(2)))
        else:
            # python scripts/foo.py
            commands.append((full, m.group(1)))
    return commands


def _resolve_module(module_dotted: str) -> Path | None:
    """Resolve a dotted module path to a file under src/."""
    parts = module_dotted.split(".")
    # Try src/package/sub.py
    candidate = SRC.joinpath(*parts).with_suffix(".py")
    if candidate.exists():
        return candidate
    # Try src/package/sub/__init__.py
    candidate = SRC.joinpath(*parts, "__init__.py")
    if candidate.exists():
        return candidate
    return None


def _resolve_script(script_rel: str) -> Path | None:
    """Resolve a scripts/ path relative to repo root."""
    candidate = ROOT / script_rel
    if candidate.exists():
        return candidate
    return None


def main() -> int:
    if not RUNBOOK.exists():
        print(f"FAIL: runbook not found at {RUNBOOK}", file=sys.stderr)
        return 1

    text = RUNBOOK.read_text(encoding="utf-8")
    commands = _extract_commands(text)

    if not commands:
        print("FAIL: no commands found in runbook", file=sys.stderr)
        return 1

    failures: list[str] = []
    checked: set[str] = set()

    for full_cmd, ref in commands:
        if ref in checked:
            continue
        checked.add(ref)

        if ref.startswith("scripts/"):
            resolved = _resolve_script(ref)
        else:
            resolved = _resolve_module(ref)

        if resolved is None:
            failures.append(f"  NOT FOUND: {ref}  (in: {full_cmd})")
        else:
            print(f"  OK: {ref} -> {resolved.relative_to(ROOT)}")

    if failures:
        print(f"\nFAIL: {len(failures)} command(s) reference missing modules/scripts:")
        for f in failures:
            print(f)
        return 1

    print(f"\nAll {len(checked)} unique commands verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
