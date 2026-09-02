# Installation

## Requirements

- Python **3.14** (exact; `pyproject.toml` declares `>=3.14,<3.15`, and the image is `FROM python:3.14`)
- [uv](https://docs.astral.sh/uv/) — recommended package manager
- Docker + Docker Compose — for Postgres, Redis, and full-stack runs

## Option A — Docker Compose (recommended for first run)

Start all services (Postgres, Redis, and the app itself):

```bash
docker compose up -d
docker compose logs -f app   # stream app logs
```

On first start, run migrations against the running Postgres:

```bash
export DATABASE_URL='postgresql+asyncpg://postgres:password@127.0.0.1:5432/agent_router'
make migrate
```

Load demo data (optional):

```bash
make seed-demo
```

!!! note "`make seed-demo` applies committed SQL"
    The demo tenant ships as data: `resources/sql/demo_seed.sql`, 51 tables including the RAG
    corpus with its 3072-dimension embedding vectors. Applying it needs a migrated database and
    nothing else — no OpenAI key, no second service. The file is one transaction of
    `INSERT … ON CONFLICT DO UPDATE`, so re-applying converges instead of duplicating.

    It is plain SQL, so any client works:

    ```bash
    psql "postgresql://postgres:password@127.0.0.1:5432/agent_router" \
      -v ON_ERROR_STOP=1 -f resources/sql/demo_seed.sql
    ```

    To change the demo, edit the Python seeds and regenerate — they compile the flow graph and call
    the embedding provider, neither of which can be hand-written as stable SQL:

    ```bash
    make seed-demo-python    # generate (needs an OpenAI key for the RAG corpus)
    make seed-demo-export    # capture into resources/sql/demo_seed.sql
    ```

    `seed_05_tool` imports its tools from a **vendored OpenAPI fixture**, so the generator needs
    no external service either. Point `DEMO_OPENAPI_URL` at your own OpenAPI document (URL or file
    path) and `DEMO_API_HTTP_BASE` at wherever those tools should be called at execution time. Details: `resources/sql/README.md` in the repository.

> **Resetting the database:** `docker compose down -v` removes only named/anonymous Docker volumes. Data is stored in `./docker-volumes/postgres` (bind mount). To reset completely, stop services and delete that directory:
>
> ```bash
> rm -rf docker-volumes/postgres docker-volumes/redis
> ```

## Option B — Local virtualenv + external services

Bring up Postgres and Redis via Docker Compose:

```bash
docker compose up -d postgres redis
```

Add `temporal` if you want durable flow runs or scheduled tool execution — note that the `app`
compose service `depends_on` it, so `docker compose up -d` (Option A) starts it either way:

```bash
docker compose up -d postgres redis temporal
```

Install all dependencies (including dev and docs groups):

```bash
uv sync --all-extras --all-groups
source .venv/bin/activate
```

Configure environment variables:

```bash
cp env.example .env
# edit .env with your DATABASE_URL, REDIS_URL, JWT_SECRET, etc.
```

Run migrations:

```bash
export DATABASE_URL='postgresql+asyncpg://postgres:password@127.0.0.1:5432/agent_router'
make migrate
```

Start the app:

```bash
PYTHONPATH=src uvicorn src.app:app --reload --port 8000
```

## Key environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | `postgresql+asyncpg://user:pass@host:5432/db` |
| `REDIS_URL` | No | `redis://localhost:6379/0`. Wins when set, including the database index; otherwise `REDIS_HOST`/`REDIS_PORT`/`REDIS_DB` are composed |
| `JWT_SECRET` | Yes | Secret key for JWT validation |
| `JWT_ISSUER` | Yes | Expected `iss` claim in JWT |
| `JWT_AUDIENCE` | Yes | Expected `aud` claim in JWT |
| `ADMIN_API_KEY` | No | Required to call `/admin/llm/*` and `/core/v1/auth/admin/api-keys` (`X-Admin-Key`) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | No | OTLP/HTTP endpoint (default `http://localhost:4318`) |
| `OTEL_SERVICE_NAME` | No | Resource `service.name` (default `agent-orchestration-core`) |
| `OTEL_CAPTURE_CONTENT` | No | `false` (default). `true` exports prompts and completions |
| `TRACING_ENABLED` | No | `true` (default). Set `false` to run with no telemetry at all |
| `METRICS_ENABLED` | No | `true` (default) |
| `CACHE_SILENT_MODE` | No | `true` (default) — cache failures are silent |
| `TEMPORAL_ENABLED` | No | `false` (default) — when true, flow runs execute as Temporal workflows |
| `TEMPORAL_HOST` | No | `localhost:7233` |

`env.example` documents **every** setting `src/settings.py` reads, grouped by concern, with the real
default beside each one. Copy it to `.env` — the loader does not read `env.local`.

Full durable-execution configuration: [Durable execution](../Execution/durable-execution.md).

## Temporal

Temporal is a **hard dependency of `docker-compose.yml`**: the `app` service declares
`depends_on: temporal (service_healthy)`, so `docker compose up -d` starts it whether or not
`TEMPORAL_ENABLED` is set. With the flag off, flow runs still execute inline in the HTTP request and
Temporal simply idles.

```bash
make temporal-up          # dev server: gRPC on 7233, Web UI on 8233
make worker               # flow-run + tool-run workers, plus the flow-run reconciler
make test-temporal        # workflow and activity tests
```

Turning it on requires **both** halves: `TEMPORAL_ENABLED=true` for the API process (so runs are
dispatched) and a running worker (so they execute). With the flag on and no worker, runs sit in
`QUEUED` until the reconciler fails them.

The worker also hosts `FlowRunReconciler`, which fails flow runs stranded between dispatch and
finalization — see [Durable execution](../Execution/durable-execution.md).

## Verify

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "healthy",
  "service": "agent-orchestration-core",
  "components": {
    "database": {"status": "ok", "response_time_ms": 19.63},
    "redis": {"status": "ok", "response_time_ms": 1.61},
    "temporal": {"status": "ok", "response_time_ms": 4.02}
  }
}
```

The `temporal` component appears only when `TEMPORAL_ENABLED=true`. There is still a single
`/health` route — no separate `/health/live` and `/health/ready`.

OpenAPI spec is served at `http://localhost:8000/openapi.json`.

## Examples

Four runnable scenarios that need **no tenant data and no external service**. Three need no
infrastructure at all; only the last needs Temporal.

```bash
PYTHONPATH=src uv run python examples/context_compaction.py
PYTHONPATH=src uv run python examples/tool_retry_loop.py
PYTHONPATH=src uv run python examples/memory_commit_outcomes.py

docker compose up -d temporal
PYTHONPATH=src uv run python examples/scheduled_tool_run.py
```

Each prints a narrated trace and exits non-zero if the runtime does not behave as described, so
they double as executable documentation. See `examples/README.md`.

## Next steps

- [Examples](#examples) — the fastest way to see the runtime do something
- [Full tenant configuration](full-tenant-configuration.md) — end-to-end setup of a usable tenant
- [Architecture overview](../Architecture/ARCHITECTURE.md) — system design and bounded contexts
- [Durable execution](../Execution/durable-execution.md) — Temporal workflows and scheduled tools
- Development guide: `DEVELOPMENT.md` at the repository root
