"""Compute reliability metrics for the fitted scorer against gold_dense.jsonl.

Output: data/reliability.json with BSS, dual ECE, MCE, and reliability table.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from aiand_router.metrics import (
    brier_skill_score,
    ece_equal_width,
    ece_equal_mass,
    mce,
    reliability_table,
)
from aiand_router.scorer import load_scorer, score_eligible

SCORER_PATH = ROOT / "data" / "scorer.json"
GOLD_PATH = ROOT / "data" / "gold_dense.jsonl"
OUT_PATH = ROOT / "data" / "reliability.json"


def main() -> None:
    artifact = load_scorer(SCORER_PATH)
    if artifact is None:
        print("FAIL: could not load scorer.json", file=sys.stderr)
        sys.exit(1)

    rows = []
    for line in GOLD_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))

    # Filter to observed rows only (have success gold)
    observed = [r for r in rows if not r.get("unobserved", True)]
    print(f"gold_dense.jsonl: {len(rows)} total, {len(observed)} observed")

    pairs: list[tuple[float, float]] = []
    skipped = 0
    for i, r in enumerate(observed):
        model_id = r["model_id"]
        phase = r.get("phase", "plan")
        needs_tools = bool(r.get("needs_tools", False))
        tokens = int(r.get("tokens", 1))
        hint_bin = r.get("hint_bin", "standard")
        text = r.get("prompt", "")
        success = int(r.get("success", 0))

        bin_, p_success = score_eligible(
            artifact,
            [model_id],
            phase=phase,
            needs_tools=needs_tools,
            tokens=tokens,
            hint_bin=hint_bin,
            text=text,
        )
        if model_id not in p_success:
            skipped += 1
            continue
        pairs.append((p_success[model_id], float(success)))

    print(f"scored {len(pairs)} rows, skipped {skipped} (model not in artifact)")

    if not pairs:
        print("FAIL: no scored pairs", file=sys.stderr)
        sys.exit(1)

    bss = brier_skill_score(pairs)
    ece_w = ece_equal_width(pairs, M=10)
    ece_m = ece_equal_mass(pairs, M=10)
    mce_val = mce(pairs, M=10)
    table = reliability_table(pairs, M=10)

    result = {
        "bss": bss,
        "ece_equal_width": ece_w,
        "ece_equal_mass": ece_m,
        "mce": mce_val,
        "reliability_table": table,
        "n_rows": len(pairs),
    }

    OUT_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"\nReliability metrics ({len(pairs)} rows):")
    print(f"  BSS:              {bss:.6f}")
    print(f"  ECE equal-width:  {ece_w:.6f}")
    print(f"  ECE equal-mass:   {ece_m:.6f}")
    print(f"  MCE:              {mce_val:.6f}")
    print(f"  -> {OUT_PATH}")


if __name__ == "__main__":
    main()