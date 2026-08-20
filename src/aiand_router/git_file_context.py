"""Git shallow file-context fallback (no SWE eval image pull).

When a local ``sweb.eval`` image is missing, fetch ``repo``@``base_commit`` into
``data/repo_cache/`` and read ``likely_target_files`` via ``git show``. Prefer
``docker_cp`` when the eval image is already local.

Never reads or injects gold ``patch`` / ``test_patch``. Cache git objects and
extracted blobs aggressively so re-runs do not re-clone.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable

DEFAULT_CACHE_DIR = Path("data/repo_cache")
DEFAULT_MAX_BYTES = 120_000
DEFAULT_MAX_FILES = 2

_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$", re.IGNORECASE)
_SAFE_PATH_RE = re.compile(r"^[A-Za-z0-9_./+-]+$")

RunFn = Callable[..., subprocess.CompletedProcess[str]]


def _file_context_enabled() -> bool:
    return os.getenv("VERIFIED_FILE_CONTEXT", "1").strip().lower() not in {
        "0",
        "false",
        "off",
        "no",
    }


def git_available(*, run: RunFn | None = None) -> bool:
    if not _file_context_enabled():
        return False
    if os.getenv("VERIFIED_FILE_CONTEXT_GIT", "1").strip().lower() in {
        "0",
        "false",
        "off",
        "no",
    }:
        return False
    if not shutil.which("git"):
        return False
    runner = run or _run
    try:
        proc = runner(["git", "--version"], timeout=30)
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


def normalize_repo(repo: str) -> str | None:
    r = (repo or "").strip().removesuffix(".git")
    if r.startswith("https://github.com/"):
        r = r[len("https://github.com/") :]
    elif r.startswith("http://github.com/"):
        r = r[len("http://github.com/") :]
    elif r.startswith("git@github.com:"):
        r = r[len("git@github.com:") :]
    r = r.strip("/")
    if not _REPO_RE.match(r):
        return None
    owner, _, name = r.partition("/")
    if not owner or not name or ".." in owner or ".." in name:
        return None
    return r


def normalize_commit(commit: str) -> str | None:
    c = (commit or "").strip().lower()
    if not _COMMIT_RE.match(c):
        return None
    return c


def _safe_repo_path(path: str) -> str | None:
    p = (path or "").replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    p = p.lstrip("/")
    if not p or p.startswith("/") or ".." in p.split("/"):
        return None
    if not _SAFE_PATH_RE.match(p):
        return None
    return p


def repo_cache_dir(repo: str, cache_root: Path | str = DEFAULT_CACHE_DIR) -> Path:
    slug = repo.replace("/", "__")
    return Path(cache_root) / slug


def github_clone_url(repo: str) -> str:
    return f"https://github.com/{repo}.git"


def _commit_present(repo_dir: Path, commit: str, *, run: RunFn) -> bool:
    proc = run(
        ["git", "-C", str(repo_dir), "cat-file", "-e", f"{commit}^{{commit}}"],
        timeout=30,
    )
    return proc.returncode == 0


def ensure_commit_fetched(
    repo: str,
    commit: str,
    *,
    cache_dir: Path | str = DEFAULT_CACHE_DIR,
    run: RunFn | None = None,
) -> tuple[Path | None, str | None]:
    """Ensure ``commit`` objects exist under the repo cache. Returns (repo_dir, err)."""
    runner = run or _run
    if not git_available(run=runner):
        return None, "git_unavailable"
    norm_repo = normalize_repo(repo)
    norm_commit = normalize_commit(commit)
    if not norm_repo:
        return None, "invalid_repo"
    if not norm_commit:
        return None, "invalid_commit"

    repo_dir = repo_cache_dir(norm_repo, cache_dir)
    repo_dir.mkdir(parents=True, exist_ok=True)
    git_dir = repo_dir / ".git"
    url = github_clone_url(norm_repo)

    if not git_dir.exists():
        init = runner(["git", "init", str(repo_dir)], timeout=60)
        if init.returncode != 0:
            err = (init.stderr or init.stdout or "git_init_failed").strip()
            return None, f"git_init_failed:{err[:200]}"
        remote = runner(
            ["git", "-C", str(repo_dir), "remote", "add", "origin", url],
            timeout=30,
        )
        if remote.returncode != 0:
            # Remote may already exist from a partial prior run.
            runner(
                ["git", "-C", str(repo_dir), "remote", "set-url", "origin", url],
                timeout=30,
            )

    if _commit_present(repo_dir, norm_commit, run=runner):
        return repo_dir, None

    fetch = runner(
        [
            "git",
            "-C",
            str(repo_dir),
            "fetch",
            "--depth",
            "1",
            "origin",
            norm_commit,
        ],
        timeout=300,
    )
    if fetch.returncode != 0 or not _commit_present(
        repo_dir, norm_commit, run=runner
    ):
        err = (fetch.stderr or fetch.stdout or "git_fetch_failed").strip()
        return None, f"git_fetch_failed:{err[:300]}"
    return repo_dir, None


def _blob_cache_path(repo_dir: Path, commit: str, rel: str) -> Path:
    return repo_dir / "blobs" / commit / rel


def _read_via_git_show(
    repo_dir: Path,
    commit: str,
    rel: str,
    *,
    max_bytes: int,
    run: RunFn,
) -> str | None:
    proc = run(
        ["git", "-C", str(repo_dir), "show", f"{commit}:{rel}"],
        timeout=60,
    )
    if proc.returncode != 0:
        return None
    raw = (proc.stdout or "").encode("utf-8", errors="replace")
    if len(raw) > max_bytes:
        raw = raw[:max_bytes]
    text = raw.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    return text if text.strip() else None


def copy_paths_from_git(
    repo: str,
    base_commit: str,
    paths: list[str],
    *,
    cache_dir: Path | str = DEFAULT_CACHE_DIR,
    max_files: int = DEFAULT_MAX_FILES,
    max_bytes: int = DEFAULT_MAX_BYTES,
    run: RunFn | None = None,
) -> tuple[dict[str, str], str | None]:
    """Read repo-relative paths at ``base_commit`` via cached shallow fetch.

    Returns ``({path: text}, error_or_none)``. Empty dict + error when git/network
    fails — honest unpaid fallback (never raises for missing remote).
    """
    runner = run or _run
    if not paths:
        return {}, "no_paths"
    repo_dir, err = ensure_commit_fetched(
        repo, base_commit, cache_dir=cache_dir, run=runner
    )
    if repo_dir is None:
        return {}, err or "git_unavailable"

    commit = normalize_commit(base_commit)
    assert commit is not None  # validated in ensure_commit_fetched

    safe_paths: list[str] = []
    for raw in paths:
        sp = _safe_repo_path(str(raw))
        if sp and sp not in safe_paths:
            safe_paths.append(sp)
        if len(safe_paths) >= max_files:
            break
    if not safe_paths:
        return {}, "no_safe_paths"

    out: dict[str, str] = {}
    for rel in safe_paths:
        blob = _blob_cache_path(repo_dir, commit, rel)
        if blob.is_file():
            raw = blob.read_bytes()
            if len(raw) > max_bytes:
                raw = raw[:max_bytes]
            text = (
                raw.decode("utf-8", errors="replace")
                .replace("\r\n", "\n")
                .replace("\r", "\n")
            )
            if text.strip():
                out[rel] = text
            continue
        text = _read_via_git_show(
            repo_dir, commit, rel, max_bytes=max_bytes, run=runner
        )
        if text is None:
            continue
        try:
            blob.parent.mkdir(parents=True, exist_ok=True)
            blob.write_text(text, encoding="utf-8", newline="\n")
        except OSError:
            pass
        out[rel] = text

    if not out:
        return {}, "paths_missing_at_commit"
    return out, None
