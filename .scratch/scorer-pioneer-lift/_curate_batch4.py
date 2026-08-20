"""Unpaid: curate path-ready Verified ids from LOCAL eval images only.

HARD CONSTRAINT (2026-08-20): do NOT docker pull. Disk full.
Only select instance_ids whose swebench/sweb.eval image is already present.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from aiand_router.docker_file_context import docker_image_present, swebench_eval_image
from aiand_router.lite_runner import guess_target_paths

ROOT = Path(__file__).resolve().parents[2]
DUMP = ROOT / "data" / "dump_cache" / "swe_verified.jsonl"
OUT = ROOT / "data" / "verified_ids_filectx_batch4.jsonl"
META = ROOT / "data" / "verified_ids_filectx_batch4.json"
INV = ROOT / ".scratch" / "scorer-pioneer-lift" / "local-sweb-eval-inventory-2026-08-20.md"

# Already have filectx session rows (do not re-spend unless operator asks).
EXCLUDE = {
    "django__django-11099",
    "django__django-10880",
    "django__django-10914",
    "django__django-11066",
    "django__django-12754",
    "django__django-15252",
    "django__django-14140",
    "django__django-11532",
    "django__django-11880",
    "django__django-13512",
    "django__django-13786",
    "django__django-14011",
}

PULL_BUDGET = 0  # hard: never pull
LIMIT = 5

_IMG_RE = re.compile(
    r"swebench/sweb\.eval\.x86_64\.(?P<key>.+):latest",
    re.IGNORECASE,
)


def image_to_instance_id(image: str) -> str | None:
    """swebench/sweb.eval.x86_64.django_1776_django-11099:latest → django__django-11099"""
    m = _IMG_RE.search(image.strip())
    if not m:
        return None
    key = m.group("key")
    if "_1776_" not in key:
        return None
    left, right = key.split("_1776_", 1)
    return f"{left}__{right}"


def list_local_eval_images() -> list[str]:
    import subprocess

    proc = subprocess.run(
        [
            "docker",
            "images",
            "swebench/sweb.eval*",
            "--format",
            "{{.Repository}}:{{.Tag}}",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    if proc.returncode != 0:
        return []
    return [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]


def score(r: dict) -> tuple:
    django = 1 if str(r.get("repo") or "").startswith("django/") else 0
    rooted = sum(1 for p in r["paths"] if p.startswith("django/") or p.startswith("tests/"))
    return (django, rooted, len(r["paths"]))


def main() -> None:
    local_images = list_local_eval_images()
    local_ids: dict[str, str] = {}
    for img in local_images:
        iid = image_to_instance_id(img)
        if iid:
            local_ids[iid] = img

    rows: list[dict] = []
    with DUMP.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            iid = str(row.get("instance_id") or "")
            if not iid or iid in EXCLUDE:
                continue
            if iid not in local_ids:
                continue
            img = local_ids[iid]
            if not docker_image_present(img):
                continue
            paths = guess_target_paths(row, limit=8)
            if not paths:
                continue
            rows.append(
                {
                    "instance_id": iid,
                    "paths": paths,
                    "local": True,
                    "repo": row.get("repo"),
                    "image": img,
                }
            )

    rows.sort(key=score, reverse=True)
    selected = rows[:LIMIT]

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
                "n_local": len(selected),
                "n_pull": 0,
                "pull_budget": PULL_BUDGET,
                "no_docker_pull": True,
                "exclude": sorted(EXCLUDE),
                "local_eval_images": sorted(local_images),
                "local_instance_ids": sorted(local_ids),
                "local_unused_pathready": len(rows),
                "instance_ids": [r["instance_id"] for r in selected],
                "details": [
                    {
                        "instance_id": r["instance_id"],
                        "local": True,
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

    inv_lines = [
        "# Local sweb.eval inventory (2026-08-20)",
        "",
        "**HARD: do not `docker pull` any more images.** Disk space limited.",
        "",
        f"Local eval images: **{len(local_images)}**.",
        f"Mapped Verified ids: **{len(local_ids)}**.",
        f"Unused path-ready (excl already-run): **{len(rows)}** → selected **{len(selected)}**.",
        "",
        "## Images → instance_id",
        "",
        "| image | instance_id | already-run |",
        "| --- | --- | --- |",
    ]
    for iid in sorted(local_ids):
        ran = "yes" if iid in EXCLUDE else "no (eligible)"
        inv_lines.append(f"| `{local_ids[iid]}` | `{iid}` | {ran} |")
    inv_lines.extend(
        [
            "",
            "## Selected for batch4 (local-only, no pull)",
            "",
        ]
    )
    for r in selected:
        inv_lines.append(f"- `{r['instance_id']}` → {r['paths'][:2]}")
    if not selected:
        inv_lines.append("- *(none — all local ids already have filectx session rows)*")
    inv_lines.extend(
        [
            "",
            "## Next without downloads",
            "",
            "- Paid: only the selected local-unused ids above (or re-run local misses).",
            "- Unpaid: path ranking / apply-reason logging already in tree; optional prune",
            "  reclaim of unused images only if operator explicitly frees disk.",
            "- Serve: `data/scorer-hard-logistic.json`, `TRAINED_PATH=shadow` only.",
            "",
        ]
    )
    INV.write_text("\n".join(inv_lines), encoding="utf-8")

    print(
        f"local_images={len(local_images)} mapped={len(local_ids)} "
        f"unused_pathready={len(rows)} selected={len(selected)} n_pull=0"
    )
    for r in selected:
        print(f"  LOCAL {r['instance_id']} -> {r['paths'][:2]}")
    print(f"wrote {OUT}")
    print(f"wrote {META}")
    print(f"wrote {INV}")


if __name__ == "__main__":
    main()
