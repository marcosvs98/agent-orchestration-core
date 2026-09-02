# agent-orchestration-core

A self-hostable, multi-tenant agent orchestration platform where every run is pinned to the exact definitions and policies that governed it.

**Who it is for.** Platform and backend engineers embedding AI workflows in a multi-tenant product,
who must be able to explain months later why a given run did what it did.

**Who it is not for.** If you want the fastest path from idea to a working agent in one afternoon,
choose [LangGraph](https://github.com/langchain-ai/langgraph) or
[CrewAI](https://github.com/crewAIInc/crewAI) — they have the ecosystem, and this project asks you to
model tenants, policies and versions before your first run.

**The problem it solves.** AI workflows that touch real systems need to be governed and
reconstructable, but most orchestration tools treat tenancy, admission control and run provenance as
the adopter's problem.

## What is different here

Measured against seven comparable platforms — LangGraph Platform, AWS Bedrock AgentCore, Google
Vertex AI Agent Engine, Azure AI Foundry Agent Service, Dify and Vellum — on a
[published rubric](specs/001-market-positioning/analysis.md):

| | This project | Best of the seven |
|---|---|---|
| Every run records content hashes of the graph, runtime policy and tool catalog that governed it | **yes** | stores version ids, not hashes |
| Authorization, per-principal rate limit and budget enforced in-engine before the first token | **yes, non-bypassable** | enforced at the API edge |
| Tenant identity derived from credentials and enforced across data, policy and tool registry | **yes** | tenant at the data layer only |
| Published definitions immutable; changes require a new version, audited with a justification | **yes** | versioned, unaudited |

Where it is weaker: human-in-the-loop has a persisted pause but no declarative SLA policy on it
(Dify and n8n do this better), and the ecosystem around it is a fraction of LangGraph's. The full
scoring, including every dimension where a competitor wins, is in the
[analysis](specs/001-market-positioning/analysis.md).

## Try it in one command

```bash
docker compose up -d && curl -s localhost:8000/health
```

Full setup, including the demo tenant and a worked flow run, is in [§6 Setup](#6-setup).

---

## 1. System context

```mermaid
flowchart LR
  U["Channels<br/>web · messaging · API"] --> API["agent-orchestration-core<br/>REST /core/v1"]
  MCPC["MCP clients<br/>IDEs · external agents"] --> API
  API --> EXT["Tenant HTTP APIs<br/>imported from openapi.json"]
  API --> PROV["LLM / embedding providers"]
  API --> DB[("PostgreSQL + pgvector")]
  API --> RD[("Redis")]
  API --> OBS["OpenTelemetry · structlog"]
  API --> TMP["Temporal<br/>durable execution"]
```

| Problem | Approach |
|---------|----------|
| Uncontrolled AI side effects | The LLM only classifies, extracts, routes, or formats; effects execute deterministically |
| Reproducibility | Runs are append-only and fully traceable to the exact versions they used |
| Version drift | Every artefact is versioned and immutable once published |
| Multi-tenant leakage | `tenant_id` is structural and always derived from the JWT |
| Authoring vs runtime confusion | Definitions are immutable; execution never mutates definitions |

---

## 2. Architecture

Hexagonal architecture with DDD bounded contexts. Dependencies point inward: adapters and
infrastructure implement domain contracts, never the reverse.

```mermaid
flowchart TB
  subgraph edge["Adapters · src/adapters, src/infra"]
    HTTP["FastAPI controllers"]
    MCPGW["MCP gateway (FastMCP)"]
    WRK["Temporal worker · ARQ jobs"]
    PERS["SQLAlchemy · Alembic"]
    PROV["LLM · embedding · blob · secrets"]
  end
  subgraph app["Application · app.py, containers.py, services/"]
    BOUND["ExecutionBoundary<br/>ConversationBoundary"]
  end
  subgraph dom["Domain · src/domain/**"]
    EXEC["Execution + graph runtime"]
    FLOW["Flows · Agents · Prompts"]
    KNOW["RAG · Context · LLM"]
    GOV["Governance · AI policy · Auth · Tenants"]
    TOOL["Tools · MCP registry · Human SLA"]
  end
  HTTP --> BOUND
  MCPGW --> BOUND
  WRK --> BOUND
  BOUND --> EXEC
  EXEC --> FLOW & KNOW & GOV & TOOL
  dom -.->|ports| PERS & PROV
```

### Two planes

| Plane | Purpose | States |
|-------|---------|--------|
| Authoring | Define and version flows, agents, tools, policies | `DRAFT → VALIDATED → PUBLISHED → DEPRECATED → DISABLED` |
| Runtime | Execute published versions, never mutate them | `CREATED → RUNNING → COMPLETED / FAILED` |

```mermaid
flowchart LR
  subgraph authoring["Authoring plane"]
    D["Draft"] --> V["Validated"] --> P["Published"]
    P --> DEP["Deprecated"] --> DIS["Disabled"]
  end
  subgraph runtime["Runtime plane"]
    FR["FlowRun"] --> NR["NodeRun"] --> AR["AgentRun / ToolRun"]
    NR --> EV["ExecutionEvent (append-only)"]
  end
  P -->|"FlowGraphSnapshot (immutable)"| FR
```

### Request path

```mermaid
sequenceDiagram
  participant C as Client
  participant B as ExecutionBoundary
  participant S as ExecutionService
  participant G as Graph runtime
  participant N as Node (LLM / tool / router)
  C->>B: POST /core/v1/executions/flow-runs + Idempotency-Key
  B->>B: rate limit → scope authorization → idempotency
  B->>S: ingest interaction, create FlowRun
  S->>G: load FlowGraphSnapshot, build execution plan
  loop until terminal node
    G->>N: execute node with resolved runtime policy
    N-->>G: output + events
    G->>G: edge evaluation → next node
  end
  G-->>S: GraphState + ExecutionEvents
  S-->>C: FlowRun result
```

---

## 3. Bounded contexts

Each maps one-to-one to `src/domain/<package>/`; shared helpers live in `src/domain/common/`.

| Group | Contexts |
|-------|----------|
| Execution stack | **Execution** (graph runtime, state machine, hooks), **Flows** (graph definition, compilation, validation) |
| Inference and memory | **LLM** (layered inference, executor, providers, semantic cache), **RAG** (embeddings, vector stores, chunking), **Context** (layered memory, RAG activation) |
| Integrations | **Tools** (contracts, OpenAPI import, HTTP execution), **MCP registry** (tenant MCP servers, gateway), **User prompts** |
| Agents and conversation | **Agents**, **Conversation** (sessions, SSE), **Prompts** |
| Policy and identity | **Governance** (scopes, rate limits, authoring audit), **AI policy**, **Auth**, **Tenants**, **Human SLA** |
| Onboarding | **Onboarding** (structured step flows) |

---

## 4. Engineering highlights

### HTTP-to-MCP conversion from `openapi.json`

Any HTTP API described by an OpenAPI document becomes tenant-scoped tool contracts and, without
further code, MCP tools served to external clients.

```mermaid
flowchart LR
  S["openapi.json"] --> I["POST /tools/import-tools"] --> TC[("tool_config<br/>published, versioned")]
  TC --> GR["Graph runtime<br/>ToolOrchestrator"]
  TC --> MB["MCP server binding"] --> GW["FastMCP gateway"] --> CL["MCP client"]
  GR --> API["Target HTTP API"]
  GW --> API
```

Operations are flattened into a single JSON Schema (body + path + query, `$ref` resolved), base URLs
are resolved from `servers` or the fetch origin, and end-user credentials are late-bound per call
through `interaction_metadata_key` headers.
Details: [OpenAPI to MCP](docs/Tools/openapi-to-mcp.md).

### RAG and CAG

Retrieval decides what enters the prompt; caching decides what can be skipped.

```mermaid
flowchart TB
  Q["Node request"] --> AC{"Semantic answer cache"}
  AC -->|hit| R["Result · InferenceLayer=CACHE · cost 0"]
  AC -->|miss| CTX["Layered context<br/>session · tenant knowledge · user memory"]
  CTX --> LAD["SLM → LLM ladder"] --> R
  CTX --> QC["Query-embedding cache"]
  LAD -->|persist| AC
```

Governed activation, metadata-filtered vector search, chunking strategies, query-embedding cache,
answer cache, and definition caches are documented in
[Context and cache strategy](docs/Architecture/context-and-cache-strategy.md).

### Deterministic output budgeting

`CompletionBudgetPolicy` derives `max_tokens` for structured outputs from the serialized output JSON
Schema (tiktoken `cl100k_base`, schema factor, safety margin, floor), capped by policy. Structured
outputs are further composed with tool request schemas for strict slot filling.
Details: [Structured output and budget](docs/LLM/structured-output-and-budget.md).

### Durability and observability

Flow runs and scheduled tool runs can execute under Temporal; every step emits append-only execution
events plus OpenTelemetry spans with token and cost attribution.
Details: [Durable execution](docs/Execution/durable-execution.md) · [Tracing and cost](docs/Develop/tracing-and-cost.md).

---

## 5. Technology

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.14, FastAPI, uvicorn |
| Validation | Pydantic v2 |
| Persistence | SQLAlchemy 2.0 async, asyncpg, PostgreSQL + pgvector, Alembic |
| Cache and limits | Redis |
| Graph execution | LangGraph |
| Durable execution | Temporal (`temporalio`) |
| Inference | OpenAI SDK, llama-cpp-python (local SLM), instructor, tiktoken |
| MCP | fastmcp |
| Async jobs | ARQ |
| Observability | OpenTelemetry (Collector, Tempo, Prometheus, Loki, Grafana), structlog |
| DI | dependency-injector |
| Tooling | uv, Docker Compose, pytest, ruff, vulture |

---

## 6. Setup

### Docker Compose

```bash
docker compose up -d          # postgres, redis, temporal, app, worker
docker compose logs -f app
docker compose --profile docs up -d docs   # documentation site on http://localhost:8001
docker compose down
```

Postgres and Redis data are bind-mounted to `./docker-volumes/`; `docker compose down -v` does not
remove them. Reset with `rm -rf docker-volumes/postgres docker-volumes/redis`.

### Local

```bash
uv sync --all-extras --all-groups
source .venv/bin/activate
cp env.example .env
docker compose up -d postgres redis

export DATABASE_URL='postgresql+asyncpg://postgres:password@127.0.0.1:5432/agent_router'
make migrate
PYTHONPATH=src uvicorn src.app:app --reload --port 8000
```

`PYTHONPATH=src` is required — the application uses absolute imports rooted at `src/`.

### Environment variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:5432/db` |
| `REDIS_URL` | `redis://localhost:6379/0`; falls back to `REDIS_HOST`/`REDIS_PORT`/`REDIS_DB` |
| `JWT_SECRET` / `JWT_ISSUER` / `JWT_AUDIENCE` | JWT validation |
| `ADMIN_API_KEY` | Platform-operator credential for `/admin/llm/*` (`X-Admin-Key`) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP/HTTP collector endpoint (default `http://localhost:4318`) |
| `TOOL_IMPORT_DEFAULT_BASE_URL` | Fallback base URL for imported OpenAPI tools |
| `EXPOSE_API_DOCS` | Serves `/docs`, `/redoc` and `/openapi.json`; true only when `ENVIRONMENT=development` |
| `TEMPORAL_ENABLED` / `TEMPORAL_HOST` | Durable execution |
| `CACHE_SILENT_MODE` | `true` (default) absorbs Redis failures; `false` fails hard |

`env.example` documents every setting the service reads, with its real default.

### Make targets

```bash
make migrate            # alembic upgrade head
make seed-demo          # load the demo tenant from committed SQL
make seed-demo-python   # regenerate it from the Python seeds (needs an OpenAI key for RAG)
make seed-demo-export   # capture the result back into resources/sql/demo_seed.sql
make temporal-up        # Temporal dev server
make worker             # Temporal workers + flow-run reconciler
make test-temporal      # workflow and activity tests
make docs-up            # documentation site on :8001
make pc-config          # install pre-commit hooks
make pc-run-all         # run pre-commit on all files
```

`make seed-demo` applies [`resources/sql/demo_seed.sql`](resources/sql/README.md) — 51 tables
including the RAG corpus with its embedding vectors. It needs a migrated database and nothing else:
no OpenAI key, no second service. The Python seeds remain the generator behind it, because the
graph hash and the embeddings have to be computed before they can be captured.

For an API-driven walkthrough instead, use [`examples/`](examples/README.md):

```bash
PYTHONPATH=src uv run python -m examples.full_tenant_setup
PYTHONPATH=src uv run python -m examples.scenarios.run_conversation
```

---

## 7. API surface

Every endpoint requires a JWT Bearer token carrying `tenant_id`, `principal_type`, `principal_id`,
and `scopes`. POST operations on the execution plane require an `Idempotency-Key` header.

### Control plane — `/core/v1/*`

| Group | Key endpoints |
|-------|--------------|
| Tenants | `GET /tenants/current`, `GET /tenants/current/settings` |
| Flows | `GET/POST /flows`, `POST /flows/{id}/versions` |
| Nodes and routing | `POST /nodes`, `POST /routers`, `POST /routing-rules` |
| Agents | `GET/POST /agents`, `POST /agents/{id}/versions` |
| Tools | `POST /tools/import-tools`, `GET /tools`, `POST /tool-configs` |
| MCP | `POST /tenants/mcp-servers`, `GET /tenants/mcp-servers` |
| AI policy | `POST /ai-execution-policies`, `GET /models` |
| RAG | `GET/POST /rag-configs`, `GET /vector-stores` |
| Governance | `POST /{resource}/{id}:{publish,deprecate,disable,activate,rollback}` |
| Onboarding | `GET/POST /onboardings`, `POST /onboarding-runs` |

### Execution plane — `/core/v1/executions/*`

| Endpoint | Description |
|----------|-------------|
| `POST /flow-runs` | Create and execute a FlowRun |
| `GET /flow-runs/{id}` | FlowRun state |
| `GET /flow-runs/{id}/graph-state` | Consolidated node output state |
| `POST /tool-runs`, `POST /tool-runs/{id}:execute` | Create and execute a ToolRun |
| `GET /execution-events` | Append-only execution events |
| `GET /node-runs`, `GET /agent-runs` | Run inspection |

### MCP plane

`/core/v1/mcp-servers/{id}/mcp` — Streamable HTTP, authenticated with `X-Api-Key` or
`Authorization: Bearer`.

### Operations

`GET /health` · `GET /openapi.json`

---

## 8. Testing

```bash
uv run python -m pytest                                              # full suite with coverage gate
uv run python -m pytest tests/unit --cov=src --cov-fail-under=0 -q   # local iteration
make test-temporal
```

Suites: `tests/unit/`, `tests/integration/`, `tests/bdd/`. External dependencies are mocked through
ports; integration tests use real Postgres and Redis. No test file is suppressed — `addopts` carries
no `--ignore` entries.

| Scope | Statements | Coverage |
|-------|-----------:|---------:|
| Measured surface (CI gate ≥ 90%) | ~13,456 | ~90.7% |
| Whole codebase | ~20,712 | ~74% |

The gap is the `[tool.coverage.run] omit` list, which is being retired in tranches — security- and
execution-adjacent modules came out first and are now measured. To see the unfiltered number:

```bash
uv run python -m pytest --cov-config=/dev/null --cov=src --cov-fail-under=0
```

---

## 9. Governance model

Artefacts use `major.minor.patch`. With `source_version_id` the new version derives from that source;
without it, the patch of the latest version in scope is incremented. Versioned artefacts:
`FlowVersion`, `AgentVersion`, `OnboardingVersion`, `AIExecutionPolicyVersion`, `RagConfig`,
`ToolConfig`.

```mermaid
stateDiagram-v2
  [*] --> Draft: create
  Draft --> Published: publish
  Published --> Active: activate
  Published --> Deprecated: deprecate
  Deprecated --> Disabled: disable
  Published --> Published: rollback (new version)
```

Every transition requires a `justification` and is persisted in `authoring_event`. Scopes are declared
in `src/domain/governance/schemas/scopes.py` and enforced by `AccessPolicyService` inside
`ExecutionBoundary`; rate limits are Redis-backed.

---

## 10. Data dictionary

| Entity | Description | Scope |
|--------|-------------|-------|
| **Tenant** | Isolation root | Root of every entity |
| **Flow** / **FlowVersion** | Process definition and its immutable versions | `Tenant 1:N`, `Flow 1:N` |
| **FlowGraphSnapshot** | Compiled immutable DAG used by the runtime | `FlowVersion 1:1` |
| **FlowRun** / **NodeRun** | Execution records | `FlowVersion 1:N`, `FlowRun 1:N` |
| **Agent** / **AgentVersion** / **AgentRun** | Cognitive agent definition, versions, executions | `Tenant 1:N` |
| **Tool** / **ToolConfig** / **ToolRun** | Integration contract, tenant configuration, invocation | Global / `Tenant 1:N` |
| **AIExecutionPolicy** | Model and inference policy | Global |
| **RagConfig** / **VectorStore** | Retrieval strategy and vector index | `Tenant 1:N` |
| **GraphState** | Consolidated node output state | `FlowRun 1:1` |
| **ExecutionEvent** / **AuthoringEvent** | Append-only runtime and governance audit | `FlowRun 1:N` / `Resource 1:N` |
| **Session** / **Interaction** | Interaction context and persisted input | `Tenant 1:N` / `Session 1:N` |

ORM models: `src/infra/database/models/` · schemas: `src/domain/<context>/schemas/` ·
repositories: `src/domain/<context>/repositories/`

---

## 11. Invariants

1. `tenant_id` always comes from the security context, never from a request body.
2. Definitions are versioned and immutable after publication; execution never mutates them.
3. The LLM performs no side effects.
4. Everything material — flows, agents, prompts, policies, tools, decisions — is versioned.
5. The channel is an I/O detail; the core is medium-agnostic.
6. Domain code never imports from `src/infra/` or `src/adapters/`.

---

## 12. Documentation

Full documentation site (MkDocs Material):

```bash
docker compose --profile docs up -d docs   # http://localhost:8001
# or: uv run mkdocs serve
```

| Topic | Document |
|-------|----------|
| Architecture | [Overview](docs/Architecture/ARCHITECTURE.md) · [Runtime vs authoring](docs/Architecture/runtime-vs-authoring.md) |
| Context, RAG, CAG | [Context and cache strategy](docs/Architecture/context-and-cache-strategy.md) · [RAG](docs/RAG/index.md) · [LLM](docs/LLM/index.md) |
| Integrations | [OpenAPI to MCP](docs/Tools/openapi-to-mcp.md) · [MCP registry](docs/MCP/index.md) · [Tools](docs/Tools/index.md) |
| Execution | [Graph runtime](docs/Execution/graph-runtime/index.md) · [Durable execution](docs/Execution/durable-execution.md) |
| Operations | [Installation](docs/Get-Started/installation.md) · [Full tenant configuration](docs/Get-Started/full-tenant-configuration.md) · [Tracing and cost](docs/Develop/tracing-and-cost.md) |
| Model and terms | [Domain overview](docs/Models/domain-overview.md) · [Glossary](docs/Glossary/index.md) |
| Known limitations | [Known limitations](docs/Develop/limitations.md) |
| Repository | [CONTRIBUTING](CONTRIBUTING.md) · [DEVELOPMENT](DEVELOPMENT.md) · [SECURITY](SECURITY.md) · [examples](examples/README.md) |
