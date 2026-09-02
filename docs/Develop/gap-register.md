# Gap register — August 2026

Findings from a full-codebase audit plus a clean-environment provisioning run, produced
alongside the node work described in [What changed](#what-changed).

## How to read this

| Label | Meaning |
|-------|---------|
| **Verified** | A second reader independently opened the cited code and tried to refute the claim. It survived. |
| **Unverified** | Surveyed and cited, but the adversarial verification pass did not run for it. Treat as a strong lead, not a fact. |
| **Rejected** | Claimed by the survey, refuted on verification. Listed so nobody re-reports them. |

Coverage of the verification pass: **57 of 108** findings were verified (55 confirmed, 2 rejected).
The remaining 51 ran out of budget mid-pass. Every finding below carries file references so it can
be checked directly.

[Defects found by running the API end to end](#defects-found-by-running-the-api-end-to-end) is a
later addition and is held to a higher bar than the rest of this document: every item there was
reproduced against a live service, and five of the six are already fixed.

Everything in [Developer experience](#6-developer-experience) was reproduced first-hand on this
machine rather than read off the code, and is marked **Reproduced**.

---

## What changed

Four items from `todo.txt` were implemented. `IntentClassifier` was explicitly out of scope.

### ContextSummarizer — real compaction

`ContextSummarizer` was a 17-line class with no `execute` override. Its declared config
(`source_node_id`, `min_payload_bytes_to_run`) was enforced by `validate_node_config` at authoring
time and **never read at runtime**, and the staging key its prompt reads
(`MEMORY_CONTENT_SUMMARIZE_STAGING_KEY`) had **no writer anywhere in the repo** — so
`memory_payload_raw` was always `None`. Documentation claimed it "runs only when staged payload
exceeds `min_payload_bytes_to_run`".

It now reads the source node's output from the graph-state snapshot, measures its serialized size,
and short-circuits below the threshold without spending a token. Above the threshold it stages the
raw payload, runs the LLM, strips the staging key from the outgoing state, and reports a
`compaction` block (`payload_bytes`, `summary_bytes`, `saved_bytes`, `compaction_ratio`) on both
`data` and `metrics`.

A new `replace_source_output` flag (default `false`) makes the compaction real by replacing the
source slice. It is opt-in on purpose: the demo graph's `MemoryCommitNode` merges from
`NODE_SLOT_ID` via `data_merge` — the exact node the summarizer targets — so unconditional
replacement would break it.

- `src/domain/execution/services/graph_runtime/nodes/context_summarizer.py`
- `src/domain/flows/schemas/graph_node_config.py`

### ToolExecutor — `ToolExecutionMode.SCHEDULED`

`SCHEDULED`, `schedule_id` and `run_at` existed in the schema with no producer and no consumer,
while the demo graph already had an edge matching `HasAll(result.status, ['success', 'scheduled'])`.

Scheduling is now a first-class execution mode built on Temporal:

- `ToolRunSchedulerPort` (domain protocol) + `ToolRunScheduleRequest` / `ToolRunSchedule` schemas.
- `ScheduledToolRunWorkflow` waits on a **durable server-side timer**, then executes the tool run in
  an activity. A worker restart does not lose the schedule.
- `TemporalToolRunScheduler` starts it with `WorkflowIDReusePolicy.REJECT_DUPLICATE` keyed on the
  tool run id, and honours the existing tenant fairness setting.
- The worker now runs a second `Worker` on `TEMPORAL_TOOL_RUN_TASK_QUEUE` so scheduled tool runs do
  not compete with flow-run activity slots.

Node config accepts `scheduling: {mode, delay_seconds, run_at_param, tool_names}`. `run_at` may come
from an LLM-extracted parameter, but the node — not the LLM — decides whether to schedule, and a
past or malformed `run_at` is refused rather than executed. When no scheduler is wired the node
returns `tool_scheduler_unavailable` instead of silently firing the side effect immediately.

- `src/adapters/temporal/tool_run_{workflow,activities,dtos}.py`, `tool_scheduler.py`
- `src/domain/execution/ports/tool_run_scheduler.py`, `src/domain/execution/schemas/tool_schedule.py`

### MemoryCommitNode — honest outcomes

`_persist_memory_item` returned silently on four distinct failure paths and the node returned
`SUCCESS` with `memory_commit: "pending_persist"` regardless of what happened. A quota rejection and
a successful write were indistinguishable to the graph, to the operator, and to the audit trail.

It now returns a `MemoryCommitPersistOutcome` and the node reports `persisted` plus a `reason_code`
(`persisted`, `write_not_allowed`, `writer_unavailable`, `node_not_found`, `invalid_node_id`,
`write_failed`). A write that was attempted and failed is now `NodeExecutionStatus.ERROR`; a
deliberate skip stays `SUCCESS`.

Session memory (`NodeResult.memory`) still advances in every case — that is the node's documented
contract for this graph — but it no longer implies durable persistence.

### HumanFallback / ToolErrorHandlerNode

Two independent defects:

**Every SLA case was opened as `LOW_CONFIDENCE`.** `HumanFallback` reads
`metadata["fallback_reason"]`, but nothing in the runtime ever wrote that key, so the default fired
100% of the time and `resolve_policy(tenant_id, node, fallback_reason)` could only ever match the
`LOW_CONFIDENCE` policy — moderation blocks, tool failures and unknown intents all landed on the
wrong escalation path. `node_step_runner` now stamps a reason derived from the source node via a new
`resolve_fallback_reason` (moderation → `POLICY_BLOCK`, tool paths → `TOOL_FAILURE`, missing intent →
`UNKNOWN_INTENT`).

**The retry loop duplicated side effects.** `ToolErrorHandlerNode` computed `retry_operation_ids` but
only published it in `data`; `ToolExecutor` never read it and re-ran *every* READY operation on each
loop iteration. Because the idempotency key embeds `current_node_run_id`, which changes per
iteration, a payment that already succeeded was charged again on every retry. `tool_run.idempotency_key`
is a plain nullable column with no unique constraint and no read-before-insert, so nothing downstream
caught it either.

`ToolErrorHandlerNode` now publishes `retry_operation_ids` into state; `ToolExecutor` re-executes only
those operations, carries the already-final results forward from `finalized_results`, merges by
`operation_id`, and clears the selection. `examples/tool_retry_loop.py` demonstrates the
previously-double-charged operation being executed exactly once.

### Verification

```
972 passed, 8 deselected
Required test coverage of 95% reached. Total coverage: 95.17%
ruff check src examples — All checks passed!
```

Baseline before the change was 911 passing at 95.14% over 9,953 statements; it is now 95.17% over
10,332 statements, so the gate was met on a **larger** measured surface. 47 new tests were added
across `test_context_summarizer_node.py`, `test_memory_commit_node.py`, `test_tool_execution_node.py`,
`test_fallback_reason_resolver.py` and `test_runtime_executor.py`.

The scheduled path was additionally exercised against the real Temporal dev server
(`examples/scheduled_tool_run.py`): `WAITING → EXECUTING → COMPLETED`, side effect deferred 4.0s,
workflow queryable while parked.

---

## Defects found by running the API end to end

Building `examples/full_tenant_setup.py` — a first-principles walk through the authoring surface
against a live service — surfaced six defects that no test covered. All are **Reproduced**: each
one blocked the provisioning script at a specific step, and each fix was verified by re-running it.

Five are fixed here. One is reported, not fixed.

| # | Defect | Impact | Status |
|---|--------|--------|--------|
| 1 | `normalize_json_for_rag_hash` used `type(v) is UUID`, but asyncpg returns a `UUID` **subclass** | `activate_flow_version` 500s with `TypeError: Object of type UUID is not JSON serializable` for any flow whose nodes carry a `rag_config_id` | **Fixed** |
| 2 | `McpServer(metadata_col=...)` is not a valid keyword; the column attribute is `server_metadata` | Creating an MCP server 500s. Two `getattr(row, "metadata_col", None)` reads silently returned `None`, so outbound auth refs were invisible, and writes went to a phantom attribute | **Fixed** |
| 3 | `mcp_server_tool`, `mcp_server_vector_store`, `mcp_server_user_prompt` lack the `created_at`/`updated_at` that `ORMBaseModel` declares; `mcp_server_credential` lacks `updated_at` | Any insert fails with `UndefinedColumnError` | **Fixed** (migration `a1b2c3d4e5f6`) |
| 4 | `GraphCompiler._validate_loops` ran its DFS from **every** node in adjacency order, which is derived from sorting edges by node UUID | `cycle_not_marked_loop` at execution time for a graph that `graph:validate` accepted. Whether a valid retry loop compiled depended on the random UUIDs assigned to its nodes | **Fixed** |
| 5 | `execution_service.get_flow_run` read `event.tool_run`, which does not exist on `ExecutionEvent`, while guarding on `event.payload` | `GET /executions/flow-runs/{id}` 500s for any run with a `FlowFailed` event — exactly when a caller most needs it | **Fixed** |
| 6 | `uq_flow_deployment_slot` was `UNIQUE (flow_id, environment, status)` | Only one `INACTIVE` deployment can exist per flow, so a flow could be activated at most **twice**; the third activation — and every rollback — died on a unique violation | **Fixed** (migration `b2c3d4e5f6a7`) |
| 7 | `_chunk_text` re-emitted the final sliding window until `max_chunks_per_document` | Every document longer than `target_tokens` produced up to 100 chunks where a handful were correct — ~25× the embedding cost, `top_k` flooded with duplicates, and a false `truncated=True` | **Fixed** |
| 8 | `DoclingDocumentToText.to_text` ran a synchronous CPU-bound conversion on the event loop | Every PDF froze the whole API process for the duration — measured at 0 heartbeat ticks across a 2.2 s conversion | **Fixed** |

### Why the tests did not catch these

Defect 5 had a test that **encoded the bug**: it built a `SimpleNamespace` and set `ev.tool_run`
on it, a shape production never produces, so the assertion passed while the endpoint 500ed. That
test now uses a realistic event and asserts the parsed enum. Defects 1 and 6 had no test at all on
the module. Regression tests were added for 1, 4, 5 and 6, and each was confirmed to fail against
the unfixed code before the fix landed.

### Fixed: the token-window chunker never terminated its sliding window

`RagRuntimeService._chunk_text` advanced with `start = end - overlap_tokens`. Once `end` reached
`len(tokens)` the final window was re-emitted forever, because `start` stalled at
`len(tokens) - overlap_tokens` and every subsequent iteration produced the same slice — until
`max_chunks_per_document` cut it off.

Measured on a 202-token document with `target_tokens=60, overlap_tokens=10`:

| | before | after |
|---|--------|-------|
| chunks emitted | 100 | 4 |
| distinct chunks | 4 | 4 |
| `truncated` | `True` | `False` |

Every document longer than `target_tokens` was affected, on both `TOKEN_WINDOW` and `SEMANTIC`
(they share the code path). The impact is threefold: embedding cost inflated roughly 25× on this
input (and up to `max_chunks_per_document`× in general), `top_k` filled with near-identical copies
of one chunk so retrieval lost diversity, and `truncated=True` was reported for documents that
were never actually truncated — making the real data-loss signal untrustworthy.

The loop now breaks when the final window is emitted and advances by
`step = max(1, target_tokens - overlap_tokens)`, which also stops a pathological
`overlap >= target` config from looping. Regression tests: `tests/unit/rag/test_rag_chunking.py`
(three of them fail against the old code, one with `assert 1000 == 16`).

### Fixed: PDF conversion froze the entire API process

`DoclingDocumentToText.to_text` was declared `async def` but called the synchronous, CPU-bound
`DocumentConverter.convert()` directly on the event loop. Measured with a heartbeat coroutine
against a one-page PDF:

| | before | after |
|---|--------|-------|
| conversion time | 2.2 s | 1.9 s |
| heartbeat ticks during it | **0** | 36 |
| ticks a free loop would make | 43 | 38 |

Zero ticks means the process served nothing else for the duration: every other request, health
check and SSE stream stalled. A one-page PDF costs ~1–2 s; a scanned multi-page document costs
minutes of total unavailability, and this is reachable from both the conversation path
(`UserInputNormalizer`) and RAG media ingest. It also violates the repository's own rule against
blocking I/O in async paths.

The call now runs through `asyncio.to_thread`. `DocumentConverter` is still constructed per call,
which keeps the adapter thread-safe under concurrent conversions at the cost of ~1 s setup each
time. Regression tests: `tests/unit/adapters/test_docling_document_to_text.py` (two fail against
the old code, one with `assert 0 > 5`).

### Reported, not fixed: neither document pipeline can run in the shipped wiring

`containers.py` binds `blob_store` to `UnconfiguredBlobStore`, whose `get_bytes` raises
`blob_store_unconfigured` unconditionally, and no endpoint writes bytes into a blob store.
Confirmed against a running service:

```
POST /core/v1/rag-configs/{id}/documents:ingestFromMedia
→ 400 {"code":"DOMAIN_VALIDATION","message":"blob_store_unconfigured"}
```

Conversation media parts (`input_parts` with a `media_ref`) fail identically. Both pipelines are
otherwise complete — `examples/documents/media_pipeline.py` runs them end to end against
`MemoryBlobStore` — so the gap is a single missing adapter binding, not missing functionality.

Related: `DOCLING_ENABLED` defaults to **false**, which makes `build_document_to_text()` return
`FakeDocumentToText`. That adapter returns `[fake-extract:<mime>:<name>:len=N]` for a PDF instead
of raising, and the marker is then chunked, embedded and stored as if it were the document. A
deployment that enables blob storage but forgets `DOCLING_ENABLED` silently builds a corpus of
markers.

### Reported, not fixed: `/rag-retrieval:preview` cannot see tenant knowledge

`RagController.preview_rag_retrieval` calls `get_context(user_id=auth.principal_id)`, and
`search_similar_chunks` turns a non-null `user_id` into a hard filter on
`doc_metadata->>'user_id'`. Tenant-wide documents carry no `user_id`, so the endpoint returns
`NO_MATCHES` for precisely the corpus an operator would use it to debug. The runtime path is
unaffected — it passes `user_id=None` for `TENANT_KNOWLEDGE`. Reproduced in
`examples/rag/retrieval_tuning.py` step 2.

### Reported, not fixed: ingest dedupe is tenant-wide and crosses rag configs

Already recorded in §4 as a user-collision issue; running it produced a sharper statement.
`get_document_by_hash` filters on `(tenant_id, content_hash)` only — not `rag_config_id`, not
`user_id`. Two consequences, both reproduced in `examples/rag/retrieval_tuning.py` steps 7 and 8:

1. Identical content under different `source`, `doc_type`, `version` and `user_id` collapses into
   one row, and the first writer's `user_id` is the one retrieval filters on.
2. A document whose content already exists under **another config in the same tenant** is silently
   not added to the new config, which can then never retrieve it — behind a `202 Accepted` and a
   background task that swallows the skip. Shared boilerplate belongs to whichever config ingested
   it first.

### Reported, not fixed: upstream 4xx/5xx counts as success

`HttpToolExecutor.execute_http` never calls `raise_for_status`, so its `httpx.HTTPStatusError`
branch is dead code, and `tool_orchestrator` writes `RunStatus.COMPLETED` / `ToolRunStatus.SUCCESS`
for **any** response it receives (`src/domain/tools/services/tool_orchestrator.py:280`).

An upstream returning `503` is therefore recorded as a successful tool run. The consequences:

- the `ToolErrorHandlerNode` retry path and the `HumanFallback` escalation path are unreachable for
  HTTP errors — the single most common upstream failure mode
- `ResponseBuilder` renders an error body as a success
- tool runs that failed are billed and counted as successful

This is left unfixed deliberately: what counts as a successful tool run feeds billing policy,
circuit breakers and idempotency, so changing it is a product decision rather than a bug fix. It is
the highest-value item in this section. `examples/scenarios/tool_failure_and_sla.py` works around it
by making the stub hang up (a transport error, which *is* classified correctly).

---

## 1. Security — highest priority

Every item here is **Verified** unless marked otherwise. These are cross-tenant issues in a system
whose stated first invariant is that `tenant_id` always comes from the JWT.

**Fixed (WS1).** The five holes the recommendation called incident-grade are closed, with
regression tests in `tests/unit/security/test_cross_tenant_isolation.py`. Those tests were run
against the pre-fix tree in a detached worktree first: **13 of 14 failed**, the fourteenth being the
positive control (a tenant minting for itself). Details below the table.

| Finding | Where | Status |
|---------|-------|--------|
| `POST /core/v1/auth/tenant-token` mints a token for an **arbitrary** `tenant_id` carrying the caller's own scopes | auth controller | **Fixed** |
| `/admin/llm/*` takes `tenant_id` from the **query string** and is guarded by any authenticated tenant's JWT | admin llm routes | **Fixed** |
| `GET /core/v1/executions/execution-events` queries **across all tenants** and filters after the DB limit | execution events | **Fixed** |
| Every governance policy *version* create/publish/activate path **skips the tenant ownership check** | governance controllers | **Fixed** |
| `ExecutionBoundary` skips tenant-ownership checks on **resume, tool execution and event listing** | `src/services/execution_boundary.py` | **Fixed** |
| LLM-emitted `tool_config_id` is executed with **no tenant, binding or status validation** | tool resolution → execution | Open |
| Agent-version tool allowlist **fails open** when an agent version has no bindings | agent runtime | Open |
| Node prompts are a **global, non-tenant-scoped table** mutated by a tenant-facing endpoint | prompts controller | Open |
| Node AI-execution-policy bindings created/listed/deleted with **no tenant scoping** | ai_policy | Open |
| End-user memory/preference read API bypasses `ConversationBoundary` — no scope or principal check | context | Open |
| No egress allowlist / SSRF control on tool HTTP calls; redirects followed **with resolved secrets attached** | `HttpToolExecutor` | Open |
| MCP servers expose **unpublished** tool configs; no key rotation/revocation/deletion API | mcp_registry | Open |
| Rate limits and cost guardrails **fail open** on Redis error (`CACHE_SILENT_MODE` defaults `True`) | governance + cache | Open |
| The `Scope` taxonomy is declared but enforced on **almost no authoring controller** | authoring surface | Open |

`/docs`, `/redoc` and `/openapi.json` are unauthenticated in every environment, and CORS origins are
hardcoded to localhost. *(Unverified.)*

**Recommendation:** treat the tenant-token endpoint and `/admin/llm` as an incident-grade fix before
anything else in this document.

### What the WS1 fix changed

**Tenant-token minting.** Two rules now hold together. First, a **tenant-scoped** caller (one whose
JWT carries a `tenant_id` claim) may only mint for that same tenant; a mismatching `body.tenant_id`
raises `tenant_scope_mismatch`. Cross-tenant minting is reserved for a **tenant-less platform
principal**, which the token model already permitted only when `tenants:create` is present
(`utils/auth.py`). Second, `tenants:create` is stripped from every minted token
(`NON_DELEGABLE_SCOPES` in `auth_service.py`), so a tenant token can never mint again — this is what
breaks the unbounded pivot chain, since the endpoint's own gate requires that scope.

`examples/api/tokens.py` previously minted its bootstrap JWT with a placeholder `tenant_id`
(`…0100`). It now omits the claim, making the platform principal explicit instead of disguising it
as a tenant. Everything else in `examples/` is unchanged.

The per-process rate limiter (module-global dict, reset on every deploy, ineffective across
replicas) now increments a Redis counter, falling back to the in-process store only when Redis is
unreachable.

**`/admin/llm/*`.** The router moved from `get_auth_context` to `get_admin_auth` (`X-Admin-Key`), and
the three routes take typed request bodies instead of query parameters, so `tenant_id`,
`credential_secret_ref` and pricing no longer travel in URLs.

**Execution events.** `list_execution_events` now takes `tenant_id` at repository, service, port and
boundary level, and the `WHERE tenant_id = …` predicate is applied **before** `LIMIT` — the previous
controller-side post-filter left the page both truncated and wrong. That post-filter is retained as
defence in depth.

**Governance version paths.** All 14 create/publish/activate methods take `tenant_id`, resolve the
parent policy (directly, or through the version's `*_policy_id`) and raise **not-found** — not
forbidden — on a tenant mismatch, so the endpoints stop confirming that another tenant's UUID
exists. `activate_billing_policy_version` previously accepted `tenant_id` but only forwarded it to
`set_active_version`, which let a tenant point its own active pointer at a foreign version; that is
now blocked too.

**`ExecutionBoundary`.** The ownership check already present in `get_flow_run` is extracted into
`_assert_flow_run_tenant` and applied to `resume_flow_run` and `list_execution_events`;
`_assert_tool_run_tenant` resolves a tool run's flow run through either `node_run_id` or
`agent_run_id` and applies the same check to `execute_tool_run`.

## 2. Execution modes and durability

**Fixed (WS2):** the two critical items below. See
[Durable execution](../Execution/durable-execution.md) for the design and settings.

- ~~**Verified — critical.** Any failure after `prepare_flow_run` leaves the `FlowRun` row permanently
  stuck. There is no reconciler.~~ **Fixed.** `FlowRunReconciler` runs in the worker process, sweeps
  QUEUED/RUNNING rows whose `updated_at` is past the stale window (new
  `ix_flow_run_status_updated_at` index), asks Temporal whether the workflow is still alive, and
  fails only the abandoned ones with `flow_run_abandoned`. An unreachable engine is treated as
  "still running" so a Temporal outage cannot mass-fail live runs.
- ~~**Verified — critical.** WAITING runs are resumed **entirely outside Temporal**.~~ **Fixed.**
  `resume_flow_run` now branches on `TEMPORAL_ENABLED` exactly as `create_flow_run` does. A literal
  `signal_resume` was the wrong shape: `FlowRunWorkflow` is turn-scoped and has already returned by
  the time a WAITING run resumes, so there is nothing to signal. The raising `signal_resume` is
  replaced by `start_resume_turn`, which starts a **new** workflow at `resume_to_node_id`
  (`flow-run-{id}-t{n}`, from the new `flow_run.turn_index` column) over the graph state the previous
  turn left in Postgres. `set_flow_run_input` persists the turn's message first, because
  `execute_node` builds its context from `flow_run.input` rather than from the call.
- **Verified — high.** Activity retries re-execute the whole node, duplicating tool side effects and
  LLM spend. This is the durable-path twin of the retry defect fixed above; the fix here belongs in
  the activity boundary, not the node.
- **Verified — high.** Async mode (`wait=false`) caches a `QUEUED` response under the idempotency key,
  so retries return a permanently stale result. `201` vs `202` depends on a race with the worker, so
  callers cannot reliably tell sync from async.
- **Verified — high.** No workflow versioning strategy, for a workflow that is expected to evolve.
  Replay coverage exists but is thin (`tests/unit/temporal/test_replay.py` against recorded
  histories); there is no policy requiring a new history when the workflow changes.
- **Partly fixed — high.** The Temporal worker is absent from production deployment. Its health is
  now observable: the `worker` service declares a `healthcheck` in `docker-compose.yml`, and
  `/health` reports a `temporal` component when `TEMPORAL_ENABLED` is true. The production
  deployment gap remains.

Scheduled execution now exists (above). Cron/recurring flow execution still does not.

## 3. Cost, observability and usage tracking

**Fixed (WS5).** See [Tracing and cost](tracing-and-cost.md#spend-ledger-llm_usage_ledger).

- ~~**Verified — critical.** `agent_run.input_tokens` / `output_tokens` / `estimated_cost` … are
  **never written by the graph runtime**.~~ **Fixed.** `NodeStepRunner._record_usage` creates the
  `AgentRun` when an agent version governs the node and writes tokens and cost onto it. This also
  makes the previously unreachable `assert_can_create_agent_run` gate reachable (§5).
- ~~**Verified — high.** There is **no durable per-tenant spend ledger**.~~ **Fixed.** New
  append-only `llm_usage_ledger` table (migration `e5f6a7b8c9d0`), written after every provider
  interaction, indexed on `(tenant_id, occurred_at)`. `inference_layer` distinguishes `LLM` / `SLM` /
  `CACHE`, so cache hits are not mistaken for spend. Verified against the live database:
  `sum_llm_cost_for_tenant` returned the inserted amount.
- ~~**Verified — high.** Spend counters use non-atomic read-modify-write.~~ **Fixed.** Counters use
  `INCRBYFLOAT`; a regression test runs 20 concurrent recordings and asserts the exact sum, which
  the old GET-then-SET pair could not satisfy.
- ~~**Verified — high.** The direct conversation endpoint bypasses cost accounting.~~ **Fixed.**
  `ConversationService` computes cost through `CostEngine` and writes its own ledger row with
  `task_type=conversation_turn`. It still calls the provider adapter directly rather than through
  `LLMExecutor`, so pre-call guardrail *reservation* on that path remains open.
- ~~**Verified — high.** Latency policy enforcement is disabled behind a debug print statement.~~
  **Fixed.** `print("Que merda")` removed and the raise restored.
- **New — the guardrails failed open.** Every counter read went through `CACHE_SILENT_MODE`, which
  returns `False` on error; `float(...)` of that read as `0.0`, so budgets stopped binding exactly
  when Redis was unhealthy. Counter access now raises `GuardrailUnavailableException` (503) instead.
- **Verified — high.** Default log level is `CRITICAL`; there is no access log; there is no metrics
  endpoint and no liveness/readiness split. I confirmed the running app exposes exactly one health
  route (`/health`), against a project rule that requires `/health/live` and `/health/ready`.

## 4. Memory, context and boundaries

- **Verified — high.** **No context or token budget anywhere.** Retrieved memory and knowledge are
  concatenated unbounded into the system context.
- ~~Conversation history is delegated to the OpenAI Conversations API … no truncation, window or
  compaction … all history is silently dropped rather than summarized.~~ **Fixed (WS6).** The
  provider conversation is now **rolled**, not left to grow: `ConversationContinuityService` tracks
  turns and an estimated token total per `conversation_key`, and at the policy threshold the service
  builds a carry-forward summary, persists it to the new `conversation_summary` table (migration
  `f6a7b8c9d0e1`), and opens a **new** provider conversation seeded with it. A Redis mapping miss now
  reseeds from that summary instead of starting empty — the silent-loss path is closed.

  Owning history locally was the alternative; rolling the provider conversation was chosen to keep
  provider-side caching. The cost is that the bound is an **estimate** maintained on our side, since
  the authoritative token count lives with the provider. Stated in
  [Token cost and context strategy](token-cost-and-context-strategy.md#provider-side-conversation-rollover).

  The port (`domain/llm/ports/conversation_continuity.py`) is deliberately declared in the LLM
  domain: `tests/unit/llm/test_openai_streaming_request_payload.py` enforces that `domain/llm` never
  imports `domain/conversation`, and the first cut of this change violated it.
- **Verified — high.** Retention TTL is advisory metadata only: no eviction, no purge job, structured
  memory never expires.
- **Reproduced — high.** RAG document dedupe keyed on `(tenant_id, content_hash)` collides across users
  and RAG configs, misattributing documents. Now demonstrated end to end — see
  [the dedupe write-up above](#reported-not-fixed-ingest-dedupe-is-tenant-wide-and-crosses-rag-configs);
  the cross-config case is silent data loss behind a `202`, not just misattribution.
- **Verified — high.** `USER_CONTEXT_READ_GATE` can never be published — the publishing node was
  deprecated while the reader remains.

## 5. Agents, tools and composition

- ~~**Verified — high.** `AgentRun` records are never produced, so the agent-run governance gate is
  unreachable dead code.~~ **Fixed (WS5).** The graph runtime creates an `AgentRun` for every LLM
  node governed by an agent version, populating tokens, cost and the new
  `ai_execution_policy_version_id` column.
- **Verified — high.** Tool bindings **mutate already-published agent versions**, violating the
  immutability invariant, and there is no unbind endpoint.
- **Verified — high.** The graph runtime uses whatever agent version is bound to a node, ignoring
  status and the active-version pointer.
- **Verified — high.** **No tool composition and no agent-to-agent invocation.** Multi-tool selection
  uses the wrong parameter schema.
- **Verified — high.** MCP tool invocation bypasses the entire ToolRun / audit / governance plane.

Dynamic tool binding at runtime is therefore not supported today: bindings are static per agent
version, and the one dynamic element (LLM-chosen `tool_config_id`) is the security hole listed in §1.

## 6. Developer experience

**Reproduced** — all of the following were run on this machine.

- **The documented onboarding path is now bypassable.** `examples/full_tenant_setup.py` provisions
  a complete tenant through the public REST API with no external service (see `examples/README.md`
  at the repository root). It does not fix `seed-demo`; it removes the dependency from the critical
  path for a new developer.
- ~~**`make seed-demo` fails outright on a clean machine.**~~ **Fixed (WS3).** A fixture OpenAPI
  document is vendored at `resources/scripts/seeds/demo/openapi/uora_app_platform.json`, covering all
  35 allowlisted operations with matching paths and `operationId`s, and
  `fetch_uora_platform_tool_rows` now accepts an http(s) URL, a `file://` URL, or a filesystem path —
  defaulting to the fixture. Verified end to end against the live Postgres: `seed_01` + `seed_05`
  completed with no external service and produced **35 published `tool_config` rows** for the demo
  tenant, and the full `make seed-demo` then completed twice: once with an OpenAI key (347 RAG
  documents, 310 chunks) and once with `OPENAI_API_KEY=""`, where the two RAG seeds skip loudly and
  the bootstrap still reports success. `UORA_OPENAPI_URL` and `UORA_APP_PLATFORM_HTTP_BASE` are now
  documented in `env.example`, `README.md` and `docs/Get-Started/installation.md`.
- **The documented run command failed.** `README.md` §5.3 said `uvicorn src.app:app --reload`, which
  raises `ModuleNotFoundError: No module named 'adapters'`. `PYTHONPATH=src` is required; `CLAUDE.md`
  had it right, `README.md` did not, and the Makefile comment gives a third variant
  (`src.app:create_app --factory`). **Fixed here** — the corrected command was run end-to-end and
  `/health` returned 200 with `database` and `redis` `ok`.
- ~~**5 Makefile targets point at files that do not exist.**~~ **Fixed (WS3).** `test-flow-demo`,
  `test-flow-demo-2`, `test-trace-hierarchy`, `seed-demo2` and `serve-conversation-test` are deleted
  along with their `.PHONY` entries; `docs-up` / `docs-down` are added. Every remaining target now
  resolves to a file that exists (checked mechanically across all 18 targets).
- ~~**`env.example` covers 10 of ~70 settings.**~~ **Fixed (WS3).** It now documents **all 72**
  settings `src/settings.py` reads, grouped by concern with the real default beside each, and the
  `env.local` pointer is gone. Two dead settings were deleted rather than documented: `PYTEST_RUNNING`
  and `TRACING_ENABLE` (a near-duplicate of `TRACING_ENABLED`) had zero readers anywhere in the repo.
- ~~Temporal appeared in **zero** documentation.~~ **Fixed (WS3).**
  [Installation](../Get-Started/installation.md#temporal) now has a Temporal section covering the
  `depends_on` coupling, the two halves required to turn it on (`TEMPORAL_ENABLED` *and* a running
  worker), and the reconciler.
- **Verified here, previously unverified: `REDIS_URL` was never read.** `RedisAdapter` composed its
  URL from `REDIS_HOST`/`REDIS_PORT` and hardcoded database `0`, while `docker-compose.yml` sets
  `redis://redis:6379/3` — the documented database index was silently ignored. **Fixed:**
  `build_redis_url()` honours `REDIS_URL` when set and falls back to the discrete settings.
  *Operational note:* environments that set `REDIS_URL` with a non-zero database will move to that
  database on next deploy. Everything stored there is a TTL-bounded cache, but in-flight idempotency
  keys do not carry over.
- What *does* work, verified: `docker compose up -d postgres redis temporal` → all healthy;
  `make migrate` applied cleanly; the app boots and `/health` returns 200. `/health` now also reports
  a `temporal` component when `TEMPORAL_ENABLED` is true.

- ~~*(Unverified, from the survey: the app refuses to boot without Langfuse credentials while docs
  call Langfuse optional.)*~~ **Verified, then fixed.** The claim was correct: `TRACING_ENABLED`
  defaulted to `true` and the tracer raised `langfuse_not_configured` from `__init__`, through DI,
  inside `create_app()` — a rotated key took the whole engine offline at deploy time. The vendor has
  since been replaced wholesale by OpenTelemetry (`otel_runtime_tracer.py`); the adapter now never
  raises on missing configuration and degrades to a no-op. See
  [Tracing and cost](tracing-and-cost.md).

*(Still unverified, from the survey: `docker compose up -d` fails on a clean clone; `uv sync
--all-extras` silently pulls the multi-GB `docling` extra.)*

## 7. AI harness — testing, evaluation, reproducibility

- ~~**Verified — critical.** `pyproject.toml` `addopts` permanently suppresses **12 test files plus the
  entire `tests/unit/validation` directory** via `--ignore`.~~ **Fixed (WS4).** Every `--ignore` is
  gone. The suppressed files were not slow — they were stale, and running them surfaced **35
  failures** (28 in the 12 files, 7 more in `tests/unit/validation`). All are now green, and the
  suite went from 1,038 to 1,145 tests. Four were **code** defects rather than test drift:

  | Defect | Fix |
  |--------|-----|
  | `flow()` in the Langfuse tracer assembled `propagate_metadata` (tenant, flow, version, correlation, channel, env) and **never attached it** — flow traces carried only structlog contextvars, while `conversation()` did it correctly | metadata now reaches both the span and the propagated attributes |
  | `MemoryExtractionProcessor` returned silently on **five** skip conditions, so an operator could not tell why memory was never written | each emits `domain.context.memory_extraction.skipped` with a `reason_code` |
  | `MemoryWriteService` dropped the write silently when the user-memory vector quota was reached | emits `domain.memory.write.cap_reached` with cap, count and reason |
  | `create_flow_run` dereferenced `flow_run.input` although the schema marks it optional — a caller omitting `input` got a 500 | guarded at both use sites |

  Two further tests specified behaviour that had never been implemented: `extra_system_context` on
  LLM node config (test committed in b7e34cd **without** its implementation — now implemented, 4
  lines in `_llm_base.py`) and `AgentRun.ai_execution_policy_version_id` (column existed on
  `agent_version`, never on `agent_run` — added with migration `d4e5f6a7b8c9`, populated in WS5).
  `test_tool_catalog_retriever` targeted `retrieve_candidates`, deliberately replaced by
  `retrieve_tools` in c51f2f8; it was rewritten against the surviving behaviour rather than deleted.

- **Partly fixed — critical.** The **91-entry coverage `omit` list**. The register measured the
  advertised gate at 95.14% over 9,953 statements against 70% over 20,096 unfiltered. Two tranches
  have been retired, security- and execution-adjacent modules first (`utils/auth.py`,
  `services/execution_boundary.py`, `access_policy_service`, `governance_policies_service` and its
  controller, `rate_limit_service`, `auth_service`, `auth_controller`,
  `inbound_service_key_repository`, `tool_orchestrator`, `http_tool_executor`,
  `tenant_mcp_gateway`, then 19 already-covered modules). Current state:

  | Scope | Statements | Coverage |
  |-------|-----------:|---------:|
  | Measured surface (gate ≥ 90%) | 13,456 | 90.73% |
  | Whole codebase | 20,712 | 74% |

  The measured surface grew **29%** and the gate was re-pinned to the honest floor rather than
  keeping a 95% that covered half the tree. 74 omit entries remain; retiring them needs new tests,
  not a lower gate.
- **Verified — critical.** **No golden-dataset, eval-set or regression harness** for prompts or LLM
  node decisions. There is no way to answer "does flow version N+1 regress against N" — and,
  separately verified, N+1 cannot even be executed alongside N because the runtime hard-rejects
  non-active versions.
- **Verified — high.** LLM output is not deterministically mockable: no shared fake provider, no
  recorded responses, no seed.
- **Verified — high.** The execution event stream records only key *names*, never values, so recorded
  runs cannot be replayed or evaluated.
- **Verified — medium.** The `validation_integration` "replay determinism" test does not exercise the
  runtime — it inserts ORM rows directly. The node validation scripts under
  `resources/scripts/examples/nodes/` assert only `NodeExecutionStatus.SUCCESS`, never the decision,
  so they pass vacuously. One of them asserts a `summarize_skipped` contract that did not exist until
  the ContextSummarizer work above.

## 8. API surface

- **Verified — high.** Idempotency keys are never released on failure and are not bound to the request
  payload — a retry with a *different* body reuses the first response.
- **Verified — high.** No endpoint to cancel or terminate a flow run, although the engine supports it.
- **Verified — high.** Flow runs and tool runs **cannot be listed**, only fetched by id.
- **Verified — high.** Human SLA policies and escalation rules have **no HTTP surface at all**, so the
  SLA cases opened by `HumanFallback` cannot be managed through the API.
- **Verified — medium.** Version deprecate/disable endpoints for flows and agents are permanent `405`
  placeholders. Pagination, error shape and versioning are inconsistent across controllers.

## Rejected claims

Refuted on verification — do not re-report:

- *"`NodeRegistry.resolve` synthesizes a new dynamic subclass on every node execution."* The dynamic
  subclass pattern is real and is how zero-arg `node_cls()` construction works, but the performance
  claim did not hold up.
- *"Temporal worker liveness is unobservable."* Partially superseded — `docker-compose.yml` does
  define the worker service; the accurate residual finding is the missing healthcheck and the absent
  `/health` signal, recorded in §2.

---

## Demo seed as SQL (added scope)

Beyond the register's own list, the demo seeds were asked to become SQL — "more agnostic and
simple". They now are, without pretending the computed parts can be hand-written.

The Python seeds stay the **generator** and `resources/sql/demo_seed.sql` is the **artifact**: 51
tables, ~800 rows, one transaction of `INSERT … ON CONFLICT DO UPDATE`, including the RAG corpus with
its 3072-dimension embedding vectors. `make seed-demo` applies it against a migrated database and
needs nothing else — no Python seeds, no OpenAI key, no second service. That is strictly better than
the fixture fix in §6, where the RAG corpus was skipped without an API key.

Hand-writing all of it was rejected: `seed_11_graph` runs the graph compiler, `seed_26` hashes the
snapshot, and the two RAG seeds call the embedding API. Freezing those by hand means they drift
silently the moment the compiler or the embedding model changes. Generating the file keeps one
source of truth and makes the drift visible at regeneration time instead.

Verified on a clean database: `CREATE DATABASE` → `make migrate` → `make seed-demo` with
`OPENAI_API_KEY=""` produced 1 tenant, 12 nodes, 35 tool configs, 181 RAG chunks at 3072 dimensions;
applying a second time left every count unchanged.

Two things the exporter had to get right, both found by running it:

- **The tenant column must never be widened by a foreign-key link.** The first version ORed them and
  pulled 16 tenants into the file, because the shared `tool` catalogue reached every tenant's
  `tool_config`.
- **`tenant.default_flow_version_id` is a genuine cycle** (tenant → flow_version → flow → tenant).
  Forward references are inserted `NULL` and set by `UPDATE` at the end of the file.

CI's `demo-seed` job migrates a fresh Postgres, applies the file twice and asserts the header's row
counts — catching broken SQL, foreign-key order, reserved-word identifiers and any migration that
tightens a column the seed writes. It does **not** prove the file still matches the Python seeds:
regenerating needs an API key and embeddings are not byte-stable. That step stays manual and is
stated in the file header.

## Recommended next actions

1. **Fix the cross-tenant authorization holes in §1** — specifically `POST /auth/tenant-token`,
   `/admin/llm/*`, the execution-events query, and the governance version paths. Nothing else in this
   list matters if any tenant can mint another tenant's token.
2. **Make the durable path whole**: implement `signal_resume` and route `resume_flow_run` through
   Temporal when enabled, and add a reconciler for runs stranded after `prepare_flow_run`.
3. **Unblock onboarding**: either vendor a fixture OpenAPI spec for `seed_05_tool.py` or document the
   `app-platform` dependency; fix the `README` run command and the five broken Makefile targets. The
   `examples/` directory added here is a stopgap, not a substitute.
4. **Close the honesty gap in the quality bar**: unsuppress or delete the 12 ignored test files, and
   shrink the omit list toward the real surface. A 95% gate over half the codebase invites false
   confidence.
5. **Give cost a durable home**: write token counts and cost onto `agent_run` (or a purpose-built
   ledger) from the graph runtime, and make budget enforcement atomic and fail-closed.
6. **Bound the context**: the provider-side conversation is the real growth surface. A local
   compaction node cannot fix it alone — decide whether to own history locally or to roll the
   provider conversation with a summary carry-forward.
