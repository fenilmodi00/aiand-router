# web — Marketing + Playground

**Generated:** 2026-08-21
**Commit:** 492a192
**Branch:** v0

## OVERVIEW

Next.js 16.3 / React 19 / Tailwind 4 marketing site and `/playground` router simulator. No test suite.

## STRUCTURE

```
web/
├── app/                # Next.js App Router — page.tsx + api/chat + api/keys
├── components/         # 26 components + ui/ (shadcn 29 primitives)
├── lib/                # aiand.ts, api.ts, format.ts, types.ts, utils.ts
└── hooks/              # use-mobile.ts
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Playground simulator | `components/Playground.tsx`, `components/InteractiveRouterSimulator.tsx` | Client-side routing demo |
| Routing viz | `components/RoutingPipeline.tsx`, `components/PipelineDots.tsx` | Pipeline dots + cost display |
| API proxy | `app/api/chat/route.ts` | Forwards to Python gateway |
| Keys page | `app/keys/page.tsx`, `app/api/keys/route.ts` | Key management |
| Shared utils | `lib/utils.ts` (`cn` helper), `lib/format.ts` | Tailwind merge |
| UI primitives | `components/ui/` | shadcn/ui — do not hand-edit generated styles |

## CONVENTIONS

- Tailwind 4 via `@tailwindcss/postcss`; `cn()` from `lib/utils.ts` merges classes.
- shadcn/ui components in `components/ui/` — update via `shadcn` CLI, not manual edits.
- `next.config.ts` + `tsconfig.json` + `eslint.config.mjs` — Next.js config is TypeScript, not JS.

## ANTI-PATTERNS

- Never put `AIAND_API_KEY` in `web/.env.local` — stays in Python `src` process only (`SECURITY.md`).
- Never add a test framework here without updating root `COMMANDS` — currently `web/package.json` has no `test` script.
- Both `bun.lock` + `package-lock.json` tracked — do not delete one; check install path first.
