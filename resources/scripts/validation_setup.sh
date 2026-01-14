#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

docker compose up -d postgres redis
docker compose run --rm --entrypoint "" app bash -c "python resources/scripts/wait_for_db.py && alembic upgrade head"
docker compose ps
