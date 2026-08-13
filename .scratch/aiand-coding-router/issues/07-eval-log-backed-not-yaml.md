# 07 — Eval is log-backed, not YAML-probed

**What to build:** A judge (or the eval command) can trust the comparison report: costs, models, stubbed baselines, and resolution come from the request log. Tests assert those observables, not the shape of the task spec file. `resolved` is not “HTTP 200”; empty response, escalation, or an explicit fail counts as unresolved. No invented savings percentage.

**Blocked by:** None — can start immediately.

**Status:** resolved

- [x] Eval test no longer asserts task-spec YAML keys or list lengths as a substitute for behaviour
- [x] Report still shows three executed baselines (premium, Kimi-only, adaptive) plus stubbed names, from the log
- [x] `resolved` is not counted from HTTP 200 alone; empty / escalate / explicit fail is unresolved
- [x] Report still has no invented savings `%`; quality note still distinguishes AA priors from measured log numbers
