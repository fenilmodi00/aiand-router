"""Shallow file context via docker create + docker cp (no full SWE agent).

Copies ``likely_target_files`` from a local SWE-bench eval image workdir into
Verified edit prompts so hunk context matches ``base_commit``. Never reads or
injects gold ``patch`` / ``test_patch``.

When the local ``sweb.eval`` image is missing, falls back to a shallow git
fetch of ``repo``@``base_commit`` (see ``git_file_context``) into
``data/repo_cache/``. Resolve via ``SWE_EVAL_CMD`` still needs an image when
present; without one, stay honest ``needs_swe_eval``.

Falls back honestly when Docker/image/git/path is unavailable (empty result).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

from .git_file_context import copy_paths_from_git
from .lite_runner import guess_target_paths

DEFAULT_WORKDIR = "/testbed"
DEFAULT_MAX_LINES = 400
DEFAULT_MAX_BYTES = 120_000
DEFAULT_MAX_FILES = 2  # tighter: fewer mixed-file malformed hunks on apply
_IMAGE_SAFE_RE = re.compile(r"^[a-z0-9][a-z0-9._/-]*$", re.IGNORECASE)

RunFn = Callable[..., subprocess.CompletedProcess[str]]


def swebench_eval_image(instance_id: str, *, registry: str = "swebench") -> str:
    """Map SWE-bench instance_id → local eval image tag (swebench harness naming)."""
    iid = str(instance_id or "").strip().lower()
    if not iid or "__" not in iid:
        raise ValueError(f"invalid instance_id for eval image: {instance_id!r}")
    # django__django-11099 → django_1776_django-11099
    key = iid.replace("__", "_1776_")
    return f"{registry}/sweb.eval.x86_64.{key}:latest"


def docker_available(*, run: RunFn | None = None) -> bool:
    if not shutil.which("docker"):
        return False
    if os.getenv("VERIFIED_FILE_CONTEXT", "1").strip().lower() in {"0", "false", "off", "no"}:
        return False
    runner = run or _run
    try:
        proc = runner(["docker", "info"], timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def docker_image_present(image: str, *, run: RunFn | None = None) -> bool:
    if not image or not _IMAGE_SAFE_RE.match(image.split(":")[0]):
        return False
    runner = run or _run
    try:
        proc = runner(["docker", "image", "inspect", image], timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def _run(
    cmd: list[str],
    *,
    timeout: float = 120,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )


def _safe_repo_path(path: str) -> str | None:
    p = (path or "").replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    p = p.lstrip("/")
    if not p or p.startswith("/") or ".." in p.split("/"):
        return None
    if not re.match(r"^[A-Za-z0-9_./+-]+$", p):
        return None
    return p


def copy_paths_from_eval_image(
    instance_id: str,
    paths: list[str],
    *,
    image: str | None = None,
    workdir: str = DEFAULT_WORKDIR,
    max_files: int = DEFAULT_MAX_FILES,
    max_bytes: int = DEFAULT_MAX_BYTES,
    run: RunFn | None = None,
) -> dict[str, str]:
    """docker create + docker cp named paths from eval image workdir.

    Returns ``{repo_relative_path: text}`` for successful copies only.
    Empty dict when Docker/image unavailable or all copies fail — never raises
    for missing image (honest unpaid fallback).
    """
    runner = run or _run
    if not paths:
        return {}
    if not docker_available(run=runner):
        return {}
    img = image or swebench_eval_image(instance_id)
    if not docker_image_present(img, run=runner):
        return {}

    safe_paths: list[str] = []
    for raw in paths:
        sp = _safe_repo_path(str(raw))
        if sp and sp not in safe_paths:
            safe_paths.append(sp)
        if len(safe_paths) >= max_files:
            break
    if not safe_paths:
        return {}

    create = runner(["docker", "create", img], timeout=120)
    if create.returncode != 0 or not (create.stdout or "").strip():
        return {}
    cid = (create.stdout or "").strip().splitlines()[-1].strip()
    out: dict[str, str] = {}
    try:
        with tempfile.TemporaryDirectory(prefix="aiand_docker_cp_") as tmp:
            tmp_path = Path(tmp)
            for rel in safe_paths:
                dest = tmp_path / rel.replace("/", "_")
                src = f"{cid}:{workdir.rstrip('/')}/{rel}"
                cp = runner(["docker", "cp", src, str(dest)], timeout=120)
                if cp.returncode != 0 or not dest.is_file():
                    continue
                raw = dest.read_bytes()
                if len(raw) > max_bytes:
                    raw = raw[:max_bytes]
                text = raw.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
                if text.strip():
                    out[rel] = text
    finally:
        runner(["docker", "rm", "-f", cid], timeout=60)
    return out


def resolve_target_file_contents(
    instance: dict[str, Any],
    *,
    paths: list[str] | None = None,
    run: RunFn | None = None,
    max_files: int = DEFAULT_MAX_FILES,
    prefer_git: bool = False,
    cache_dir: Path | str | None = None,
) -> tuple[dict[str, str], str, str | None]:
    """Resolve likely_target_files: docker_cp first (when image local), else git.

    Returns ``(files, source, error)`` where source is
    ``docker_cp`` | ``git`` | ``unavailable``. Never consults gold
    ``patch`` / ``test_patch``.
    """
    cached = instance.get("target_file_contents")
    if isinstance(cached, dict) and cached:
        prior = str(instance.get("file_context_source") or "cached")
        return (
            {str(k): str(v) for k, v in cached.items() if str(v).strip()},
            prior if prior in {"docker_cp", "git", "cached"} else "cached",
            None,
        )

    wanted = list(paths) if paths is not None else guess_target_paths(
        instance, limit=max_files
    )
    if not wanted:
        return {}, "unavailable", "no_paths"

    iid = str(instance.get("instance_id") or "")
    git_err: str | None = None

    def _try_git() -> tuple[dict[str, str], str, str | None]:
        nonlocal git_err
        repo = str(instance.get("repo") or "").strip()
        commit = str(instance.get("base_commit") or "").strip()
        if not repo or not commit:
            git_err = "missing_repo_or_base_commit"
            return {}, "unavailable", git_err
        kwargs: dict[str, Any] = {
            "max_files": max_files,
            "run": run,
        }
        if cache_dir is not None:
            kwargs["cache_dir"] = cache_dir
        files, err = copy_paths_from_git(repo, commit, wanted, **kwargs)
        git_err = err
        if files:
            return files, "git", None
        return {}, "unavailable", err or "git_unavailable"

    if prefer_git:
        files, source, err = _try_git()
        if files:
            return files, source, err

    if iid and not prefer_git:
        docker_files = copy_paths_from_eval_image(
            iid,
            wanted,
            max_files=max_files,
            run=run,
        )
        if docker_files:
            return docker_files, "docker_cp", None

    if not prefer_git:
        files, source, err = _try_git()
        if files:
            return files, source, err

    return {}, "unavailable", git_err or "unavailable"


def load_target_file_contents(
    instance: dict[str, Any],
    *,
    paths: list[str] | None = None,
    run: RunFn | None = None,
    max_files: int = DEFAULT_MAX_FILES,
    prefer_git: bool = False,
    cache_dir: Path | str | None = None,
) -> dict[str, str]:
    """Resolve likely_target_files via docker cp, else git shallow fetch.

    Uses ``instance['target_file_contents']`` if already attached (tests / cache).
    Never consults gold ``patch`` / ``test_patch``.
    """
    files, _source, _err = resolve_target_file_contents(
        instance,
        paths=paths,
        run=run,
        max_files=max_files,
        prefer_git=prefer_git,
        cache_dir=cache_dir,
    )
    return files


def format_file_contents(
    files: dict[str, str],
    *,
    max_lines: int = DEFAULT_MAX_LINES,
) -> str:
    """Prompt block with capped file excerpts for exact hunk context."""
    if not files:
        return ""
    chunks = [
        "file_contents (from instance base tree via docker_cp or git; use as exact "
        "hunk context - do not invent surrounding lines):"
    ]
    for path, body in files.items():
        lines = body.splitlines()
        truncated = len(lines) > max_lines
        shown = lines[:max_lines]
        block = "\n".join(shown)
        if truncated:
            block += f"\n... [truncated after {max_lines} lines]"
        chunks.append(f"### {path}\n```\n{block}\n```")
    return "\n\n".join(chunks)


def ensure_target_file_contents(
    instance: dict[str, Any],
    *,
    run: RunFn | None = None,
    prefer_git: bool = False,
    cache_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Shallow-copy instance and attach ``target_file_contents`` when available.

    Prefers local docker_cp; git shallow fetch is the unpaid fallback when the
    eval image is missing. Sets ``file_context_source`` to ``docker_cp``,
    ``git``, or ``unavailable`` (plus optional ``file_context_error``).
    """
    out = dict(instance)
    if out.get("_file_context_attempted"):
        return out
    out["_file_context_attempted"] = True
    files, source, err = resolve_target_file_contents(
        out, run=run, prefer_git=prefer_git, cache_dir=cache_dir
    )
    if files:
        out["target_file_contents"] = files
        out["file_context_source"] = source
        out.pop("file_context_error", None)
    else:
        out["file_context_source"] = "unavailable"
        if err:
            out["file_context_error"] = err
    return out


def main(argv: list[str] | None = None) -> int:
    """Unpaid CLI: docker-cp or git file-context smoke without LLM."""
    parser = argparse.ArgumentParser(
        description=(
            "Copy likely_target_files from SWE eval image or git@base_commit (unpaid)"
        )
    )
    parser.add_argument("--instance", required=True, help="SWE-bench instance_id")
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        help="Repo-relative path (repeatable). Default: guess from --problem or dump.",
    )
    parser.add_argument(
        "--problem",
        default="",
        help="Optional problem_statement for path guessing when --path omitted",
    )
    parser.add_argument("--repo", default="", help="Optional repo (owner/name)")
    parser.add_argument(
        "--base-commit",
        default="",
        help="Optional base_commit SHA (enables git fallback / --prefer-git)",
    )
    parser.add_argument(
        "--prefer-git",
        action="store_true",
        help="Skip docker_cp and use git shallow fetch only",
    )
    parser.add_argument(
        "--cache-dir",
        default="",
        help="Git repo cache root (default: data/repo_cache)",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional JSON path to write {path: content}",
    )
    parser.add_argument("--max-lines", type=int, default=DEFAULT_MAX_LINES)
    args = parser.parse_args(argv)

    instance: dict[str, Any] = {
        "instance_id": args.instance,
        "repo": args.repo or None,
        "base_commit": args.base_commit or None,
        "problem_statement": args.problem,
    }
    paths = list(args.path) or None
    cache = Path(args.cache_dir) if args.cache_dir else None
    files, source, err = resolve_target_file_contents(
        instance,
        paths=paths,
        prefer_git=bool(args.prefer_git),
        cache_dir=cache,
    )
    payload = {
        "instance_id": args.instance,
        "image": swebench_eval_image(args.instance),
        "repo": instance.get("repo"),
        "base_commit": instance.get("base_commit"),
        "paths_requested": paths or guess_target_paths(instance),
        "paths_copied": list(files),
        "n_bytes": {p: len(t.encode("utf-8")) for p, t in files.items()},
        "file_context_source": source,
        "file_context_error": err,
        "preview": format_file_contents(files, max_lines=min(40, args.max_lines))
        if files
        else "",
    }
    if args.out:
        Path(args.out).write_text(
            json.dumps({**payload, "contents": files}, indent=2),
            encoding="utf-8",
        )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if files else 2


if __name__ == "__main__":
    raise SystemExit(main())
