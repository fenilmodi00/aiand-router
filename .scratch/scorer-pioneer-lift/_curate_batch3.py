"""Unpaid: curate up to 8 path-ready Verified ids for filectx batch3.

Excludes already-run batch1/2 ids. Prefer local eval images; allow ≤3 pulls.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from aiand_router.docker_file_context import docker_image_present, swebench_eval_image
from aiand_router.lite_runner import guess_target_paths

ROOT = Path(__file__).resolve().parents[2]
DUMP = ROOT / "data" / "dump_cache" / "swe_verified.jsonl"
OUT = ROOT / "data" / "verified_ids_filectx_batch3.jsonl"
META = ROOT / "data" / "verified_ids_filectx_batch3.json"

EXCLUDE = {
    "django__django-11099",
    "django__django-10880",
    "django__django-10914",
    "django__django-11066",
    "django__django-12754",
    "django__django-15252",
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

PULL_BUDGET = 3
LIMIT = 8


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
        if p.startswith(("a/", "b/")):
            continue
        if top and not (
            p.startswith(f"{top}/")
            or p.startswith("tests/")
            or p.startswith("src/")
            or p.startswith("lib/")
        ):
            continue
        parts = p.split("/")
        if any(re.match(r"^[A-Z][A-Za-z0-9]+$", seg) for seg in parts[:-1]):
            continue
        good.append(p)
    return good


def score(r: dict) -> tuple:
    django = 1 if str(r.get("repo") or "").startswith("django/") else 0
    rooted = sum(1 for p in r["paths"] if p.startswith("django/") or p.startswith("tests/"))
    return (django, rooted, len(r["paths"]))


def main() -> None:
    rows: list[dict] = []
    with DUMP.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            iid = str(row.get("instance_id") or "")
            if not iid or iid in EXCLUDE:
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
                    "local": local,
                    "repo": repo,
                    "image": img,
                }
            )

    local_rows = [r for r in rows if r["local"]]
    remote_rows = [r for r in rows if not r["local"]]
    local_rows.sort(key=score, reverse=True)
    django_remote = [r for r in remote_rows if str(r.get("repo") or "").startswith("django/")]
    other_remote = [r for r in remote_rows if r not in django_remote]
    django_remote.sort(key=score, reverse=True)
    other_remote.sort(key=score, reverse=True)

    selected_local = local_rows[:LIMIT]
    need = LIMIT - len(selected_local)
    pulls: list[dict] = []
    if need > 0:
        pulls = (django_remote + other_remote)[: min(PULL_BUDGET, need)]
    selected = pulls + selected_local  # pulls first so --limit 5 hits new images

    OUT.write_text(
        "".join(
            json.dumps({"instance_id": r["instance_id"]}, ensure_ascii=False) + "\n"
            for r in selected
        ),
        encoding="utf-8",
    )
    META.write_text(
        json.dumps(
            {
                "n": len(selected),
                "n_local": sum(1 for r in selected if r["local"]),
                "n_pull": sum(1 for r in selected if not r["local"]),
                "pull_budget": PULL_BUDGET,
                "exclude": sorted(EXCLUDE),
                "pathready_plausible_remaining": len(rows),
                "local_available": len(local_rows),
                "instance_ids": [r["instance_id"] for r in selected],
                "details": [
                    {
                        "instance_id": r["instance_id"],
                        "local": r["local"],
                        "paths": r["paths"][:4],
                        "repo": r["repo"],
                        "image": r["image"],
                    }
                    for r in selected
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"remaining_pathready={len(rows)} local_avail={len(local_rows)} "
        f"selected={len(selected)} n_pull={len(pulls)}"
    )
    for r in selected:
        tag = "LOCAL" if r["local"] else "PULL "
        print(f"  {tag} {r['instance_id']} -> {r['paths'][:2]}")
    print(f"wrote {OUT}")
    print(f"wrote {META}")


if __name__ == "__main__":
    main()
