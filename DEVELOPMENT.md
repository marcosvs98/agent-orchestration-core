# Development

Getting agent-orchestration-core running locally, and what to reach for once it is.
This repository does not accept contributions; see [CONTRIBUTING.md](CONTRIBUTING.md) for the
conventions and invariants to keep in mind if you fork it.

## Requirements

- Python 3.14
- [uv](https://docs.astral.sh/uv/)
- Docker and Docker Compose

## The fastest path

```bash
docker compose up -d
docker compose logs -f app
```

That brings up Postgres, Redis, Temporal, the API on `:8000`, and the workers. Add the demo
tenant:

```bash
make migrate
make seed-demo
```

`make seed-demo` applies a committed SQL dump — 51 tables including the RAG corpus with its
embedding vectors already computed. It needs a migrated database and nothing else: no model
provider key, no second service.

Interactive API documentation is served at `http://localhost:8000/docs` in development only.
See [API documentation exposure](#api-documentation-exposure) below.

## Running the API outside Docker

```bash
uv sync --all-extras --all-groups
source .venv/bin/activate
cp env.example .env
docker compose up -d postgres redis

export DATABASE_URL='postgresql+asyncpg://postgres:password@127.0.0.1:5432/agent_router'
make migrate
PYTHONPATH=src uvicorn src.app:app --reload --port 8000
```

`PYTHONPATH=src` is not optional — the application uses absolute imports rooted at `src/`.

## Configuration

`env.example` lists every setting the service reads, each commented with its real default. Copy
it to `.env` and uncomment only what you change. `docker-compose.yml` overrides `DATABASE_URL`,
`REDIS_HOST`, `REDIS_PORT`, `TEMPORAL_HOST` and `PORT` for the containerised path.

### API documentation exposure

`/docs`, `/redoc` and `/openapi.json` are served only when `EXPOSE_API_DOCS` is true. It defaults
to true when `ENVIRONMENT=development` and false everywhere else, so a deployment that does not
set `ENVIRONMENT` at all ships with the schema closed. Set `EXPOSE_API_DOCS=true` to open it
deliberately.

## Tests

```bash
uv run python -m pytest                      # full suite with the coverage gate
uv run python -m pytest tests/unit -q        # unit only
uv run python -m pytest tests/unit --cov=src --cov-fail-under=0 -q   # iterating, no gate
```

Integration tests need Postgres and Redis running. The validation suite
(`@pytest.mark.validation_integration`) needs the full Compose stack and is excluded from the
default run.

To see coverage across the whole codebase rather than the gated surface:

```bash
uv run python -m pytest --cov-config=/dev/null --cov=src --cov-fail-under=0 -q
```

## Pre-commit

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

Ruff is configured for `E9` and `F` only — real errors and unused imports, not formatting
opinions. Vulture finds dead code; `vulture_whitelist.py` at the root holds the legitimate false
positives.

## Migrations

```bash
PYTHONPATH=src uv run alembic revision --autogenerate -m "short description"
PYTHONPATH=src uv run alembic upgrade head
```

Revisions live in `src/infra/database/migrations/versions/`. Read what autogenerate produced
before committing it.

## Make targets

| Target | What it does |
|--------|-------------|
| `make migrate` | `alembic upgrade head` |
| `make seed-demo` | Load the demo tenant from committed SQL |
| `make seed-demo-python` | Regenerate it from the Python seeds (needs a model provider key for RAG) |
| `make seed-demo-export` | Capture the result back into `resources/sql/demo_seed.sql` |
| `make temporal-up` / `make temporal-down` | Temporal dev server |
| `make temporal-ui` | Temporal Web UI |
| `make worker` | Temporal workers plus the flow-run reconciler |
| `make test-temporal` | Workflow and activity tests |
| `make docs-up` / `make docs-down` | Documentation site on `:8001` |
| `make gen-token` | Mint a tenant JWT for local calls |
| `make ci` | The gate CI runs |

## Where things live

```text
src/
├── domain/<context>/     # one folder per bounded context
│   ├── controllers/      # FastAPI route handlers
│   ├── services/         # business logic
│   ├── repositories/     # persistence ports
│   └── schemas/          # Pydantic request/response models
├── adapters/             # LLM, RAG, cache, jobs, MCP
├── infra/                # SQLAlchemy models, Alembic, HTTP executor
├── services/             # cross-cutting boundaries
├── app.py                # FastAPI factory
├── containers.py         # dependency-injector wiring
└── settings.py           # configuration
```

Useful entry points:

| Question | File |
|----------|------|
| How does a flow run start? | `src/domain/execution/services/execution_service.py` |
| How does graph execution work? | `src/domain/execution/services/graph_runtime/executor.py` |
| What node types exist? | `src/domain/execution/services/graph_runtime/node_registry.py` |
| How are routes wired? | `src/rest.py` |
| How is DI configured? | `src/containers.py` |
| How is tenant isolation enforced? | `src/services/execution_boundary.py` |

## Documentation

```bash
uv run mkdocs serve      # http://127.0.0.1:8000
make docs-up             # containerised, http://localhost:8001
```

The build is strict — a broken internal link fails it.

## Observability

The Compose stack includes an OpenTelemetry collector, Tempo, Prometheus, Loki and Grafana.
Grafana is on `http://localhost:3000` with the dashboards provisioned. Traces carry
`tenant_id`, so a single flow run can be followed from the HTTP span through node execution to
the model call.

Temporal's Web UI is on `http://localhost:8233`; a flow run appears there as a `FlowRunWorkflow`
with one `execute_node` activity per node.
