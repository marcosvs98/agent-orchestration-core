# agent-orchestration-core

Multi-tenant cognitive orchestration platform. Interprets natural language input, determines execution paths deterministically, and invokes external integrations in a controlled, auditable, and predictable way.

---

## 1. System Context

### What it does

**agent-orchestration-core** is a governance and execution engine that orchestrates cognitive agents and execution flows deterministically and auditably. It is **not** a chatbot, a generic assistant, or an LLM wrapper.

Core capabilities:

- **Definition and versioning** of flows, agents, tools, and AI policies
- **Deterministic execution** of flows with complete state tracking
- **Controlled integration** with external systems via tools and MCP servers
- **Multi-tenant governance** with structural isolation per tenant
- **Full observability** via execution events and distributed tracing

### Problems it solves

| Problem | Approach |
|---------|----------|
| Uncontrolled AI side-effects | AI only classifies, extracts, decides a path, and formats — side-effects execute deterministically outside the LLM |
| Reproducibility | Executions are deterministic and auditable; full state is traceable |
| Version drift | Every artefact is versioned and immutable after publication; executions always reference explicit versions |
| Multi-tenant leakage | Structural isolation by `tenant_id` from the foundation |
| Authoring vs runtime confusion | Definitions are immutable; execution never mutates definitions |

---

## 2. Architecture

### Style

**Hexagonal Architecture (Ports & Adapters)** with **Domain-Driven Design (DDD)**:

- **Domain** (`src/domain/**`): business rules, services, repositories
- **Adapters** (`src/adapters/**`): LLM/RAG adapters, Langfuse tracer, MCP gateway
- **Infrastructure** (`src/infra/**`): SQLAlchemy models, migrations, HTTP tool executor
- **Application** (`src/app.py`, `src/containers.py`, `src/rest.py`): FastAPI factory, DI wiring, route registration

Runtime code depends inward on domain contracts; infrastructure and adapters implement those contracts at the edges.

### Design-time vs execution-time

| Plane | Purpose | Artefact states |
|-------|---------|-----------------|
| **Authoring** | Define and version flows, agents, tools, policies | `DRAFT → VALIDATED → PUBLISHED → DEPRECATED → DISABLED` |
| **Runtime** | Execute published versions; never mutate definitions | `CREATED → RUNNING → COMPLETED / FAILED` |

### High-level diagram

```mermaid
flowchart LR
  subgraph Adapters
    HTTP[HTTP / FastAPI]
    Jobs[Workers / ARQ]
  end
  subgraph Domain
    EX[Execution]
    FL[Flows]
    RAG[RAG]
    GOV[Governance]
  end
  subgraph Infra
    DB[(Postgres + pgvector)]
    RD[(Redis)]
    LF[Langfuse]
    LLM[LLM Providers]
  end
  HTTP --> EX
  Jobs --> EX
  EX --> FL & RAG & GOV
  EX --> DB & LF
  GOV --> RD
  EX --> LLM
```

---

## 3. Bounded Contexts

All contexts map one-to-one to `src/domain/<package>/`. Shared helpers live under `src/domain/common/`.

### Core runtime and inference

| Context | Responsibility |
|---------|---------------|
| **Execution** | Graph execution, state machine, node runtime, hooks |
| **Flows** | Graph definition, compilation (DAG), validation, HTTP authoring |
| **LLM** | Layered inference, executor, provider abstraction, semantic cache, moderation |
| **RAG** | Retrieval-augmented generation, embeddings, vector stores, chunking |
| **MCP** | Tenant MCP registry, gateway, HTTP tool bridge (`src/domain/mcp_registry/`) |

### Agents, conversation, and prompts

| Context | Responsibility |
|---------|---------------|
| **Agents** | Agent definitions, versions, node bindings |
| **Conversation** | Sessions, interactions, SSE streaming |
| **Context** | Layered memory, RAG activation, context retrieval |
| **Prompts** | Dynamic prompt templates and versioning |
| **User Prompts** | User-provided prompt variants |

### Policy, identity, and operations

| Context | Responsibility |
|---------|---------------|
| **Governance** | Access policies, rate limits, scope enforcement, authoring audit |
| **AI Policy** | Tenant AI execution policy, model configuration, lifecycle |
| **Human SLA** | Escalation triggers, handoff policies, case management |
| **Auth** | JWT validation, inbound service key management |
| **Tenants** | Multi-tenant isolation, JSONB settings |
| **Tools** | Tool contracts, OpenAPI parsing, HTTP execution |
| **Onboarding** | Structured step-based onboarding flows |

---

## 4. Technologies

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.12+, FastAPI ≥0.135.0, uvicorn |
| Validation | Pydantic v2 ≥2.12.5 |
| ORM | SQLAlchemy 2.0 (async), asyncpg |
| Database | PostgreSQL + pgvector |
| Cache / rate-limit | Redis 5.0 |
| Graph execution | LangGraph ≥1.0.0 |
| LLM providers | OpenAI SDK ≥1.54.0, llama-cpp-python (local SLM) |
| Structured LLM output | instructor ≥1.14.5 |
| MCP | fastmcp ≥3.1.1 |
| Async jobs | ARQ (embedding queue) |
| Observability | Langfuse ≥3.12.0, structlog |
| Migrations | Alembic ≥1.14.0 |
| DI | dependency-injector ≥4.41.0 |
| HTTP client | httpx ≥0.28.0 |
| Auth | PyJWT ≥2.8.0, python-jose |
| Token counting | tiktoken ≥0.7.0 |
| Templates | Jinja2 ≥3.1.0 |
| Package manager | [uv](https://docs.astral.sh/uv/) |
| Containers | Docker / Docker Compose |

---

## 5. Setup and Execution

### 5.1 Via Docker Compose

```bash
# Start all services (PostgreSQL, Redis, App)
docker compose up -d

# Stream application logs
docker compose logs -f app

# Stop
docker compose down
```

> **Data persistence:** The compose file binds Postgres data to `./docker-volumes/postgres`. `docker compose down -v` only removes named/anonymous volumes declared in the `volumes:` section — it does **not** delete that directory. To reset the database, stop services and remove the bind-mount directory manually:
>
> ```bash
> rm -rf docker-volumes/postgres docker-volumes/redis
> ```

### 5.2 Database migrations and seed

Run migrations against a reachable Postgres instance (e.g., after `docker compose up -d postgres`):

```bash
export DATABASE_URL='postgresql+asyncpg://postgres:password@127.0.0.1:5432/agent_router'
make migrate
# equivalent: PYTHONPATH=src uv run python -m alembic upgrade head
```

Load the demo seed (also requires `REDIS_URL` and relevant env vars from `.env`):

```bash
make seed-demo
# equivalent: PYTHONPATH=src uv run python resources/scripts/seeds/demo/run.py
```

### 5.3 Local development (without Docker app container)

```bash
# Install all dependencies including dev and docs groups
uv sync --all-extras --all-groups

# Activate the virtual environment
source .venv/bin/activate

# Copy and configure environment variables
cp env.example .env
# Edit .env with your values

# Run the app
uvicorn src.app:app --reload
```

### 5.4 Environment variables

Copy `.env.example` and adjust:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string (`postgresql+asyncpg://user:pass@host:5432/db`) |
| `REDIS_URL` | Redis connection string (`redis://localhost:6379/3`) |
| `JWT_SECRET` | Secret key for JWT validation |
| `JWT_ISSUER` | Expected JWT issuer claim |
| `JWT_AUDIENCE` | Expected JWT audience claim |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key (optional, for LLM tracing) |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key (optional) |
| `LANGFUSE_HOST` | Langfuse host (optional) |
| `CACHE_SILENT_MODE` | `true` (default) — cache failures are silent; set `false` to fail hard |

### 5.5 Makefile targets

```bash
make pc-config      # Install pre-commit hooks
make pc-run         # Run pre-commit on staged files
make pc-run-all     # Run pre-commit on all files
make migrate        # Run Alembic migrations
make seed-demo      # Load demo seed data
make validate-test  # Run validation suite (requires docker compose)
make test-flow-demo # Exercise demo flow via REST API
```

---

## 6. API Surface

All endpoints require a **JWT Bearer Token** with claims: `tenant_id`, `principal_type`, `principal_id`, `scopes`.

POST operations on the execution plane require an **`Idempotency-Key`** header.

### Control plane (`/core/v1/*`)

| Resource group | Key endpoints |
|----------------|--------------|
| Tenants | `GET /core/v1/tenants/current`, `GET /core/v1/tenants/current/settings` |
| Flows | `GET/POST /core/v1/flows`, `POST /core/v1/flows/{id}/versions` |
| Nodes & Routing | `POST /core/v1/nodes`, `POST /core/v1/routers`, `POST /core/v1/routing-rules` |
| Agents | `GET/POST /core/v1/agents`, `POST /core/v1/agents/{id}/versions` |
| Tools | `POST /core/v1/tools/import-tools`, `GET /core/v1/tools`, `POST /core/v1/tool-configs` |
| AI Policy | `POST /core/v1/ai-execution-policies`, `GET /core/v1/models` |
| RAG | `GET/POST /core/v1/rag-configs`, `GET /core/v1/vector-stores` |
| Governance | `POST /core/v1/{resource}/{id}:{publish,deprecate,disable,activate,rollback}` |
| Onboarding | `GET/POST /core/v1/onboardings`, `POST /core/v1/onboarding-runs` |

### Execution plane (`/core/v1/executions/*`)

| Endpoint | Description |
|----------|-------------|
| `POST /core/v1/executions/flow-runs` | Create and execute a FlowRun |
| `GET /core/v1/executions/flow-runs/{id}` | Fetch FlowRun state |
| `GET /core/v1/executions/flow-runs/{id}/graph-state` | Consolidated node output state |
| `POST /core/v1/executions/tool-runs` | Create a ToolRun |
| `POST /core/v1/executions/tool-runs/{id}:execute` | Execute a ToolRun |
| `GET /core/v1/executions/execution-events` | Query append-only execution events |
| `GET /core/v1/executions/node-runs` | List NodeRuns |
| `GET /core/v1/executions/agent-runs` | List AgentRuns |

### Observability

- `GET /health` — liveness check
- `GET /openapi.json` — OpenAPI 3.0 spec

---

## 7. Testing

### Install dev dependencies

```bash
uv sync --all-extras --all-groups
```

### Run tests

```bash
# All tests (unit + integration + bdd)
uv run python -m pytest

# Specific test file
uv run python -m pytest tests/unit/execution/test_execution_service.py

# Verbose output
uv run python -m pytest -vv

# Skip coverage gate (useful during local iteration)
uv run python -m pytest tests/unit --cov=src --cov-fail-under=0 -q
```

### Coverage policy

| Item | Value |
|------|-------|
| Minimum enforced by CI | **95%** on measured surface |
| Pattern | AAA (Arrange, Act, Assert) |
| Test isolation | Each test is independent; fixtures in `conftest.py` |
| External deps | Mocked via ports/protocols |
| Excluded | Migrations, `__init__.py`, some low-ROI adapters (see `pyproject.toml` `[tool.coverage.run] omit`) |

Test suites: `tests/unit/`, `tests/integration/`, `tests/bdd/`.

---

## 8. Versioning and Governance

### Semantic versioning of artefacts

All versioned artefacts use `major.minor.patch` with hybrid logic:

- **With `source_version_id`**: derives version from the source version (increments patch)
- **Without `source_version_id`**: auto-increments patch of the latest version in scope

Versioned artefacts: `FlowVersion`, `AgentVersion`, `OnboardingVersion`, `AIExecutionPolicyVersion`, `RagConfig`, `ToolConfig`.

### Version lifecycle events

All authoring events require a `justification` field and are persisted in `authoring_event` for audit:

```
CREATE → PUBLISH → ACTIVATE
                ↘ DEPRECATE → DISABLE
                ↘ ROLLBACK
```

### Scope-based authorization

Scopes are defined in `src/domain/governance/schemas/scopes.py` and enforced by `AccessPolicyService` inside `ExecutionBoundary`. Rate limiting uses Redis via `RateLimitService`.

Example scopes: `execution:flow_run:create`, `flows:flow:list`, `agents:agent_version:publish`, `rag:rag_config:create`.

---

## 9. Data Dictionary

| Entity | Description | Scope |
|--------|-------------|-------|
| **Tenant** | Structural isolation root | Isolation root for all entities |
| **Flow** | Process definition (DAG of nodes) | `Tenant 1:N Flows` |
| **FlowVersion** | Immutable published flow version | `Flow 1:N FlowVersions` |
| **FlowGraphSnapshot** | Compiled immutable DAG; used by runtime | `FlowVersion 1:1` |
| **FlowRun** | Concrete execution of a flow version | `FlowVersion 1:N FlowRuns` |
| **Node** | Executable unit inside a flow (optional in current phase) | `FlowVersion 1:N Nodes` |
| **NodeRun** | Single node execution record | `FlowRun 1:N NodeRuns` |
| **Agent** | Cognitive agent definition | `Tenant 1:N Agents` |
| **AgentVersion** | Immutable published agent version | `Agent 1:N AgentVersions` |
| **AgentRun** | Effective agent execution | `AgentVersion 1:N AgentRuns` |
| **Tool** | Abstract external integration contract | Global |
| **ToolConfig** | Concrete tool configuration for a tenant | `Tenant 1:N ToolConfigs` |
| **ToolRun** | Tool invocation record | `ToolConfig 1:N ToolRuns` |
| **AIExecutionPolicy** | AI execution policy | Global |
| **RagConfig** | RAG strategy per tenant | `Tenant 1:N RagConfigs` |
| **VectorStore** | Vector similarity search store | `Tenant 1:N VectorStores` |
| **GraphState** | Consolidated node output state | `FlowRun 1:1` |
| **ExecutionEvent** | Append-only execution event log | `FlowRun 1:N` |
| **AuthoringEvent** | Governance audit trail for version changes | `Resource 1:N` |
| **Session** | Technical interaction context | `Tenant 1:N Sessions` |
| **Interaction** | Persisted input event | `Session 1:N Interactions` |

ORM models: `src/infra/database/models/`
Pydantic schemas: `src/domain/<context>/schemas/`
Repositories: `src/domain/<context>/repositories/`

---

## 10. Core Invariants

1. **Tenant isolation is structural**: every datum, decision, and execution belongs to a tenant. `tenant_id` comes from the security context — never from the request body.
2. **Definition is separate from execution**: flows and agents are defined and versioned; executions are traceable and auditable, and never mutate definitions.
3. **AI does not execute side-effects**: the LLM only classifies, extracts, decides a path, or formats — side-effects are deterministic code outside the LLM.
4. **Everything is explicit and versioned**: flows, agents, prompts, policies, tools, and decisions all have a version.
5. **The channel is an input/output detail**: the core is agnostic to the interaction medium.

---

## 11. References

### Internal documentation

- [Architecture overview](docs/Architecture/ARCHITECTURE.md)
- [Runtime vs authoring](docs/Architecture/runtime-vs-authoring.md)
- [Domain model overview](docs/Models/domain-overview.md)
- [Glossary](docs/Glossary/index.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [DEVELOPMENT.md](DEVELOPMENT.md)
- [SECURITY.md](SECURITY.md)
- [MkDocs site](docs/index.md) — full domain documentation

### External references

- [Hexagonal Architecture](https://herbertograca.com/2017/11/16/explicit-architecture-01-ddd-hexagonal-onion-clean-cqrs-how-i-put-it-all-together/)
- [Domain-Driven Design](https://lyz-code.github.io/blue-book/architecture/domain_driven_design/)
- [FastAPI](https://fastapi.tiangolo.com/) · [Pydantic v2](https://docs.pydantic.dev/) · [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/)
- [uv package manager](https://docs.astral.sh/uv/)
- [LangGraph](https://langchain-ai.github.io/langgraph/)
