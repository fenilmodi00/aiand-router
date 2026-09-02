#!/usr/bin/env bash
# Fetch workweave/router into a persistent temp clone for diff/triage.
set -euo pipefail

UPSTREAM_URL="${UPSTREAM_URL:-https://github.com/workweave/router.git}"
UPSTREAM_DIR="${UPSTREAM_DIR:-/tmp/workweave-router-upstream}"
BRANCH="${BRANCH:-main}"

if [[ -d "${UPSTREAM_DIR}/.git" ]]; then
  echo "Updating existing clone at ${UPSTREAM_DIR} ..."
  git -C "${UPSTREAM_DIR}" fetch origin "${BRANCH}" --tags --prune
  git -C "${UPSTREAM_DIR}" checkout -q "${BRANCH}"
  git -C "${UPSTREAM_DIR}" merge -q --ff-only "origin/${BRANCH}" 2>/dev/null || \
    git -C "${UPSTREAM_DIR}" reset -q --hard "origin/${BRANCH}"
else
  echo "Cloning ${UPSTREAM_URL} → ${UPSTREAM_DIR} ..."
  git clone --branch "${BRANCH}" "${UPSTREAM_URL}" "${UPSTREAM_DIR}"
fi

HEAD=$(git -C "${UPSTREAM_DIR}" rev-parse HEAD)
echo "Upstream ${BRANCH} @ ${HEAD}"
git -C "${UPSTREAM_DIR}" log -1 --oneline
