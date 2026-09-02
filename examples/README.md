# Examples

Runnable reference scenarios for `agent-orchestration-core`.

Every example here is **self-contained**: none of them require a service you do not have. Each
prints a narrated trace and exits non-zero if the runtime does not behave as described, so they
double as executable documentation.

## Two families

| Family | What it exercises | Needs the API? |
|--------|-------------------|----------------|
| **Node examples** (`examples/*.py`) | One graph-runtime node in isolation, in-process | no |
| **API examples** (`examples/full_tenant_setup.py`, `examples/scenarios/*.py`) | The real REST surface, end to end | yes |
| **Payments example** ([`examples/payments/`](payments/README.md)) | A FastAPI payments API imported from its own `openapi.json`, reviewed and partly approved | yes |
| **RAG examples** ([`examples/rag/`](rag/README.md)) | Chunking strategies, embedding widths, retrieval tuning, activation gates | two of four |
| **Document examples** ([`examples/documents/`](documents/README.md)) | PDF/text to prompt text and to a RAG corpus, via Docling | no |

All prompts, tenant knowledge and RAG corpora in these examples are in English.

## Node examples

No database, no API, no tenant. Three need no infrastructure at all.

```bash
PYTHONPATH=src uv run python -m examples.context_compaction
PYTHONPATH=src uv run python -m examples.tool_retry_loop
PYTHONPATH=src uv run python -m examples.memory_commit_outcomes

docker compose up -d temporal
PYTHONPATH=src uv run python -m examples.scheduled_tool_run
```

- **`context_compaction`** — `ContextSummarizer` is size-gated: below `min_payload_bytes_to_run`
  it returns without spending a token. Shows the skip path, the compaction metrics, and the
  opt-in `replace_source_output` flag.
- **`tool_retry_loop`** — when `ToolErrorHandlerNode` routes back over a `LOOP` edge, only the
  operations in `retry_operation_ids` re-execute; already-successful ones are carried forward
  instead of being charged twice.
- **`memory_commit_outcomes`** — `MemoryCommitNode` reports `persisted` plus a `reason_code`, and
  returns `ERROR` when a write was attempted and failed.
- **`scheduled_tool_run`** — a real `ScheduledToolRunWorkflow` on the local Temporal dev server:
  `WAITING → EXECUTING → COMPLETED`, with the side effect deferred by a durable timer.

## API examples

These replicate the `demo / financial-assistance` folder of
`resources/collections/aoc.postman_collection.json` against a running service.

### Prerequisites

```bash
docker compose up -d postgres redis temporal
make migrate
PYTHONPATH=src uv run uvicorn src.app:app --port 8000
```

`.env` must contain `JWT_SECRET`, `JWT_ISSUER`, `JWT_AUDIENCE` (the examples mint their own
bootstrap token from these) and a working `OPENAI_API_KEY` — the flow makes real LLM calls for
moderation, tool selection, slot filling and response rendering.

### 1. Provision a tenant

```bash
PYTHONPATH=src uv run python -m examples.full_tenant_setup
```

~113 API calls covering the whole authoring surface: tenant, tenant token, model catalog, LLM
provider config, AI execution policy, tool import, RAG (vector store, chunking rule, config,
ingest, publish), agent + version lifecycle, node prompts, flow + version, nodes, graph draft →
validate → publish → compile → activate, bindings, runtime policy, five governance policies, a
user prompt and an MCP server.

It writes every captured id to `examples/.state/full_tenant_setup.json`, which the scenarios read.
It is safe to run repeatedly — each run provisions a fresh tenant.

The upstream tool API is a local stub (`examples/api/expense_api.py`) that serves the bundled
`resources/scripts/seeds/demo/openapi/demo_api.json` and implements `POST /createExpense`. It runs
in-process, so nothing external is required.

### 2. Scenarios

```bash
PYTHONPATH=src uv run python -m examples.scenarios.run_conversation
PYTHONPATH=src uv run python -m examples.scenarios.tool_failure_and_sla
PYTHONPATH=src uv run python -m examples.scenarios.scheduled_tool_execution
PYTHONPATH=src uv run python -m examples.scenarios.inspect_execution
```

| Scenario | Demonstrates |
|----------|--------------|
| `run_conversation` | A full turn: moderation → tool resolution → slot filling → tool execution → response. Asserts the upstream tool was called exactly once with the extracted parameters. |
| `tool_failure_and_sla` | A failing upstream: one bounded retry, then escalation. Asserts the tool ran exactly twice and the SLA case carries `fallback_reason: TOOL_FAILURE` rather than the old `LOW_CONFIDENCE` default. |
| `scheduled_tool_execution` | Publishes a second flow version whose `ToolExecutor` uses `scheduling.mode = "scheduled"`, then proves the side effect was deferred to a Temporal timer and the upstream was not called. Restores the immediate version at the end. |
| `inspect_execution` | Everything the platform records for one turn: flow run fields, node runs, execution events, graph state, agent runs, token usage. |

Scenarios reuse the port the stub held during provisioning, because the imported `tool_config`
stores an absolute `url`.

## Payments example

A market-standard payments API — charge, capture, refund, list, look up, pay out, balance — served
by a real FastAPI app, imported as tools from its own `openapi.json`, then reviewed and only partly
approved before the agent is allowed near it.

```bash
PYTHONPATH=src uv run python -m examples.payments.setup

PYTHONPATH=src uv run python -m examples.payments.charge_and_refund
PYTHONPATH=src uv run python -m examples.payments.read_only_queries
PYTHONPATH=src uv run python -m examples.payments.withheld_operation
PYTHONPATH=src uv run python -m examples.payments.declined_charge
PYTHONPATH=src uv run python -m examples.payments.upstream_failure_and_sla
```

See [`examples/payments/README.md`](payments/README.md) for the operation table, the approval gate,
and why path parameters, `operationId` collisions and the retrieval threshold all matter.

## RAG examples

The retrieval stack has its own set, with its own README:

```bash
PYTHONPATH=src uv run python -m examples.rag.chunking_strategies          # no infrastructure
PYTHONPATH=src uv run python -m examples.rag.corpus_kinds_and_activation  # no infrastructure
PYTHONPATH=src uv run python -m examples.rag.retrieval_tuning             # needs the API
PYTHONPATH=src uv run python -m examples.rag.embedding_dimensions         # needs the API
```

See [`examples/rag/README.md`](rag/README.md) for the chunking-strategy catalog, the
`embedding` / `indexing_embedding` pair, retrieval tuning, and the activation gate chain.

## Document examples

How an uploaded PDF becomes prompt text or a RAG corpus. Neither needs infrastructure:

```bash
PYTHONPATH=src uv run python -m examples.documents.document_to_text
PYTHONPATH=src uv run python -m examples.documents.media_pipeline

# with real Docling PDF conversion
uv sync --extra docling
DOCLING_ENABLED=true PYTHONPATH=src uv run python -m examples.documents.document_to_text
```

See [`examples/documents/README.md`](documents/README.md).

## Non-obvious things these examples encode

Each of these cost a debugging cycle and is called out inline where it applies.

**Bootstrap.** There is no unauthenticated route to create the first tenant. A client self-mints
an HS256 JWT from `JWT_SECRET`/`JWT_ISSUER`/`JWT_AUDIENCE`. That bootstrap token **omits** the
`tenant_id` claim, which is permitted only when `tenants:create` is among the scopes; a tenant-less
principal is what allows `/auth/tenant-token` to mint for a tenant it does not itself belong to. A
token that *does* carry a `tenant_id` may only mint for that same tenant.

The minted token inherits the caller's scopes **except `tenants:create`**, which is never
delegated — otherwise a tenant token could mint tokens for other tenants. So the bootstrap token
must already carry every scope you will need, and the tenant token it returns cannot mint again.

**Tool import is URL-only.** `POST /tools/import-tools` accepts `openapi_url` and fetches it
server-side; there is no inline-document field. That is why the examples run a local stub. The
response is `tools: list[Tool]`, so `tools[0].id` is a **tool** id — the Postman collection stores
it as `tool_config_id`, and the agent-version binding then fails with `404 tool_config_not_found`.
Resolve the real config through `GET /tool-configs` and publish it.

**Graph node ids must be real `node` rows.** `node_step_runner` creates every `NodeRun` with
`node_id=UUID(current_node_id)` against a `RESTRICT` foreign key, so a graph cannot reference
invented UUIDs. The Postman graph works only because it hardcodes ids that `make seed-demo`
already created.

**Ordering.** `nodes:custom` upserts the graph draft and resets it to `DRAFT`, and `graph:compile`
requires a **PUBLISHED** flow version plus a **VALIDATED** draft. The only order that works is:
create nodes → draft → validate draft → validate version → publish → compile → activate. Compile
is one-shot; a second call returns `404 flow_graph_snapshot_exists`.

**ToolResolver retrieves, it does not read bindings.** It runs a vector search over documents
whose `source` and `doc_type` are `tool_catalog` and whose metadata carries a real
`tool_config_id`, then intersects the result with the agent version's bindings. Without those
documents it returns `[]` and no tool is ever selected. It resolves its corpus from the **node
row's** `rag_config_id`, so every node needs one and they must all agree.

**Nothing writes those catalog documents for you.** `ToolsService` would index one per imported
operation, but `containers.py` constructs it without `tool_catalog_indexer`, so the parameter
defaults to `None` and the call returns early. Provisioning ingests the catalog itself.

**The retrieval threshold is lower than it looks.** `ToolCatalogRetriever` applies
`min(config threshold, 0.42)`. Correct matches score 0.32–0.58 with `text-embedding-3-large`, so a
config threshold of 0.5 silently drops the loosely worded half of the intent space and the resolver
returns `[]` without calling the LLM. The examples use 0.25. Documents are embedded with
`indexing_embedding` and queried with the **same** model truncated to `embedding.dimension` —
pointing `embedding` at another model family compares incompatible vector spaces and scores
everything near 0.05.

**Path parameters are never interpolated.** The parser merges them into the request schema as
ordinary properties, and neither `effective_tool_http_url` nor `HttpToolExecutor` substitutes them,
so an imported `/things/{id}` is called with the literal `{id}` in the URL. Keep identifiers in the
body or the query string.

**`operationId` becomes a globally unique `Tool.name`.** It is not tenant-scoped, and re-importing
into the same tenant adds a second **published** config (`1.0.1`) without deprecating the first,
which surfaces later as `ready_operation_tool_config_ambiguous`.

**Imported tools require interaction metadata.** `import-tools` always binds the upstream
`Authorization` header to `interaction_metadata_key: end_user_authorization`. A flow run
without that key in `metadata` fails every tool call with `interaction_metadata_header_missing`.

**Governance fails closed, per action.** Once a tenant has a published access policy, `rules.allow`
is a strict allowlist and anything missing is `403 action_not_allowed`. Rate limiting resolves a
**published version per action**, so every action needs its own version.

**Config validation errors surface as 500.** `nodes:custom` runs `validate_node_config`, whose
`ValidationError` escapes uncaught. `MemoryCommitNode` (`schema_id`, `rag_config_id`) and
`ContextSummarizer` (`source_node_id`) have required config fields.

**An upstream 4xx/5xx counts as a successful tool run.** `HttpToolExecutor` never calls
`raise_for_status`, and `tool_orchestrator` writes `ToolRunStatus.SUCCESS` for any response it
receives. Only transport-level failures (timeout, connection hangup) reach the retry and fallback
path — which is why `tool_failure_and_sla` makes the stub hang up rather than return 503. This is
a documented limitation; see [Known limitations](../docs/Develop/limitations.md).

## Layout

```
examples/
├── api/                       shared client, bootstrap token, upstream stubs, provisioning
│   ├── client.py              HTTP client with step logging, idempotency keys, SSE support
│   ├── expense_api.py         local OpenAPI + POST /createExpense stub with failure injection
│   ├── payments_api.py        FastAPI payments API, 7 operations, failure injection
│   ├── provisioning.py        the domain-agnostic tenant stages, shared by both setups
│   ├── runtime.py             flow-run helpers shared by every scenario
│   ├── node_prompts.json      the 11 node prompts, with their output schemas
│   ├── state.py               captured ids shared between provisioning and scenarios
│   └── tokens.py              self-minted bootstrap JWT
├── payments/                  the payments API example, setup and scenarios
├── scenarios/                 API scenarios that build on a provisioned tenant
├── full_tenant_setup.py       the whole authoring surface, in order
└── *.py                       node-level examples (no API required)
```
