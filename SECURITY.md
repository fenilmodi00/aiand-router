# Security

- The gateway holds `AIAND_API_KEY`. Clients send `Authorization: Bearer <ROUTER_API_KEY>`. A wrong client key is 401 and never reaches aiand.
- Do not put the aiand key in OpenCode, flashlight config, logs, replay, or `/health`. Health only reports whether the key is **set**.
- JSONL redaction is configurable (`redact_keys` in the registry / default: key, authorization, token, secret). Replay uses the same redaction.
- Soft spend cap: `BUDGET_LIMIT_USD` (default $15). Request `max_tokens` above `MAX_TOKENS_LIMIT` is 400 before upstream. Upstream timeout is `UPSTREAM_TIMEOUT_S`.
- Sensitive repos still go to aiand when a client sends them. Document that to users; this proxy does not add a privacy boundary.
