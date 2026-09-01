# Aiand Router pi extension

> Bundled inside the [`aiand-router`](https://www.npmjs.com/package/aiand-router) package — not published separately. `src/` here is the source of truth; `npm run prepack` copies it into the package.

A [pi](https://pi.dev) extension that routes every request through the
[Aiand Router](https://github.com/fenilmodi00/aiand-router) — a trained, per-request
LLM proxy that picks the most cost-efficient model that still solves each task.

Installed automatically by the Aiand Router installer:

```bash
AIAND_ROUTER_KEY=rk_… npx --package aiand-router -y -- aiand-router --pi
AIAND_ROUTER_KEY=rk_… npx --package aiand-router -y -- aiand-router --pi --local  # local router
```

That writes `~/.pi/agent/models.json` (the `aiand` provider), adds
`npm:aiand-router` to `~/.pi/agent/settings.json` `packages`, and stores
the key in `~/.pi/agent/.aiand_router_key`. pi auto-installs `aiand-router`
from npm on next start and loads this extension via its `pi.extensions` field.

## What it does

- **Loom experience on stock pi.** Replaces pi's startup header through the
  public extension API, adds Wooly's responsive orange terminal animation, and
  keeps pi's own runtime/footer intact. Wooly is visual only: there is no
  dialogue box, narration, coaching request, or separate Loom runtime.
- **Automatic model selection.** All pi traffic flows through the router, which
  selects the model per request. You don't pick a model — the router does.
- **Force-model commands.** `/fm <model>` and `/force-model <model>` pin the
  current router session; `/ufm` and `/unforce-model` resume automatic routing.
  The persistent status changes to `AIAND ROUTER — <model> [forced]` after the
  router validates and canonicalizes the requested model. Headless clients
  (no slash-command UI) can pin the same way with the OpenAI-compatible
  `model` field instead — e.g. `model="moonshotai/kimi-k2.7":high` — which is
  treated as identical routing intent. Use `model="auto"` to route normally
  without touching an existing pin (only `/unforce-model` clears one).
- **Per-process routing bias.** Static `x-aiand-routing-*` knob headers bias the
  router: quality on the main loop and speed + cheap on subagents.
- **Long tool-loop compaction.** Pi can cross its context threshold inside an
  uninterrupted tool loop before its normal post-run compaction check. The
  extension preserves a usable output budget for the real continuation,
  compacts once the loop settles, and resumes that extension-owned tool loop.
  Ordinary Pi threshold compaction remains under Pi's control.
- **Sticky sessions.** `metadata.user_id = "pi:<sessionId>"` pins the main loop
  to one model for the session; subagents get their own pins.
- **`dispatch` tool — parallel, context-isolated subagents.** pi has none
  natively. `dispatch` spawns child `pi` processes (read-only by default), runs
  them concurrently, and returns only each subagent's final answer — intermediate
  tool output stays in the child, so the main context stays small.
- **Persistent route + savings display.** Shows
  `AIAND ROUTER — <routed> ← <selected> · saved $X.XX` below pi's native footer
  data. Savings compare the selected and routed catalog prices against the same
  input/output/cache usage, accumulate across the reachable session branch,
  and survive resume. Unknown catalog prices are labeled `unpriced` instead of
  silently contributing zero; costlier routing is labeled `extra`, not savings.
- **No duplicate in-band badge.** Sets `X-Aiand-Routing-Marker: off` because the
  persistent status already conveys the actual model.
- **Safety backstop.** Blocks a few catastrophic shell commands (`rm -rf /`,
  `mkfs`, `dd of=/dev/…`, fork bombs, force-push to main). Disable with
  `AIAND_NO_SAFETY=1`.

## Configuration (environment)

| Variable | Default | Purpose |
|---|---|---|
| `AIAND_ROUTER_URL` | `http://localhost:8080` | Router base URL (children inherit it) |
| `AIAND_ROUTER_KEY` | — | Router key (else read from `.aiand_router_key`) |
| `AIAND_ROUTER_KEY_FILE` | `<agentDir>/.aiand_router_key` | Override key file path |
| `AIAND_USER_EMAIL` / `AIAND_USER_NAME` | from `git config` | Identity headers for attribution |
| `AIAND_PI_SUBAGENT_MODEL` | `claude-sonnet-4-6` | `aiand/<model>` handle children launch with (router re-routes) |
| `AIAND_PI_DISPATCH_CONCURRENCY` | `4` | Max concurrent subagents |
| `AIAND_PI_SUBAGENT_TIMEOUT_MS` | `600000` | Per-subagent timeout |
| `AIAND_PI_ALLOW_SUBAGENT_TOOLS` | unset | `1` lets `dispatch` grant subagents write/exec tools (bash, write, edit); default strips them |
| `AIAND_ROUTING_ALPHA` / `…_SPEED_WEIGHT` / `…_OUTPUT_COST_RATIO` / `…_EXPECTED_OUTPUT_TOKENS` | role preset | Override individual routing knobs (main process only — children always use their role preset) |
| `AIAND_NO_SAFETY` | unset | `1` disables the catastrophic-bash gate |
| `AIAND_PI_AUTO_COMPACTION` | unset | `0` disables the routed tool-loop compaction safeguard |

Internal: `AIAND_PI_SUBAGENT=1` and `AIAND_PI_SUBAGENT_ID` are set by `dispatch`
on child processes; don't set them yourself.

## Costs

Routing through the router charges your turn to the router deployment's key
(or your BYOK key). BYOK skips cross-provider failover; the deployment key is
the default.

The displayed savings are a client-side estimate from the router's generated
model-price catalog. Cache writes use 1.25× input price and cache reads use 0.1×
input price, matching the Claude Code statusline. The ledger stores its catalog
version with each response so resumed totals remain auditable.


## Notes

- Actual SDK/router probes keep their small output budget. Only a probe-sized
  request carrying a real tool-result continuation is repaired.
