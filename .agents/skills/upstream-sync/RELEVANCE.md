# Upstream relevance rules (aiand-router fork)

Default: **skip** upstream commits unless they clearly improve shared core code this fork still uses.

## Always skip (whole commit if primary intent)

| Area | Why |
|------|-----|
| `install/npm/`, `npx @workweave/router`, Codex/opencode/pi installers | Hosted aiand product; not Weave CLI |
| Self-host / `make full-setup` / `docker-compose` BYOK flows | Hosted-only deploy |
| Multi-provider registration in `cmd/router/main.go` | aiand-only `providerMap` |
| OpenRouter / Anthropic / Gemini / native provider adapters (new or expanded) | Not deployed; translation fixtures may remain |
| `rk_` key issuance / selfhosted dashboard auth | aiand `sk-` identity probe |
| Weave / WorkWeave branding, URLs, `x-weave-*` renames we intentionally diverged on | Product identity (`x-aiand-*` here) |
| Claude catalog rows, Appendix-F remaps, Claude-era model tables | Catalog is open-weight + aiand bindings |
| Managed vs selfhosted mode switches | Single hosted mode |
| `.conductor/`, upstream-only CI/deploy to Weave infra | Not our pipeline |
| Customer-specific fixes naming orgs/tickets | Public repo hygiene |

## Usually apply (when commit touches these)

| Area | Notes |
|------|-------|
| `internal/proxy/` | Routing, dispatch, cache, failover — adapt provider names |
| `internal/translate/` | Wire-format fixes benefit all ingress |
| `internal/router/cluster/` | Scorer, embedder, artifacts (retrain separately if needed) |
| `internal/router/{planner,handover,cache,sessionpin,turntype,banditexplore}/` | Pure inner-ring logic |
| `internal/providers/httputil/` | Shared transport/timeouts |
| `internal/sse/`, `internal/timing/` | Pure helpers |
| `internal/observability/` | Logging/OTel (not Weave-dashboard-specific) |
| `internal/auth/` | Only if compatible with aiand sk- login (ignore rk_/selfhosted paths) |
| `internal/api/` | Dashboard/data plane — strip selfhosted-only routes |
| `frontend/` | UI shared with hosted dashboard |
| `smoke/` | If scenario still valid for aiand-only path |
| Security / DoS / timeout / panic fixes in core packages | Port even if commit message is vague |

## Partial apply — inspect hunk-by-hunk

| Area | Rule |
|------|------|
| `internal/router/catalog/catalog.go` | Port pricing/capability math; do not re-add Claude rows or non-aiand bindings |
| `cmd/router/main.go` | Port wiring patterns, not extra providers |
| `db/migrations/` | Port only if schema matches our hosted model |
| `docs/` | Port technical accuracy; rewrite product/deployment story for aiand |
| `AGENTS.md` / `CLAUDE.md` | Merge engineering rules; keep aiand deploy identity paragraph |
| `.github/workflows/` | Port test/lint patterns, not Weave deploy jobs |

## Path existence check

Before porting, confirm the file exists locally:

```bash
test -f path/to/file && echo exists || echo "gone — skip or manual port"
```

Deleted in our fork → skip unless the bug class clearly applies elsewhere.

## Commit message signals

| Signal | Action |
|--------|--------|
| `fix(proxy`, `fix(translate`, `fix(cluster` | Likely apply |
| `selfhosted`, `managed mode`, `OpenRouter`, `install/` | Likely skip |
| `rename weave →` | Skip unless pure refactor in shared inner ring |
| `customer`, org name, Linear private link | Skip verbatim; reimplement generically if needed |

## Git and PR hygiene (when porting)

- Work on branch `sync/<topic>`; one git commit per ported logical change.
- Commit/PR text: describe the **behavior fix** only. Never mention upstream, workweave, cherry-pick, or foreign PR numbers.
- Skipped commits: omit from PR body entirely (no "ignored commits" list).
- Schema ports: always `make migrate-up` against Supabase after adding migrations; see SKILL.md § Database / Supabase.
