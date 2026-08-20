"""Phase-2 minimise: shrink holdout prompts while keeping gate fail."""
from __future__ import annotations

import json
import os
import tempfile
from collections import OrderedDict
from pathlib import Path

from aiand_router.replay_report import replay_report
from aiand_router.router import load_config, load_models
from aiand_router.scorer import load_scorer


def main() -> None:
    gold_path = Path("data/gold-verified.jsonl")
    rows = [json.loads(l) for l in gold_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    by_prompt: OrderedDict[str, list] = OrderedDict()
    for r in rows:
        by_prompt.setdefault(r["prompt"], []).append(r)
    prompts = list(by_prompt.keys())
    print(f"total_prompts={len(prompts)} total_cells={len(rows)}")

    cfg = load_config(Path("config/models.yaml"))
    models = load_models(cfg)
    artifact = load_scorer(Path("data/scorer.json"))
    assert artifact is not None

    for n in [89, 40, 20, 10, 5, 3]:
        keep = set(prompts[:n])
        subset = [r for r in rows if r["prompt"] in keep]
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            for r in subset:
                f.write(json.dumps(r) + "\n")
            tmp = f.name
        try:
            rep = replay_report(tmp, artifact, models, cfg)
            print(
                f"n={n} gate={rep['replay_gate_pass']} "
                f"auc={rep['rank_auc']:.3f} brier_skill={rep['brier_skill']:.3f} "
                f"ece_w={rep['ece_equal_width']:.3f} cost_d={rep['rules_cost_delta']} "
                f"disagree={rep['disagreement_rate']:.3f} "
                f"p_spread={rep['mean_p_spread']:.3f}"
            )
        finally:
            os.unlink(tmp)


if __name__ == "__main__":
    main()
