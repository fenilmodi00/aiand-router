from pathlib import Path

n5_block = """

---

## Scaled filectx dual-policy (n=4 of target 5) — 2026-08-20

**Serve candidate unchanged:** `data/scorer-hard-logistic.json` + `config/models.yaml`. Gateway override `TRAINED_PATH=shadow` (do not flip `.env` to trained).

### Instances / images

| instance_id | image | local vs pulled | size |
| --- | --- | --- | --- |
| django__django-11099 | swebench/sweb.eval.x86_64.django_1776_django-11099:latest | already local | 4.19GB |
| django__django-10880 | ...django-10880:latest | **pulled** | 4.18GB (~1.15GB content) |
| django__django-10914 | ...django-10914:latest | **pulled** | 4.19GB |
| django__django-11066 | ...django-11066:latest | **pulled** | 4.18GB |

Pull cap **3** additional images → max **4** instances with local eval images (not 5). Fifth candidate `django__django-11087` not pulled.

Ids: `data/verified_ids_filectx_n5.jsonl` (4 rows). Artifact: `data/verified_session_filectx_n5.jsonl`.

### Metrics

| metric | value |
| --- | --- |
| n_sessions | 4 |
| session_gold | **2/4 (0.50)** — 11099, 10880 |
| rules resolved | 2 true / 0 false / 2 null (needs_swe_eval) |
| trained resolved | 2 true / 0 false / 2 null |
| file_context_source | 11099=docker_cp; others=unavailable (no guessable target paths) |
| spend | 15.653121 → 15.662449 (**+$0.009328**) |
| eval --gate | bounded_check_only; session_gold=true; n_unlabeled_sessions=2; floor n>=300 fail; cost_rules_delta fail (+3.39e-05); BSS/ECE_w fail; ECE_mass waived_small_n |
| production_parity | false; do_not_flip_trained_path |

Labeled subset quality bar: rules/trained resolve rate **1.0** on the 2 session_gold rows (gate quality_session_gold pass).

### Notes

- Mid-run abort after 10914; resumed 11066 alone then merged.
- 10914/11066: SWE_EVAL attempted but unlabeled — honest needs_swe_eval.
- No gold patch injection. No n=300/500 this turn.
"""

handoff_block = """

## Verified filectx scale n=4 (2026-08-20 evening)

- Artifact: `data/verified_session_filectx_n5.jsonl` (n=4; pull-cap limited vs target 5).
- Instances: django__django-11099 (local), 10880/10914/11066 (**pulled**, ~4.18-4.19GB each).
- **session_gold 2/4**; rules+trained both resolved on gold rows; 2x needs_swe_eval.
- Spend delta **+$0.009328** (15.653121 → 15.662449).
- Gate: `bounded_check_only` (n=4 << 300). Serve candidate **unchanged**; keep TRAINED_PATH=shadow for gateway.
- Blockers: floor n; rules_cost_delta>0; BSS/ECE; file_ctx only when paths guessable; do not scale to n=300 this turn without budget/operator plan.
- Next (exact): shadow gateway + SWE_EVAL_CMD + --ids of more local-image django ids (pull <=2-3) then eval --gate on the sessions file.
"""

audit_block = """

## Verified filectx n=4 scale (2026-08-20)

| Item | Status |
| --- | --- |
| Serve candidate | **Unchanged** data/scorer-hard-logistic.json |
| Docker images | 1 prior + 3 pulled (cap); n=4 sessions |
| session_gold rate | **2/4 = 0.50** |
| Resolve (rules/trained) | 2/2 on labeled; 2 unlabeled needs_swe_eval |
| Spend delta | +$0.009328 |
| eval --gate | bounded_check_only |
| TRAINED_PATH flip | **No** |
| Goal complete? | **No** — n<<300; parity blockers remain |

"""

progress_line = """
- **Verified filectx scale n=4 (2026-08-20):** ids prefer local images; pulled 3 django eval images (~4.18-4.19GB). Out data/verified_session_filectx_n5.jsonl. session_gold **2/4**; spend 15.653121→15.662449 (+$0.009328). Gate bounded_check_only. Serve candidate unchanged. Do **not** run n=300/500 this turn.
"""

updates = {
  Path(".scratch/scorer-pioneer-lift/docker-swe-eval-status-2026-08-20.md"): n5_block,
  Path(".scratch/scorer-pioneer-lift/operator-handoff-2026-08-20.md"): handoff_block,
  Path(".scratch/scorer-pioneer-lift/completion-audit-2026-08-20.md"): audit_block,
  Path(".scratch/scorer-pioneer-lift/progress.md"): progress_line,
}
for path, block in updates.items():
  text = path.read_text(encoding="utf-8")
  marker = "filectx scale n=4" if "progress" in path.name or "handoff" in path.name or "audit" in path.name else "Scaled filectx dual-policy"
  if "Scaled filectx dual-policy" in text or "Verified filectx scale n=4" in text or "Verified filectx n=4 scale" in text:
    print("skip already", path)
    continue
  path.write_text(text.rstrip() + "\n" + block.lstrip("\n"), encoding="utf-8")
  print("updated", path)
