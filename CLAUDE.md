# CLAUDE.md — agent-orchestration-core

This file tells Claude Code how this codebase is structured, what invariants to respect, and how to contribute safely. Read it before writing code.

---

## What this project is

A **multi-tenant cognitive orchestration engine** — not a chatbot, not an LLM wrapper. It governs the execution of versioned flows built from deterministic node graphs, where LLM calls are isolated to classification/formatting decisions and all side-effects (tool calls, writes) are explicit and auditable.

The canonical design doc is [`docs/Architecture/ARCHITECTURE.md`](docs/Architecture/ARCHITECTURE.md).

---

## Project layout

```
src/
├── domain/          # Business logic, organized by bounded context
│   ├── agents/
│   ├── ai_policy/
│   ├── auth/
│   ├── common/      # Shared schemas (error, versioning, change log)
│   ├── context/     # Memory extraction, RAG activation, retrievers
│   ├── conversation/
│   ├── execution/   # Core runtime — THIS is the main execution engine
│   │   └── services/graph_runtime/   # node registry, executor, edge evaluator
│   ├── flows/
│   ├── governance/  # Policies, rate limits, scopes, authoring audit
│   ├── human_sla/
│   ├── llm/
│   ├── mcp_registry/
│   ├── onboarding/
│   ├── prompts/
│   ├── rag/
│   ├── tenants/
│   ├── tools/
│   ├── user_input/
│   └── user_prompts/
├── adapters/        # External integrations (LLM, RAG, cache, jobs, MCP)
├── infra/           # SQLAlchemy models, Alembic migrations, HTTP executor
├── services/        # Cross-cutting boundaries (ExecutionBoundary, ConversationBoundary)
├── utils/           # Auth helpers, query compiler
├── app.py           # FastAPI factory + DI wiring
├── containers.py    # dependency-injector container
├── rest.py          # Middleware + route registration
└── settings.py      # pydantic-settings config from env vars
tests/
├── unit/
├── integration/
└── bdd/
docs/                # MkDocs site source
```

Each bounded context under `src/domain/<context>/` follows this internal layout:

```
<context>/
├── controllers/   # FastAPI route handlers
├── repositories/  # Persistence ports (Protocol or ABC)
├── schemas/       # Pydantic request/response models
└── services/      # Business logic
```

---

## Architectural invariants — never break these

1. **`tenant_id` always comes from the JWT security context**, never from the request body. All domain objects are scoped to a tenant.

2. **Domain code does not import from `infra/` or `adapters/`**. Dependency direction is inward: adapters/infra depend on domain protocols; domain does not depend on adapters.

3. **Published versions are immutable**. Once a `FlowVersion`, `AgentVersion`, `AIExecutionPolicyVersion`, etc. reaches `PUBLISHED` state, its payload must not change. Create a new version instead.

4. **Execution never mutates definitions**. `FlowRun`, `NodeRun`, `AgentRun`, and `ToolRun` are append-only records. They reference versioned artefacts but do not alter them.

5. **LLM calls stay within node implementations**. The LLM classifies, extracts, or formats. Tool invocations, DB writes, and external HTTP calls happen deterministically in node executor logic outside the LLM call.

6. **Idempotency keys are required on POST execution endpoints**. When writing tests or client code, always pass `Idempotency-Key`.

---

## How to navigate the codebase

### Entry points

| Question | Where to look |
|----------|--------------|
| How does a flow run start? | `src/domain/execution/services/execution_service.py` |
| How does graph execution work? | `src/domain/execution/services/graph_runtime/executor.py` |
| What node types exist? | `src/domain/execution/services/graph_runtime/node_registry.py` |
| How are routes wired? | `src/rest.py` |
| How is DI configured? | `src/containers.py` |
| How is the app started? | `src/app.py` |
| Where are ORM models? | `src/infra/database/models/` |
| Where are DB migrations? | `src/infra/database/migrations/` |
| How does JWT auth work? | `src/domain/auth/services/auth_service.py` |
| How is tenant isolation enforced? | `src/services/execution_boundary.py` |

### Finding a domain service

Each context has a primary service: `src/domain/<context>/services/<context>_service.py`. For example:
- `src/domain/flows/services/flows_service.py`
- `src/domain/rag/services/rag_service.py`
- `src/domain/governance/services/governance_policies_service.py`

### Graph runtime node types

Built-in nodes live in `src/domain/execution/services/graph_runtime/nodes/`. Each maps to a `FlowGraphSnapshot` node type (e.g., `IntentClassifier`, `ToolResolver`, `ResponseBuilder`, `HumanFallback`). To add a new node type, register it in the node registry and implement the executor interface.

---

## Development workflow

### Setup

```bash
uv sync --all-extras --all-groups
source .venv/bin/activate
docker compose up -d postgres redis
export DATABASE_URL='postgresql+asyncpg://postgres:password@127.0.0.1:5432/agent_router'
make migrate
```

### Run the app locally

```bash
PYTHONPATH=src uvicorn src.app:app --reload --port 8000
```

### Tests

```bash
uv run python -m pytest                          # full suite with coverage
uv run python -m pytest tests/unit -q            # unit only
uv run python -m pytest tests/unit --cov=src --cov-fail-under=0 -q  # local iteration, no gate
```

CI enforces **≥95% coverage** on the measured surface. The omit list in `pyproject.toml` excludes low-ROI adapters, controllers, and some experimental services from the denominator — do not add new omits without justification.

### Pre-commit

```bash
uv run pre-commit install
uv run pre-commit run --all-files   # ruff + vulture
```

Ruff is configured for `E9` and `F` rules only (errors and unused imports). Vulture detects dead code; there is a `vulture_whitelist.py` at the root for legitimate false positives.

### Makefile shortcuts

| Target | What it does |
|--------|-------------|
| `make migrate` | `alembic upgrade head` via uv |
| `make seed-demo` | Load demo tenant/flow/agent data |
| `make pc-config` | Install pre-commit hooks |
| `make pc-run-all` | Run pre-commit on all files |
| `make validate-test` | Validation suite (needs running Docker services) |
| `make test-flow-demo` | Exercise demo flow via REST |

---

## Writing code in this project

### Adding a new domain service

1. Create `src/domain/<context>/services/<name>_service.py` — no direct infra imports.
2. Inject the repository via the class constructor (dependency-injector wires this).
3. Register the service in `src/containers.py`.
4. Write a unit test in `tests/unit/<context>/test_<name>_service.py` using mocked repositories.

### Adding a new repository

1. Define the protocol/ABC in `src/domain/<context>/repositories/<name>_repository.py`.
2. Implement the SQLAlchemy version alongside the protocol or in a separate `infra` file.
3. Wire the implementation in `src/containers.py`.
4. Test the protocol boundary; integration tests can hit the real DB.

### Adding a database migration

```bash
PYTHONPATH=src uv run alembic revision --autogenerate -m "short description"
# Review the generated file in src/infra/database/migrations/versions/
PYTHONPATH=src uv run alembic upgrade head
```

Always review autogenerated migrations before committing — SQLAlchemy's diff can miss edge cases (e.g., server defaults, sequences, index changes).

### Adding a new node type

1. Implement the node executor in `src/domain/execution/services/graph_runtime/nodes/`.
2. Register it in `src/domain/execution/services/graph_runtime/node_registry.py`.
3. Add it to the node type enum / schema if it needs to appear in `FlowGraphDraft`.
4. Document it in `docs/Execution/graph-runtime/nodes/`.

### Versioned artefacts

All artefacts with a `*Version` model follow the same lifecycle. Triggering `publish` makes the version immutable. Use the `AuthoringEvent` service to log every lifecycle transition with a `justification`.

---

## Testing patterns

- **Unit tests** mock repositories and external adapters via `pytest-mock`. No DB, no network.
- **Integration tests** require running Postgres and Redis. Mark with `@pytest.mark.integration`.
- **BDD tests** (`tests/bdd/`) use pytest-bdd with Gherkin feature files. Mark with `@pytest.mark.bdd`.
- **Validation suite** (`@pytest.mark.validation_integration`) runs against a full Docker Compose stack. Excluded from default `pytest` run.

Fixtures that are used across multiple test modules live in `tests/conftest.py`.

---

## Key documentation

| Topic | Location |
|-------|----------|
| Architecture overview | `docs/Architecture/ARCHITECTURE.md` |
| Runtime vs authoring | `docs/Architecture/runtime-vs-authoring.md` |
| Domain model | `docs/Models/domain-overview.md` |
| Full tenant setup guide | `docs/Get-Started/full-tenant-configuration.md` |
| Execution graph runtime | `docs/Execution/graph-runtime/` |
| RAG pipeline | `docs/RAG/` |
| LLM layer | `docs/LLM/` |
| Governance policies | `docs/Governance/` |
| Glossary | `docs/Glossary/index.md` |
| Tracing and cost | `docs/Develop/tracing-and-cost.md` |
| Coverage loop | `docs/Develop/coverage-incremental-loop.md` |
| Dead code pipeline | `docs/Develop/dead-code-pipeline.md` |
| MkDocs contributing | `docs/Contributing/README.md` |

---

## Things to avoid

- **Do not import `src/infra/` or `src/adapters/` from `src/domain/`**. If you need an external capability in a domain service, define a protocol and inject it.
- **Do not mutate a published version's payload**. If something needs to change, publish a new version.
- **Do not hardcode `tenant_id`** anywhere. Always resolve it from `SecurityContext` or the injected dependency.
- **Do not add rows to the coverage `omit` list** without a documented reason. The 95% gate exists for a reason.
- **Do not skip pre-commit hooks** (`--no-verify`). Fix the linting or dead-code issue instead.
- **Do not add error handling for scenarios that cannot happen**. Trust internal invariants and framework guarantees; validate only at system boundaries (JWT claims, request body, external API responses).