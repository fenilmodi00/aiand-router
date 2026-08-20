from __future__ import annotations
import json
from pathlib import Path
import sys
sys.path.insert(0, "src")
from aiand_router.lite_runner import guess_target_paths

want = {
    "django__django-12754",
    "django__django-15252",
    "django__django-11066",
    "django__django-11099",
}
found = {}
with open("data/dump_cache/swe_verified.jsonl", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        iid = r.get("instance_id")
        if iid in want:
            found[iid] = r

for iid in sorted(found):
    r = found[iid]
    patch = r.get("patch") or ""
    files = []
    for ln in patch.splitlines():
        if ln.startswith("diff --git "):
            parts = ln.split()
            if len(parts) >= 4:
                p = parts[3]
                files.append(p[2:] if p.startswith("b/") else p)
    files = sorted(set(files))
    guessed = guess_target_paths(r) or []
    f2p = r.get("FAIL_TO_PASS") or r.get("fail_to_pass")
    print("=" * 60)
    print(iid)
    print("gold_files", files)
    print("guessed", guessed[:8])
    print("FAIL_TO_PASS", f2p)
    gset = set(guessed)
    print("guess_covers_any_gold", bool(gset & set(files)))
    print("gold_only", sorted(set(files) - gset))
    print("guess_extra", sorted(gset - set(files))[:6])
