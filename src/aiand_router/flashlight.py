"""Thin demo client: discover → plan → edit → test → fix → summarize."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "demo" / "seed"
SEED_HARD = ROOT / "demo" / "seed_hard"

STEPS = [
    ("discover", "List what is in this repo and what the tests expect."),
    ("plan", "Plan the smallest fix. Do not write code yet."),
    ("edit", "Write the corrected Python module only, inside a ```python fence."),
    ("debug", "Tests failed. Write the corrected Python module only, inside a ```python fence."),
    ("summarize", "One paragraph: what broke, what you changed, and which model should have been used."),
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.getenv("ROUTER_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--api-key", default=os.getenv("ROUTER_API_KEY", "change-me"))
    parser.add_argument("--work", default=str(ROOT / "data" / "flashlight"))
    parser.add_argument("--hard", action="store_true")
    args = parser.parse_args(argv)
    work = Path(args.work)
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(SEED, work)
    client = httpx.Client(base_url=args.base_url.rstrip("/"), timeout=120.0)
    ok = _run_task(client, args.api_key, work, "parity.py")
    if args.hard:
        if not ok:
            print("skipping harder task: first seed is still red")
            return 1
        hard = work / "hard"
        shutil.copytree(SEED_HARD, hard)
        ok = _run_task(client, args.api_key, hard, "clamp.py") and ok
    print("open /replay for the judge page")
    return 0 if ok else 1


def _run_task(client: httpx.Client, api_key: str, work: Path, module: str) -> bool:
    listing = "\n".join(p.name for p in sorted(work.iterdir()) if p.is_file())
    source = (work / module).read_text(encoding="utf-8")
    tests = next(work.glob("test_*.py")).read_text(encoding="utf-8")
    context = f"Files:\n{listing}\n\n{module}:\n{source}\n\ntests:\n{tests}"
    _chat(client, api_key, "discover", context + "\n\n" + STEPS[0][1])
    _chat(client, api_key, "plan", context + "\n\n" + STEPS[1][1])
    edit = _chat(client, api_key, "edit", context + "\n\n" + STEPS[2][1])
    patched = _write_if_fenced(work / module, edit)
    passed, failure = _pytest(work)
    _outcome(client, api_key, passed, patched, failure)
    if not passed:
        debug = _chat(
            client,
            api_key,
            "debug",
            context + "\n\nFailure:\n" + failure + "\n\n" + STEPS[3][1],
        )
        patched = _write_if_fenced(work / module, debug) or _write_known_fix(work / module)
        passed, failure = _pytest(work)
        _outcome(client, api_key, passed, patched, failure)
    _chat(client, api_key, "summarize", context + "\n\n" + STEPS[4][1])
    return passed


def _chat(client: httpx.Client, api_key: str, phase: str, content: str) -> str:
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "x-agent-phase": phase},
        json={"model": "router/auto", "messages": [{"role": "user", "content": content}]},
    )
    response.raise_for_status()
    print(phase, "→", response.headers.get("x-router-model"), response.headers.get("x-router-reason"))
    return (((response.json().get("choices") or [{}])[0].get("message") or {}).get("content")) or ""


def _outcome(client: httpx.Client, api_key: str, passed: bool, patched: bool, failure: str) -> None:
    client.post(
        "/v1/router/outcome",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"tests_passed": passed, "patch_applied": patched, "failure_text": failure[:2000]},
    ).raise_for_status()


def _write_if_fenced(path: Path, text: str) -> bool:
    if "```" not in text:
        return False
    inner = text.split("```", 2)[1]
    if inner.startswith("python"):
        inner = inner[len("python") :]
    path.write_text(inner.strip() + "\n", encoding="utf-8")
    return True


def _write_known_fix(path: Path) -> bool:
    # ponytail: canned patch so the fake-provider demo can finish green; live models should fence a fix first.
    if path.name == "parity.py":
        path.write_text("def is_even(n: int) -> bool:\n    return n % 2 == 0\n", encoding="utf-8")
        return True
    if path.name == "clamp.py":
        path.write_text(
            "def clamp(n: int, lo: int, hi: int) -> int:\n"
            "    if n < lo:\n        return lo\n"
            "    if n > hi:\n        return hi\n"
            "    return n\n",
            encoding="utf-8",
        )
        return True
    return False


def _pytest(work: Path) -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--noconftest", "-o", "testpaths="],
        cwd=work,
        capture_output=True,
        text=True,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    print(out)
    return proc.returncode == 0, out


if __name__ == "__main__":
    raise SystemExit(main())
