#!/usr/bin/env bash
# Claude Code Stop Hook for AIand Coding Router
# Extracts pioneer_routed_model and pioneer_savings to display real-time session cost savings.

ROUTER_BASE_URL="${ROUTER_BASE_URL:-http://127.0.0.1:8000}"
SESSION_ID="${CLAUDE_SESSION_ID:-}"

if [ -n "$SESSION_ID" ]; then
  SAVINGS_JSON=$(curl -s "$ROUTER_BASE_URL/v1/session-savings/$SESSION_ID" \
    -H "Authorization: Bearer ${ROUTER_API_KEY:-change-me}" 2>/dev/null)

  if [ -n "$SAVINGS_JSON" ]; then
    SAVINGS=$(echo "$SAVINGS_JSON" | grep -o '"savings_usd":[0-9.]*' | cut -d: -f2)
    REQUESTS=$(echo "$SAVINGS_JSON" | grep -o '"total_requests":[0-9]*' | cut -d: -f2)
    if [ -n "$SAVINGS" ]; then
      echo "⚡ AIand Router saved ~$${SAVINGS} across ${REQUESTS:-0} turns this session."
    fi
  fi
fi
