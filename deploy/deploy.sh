#!/usr/bin/env bash
# Run on the EC2 host after `git pull` (invoked by GitHub Actions or manually).
set -euo pipefail

AOC_DIR="${AOC_DIR:-/opt/uora/agent-orchestration-core}"
API_DIR="${API_DIR:-/opt/uora/app-platform-api}"
cd "${AOC_DIR}"

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.ec2.yml)

sync_from_origin_main() {
  git fetch origin main
  while IFS= read -r f; do
    [[ -z "${f}" ]] && continue
    git checkout origin/main -- "${f}"
  done < <(git diff --name-only HEAD origin/main | grep -v '^docker-volumes/' || true)
}

echo "==> Disk usage"
df -h /

echo "==> Syncing code from origin/main (preserving docker-volumes bind mounts)"
sync_from_origin_main

echo "==> Pruning Docker build cache"
docker builder prune -af || true
docker image prune -f || true

echo "==> Building and starting AOC containers"
"${COMPOSE[@]}" up -d --build --remove-orphans

echo "==> Waiting for AOC health"
ready=0
for _ in $(seq 1 36); do
  if curl -sf --max-time 5 http://127.0.0.1:8000/health >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 5
done

if [[ "${ready}" -ne 1 ]]; then
  echo "AOC health check failed" >&2
  "${COMPOSE[@]}" logs app --tail 60 || true
  exit 1
fi

if [[ -f "${API_DIR}/deploy/verify-aoc.sh" ]]; then
  echo "==> Verifying API → AOC integration"
  bash "${API_DIR}/deploy/verify-aoc.sh"
fi

echo "==> AOC deploy complete"
