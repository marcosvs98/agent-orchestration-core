# Installation

## Requirements

- Python **3.12** (exact; `pyproject.toml` declares `>=3.12,<3.13`)
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
| `REDIS_URL` | Yes | `redis://localhost:6379/3` |
| `JWT_SECRET` | Yes | Secret key for JWT validation |
| `JWT_ISSUER` | Yes | Expected `iss` claim in JWT |
| `JWT_AUDIENCE` | Yes | Expected `aud` claim in JWT |
| `LANGFUSE_PUBLIC_KEY` | No | Langfuse public key (LLM tracing) |
| `LANGFUSE_SECRET_KEY` | No | Langfuse secret key |
| `LANGFUSE_HOST` | No | Langfuse host URL |
| `CACHE_SILENT_MODE` | No | `true` (default) — cache failures are silent |

## Verify

```bash
curl http://localhost:8000/health
# → {"status": "ok"}
```

OpenAPI spec is served at `http://localhost:8000/openapi.json`.

## Next steps

- [Full tenant configuration](full-tenant-configuration.md) — end-to-end setup of a usable tenant
- [Architecture overview](../Architecture/ARCHITECTURE.md) — system design and bounded contexts
- Development guide: `DEVELOPMENT.md` at the repository root
