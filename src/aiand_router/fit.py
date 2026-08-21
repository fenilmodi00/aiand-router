"""Offline scorer fit: row featurize adapters, heads, calibration, artifact write.

Serve reads the Scorer JSON schema produced by fit_scorer; keep that seam stable.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

import random

from .router import _text, estimate_tokens
from .scorer import (
    BINS,
    _bilinear_z,
    _gbdt_z,
    _query_latent,
    featurize,
    featurize_bilinear,
    featurize_observable,
)

# Catalog id used only for silver-only prior fill (no K3 gold at plan budget).
K3 = "moonshotai/kimi-k3"


def _row_x_observable(row: dict[str, Any]) -> list[float]:
    messages = row.get("messages") or [{"role": "user", "content": row.get("prompt") or ""}]
    tokens = int(row.get("tokens") or estimate_tokens(messages))
    return featurize_observable(str(row.get("phase") or "plan"), bool(row.get("needs_tools")), tokens)


def _row_x(row: dict[str, Any]) -> list[float]:
    messages = row.get("messages") or [{"role": "user", "content": row.get("prompt") or ""}]
    tokens = int(row.get("tokens") or estimate_tokens(messages))
    hint = str(row.get("hint_bin") or row.get("complexity_bin") or "standard")
    text = str(row.get("prompt") or "")
    if not text and messages:
        text = "\n".join(_text(m.get("content")) for m in messages if isinstance(m, dict))
    return featurize(str(row.get("phase") or "plan"), bool(row.get("needs_tools")), tokens, hint, text=text)


def _logit(p: float) -> float:
    p = max(1e-6, min(1.0 - 1e-6, p))
    return math.log(p / (1.0 - p))


def _fit_binary(xs: list[list[float]], ys: list[float], steps: int = 80, lr: float = 0.35) -> list[float]:
    dim = len(xs[0])
    w = [0.0] * dim
    n = max(1, len(xs))
    for _ in range(steps):
        grad = [0.0] * dim
        for x, y in zip(xs, ys):
            z = sum(w[i] * x[i] for i in range(dim))
            z = max(-30.0, min(30.0, z))
            err = (1.0 / (1.0 + math.exp(-z))) - y
            for i in range(dim):
                grad[i] += err * x[i]
        for i in range(dim):
            w[i] -= lr * grad[i] / n
    return w


def _fit_binary_intercept(
    xs: list[list[float]], ys: list[float], intercept: float, steps: int = 80, lr: float = 0.35
) -> list[float]:
    dim = len(xs[0])
    w = [0.0] * dim
    n = max(1, len(xs))
    for _ in range(steps):
        grad = [0.0] * dim
        for x, y in zip(xs, ys):
            z = intercept + sum(w[i] * x[i] for i in range(dim))
            z = max(-30.0, min(30.0, z))
            err = (1.0 / (1.0 + math.exp(-z))) - y
            for i in range(1, dim):
                grad[i] += err * x[i]
        for i in range(1, dim):
            w[i] -= lr * grad[i] / n
    return w


GBDT_TREES = 24
GBDT_LR = 0.1
# Latent dim tracks feature dim (identity init). A padded 32-d trunk left
# unused rows at 0 and interaction terms too small to move vs intercepts.
BILINEAR_DIM = 0
GEOMETRY_OVERRIDE_ENV = "GEOMETRY_OVERRIDE"


def _row_x_bilinear(
    row: dict[str, Any],
    *,
    hash_dim: int = 0,
    hash_seed: int = 17,
) -> list[float]:
    messages = row.get("messages") or [{"role": "user", "content": row.get("prompt") or ""}]
    tokens = int(row.get("tokens") or estimate_tokens(messages))
    hint = str(row.get("hint_bin") or row.get("complexity_bin") or "standard")
    text = str(row.get("prompt") or "")
    if not text and messages:
        text = "\n".join(_text(m.get("content")) for m in messages if isinstance(m, dict))
    return featurize_bilinear(
        str(row.get("phase") or "plan"),
        bool(row.get("needs_tools")),
        tokens,
        hint,
        text=text,
        hash_dim=hash_dim,
        hash_seed=hash_seed,
    )


def _ridge_multivariate(
    xs: list[list[float]],
    ys: list[list[float]],
    *,
    l2: float = 0.05,
) -> list[list[float]]:
    """Row-major W (out_dim × in_dim) minimizing ||W x - y||^2 + l2||W||^2."""
    if not xs or not ys or len(xs) != len(ys):
        return []
    in_dim = len(xs[0])
    out_dim = len(ys[0])
    # Accumulate XtX and XtY
    xtx = [[0.0] * in_dim for _ in range(in_dim)]
    xty = [[0.0] * out_dim for _ in range(in_dim)]
    for x, y in zip(xs, ys):
        for i in range(in_dim):
            xi = x[i]
            for j in range(in_dim):
                xtx[i][j] += xi * x[j]
            for k in range(out_dim):
                xty[i][k] += xi * y[k]
    for i in range(in_dim):
        xtx[i][i] += l2
    # Gauss-Jordan solve for each output column.
    w_t = [[0.0] * out_dim for _ in range(in_dim)]  # in_dim × out_dim
    for k in range(out_dim):
        a = [row[:] + [xty[i][k]] for i, row in enumerate(xtx)]
        n = in_dim
        for col in range(n):
            pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
            a[col], a[pivot] = a[pivot], a[col]
            diag = a[col][col] or 1e-12
            inv = 1.0 / diag
            a[col] = [v * inv for v in a[col]]
            for r in range(n):
                if r == col:
                    continue
                factor = a[r][col]
                a[r] = [a[r][c] - factor * a[col][c] for c in range(n + 1)]
        for i in range(n):
            w_t[i][k] = a[i][n]
    # Return out_dim × in_dim (query_proj layout).
    return [[w_t[j][i] for j in range(in_dim)] for i in range(out_dim)]


def _fit_bilinear(
    cells: list[tuple[list[float], float, str]],
    *,
    dim: int | None = None,
    steps: int = 120,
    lr: float = 0.08,
) -> tuple[list[list[float]], dict[str, list[float]], dict[str, float]]:
    """Shared query projection + per-model factor vectors (EmbedLLM/IRT-lite).

    Intercepts stay at gold logit(rate) (same as logistic). Stage 1 fits
    per-model factors with identity projection so the head cannot collapse
    below a per-model linear model. Stage 2 takes small joint steps on the
    projection so query×model terms can move without wiping the intercepts.
    """
    if not cells:
        return [], {}, {}
    feat_dim = len(cells[0][0])
    dim = feat_dim if not dim else min(int(dim), feat_dim)
    mids = sorted({mid for _, _, mid in cells})
    intercepts: dict[str, float] = {}
    factors: dict[str, list[float]] = {}
    counts: dict[str, int] = {}
    for mid in mids:
        xs = [x for x, _, m in cells if m == mid]
        ys = [y for _, y, m in cells if m == mid]
        rate = sum(ys) / len(ys) if ys else 0.5
        intercepts[mid] = _logit(rate)
        counts[mid] = len(ys)
        w = _fit_binary_intercept(xs, ys, intercepts[mid])
        factors[mid] = (list(w) + [0.0] * dim)[:dim]
    query_proj = [[0.0] * feat_dim for _ in range(dim)]
    for i in range(dim):
        query_proj[i][i] = 1.0
    n = max(1, len(cells))
    l2 = 0.002
    for _ in range(steps):
        g_proj = [[0.0] * feat_dim for _ in range(dim)]
        g_factors: dict[str, list[float]] = {mid: [0.0] * dim for mid in mids}
        for x, y, mid in cells:
            q = [
                sum(query_proj[i][j] * x[j] for j in range(feat_dim))
                for i in range(dim)
            ]
            fac = factors[mid]
            z = intercepts[mid] + sum(q[i] * fac[i] for i in range(dim))
            z = max(-30.0, min(30.0, z))
            err = (1.0 / (1.0 + math.exp(-z))) - y
            for i in range(dim):
                g_factors[mid][i] += err * q[i]
                for j in range(feat_dim):
                    g_proj[i][j] += err * fac[i] * x[j]
        for mid in mids:
            nm = max(1, counts[mid])
            for i in range(dim):
                factors[mid][i] -= lr * (g_factors[mid][i] / nm + l2 * factors[mid][i])
        for i in range(dim):
            for j in range(feat_dim):
                # Keep the identity diagonal from shrinking to the old 0.05 collapse.
                if i == j:
                    continue
                query_proj[i][j] -= lr * (g_proj[i][j] / n + l2 * query_proj[i][j])
    return query_proj, factors, intercepts


def _fit_bilinear_distill(
    student_cells: list[tuple[list[float], float, str]],
    teacher_cells: list[tuple[list[float], float, str]],
    *,
    latent_dim: int | None = None,
    ridge_l2: float = 0.05,
) -> tuple[list[list[float]], dict[str, list[float]], dict[str, float], dict[str, Any]]:
    """Offline distill: fit teacher on richer x, map student x → teacher query latent."""
    if not teacher_cells or not student_cells:
        return [], {}, {}, {}
    t_dim = len(teacher_cells[0][0])
    # Keep latent compact so ridge→student does not overfit Mix1 n≈160.
    ld = int(latent_dim) if latent_dim else min(32, t_dim)
    teacher_proj, factors, intercepts = _fit_bilinear(teacher_cells, dim=ld)
    if not teacher_proj:
        return [], {}, {}, {}
    xs_s: list[list[float]] = []
    qs_t: list[list[float]] = []
    for (xs, _ys, _ms), (xt, _yt, _mt) in zip(student_cells, teacher_cells):
        qs_t.append(_query_latent(teacher_proj, xt))
        xs_s.append(xs)
    l2 = float(ridge_l2)
    student_proj = _ridge_multivariate(xs_s, qs_t, l2=l2)
    meta = {
        "mode": "hash_teacher_ridge",
        "teacher_feat_dim": t_dim,
        "student_feat_dim": len(student_cells[0][0]),
        "latent_dim": ld,
        "ridge_l2": l2,
        "n_distill": len(xs_s),
    }
    return student_proj, factors, intercepts, meta


def _geometry_gate(
    train_path: Path,
    eval_path: Path,
    cal_path: Path | None = None,
) -> tuple[bool, dict[str, Any]]:
    from .geometry import geometry_report

    report = geometry_report(train_path, eval_path, cal_path)
    blocked = not report.get("geometry_pass", False)
    if blocked and os.getenv(GEOMETRY_OVERRIDE_ENV) == "1":
        blocked = False
        report["geometry_override"] = True
    return blocked, report


def _fit_stump(xs: list[list[float]], resid: list[float]) -> dict[str, float]:
    n = len(xs)
    dim = len(xs[0]) if xs else 0
    best: tuple[float, int, float, float, float] | None = None
    for j in range(1, dim):
        vals = sorted({x[j] for x in xs})
        if len(vals) < 2:
            continue
        for k in range(len(vals) - 1):
            thr = 0.5 * (vals[k] + vals[k + 1])
            left_s = left_n = right_s = right_n = 0.0
            for x, r in zip(xs, resid):
                if x[j] <= thr:
                    left_s += r
                    left_n += 1
                else:
                    right_s += r
                    right_n += 1
            if left_n == 0 or right_n == 0:
                continue
            left, right = left_s / left_n, right_s / right_n
            sse = 0.0
            for x, r in zip(xs, resid):
                pred = left if x[j] <= thr else right
                sse += (r - pred) ** 2
            if best is None or sse < best[0]:
                best = (sse, j, thr, left, right)
    if best is None:
        mean = (sum(resid) / n) if n else 0.0
        return {"feature": 0, "threshold": 0.0, "left": mean, "right": mean}
    return {"feature": best[1], "threshold": best[2], "left": best[3], "right": best[4]}


def _fit_gbdt(
    xs: list[list[float]],
    ys: list[float],
    intercept: float,
    n_trees: int = GBDT_TREES,
    lr: float = GBDT_LR,
) -> dict[str, Any]:
    z = [intercept] * len(xs)
    trees: list[dict[str, float]] = []
    for _ in range(n_trees):
        p = [1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, zi)))) for zi in z]
        resid = [y - pi for y, pi in zip(ys, p)]
        stump = _fit_stump(xs, resid)
        stump["left"] = float(stump["left"]) * lr
        stump["right"] = float(stump["right"]) * lr
        trees.append(stump)
        j = int(stump["feature"])
        thr = float(stump["threshold"])
        for i, x in enumerate(xs):
            z[i] += stump["left"] if (j < len(x) and x[j] <= thr) else stump["right"]
    return {"intercept": intercept, "trees": trees}


def _fit_platt(zs: list[float], ys: list[float]) -> tuple[float, float]:
    if len(zs) < 2:
        return 1.0, 0.0
    a, b = 1.0, 0.0
    n = len(zs)
    for _ in range(60):
        ga = gb = 0.0
        for z, y in zip(zs, ys):
            p = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, a * z + b))))
            err = p - y
            ga += err * z
            gb += err
        a -= 0.2 * ga / n
        b -= 0.2 * gb / n
    # Negative slope inverts ranking (Mix1 bilinear probe: always-Flash).
    if a <= 0:
        return 1.0, 0.0
    return a, b


def _fit_isotonic(zs: list[float], ys: list[float]) -> list[list[float]]:
    """Pure-Python PAVA (Pool Adjacent Violators).

    Returns a monotone step table ``[[z, p], ...]`` suitable for JSON.
    Each entry is ``[max_z_of_block, pooled_mean]``; p is non-decreasing.
    Lookup: first entry where ``z_q <= boundary`` wins; clamp to last.
    """
    if len(zs) != len(ys):
        raise ValueError("zs and ys must have equal length")
    if not zs:
        raise ValueError("cannot fit isotonic on empty (z, y) lists")
    pairs = sorted(zip(zs, ys), key=lambda p: p[0])
    # blocks: [sum_y, count, max_z]
    blocks: list[list[float]] = []
    for z, y in pairs:
        blocks.append([y, 1, z])
        while len(blocks) >= 2 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
            blocks[-2][0] += blocks[-1][0]
            blocks[-2][1] += blocks[-1][1]
            blocks[-2][2] = blocks[-1][2]
            blocks.pop()
    return [[b[2], b[0] / b[1]] for b in blocks]


CAL_FRAC = 0.2


def _split_cal_prompts(prompts: list[str], frac: float = CAL_FRAC) -> tuple[set[str], set[str]]:
    """Hold out a sorted tail of unique prompts as the gold cal slice."""
    uniq = sorted({p for p in prompts if p})
    if len(uniq) < 2:
        return set(uniq), set()
    n_cal = max(1, int(round(len(uniq) * frac)))
    cal = set(uniq[-n_cal:])
    return set(uniq) - cal, cal


def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _observed_gold(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if not r.get("unobserved") and "model_id" in r]


def fit_scorer(
    gold_path: Path,
    silver_path: Path | None,
    out: Path,
    cal_path: Path | None = None,
    gbdt: bool = False,
    bilinear: bool = False,
    geometry_report_out: dict[str, Any] | None = None,
    bilinear_hash_dim: int = 0,
    bilinear_distill_hash_dim: int = 0,
    bilinear_hash_seed: int = 17,
    bilinear_distill_latent_dim: int = 0,
    bilinear_ridge_l2: float = 0.05,
    noise_alpha: float = 0.0,
) -> None:
    gold = _jsonl_rows(gold_path)
    silver = _jsonl_rows(silver_path) if silver_path and silver_path.exists() else []
    observed = _observed_gold(gold)
    cal_file = _observed_gold(_jsonl_rows(cal_path)) if cal_path and cal_path.exists() else []
    tagged_cal = [r for r in observed if r.get("dense")]
    tagged_train = [r for r in observed if not r.get("dense")]
    if cal_file:
        train_gold = tagged_train
        cal_gold = cal_file
    elif tagged_cal:
        train_gold = tagged_train
        cal_gold = tagged_cal
    else:
        train_prompts, cal_prompts = _split_cal_prompts(
            [str(r.get("prompt") or "") for r in observed]
        )
        train_gold = [r for r in observed if str(r.get("prompt") or "") in train_prompts]
        cal_gold = [r for r in observed if str(r.get("prompt") or "") in cal_prompts]
    observed = train_gold + cal_gold
    gold_cells = {(str(r.get("prompt")), r["model_id"]) for r in observed}
    gold_ids = {mid for _, mid in gold_cells}
    by_model_x: dict[str, list[list[float]]] = {mid: [] for mid in gold_ids}
    by_model_y: dict[str, list[float]] = {mid: [] for mid in gold_ids}
    train_counts: dict[str, int] = {mid: 0 for mid in gold_ids}
    hash_dim = int(bilinear_hash_dim or 0)
    distill_dim = int(bilinear_distill_hash_dim or 0)
    hash_seed = int(bilinear_hash_seed or 17)
    # Distill serve path keeps student hash_dim=0; teacher uses distill_dim.
    serve_hash_dim = 0 if distill_dim > 0 else hash_dim
    teacher_hash_dim = distill_dim if distill_dim > 0 else hash_dim
    bilinear_cells: list[tuple[list[float], float, str]] = []
    teacher_cells: list[tuple[list[float], float, str]] = []
    for row in train_gold:
        mid = row["model_id"]
        by_model_x[mid].append(_row_x(row))
        by_model_y[mid].append(1.0 if row.get("success") else 0.0)
        train_counts[mid] += 1
        y = 1.0 if row.get("success") else 0.0
        bilinear_cells.append(
            (
                _row_x_bilinear(row, hash_dim=serve_hash_dim, hash_seed=hash_seed),
                y,
                mid,
            )
        )
        if distill_dim > 0:
            teacher_cells.append(
                (
                    _row_x_bilinear(row, hash_dim=teacher_hash_dim, hash_seed=hash_seed),
                    y,
                    mid,
                )
            )
    for row in silver:
        if row.get("unlabeled"):
            continue
        x = _row_x(row)
        prompt = str(row.get("prompt") or "")
        for mid, p in (row.get("p_success") or {}).items():
            if mid not in gold_ids:
                continue
            if (prompt, mid) in gold_cells:
                continue
            by_model_x[mid].append(x)
            by_model_y[mid].append(float(p))
            bilinear_cells.append(
                (
                    _row_x_bilinear(row, hash_dim=serve_hash_dim, hash_seed=hash_seed),
                    float(p),
                    mid,
                )
            )
            if distill_dim > 0:
                teacher_cells.append(
                    (
                        _row_x_bilinear(row, hash_dim=teacher_hash_dim, hash_seed=hash_seed),
                        float(p),
                        mid,
                    )
                )
    if noise_alpha < 0:
        raise ValueError("noise_alpha must be >= 0")
    if noise_alpha > 0:
        rng = random.Random(0)
        for xs in by_model_x.values():
            for x in xs:
                for i in range(len(x)):
                    x[i] += rng.gauss(0, float(noise_alpha))
        for idx in range(len(bilinear_cells)):
            x, y, mid = bilinear_cells[idx]
            jittered = [v + rng.gauss(0, float(noise_alpha)) for v in x]
            bilinear_cells[idx] = (jittered, y, mid)
        for idx in range(len(teacher_cells)):
            x, y, mid = teacher_cells[idx]
            jittered = [v + rng.gauss(0, float(noise_alpha)) for v in x]
            teacher_cells[idx] = (jittered, y, mid)
    weights: dict[str, list[float]] = {}
    intercepts = {}
    gbdt_heads: dict[str, dict[str, Any]] = {}
    bilinear_models: dict[str, dict[str, Any]] = {}
    query_proj: list[list[float]] = []
    distill_meta: dict[str, Any] = {}
    for mid, xs in by_model_x.items():
        n_train = train_counts[mid]
        if n_train == 0 or not xs:
            continue
        gold_ys = by_model_y[mid][:n_train]
        rate = sum(gold_ys) / len(gold_ys) if gold_ys else 0.5
        ic = _logit(rate)
        intercepts[mid] = ic
        if gbdt:
            gbdt_heads[mid] = _fit_gbdt(xs, by_model_y[mid], ic)
        elif bilinear:
            continue
        else:
            weights[mid] = _fit_binary_intercept(xs, by_model_y[mid], ic)
    if bilinear and bilinear_cells:
        if distill_dim > 0 and teacher_cells:
            ld_arg = int(bilinear_distill_latent_dim or 0) or None
            query_proj, factors, bi_ic, distill_meta = _fit_bilinear_distill(
                bilinear_cells,
                teacher_cells,
                latent_dim=ld_arg,
                ridge_l2=float(bilinear_ridge_l2),
            )
        else:
            query_proj, factors, bi_ic = _fit_bilinear(bilinear_cells)
        for mid, fac in factors.items():
            if train_counts.get(mid, 0) == 0:
                continue
            intercepts[mid] = bi_ic[mid]
            bilinear_models[mid] = {"factor": fac, "intercept": bi_ic[mid]}
    zs_cal: list[float] = []
    ys_cal: list[float] = []
    for row in cal_gold:
        mid = row["model_id"]
        if gbdt:
            head = gbdt_heads.get(mid)
            if not head:
                continue
            zs_cal.append(_gbdt_z(head, _row_x(row)))
        elif bilinear:
            if mid not in bilinear_models or not query_proj:
                continue
            bm = bilinear_models[mid]
            zs_cal.append(
                _bilinear_z(
                    query_proj,
                    bm["factor"],
                    _row_x_bilinear(row, hash_dim=serve_hash_dim, hash_seed=hash_seed),
                    intercept=float(bm.get("intercept", intercepts.get(mid, 0.0))),
                )
            )
        else:
            w = weights.get(mid)
            if not w:
                continue
            ic = intercepts[mid]
            x = _row_x(row)
            zs_cal.append(ic + sum(w[i] * x[i] for i in range(len(w))))
        ys_cal.append(1.0 if row.get("success") else 0.0)
    n_cal = len(zs_cal)
    if n_cal <= 1000:
        a, b = _fit_platt(zs_cal, ys_cal)
        calibrator: dict[str, Any] = {"mode": "platt", "a": a, "b": b}
    else:
        table = _fit_isotonic(zs_cal, ys_cal)
        calibrator = {"mode": "isotonic", "table": table}
        a, b = 1.0, 0.0
    bin_xs: list[list[float]] = []
    bin_ys: dict[str, list[float]] = {bn: [] for bn in BINS}
    for row in silver:
        if row.get("unlabeled") or row.get("complexity_bin") not in BINS:
            continue
        x = _row_x_observable(row)
        bin_xs.append(x)
        for bn in BINS:
            bin_ys[bn].append(1.0 if row["complexity_bin"] == bn else 0.0)
    bin_weights = {bn: _fit_binary(bin_xs, bin_ys[bn]) for bn in BINS} if bin_xs else {}
    p_success = {}
    for mid in gold_ids:
        gold_ys = [1.0 if r.get("success") else 0.0 for r in observed if r["model_id"] == mid]
        if gold_ys:
            p_success[mid] = sum(gold_ys) / len(gold_ys)
    k3_prior = [
        float(p)
        for row in silver
        if not row.get("unlabeled")
        for mid, p in (row.get("p_success") or {}).items()
        if mid == K3 and p is not None
    ]
    if k3_prior:
        p_success[K3] = sum(k3_prior) / len(k3_prior)
    bins = [str(r.get("complexity_bin")) for r in silver if r.get("complexity_bin") in BINS]
    bin_ = max(set(bins), key=bins.count) if bins else "standard"
    artifact: dict[str, Any] = {
        "not_spec_floors": True,
        "complexity_bin": bin_,
        "p_success": p_success,
        "weights": weights,
        "intercepts": intercepts,
        "bin_weights": bin_weights,
        "platt": {"a": a, "b": b},
        "calibrator": calibrator,
        "n_gold": len(gold),
        "n_cal": len(cal_gold),
        "n_silver": len(silver),
    }
    if gbdt:
        artifact["head"] = "gbdt"
        artifact["gbdt"] = gbdt_heads
    elif bilinear and query_proj:
        artifact["head"] = "bilinear"
        bi_block: dict[str, Any] = {
            "dim": len(query_proj),
            "query_proj": query_proj,
            "models": bilinear_models,
            "hash_dim": serve_hash_dim,
            "hash_seed": hash_seed,
        }
        if distill_meta:
            bi_block["distill"] = distill_meta
            bi_block["teacher_hash_dim"] = distill_dim
        artifact["bilinear"] = bi_block
    else:
        artifact["head"] = "logistic"
    if geometry_report_out is not None:
        artifact["geometry"] = {
            "geometry_pass": geometry_report_out.get("geometry_pass"),
            "spearman_train_eval": geometry_report_out.get("spearman_train_eval"),
            "kill": geometry_report_out.get("kill"),
            "recommended_artifact": geometry_report_out.get("recommended_artifact"),
            "geometry_override": geometry_report_out.get("geometry_override"),
        }
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")

