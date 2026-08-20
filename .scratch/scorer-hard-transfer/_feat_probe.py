"""Unpaid: text-feature vs y correlation on train Kimi + verified Kimi."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def cells(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def feats(p: str) -> dict[str, float]:
    pl = p.lower()
    return {
        "json": float("json" in pl or '{"' in p),
        "reply_word": float("reply with the single word" in pl or "reply with only" in pl),
        "math": float(bool(re.search(r"\d+\s*\+\s*\d+", p))),
        "code": float("def " in p or "Files:" in p or ".py" in p),
        "vq": float("Query vq-" in p),
        "bool_lit": float(bool(re.search(r"\b(true|false)\b", pl))),
        "log_chars": math.log1p(len(p)),
        "has_colon": float(":" in p),
        "word_n": float(len(p.split())),
        "fix_bug": float("fix the bug" in pl or "broken" in pl),
        "pytest": float("pytest" in pl or "assert " in pl),
        "tools_mark": float("tool" in pl and "call" in pl),
    }


def kimi_rows(path: Path) -> list[dict]:
    rows = []
    for r in cells(path):
        mid = str(r.get("model_id") or "")
        if "kimi" not in mid or r.get("unobserved"):
            continue
        if "success" not in r:
            continue
        f = feats(str(r.get("prompt") or ""))
        f["y"] = 1.0 if r.get("success") else 0.0
        f["tokens"] = float(r.get("tokens") or 0)
        rows.append(f)
    return rows


def summarize(name: str, rows: list[dict]) -> None:
    if not rows:
        print(name, "empty")
        return
    ybar = sum(r["y"] for r in rows) / len(rows)
    print(f"\n{name} n={len(rows)} ybar={ybar:.3f}")
    keys = [k for k in rows[0] if k not in {"y"}]
    for k in keys:
        pos = [r for r in rows if r[k] >= 0.5] if max(r[k] for r in rows) <= 1.0 and min(r[k] for r in rows) >= 0.0 and k not in {"log_chars", "word_n", "tokens"} else None
        if pos is not None:
            neg = [r for r in rows if r[k] < 0.5]
            if pos and neg:
                print(
                    f"  {k}: y|1={sum(r['y'] for r in pos)/len(pos):.3f} n={len(pos)} "
                    f"y|0={sum(r['y'] for r in neg)/len(neg):.3f} n={len(neg)}"
                )
        # spearman-ish via rank of continuous
        xs = [r[k] for r in rows]
        ys = [r["y"] for r in rows]
        if len(set(xs)) < 2:
            continue
        rx = {v: i for i, v in enumerate(sorted(xs))}
        # average ranks for ties skip; rough
        from statistics import mean

        def ranks(vals):
            order = sorted(range(len(vals)), key=lambda i: vals[i])
            r = [0.0] * len(vals)
            i = 0
            while i < len(vals):
                j = i
                while j + 1 < len(vals) and vals[order[j + 1]] == vals[order[i]]:
                    j += 1
                avg = (i + j) / 2 + 1
                for t in range(i, j + 1):
                    r[order[t]] = avg
                i = j + 1
            return r

        rxv, ryv = ranks(xs), ranks(ys)
        mx, my = mean(rxv), mean(ryv)
        num = sum((a - mx) * (b - my) for a, b in zip(rxv, ryv))
        den = (sum((a - mx) ** 2 for a in rxv) * sum((b - my) ** 2 for b in ryv)) ** 0.5
        if den:
            print(f"  spearman({k},y)={num/den:.3f}")


for label, path in [
    ("mix1", ROOT / "data" / "gold-sparse-hard-mix1.jsonl"),
    ("cal", ROOT / "data" / "gold-dense-hard-cal-merged.jsonl"),
    ("verified", ROOT / "data" / "gold-verified.jsonl"),
]:
    summarize(label, kimi_rows(path))

# mix1 prompt samples
print("\nmix1 prompt samples:")
seen = set()
for r in cells(ROOT / "data" / "gold-sparse-hard-mix1.jsonl"):
    p = r.get("prompt") or ""
    if p in seen:
        continue
    seen.add(p)
    if len(seen) <= 8:
        print(repr(p[:140]))
