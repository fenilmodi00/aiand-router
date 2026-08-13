# Router console

Local operator UI for `router/auto`. The browser talks to this Next app; the Next server talks to the FastAPI gateway with `ROUTER_API_KEY`. `AIAND_API_KEY` never leaves the Python process.

## Run

Gateway must already be listening on port 8000:

```bash
uvicorn aiand_router.app:app --app-dir src --host 127.0.0.1 --port 8000
```

Then, from `web/`:

```bash
npm install
copy .env.local.example .env.local
```

Set `ROUTER_API_KEY` in `.env.local` to the same value clients send the gateway (the repo-root `.env` `ROUTER_API_KEY`, default `change-me`). Do not put `AIAND_API_KEY` here.

```bash
npm run dev
```

Open http://127.0.0.1:3000 — it redirects to `/routers`.

```bash
npm run typecheck
npm run build
```

## Env

```
ROUTER_BASE_URL=http://127.0.0.1:8000
ROUTER_API_KEY=change-me
```

Windows: `copy .env.local.example .env.local`
