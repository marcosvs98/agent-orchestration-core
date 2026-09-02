# Deployment

## Containers

Build and run using the project `Dockerfile` / `docker-compose.yml`. Dependencies:

| Service | Compose name | Required by | Notes |
|---------|--------------|-------------|-------|
| Postgres | `postgres` | always | Needs `pgvector` where RAG is enabled. Bind-mounted at `./docker-volumes/postgres`. |
| Redis | `redis` | always | Caches, rate limiting, idempotency. |
| Temporal | `temporal` | the `app` service `depends_on` it | Dev server (`temporal server start-dev`), frontend on `7233`, Web UI on `8233`. |
| Docs site | `docs` | never (profile `docs`) | MkDocs Material live server: `docker compose --profile docs up -d docs` → <http://localhost:8001>. Mounts `./docs` and `mkdocs.yml`; restart the container after editing `mkdocs.yml` nav. |

Because `app` declares `depends_on: temporal (service_healthy)`, a plain `docker compose up -d`
starts Temporal whether or not `TEMPORAL_ENABLED` is set.

> **Resetting Postgres.** `docker compose down -v` removes named volumes only. Postgres data lives
> in the `./docker-volumes/postgres` bind mount and survives; delete that directory to reset.

## Processes

The API and the Temporal worker are **separate processes** sharing one image:

| Process | Entrypoint | Scales with |
|---------|------------|-------------|
| API | `uvicorn src.app:app` (`PYTHONPATH=src`) | HTTP traffic |
| Worker | `python -m adapters.temporal.worker` (`PYTHONPATH=src`) | flow-run and scheduled-tool-run volume |

The worker serves **two task queues** in one process (`flow-runs` and `tool-runs`). See
[Durable execution](../Execution/durable-execution.md).

## Health

The app exposes a single `GET /health` returning component status for `database` and `redis`.

Two known gaps to account for when wiring orchestrator probes:

- There is **no `/health/live` vs `/health/ready` split**, so a readiness probe cannot be
  distinguished from a liveness probe.
- `/health` does **not** report Temporal, and the worker container has **no healthcheck**, so
  worker liveness is unobservable from the platform.

## Scaling

Scale stateless API workers horizontally. Ensure Postgres and Redis are sized for connection
counts. Scale the Temporal worker independently of the API — activity concurrency is bounded per
worker by `TEMPORAL_WORKER_MAX_CONCURRENT_ACTIVITIES` (default `20`).

Enable `TEMPORAL_FAIRNESS_ENABLED` in multi-tenant deployments so a single tenant's backlog
cannot monopolise task-queue slots.
