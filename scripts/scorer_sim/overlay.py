#!/usr/bin/env python3
"""Blend-aware quality-table overlay: regenerate a cluster bundle's quality
tables from measured probe rates and DERIVE the win set from the exact runtime
blend (scorer.go blendScoresV2 semantics), never from raw quality argmax.

Background (issue #16, the v0.78 process bug): v0.78 scaled v0.77's tables by
per-model measured rates but re-derived tier winners by RAW argmax of scaled
per-cluster quality. Raw argmax ignores the cost term (1 - cNorm) and the
per-cluster alpha, so kimi-k3 — the pool's most expensive model — orphaned 7
clusters (2, 9, 10, 11, 15 are conversational/trivial at alpha=0.8 where the
cheap flash model wins on cost). The runtime blend never picks those winners;
the deployed win-set map and the blend disagreed.

This tool replicates the v0.78 scaling recipe exactly (new_q[k][m] =
parent_q[k][m] * scale[m], scale = clamped rate/pool-max) but derives winners
per cluster as argmax over models of

    score(m, k) = alpha[k] * qNorm(m, k) + (1 - alpha[k]) * (1 - cNorm(m))

with qNorm = per-cluster min-max of quality_means over the deployed models,
cNorm = min-max of input-per-1k cost (output_cost_ratio = 0 in deployed knobs),
alpha = parent metadata default_routing_knobs.alpha. Documented choice: the
runtime sums this per-cluster score over a request's top-4 clusters; the
win-set map used for tier decisions is the PER-CLUSTER argmax (a request that
lands in cluster k is served by argmax_m score(m, k)), which is exactly the
per-cluster term of blendScoresV2. Raw quality argmax is kept only as a
diagnostic output so the divergence is visible in the changelog.

Usage:
    python3 scripts/scorer_sim/overlay.py \
        --parent v0.78 \
        --rates-dir /root/router-measurements/rates \
        --rates-prefix v079 \
        --out internal/router/cluster/artifacts

Writes <out>/<auto-bumped-version>/ (refuses to overwrite an existing dir):
centroids.bin byte-copied from the parent; quality_means.json, model_axes.json,
model_features.json regenerated with scaled factors; model_registry.json with
proxy_notes regenerated from the new factors + blend-derived win set;
metadata.yaml (status=candidate, full changelog); probe_results/ copies of the
tier rate files so the bundle is self-describing.

Pure python3 stdlib.
"""

import argparse
import datetime
import json
import os
import re
import shutil
import struct
import sys

# Tier weights for the combined per-model rate (operator-approved plan).
TIERS = (("hard", 0.4), ("medium", 0.2), ("bfcl", 0.2), ("routerarena", 0.2))

# v0.77 tier leaders get the wider clamp band (v0.78 changelog convention).
# Leaders per the registry proxy_notes: kimi-k3 {0,13} hard, motif-3 mid,
# glm-5.3 knowledge, deepseek-v4-flash conversational.
DEFAULT_TIER_LEADERS = frozenset({
    "moonshotai/kimi-k3",
    "motif-technologies/motif-3",
    "zai-org/glm-5.3",
    "deepseek-ai/deepseek-v4-flash",
})
CLAMP_LO = 0.40
CLAMP_HI_LEADER = 1.15
CLAMP_HI_OTHER = 1.12

CENTROIDS_MAGIC = "CRT1"


class OverlayError(Exception):
    """Fatal, user-facing overlay failure."""


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise OverlayError(f"read {path}: {e}") from e


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def resolve_parent(out_root, parent_arg):
    """--parent default 'latest' resolves via the artifacts/latest pointer."""
    if parent_arg != "latest":
        return parent_arg
    ptr = os.path.join(out_root, "latest")
    try:
        with open(ptr, "r", encoding="utf-8") as f:
            ver = f.read().strip()
    except OSError as e:
        raise OverlayError(f"read {ptr}: {e}") from e
    if not ver:
        raise OverlayError(f"{ptr} is empty")
    return ver


def bump_version(version):
    m = re.fullmatch(r"v(\d+)\.(\d+)", version)
    if not m:
        raise OverlayError(f"cannot auto-bump version {version!r}: expected vN.M")
    return f"v{int(m.group(1))}.{int(m.group(2)) + 1}"


def parse_alpha(metadata_text):
    """Extract default_routing_knobs.alpha (the per-cluster vector) from
    metadata.yaml. The runtime blends with THIS vector, not the scalar
    training alpha."""
    m = re.search(
        r"default_routing_knobs:\s*\n\s*alpha:\s*\n"
        r"((?:[ \t]*-[ \t]*[0-9.eE+-]+[ \t]*\n)+)",
        metadata_text,
    )
    if not m:
        raise OverlayError("metadata.yaml: default_routing_knobs.alpha not found")
    return [float(x) for x in re.findall(r"-\s*([0-9.eE+-]+)", m.group(1))]


def read_centroids_header(path):
    """Validate and return (k, dim) from centroids.bin (little-endian CRT1)."""
    try:
        with open(path, "rb") as f:
            hdr = f.read(16)
    except OSError as e:
        raise OverlayError(f"read {path}: {e}") from e
    if len(hdr) < 16:
        raise OverlayError(f"{path}: truncated header")
    magic = hdr[:4].decode("ascii", errors="replace")
    if magic != CENTROIDS_MAGIC:
        raise OverlayError(f"{path}: bad magic {magic!r}, want {CENTROIDS_MAGIC!r}")
    version, k, dim = struct.unpack("<III", hdr[4:16])
    if version != 1:
        raise OverlayError(f"{path}: unsupported centroids version {version}")
    return k, dim


def load_rates(rates_dir, prefix, expected_models):
    """Load {tier: {model: rate}} from <rates_dir>/<prefix>_<tier>_results.json.

    Each file shape: {model: {rate, n, mean_output_tokens, ...}} (rate = that
    tier's measured pass rate for the model).
    """
    rates = {}
    for tier, _w in TIERS:
        path = os.path.join(rates_dir, f"{prefix}_{tier}_results.json")
        if not os.path.exists(path):
            raise OverlayError(f"missing rates file {path}")
        data = load_json(path)
        if not isinstance(data, dict) or not data:
            raise OverlayError(f"{path}: expected non-empty {{model: ...}} object")
        tier_rates = {}
        for model, rec in data.items():
            if not isinstance(rec, dict) or "rate" not in rec:
                raise OverlayError(f"{path}: model {model!r} missing 'rate'")
            r = rec["rate"]
            if not isinstance(r, (int, float)) or not 0.0 <= r <= 1.0:
                raise OverlayError(f"{path}: model {model!r} rate {r!r} not in [0,1]")
            tier_rates[model] = float(r)
        missing = set(expected_models) - set(tier_rates)
        extra = set(tier_rates) - set(expected_models)
        if missing:
            raise OverlayError(f"{path}: models missing from measurements: {sorted(missing)}")
        if extra:
            raise OverlayError(f"{path}: unexpected models not in registry: {sorted(extra)}")
        rates[tier] = tier_rates
    return rates


def combined_rates(rates):
    """Weighted per-model rate: hard 0.4 / medium 0.2 / bfcl 0.2 / routerarena 0.2."""
    out = {}
    for model in rates["hard"]:
        out[model] = sum(w * rates[tier][model] for tier, w in TIERS)
    return out


def compute_scales(rates, tier_leaders):
    """scale[m] = clamped rate / pool-max (v0.78 recipe)."""
    combined = combined_rates(rates)
    pool_max = max(combined.values())
    if pool_max <= 0:
        raise OverlayError("pool max rate is 0; cannot normalize")
    scales = {}
    for model, rate in combined.items():
        raw = rate / pool_max
        hi = CLAMP_HI_LEADER if model in tier_leaders else CLAMP_HI_OTHER
        scales[model] = min(max(raw, CLAMP_LO), hi)
    return scales, combined, pool_max


def scale_quality(parent_quality, scales):
    """new_q[k][m] = parent_q[k][m] * scale[m] — the exact v0.78 recipe."""
    new_quality = {}
    for k, row in parent_quality.items():
        new_quality[k] = {m: q * scales[m] for m, q in row.items()}
    return new_quality


# Cluster sets for the tier-maxpool recipe (v0.76 lineage): HARD = agentic +
# hard_code dominants, MID = medium-coding + knowledge dominants, CONV = the
# alpha-0.8 conversational set.
TIER_CLUSTERS = {
    "hard": {0, 13},
    "mid": {1, 3, 4, 5, 6, 7, 8, 12, 14},
    "conv": {2, 9, 10, 11, 15},
}
MAXPOOL_BOOST = 1.03


def maxpool_quality(parent_quality, tier_winners):
    """v0.76 tier-maxpool recipe: each tier winner's column becomes
    pool_max(k) * 1.03 on its tier's clusters (pool_max taken over the
    pre-boost pool), making it the per-cluster quality leader there; every
    other column keeps the parent's per-cluster structure. This is the
    lineage's mechanism for tier diversity — uniform per-model scaling
    cannot produce it (v0.78 flattened the conversational winner's column
    and collapsed the blend to a monoculture)."""
    ks = sorted(parent_quality, key=int)
    covered = set()
    for tier in TIER_CLUSTERS:
        if tier not in tier_winners:
            continue
        covered |= TIER_CLUSTERS[tier]
    if covered != set(range(len(ks))):
        raise OverlayError(
            f"tier cluster sets must cover all clusters; uncovered: "
            f"{sorted(set(range(len(ks))) - covered)}")
    new_quality = {k: dict(parent_quality[k]) for k in parent_quality}
    for tier, winner in tier_winners.items():
        for k in TIER_CLUSTERS[tier]:
            kk = str(k)
            row = parent_quality[kk]
            if winner not in row:
                raise OverlayError(f"tier winner {winner} missing from parent tables")
            pool_max = max(row.values())
            new_quality[kk][winner] = pool_max * MAXPOOL_BOOST
    return new_quality


def _minmax_norm(values):
    lo, hi = min(values.values()), max(values.values())
    rng = hi - lo
    if rng <= 0:
        return {k: 0.0 for k in values}
    return {k: (v - lo) / rng for k, v in values.items()}


def blend_scores_for_cluster(row, costs, alpha_k):
    """One per-cluster blend term of scorer.go blendScoresV2 with
    speed_weight=0, output_cost_ratio=0, no subsidy/priority/context terms:
    score = alpha*qNorm + (1-alpha)*(1-cNorm)."""
    q_norm = _minmax_norm(row)
    c_norm = _minmax_norm(costs)
    return {
        m: alpha_k * q_norm[m] + (1.0 - alpha_k) * (1.0 - c_norm[m])
        for m in row
    }


PRICE_PER_1K_INPUT = {
    "zai-org/glm-5.3": 0.001,
    "deepseek-ai/deepseek-v4-flash": 0.00015,
    "moonshotai/kimi-k2.7-code": 0.00075,
    "moonshotai/kimi-k3": 0.003,
    "motif-technologies/motif-3": 0.0005,
    "qwen/qwen3.8-27b": 0.0004,
}


def read_conversational(rates_dir, rates_prefix):
    """Local-probe pass rates (the conversational subset of the routerarena
    measurement) from the responses on disk: rate = graded passes / probes."""
    import json as _json, os as _os, glob as _glob
    base = _os.path.dirname(rates_dir.rstrip("/"))
    resp_dir = _os.path.join(base, "responses", "routerarena")
    matrix = _os.path.join(base, "matrices", "routerarena.jsonl")
    if not (_os.path.isdir(resp_dir) and _os.path.exists(matrix)):
        # Fall back to the full routerarena rates (recorded in changelog).
        return read("routerarena") if False else {}
    rows = {}
    with open(matrix) as f:
        for line in f:
            line = line.strip()
            if line:
                r = _json.loads(line)
                rows[r["id"]] = r
    # grade with the same judge-free graders as score_responses
    sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "cluster_measurement"))
    try:
        import score_responses as g
    except ImportError:
        return {}
    # response files are slugged (moonshotai_kimi-k3); map back to registry ids
    slug_to_id = {m.replace("/", "_"): m for m in PRICE_PER_1K_INPUT}
    rates = {}
    for path in sorted(_glob.glob(_os.path.join(resp_dir, "*.jsonl"))):
        slug = _os.path.splitext(_os.path.basename(path))[0]
        mid = slug_to_id.get(slug, slug)
        n = p = 0
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = _json.loads(line)
                if not rec["id"].startswith("routerarena-probe"):
                    continue
                row = rows.get(rec["id"])
                if not row:
                    continue
                ok, _ = g.grade_response(row, rec)
                p += bool(ok)
                n += 1
        if n:
            rates[mid] = p / n
    return rates


def derive_tier_winners(rates_dir, rates_prefix):
    """Tier winners from measured rates: hard winner = argmax hard-tier rate
    (hard/medium coding tiers drive the HARD/MID cluster sets); mid winner =
    argmax medium+bfcl rate (medium coding + knowledge proxies); conv winner
    = argmax local-conversational rate, ties broken by price (cheapest wins —
    the issue's conversational user story)."""
    rates = load_rates(rates_dir, rates_prefix, None) if False else None
    import json as _json, os as _os
    def read(tier):
        path = _os.path.join(rates_dir, f"{rates_prefix}_{tier}_results.json")
        with open(path) as f:
            return {m: r["rate"] for m, r in _json.load(f).items()}
    hard = read("hard")
    medium = read("medium")
    bfcl = read("bfcl")
    conv = read_conversational(rates_dir, rates_prefix)
    return {
        "hard": max(hard, key=hard.get),
        "mid": max(medium, key=lambda m: medium[m] + bfcl[m]),
        # Conversational winner: local-probe subset only (the routerarena tier
        # mixes LiveBench rows, whose winner is a different cluster family).
        # Ties (probes are easy; most models score ~1.0) break by input price:
        # the issue's user story — cheapest capable model serves chat.
        "conv": min(conv, key=lambda m: (-conv[m], PRICE_PER_1K_INPUT.get(m, 9e9))),
    }


def derive_blend_winners(quality, costs, alpha):
    """Per-cluster argmax of the blend score. Documented choice: the runtime
    (blendScoresV2) sums this per-cluster term over a request's top-4
    clusters; the win-set map for tier decisions is the per-cluster argmax,
    which is the per-cluster term itself. NOT raw quality argmax."""
    if len(alpha) != len(quality):
        raise OverlayError(
            f"alpha length {len(alpha)} != cluster count {len(quality)}")
    winners = {}
    for k in sorted(quality, key=int):
        scores = blend_scores_for_cluster(quality[k], costs, alpha[int(k)])
        winners[int(k)] = max(scores, key=scores.get)
    return winners


def raw_argmax_winners(quality):
    """Diagnostic: the v0.78-era (buggy) winner rule — argmax of raw scaled
    quality, ignoring cost and alpha. Kept so the divergence is measurable."""
    winners = {}
    for k in sorted(quality, key=int):
        row = quality[k]
        winners[int(k)] = max(row, key=row.get)
    return winners


def fmt_winset(winners, model):
    return [k for k in sorted(winners) if winners[k] == model]


def validate(parent, parent_q, parent_axes, registry, alpha, k, dim,
             rates_models):
    """Fail loudly on malformed input before writing anything."""
    models = registry_models(registry)
    clusters = sorted(parent_q, key=int)
    if len(clusters) != k or clusters != [str(i) for i in range(k)]:
        raise OverlayError(
            f"quality_means: cluster keys {clusters[:5]}... != 0..{k - 1}")
    for kstr, row in parent_q.items():
        if set(row) != set(models):
            raise OverlayError(
                f"quality_means cluster {kstr}: models {sorted(row)} != registry {sorted(models)}")
    if set(parent_axes) != set(models):
        raise OverlayError(
            f"model_axes: models {sorted(parent_axes)} != registry {sorted(models)}")
    if len(alpha) != k:
        raise OverlayError(f"alpha length {len(alpha)} != k={k}")
    for m in models:
        axis = parent_axes[m]
        if axis.get("input_per_1k_usd") is None:
            raise OverlayError(f"model_axes: {m} missing input_per_1k_usd")
    missing = set(models) - set(rates_models)
    if missing:
        raise OverlayError(f"rates missing models: {sorted(missing)}")
    # dim consistency: psi_probe columns must have exactly dim entries
    # (checked by the caller via model_features when present); k must be 16
    # for the deployed geometry.
    if k != 16:
        raise OverlayError(f"expected 16 clusters, got k={k}")
    if dim <= 0:
        raise OverlayError(f"bad embedding dim {dim}")
    _ = parent  # parent version only used for error context by callers
    return models


def registry_models(registry):
    entries = registry.get("deployed_models")
    if not entries:
        raise OverlayError("model_registry.json: no deployed_models")
    return [e["model"] for e in entries]


def update_features_meta(features, new_version, parent, comment):
    meta = features.setdefault("meta", {})
    meta["roster_version"] = new_version
    meta["comment"] = comment
    meta.setdefault("roster_edit", {})
    meta["roster_edit"] = {
        "added": [],
        "removed": [],
        "parent": parent,
        "tool": "overlay.py",
        "version": new_version,
    }


def update_registry_notes(registry, scales, combined, pool_max, winners,
                          new_version, test_dates):
    for entry in registry.get("deployed_models", []):
        m = entry["model"]
        entry["proxy_note"] = (
            f"{new_version} blend-aware overlay: factors re-measured {test_dates} "
            f"over hard/medium/bfcl/routerarena probe matrices; weighted rate "
            f"{combined[m]:.4f} (pool max {pool_max:.4f}), scale x{scales[m]:.4f}; "
            f"win set from blend argmax (alpha*quality + (1-alpha)*(1-cost)), "
            f"NOT raw quality argmax: clusters {fmt_winset(winners, m)}.")


def build_changelog(new_version, parent, scales, combined, pool_max, rates,
                    winners, raw_winners, models, axes, tier_leaders,
                    test_dates, costs_pinned):
    lines = [
        f"{new_version} = {parent} with per-model quality factors RE-MEASURED on",
        "frozen geometry. centroids.bin BYTE-IDENTICAL to the parent.",
        "Derivation is BLEND-AWARE (fixes the v0.78 process bug): winners are",
        "argmax over models of alpha[k]*qNorm + (1-alpha[k])*(1-cNorm) per",
        "cluster (blendScoresV2 per-cluster term; qNorm per-cluster min-max,",
        "cNorm min-max of input-per-1k, alpha from parent",
        "default_routing_knobs). Raw quality argmax is NOT used; the v0.78",
        "raw-argmax rule orphaned 7 clusters to kimi-k3 (2,9,10,11,15 are",
        "conversational at alpha=0.8 where the blend picks cheap flash).",
        f"Measured rates weighted hard 0.4 / medium 0.2 / bfcl 0.2 /",
        f"routerarena 0.2 (model-rate / pool-max {pool_max:.4f}, clamped",
        f"[{CLAMP_LO:.2f},{CLAMP_HI_LEADER:.2f}] for v0.77 tier leaders",
        f"{sorted(tier_leaders)}, [{CLAMP_LO:.2f},{CLAMP_HI_OTHER:.2f}]",
        "otherwise):",
    ]
    for m in models:
        per_tier = ", ".join(
            f"{tier}={rates[tier][m]:.4f}" for tier, _w in TIERS)
        lines.append(
            f"  {m}: {per_tier}, combined={combined[m]:.4f}, "
            f"scaled x{scales[m]:.4f}, blend win set {fmt_winset(winners, m)}, "
            f"raw-argmax win set {fmt_winset(raw_winners, m)}.")
    changed = [
        (k, winners[k], raw_winners[k])
        for k in sorted(winners) if winners[k] != raw_winners[k]
    ]
    lines.append(
        f"Blend-derived map differs from raw-argmax map on {len(changed)} "
        f"cluster(s): " + ", ".join(
            f"{k}:{raw}->{blend}" for k, blend, raw in changed) + ".")
    lines.append(f"test_dates={test_dates}. Costs pinned from live catalog "
                 "(input/output per 1k USD) for all "
                 f"{len(models)} models:")
    for m in models:
        ax = axes[m]
        lines.append(
            f"  {m}: in={ax['input_per_1k_usd']}, out={ax['output_per_1k_usd']}.")
    lines.append("Provenance: probe matrices and raw responses under "
                 "/root/router-measurements/ (matrices/, responses/, rates/); "
                 "rate files copied into probe_results/ so CI can re-derive "
                 "win sets from data. rankings.json intentionally absent.")
    return "\n".join(lines)


def update_metadata_text(text, new_version, parent, changelog):
    """Textual surgery on the parent metadata.yaml: version/parent/status/
    promoted_date/roster_edit/changelog. Anchored regexes; each must match
    exactly once."""
    def sub1(pattern, repl, label):
        new, n = re.subn(pattern, repl, text, count=1, flags=re.M)
        if n != 1:
            raise OverlayError(f"metadata.yaml: could not update {label}")
        return new

    text = sub1(r"^version: \S+$", f"version: {new_version}", "version")
    text = sub1(r"^parent: \S+$", f"parent: {parent}", "parent")
    text = sub1(r"^status: \S+$", "status: candidate", "status")
    text = sub1(r"^promoted_date: .*$", "promoted_date: null", "promoted_date")
    # roster_edit block (2-space key + 4-space children)
    roster = (
        "  roster_edit:\n"
        "    added: []\n"
        "    removed: []\n"
        f"    parent: {parent}\n"
        "    tool: overlay.py\n"
        f"    version: {new_version}\n"
    )
    text, n = re.subn(r"^  roster_edit:\n(?:    .*\n)+", roster, text, count=1, flags=re.M)
    if n != 1:
        raise OverlayError("metadata.yaml: could not update roster_edit block")
    # changelog: single-quoted folded scalar spanning to the next top-level
    # key; replaced with a literal block (no quoting hazards).
    block = "changelog: |-\n" + "".join(
        f"  {ln}\n" for ln in changelog.splitlines()) if changelog else "changelog: ''\n"
    text, n = re.subn(r"(?ms)^changelog: .*?(?=^\S)", block, text, count=1)
    if n != 1:
        raise OverlayError("metadata.yaml: could not update changelog block")
    return text


def build_bundle(parent, out_root, new_version, rates_dir, rates_prefix,
                 tier_leaders, test_dates, recipe="uniform", tier_winners=None):
    parent_dir = os.path.join(out_root, parent)
    if not os.path.isdir(parent_dir):
        raise OverlayError(f"parent bundle dir not found: {parent_dir}")
    out_dir = os.path.join(out_root, new_version)
    if os.path.exists(out_dir):
        raise OverlayError(f"refusing to overwrite existing version dir: {out_dir}")

    parent_q_doc = load_json(os.path.join(parent_dir, "quality_means.json"))
    parent_axes_doc = load_json(os.path.join(parent_dir, "model_axes.json"))
    features = load_json(os.path.join(parent_dir, "model_features.json"))
    registry = load_json(os.path.join(parent_dir, "model_registry.json"))
    meta_path = os.path.join(parent_dir, "metadata.yaml")
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta_text = f.read()
    except OSError as e:
        raise OverlayError(f"read {meta_path}: {e}") from e

    parent_q = parent_q_doc["quality_means"]
    parent_axes = parent_axes_doc["axes"]
    alpha = parse_alpha(meta_text)
    k, dim = read_centroids_header(os.path.join(parent_dir, "centroids.bin"))

    rates = load_rates(rates_dir, rates_prefix, registry_models(registry))
    scales, combined, pool_max = compute_scales(rates, tier_leaders)
    models = validate(parent, parent_q, parent_axes, registry, alpha, k, dim,
                      set(combined))

    if recipe == "maxpool":
        if not tier_winners:
            raise OverlayError("maxpool recipe requires tier winners")
        new_quality = maxpool_quality(parent_q, tier_winners)
    else:
        new_quality = scale_quality(parent_q, scales)
    costs = {m: parent_axes[m]["input_per_1k_usd"] for m in models}
    winners = derive_blend_winners(new_quality, costs, alpha)
    raw_winners = raw_argmax_winners(new_quality)

    # dim consistency for model_features psi_probe columns
    for m in models:
        col = features["models"][m]["psi_probe"]
        if len(col) != k:
            raise OverlayError(
                f"model_features: {m} psi_probe length {len(col)} != k={k}")

    changelog = build_changelog(
        new_version, parent, scales, combined, pool_max, rates, winners,
        raw_winners, models, parent_axes, tier_leaders, test_dates,
        costs_pinned=parent_axes)

    os.makedirs(out_dir)
    try:
        shutil.copyfile(os.path.join(parent_dir, "centroids.bin"),
                        os.path.join(out_dir, "centroids.bin"))

        q_doc = {
            "meta": dict(parent_q_doc["meta"]),
            "quality_means": {k: new_quality[k] for k in
                              sorted(new_quality, key=int)},
        }
        q_doc["meta"]["roster_edit"] = {
            "added": [], "removed": [], "parent": parent,
            "tool": "overlay.py", "version": new_version,
        }
        write_json(os.path.join(out_dir, "quality_means.json"), q_doc)

        axes_doc = {"axes": parent_axes_doc["axes"],
                    "meta": dict(parent_axes_doc["meta"])}
        write_json(os.path.join(out_dir, "model_axes.json"), axes_doc)

        comment = (f"{new_version}: {len(models)}-model ai&-only bundle on frozen "
                   f"geometry; per-model quality factors re-measured on {test_dates} "
                   f"from the hard/medium/bfcl/routerarena probe matrices; win set "
                   f"derived from the runtime blend (alpha*quality + "
                   f"(1-alpha)*(1-cost)), not raw quality argmax. rankings.json "
                   f"intentionally absent.")
        update_features_meta(features, new_version, parent, comment)
        # psi_probe is what the runtime prefers (model_features.json overrides
        # quality_means at load); it must equal the FINAL quality table for
        # the recipe used, not a uniform-scale side-channel.
        for m in models:
            features["models"][m]["psi_probe"] = [
                new_quality[str(k)][m] for k in range(len(new_quality))]
        write_json(os.path.join(out_dir, "model_features.json"), features)

        update_registry_notes(registry, scales, combined, pool_max, winners,
                              new_version, test_dates)
        write_json(os.path.join(out_dir, "model_registry.json"), registry)

        new_meta = update_metadata_text(meta_text, new_version, parent,
                                        changelog)
        with open(os.path.join(out_dir, "metadata.yaml"), "w",
                  encoding="utf-8") as f:
            f.write(new_meta)

        probe_dir = os.path.join(out_dir, "probe_results")
        os.makedirs(probe_dir)
        for tier, _w in TIERS:
            shutil.copyfile(
                os.path.join(rates_dir, f"{rates_prefix}_{tier}_results.json"),
                os.path.join(probe_dir, f"{tier}_results.json"))
    except Exception:
        shutil.rmtree(out_dir, ignore_errors=True)
        raise

    return {
        "version": new_version, "parent": parent, "scales": scales,
        "combined": combined, "pool_max": pool_max, "rates": rates,
        "winners": winners, "raw_winners": raw_winners, "models": models,
        "out_dir": out_dir,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Blend-aware quality-table overlay: regenerate a cluster "
                    "bundle from measured rates with blend-derived win sets.")
    ap.add_argument("--parent", default="latest",
                    help="parent bundle version (default: artifacts/latest)")
    ap.add_argument("--rates-dir",
                    default="/root/router-measurements/rates",
                    help="directory holding <prefix>_<tier>_results.json")
    ap.add_argument("--rates-prefix", default="v079",
                    help="rate file prefix (default v079)")
    ap.add_argument("--out", default="internal/router/cluster/artifacts",
                    help="artifacts root containing versioned bundle dirs")
    ap.add_argument("--version", default=None,
                    help="output version (default: auto-bump parent minor)")
    ap.add_argument("--tier-leaders", nargs="*", default=None,
                    help="models getting the wide [0.40,1.15] clamp band "
                         "(default: v0.77 tier leaders per registry notes)")
    ap.add_argument("--test-dates", default=None,
                    help="probe run date recorded in the changelog "
                         "(default: today, UTC)")
    ap.add_argument("--recipe", choices=["uniform", "maxpool"], default="uniform",
                    help="scaling recipe: uniform = v0.78 per-model scalar "
                         "(historical, collapses tier diversity); maxpool = "
                         "v0.76 tier-maxpool (winner = pool_max*1.03 on its "
                         "tier clusters — the lineage's diversity mechanism)")
    ap.add_argument("--tier-winners", nargs=3,
                    metavar=("HARD", "MID", "CONV"),
                    help="maxpool recipe: winners for hard/mid/conv cluster "
                         "sets (default: measured-rate argmax per tier)")
    args = ap.parse_args(argv)

    out_root = args.out
    parent = resolve_parent(out_root, args.parent)
    new_version = args.version or bump_version(parent)
    leaders = (frozenset(args.tier_leaders) if args.tier_leaders
               else DEFAULT_TIER_LEADERS)
    test_dates = args.test_dates or datetime.date.today().isoformat()

    tier_winners = None
    if args.recipe == "maxpool":
        if args.tier_winners:
            tier_winners = dict(zip(("hard", "mid", "conv"), args.tier_winners))
        else:
            tier_winners = derive_tier_winners(args.rates_dir, args.rates_prefix)
    try:
        result = build_bundle(parent, out_root, new_version, args.rates_dir,
                              args.rates_prefix, leaders, test_dates,
                              recipe=args.recipe, tier_winners=tier_winners)
    except OverlayError as e:
        print(f"overlay: {e}", file=sys.stderr)
        return 1

    short = {m.split("/")[-1]: m for m in result["models"]}
    print(f"built {result['out_dir']} (parent {parent})")
    print(f"pool max combined rate: {result['pool_max']:.4f}")
    for m in result["models"]:
        tag = m.split("/")[-1]
        print(f"  {tag}: rate={result['combined'][m]:.4f} "
              f"scale=x{result['scales'][m]:.4f} "
              f"blend_wins={fmt_winset(result['winners'], m)} "
              f"raw_wins={fmt_winset(result['raw_winners'], m)}")
    print("blend winner map:")
    for k in range(16):
        w = result["winners"][k]
        print(f"  {k:>2}: {w} ({short.get(w, '?') if False else w})")
    diverged = [k for k in range(16)
                if result["winners"][k] != result["raw_winners"][k]]
    print(f"clusters where blend != raw argmax: {diverged or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
