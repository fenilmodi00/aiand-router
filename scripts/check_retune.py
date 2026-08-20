#!/usr/bin/env python
"""QA for the retune CLI subcommand (threshold/max_regret grid search).

Assert-based, stdlib + PyYAML only. Run: python scripts/check_retune.py

Covers:
  (a) Normal case: trained path finds cheaper model with similar resolve rate
      -> emits valid YAML fragment, not do-not-promote.
  (b) Do-not-promote case: trained path can't match rules resolve rate
      -> prints do-not-promote.
  (c) YAML fragment is valid YAML with trained_effort / low/medium/high/max
      each having threshold + max_regret.
  (d) Monotonicity: t_low <= t_med <= t_high <= t_max,
      r_low >= r_med >= r_high >= r_max.
  (e) n < 300 refusal: run_retune raises ValueError.

Adversarial:
  (1) stale_state: two calls with identical inputs produce identical output.
  (2) empty scorer: missing scorer -> do-not-promote.
"""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import yaml

from aiand_router.train import run_retune

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} {detail}")


# Model IDs from config/models.yaml
FLASH = "deepseek-ai/deepseek-v4-flash"
PRO = "deepseek-ai/deepseek-v4-pro"
GLM = "zai-org/glm-5.2"

N_QUERIES = 100  # 100 queries x 3 models = 300 rows (meets n >= 300)


def make_tune_rows(
    n_queries: int, success_rates: dict[str, float]
) -> list[dict]:
    """Generate dense gold rows: n_queries x len(success_rates) models."""
    rows = []
    for i in range(n_queries):
        for model_id, rate in success_rates.items():
            success = i < int(n_queries * rate)
            rows.append(
                {
                    "prompt": f"query {i}",
                    "model_id": model_id,
                    "success": success,
                    "tokens": 500,
                    "needs_tools": False,
                    "phase": "plan",
                }
            )
    return rows


def write_jsonl(path: pathlib.Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )


def write_scorer(path: pathlib.Path, p_success: dict[str, float]) -> None:
    artifact = {
        "not_spec_floors": True,
        "complexity_bin": "standard",
        "p_success": p_success,
    }
    path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Test (a): Normal case -> YAML fragment
# ---------------------------------------------------------------------------
print("=== Test (a): Normal case -> YAML fragment ===")

# Scorer: Flash high P, Pro/GLM lower P -> trained picks Flash (cheaper)
scorer_a = {FLASH: 0.9, PRO: 0.5, GLM: 0.5}
# Dense gold: all models succeed on 80% of queries
rows_a = make_tune_rows(N_QUERIES, {FLASH: 0.8, PRO: 0.8, GLM: 0.8})

with tempfile.TemporaryDirectory() as td:
    tdp = pathlib.Path(td)
    dense_path = tdp / "tune.jsonl"
    scorer_path = tdp / "scorer.json"
    write_jsonl(dense_path, rows_a)
    write_scorer(scorer_path, scorer_a)

    output_a = run_retune(dense_path, scorer_path=scorer_path)

check("output is not do-not-promote", output_a != "do-not-promote", f"({output_a[:80]})")
check("output starts with trained_effort:", output_a.startswith("trained_effort:"))

# ---------------------------------------------------------------------------
# Test (b): Do-not-promote case
# ---------------------------------------------------------------------------
print("=== Test (b): Do-not-promote case ===")

# Scorer: only Flash in p_success (Pro/GLM not in scorer)
scorer_b = {FLASH: 0.9}
# Dense gold: Flash succeeds on 50%, Pro/GLM on 95%
rows_b = make_tune_rows(N_QUERIES, {FLASH: 0.5, PRO: 0.95, GLM: 0.95})

with tempfile.TemporaryDirectory() as td:
    tdp = pathlib.Path(td)
    dense_path = tdp / "tune.jsonl"
    scorer_path = tdp / "scorer.json"
    write_jsonl(dense_path, rows_b)
    write_scorer(scorer_path, scorer_b)

    output_b = run_retune(dense_path, scorer_path=scorer_path)

check("output is do-not-promote", output_b == "do-not-promote", f"({output_b[:80]})")

# ---------------------------------------------------------------------------
# Test (c): YAML fragment is valid YAML with correct structure
# ---------------------------------------------------------------------------
print("=== Test (c): YAML fragment structure ===")

parsed = yaml.safe_load(output_a)
check("parsed is a dict", isinstance(parsed, dict))
check("has trained_effort key", "trained_effort" in parsed)

te = parsed.get("trained_effort") if isinstance(parsed, dict) else {}
check("trained_effort is a dict", isinstance(te, dict))

for level in ("low", "medium", "high", "max"):
    check(
        f"has {level} key", isinstance(te, dict) and level in te,
    )
    row = te.get(level) if isinstance(te, dict) else None
    check(
        f"{level} is a dict", isinstance(row, dict),
    )
    if isinstance(row, dict):
        check(
            f"{level} has threshold",
            "threshold" in row and isinstance(row["threshold"], (int, float)),
        )
        check(
            f"{level} has max_regret",
            "max_regret" in row and isinstance(row["max_regret"], (int, float)),
        )
        check(
            f"{level} threshold in [0,1]",
            0.0 <= float(row["threshold"]) <= 1.0,
        )
        check(
            f"{level} max_regret in [0,1]",
            0.0 <= float(row["max_regret"]) <= 1.0,
        )

# ---------------------------------------------------------------------------
# Test (d): Monotonicity
# ---------------------------------------------------------------------------
print("=== Test (d): Monotonicity ===")

t_low = float(te["low"]["threshold"])
t_med = float(te["medium"]["threshold"])
t_high = float(te["high"]["threshold"])
t_max = float(te["max"]["threshold"])
r_low = float(te["low"]["max_regret"])
r_med = float(te["medium"]["max_regret"])
r_high = float(te["high"]["max_regret"])
r_max = float(te["max"]["max_regret"])

check("t_low <= t_med", t_low <= t_med + 1e-9, f"({t_low} vs {t_med})")
check("t_med <= t_high", t_med <= t_high + 1e-9, f"({t_med} vs {t_high})")
check("t_high <= t_max", t_high <= t_max + 1e-9, f"({t_high} vs {t_max})")
check("r_low >= r_med", r_low >= r_med - 1e-9, f"({r_low} vs {r_med})")
check("r_med >= r_high", r_med >= r_high - 1e-9, f"({r_med} vs {r_high})")
check("r_high >= r_max", r_high >= r_max - 1e-9, f"({r_high} vs {r_max})")

# ---------------------------------------------------------------------------
# Test (e): n < 300 refusal
# ---------------------------------------------------------------------------
print("=== Test (e): n < 300 refusal ===")

rows_e = make_tune_rows(99, {FLASH: 0.8, PRO: 0.8, GLM: 0.8})  # 99x3=297 < 300

with tempfile.TemporaryDirectory() as td:
    tdp = pathlib.Path(td)
    dense_path = tdp / "tune.jsonl"
    scorer_path = tdp / "scorer.json"
    write_jsonl(dense_path, rows_e)
    write_scorer(scorer_path, scorer_a)

    refused = False
    try:
        run_retune(dense_path, scorer_path=scorer_path)
    except ValueError:
        refused = True
    check("n < 300 raises ValueError", refused)

# ---------------------------------------------------------------------------
# Adversarial (1): stale_state — two calls produce identical output
# ---------------------------------------------------------------------------
print("=== Adversarial (1): stale_state ===")

with tempfile.TemporaryDirectory() as td:
    tdp = pathlib.Path(td)
    dense_path = tdp / "tune.jsonl"
    scorer_path = tdp / "scorer.json"
    write_jsonl(dense_path, rows_a)
    write_scorer(scorer_path, scorer_a)

    out1 = run_retune(dense_path, scorer_path=scorer_path)
    out2 = run_retune(dense_path, scorer_path=scorer_path)
    check("identical outputs across two calls", out1 == out2)

# ---------------------------------------------------------------------------
# Adversarial (2): empty scorer -> do-not-promote
# ---------------------------------------------------------------------------
print("=== Adversarial (2): empty scorer ===")

with tempfile.TemporaryDirectory() as td:
    tdp = pathlib.Path(td)
    dense_path = tdp / "tune.jsonl"
    scorer_path = tdp / "scorer.json"
    write_jsonl(dense_path, rows_a)
    # Write an empty file (not valid scorer JSON)
    scorer_path.write_text("", encoding="utf-8")

    out = run_retune(dense_path, scorer_path=scorer_path)
    check("empty scorer -> do-not-promote", out == "do-not-promote")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"\n=== Summary: {PASS} passed, {FAIL} failed ===")
sys.exit(1 if FAIL else 0)
