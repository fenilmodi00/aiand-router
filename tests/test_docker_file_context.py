"""Unpaid tests for docker create + docker cp / git file context (no LLM)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from aiand_router.docker_file_context import (
    copy_paths_from_eval_image,
    docker_image_present,
    ensure_target_file_contents,
    format_file_contents,
    load_target_file_contents,
    resolve_target_file_contents,
    swebench_eval_image,
)
from aiand_router.git_file_context import (
    copy_paths_from_git,
    ensure_commit_fetched,
    normalize_commit,
    normalize_repo,
)
from aiand_router.lite_runner import instance_turn_context
from aiand_router.verified_runner import instance_field_flags, verified_turn_context

DJANGO_IMAGE = "swebench/sweb.eval.x86_64.django_1776_django-11099:latest"
VALIDATORS = "django/contrib/auth/validators.py"
DJANGO_REPO = "django/django"
DJANGO_BASE = "d26b2424437dabeeca94d7900b37d2df4410da0c"


def test_swebench_eval_image_naming():
    assert swebench_eval_image("django__django-11099") == DJANGO_IMAGE
    assert "1776" in swebench_eval_image("astropy__astropy-12907")


def test_format_file_contents_caps_lines():
    body = "\n".join(f"line{i}" for i in range(500))
    text = format_file_contents({"a/b.py": body}, max_lines=10)
    assert "### a/b.py" in text
    assert "file_contents" in text
    assert "line9" in text
    assert "line10" not in text or "truncated" in text
    assert "truncated after 10 lines" in text


def test_default_max_files_is_two():
    from aiand_router import docker_file_context as dfc

    assert dfc.DEFAULT_MAX_FILES == 2


def test_instance_turn_context_includes_attached_file_contents_not_gold():
    row = {
        "instance_id": "django__django-11099",
        "repo": "django/django",
        "problem_statement": "Fix validators in contrib.auth.validators.",
        "patch": "diff --git a/gold_only.py b/gold_only.py\n+LEAK\n",
        "target_file_contents": {
            VALIDATORS: "regex = r'^[\\w.@+-]+$'\n",
        },
    }
    ctx = instance_turn_context(row)
    assert "file_contents" in ctx
    assert "regex = r'^[\\w.@+-]+$'" in ctx
    assert "LEAK" not in ctx
    assert "gold_only" not in ctx
    flags = instance_field_flags(row)
    assert flags["has_file_contents"] is True
    assert flags["has_target_paths"] is True


def test_copy_paths_from_eval_image_mocked_docker_cp(monkeypatch):
    """Unpaid mock: docker create/cp/rm sequence yields file text."""
    blob = "from django.core import validators\nregex = r'^x$'\n"
    calls: list[list[str]] = []

    def fake_run(cmd, *, timeout=120, **_kwargs):
        calls.append(list(cmd))
        if cmd[:2] == ["docker", "info"]:
            return SimpleNamespace(returncode=0, stdout="ok", stderr="")
        if cmd[:3] == ["docker", "image", "inspect"]:
            return SimpleNamespace(returncode=0, stdout="[]", stderr="")
        if cmd[:2] == ["docker", "create"]:
            return SimpleNamespace(returncode=0, stdout="cid123\n", stderr="")
        if cmd[:2] == ["docker", "cp"]:
            dest = Path(cmd[3])
            dest.write_text(blob, encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if cmd[:3] == ["docker", "rm", "-f"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=1, stdout="", stderr="nope")

    monkeypatch.setattr(
        "aiand_router.docker_file_context.shutil.which", lambda _: "docker"
    )
    monkeypatch.delenv("VERIFIED_FILE_CONTEXT", raising=False)
    out = copy_paths_from_eval_image(
        "django__django-11099",
        [VALIDATORS, "../evil"],
        run=fake_run,
    )
    assert out == {VALIDATORS: blob}
    assert any(c[:2] == ["docker", "create"] for c in calls)
    assert any(c[:2] == ["docker", "cp"] for c in calls)
    assert any(c[:3] == ["docker", "rm", "-f"] for c in calls)


def test_copy_paths_unavailable_when_image_missing(monkeypatch):
    def fake_run(cmd, *, timeout=120, **_kwargs):
        if cmd[:2] == ["docker", "info"]:
            return SimpleNamespace(returncode=0, stdout="ok", stderr="")
        if cmd[:3] == ["docker", "image", "inspect"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="missing")
        raise AssertionError(f"unexpected docker call: {cmd}")

    monkeypatch.setattr(
        "aiand_router.docker_file_context.shutil.which", lambda _: "docker"
    )
    monkeypatch.delenv("VERIFIED_FILE_CONTEXT", raising=False)
    assert (
        copy_paths_from_eval_image(
            "django__django-11099", [VALIDATORS], run=fake_run
        )
        == {}
    )


def test_ensure_target_file_contents_caches_and_falls_back(monkeypatch):
    monkeypatch.setenv("VERIFIED_FILE_CONTEXT", "0")
    row = {
        "instance_id": "django__django-11099",
        "repo": "django/django",
        "problem_statement": "Fix validators in contrib.auth.validators.",
    }
    out = ensure_target_file_contents(row)
    assert out["file_context_source"] == "unavailable"
    assert "target_file_contents" not in out
    # Cache: second call must not re-attempt.
    out2 = ensure_target_file_contents(out)
    assert out2 is out or out2.get("_file_context_attempted")


def test_verified_turn_context_uses_cached_contents(monkeypatch):
    monkeypatch.setenv("VERIFIED_FILE_CONTEXT", "0")
    row = {
        "instance_id": "x__y-1",
        "problem_statement": "see pkg/mod.py",
        "target_file_contents": {"pkg/mod.py": "x = 1\n"},
        "_file_context_attempted": True,
        "file_context_source": "docker_cp",
    }
    ctx = verified_turn_context(row)
    assert "### pkg/mod.py" in ctx
    assert "x = 1" in ctx


def test_normalize_repo_and_commit():
    assert normalize_repo("django/django") == "django/django"
    assert normalize_repo("https://github.com/django/django.git") == "django/django"
    assert normalize_repo("../evil") is None
    assert normalize_commit(DJANGO_BASE) == DJANGO_BASE
    assert normalize_commit("not-a-sha") is None


def test_copy_paths_from_git_mocked(tmp_path, monkeypatch):
    """Unpaid mock: git init/fetch/show yields file text; second call hits blob cache."""
    blob = "from django.core import validators\nregex = r'^x$'\n"
    calls: list[list[str]] = []

    def fake_run(cmd, *, timeout=120, **_kwargs):
        calls.append(list(cmd))
        if cmd[:2] == ["git", "--version"]:
            return SimpleNamespace(returncode=0, stdout="git version 2.0", stderr="")
        if cmd[:2] == ["git", "init"]:
            Path(cmd[2]).mkdir(parents=True, exist_ok=True)
            (Path(cmd[2]) / ".git").mkdir(exist_ok=True)
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if len(cmd) >= 4 and cmd[3] == "remote":
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if len(cmd) >= 4 and cmd[3] == "cat-file":
            fetched = any(len(c) >= 4 and c[3] == "fetch" for c in calls[:-1])
            return SimpleNamespace(
                returncode=0 if fetched else 1, stdout="", stderr=""
            )
        if len(cmd) >= 4 and cmd[3] == "fetch":
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if len(cmd) >= 4 and cmd[3] == "show":
            return SimpleNamespace(returncode=0, stdout=blob, stderr="")
        return SimpleNamespace(returncode=1, stdout="", stderr="nope")

    monkeypatch.setattr(
        "aiand_router.git_file_context.shutil.which", lambda _: "git"
    )
    monkeypatch.delenv("VERIFIED_FILE_CONTEXT", raising=False)
    monkeypatch.delenv("VERIFIED_FILE_CONTEXT_GIT", raising=False)

    files, err = copy_paths_from_git(
        DJANGO_REPO,
        DJANGO_BASE,
        [VALIDATORS, "../evil"],
        cache_dir=tmp_path,
        run=fake_run,
    )
    assert err is None
    assert files == {VALIDATORS: blob}
    assert any(len(c) >= 4 and c[3] == "fetch" for c in calls)
    assert any(len(c) >= 4 and c[3] == "show" for c in calls)

    # Blob cache: second read should not re-show.
    calls.clear()

    def fake_run_cache(cmd, *, timeout=120, **_kwargs):
        calls.append(list(cmd))
        if cmd[:2] == ["git", "--version"]:
            return SimpleNamespace(returncode=0, stdout="git version 2.0", stderr="")
        if len(cmd) >= 4 and cmd[3] == "cat-file":
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if len(cmd) >= 4 and cmd[3] == "show":
            raise AssertionError("should use blob cache, not git show")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    files2, err2 = copy_paths_from_git(
        DJANGO_REPO,
        DJANGO_BASE,
        [VALIDATORS],
        cache_dir=tmp_path,
        run=fake_run_cache,
    )
    assert err2 is None
    assert files2 == {VALIDATORS: blob}
    assert not any(len(c) >= 4 and c[3] == "show" for c in calls)


def test_copy_paths_from_git_fetch_failure_is_honest(tmp_path, monkeypatch):
    def fake_run(cmd, *, timeout=120, **_kwargs):
        if cmd[:2] == ["git", "--version"]:
            return SimpleNamespace(returncode=0, stdout="git version 2.0", stderr="")
        if cmd[:2] == ["git", "init"]:
            Path(cmd[2]).mkdir(parents=True, exist_ok=True)
            (Path(cmd[2]) / ".git").mkdir(exist_ok=True)
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if len(cmd) >= 4 and cmd[3] == "remote":
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if len(cmd) >= 4 and cmd[3] == "cat-file":
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        if len(cmd) >= 4 and cmd[3] == "fetch":
            return SimpleNamespace(
                returncode=1, stdout="", stderr="Could not resolve host"
            )
        return SimpleNamespace(returncode=1, stdout="", stderr="nope")

    monkeypatch.setattr(
        "aiand_router.git_file_context.shutil.which", lambda _: "git"
    )
    monkeypatch.delenv("VERIFIED_FILE_CONTEXT", raising=False)
    monkeypatch.delenv("VERIFIED_FILE_CONTEXT_GIT", raising=False)

    files, err = copy_paths_from_git(
        DJANGO_REPO,
        DJANGO_BASE,
        [VALIDATORS],
        cache_dir=tmp_path,
        run=fake_run,
    )
    assert files == {}
    assert err is not None
    assert "git_fetch_failed" in err


def test_resolve_prefers_docker_when_image_present(monkeypatch, tmp_path):
    blob = "docker_bytes\n"

    def fake_run(cmd, *, timeout=120, **_kwargs):
        if cmd[:2] == ["docker", "info"]:
            return SimpleNamespace(returncode=0, stdout="ok", stderr="")
        if cmd[:3] == ["docker", "image", "inspect"]:
            return SimpleNamespace(returncode=0, stdout="[]", stderr="")
        if cmd[:2] == ["docker", "create"]:
            return SimpleNamespace(returncode=0, stdout="cid\n", stderr="")
        if cmd[:2] == ["docker", "cp"]:
            Path(cmd[3]).write_text(blob, encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if cmd[:3] == ["docker", "rm", "-f"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if cmd[:2] == ["git", "--version"] or (
            len(cmd) >= 2 and cmd[0] == "git"
        ):
            raise AssertionError("git must not run when docker_cp succeeds")
        return SimpleNamespace(returncode=1, stdout="", stderr="")

    monkeypatch.setattr(
        "aiand_router.docker_file_context.shutil.which", lambda _: "docker"
    )
    monkeypatch.delenv("VERIFIED_FILE_CONTEXT", raising=False)
    monkeypatch.delenv("VERIFIED_FILE_CONTEXT_GIT", raising=False)

    files, source, err = resolve_target_file_contents(
        {
            "instance_id": "django__django-11099",
            "repo": DJANGO_REPO,
            "base_commit": DJANGO_BASE,
            "problem_statement": "Fix validators in contrib.auth.validators.",
        },
        paths=[VALIDATORS],
        run=fake_run,
        cache_dir=tmp_path,
    )
    assert err is None
    assert source == "docker_cp"
    assert files == {VALIDATORS: blob}


def test_resolve_git_fallback_when_image_missing(monkeypatch, tmp_path):
    blob = "git_bytes\n"

    def fake_run(cmd, *, timeout=120, **_kwargs):
        if cmd[:2] == ["docker", "info"]:
            return SimpleNamespace(returncode=0, stdout="ok", stderr="")
        if cmd[:3] == ["docker", "image", "inspect"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="missing")
        if cmd[:2] == ["git", "--version"]:
            return SimpleNamespace(returncode=0, stdout="git version 2.0", stderr="")
        if cmd[:2] == ["git", "init"]:
            Path(cmd[2]).mkdir(parents=True, exist_ok=True)
            (Path(cmd[2]) / ".git").mkdir(exist_ok=True)
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if len(cmd) >= 4 and cmd[3] == "remote":
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if len(cmd) >= 4 and cmd[3] == "cat-file":
            fetched = getattr(fake_run, "_fetched", False)
            return SimpleNamespace(
                returncode=0 if fetched else 1, stdout="", stderr=""
            )
        if len(cmd) >= 4 and cmd[3] == "fetch":
            fake_run._fetched = True
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if len(cmd) >= 4 and cmd[3] == "show":
            return SimpleNamespace(returncode=0, stdout=blob, stderr="")
        return SimpleNamespace(returncode=1, stdout="", stderr="")

    monkeypatch.setattr(
        "aiand_router.docker_file_context.shutil.which", lambda _: "docker"
    )
    monkeypatch.setattr(
        "aiand_router.git_file_context.shutil.which", lambda _: "git"
    )
    monkeypatch.delenv("VERIFIED_FILE_CONTEXT", raising=False)
    monkeypatch.delenv("VERIFIED_FILE_CONTEXT_GIT", raising=False)

    out = ensure_target_file_contents(
        {
            "instance_id": "django__django-99999",
            "repo": DJANGO_REPO,
            "base_commit": DJANGO_BASE,
            "problem_statement": "Fix validators in contrib.auth.validators.",
        },
        run=fake_run,
        cache_dir=tmp_path,
    )
    assert out["file_context_source"] == "git"
    assert out["target_file_contents"] == {VALIDATORS: blob}
    assert "file_context_error" not in out


def test_ensure_git_error_recorded_when_fetch_fails(monkeypatch, tmp_path):
    def fake_run(cmd, *, timeout=120, **_kwargs):
        if cmd[:2] == ["docker", "info"]:
            return SimpleNamespace(returncode=0, stdout="ok", stderr="")
        if cmd[:3] == ["docker", "image", "inspect"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="missing")
        if cmd[:2] == ["git", "--version"]:
            return SimpleNamespace(returncode=0, stdout="git version 2.0", stderr="")
        if cmd[:2] == ["git", "init"]:
            Path(cmd[2]).mkdir(parents=True, exist_ok=True)
            (Path(cmd[2]) / ".git").mkdir(exist_ok=True)
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if len(cmd) >= 4 and cmd[3] == "remote":
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if len(cmd) >= 4 and cmd[3] == "cat-file":
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        if len(cmd) >= 4 and cmd[3] == "fetch":
            return SimpleNamespace(returncode=1, stdout="", stderr="network down")
        return SimpleNamespace(returncode=1, stdout="", stderr="")

    monkeypatch.setattr(
        "aiand_router.docker_file_context.shutil.which", lambda _: "docker"
    )
    monkeypatch.setattr(
        "aiand_router.git_file_context.shutil.which", lambda _: "git"
    )
    monkeypatch.delenv("VERIFIED_FILE_CONTEXT", raising=False)
    monkeypatch.delenv("VERIFIED_FILE_CONTEXT_GIT", raising=False)

    out = ensure_target_file_contents(
        {
            "instance_id": "django__django-99999",
            "repo": DJANGO_REPO,
            "base_commit": DJANGO_BASE,
            "problem_statement": "Fix validators in contrib.auth.validators.",
        },
        run=fake_run,
        cache_dir=tmp_path,
    )
    assert out["file_context_source"] == "unavailable"
    assert "target_file_contents" not in out
    assert "git_fetch_failed" in str(out.get("file_context_error") or "")


def _local_django_image() -> bool:
    try:
        proc = subprocess.run(
            ["docker", "image", "inspect", DJANGO_IMAGE],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def _git_network_ok() -> bool:
    if not shutil.which("git"):
        return False
    try:
        proc = subprocess.run(
            [
                "git",
                "ls-remote",
                "--heads",
                "https://github.com/django/django.git",
                "main",
            ],
            capture_output=True,
            text=True,
            timeout=45,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0 and bool((proc.stdout or "").strip())


@pytest.mark.skipif(not _local_django_image(), reason="django-11099 eval image not local")
def test_real_docker_cp_django_11099_validators_unpaid():
    """Unpaid smoke: real docker create+cp of validators.py (no LLM)."""
    assert docker_image_present(DJANGO_IMAGE)
    files = load_target_file_contents(
        {
            "instance_id": "django__django-11099",
            "repo": "django/django",
            "problem_statement": "Fix ASCIIUsernameValidator in contrib.auth.validators.",
        }
    )
    assert VALIDATORS in files
    text = files[VALIDATORS]
    assert "ASCIIUsernameValidator" in text
    # base_commit buggy anchors end with $ (gold would use \\Z)
    assert "regex = r'^[\\w.@+-]+$'" in text


@pytest.mark.skipif(not _git_network_ok(), reason="git network to github.com unavailable")
def test_real_git_fetch_django_11099_validators_unpaid(tmp_path):
    """Unpaid live git shallow fetch of validators.py (no LLM, no docker pull)."""
    files, err = copy_paths_from_git(
        DJANGO_REPO,
        DJANGO_BASE,
        [VALIDATORS],
        cache_dir=tmp_path / "repo_cache",
    )
    assert err is None, err
    assert VALIDATORS in files
    text = files[VALIDATORS]
    assert "ASCIIUsernameValidator" in text
    assert "regex = r'^[\\w.@+-]+$'" in text

    # Aggressive cache: re-read without re-fetch (blob file present).
    repo_dir, err2 = ensure_commit_fetched(
        DJANGO_REPO, DJANGO_BASE, cache_dir=tmp_path / "repo_cache"
    )
    assert err2 is None
    assert repo_dir is not None
    blob = repo_dir / "blobs" / DJANGO_BASE / VALIDATORS
    assert blob.is_file()
