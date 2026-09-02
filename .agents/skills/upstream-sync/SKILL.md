---
name: upstream-sync
description: Fetches incremental commits from workweave/router upstream into a temp clone, triages them for aiand-only fork relevance, ports applicable changes on a new git branch (one commit per change for manual PR review), applies Supabase migrations when schema changes, and never mentions upstream in commit or PR text. Use when syncing upstream or asking what changed since last sync.
---

# Upstream Sync (workweave/router → aiand-router)

Port **relevant** upstream fixes/features from [workweave/router](https://github.com/workweave/router) without re-introducing multi-provider, self-host, or Weave-branded product surface this fork removed.

## State file (internal only)

[`last-upstream-commit.txt`](last-upstream-commit.txt) stores the last upstream commit **fully reviewed** (applied or explicitly skipped). One full SHA per file; `#` lines are comments.

- Empty SHA → script lists recent upstream commits; set a baseline before first real sync.
- After a sync session → update to upstream `main` HEAD (or last reviewed commit if stopping mid-queue).
- **Never** copy this SHA or the word "upstream" into git commits, PR titles, or PR bodies — agent bookkeeping only.

## Branch, commit, and PR rules (mandatory)

All ported work lands on a **new branch** so the user can open a PR and review manually. **Never** commit directly on `main`.

### Branch

Before porting the first change in a session:

```bash
git checkout main && git pull
git checkout -b sync/<short-kebab-topic>   # e.g. sync/force-model-session-pin
```

One branch per sync session is fine; use a second branch only when changes are unrelated and should be separate PRs.

### Commits — one per ported logical change

For each **apply** or **partial** commit in the triage queue:

1. Port the files for that change only.
2. Stage and commit with a **standalone message** derived from the upstream subject (what the fix does in *our* repo), not where it came from.
3. Repeat for the next ported change (same branch unless splitting PRs).

**Commit message format** — mirror upstream intent, strip attribution:

```
fix(proxy): write session-wide pin so sub-agents inherit forced model
```

**Forbidden in commit messages and PR text** (hard rule):

- "upstream", "workweave", "cherry-pick", "ported from", "sync from", upstream SHAs, PR numbers from the other repo (`#741`, `#1144`), "fork", "fetched changes"
- Lists of skipped upstream commits
- Any note that changes were imported from another repository

PR title/body describe **what changed and why for aiand-router** only — same hygiene as commits. Test plan is fine; provenance is not.

### Push and PR

- Do **not** push or open a PR unless the user asks.
- When they do: one PR per branch; user reviews before merge.

## Quick workflow (~2 min fetch + triage)

```
Task Progress:
- [ ] 0. Create sync branch (never commit on main)
- [ ] 1. Fetch upstream
- [ ] 2. List new commits
- [ ] 3. Triage each commit (relevant / skip / partial)
- [ ] 4. Port relevant changes file-by-file (one git commit per logical change)
- [ ] 5. If db/ touched → migration + make generate + apply on Supabase
- [ ] 6. Run checks (`go test ./...` on touched packages)
- [ ] 7. Update last-upstream-commit.txt (internal file only)
```

### 1. Fetch upstream

```bash
.agents/skills/upstream-sync/scripts/fetch-upstream.sh
```

Clones or fast-fetches `https://github.com/workweave/router` into `/tmp/workweave-router-upstream` (override with `UPSTREAM_DIR`).

### 2. List new commits

```bash
.agents/skills/upstream-sync/scripts/list-commits.sh
```

Shows `oneline` log from `last-upstream-commit.txt` → upstream `main` HEAD. Pass `--stat` for file lists:

```bash
.agents/skills/upstream-sync/scripts/list-commits.sh --stat
```

### 3. Triage

For each commit, read subject + changed paths. Use [RELEVANCE.md](RELEVANCE.md) — default **skip** unless clearly core routing/translation/proxy.

Inspect one commit:

```bash
.agents/skills/upstream-sync/scripts/show-commit.sh <sha>
.agents/skills/upstream-sync/scripts/show-commit.sh <sha> -- internal/proxy/
```

Mark each commit: **apply** | **partial** (list files) | **skip** (note why).

### 4. Port changes

**Do not** `git cherry-pick` or merge upstream — histories diverged.

For each file to port:

```bash
# Upstream patch for one file in one commit
.agents/skills/upstream-sync/scripts/show-commit.sh <sha> -- path/to/file.go

# Or diff upstream file vs local (when paths match)
.agents/skills/upstream-sync/scripts/diff-file.sh path/to/file.go
```

Apply manually in the local repo:

- Preserve aiand-only invariants ([CONTEXT.md](../../../CONTEXT.md), [AGENTS.md](../../../AGENTS.md)).
- Replace `ProviderWeave` / multi-provider wiring with `ProviderAiand` where upstream touched providers.
- Drop selfhosted/managed mode branches; keep hosted-only dashboard path.
- Never commit customer names, org IDs, or private ticket references from upstream messages.

For **partial** commits, port only the listed files; ignore the rest.

After each logical port, **commit on the sync branch** (see Branch, commit, and PR rules above).

### 5. Database / Supabase (when schema changes)

If the port touches `db/migrations/`, `db/init/`, or `db/queries/`:

1. Follow [db/CLAUDE.md](../../../db/CLAUDE.md): edit `db/init/00-create-schema.sql`, `make migrate-create NAME=<descriptive-name>`, update `db/queries/`, `make generate`.
2. **Apply to Supabase** (hosted DB — do not skip):
   ```bash
   # .env.local must have session-pooler DATABASE_URL (:5432)
   make migrate-up
   ```
3. Use the **supabase** skill / Supabase MCP when helpful:
   - `execute_sql` — verify tables/columns after migrate
   - `get_advisors` — security/performance check on schema changes
   - See [docs/HOST_WSL_SUPABASE.md](../../../docs/HOST_WSL_SUPABASE.md) for session pooler setup
4. Include migration files + regenerated `internal/sqlc/` in the same git commit as the Go changes they support.

If migrate fails (permissions on shared Supabase), document the exact SQL needed and stop — do not claim the DB is updated.

### 6. Verify

Minimum on touched packages:

```bash
go test ./internal/proxy/... ./internal/translate/...   # adjust paths
```

Run broader `go test ./...` before marking sync complete if changes span layers.

### 7. Record progress (internal)

Edit `last-upstream-commit.txt` — set SHA to upstream HEAD (or last reviewed commit). **Do not** reference this file or SHA in git commits or PR descriptions.

## First-time setup

1. Fetch upstream (step 1).
2. Find fork baseline if known:
   ```bash
   git -C /tmp/workweave-router-upstream log --oneline -1
   ```
3. Write that SHA (or the upstream commit you last manually ported) into `last-upstream-commit.txt`.
4. Run `list-commits.sh` to confirm the queue looks right.

## Scripts

| Script | Purpose |
|--------|---------|
| [`scripts/fetch-upstream.sh`](scripts/fetch-upstream.sh) | Clone/fetch upstream into temp dir |
| [`scripts/list-commits.sh`](scripts/list-commits.sh) | Commits since last-upstream-commit |
| [`scripts/show-commit.sh`](scripts/show-commit.sh) | Stat or patch for one commit |
| [`scripts/diff-file.sh`](scripts/diff-file.sh) | Upstream main vs local for one path |

## Additional resources

- Fork-specific skip/apply rules: [RELEVANCE.md](RELEVANCE.md)
- Provider/ingress glossary: [CONTEXT.md](../../../CONTEXT.md)
