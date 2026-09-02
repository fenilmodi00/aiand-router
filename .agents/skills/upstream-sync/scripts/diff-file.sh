#!/usr/bin/env bash
# Diff one path: upstream main vs local repo working tree.
set -euo pipefail

UPSTREAM_DIR="${UPSTREAM_DIR:-/tmp/workweave-router-upstream}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
FILE="${1:-}"

if [[ -z "${FILE}" ]]; then
  echo "Usage: diff-file.sh <repo-relative-path>" >&2
  exit 1
fi

if [[ ! -d "${UPSTREAM_DIR}/.git" ]]; then
  echo "No upstream clone. Run fetch-upstream.sh first." >&2
  exit 1
fi

if ! git -C "${UPSTREAM_DIR}" cat-file -e "HEAD:${FILE}" 2>/dev/null; then
  echo "Path not in upstream HEAD: ${FILE}" >&2
  exit 1
fi

LOCAL="${REPO_ROOT}/${FILE}"
if [[ ! -f "${LOCAL}" ]]; then
  echo "Path not in local repo: ${FILE}" >&2
  echo "--- upstream version only ---"
  git -C "${UPSTREAM_DIR}" show "HEAD:${FILE}"
  exit 0
fi

diff -u "${LOCAL}" <(git -C "${UPSTREAM_DIR}" show "HEAD:${FILE}") || true
