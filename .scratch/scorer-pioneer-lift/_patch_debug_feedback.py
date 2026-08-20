from pathlib import Path

path = Path("src/aiand_router/verified_runner.py")
text = path.read_text(encoding="utf-8")

helper = '''
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
    snippet = "\\n".join(keep[-12:] if keep else lines[-8:])
    if len(snippet) > 900:
        snippet = snippet[-900:]
    bits = []
    if reason:
        bits.append(f"reason={reason}")
    if snippet:
        bits.append(snippet)
    return (
        base
        + "\\n\\nPrior harness feedback (fix the patch; do not repeat the same "
        "malformed hunks or test-file edits):\\n"
        + "\\n".join(bits)
    )


'''

anchor = "def verified_turn_instruction(phase: str, instance: dict[str, Any] | None = None) -> str:"
if "_debug_instruction_with_harness_feedback" not in text:
    if anchor not in text:
        raise SystemExit("anchor missing")
    text = text.replace(anchor, helper + anchor, 1)

old_trained = '''        out = decide_resolve(edit_text, enriched)
        if out.get("resolved") is False or out.get("swe_eval_attempted"):
            debug_text = gateway_fn(
                "debug",
                context + "\\n\\n" + verified_turn_instruction("debug", enriched),
            )
            out = decide_resolve(debug_text, enriched)'''

new_trained = '''        out = decide_resolve(edit_text, enriched)
        if out.get("resolved") is False or out.get("swe_eval_attempted"):
            debug_text = gateway_fn(
                "debug",
                context
                + "\\n\\n"
                + _debug_instruction_with_harness_feedback(enriched, out),
            )
            out = decide_resolve(debug_text, enriched)'''

old_rules = '''    rules_out = decide_resolve(edit_text, enriched)
    if rules_out.get("resolved") is False or rules_out.get("swe_eval_attempted"):
        debug_text = gateway_fn(
            "debug",
            context + "\\n\\n" + verified_turn_instruction("debug", enriched),
        )
        rules_out = decide_resolve(debug_text, enriched)'''

new_rules = '''    rules_out = decide_resolve(edit_text, enriched)
    if rules_out.get("resolved") is False or rules_out.get("swe_eval_attempted"):
        debug_text = gateway_fn(
            "debug",
            context
            + "\\n\\n"
            + _debug_instruction_with_harness_feedback(enriched, rules_out),
        )
        rules_out = decide_resolve(debug_text, enriched)'''

if old_trained not in text:
    raise SystemExit("trained block not found")
if old_rules not in text:
    raise SystemExit("rules block not found")
text = text.replace(old_trained, new_trained, 1)
text = text.replace(old_rules, new_rules, 1)
path.write_text(text, encoding="utf-8")
print("patched verified_runner.py ok")
