#!/usr/bin/env bash
# Run CI-equivalent checks before push/PR. Exits non-zero on first failure.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "${REPO_ROOT}"

echo "=== upstream-sync CI gate ==="

echo "→ gofmt (write fixes in place)"
UNFORMATTED=$(gofmt -l .)
if [[ -n "${UNFORMATTED}" ]]; then
  echo "Formatting:"
  gofmt -w ${UNFORMATTED}
  echo "Fixed gofmt on:"
  echo "${UNFORMATTED}"
  echo "Re-stage formatted files before commit."
fi

echo "→ make check (generate + fmt + vet + build + test + install/statusline)"
make check

echo "=== All CI checks passed ==="
