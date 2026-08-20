from pathlib import Path

path = Path("tests/test_verified_runner.py")
text = path.read_text(encoding="utf-8")
marker = "def test_live_debug_runs_when_swe_eval_apply_fails"
if "test_debug_instruction_includes_harness_feedback" in text:
    print("test already present")
    raise SystemExit(0)

insert = '''
def test_debug_instruction_includes_harness_feedback():
    from aiand_router.verified_runner import _debug_instruction_with_harness_feedback

    inst = {"instance_id": "django__django-10914", "target_file_contents": {"django/conf/global_settings.py": "X = 1\\n"}}
    prior = {
        "swe_eval_reason": "swebench_instance_error",
        "swe_eval_detail": (
            ">>>>> Patch Apply Failed:\\n"
            "patching file django/conf/global_settings.py\\n"
            "Hunk #1 succeeded at 305.\\n"
            "patching file tests/test_utils/tests.py\\n"
            "Hunk #1 FAILED at 1306.\\n"
        ),
    }
    text = _debug_instruction_with_harness_feedback(inst, prior)
    assert "Prior harness feedback" in text
    assert "Hunk #1 FAILED" in text
    assert "tests/test_utils/tests.py" in text
    assert "django/conf/global_settings.py" in text  # target path from instruction


'''

# Also strengthen live debug test to capture debug content
old = '''        if request.url.path == "/v1/chat/completions":
            phase = request.headers.get("x-agent-phase", "")
            phases.append(phase)
            content = (
                "```diff\\n"
                "diff --git a/x.py b/x.py\\n"
                "--- a/x.py\\n"
                "+++ b/x.py\\n"
                "@@ -1 +1 @@\\n"
                "-a\\n"
                "+b\\n"
                "```\\n"
            )
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": content}}]},
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(base_url="http://test", transport=transport)
    spend = tmp_path / "spend.txt"
    spend.write_text("0\\n", encoding="utf-8")
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
'''

# Simpler: just insert unit test before the live debug test
if marker not in text:
    raise SystemExit("marker missing")
text = text.replace(marker, insert + marker, 1)
path.write_text(text, encoding="utf-8")
print("test inserted")
