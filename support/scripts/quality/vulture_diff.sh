#!/usr/bin/env bash
# Fail if vulture-latest.txt has NEW lines vs vulture-baseline.txt (sorted compare).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
BASELINE="${ROOT}/artifacts/vulture-baseline.txt"
LATEST="${ROOT}/artifacts/vulture-latest.txt"
if [[ ! -f "${BASELINE}" ]]; then
  echo "Missing ${BASELINE}. Generate with: bash support/scripts/quality/vulture_report.sh && cp artifacts/vulture-latest.txt artifacts/vulture-baseline.txt"
  exit 1
fi
if [[ ! -f "${LATEST}" ]]; then
  echo "Missing ${LATEST}. Run: bash support/scripts/quality/vulture_report.sh"
  exit 1
fi
# Lines unique to latest (new dead-code findings vs baseline)
NEW_ONLY="$(comm -13 <(sort "${BASELINE}") <(sort "${LATEST}") || true)"
if [[ -n "${NEW_ONLY}" ]]; then
  echo "Vulture: new unused-code findings vs baseline:"
  echo "${NEW_ONLY}"
  echo "---"
  echo "Fix by removing dead code, extending vulture_whitelist.py with justification, or updating artifacts/vulture-baseline.txt in a dedicated PR."
  exit 1
fi
echo "Vulture: no new findings vs baseline."
