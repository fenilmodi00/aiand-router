#!/usr/bin/env bash
# Show one upstream commit: metadata, stat, or patch (optional path filter).
set -euo pipefail

UPSTREAM_DIR="${UPSTREAM_DIR:-/tmp/workweave-router-upstream}"
COMMIT="${1:-}"

if [[ -z "${COMMIT}" ]]; then
  echo "Usage: show-commit.sh <sha> [-- path/to/file ...]" >&2
  exit 1
fi
shift

if [[ ! -d "${UPSTREAM_DIR}/.git" ]]; then
  echo "No upstream clone. Run fetch-upstream.sh first." >&2
  exit 1
fi

git -C "${UPSTREAM_DIR}" show -s --format=fuller "${COMMIT}"
echo "---"
git -C "${UPSTREAM_DIR}" show --stat "${COMMIT}" -- "$@"
echo "--- patch ---"
git -C "${UPSTREAM_DIR}" show "${COMMIT}" -- "$@"
