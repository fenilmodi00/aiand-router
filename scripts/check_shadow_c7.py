"""C7 gate: shadow/trained hop count, field completeness, scorer_down, fallback rate."""
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "src"))

REQUESTS = root / "data" / "requests.jsonl"
MIN_HOPS = 100


def _load_rows() -> list[dict]:
    rows = []
    if not REQUESTS.exists():
        return rows
    for line in REQUESTS.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _is_trained_row(r: dict) -> bool:
    """Row exercised the fitted scorer (shadow or trained path, or has trained_would)."""
    path = r.get("path", "")
    return path in ("shadow", "trained") or "trained_would" in r


def main() -> None:
    rows = _load_rows()
    trained_rows = [r for r in rows if _is_trained_row(r)]
    n_trained = len(trained_rows)

    # --- Gate 1: hop count ---
    count_pass = n_trained >= MIN_HOPS

    # --- Gate 2: field completeness ---
    # fallback_declined rows: scorer declined (no pick), so confidence may be absent.
    # Only require confidence on rows where the scorer actually made a pick.
    missing_fields: list[dict] = []
    for i, r in enumerate(trained_rows):
        codes = r.get("reason_codes", [])
        if isinstance(codes, str):
            codes = [codes]
        is_declined = any("fallback_declined" in str(c) for c in codes)

        has_confidence = (
            "confidence" in r
            or "trained_confidence" in r
        )
        has_rules_delta = "rules_cost_delta_usd" in r
        has_cache_aware = "est_cache_aware" in r
        has_trained_pick = (
            "trained_selected" in r
            or "trained_would" in r
            or "selected" in r  # trained path: selected IS the trained pick
        )
        missing = []
        if not is_declined and not has_confidence:
            missing.append("confidence/trained_confidence")
        if not has_rules_delta:
            missing.append("rules_cost_delta_usd")
        if not has_cache_aware:
            missing.append("est_cache_aware")
        if not has_trained_pick:
            missing.append("trained_selected/trained_would/selected")
        if missing:
            missing_fields.append({"row": i, "missing": missing})

    fields_pass = len(missing_fields) == 0

    # --- Gate 3: zero scorer_down ---
    scorer_down_count = 0
    for r in trained_rows:
        codes = r.get("reason_codes", [])
        if isinstance(codes, str):
            codes = [codes]
        if any("scorer_down" in str(c) for c in codes):
            scorer_down_count += 1
    no_scorer_down_pass = scorer_down_count == 0

    # --- Gate 4: fallback_declined rate ---
    fallback_declined = 0
    for r in trained_rows:
        codes = r.get("reason_codes", [])
        if isinstance(codes, str):
            codes = [codes]
        if any("fallback_declined" in str(c) for c in codes):
            fallback_declined += 1
    fallback_rate = fallback_declined / n_trained if n_trained else 0.0

    # --- Phase distribution ---
    phase_dist: dict[str, int] = {}
    for r in trained_rows:
        p = r.get("phase", "unknown")
        phase_dist[p] = phase_dist.get(p, 0) + 1

    # --- Effort distribution ---
    effort_dist: dict[str, int] = {}
    for r in trained_rows:
        e = r.get("effort", "unknown")
        effort_dist[e] = effort_dist.get(e, 0) + 1

    # --- Model distribution ---
    model_dist: dict[str, int] = {}
    for r in trained_rows:
        m = r.get("selected", "unknown")
        model_dist[m] = model_dist.get(m, 0) + 1

    overall_pass = count_pass and fields_pass and no_scorer_down_pass

    report = {
        "gate": "C7",
        "total_rows": len(rows),
        "trained_rows": n_trained,
        "count_gate": {"threshold": MIN_HOPS, "actual": n_trained, "pass": count_pass},
        "fields_gate": {
            "pass": fields_pass,
            "missing_count": len(missing_fields),
            "missing_examples": missing_fields[:5],
        },
        "scorer_down_gate": {
            "pass": no_scorer_down_pass,
            "scorer_down_count": scorer_down_count,
        },
        "fallback_declined_rate": round(fallback_rate, 4),
        "fallback_declined_count": fallback_declined,
        "phase_distribution": phase_dist,
        "effort_distribution": effort_dist,
        "model_distribution": model_dist,
        "overall_pass": overall_pass,
    }
    print(json.dumps(report, indent=2))
    verdict = "PASS" if overall_pass else "FAIL"
    print(f"\nC7 {verdict}: {n_trained} trained hops, "
          f"{scorer_down_count} scorer_down, "
          f"fallback_declined={fallback_rate:.1%}")


if __name__ == "__main__":
    main()
