#!/usr/bin/env bash
# List upstream commits since last-upstream-commit.txt (oldest first).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
STATE_FILE="${SKILL_DIR}/last-upstream-commit.txt"
UPSTREAM_DIR="${UPSTREAM_DIR:-/tmp/workweave-router-upstream}"

if [[ ! -d "${UPSTREAM_DIR}/.git" ]]; then
  echo "No upstream clone at ${UPSTREAM_DIR}. Run fetch-upstream.sh first." >&2
  exit 1
fi

read_last_sha() {
  grep -v '^#' "${STATE_FILE}" 2>/dev/null | grep -v '^[[:space:]]*$' | head -1 || true
}

LAST=$(read_last_sha)
HEAD=$(git -C "${UPSTREAM_DIR}" rev-parse HEAD)

if [[ -z "${LAST}" ]]; then
  echo "No baseline in ${STATE_FILE} — showing last 30 upstream commits (newest first):" >&2
  echo "Set baseline SHA in last-upstream-commit.txt to limit the queue." >&2
  echo "---" >&2
  git -C "${UPSTREAM_DIR}" log -30 --oneline
  echo "---" >&2
  echo "upstream HEAD: ${HEAD}"
  exit 0
fi

if ! git -C "${UPSTREAM_DIR}" cat-file -e "${LAST}^{commit}" 2>/dev/null; then
  echo "Baseline ${LAST} not found in upstream clone. Fetch again or fix last-upstream-commit.txt." >&2
  exit 1
fi

COUNT=$(git -C "${UPSTREAM_DIR}" rev-list --count "${LAST}..HEAD")
echo "Commits since ${LAST:0:12}: ${COUNT} (upstream HEAD ${HEAD:0:12})"
echo "---"

if [[ "${1:-}" == "--stat" ]]; then
  git -C "${UPSTREAM_DIR}" log --reverse --stat "${LAST}..HEAD"
else
  git -C "${UPSTREAM_DIR}" log --reverse --oneline "${LAST}..HEAD"
fi
