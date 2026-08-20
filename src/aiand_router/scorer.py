"""Features-only Scorer + cheapest-above-bar pick. Fixture JSON is enough for v1."""

from __future__ import annotations

import json
import math
import re
import zlib
from pathlib import Path
from typing import Any

from .router import (
    PHASE_FAMILY,
    Decision,
    Model,
    eligible_models,
    estimate_cost,
    fallback_decision,
    stamp_baseline,
)

SHIP_EFFORT = {
    "low": {"threshold": 0.05, "max_regret": 0.30},
    "medium": {"threshold": 0.10, "max_regret": 0.20},
    "high": {"threshold": 0.20, "max_regret": 0.15},
    "max": {"threshold": 0.60, "max_regret": 0.03},
}
FAMILIES = ("discover", "plan", "edit", "tool", "debug", "summarize")
BINS = ("trivial", "standard", "hard", "frontier")
DEFAULT_CASCADE_PHASES = (
    "plan",
    "planning",
    "edit",
    "code_generation",
    "code_edit",
    "refactoring",
    "tool",
    "tool_call",
    "debug",
    "debugging",
    "test_failure_analysis",
    "security_review",
)
_MATH_RE = re.compile(r"\d+\s*[+\-*/]\s*\d+")
_BOOL_LIT_RE = re.compile(r"\b(true|false)\b", re.I)


def parse_trained_path(raw: str | None) -> str:
    value = (raw or "shadow").strip().lower()
    return value if value in {"off", "shadow", "trained"} else "shadow"


def load_scorer(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if "p_success" not in data and "weights" not in data and "bilinear" not in data:
        return None
    return data


def _token_bins(tokens: int) -> list[float]:
    t = max(0, tokens)
    return [
        1.0 if t < 128 else 0.0,
        1.0 if 128 <= t < 512 else 0.0,
        1.0 if 512 <= t < 2048 else 0.0,
        1.0 if t >= 2048 else 0.0,
    ]


def text_features(text: str) -> list[float]:
    """Cheap binary prompt cues for within-model P(success). No embed / Rec B.

    Continuous char-length is omitted: Mix1 flashlights are long and dominate GD,
    which collapses short verified holdout ranking.
    """
    t = text or ""
    tl = t.lower()
    return [
        1.0 if ("```" in t or "def " in t or ".py" in tl or "Files:" in t) else 0.0,
        1.0 if ("json" in tl or '{"' in t) else 0.0,
        1.0 if "reply with" in tl else 0.0,
        1.0 if _MATH_RE.search(t) else 0.0,
        1.0 if _BOOL_LIT_RE.search(t) else 0.0,
    ]


_TOKEN_RE = re.compile(r"[a-z0-9_]+", re.I)


def hash_text_latent(text: str, dim: int, *, seed: int = 17) -> list[float]:
    """Signed hashing-trick bag of tokens + char trigrams. Features-only; not a neural embed.

    Used as optional bilinear query capacity / offline teacher for distill. Deterministic
    across processes (zlib.adler32), O(tokens) and safe for the <10ms hop.
    """
    if dim <= 0:
        return []
    out = [0.0] * dim
    t = text or ""
    tl = t.lower()
    toks = _TOKEN_RE.findall(tl)[:256]
    grams = [tl[i : i + 3] for i in range(min(max(0, len(tl) - 2), 200))]
    for kind, pieces in (("w", toks), ("c3", grams)):
        for piece in pieces:
            h = zlib.adler32(f"{seed}:{kind}:{piece}".encode("utf-8")) & 0xFFFFFFFF
            idx = h % dim
            sign = 1.0 if (h & 1) else -1.0
            out[idx] += sign
    # Unit-ish scale so GD does not drown regex features on long flashlights.
    norm = math.sqrt(sum(v * v for v in out)) or 1.0
    scale = 1.0 / norm
    return [v * scale for v in out]


def featurize_observable(phase: str, needs_tools: bool, tokens: int) -> list[float]:
    """Request-observable features only (no hint_bin). Used for live complexity prediction."""
    fam = PHASE_FAMILY.get(phase, "plan")
    return [
        1.0,
        1.0 if needs_tools else 0.0,
        math.log1p(max(0, tokens)),
        *_token_bins(tokens),
        *[1.0 if fam == f else 0.0 for f in FAMILIES],
    ]


def featurize_bilinear(
    phase: str,
    needs_tools: bool,
    tokens: int,
    hint_bin: str = "standard",
    text: str = "",
    *,
    hash_dim: int = 0,
    hash_seed: int = 17,
) -> list[float]:
    """Query trunk for bilinear head: observable + hint + phase family + text cues.

    Optional ``hash_dim`` appends a hashing-trick latent (live or teacher). Distilled
    serve artifacts keep ``hash_dim=0`` and bake teacher signal into ``query_proj``.
    """
    fam = PHASE_FAMILY.get(phase, "plan")
    hb = hint_bin if hint_bin in BINS else "standard"
    x = [
        1.0,
        1.0 if needs_tools else 0.0,
        math.log1p(max(0, tokens)),
        *_token_bins(tokens),
        *[1.0 if hb == b else 0.0 for b in BINS],
        *[1.0 if fam == f else 0.0 for f in FAMILIES],
        *text_features(text),
    ]
    if hash_dim > 0:
        x.extend(hash_text_latent(text, int(hash_dim), seed=int(hash_seed)))
    return x


def featurize(
    phase: str,
    needs_tools: bool,
    tokens: int,
    hint_bin: str = "standard",
    text: str = "",
) -> list[float]:
    """P(success) vector: tokens + bin + prompt cues. No phase one-hots.

    Phase families stay on the bin head only. Exclusive phase one-hots on an
    edit-only train set leave a residual that anti-correlates on multi-phase
    holdouts (discover/plan get a free boost when edit=0).
    """
    del phase  # phase is for callers / bin head; not a P(success) one-hot
    hb = hint_bin if hint_bin in BINS else "standard"
    return [
        1.0,
        1.0 if needs_tools else 0.0,
        math.log1p(max(0, tokens)),
        *_token_bins(tokens),
        *[1.0 if hb == b else 0.0 for b in BINS],
        *text_features(text),
    ]


def predict_complexity_bin(
    artifact: dict[str, Any],
    *,
    phase: str,
    needs_tools: bool,
    tokens: int,
) -> str:
    bin_w = artifact.get("bin_weights") or {}
    if not bin_w:
        bin_ = str(artifact.get("complexity_bin") or "standard")
        return bin_ if bin_ in BINS else "standard"
    x = featurize_observable(phase, needs_tools, tokens)
    return max(BINS, key=lambda b: _dot([float(v) for v in (bin_w.get(b) or [])], x))


def _sigmoid(z: float) -> float:
    z = max(-30.0, min(30.0, z))
    return 1.0 / (1.0 + math.exp(-z))


def _dot(w: list[float], x: list[float]) -> float:
    n = min(len(w), len(x))
    return sum(float(w[i]) * x[i] for i in range(n))


def _calibrator_ab(artifact: dict[str, Any]) -> tuple[float, float]:
    cal = artifact.get("calibrator") if isinstance(artifact.get("calibrator"), dict) else {}
    src = cal if ("a" in cal or "b" in cal) else (artifact.get("platt") or {})
    return float(src.get("a", 1.0)), float(src.get("b", 0.0))


def _isotonic_lookup(table: list[list[float]], z: float) -> float:
    if not table:
        return 0.5
    for boundary, p in table:
        if z <= boundary:
            return p
    return table[-1][1]


def _calibrate(artifact: dict[str, Any], z: float) -> float:
    cal = artifact.get("calibrator")
    if isinstance(cal, dict) and cal.get("mode") == "isotonic":
        return _isotonic_lookup(cal.get("table") or [], z)
    a, b = _calibrator_ab(artifact)
    return _sigmoid(a * z + b)


def _gbdt_z(head: dict[str, Any], x: list[float]) -> float:
    z = float(head.get("intercept") or 0.0)
    for t in head.get("trees") or []:
        j = int(t["feature"])
        if j >= len(x):
            continue
        z += float(t["left"] if x[j] <= float(t["threshold"]) else t["right"])
    return z


def _query_latent(query_proj: list[list[float]], x: list[float]) -> list[float]:
    return [
        sum(float(row[j]) * x[j] for j in range(min(len(x), len(row))))
        for row in query_proj
    ]


def _bilinear_z(
    query_proj: list[list[float]],
    factor: list[float],
    x: list[float],
    *,
    intercept: float = 0.0,
) -> float:
    q = _query_latent(query_proj, x)
    n = min(len(q), len(factor))
    return intercept + sum(q[i] * float(factor[i]) for i in range(n))


def score_eligible(
    artifact: dict[str, Any],
    eligible_ids: list[str],
    *,
    phase: str = "plan",
    needs_tools: bool = False,
    tokens: int = 1,
    hint_bin: str | None = None,
    text: str = "",
) -> tuple[str, dict[str, float]]:
    head_mode = str(artifact.get("head") or "")
    bilinear = artifact.get("bilinear")
    if head_mode == "bilinear" or (isinstance(bilinear, dict) and bilinear.get("query_proj")):
        bin_ = (
            hint_bin
            if hint_bin in BINS
            else predict_complexity_bin(
                artifact, phase=phase, needs_tools=needs_tools, tokens=tokens
            )
        )
        hash_dim = int(bilinear.get("hash_dim") or 0)
        hash_seed = int(bilinear.get("hash_seed") or 17)
        x = featurize_bilinear(
            phase,
            needs_tools,
            tokens,
            bin_,
            text=text,
            hash_dim=hash_dim,
            hash_seed=hash_seed,
        )
        query_proj = bilinear.get("query_proj") or []
        models = bilinear.get("models") or {}
        intercepts = artifact.get("intercepts") or {}
        table = artifact.get("p_success") or {}
        p_success = {}
        for i in eligible_ids:
            if intercepts and i not in intercepts and i not in models:
                if i in table:
                    p_success[i] = float(table[i])
                continue
            row = models.get(i) if isinstance(models.get(i), dict) else {}
            factor = row.get("factor")
            if not factor or not query_proj:
                if i in table:
                    p_success[i] = float(table[i])
                continue
            ic = float(row.get("intercept", intercepts.get(i, 0.0)))
            p_success[i] = _calibrate(
                artifact, _bilinear_z(query_proj, [float(v) for v in factor], x, intercept=ic)
            )
        return bin_, p_success
    gbdt = artifact.get("gbdt")
    if isinstance(gbdt, dict) and gbdt:
        bin_ = (
            hint_bin
            if hint_bin in BINS
            else predict_complexity_bin(
                artifact, phase=phase, needs_tools=needs_tools, tokens=tokens
            )
        )
        x = featurize(phase, needs_tools, tokens, bin_, text=text)
        intercepts = artifact.get("intercepts") or {}
        table = artifact.get("p_success") or {}
        p_success = {}
        for i in eligible_ids:
            if intercepts and i not in intercepts:
                if i in table:
                    p_success[i] = float(table[i])
                continue
            head = gbdt.get(i)
            if not isinstance(head, dict):
                if i in table:
                    p_success[i] = float(table[i])
                continue
            p_success[i] = _calibrate(artifact, _gbdt_z(head, x))
        return bin_, p_success
    weights = artifact.get("weights")
    if isinstance(weights, dict) and weights:
        bin_ = (
            hint_bin
            if hint_bin in BINS
            else predict_complexity_bin(
                artifact, phase=phase, needs_tools=needs_tools, tokens=tokens
            )
        )
        x = featurize(phase, needs_tools, tokens, bin_, text=text)
        intercepts = artifact.get("intercepts") or {}
        table = artifact.get("p_success") or {}
        p_success = {}
        for i in eligible_ids:
            if intercepts and i not in intercepts:
                if i in table:
                    p_success[i] = float(table[i])
                continue
            w = weights.get(i)
            if not w or len(w) != len(x):
                if i in table:
                    p_success[i] = float(table[i])
                continue
            ic = float(intercepts.get(i, 0.0))
            p_success[i] = _calibrate(artifact, ic + _dot([float(v) for v in w], x))
        return bin_, p_success
    raw = artifact.get("p_success") or {}
    p_success = {i: float(raw[i]) for i in eligible_ids if i in raw}
    bin_ = str(artifact.get("complexity_bin") or "standard")
    if bin_ not in BINS:
        bin_ = "standard"
    return bin_, p_success


def effort_knobs(cfg: dict[str, Any], effort: str) -> tuple[float, float]:
    table = cfg.get("trained_effort") or SHIP_EFFORT
    row = table.get(effort) if effort in SHIP_EFFORT else None
    if not row:
        row = table.get("medium") or SHIP_EFFORT["medium"]
    return float(row["threshold"]), float(row["max_regret"])


def cascade_lane_config(cfg: dict[str, Any], *, phase: str) -> dict[str, Any] | None:
    raw = cfg.get("cascade_lane")
    if not isinstance(raw, dict) or not raw.get("enabled"):
        return None
    phases = raw.get("phases") or list(DEFAULT_CASCADE_PHASES)
    if phase not in {str(name) for name in phases}:
        return None
    cheap_id = str(raw.get("cheap_model") or "").strip()
    strong_id = str(raw.get("strong_model") or "").strip()
    if not cheap_id or not strong_id or cheap_id == strong_id:
        return None
    return {"cheap_model": cheap_id, "strong_model": strong_id, "phases": phases}


def pick_cheapest_above_bar(
    eligible: list[Model],
    p_success: dict[str, float],
    *,
    threshold: float,
    max_regret: float,
) -> tuple[Model | None, str]:
    scored = [(m, p_success[m.id]) for m in eligible if m.id in p_success]
    if not scored:
        return None, "fallback_declined"
    top_p = max(p for _, p in scored)
    above = [(m, p) for m, p in scored if p >= threshold]
    if not above:
        return None, "fallback_declined"
    within = [(m, p) for m, p in above if (top_p - p) <= max_regret]
    if not within:
        return None, "fallback_declined"
    within.sort(key=lambda mp: (mp[0].unit_cost, -mp[1]))
    dropped_regret = any((top_p - p) > max_regret for _, p in above)
    rule = "max_regret" if dropped_regret else "threshold"
    return within[0][0], rule


def cascade_select(
    cfg: dict[str, Any],
    models: list[Model],
    artifact: dict[str, Any],
    *,
    phase: str,
    needs_tools: bool,
    tokens: int,
    effort: str,
    allowed: set[str] | None,
    spend_usd: float,
    budget_usd: float,
    needs_json: bool = False,
    streaming: bool = False,
    max_tokens: int | None = None,
    latency_limit_ms: float | None = None,
    hint_bin: str | None = None,
    text: str = "",
) -> Decision | None:
    lane = cascade_lane_config(cfg, phase=phase)
    if lane is None:
        return None
    lane_allowed = {lane["cheap_model"], lane["strong_model"]}
    if allowed is not None:
        lane_allowed &= allowed
    if lane["strong_model"] not in lane_allowed:
        return None
    _, eligible = eligible_models(
        cfg,
        models,
        phase=phase,
        needs_tools=needs_tools,
        tokens=tokens,
        effort=effort,
        allowed=lane_allowed,
        spend_usd=spend_usd,
        budget_usd=budget_usd,
        needs_json=needs_json,
        streaming=streaming,
        max_tokens=max_tokens,
        latency_limit_ms=latency_limit_ms,
    )
    by_id = {m.id: m for m in eligible}
    strong = by_id.get(lane["strong_model"])
    if strong is None:
        return None
    cheap = by_id.get(lane["cheap_model"])
    bin_, p_success = score_eligible(
        artifact,
        [m.id for m in eligible],
        phase=phase,
        needs_tools=needs_tools,
        tokens=tokens,
        hint_bin=hint_bin,
        text=text,
    )
    if strong.id not in p_success:
        return None
    threshold, max_regret = effort_knobs(cfg, effort)
    choice = strong
    rule = "strong_pass_through"
    confidence = p_success[strong.id]
    reason = (
        f"cascade strong={strong.id} p={p_success[strong.id]:.3f}; "
        f"cheap={lane['cheap_model']} unavailable"
    )
    if cheap is not None and cheap.id in p_success:
        cheap_p = p_success[cheap.id]
        strong_p = p_success[strong.id]
        if cheap_p >= threshold and (strong_p - cheap_p) <= max_regret:
            choice = cheap
            rule = "cheap_redirect"
            confidence = cheap_p
        reason = (
            f"cascade cheap={cheap.id} p={cheap_p:.3f} strong={strong.id} p={strong_p:.3f} "
            f"t={threshold:.2f} r={max_regret:.2f}"
        )
    decision = Decision(
        model=choice,
        phase=phase,
        threshold=threshold,
        reason=reason,
        candidates=[m.id for m in eligible],
        effort=effort,
        path="cascade",
        rule=rule,
        complexity_bin=bin_,
        confidence=confidence,
        p_success=p_success,
        max_regret=max_regret,
        reason_codes=[f"bin:{bin_}", f"cascade:{rule}"],
    )
    stamp_baseline(decision, eligible, tokens)
    return decision


def trained_select(
    cfg: dict[str, Any],
    models: list[Model],
    artifact: dict[str, Any],
    *,
    phase: str,
    needs_tools: bool,
    tokens: int,
    effort: str,
    allowed: set[str] | None,
    spend_usd: float,
    budget_usd: float,
    needs_json: bool = False,
    streaming: bool = False,
    max_tokens: int | None = None,
    latency_limit_ms: float | None = None,
    hint_bin: str | None = None,
    text: str = "",
) -> Decision:
    aa_bar, eligible = eligible_models(
        cfg,
        models,
        phase=phase,
        needs_tools=needs_tools,
        tokens=tokens,
        effort=effort,
        allowed=allowed,
        spend_usd=spend_usd,
        budget_usd=budget_usd,
        needs_json=needs_json,
        streaming=streaming,
        max_tokens=max_tokens,
        latency_limit_ms=latency_limit_ms,
    )
    t, regret = effort_knobs(cfg, effort)
    bin_, p_success = score_eligible(
        artifact,
        [m.id for m in eligible],
        phase=phase,
        needs_tools=needs_tools,
        tokens=tokens,
        hint_bin=hint_bin,
        text=text,
    )
    chosen, rule = pick_cheapest_above_bar(eligible, p_success, threshold=t, max_regret=regret)
    if chosen is None:
        fb = fallback_decision(cfg, models, phase, aa_bar)
        fb.path = "trained"
        fb.effort = effort
        fb.rule = "fallback_declined"
        fb.complexity_bin = bin_
        fb.p_success = p_success
        fb.threshold = t
        fb.max_regret = regret
        fb.reason_codes = [f"bin:{bin_}", f"decline:{rule}"]
        fb.candidates = [m.id for m in eligible]
        stamp_baseline(fb, eligible, tokens)
        return fb
    conf = p_success.get(chosen.id)
    codes = [f"bin:{bin_}", "pick:cheapest_above_bar"]
    if rule == "max_regret":
        codes.append("pick:cheapest_within_regret")
    decision = Decision(
        model=chosen,
        phase=phase,
        threshold=t,
        reason="",
        candidates=[m.id for m in eligible],
        effort=effort,
        path="trained",
        rule=rule,
        complexity_bin=bin_,
        confidence=conf,
        p_success=p_success,
        max_regret=regret,
        reason_codes=codes,
    )
    stamp_baseline(decision, eligible, tokens)
    return decision


def apply_trained_path(
    hop_path: str,
    rules: Decision,
    trained: Decision | None,
    *,
    tokens: int,
    by_id: dict[str, Model] | None = None,
) -> Decision:
    if hop_path == "off":
        return rules
    if trained is None:
        rules.path = "rules"
        rules.rule = "fallback_declined"
        rules.reason_codes = ["scorer_down"]
        rules.confidence = None
        rules.complexity_bin = None
        return rules
    if hop_path == "trained":
        trained.path = "trained"
        trained.rules_cost_delta_usd = round(
            estimate_cost(trained.model, tokens, 800) - estimate_cost(rules.model, tokens, 800),
            6,
        )
        return trained
    rules.path = "shadow"
    rules.trained_selected = trained.model.id
    rules.trained_confidence = trained.confidence
    rules.complexity_bin = trained.complexity_bin
    rules.confidence = trained.confidence
    rules.rule = trained.rule
    rules.p_success = trained.p_success
    rules.threshold = trained.threshold
    rules.max_regret = trained.max_regret
    rules.reason_codes = list(trained.reason_codes or []) + ["shadow:rules_serving"]
    rules.baseline_model_id = trained.baseline_model_id
    rules.candidates = trained.candidates
    rules.effort = trained.effort
    if trained.baseline_model_id and by_id and trained.baseline_model_id in by_id:
        base = by_id[trained.baseline_model_id]
        rules.savings_usd = round(
            max(0.0, estimate_cost(base, tokens, 800) - estimate_cost(rules.model, tokens, 800)),
            6,
        )
    rules.rules_cost_delta_usd = round(
        estimate_cost(trained.model, tokens, 800) - estimate_cost(rules.model, tokens, 800),
        6,
    )
    return rules


