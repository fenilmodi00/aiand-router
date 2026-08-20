"""Unpaid Verified session-gold promotion gate scaffolding (runbook §(a)).

Facade for readiness / checklist / live-verdict consumers:

- ``promotion_readiness`` / ``build_gate_checklist`` — unpaid local-replay + scaffold
- ``checklist_from_live_bars`` — adapts ``eval.promotion_gate_verdict`` bars onto the
  same PROMOTION_BARS surface (session-gold / shadow-log)
- ``local_replay_snapshot`` — thin adapter over offline replay

Numeric calibration bars and Brier/ECE computation live in ``metrics.py``.
Does not run paid HTTP or flip TRAINED_PATH.

Floor scaling distinguishes two resolve paths that both honor §(a) spirit:

- ``local_image_farm`` — retain many ``sweb.eval`` images on this host (disk-blocked here)
- ``remote_eval`` — Modal / sb-cli / ephemeral env+clean (disk-light; needs auth smoke)
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
from pathlib import Path
from typing import Any

from .metrics import (
    ECE_MAX,
    QUALITY_TOLERANCE,
    SMALL_N_ECE_MASS,
    VERIFIED_N_FLOOR,
    bss_passes,
    ece_mass_is_gated,
    ece_mass_passes,
    ece_passes,
)
from .replay_report import apply_replay_gate, parity_blockers, replay_report
from .router import estimate_cost, load_config, load_models
from .scorer import load_scorer

ROOT = Path(__file__).resolve().parents[2]
VERIFIED_PRIMARY_N = 500
COMPLETION_TOKENS = 800
PROMPT_TOKENS_EST = 1500
TURNS_PER_INSTANCE = 5  # discover/plan/edit/debug/summarize flashlight loop

# Scratch evidence folded into readiness (unpaid; no serve flip).
DISK_LIGHT_DOC = (
    ROOT / ".scratch" / "scorer-pioneer-lift" / "disk-light-parity-path-2026-08-20.md"
)
SESSION_JOINED_SAMPLE_DOC = (
    ROOT / ".scratch" / "scorer-pioneer-lift" / "session-joined-cost-sample-2026-08-20.md"
)
LIVE_FILECTX_SESSIONS = ROOT / "data" / "verified_session_filectx_all.jsonl"

# Runbook §(a) pass bars (medium only; all must hold). Numbers from metrics.py.
PROMOTION_BARS: tuple[dict[str, str], ...] = (
    {
        "id": "quality_session_gold",
        "bar": (
            f"session gold (tests_passed / resolve) >= rules - {QUALITY_TOLERANCE} absolute"
        ),
        "source": "docs/runbook-production.md §(a) pass bars #1",
    },
    {
        "id": "quality_escalate",
        "bar": f"per-request escalate rate >= rules - {QUALITY_TOLERANCE} absolute",
        "source": "docs/runbook-production.md §(a) pass bars #1",
    },
    {
        "id": "cost_rules_delta",
        "bar": "rules_cost_delta < 0 (trained - rules list-price USD; equal -> no promote)",
        "source": "docs/runbook-production.md §(a) pass bars #2",
    },
    {
        "id": "calibration_bss",
        "bar": "Brier skill score (BSS) > 0 on selected hops",
        "source": "docs/runbook-production.md §(a) pass bars #3",
    },
    {
        "id": "calibration_ece_width",
        "bar": f"equal-width ECE (M=10) <= {ECE_MAX}",
        "source": "docs/runbook-production.md §(a) pass bars #3",
    },
    {
        "id": "calibration_ece_mass",
        "bar": (
            f"equal-mass ECE (M=10) <= {ECE_MAX} when n_selected >= {SMALL_N_ECE_MASS}"
        ),
        "source": "docs/runbook-production.md §(a) pass bars #3",
    },
    {
        "id": "floor_session_gold_n",
        "bar": (
            f"n >= {VERIFIED_N_FLOOR} session-gold tasks (primary split n={VERIFIED_PRIMARY_N}); "
            "resolve via local_image_farm OR remote_eval (Modal/sb-cli/ephemeral)"
        ),
        "source": "docs/runbook-production.md §(a) pass bars #4",
    },
)


def _modal_configured() -> bool:
    """Same credential file check as scripts/swe_eval_cmd.py / swebench modal_eval."""
    return (Path.home() / ".modal.toml").is_file()


def _sb_cli_available() -> bool:
    if shutil.which("sb-cli"):
        return True
    try:
        return importlib.util.find_spec("sb_cli") is not None
    except (ImportError, ValueError):
        return False


def _sb_cli_configured() -> bool:
    return bool((os.getenv("SWEBENCH_API_KEY") or "").strip()) and _sb_cli_available()


def resolve_backend_posture() -> dict[str, Any]:
    """Non-interactive Modal / sb-cli / local resolve posture (no docker pull).

    Distinguishes floor blockers:

    - ``local_image_farm`` — scaling by retaining many local ``sweb.eval`` images
    - ``remote_eval`` — Modal / sb-cli / ephemeral clean eval (disk-light)
    """
    modal_pkg = importlib.util.find_spec("modal") is not None
    modal_toml = _modal_configured()
    swebench_pkg = importlib.util.find_spec("swebench") is not None
    sb_cli_pkg = _sb_cli_available()
    sb_cli_key = bool((os.getenv("SWEBENCH_API_KEY") or "").strip())
    modal_ready = modal_pkg and modal_toml and swebench_pkg
    sb_cli_ready = sb_cli_pkg and sb_cli_key
    remote_ready = modal_ready or sb_cli_ready
    return {
        "modal": {
            "package_installed": modal_pkg,
            "toml_present": modal_toml,
            "swebench_installed": swebench_pkg,
            "configured": modal_ready,
            "block_reason": (
                None
                if modal_ready
                else (
                    "modal_not_configured"
                    if modal_pkg and swebench_pkg
                    else "modal_or_swebench_missing"
                )
            ),
        },
        "sb_cli": {
            "cli_or_package": sb_cli_pkg,
            "api_key_set": sb_cli_key,
            "configured": sb_cli_ready,
            "block_reason": (
                None
                if sb_cli_ready
                else ("sb_cli_not_configured" if sb_cli_pkg else "sb_cli_missing")
            ),
        },
        "local": {
            "default_backend": True,
            "note": (
                "local run_evaluation needs instance images; this host is "
                "local_image_farm disk-blocked for n>>12 (no mass docker pull)"
            ),
            "floor_path": "local_image_farm",
            "scale_ready": False,
        },
        "remote_eval_ready": remote_ready,
        "preferred_scale_path": "remote_eval" if remote_ready else "remote_eval_auth_pending",
        "floor_paths": {
            "local_image_farm": {
                "honors_runbook_spirit": True,
                "scale_ready_on_this_host": False,
                "blocker": "disk_blocked_no_mass_pull",
            },
            "remote_eval": {
                "honors_runbook_spirit": True,
                "scale_ready_on_this_host": remote_ready,
                "blocker": None if remote_ready else "auth_pending_modal_or_sb_cli",
                "adapter": "scripts/swe_eval_cmd.py --backend modal|sb-cli",
            },
        },
        "disk_light_doc": str(DISK_LIGHT_DOC) if DISK_LIGHT_DOC.exists() else None,
    }


def count_session_gold_rows(sessions_path: Path) -> dict[str, Any]:
    """Count unique session_gold rows without claiming promotion floor."""
    if not sessions_path.exists():
        return {
            "path": str(sessions_path),
            "exists": False,
            "n_unique": 0,
            "n_session_gold": 0,
        }
    gold_ids: set[str] = set()
    all_ids: set[str] = set()
    with sessions_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            iid = str(row.get("instance_id") or row.get("id") or "")
            if not iid:
                continue
            all_ids.add(iid)
            if row.get("session_gold") is True:
                gold_ids.add(iid)
    return {
        "path": str(sessions_path),
        "exists": True,
        "n_unique": len(all_ids),
        "n_session_gold": len(gold_ids),
        "below_floor": len(gold_ids) < VERIFIED_N_FLOOR,
        "floor_n": VERIFIED_N_FLOOR,
    }


def session_joined_cost_sample_summary() -> dict[str, Any] | None:
    """Fold unpaid joined-cost sample evidence if the scratch note exists."""
    if not SESSION_JOINED_SAMPLE_DOC.exists():
        return None
    return {
        "doc": str(SESSION_JOINED_SAMPLE_DOC),
        "session_joined": True,
        "n_joinable_hops_sample": 10,
        "joined_rules_cost_delta_approx": -0.00162,
        "verdict": "bounded_check_only",
        "note": (
            "Live join works after gateway restart; sample n≪300 — not promotion evidence"
        ),
    }


def load_ids_scaffold(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: scaffold must be a JSON object")
    return data


def validate_ids_scaffold(scaffold: dict[str, Any]) -> list[str]:
    """Return validation errors; empty list means scaffold shape is OK (still not session gold)."""
    errors: list[str] = []
    verdict = scaffold.get("verdict")
    if verdict != "ids_scaffold_only":
        errors.append(f"verdict={verdict!r} (expected ids_scaffold_only)")
    if scaffold.get("session_gold") is not False:
        errors.append("session_gold must be false for unpaid scaffold")
    if scaffold.get("production_parity") is not False:
        errors.append("production_parity must be false for unpaid scaffold")
    ids = scaffold.get("instance_ids")
    if not isinstance(ids, list) or not ids:
        errors.append("instance_ids must be a non-empty list")
    elif len(set(ids)) != len(ids):
        errors.append("instance_ids contains duplicates")
    n = int(scaffold.get("n") or 0)
    if ids and n != len(ids):
        errors.append(f"n={n} does not match len(instance_ids)={len(ids)}")
    if n < VERIFIED_N_FLOOR:
        errors.append(f"n={n} below session-gold floor {VERIFIED_N_FLOOR}")
    bench = str(scaffold.get("bench") or "")
    if bench not in {"verified", "swe-bench-verified", "swe_verified"}:
        errors.append(f"bench={bench!r} (expected verified)")
    return errors


def estimate_gate_budget(
    *,
    n_instances: int,
    models_cfg: list[Any],
    prompt_tokens: int = PROMPT_TOKENS_EST,
    completion_tokens: int = COMPLETION_TOKENS,
    turns_per_instance: int = TURNS_PER_INSTANCE,
) -> dict[str, Any]:
    """Runbook §(a) list-price estimate: every eligible model × every instance × turns."""
    enabled = [m for m in models_cfg if getattr(m, "enabled", True)]
    per_model = [
        {
            "id": m.id,
            "est_usd_per_completion": round(
                estimate_cost(m, prompt_tokens, completion_tokens), 6
            ),
        }
        for m in enabled
    ]
    avg_completion = (
        sum(row["est_usd_per_completion"] for row in per_model) / len(per_model)
        if per_model
        else 0.0
    )
    # Session gate runs router/auto turn loop (not dense all-models-per-query).
    hops = n_instances * turns_per_instance * 2  # rules serve + shadow trained counterfactual logging
    shadow_session_usd = round(hops * avg_completion * 0.35, 2)  # ~one model served per hop, not full dense
    dense_all_models_usd = round(
        n_instances * len(enabled) * avg_completion, 2
    )
    return {
        "n_instances": n_instances,
        "n_enabled_models": len(enabled),
        "turns_per_instance": turns_per_instance,
        "est_usd_per_completion_avg": round(avg_completion, 6),
        "per_model_completion_est": per_model,
        "shadow_dual_policy_session_gate_est_usd": shadow_session_usd,
        "dense_all_models_per_instance_est_usd": dense_all_models_usd,
        "note": (
            "shadow_dual_policy_session_gate_est_usd is a turn-loop router/auto estimate "
            "(not train gold --dense). dense_* is runbook upper-bound if every model ran per instance."
        ),
    }


def local_replay_snapshot(
    *,
    gold_path: Path,
    artifact_path: Path,
    models_path: Path,
    cost_gold_path: Path | None = None,
) -> dict[str, Any] | None:
    """Unpaid proxy replay posture; None if inputs missing."""
    if not gold_path.exists() or not artifact_path.exists():
        return None
    cfg = load_config(models_path)
    artifact = load_scorer(artifact_path)
    if artifact is None:
        return None
    models = load_models(cfg)
    report = replay_report(gold_path, artifact, models, cfg)
    if cost_gold_path and cost_gold_path.exists():
        report["cost_slice"] = replay_report(cost_gold_path, artifact, models, cfg)
    report = apply_replay_gate(report)
    trained = report["policies"]["trained"]
    rules = report["policies"]["rules"]
    return {
        "gold_path": str(gold_path),
        "artifact_path": str(artifact_path),
        "n_prompts": int(report.get("n_prompts") or 0),
        "local_replay_gate_pass": bool(report.get("local_replay_gate_pass")),
        "production_parity": bool(report.get("production_parity")),
        "parity_blockers": list(report.get("parity_blockers") or parity_blockers(report)),
        "rank_auc": report.get("rank_auc"),
        "brier_skill": report.get("brier_skill"),
        "ece_equal_width": report.get("ece_equal_width"),
        "ece_equal_mass": report.get("ece_equal_mass"),
        "ece_equal_mass_gated": report.get("ece_equal_mass_gated"),
        "rules_success_rate": rules.get("success_rate"),
        "trained_success_rate": trained.get("success_rate"),
        "rules_cost_delta": report.get("rules_cost_delta"),
        "savings_vs_most_expensive": report.get("savings_vs_most_expensive"),
        "rules_ne_cheapest_rate": report.get("rules_ne_cheapest_rate"),
        "label_type": "gateway_success_gold_proxy",
        "session_gold": False,
    }


def cost_delta_passes(delta: float) -> bool:
    """Runbook §(a) cost bar: rules_cost_delta < 0."""
    return delta < 0.0


def quality_noninferior(trained_rate: float, rules_rate: float) -> bool:
    """Runbook §(a) quality bar: trained >= rules - QUALITY_TOLERANCE."""
    return trained_rate >= rules_rate - QUALITY_TOLERANCE


def _bar_status(
    bar_id: str,
    *,
    scaffold: dict[str, Any],
    local: dict[str, Any] | None,
    scaffold_errors: list[str],
    resolve_posture: dict[str, Any] | None = None,
    live_sessions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Map each runbook bar to done / blocked / proxy-only / not_started."""
    n_scaffold = int(scaffold.get("n") or 0)
    if bar_id == "floor_session_gold_n":
        posture = resolve_posture or {}
        live = live_sessions or {}
        n_live_gold = int(live.get("n_session_gold") or 0)
        remote_ready = bool(posture.get("remote_eval_ready"))
        floor_paths = posture.get("floor_paths") or {}
        local_farm = floor_paths.get("local_image_farm") or {}
        remote = floor_paths.get("remote_eval") or {}
        detail_bits = [
            f"live_session_gold={n_live_gold}/{VERIFIED_N_FLOOR}",
            (
                "local_image_farm="
                + (
                    "scale_ready"
                    if local_farm.get("scale_ready_on_this_host")
                    else str(local_farm.get("blocker") or "blocked")
                )
            ),
            (
                "remote_eval="
                + (
                    "scale_ready"
                    if remote.get("scale_ready_on_this_host")
                    else str(remote.get("blocker") or "blocked")
                )
            ),
        ]
        if scaffold_errors:
            return {
                "status": "blocked",
                "detail": "; ".join(scaffold_errors) + " | " + "; ".join(detail_bits),
                "floor_paths": {"local_image_farm": local_farm, "remote_eval": remote},
            }
        if n_live_gold >= VERIFIED_N_FLOOR:
            return {
                "status": "pass",
                "detail": "; ".join(detail_bits),
                "floor_paths": {"local_image_farm": local_farm, "remote_eval": remote},
            }
        if n_scaffold >= VERIFIED_PRIMARY_N and scaffold.get("session_gold") is False:
            status = (
                "scaffold_only_remote_ready"
                if remote_ready
                else "scaffold_only_remote_auth_pending"
            )
            return {
                "status": status,
                "detail": (
                    f"ids scaffold n={n_scaffold} meets primary split; "
                    "session_gold=false — need paid dual-policy + resolve "
                    f"({'Modal/sb-cli ready' if remote_ready else 'auth Modal/sb-cli first'}); "
                    + "; ".join(detail_bits)
                ),
                "floor_paths": {"local_image_farm": local_farm, "remote_eval": remote},
            }
        return {
            "status": "blocked",
            "detail": f"scaffold n={n_scaffold} < {VERIFIED_PRIMARY_N}; "
            + "; ".join(detail_bits),
            "floor_paths": {"local_image_farm": local_farm, "remote_eval": remote},
        }

    if bar_id in {"quality_session_gold", "quality_escalate"}:
        return {
            "status": "not_started",
            "detail": "requires live Verified session gold (tests_passed / patch resolve), not gateway proxy",
        }

    if bar_id == "cost_rules_delta":
        if local is None:
            return {"status": "not_started", "detail": "no local replay snapshot"}
        delta = float(local.get("rules_cost_delta") or 0.0)
        if cost_delta_passes(delta):
            return {
                "status": "proxy_pass",
                "detail": f"gateway proxy rules_cost_delta={delta:.6f} (not session gold)",
            }
        return {
            "status": "proxy_fail",
            "detail": f"ship serve gateway proxy rules_cost_delta={delta:.6f} (need < 0 at promotion scale)",
        }

    if bar_id == "calibration_bss":
        if local is None:
            return {"status": "not_started", "detail": "no local replay snapshot"}
        bss = float(local.get("brier_skill") or 0.0)
        return {
            "status": "proxy_pass" if bss_passes(bss) else "proxy_fail",
            "detail": f"gateway proxy BSS={bss:.6f} on n={local.get('n_prompts')} (not flywheel hops)",
        }

    if bar_id == "calibration_ece_width":
        if local is None:
            return {"status": "not_started", "detail": "no local replay snapshot"}
        ece = float(local.get("ece_equal_width") or 0.0)
        return {
            "status": "proxy_pass" if ece_passes(ece) else "proxy_fail",
            "detail": f"gateway proxy equal-width ECE={ece:.6f}",
        }

    if bar_id == "calibration_ece_mass":
        if local is None:
            return {"status": "not_started", "detail": "no local replay snapshot"}
        ece = float(local.get("ece_equal_mass") or 0.0)
        n_sel = int(local.get("n_prompts") or 0)
        gated = bool(local.get("ece_equal_mass_gated", ece_mass_is_gated(n_sel)))
        if not gated:
            return {
                "status": "waived_small_n",
                "detail": f"equal-mass ECE={ece:.3f} waived (n={n_sel} < {SMALL_N_ECE_MASS})",
            }
        return {
            "status": "proxy_pass" if ece_mass_passes(ece, n_selected=n_sel) else "proxy_fail",
            "detail": f"equal-mass ECE={ece:.6f} gated={gated}",
        }

    return {"status": "unknown", "detail": bar_id}


def build_gate_checklist(
    *,
    scaffold: dict[str, Any],
    scaffold_errors: list[str],
    local: dict[str, Any] | None = None,
    resolve_posture: dict[str, Any] | None = None,
    live_sessions: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Checklist surface for unpaid readiness (local-replay / scaffold adapters)."""
    rows: list[dict[str, Any]] = []
    for spec in PROMOTION_BARS:
        status = _bar_status(
            spec["id"],
            scaffold=scaffold,
            local=local,
            scaffold_errors=scaffold_errors,
            resolve_posture=resolve_posture,
            live_sessions=live_sessions,
        )
        rows.append({**spec, **status})
    return rows


def checklist_from_live_bars(bars: dict[str, Any]) -> list[dict[str, Any]]:
    """Adapt eval.promotion_gate_verdict['bars'] onto the PROMOTION_BARS checklist.

    Session-gold / shadow-log verdict consumers share this surface with unpaid
    readiness so bar ids and §(a) wording stay in one module.
    """
    rows: list[dict[str, Any]] = []
    for spec in PROMOTION_BARS:
        bar = bars.get(spec["id"]) or {}
        passed = bar.get("pass")
        if passed is True:
            status = "pass"
        elif passed is False:
            status = "fail"
        elif bar.get("waived_small_n"):
            status = "waived_small_n"
        else:
            status = "not_started"
        detail = bar.get("detail")
        if not detail:
            detail = _live_bar_detail(spec["id"], bar)
        row = {**spec, "status": status, "detail": detail}
        for key, val in bar.items():
            if key in {"pass", "detail"}:
                continue
            row[key] = val
        rows.append(row)
    return rows


def _live_bar_detail(bar_id: str, bar: dict[str, Any]) -> str:
    if bar_id == "calibration_bss":
        return f"BSS={bar.get('brier_skill')}"
    if bar_id == "calibration_ece_width":
        return f"equal-width ECE={bar.get('ece_equal_width')}"
    if bar_id == "calibration_ece_mass":
        return f"equal-mass ECE={bar.get('ece_equal_mass')}"
    if bar_id == "cost_rules_delta":
        return f"rules_cost_delta={bar.get('rules_cost_delta')}"
    if bar_id == "floor_session_gold_n":
        return f"n_sessions={bar.get('n_sessions')} floor={bar.get('floor')}"
    if bar_id == "quality_session_gold":
        return (
            f"trained={bar.get('trained_resolve_rate')} rules={bar.get('rules_resolve_rate')}"
        )
    if bar_id == "quality_escalate":
        return f"escalate_rate={bar.get('escalate_rate')}"
    return bar_id


def dual_policy_run_plan(
    *,
    scaffold_path: Path,
    artifact_path: Path,
    models_path: Path,
    gateway: str = "http://127.0.0.1:8000",
    remote_eval_ready: bool = False,
) -> list[dict[str, str]]:
    """Exact operator commands; paid steps require budget approval."""
    rel_scaffold = scaffold_path.as_posix()
    steps: list[dict[str, str]] = [
        {
            "phase": "unpaid",
            "step": "refresh_ids_scaffold",
            "command": (
                "python -m aiand_router.lite_runner --ids-only --bench verified "
                f"--n {VERIFIED_PRIMARY_N} --out {rel_scaffold}"
            ),
        },
        {
            "phase": "unpaid",
            "step": "promotion_readiness",
            "command": (
                "python -m aiand_router.promotion_gate "
                f"--scaffold {rel_scaffold} "
                f"--artifact {artifact_path.as_posix()} "
                f"--models {models_path.as_posix()} "
                "--gold data/gold-verified.jsonl"
            ),
        },
        {
            "phase": "unpaid",
            "step": "local_replay_proxy",
            "command": (
                "python -m aiand_router.replay_report "
                f"--gold data/gold-verified.jsonl --artifact {artifact_path.as_posix()} "
                f"--models {models_path.as_posix()}"
            ),
        },
        {
            "phase": "unpaid",
            "step": "bounded_dual_policy_fixture",
            "command": "python scripts/run_lite_comparison.py",
            "note": "harness-proxy only; verdict bounded_check_only",
        },
        {
            "phase": "unpaid",
            "step": "modal_auth_probe",
            "command": (
                "python scripts/swe_eval_cmd.py --backend modal "
                "--instance django__django-11099 --patch data/_gold_django_11099.patch"
            ),
            "note": (
                "Expect not_available/modal_not_configured until `modal token new`. "
                "No local docker pull."
            ),
        },
    ]
    if remote_eval_ready:
        steps.append(
            {
                "phase": "paid_disk_light",
                "step": "modal_gold_patch_smoke",
                "command": (
                    "$env:SWE_EVAL_BACKEND='modal'\n"
                    "python scripts/swe_eval_cmd.py --backend modal "
                    "--instance django__django-11099 --patch data/_gold_django_11099.patch"
                ),
                "note": "Remote resolve only; keep TRAINED_PATH=shadow; no mass local pulls",
            }
        )
    else:
        steps.append(
            {
                "phase": "human_auth",
                "step": "modal_token_new",
                "command": (
                    "pip install modal 'swebench[modal]'\n"
                    "modal token new\n"
                    "# then re-run modal_auth_probe"
                ),
                "note": "3-step auth: install → token new → unpaid gold-patch probe",
            }
        )
    steps.extend(
        [
            {
                "phase": "paid_requires_budget",
                "step": "start_gateway_shadow",
                "command": (
                    "# PowerShell:\n"
                    "$env:PYTHONPATH='src'\n"
                    "$env:TRAINED_PATH='shadow'\n"
                    "$env:SCORER_PATH='data/scorer-hard-logistic.json'\n"
                    "uvicorn aiand_router.app:app --app-dir src --host 127.0.0.1 --port 8000"
                ),
            },
            {
                "phase": "paid_requires_budget",
                "step": "verified_session_smoke",
                "command": (
                    "python -m aiand_router.verified_runner --limit 2 "
                    f"--scaffold {rel_scaffold} --gateway {gateway} "
                    "--out data/verified_session_smoke.jsonl"
                ),
                "note": (
                    "Prefer local images + git filectx for edit; set SWE_EVAL_BACKEND=modal "
                    "for resolve once auth'd"
                ),
            },
            {
                "phase": "paid_requires_budget",
                "step": "verified_session_gate",
                "command": (
                    "python -m aiand_router.verified_runner "
                    f"--scaffold {rel_scaffold} --gateway {gateway} "
                    f"--out data/verified_session_results.jsonl"
                ),
                "note": f"Primary split n={VERIFIED_PRIMARY_N}; remote_eval floor preferred on this host",
            },
            {
                "phase": "paid_requires_budget",
                "step": "gate_check_eval",
                "command": (
                    "python -m aiand_router.eval --gate --log data/requests.jsonl "
                    "--sessions data/verified_session_results.jsonl"
                ),
            },
            {
                "phase": "unpaid",
                "step": "verified_session_dry_run",
                "command": (
                    "python -m aiand_router.verified_runner --dry-run --limit 500 "
                    f"--scaffold {rel_scaffold}"
                ),
            },
        ]
    )
    return steps


def promotion_readiness(
    *,
    scaffold_path: Path,
    artifact_path: Path | None = None,
    models_path: Path | None = None,
    gold_path: Path | None = None,
    cost_gold_path: Path | None = None,
    gateway: str = "http://127.0.0.1:8000",
) -> dict[str, Any]:
    scaffold = load_ids_scaffold(scaffold_path)
    scaffold_errors = validate_ids_scaffold(scaffold)
    artifact_path = artifact_path or ROOT / "data" / "scorer-hard-logistic.json"
    models_path = models_path or ROOT / "config" / "models.yaml"
    gold_path = gold_path or ROOT / "data" / "gold-verified.jsonl"
    cost_gold_path = cost_gold_path or ROOT / "data" / "gold-cost-hard-bootstrap.jsonl"

    local = None
    if artifact_path.exists() and gold_path.exists():
        local = local_replay_snapshot(
            gold_path=gold_path,
            artifact_path=artifact_path,
            models_path=models_path,
            cost_gold_path=cost_gold_path if cost_gold_path.exists() else None,
        )

    cfg = load_config(models_path)
    models = load_models(cfg)
    budget = estimate_gate_budget(
        n_instances=int(scaffold.get("n") or VERIFIED_PRIMARY_N),
        models_cfg=models,
    )
    resolve_posture = resolve_backend_posture()
    live_sessions = count_session_gold_rows(LIVE_FILECTX_SESSIONS)
    joined = session_joined_cost_sample_summary()
    checklist = build_gate_checklist(
        scaffold=scaffold,
        scaffold_errors=scaffold_errors,
        local=local,
        resolve_posture=resolve_posture,
        live_sessions=live_sessions,
    )
    plan = dual_policy_run_plan(
        scaffold_path=scaffold_path,
        artifact_path=artifact_path,
        models_path=models_path,
        gateway=gateway,
        remote_eval_ready=bool(resolve_posture.get("remote_eval_ready")),
    )
    code_gaps = [
        "trained session-gold quality bar needs dual-policy session rows (keep TRAINED_PATH=shadow for demo)",
        "full n=500 Verified session gate prefers remote_eval (Modal/sb-cli); local_image_farm disk-blocked here",
        "prototype demo kit: .scratch/scorer-pioneer-lift/prototype-demo-2026-08-20.md",
    ]
    ready_for_paid = not scaffold_errors and local is not None
    return {
        "verdict": "promotion_readiness_unpaid",
        "session_gold": False,
        "production_parity": False,
        "prototype_ready": True,
        "promotion_gate_started": False,
        "scaffold_path": str(scaffold_path),
        "scaffold_valid": not scaffold_errors,
        "scaffold_errors": scaffold_errors,
        "scaffold_n": int(scaffold.get("n") or 0),
        "serve_candidate": str(artifact_path),
        "local_replay": local,
        "resolve_backend": resolve_posture,
        "live_filectx_sessions": live_sessions,
        "session_joined_cost_sample": joined,
        "gate_checklist": checklist,
        "budget_estimate": budget,
        "dual_policy_run_plan": plan,
        "code_gaps": code_gaps,
        "ready_for_paid_session_gate": ready_for_paid,
        "ready_for_remote_scale": bool(resolve_posture.get("remote_eval_ready")),
        "do_not_flip_trained_path": True,
    }


def format_promotion_report(report: dict[str, Any]) -> str:
    lines = [
        "# Verified session-gold promotion readiness (unpaid)",
        "",
        f"**Verdict:** `{report.get('verdict')}`",
        f"**Session gold:** `{report.get('session_gold')}` · "
        f"**Production parity:** `{report.get('production_parity')}`",
        f"**Scaffold:** `{report.get('scaffold_path')}` "
        f"(valid={report.get('scaffold_valid')}, n={report.get('scaffold_n')})",
        f"**Serve candidate (shadow):** `{report.get('serve_candidate')}`",
        "",
        "> Does **not** flip `TRAINED_PATH=trained`. Paid HTTP requires operator budget approval.",
        f"> Prototype-ready (demo bar): `{report.get('prototype_ready')}` · "
        f"Production parity: `{report.get('production_parity')}` · "
        f"Remote scale ready: `{report.get('ready_for_remote_scale')}`",
        "",
    ]
    if report.get("scaffold_errors"):
        lines.extend(["## Scaffold errors", ""])
        for err in report["scaffold_errors"]:
            lines.append(f"- {err}")
        lines.append("")

    resolve = report.get("resolve_backend") or {}
    if resolve:
        floors = resolve.get("floor_paths") or {}
        local_farm = floors.get("local_image_farm") or {}
        remote = floors.get("remote_eval") or {}
        modal = resolve.get("modal") or {}
        sb = resolve.get("sb_cli") or {}
        lines.extend(
            [
                "## Resolve floor paths (local_image_farm vs remote_eval)",
                "",
                f"- Preferred scale path: **`{resolve.get('preferred_scale_path')}`**",
                f"- `local_image_farm`: scale_ready={local_farm.get('scale_ready_on_this_host')} "
                f"({local_farm.get('blocker')})",
                f"- `remote_eval`: scale_ready={remote.get('scale_ready_on_this_host')} "
                f"({remote.get('blocker')}); adapter `{remote.get('adapter')}`",
                f"- Modal: configured={modal.get('configured')} "
                f"(toml={modal.get('toml_present')}, pkg={modal.get('package_installed')})",
                f"- sb-cli: configured={sb.get('configured')} "
                f"(cli={sb.get('cli_or_package')}, key={sb.get('api_key_set')})",
                f"- Disk-light doc: `{resolve.get('disk_light_doc')}`",
                "",
            ]
        )

    live = report.get("live_filectx_sessions") or {}
    if live:
        lines.extend(
            [
                "## Live filectx sessions (tiny-n canary)",
                "",
                f"- path: `{live.get('path')}`",
                f"- unique={live.get('n_unique')} · session_gold={live.get('n_session_gold')} "
                f"(floor {live.get('floor_n')}; below_floor={live.get('below_floor')})",
                "",
            ]
        )

    joined = report.get("session_joined_cost_sample")
    if joined:
        lines.extend(
            [
                "## Session-joined cost sample",
                "",
                f"- doc: `{joined.get('doc')}`",
                f"- session_joined={joined.get('session_joined')} · "
                f"n_joinable≈{joined.get('n_joinable_hops_sample')} · "
                f"joined rcd≈{joined.get('joined_rules_cost_delta_approx')}",
                f"- verdict `{joined.get('verdict')}` — {joined.get('note')}",
                "",
            ]
        )

    local = report.get("local_replay")
    if local:
        lines.extend(
            [
                "## Local replay proxy (not session gold)",
                "",
                f"- `local_replay_gate_pass`: **{local.get('local_replay_gate_pass')}**",
                f"- n={local.get('n_prompts')} gateway success-gold proxy",
                f"- trained success: {local.get('trained_success_rate')}",
                f"- rules success: {local.get('rules_success_rate')}",
                f"- rules_cost_delta: {local.get('rules_cost_delta')}",
                f"- savings_vs_most_expensive: {local.get('savings_vs_most_expensive')}",
                f"- parity_blockers: `{', '.join(local.get('parity_blockers') or [])}`",
                "",
            ]
        )

    lines.extend(["## Runbook §(a) gate checklist", ""])
    for row in report.get("gate_checklist") or []:
        lines.append(
            f"- **{row['id']}** — `{row['status']}`: {row['bar']} — {row.get('detail', '')}"
        )
    lines.append("")

    budget = report.get("budget_estimate") or {}
    lines.extend(
        [
            "## Budget estimate (list-price)",
            "",
            f"- n_instances: {budget.get('n_instances')}",
            f"- enabled models: {budget.get('n_enabled_models')}",
            f"- shadow dual-policy session gate (est.): **${budget.get('shadow_dual_policy_session_gate_est_usd')}**",
            f"- dense all-models upper bound (est.): ${budget.get('dense_all_models_per_instance_est_usd')}",
            f"- {budget.get('note', '')}",
            "",
        ]
    )

    lines.extend(["## Dual-policy run plan", ""])
    for step in report.get("dual_policy_run_plan") or []:
        note = step.get("note")
        lines.append(f"### {step['phase']} · {step['step']}")
        lines.append("")
        lines.append("```powershell")
        lines.append(f"$env:PYTHONPATH='src'")
        cmd = step["command"]
        if cmd.startswith("#"):
            lines.append(cmd)
        else:
            lines.append(cmd)
        lines.append("```")
        if note:
            lines.append(f"- {note}")
        lines.append("")

    if report.get("code_gaps"):
        lines.extend(["## Code / plumbing gaps", ""])
        for gap in report["code_gaps"]:
            lines.append(f"- {gap}")
        lines.append("")

    lines.append(
        f"**Ready for paid session gate (scaffold + local replay only):** "
        f"`{report.get('ready_for_paid_session_gate')}`"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Unpaid Verified promotion gate readiness (runbook §(a))"
    )
    parser.add_argument(
        "--scaffold",
        default=str(ROOT / "data" / "verified_ids_scaffold.json"),
        help="Verified ids scaffold JSON (session_gold=false)",
    )
    parser.add_argument(
        "--artifact",
        default=str(ROOT / "data" / "scorer-hard-logistic.json"),
        help="Shadow serve candidate scorer artifact",
    )
    parser.add_argument("--models", default=str(ROOT / "config" / "models.yaml"))
    parser.add_argument("--gold", default=str(ROOT / "data" / "gold-verified.jsonl"))
    parser.add_argument(
        "--cost-gold",
        default=str(ROOT / "data" / "gold-cost-hard-bootstrap.jsonl"),
    )
    parser.add_argument("--gateway", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--report",
        default=None,
        help="Optional path to write markdown report",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON summary to stdout")
    args = parser.parse_args(argv)

    report = promotion_readiness(
        scaffold_path=Path(args.scaffold),
        artifact_path=Path(args.artifact),
        models_path=Path(args.models),
        gold_path=Path(args.gold),
        cost_gold_path=Path(args.cost_gold),
        gateway=args.gateway,
    )
    md = format_promotion_report(report)
    if args.report:
        out = Path(args.report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        print(f"wrote report {out}", flush=True)
    if args.json:
        # checklist/plan only in JSON; omit huge per_model list for brevity
        slim = dict(report)
        budget = dict(slim.get("budget_estimate") or {})
        budget.pop("per_model_completion_est", None)
        slim["budget_estimate"] = budget
        print(json.dumps(slim, indent=2))
    else:
        print(md)
    return 0 if report.get("scaffold_valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
