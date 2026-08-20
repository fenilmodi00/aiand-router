# Local sweb.eval inventory (2026-08-20)

**HARD: do not `docker pull` any more images.** Disk space limited.

Local eval images: **12**. Mapped Verified ids: **12**.
Unused path-ready: **0** (every local image has a filectx session row).

## Images → instance_id

| image | instance_id | session_gold |
| --- | --- | --- |
| `swebench/sweb.eval.x86_64.django_1776_django-10880:latest` | `django__django-10880` | true |
| `swebench/sweb.eval.x86_64.django_1776_django-10914:latest` | `django__django-10914` | **true** |
| `swebench/sweb.eval.x86_64.django_1776_django-11066:latest` | `django__django-11066` | true |
| `swebench/sweb.eval.x86_64.django_1776_django-11099:latest` | `django__django-11099` | true |
| `swebench/sweb.eval.x86_64.django_1776_django-11532:latest` | `django__django-11532` | **true** |
| `swebench/sweb.eval.x86_64.django_1776_django-11880:latest` | `django__django-11880` | true |
| `swebench/sweb.eval.x86_64.django_1776_django-12754:latest` | `django__django-12754` | false |
| `swebench/sweb.eval.x86_64.django_1776_django-13512:latest` | `django__django-13512` | false |
| `swebench/sweb.eval.x86_64.django_1776_django-13786:latest` | `django__django-13786` | true |
| `swebench/sweb.eval.x86_64.django_1776_django-14011:latest` | `django__django-14011` | true |
| `swebench/sweb.eval.x86_64.django_1776_django-14140:latest` | `django__django-14140` | true |
| `swebench/sweb.eval.x86_64.django_1776_django-15252:latest` | `django__django-15252` | true |

Cumulative unique `session_gold`: **10 / 12** (batch6 miss retest).

Still unresolved: **12754, 13512** (repeat apply/malformed after harden + debug harness feedback).

## Exhaustion

Local-12 is **largely exhausted for useful paid retries** without new unpaid patch/path work or new images. Serve: `data/scorer-hard-logistic.json`, `TRAINED_PATH=shadow` only.

```powershell
$env:PYTHONPATH='src'; $env:PYTHONUTF8='1'
# see verified-filectx-batch6-2026-08-20.md
```
