from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

from aiand_router.lite_runner import instance_turn_context
from aiand_router.verified_runner import (
    BudgetExceededError,
    GatewayNotRunningError,
    assert_budget_headroom,
    budget_status,
    check_gateway,
    decide_resolve,
    extract_unified_diff,
    looks_like_unified_diff,
    load_offline_gold,
    load_verified_ids,
    load_verified_instances,
    main,
    run_verified_sessions,
    summarize_sessions,
    _parse_swe_eval_stdout,
    _TURNS,
)

ROOT = Path(__file__).resolve().parents[1]
CHECKED_IN_SCAFFOLD = ROOT / "data" / "verified_ids_scaffold.json"
CHECKED_IN_FIXTURE = ROOT / "tests" / "fixtures" / "lite_comparison" / "fixture.json"
VERIFIED_INSTANCES = ROOT / "tests" / "fixtures" / "verified_instances" / "instances.jsonl"
OFFLINE_GOLD = ROOT / "tests" / "fixtures" / "verified_instances" / "offline_gold.jsonl"


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_load_verified_ids_from_scaffold():
    if not CHECKED_IN_SCAFFOLD.exists():
        pytest.skip("scaffold missing")
    ids = load_verified_ids(scaffold_path=CHECKED_IN_SCAFFOLD)
    assert len(ids) >= 300
    assert ids[0]


def test_load_verified_ids_from_json_list(tmp_path):
    path = tmp_path / "ids.json"
    path.write_text(json.dumps(["a__b-1", "a__b-2"]), encoding="utf-8")
    assert load_verified_ids(ids_path=path) == ["a__b-1", "a__b-2"]


def test_load_verified_instances_from_local_dump():
    ids = ["astropy__astropy-12907", "django__django-11099"]
    loaded = load_verified_instances(ids, dump_path=VERIFIED_INSTANCES, fetch=False)
    assert set(loaded) == set(ids)
    assert "coordinates transform" in loaded["astropy__astropy-12907"]["problem_statement"]
    assert loaded["django__django-11099"]["repo"] == "django/django"


def test_instance_turn_context_includes_fields_not_gold_patch():
    row = load_verified_instances(
        ["astropy__astropy-12907"], dump_path=VERIFIED_INSTANCES, fetch=False
    )["astropy__astropy-12907"]
    ctx = instance_turn_context(row)
    assert "problem_statement:" in ctx
    assert "coordinates transform" in ctx
    assert "FAIL_TO_PASS" in ctx
    assert "astropy/astropy" in ctx
    assert "GOLD_SHOULD_NOT_LEAK" not in ctx
    assert "diff --git" not in ctx


def test_guess_target_paths_from_problem_module_and_explicit_path():
    from aiand_router.lite_runner import guess_target_paths

    row = {
        "repo": "django/django",
        "problem_statement": (
            "Fix the two validators in contrib.auth.validators. "
            "Also see django/contrib/auth/validators.py for the regex."
        ),
        "hints_text": "",
        "patch": "diff --git a/gold_only.py b/gold_only.py\n+LEAK\n",
    }
    paths = guess_target_paths(row)
    assert "django/contrib/auth/validators.py" in paths
    assert "gold_only.py" not in paths
    ctx = instance_turn_context(row)
    assert "likely_target_files" in ctx
    assert "django/contrib/auth/validators.py" in ctx
    assert "LEAK" not in ctx
    assert "gold_only" not in ctx


def test_guess_target_paths_empty_without_mentions():
    from aiand_router.lite_runner import guess_target_paths

    assert guess_target_paths({"problem_statement": "Something broke.", "repo": "x/y"}) == []


def test_guess_target_paths_from_github_blob_url():
    """Slash-prefixed paths in blob URLs are missed by _FILE_PATH_RE lookbehind."""
    from aiand_router.lite_runner import guess_target_paths

    row = {
        "repo": "django/django",
        "problem_statement": (
            "See https://github.com/django/django/blob/"
            "586a9dc4295357de1f5ad0590ad34bf2bc008f79/"
            "django/contrib/contenttypes/management/__init__.py#L27\n"
            "Also unrelated https://github.com/other/lib/blob/master/lib/router.py"
        ),
        "hints_text": "",
        "patch": "diff --git a/gold_only.py b/gold_only.py\n+LEAK\n",
    }
    paths = guess_target_paths(row)
    assert paths[0] == "django/contrib/contenttypes/management/__init__.py"
    assert "lib/router.py" in paths
    assert "gold_only.py" not in paths


def test_guess_target_paths_prefers_fail_to_pass_related_over_distractors():
    """FAIL_TO_PASS / primary paths rank ahead of problem-statement distractors."""
    from aiand_router.lite_runner import guess_target_paths

    row = {
        "repo": "django/django",
        "FAIL_TO_PASS": [
            "tests/migrations/test_executor.py::MigrationExecutorTests::test_hooks"
        ],
        "problem_statement": (
            "Something broke in django/test/runner.py and also "
            "django/db/migrations/executor.py needs a fix."
        ),
        "hints_text": "",
        "patch": "diff --git a/gold.py b/gold.py\n+LEAK\n",
    }
    paths = guess_target_paths(row, limit=4)
    assert paths == ["django/db/migrations/executor.py"]
    assert "django/test/runner.py" not in paths
    assert "gold.py" not in paths


def test_guess_target_paths_legacy_f2p_and_primary_over_tests():
    """Legacy nodeids map to tests/; related primary still ranks first."""
    from aiand_router.lite_runner import guess_target_paths, paths_from_fail_to_pass

    assert paths_from_fail_to_pass(
        ["test_live_server_url_is_class_property (servers.tests.LiveServerAddress)"]
    ) == ["tests/servers/tests.py"]

    row = {
        "repo": "django/django",
        "FAIL_TO_PASS": [
            "test_live_server_url_is_class_property (servers.tests.LiveServerAddress)"
        ],
        "problem_statement": (
            "LiveServerTestCase in django/test/testcases.py; also fix "
            "django/core/servers/basehttp.py connection cleanup."
        ),
        "hints_text": "",
    }
    paths = guess_target_paths(row, limit=2)
    assert paths[0] == "django/core/servers/basehttp.py"
    assert all(not p.startswith("tests/") for p in paths)
    assert "django/test/testcases.py" not in paths


def test_guess_target_paths_settings_hint_global_settings():
    from aiand_router.lite_runner import guess_target_paths

    row = {
        "repo": "django/django",
        "FAIL_TO_PASS": [
            "test_override_file_upload_permissions (test_utils.tests.OverrideSettingsTests)"
        ],
        "problem_statement": (
            "Set default FILE_UPLOAD_PERMISSIONS to 0o644 when unset."
        ),
        "hints_text": "",
    }
    paths = guess_target_paths(row, limit=2)
    assert paths == ["django/conf/global_settings.py"]


def test_guess_target_paths_filters_junk_py_py():
    from aiand_router.lite_runner import guess_target_paths

    row = {
        "repo": "django/django",
        "problem_statement": (
            "See django/test_autodetector/py.py and manage.py; "
            "real fix is django/db/migrations/autodetector.py"
        ),
        "FAIL_TO_PASS": ["tests/migrations/test_autodetector.py::T::test_x"],
    }
    paths = guess_target_paths(row, limit=4)
    assert "django/test_autodetector/py.py" not in paths
    assert "manage.py" not in paths
    assert "django/db/migrations/autodetector.py" in paths


def test_verified_turn_instruction_uses_copied_file_paths():
    from aiand_router.verified_runner import verified_turn_instruction

    inst = {
        "repo": "django/django",
        "problem_statement": "Change django/test/runner.py somehow.",
        "target_file_contents": {
            "django/db/migrations/executor.py": "class Executor:\n    pass\n",
        },
    }
    edit = verified_turn_instruction("edit", inst)
    assert "django/db/migrations/executor.py" in edit
    assert "django/test/runner.py" not in edit


def test_instance_turn_context_lists_copied_paths_only():
    from aiand_router.lite_runner import instance_turn_context

    row = {
        "instance_id": "django__django-1",
        "repo": "django/django",
        "problem_statement": "Mentions django/test/runner.py as a red herring.",
        "target_file_contents": {
            "django/db/migrations/executor.py": "x = 1\n",
        },
    }
    ctx = instance_turn_context(row)
    assert "django/db/migrations/executor.py" in ctx
    # likely_target_files block should list copied path, not distractor-first.
    assert "likely_target_files" in ctx
    idx = ctx.index("likely_target_files")
    block = ctx[idx : idx + 200]
    assert "django/db/migrations/executor.py" in block


def test_django_11066_dump_guesses_contenttypes_path():
    dump = ROOT / "data" / "dump_cache" / "swe_verified.jsonl"
    if not dump.exists():
        pytest.skip("dump cache missing")
    loaded = load_verified_instances(
        ["django__django-11066"], dump_path=dump, fetch=False
    )
    if "django__django-11066" not in loaded:
        pytest.skip("django-11066 not in dump")
    from aiand_router.lite_runner import guess_target_paths

    paths = guess_target_paths(loaded["django__django-11066"])
    assert "django/contrib/contenttypes/management/__init__.py" in paths


def test_verified_turn_instruction_names_target_paths():
    from aiand_router.verified_runner import verified_turn_instruction

    inst = {
        "repo": "django/django",
        "problem_statement": "Change validators in contrib.auth.validators.",
    }
    edit = verified_turn_instruction("edit", inst)
    assert "django/contrib/auth/validators.py" in edit
    assert "minimal unified-diff" in edit
    assert "exactly" in edit.lower()
    debug = verified_turn_instruction("debug", inst)
    assert "django/contrib/auth/validators.py" in debug
    assert verified_turn_instruction("edit", {"problem_statement": "no paths"}) == dict(
        _TURNS
    )["edit"]


def test_django_11099_dump_context_names_validators_path():
    """Real unpaid dump row (if present): module phrase → target path; no gold leak."""
    dump = ROOT / "data" / "dump_cache" / "swe_verified.jsonl"
    if not dump.exists():
        pytest.skip("dump cache missing")
    loaded = load_verified_instances(
        ["django__django-11099"], dump_path=dump, fetch=False
    )
    if "django__django-11099" not in loaded:
        pytest.skip("django-11099 not in dump")
    row = loaded["django__django-11099"]
    from aiand_router.lite_runner import guess_target_paths

    paths = guess_target_paths(row)
    assert paths[0] == "django/contrib/auth/validators.py"
    assert "django/contrib/auth/validators.py" in paths
    # Default limit=2 may also include the F2P test file — primary must lead.
    assert len(paths) <= 2
    ctx = instance_turn_context(row)
    assert "FAIL_TO_PASS" in ctx
    assert "test_ascii_validator" in ctx
    assert "likely_target_files" in ctx
    assert "django/contrib/auth/validators.py" in ctx
    gold = str(row.get("patch") or "")
    assert gold
    # Gold body must never appear in turn context.
    assert "+    regex = r'^[\\w.@+-]+\\Z'" not in ctx
    assert gold not in ctx


def test_decide_resolve_swe_fields_unlabeled():
    row = load_verified_instances(
        ["astropy__astropy-12907"], dump_path=VERIFIED_INSTANCES, fetch=False
    )["astropy__astropy-12907"]
    out = decide_resolve("```python\npass\n```", row)
    assert out["resolved"] is None
    assert out["label_type"] == "needs_swe_eval"
    assert out["session_gold"] is False


def test_decide_resolve_harness_proxy_can_pass():
    instance = {
        "instance_id": "local-fix",
        "module": "fix.py",
        "tests": "from fix import fix\n\ndef test_fix():\n    assert fix() == 42\n",
    }
    text = "```python\ndef fix():\n    return 42\n```"
    out = decide_resolve(text, instance)
    assert out["resolved"] is True
    assert out["label_type"] == "harness_proxy"
    assert out["session_gold"] is False


def test_offline_gold_join(tmp_path):
    out = tmp_path / "sessions.jsonl"
    ids = ["astropy__astropy-12907", "django__django-11099"]
    gold = load_offline_gold(OFFLINE_GOLD)
    summary = run_verified_sessions(
        ids,
        out_path=out,
        instances_path=VERIFIED_INSTANCES,
        offline_gold=gold,
        fetch_instances=False,
    )
    rows = _read_jsonl(out)
    assert len(rows) == 2
    assert rows[0]["label_type"] == "offline_gold"
    assert rows[0]["session_gold"] is False
    assert rows[0]["policies"]["rules"]["resolved"] is False
    assert rows[0]["policies"]["trained"]["resolved"] is True
    assert rows[0]["instance_fields"]["has_problem_statement"] is True
    assert rows[1]["policies"]["rules"]["resolved"] is True
    assert summary["verdict"] == "bounded_check_only"
    assert summary["session_gold"] is False


def test_dry_run_includes_gateway_start_and_budget(tmp_path):
    scaffold = tmp_path / "scaffold.json"
    scaffold.write_text(
        json.dumps(
            {
                "verdict": "ids_scaffold_only",
                "bench": "verified",
                "n": 2,
                "session_gold": False,
                "production_parity": False,
                "instance_ids": ["x__y-1", "x__y-2"],
            }
        ),
        encoding="utf-8",
    )
    spend = tmp_path / "spend.txt"
    spend.write_text("0\n", encoding="utf-8")
    rc = main(
        [
            "--dry-run",
            "--limit",
            "2",
            "--scaffold",
            str(scaffold),
            "--spend",
            str(spend),
            "--budget-limit",
            "15",
            "--no-fetch",
            "--instances",
            str(VERIFIED_INSTANCES),
        ]
    )
    assert rc == 0


def test_dry_run_reports_instance_context_counts(tmp_path):
    out = tmp_path / "unused.jsonl"
    spend = tmp_path / "spend.txt"
    spend.write_text("0\n", encoding="utf-8")
    summary = run_verified_sessions(
        ["astropy__astropy-12907", "missing__id-1"],
        dry_run=True,
        out_path=out,
        instances_path=VERIFIED_INSTANCES,
        fetch_instances=False,
        spend_path=spend,
        limit_usd=15.0,
    )
    assert summary["instances_loaded"] == 1
    assert summary["instances_with_problem_statement"] == 1
    assert summary["session_gold"] is False


def test_budget_guard_refuses_when_over_cap(tmp_path):
    spend = tmp_path / "spend.txt"
    spend.write_text("14.9\n", encoding="utf-8")
    with pytest.raises(BudgetExceededError, match="budget headroom insufficient"):
        assert_budget_headroom(
            n_instances=500,
            spend_path=spend,
            limit_usd=15.0,
            models_path=ROOT / "config" / "models.yaml",
        )


def test_budget_status_reads_spend(tmp_path):
    spend = tmp_path / "spend.txt"
    spend.write_text("1.25\n", encoding="utf-8")
    status = budget_status(spend_path=spend, limit_usd=15.0)
    assert status["spent_usd"] == 1.25
    assert status["remaining_usd"] == 13.75


def test_check_gateway_raises_with_startup_command():
    with pytest.raises(GatewayNotRunningError, match="TRAINED_PATH='shadow'"):
        check_gateway("http://127.0.0.1:59999")


def test_fixture_replay_writes_session_rows(tmp_path):
    if not CHECKED_IN_FIXTURE.exists():
        pytest.skip("fixture missing")
    out = tmp_path / "sessions.jsonl"
    fixture = json.loads(CHECKED_IN_FIXTURE.read_text(encoding="utf-8"))
    ids = [r["instance_id"] for r in fixture[:3]]
    summary = run_verified_sessions(ids, fixture=fixture[:3], out_path=out)
    rows = _read_jsonl(out)
    assert len(rows) == 3
    assert all(r["comparison_mode"] == "fixture_replay" for r in rows)
    assert summary["verdict"] == "bounded_check_only"
    assert summary["session_gold"] is False
    assert "rules" in rows[0]["policies"]
    assert "trained" in rows[0]["policies"]


def test_summarize_sessions_live_shadow():
    rows = [
        {
            "comparison_mode": "shadow_dual_policy",
            "session_gold": True,
            "policies": {"rules": {"resolved": True}, "trained": {"resolved": False}},
        },
        {
            "comparison_mode": "shadow_dual_policy",
            "session_gold": True,
            "policies": {"rules": {"resolved": False}, "trained": {"resolved": True}},
        },
    ]
    summary = summarize_sessions(rows)
    assert summary["live_shadow_sessions"] == 2
    assert summary["rules_resolved"] == 1
    assert summary["trained_resolved"] == 1
    assert summary["session_gold"] is True
    assert summary["verdict"] == "session_gate_partial"


def test_summarize_sessions_unlabeled_not_session_gold():
    rows = [
        {
            "comparison_mode": "shadow_dual_policy",
            "session_gold": False,
            "label_type": "needs_swe_eval",
            "policies": {
                "rules": {"resolved": None},
                "trained": {"resolved": None, "counterfactual": True},
            },
        }
    ]
    summary = summarize_sessions(rows)
    assert summary["unlabeled"] == 1
    assert summary["session_gold"] is False
    assert summary["verdict"] == "bounded_check_only"
    assert summary["rules_resolve_rate"] is None


def test_live_run_mock_gateway_needs_swe_eval(tmp_path):
    calls: list[tuple[str, str, str]] = []
    outcomes: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"ok": True})
        if request.url.path == "/v1/router/outcome":
            outcomes.append(json.loads(request.content.decode("utf-8")))
            return httpx.Response(200, json={"ok": True})
        if request.url.path == "/v1/chat/completions":
            phase = request.headers.get("x-agent-phase", "")
            session = request.headers.get("x-session-id", "")
            body = json.loads(request.content.decode("utf-8"))
            content = ((body.get("messages") or [{}])[0].get("content")) or ""
            calls.append((session, phase, content))
            reply = ""
            if phase in ("edit", "debug"):
                reply = "```python\ndef fix():\n    return 42\n```"
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": reply}}]},
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(base_url="http://test", transport=transport)
    spend = tmp_path / "spend.txt"
    spend.write_text("0\n", encoding="utf-8")
    out = tmp_path / "live.jsonl"
    inst = load_verified_instances(
        ["astropy__astropy-12907"], dump_path=VERIFIED_INSTANCES, fetch=False
    )
    summary = run_verified_sessions(
        ["astropy__astropy-12907"],
        gateway_url="http://test",
        out_path=out,
        spend_path=spend,
        limit_usd=15.0,
        client=client,
        instances=inst,
        fetch_instances=False,
    )
    rows = _read_jsonl(out)
    assert rows[0]["policies"]["rules"]["resolved"] is None
    assert rows[0]["label_type"] == "needs_swe_eval"
    assert rows[0]["session_gold"] is False
    assert "trained" in rows[0]["policies"]
    assert rows[0]["policies"]["trained"]["counterfactual"] is True
    assert summary["live_shadow_sessions"] == 1
    assert summary["session_gold"] is False
    assert summary["unlabeled"] == 1
    assert outcomes == []
    assert any(
        c[0] == "astropy__astropy-12907" and c[1] == "edit" and "problem_statement:" in c[2]
        for c in calls
    )
    assert any(
        c[1] == "edit" and "unified-diff" in c[2] and "```diff" in c[2]
        for c in calls
    )
    assert any(
        c[1] == "edit" and "exactly" in c[2].lower()
        for c in calls
    )
    assert all("GOLD_SHOULD_NOT_LEAK" not in c[2] for c in calls)
    assert not any(c[0] == "astropy__astropy-12907" and c[1] == "debug" for c in calls)
    assert any(c[0] == "astropy__astropy-12907::cf-trained" for c in calls)


def test_live_run_mock_gateway_harness_proxy_nonzero(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"ok": True})
        if request.url.path == "/v1/router/outcome":
            return httpx.Response(200, json={"ok": True})
        if request.url.path == "/v1/chat/completions":
            phase = request.headers.get("x-agent-phase", "")
            content = ""
            if phase in ("edit", "debug"):
                content = "```python\ndef fix():\n    return 42\n```"
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": content}}]},
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(base_url="http://test", transport=transport)
    spend = tmp_path / "spend.txt"
    spend.write_text("0\n", encoding="utf-8")
    out = tmp_path / "live.jsonl"
    instances = {
        "local-fix": {
            "instance_id": "local-fix",
            "problem_statement": "Return 42 from fix().",
            "module": "fix.py",
            "tests": "from fix import fix\n\ndef test_fix():\n    assert fix() == 42\n",
        }
    }
    summary = run_verified_sessions(
        ["local-fix"],
        gateway_url="http://test",
        out_path=out,
        spend_path=spend,
        limit_usd=15.0,
        client=client,
        instances=instances,
        fetch_instances=False,
    )
    rows = _read_jsonl(out)
    assert rows[0]["policies"]["rules"]["resolved"] is True
    assert rows[0]["label_type"] == "harness_proxy"
    assert rows[0]["session_gold"] is False
    assert summary["rules_resolved"] == 1


def test_verified_edit_turns_ask_for_unified_diff():
    edit = dict(_TURNS)["edit"]
    debug = dict(_TURNS)["debug"]
    assert "unified-diff" in edit
    assert "```diff" in edit
    assert "full module" in edit.lower() or "Do not write a full module" in edit
    assert "exactly" in edit.lower()
    assert "verbatim" in edit.lower() or "file_contents" in edit.lower()
    assert "leading" in edit.lower() or "space" in edit.lower()
    assert "unified-diff" in debug
    assert "```diff" in debug
    assert "malformed" in debug.lower() or "space" in debug.lower()
    assert "```python" not in edit
    assert "```python" not in debug


def test_normalize_unified_diff_fixes_missing_prefix_and_counts():
    from aiand_router.verified_runner import normalize_unified_diff

    raw = (
        "diff --git a/x.py b/x.py\n"
        "--- a/x.py\n"
        "+++ b/x.py\n"
        "@@ -1,3 +1,4 @@\n"
        "class Foo:\n"  # missing leading space marker (model failure)
        "-    a = 1\n"
        "+    a = 2\n"
        "+    b = 3\n"
        "Thanks!\n"  # trailing prose
    )
    fixed = normalize_unified_diff(raw)
    assert "Thanks" not in fixed
    assert "@@ -1,2 +1,3 @@" in fixed
    lines = [ln for ln in fixed.splitlines() if ln]
    assert any(ln == " class Foo:" for ln in lines)
    assert all(
        ln.startswith((" ", "+", "-", "\\"))
        or ln.startswith(("diff ", "--- ", "+++ ", "@@"))
        for ln in lines
    )


def test_extract_unified_diff_normalizes_malformed_hunk():
    text = (
        "```diff\n"
        "diff --git a/x.py b/x.py\n"
        "--- a/x.py\n"
        "+++ b/x.py\n"
        "@@ -10,2 +10,3 @@\n"
        "keep\n"  # missing space prefix
        "-old\n"
        "+new\n"
        "+extra\n"
        "```\n"
    )
    patch, reason = extract_unified_diff(text)
    assert reason is None
    assert patch is not None
    assert patch.startswith("diff --git ")
    assert "@@ -10,2 +10,3 @@" in patch
    assert " keep\n" in patch or "\n keep\n" in patch
    assert "Thanks" not in patch


def test_extract_unified_diff_from_diff_fence():
    text = (
        "Here is the fix:\n"
        "```diff\n"
        "diff --git a/x.py b/x.py\n"
        "--- a/x.py\n"
        "+++ b/x.py\n"
        "@@ -1 +1 @@\n"
        "-a\n"
        "+b\n"
        "```\n"
    )
    patch, reason = extract_unified_diff(text)
    assert reason is None
    assert patch is not None
    assert patch.startswith("diff --git ")
    assert "+++ b/x.py" in patch


def test_extract_unified_diff_from_raw_patch():
    raw = "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n"
    patch, reason = extract_unified_diff(raw)
    assert reason is None
    assert patch is not None
    assert looks_like_unified_diff(patch)


def test_extract_unified_diff_rejects_python_fence():
    patch, reason = extract_unified_diff("```python\ndef fix():\n    return 1\n```")
    assert patch is None
    assert reason == "patch_not_unified_diff"


def test_extract_unified_diff_empty():
    patch, reason = extract_unified_diff("   \n")
    assert patch is None
    assert reason == "empty_patch"


def test_swe_eval_cmd_skips_docker_on_python_fence(monkeypatch):
    """Python module text must not be sent to docker as model_patch."""
    called: list[str] = []

    def boom(instance_id: str, patch_text: str) -> bool | None:
        called.append(patch_text)
        return True

    monkeypatch.setenv("SWE_EVAL_CMD", "echo true")
    monkeypatch.setattr(
        "aiand_router.verified_runner._run_swe_eval_cmd", boom
    )
    out = decide_resolve(
        "```python\ndef fix():\n    return 42\n```",
        {"instance_id": "x__y-1"},
    )
    assert called == []
    assert out["resolved"] is None
    assert out["label_type"] == "needs_swe_eval"
    assert out["session_gold"] is False
    assert out["patch_status"] == "patch_not_unified_diff"


def test_swe_eval_cmd_can_label_session_gold(monkeypatch):
    monkeypatch.setenv("SWE_EVAL_CMD", "echo true")
    out = decide_resolve(
        "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n",
        {"instance_id": "x__y-1"},
    )
    assert out["resolved"] is True
    assert out["label_type"] == "session_gold"
    assert out["session_gold"] is True


def test_swe_eval_cmd_false_is_session_gold_fail(monkeypatch):
    monkeypatch.setenv("SWE_EVAL_CMD", "echo false")
    out = decide_resolve(
        "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n",
        {"instance_id": "x__y-1"},
    )
    assert out["resolved"] is False
    assert out["label_type"] == "session_gold"
    assert out["session_gold"] is True


def test_swe_eval_cmd_not_available_stays_unlabeled(monkeypatch, tmp_path):
    """resolved:null / status:not_available must not become fake False."""
    assert (
        _parse_swe_eval_stdout('{"resolved": null, "status": "not_available"}')
        is None
    )
    helper = tmp_path / "emit_na.py"
    helper.write_text(
        "import json\n"
        "print(json.dumps({\n"
        "  'resolved': None,\n"
        "  'status': 'not_available',\n"
        "  'reason': 'swebench_instance_error',\n"
        "  'detail': 'Patch Apply Failed: hunk mismatch',\n"
        "}))\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "SWE_EVAL_CMD",
        f'"{sys.executable}" "{helper}"',
    )
    out = decide_resolve(
        "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n",
        {"instance_id": "x__y-1"},
    )
    assert out["resolved"] is None
    assert out["label_type"] == "needs_swe_eval"
    assert out["session_gold"] is False
    assert out.get("swe_eval_attempted") is True
    assert out.get("swe_eval_reason") == "swebench_instance_error"
    assert "Patch Apply Failed" in str(out.get("swe_eval_detail") or "")



def test_debug_instruction_includes_harness_feedback():
    from aiand_router.verified_runner import _debug_instruction_with_harness_feedback

    inst = {"instance_id": "django__django-10914", "target_file_contents": {"django/conf/global_settings.py": "X = 1\n"}}
    prior = {
        "swe_eval_reason": "swebench_instance_error",
        "swe_eval_detail": (
            ">>>>> Patch Apply Failed:\n"
            "patching file django/conf/global_settings.py\n"
            "Hunk #1 succeeded at 305.\n"
            "patching file tests/test_utils/tests.py\n"
            "Hunk #1 FAILED at 1306.\n"
        ),
    }
    text = _debug_instruction_with_harness_feedback(inst, prior)
    assert "Prior harness feedback" in text
    assert "Hunk #1 FAILED" in text
    assert "tests/test_utils/tests.py" in text
    assert "django/conf/global_settings.py" in text  # target path from instruction


def test_live_debug_runs_when_swe_eval_apply_fails(tmp_path, monkeypatch):
    """Apply-fail (unlabeled after extractable patch) should still get a debug turn."""
    monkeypatch.setenv("SWE_EVAL_CMD", "echo not_a_real_eval_line")
    phases: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"ok": True})
        if request.url.path == "/v1/router/outcome":
            return httpx.Response(200, json={"ok": True})
        if request.url.path == "/v1/chat/completions":
            phase = request.headers.get("x-agent-phase", "")
            phases.append(phase)
            content = (
                "```diff\n"
                "diff --git a/x.py b/x.py\n"
                "--- a/x.py\n"
                "+++ b/x.py\n"
                "@@ -1 +1 @@\n"
                "-a\n"
                "+b\n"
                "```\n"
            )
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": content}}]},
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(base_url="http://test", transport=transport)
    spend = tmp_path / "spend.txt"
    spend.write_text("0\n", encoding="utf-8")
    out = tmp_path / "live.jsonl"
    summary = run_verified_sessions(
        ["django__django-11099"],
        out_path=out,
        spend_path=spend,
        limit_usd=15.0,
        gateway_url="http://test",
        client=client,
        instances_path=VERIFIED_INSTANCES,
        fetch_instances=False,
    )
    assert "debug" in phases
    rows = _read_jsonl(out)
    assert rows[0]["label_type"] == "needs_swe_eval"
    assert summary["session_gold"] is False


def test_swe_eval_cmd_script_mock_true(monkeypatch, tmp_path):
    script = ROOT / "scripts" / "swe_eval_cmd.py"
    assert script.is_file()
    # Use absolute python + script so shell=True works on Windows paths.
    cmd = (
        f'"{sys.executable}" "{script}" --instance {{instance_id}} '
        f'--patch {{patch_file}} --mock-resolved true'
    )
    monkeypatch.setenv("SWE_EVAL_CMD", cmd)
    out = decide_resolve("diff --git a/x b/x\n", {"instance_id": "mock__1"})
    assert out["resolved"] is True
    assert out["label_type"] == "session_gold"
    assert out["session_gold"] is True


def test_swe_eval_cmd_script_mock_false(monkeypatch):
    script = ROOT / "scripts" / "swe_eval_cmd.py"
    cmd = (
        f'"{sys.executable}" "{script}" --instance {{instance_id}} '
        f'--patch {{patch_file}} --mock-resolved false'
    )
    monkeypatch.setenv("SWE_EVAL_CMD", cmd)
    out = decide_resolve("diff --git a/x b/x\n", {"instance_id": "mock__2"})
    assert out["resolved"] is False
    assert out["label_type"] == "session_gold"
    assert out["session_gold"] is True


def test_swe_eval_cmd_script_default_not_available_without_swebench(monkeypatch):
    """Default script path must stay unlabeled when harness is missing (no fake fail)."""
    script = ROOT / "scripts" / "swe_eval_cmd.py"
    cmd = (
        f'"{sys.executable}" "{script}" --instance {{instance_id}} '
        f"--patch {{patch_file}}"
    )
    monkeypatch.setenv("SWE_EVAL_CMD", cmd)
    out = decide_resolve("diff --git a/x b/x\n", {"instance_id": "django__django-11099"})
    assert out["resolved"] is None
    assert out["label_type"] == "needs_swe_eval"
    assert out["session_gold"] is False
