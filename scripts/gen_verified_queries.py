"""Emit datasets/verified-queries.jsonl — prompts with checkable outcomes for gold.

Extra fields (optional): expected (substring), verify_pytest+module+tests, exact (full match).
hint_bin / phase / needs_tools match train-queries.jsonl. Do not put tests_passed here;
run_gold derives success from completion checks and sets success_tier on gold rows.
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "datasets" / "verified-queries.jsonl"

PARITY_TESTS = """from parity import is_even


def test_even():
    assert is_even(2) is True


def test_odd():
    assert is_even(3) is False
"""

CLAMP_TESTS = """from clamp import clamp


def test_inside():
    assert clamp(5, 0, 10) == 5


def test_below():
    assert clamp(-2, 0, 10) == 0


def test_above():
    assert clamp(99, 0, 10) == 10
"""

REVERSE_TESTS = """from reverse import reverse


def test_basic():
    assert reverse("abc") == "cba"
"""

ROWS: list[dict] = [
    # single-word / exact (trivial)
    {"prompt": "Reply with the single word yes.", "phase": "edit", "hint_bin": "trivial", "needs_tools": False},
    {"prompt": "Reply with only no.", "phase": "edit", "hint_bin": "trivial", "needs_tools": False},
    {"prompt": "Respond with only ok.", "phase": "summarize", "hint_bin": "trivial", "needs_tools": False},
    {"prompt": "Reply with the single word true.", "phase": "edit", "hint_bin": "trivial", "needs_tools": False},
    {"prompt": "Reply with only false.", "phase": "edit", "hint_bin": "trivial", "needs_tools": False},
    {"prompt": "Reply with the single word done.", "phase": "summarize", "hint_bin": "trivial", "needs_tools": False},
    {"prompt": "Reply with only pass.", "phase": "edit", "hint_bin": "trivial", "needs_tools": False},
    {"prompt": "Reply with the single word router.", "phase": "discover", "hint_bin": "trivial", "needs_tools": False},
    # JSON (standard)
    {"prompt": "Reply with JSON only: {\"status\": \"ok\"}.", "phase": "edit", "hint_bin": "standard", "needs_tools": False},
    {"prompt": "Return valid JSON with keys model and path only.", "phase": "edit", "hint_bin": "standard", "needs_tools": False},
    {"prompt": "Reply with JSON only: {\"count\": 0}.", "phase": "tool", "hint_bin": "standard", "needs_tools": False},
    {"prompt": "Return a JSON object with key threshold and numeric value 0.1.", "phase": "plan", "hint_bin": "standard", "needs_tools": False},
    {"prompt": "Reply with valid json: {\"enabled\": true}.", "phase": "edit", "hint_bin": "standard", "needs_tools": False},
    # expected substring
    {"prompt": "What is 2+2? Reply with only the digit 4.", "phase": "edit", "hint_bin": "trivial", "needs_tools": False, "expected": "4"},
    {"prompt": "Name the HTTP method for creating a resource. Reply must contain POST.", "phase": "discover", "hint_bin": "trivial", "needs_tools": False, "expected": "POST"},
    {"prompt": "Which env gates train CLI? Answer must contain AIAND_TRAIN.", "phase": "discover", "hint_bin": "standard", "needs_tools": False, "expected": "AIAND_TRAIN"},
    {"prompt": "Default TRAINED_PATH for smoke? Include the word shadow.", "phase": "debug", "hint_bin": "standard", "needs_tools": False, "expected": "shadow"},
    {"prompt": "Paths allowed on hops rows? Must contain trained.", "phase": "discover", "hint_bin": "standard", "needs_tools": False, "expected": "trained"},
    {"prompt": "Savings baseline id when eligible? Include K3.", "phase": "plan", "hint_bin": "hard", "needs_tools": False, "expected": "K3"},
    {"prompt": "Platt params live under which key in scorer.json? Include platt.", "phase": "discover", "hint_bin": "standard", "needs_tools": False, "expected": "platt"},
    {"prompt": "Cheapest-above-bar fallback rule name? Include fallback_declined.", "phase": "debug", "hint_bin": "hard", "needs_tools": False, "expected": "fallback_declined"},
    # typo proxy (verified via prompt pattern)
    {"prompt": "Fix the typo 'recieve' to 'receive' in one word.", "phase": "edit", "hint_bin": "trivial", "needs_tools": False, "expected": "receive"},
    {"prompt": "Correct spelling: change 'occured' to 'occurred'. One word only.", "phase": "edit", "hint_bin": "trivial", "needs_tools": False, "expected": "occurred"},
    {"prompt": "Fix the typo 'seperate' to 'separate'. Reply with the correct word only.", "phase": "edit", "hint_bin": "trivial", "needs_tools": False, "expected": "separate"},
    # yaml
    {"prompt": "Write a YAML snippet for trained_effort medium: threshold 0.10, max_regret 0.20.", "phase": "edit", "hint_bin": "standard", "needs_tools": False},
    {"prompt": "Write a yaml snippet with key path set to shadow.", "phase": "plan", "hint_bin": "standard", "needs_tools": False, "expected": "shadow"},
    # flashlight-style pytest seeds
    {
        "prompt": "Files:\nparity.py:\ndef is_even(n: int) -> bool:\n    return n % 2 == 1\n\nWrite the corrected Python module only, inside a ```python fence.",
        "phase": "edit",
        "hint_bin": "standard",
        "needs_tools": False,
        "verify_pytest": True,
        "module": "parity.py",
        "tests": PARITY_TESTS,
    },
    {
        "prompt": "Files:\nclamp.py:\ndef clamp(n: int, lo: int, hi: int) -> int:\n    if n < lo:\n        return hi\n    if n > hi:\n        return lo\n    return n\n\nWrite the corrected Python module only, inside a ```python fence.",
        "phase": "edit",
        "hint_bin": "hard",
        "needs_tools": False,
        "verify_pytest": True,
        "module": "clamp.py",
        "tests": CLAMP_TESTS,
    },
    {
        "prompt": "Files:\nreverse.py:\ndef reverse(s: str) -> str:\n    return s\n\nWrite the corrected Python module only, inside a ```python fence.",
        "phase": "edit",
        "hint_bin": "standard",
        "needs_tools": False,
        "verify_pytest": True,
        "module": "reverse.py",
        "tests": REVERSE_TESTS,
    },
]

# pad to ~100 with numbered variants (still checkable)
for i in range(60):
    kind = i % 5
    if kind == 0:
        word = ("alpha", "beta", "gamma", "delta", "echo", "foxtrot")[i % 6]
        ROWS.append(
            {
                "prompt": f"Reply with the single word {word}. Query vq-{i:03d}.",
                "phase": "edit",
                "hint_bin": "trivial",
                "needs_tools": False,
            }
        )
    elif kind == 1:
        ROWS.append(
            {
                "prompt": f"Reply with JSON only: {{\"id\": {i}}}. Query vq-{i:03d}.",
                "phase": "edit",
                "hint_bin": "standard",
                "needs_tools": False,
            }
        )
    elif kind == 2:
        ROWS.append(
            {
                "prompt": f"What is {i}+{i}? Reply with only the number {i+i}. Query vq-{i:03d}.",
                "phase": "edit",
                "hint_bin": "trivial",
                "needs_tools": False,
                "expected": str(i + i),
            }
        )
    elif kind == 3:
        ROWS.append(
            {
                "prompt": f"Name the router path for shadow mode. Must contain shadow. Query vq-{i:03d}.",
                "phase": "discover",
                "hint_bin": "standard",
                "needs_tools": i % 2 == 0,
                "expected": "shadow",
            }
        )
    else:
        ROWS.append(
            {
                "prompt": f"Write a yaml snippet: effort{i}: threshold: 0.{i % 10}. Query vq-{i:03d}.",
                "phase": "plan",
                "hint_bin": "standard",
                "needs_tools": False,
            }
        )


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ROWS), encoding="utf-8")
    print(f"wrote {len(ROWS)} -> {OUT}")


if __name__ == "__main__":
    main()
