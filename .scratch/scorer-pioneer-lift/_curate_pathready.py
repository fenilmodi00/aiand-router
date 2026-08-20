"""Unpaid: curate Verified ids with non-empty guess_target_paths + local/pullable images."""
from __future__ import annotations

import json
import re
from pathlib import Path

from aiand_router.docker_file_context import docker_image_present, swebench_eval_image
from aiand_router.lite_runner import guess_target_paths

ROOT = Path(__file__).resolve().parents[2]
DUMP = ROOT / "data" / "dump_cache" / "swe_verified.jsonl"
OUT = ROOT / "data" / "verified_ids_filectx_pathready.jsonl"
META = ROOT / "data" / "verified_ids_filectx_pathready.json"

# Already paid in batch1 — keep for local pathready set but deprioritize for new pulls.
PRIOR = {
    "django__django-11099",
    "django__django-10880",
    "django__django-10914",
    "django__django-11066",
}

_BAD_PATH = re.compile(
    r"(^|/)"
    r"(?:manage\.py|settings/py\.py|models/py\.py|self/|Field/|View/|Engine/|"
    r"Query/|Axes/|FigureCanvasBase/|OffsetBox/|MigrationAutodetector/|"
    r"ProductMetaData/|custom_lookups/|RelatedFieldListFilter\.py)"
    r"|^(?:a|b)/"
    r"|site-packages/"
    r"|/\.venv/"
    r"|\.css(?:\.|$)"
    r"|/css/"
)


def plausible(paths: list[str], repo: str | None) -> list[str]:
    top = (repo or "").strip().split("/")[-1].lower() if repo else ""
    good: list[str] = []
    for p in paths:
        p = p.replace("\\", "/").lstrip("./")
        if not p.endswith(".py"):
            continue
        if p.endswith("/py.py") or p.endswith(".py.py"):
            continue
        if _BAD_PATH.search(p):
            continue
        if p.count("/") < 1:
            continue
        # Strip accidental diff prefixes if both a/ and clean form appear later.
        if p.startswith(("a/", "b/")):
            continue
        if top and not (
            p.startswith(f"{top}/")
            or p.startswith("tests/")
            or p.startswith("src/")
            or p.startswith("lib/")
        ):
            if not re.match(rf"^({re.escape(top)}|tests|src|lib)/", p):
                continue
        # CamelCase directory segments (class.method false positives), keep known pkgs.
        parts = p.split("/")
        if any(re.match(r"^[A-Z][A-Za-z0-9]+$", seg) for seg in parts[:-1]):
            continue
        good.append(p)
    return good


def score(paths: list[str], local: bool, iid: str, repo: str | None) -> tuple:
    django = 1 if str(repo or "").startswith("django/") else 0
    rooted = sum(1 for p in paths if p.startswith("django/") or p.startswith("tests/"))
    return (
        1 if local else 0,
        django,
        rooted,
        0 if iid in PRIOR else 1,
        len(paths),
    )


def main() -> None:
    rows = []
    with DUMP.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            iid = str(row.get("instance_id") or "")
            if not iid:
                continue
            raw = guess_target_paths(row)
            if not raw:
                continue
            repo = row.get("repo")
            paths = plausible(raw, str(repo) if repo else None)
            if not paths:
                continue
            img = swebench_eval_image(iid)
            local = docker_image_present(img)
            rows.append(
                {
                    "instance_id": iid,
                    "paths": paths,
                    "raw_paths": raw,
                    "local": local,
                    "repo": repo,
                    "image": img,
                }
            )

    rows.sort(
        key=lambda r: score(r["paths"], r["local"], r["instance_id"], r.get("repo")),
        reverse=True,
    )
    local_rows = [r for r in rows if r["local"]]
    remote_rows = [r for r in rows if not r["local"]]

    # Prefer all local pathready, then up to 2 pull candidates (django first for image size familiarity).
    pull_budget = 2
    django_remote = [r for r in remote_rows if str(r.get("repo") or "").startswith("django/")]
    other_remote = [r for r in remote_rows if r not in django_remote]
    pull_candidates = (django_remote + other_remote)[:pull_budget]

    selected = local_rows + pull_candidates
    # Cap curated list reasonably for the runner; paid limit applied separately.
    selected = selected[:12]
    # Paid batch order: new pulls first, then local not-yet-filectx-success, then prior success.
    def batch_order(r: dict) -> tuple:
        iid = r["instance_id"]
        if not r["local"]:
            return (0, iid)
        if iid == "django__django-11066":
            return (1, iid)  # newly pathready via blob fix; local image
        if iid == "django__django-11099":
            return (3, iid)  # already session_gold with docker_cp
        return (2, iid)

    selected.sort(key=batch_order)

    OUT.write_text(
        "".join(json.dumps({"instance_id": r["instance_id"]}, ensure_ascii=False) + "\n" for r in selected),
        encoding="utf-8",
    )
    META.write_text(
        json.dumps(
            {
                "n": len(selected),
                "n_local": len(local_rows),
                "n_pull_candidates": len(pull_candidates),
                "pull_budget": pull_budget,
                "pathready_plausible_total": len(rows),
                "instance_ids": [r["instance_id"] for r in selected],
                "details": [
                    {
                        "instance_id": r["instance_id"],
                        "local": r["local"],
                        "paths": r["paths"][:4],
                        "repo": r["repo"],
                    }
                    for r in selected
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"pathready_plausible={len(rows)} local={len(local_rows)} selected={len(selected)}")
    for r in selected:
        print(
            f"  {'LOCAL' if r['local'] else 'PULL '} {r['instance_id']} -> {r['paths'][:2]}"
        )
    print(f"wrote {OUT}")
    print(f"wrote {META}")


if __name__ == "__main__":
    main()
