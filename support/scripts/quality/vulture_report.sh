#!/usr/bin/env bash
# Generate Vulture report under artifacts/vulture-latest.txt
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
mkdir -p artifacts
# Vulture exits non-zero when it finds issues; we still want the report file.
set +e
uv run vulture src vulture_whitelist.py --min-confidence 80 2>&1 \
  | tee artifacts/vulture-latest.txt
set -e
