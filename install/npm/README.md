# aiand-router

One command, anywhere, to point Claude Code, Codex, opencode, or pi at the Aiand Router.

```bash
npx aiand-router                       # interactive: pick Claude Code / Codex / opencode / pi, then scope
npx aiand-router --claude              # skip the picker, target Claude Code
npx aiand-router --codex               # skip the picker, target the OpenAI Codex CLI
npx aiand-router --opencode            # skip the picker, target opencode
npx aiand-router --pi                  # skip the picker, target pi + Loom UI
npx aiand-router --scope project       # per-repo install, commit settings.json (or .codex/ / opencode.json)
npx aiand-router --local               # self-hosted via docker-compose (localhost:8080)
npx aiand-router --base-url https://router.acme.internal
npx aiand-router --non-interactive     # reads $AIAND_ROUTER_KEY, no prompts (defaults to claude)
```

Re-running the installer to pick up changes reuses the key already on disk, so
you paste it once and never again — for every client, not just Claude Code.
`update` is the never-prompting form of that (safe for cron; errors instead of
asking when no key can be found):

```bash
npx aiand-router --claude                # reuses the installed key
npx aiand-router --codex                 # same for Codex, opencode, and pi
npx aiand-router --claude --rotate-key   # ignore it and prompt for a new one
npx aiand-router update --claude         # non-interactive refresh in place
```

For Claude Code the installed statusline and `/force-model`, `/router-*` slash
commands also refresh themselves in the background about once a week (never
overwriting a wrapper you edited). Opt out with `AIAND_STATUSLINE_UPDATE=0`, or
just the commands with `AIAND_COMMANDS_UPDATE=0`. Codex installs native `$` skills
plus managed `SessionStart`/`Stop` hooks: the latest routed model is reflected in
the terminal title and a compact `Aiand Router · …` status message is shown when
the router reports a new route. Existing Codex hooks are preserved. OpenCode and pi
have their own target-specific integrations.

Version-pin for reproducible setups:

```bash
npx aiand-router@0.3.0 --claude --scope project
```

Switch on/off without uninstalling (keeps your config so switching back is
instant; requires an explicit client):

```bash
npx aiand-router off --claude      # route Claude Code directly to Anthropic
npx aiand-router on --claude       # route Claude Code through the router again
npx aiand-router status --codex    # is Codex on the router or direct?
```

Claude Code reads its router setting at launch, so quit and reopen it after an
on/off. Codex and opencode pick it up on their next run. Inside Claude Code the
slash commands `/router-off`, `/router-on`, and `/router-status` do the same.
Codex installs a `$disable-routing` skill that switches its next session back
to the normal provider; Codex does not support third-party `/disable-routing`
slash commands. The shell equivalent is `npx aiand-router disable-routing`.
Cursor has no config file we own — toggle its base URL override in **Settings →
Models** instead.

Pick which models the router is allowed to route to:

```bash
npx aiand-router models --claude                  # list every model, with its on/off state
npx aiand-router models disable gpt-5.6 --claude  # take one out of rotation
npx aiand-router models enable gpt-5.6 --claude   # put it back
```

Inside Claude Code that's `/router-models` (alias `/models`). Editing needs a
router that serves the model-selection API; against the Aiand-hosted router the
list still prints and points you at the dashboard, where model selection is an
organization-wide setting.

Uninstall:

```bash
npx aiand-router --uninstall                       # Claude Code, user scope
npx aiand-router --uninstall --codex               # Codex, user scope
npx aiand-router --uninstall --opencode            # opencode, user scope
npx aiand-router --uninstall --pi                  # pi, user scope
npx aiand-router --uninstall --scope project       # Claude Code, inside the repo
npx aiand-router --uninstall --codex --scope project
```

## What it does

This package is a thin Node wrapper around [`install.sh`](./install.sh) from
the Aiand Router repo. It exists so you can install from any machine with
Node ≥ 18 — no `curl | sh`, no Git clone, no PATH fiddling. Everything the
shell installer documents (targets, scopes, flags, environment variables)
works identically here.

Four install targets:

- **Claude Code** (default) — patches `~/.claude/settings.json` (or
  `<repo>/.claude/settings.json` with `--scope project`) so `claude` routes
  through Aiand automatically. Anthropic plan credentials flow through to
  api.anthropic.com.
- **Codex** (`--codex`) — patches `~/.codex/config.toml` (or
  `<repo>/.codex/config.toml`) with a managed `[model_providers.aiand]`
  block plus `model_provider = "aiand"`. The provider preserves the existing
  ChatGPT OAuth login. No install pins `X-Aiand-Router-Strategy`; every
  endpoint keeps its router's configured default. HMM or forced
  `gpt-5.6-sol`, `gpt-5.6-terra`, and `gpt-5.6-luna` turns use that plan;
  every other selected model uses its Aiand deployment or BYOK credential.
  The block lives between begin/end markers
  so re-running the installer rewrites it cleanly and `--uninstall --codex`
  removes it without touching the rest of your config. Codex does not load
  third-party slash-command files; to send a router directive, type it with
  one leading space (for example, ` /force-model gpt-5.6-terra`). Its
  `$disable-routing` skill returns the next Codex session to the default
  provider without logging out or deleting the router configuration. The
  managed lifecycle hooks also keep the latest routed model in the terminal
  title and emit a compact status message when the router reports a new route.
- **opencode** (`--opencode`) — merges a `provider.aiand` entry (backed by
  opencode's built-in `@ai-sdk/anthropic` provider) into
  `~/.config/opencode/opencode.json` (or `<repo>/opencode.json` with
  `--scope project`). The router speaks the Anthropic Messages API
  natively, so opencode talks to it unmodified. Re-install rewrites only
  the managed `provider.aiand` block; `--uninstall --opencode` strips it
  and leaves your other providers and settings alone.
- **pi** (`--pi`) — registers the `aiand` provider and installs this package as
  a pi extension. Stock pi then gets the Loom startup header, Wooly's animated
  mascot, the persistent actual-route display, cumulative session savings,
  `/fm` + `/ufm` model-pin commands with a `[forced]` status, and the
  context-isolated `dispatch` tool. There is no forked pi binary and no separate
  Loom runtime.

See the [main installer docs](https://github.com/fenilmodi00/aiand-router/tree/main/install)
for the full reference.

## Requirements

- Node ≥ 18 (ships with `npx`)
- `bash` on PATH (macOS / Linux native; Windows needs Git Bash or WSL)
- `jq` on PATH — used by the Claude Code status line, the Codex lifecycle helper, and the opencode/pi JSON merges.

## Why npx

`npx aiand-router` gives Windows support via Git Bash, painless version
pinning, and discoverability via the npm registry.

## Older npm

On npm ≤ 6 the bundled `npx` treats an undeclared `-y` as consuming the next
token, so `npx -y aiand-router --claude` silently drops the package name
and resolves the following argument as the command instead. Either upgrade
(`npm i -g npm@latest`) or name the binary explicitly:

```bash
npx --package aiand-router -y -- aiand-router --claude
```

That form is correct on every npm version.
