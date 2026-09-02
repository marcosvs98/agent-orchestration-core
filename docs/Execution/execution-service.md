# Execution service

`ExecutionService` (`src/domain/execution/services/execution_service.py`) implements `ExecutionServicePort`. It is the **composition root** for a flow run: idempotency, session/interaction, **flow version** selection, **graph snapshot** and **runtime policy** resolution, **compilation** of the snapshot to an `ExecutionPlan` (with Redis cache keyed by `graph_hash`), and **`RuntimeExecutor.run`**. It also wires **LLM** (executor, layered inference, context builder), **RAG**, **memory**, **tools**, **guardrails**, **hooks**, and **limits**.

## Constructor responsibilities (summary)

Non-exhaustive list of collaborators created or held:

- `ExecutionRepository`, `IdempotencyService`, `RunLifecycleStateMachine`, `ExecutionLimitService`, `RuntimeTracerPort`
- `GraphCompiler` (`plan_compiler`), `RuntimeExecutor` (`runtime`) with `NodeRegistry` (`self.runtime.registry`)
- `LLMExecutor` / `LayeredInferenceOrchestrator`, `CompletionBudgetPolicy`, `StructuredOutputSchemaComposer`, `ContextBuilder`, RAG and memory services, `SemanticCacheService` when enabled
- `RuntimePolicyResolver` backed by `RuntimePolicyRepository` and `default_policy` dict (large inline defaults for `llm`, `moderation`, etc.)
- `CompositeHook` / `DbExecutionEventHook` / memory hooks — assigned to `self.hook` for lifecycle notifications

Exact wiring evolves with commits; always check the `__init__` body for the current graph.

## `create_flow_run`

High-level sequence:

1. **Validate** `flow_id` / `flow_version_id`, tenant, user, published/active version (`get_active_flow_version_id`).
2. **Idempotency** — `try_acquire`; on miss return cached response or `IdempotencyInProgressException`.
3. **Session** — create if missing; enforce tenant/user match on existing session.
4. **Interaction** — `create_interaction` with payload, headers, trace id.
5. **Origin handoff** — optional `origin_flow_run_id` / correlation to resume from a `WAITING_INPUT` run; loads graph state for `start_node_id`, `initial_state`, `initial_memory`.
6. **Snapshot contract** — loads `flow_deployment`, `flow_snapshot`, `graph_snapshot`. If a **flow snapshot** document exists, `runtime_policy` may be taken from `flow_snapshot.runtime_policy` (FLOW-scoped, version `"snapshot"`) with hashes for plan/tool catalog; otherwise (legacy) `policy_resolver.resolve(tenant_id, flow_id)` and hashes from graph snapshot.
7. **Persist** `create_flow_run` row with `runtime_contract` (version ids, hashes, deployment ids).
8. **Tracing** — `start_flow_trace`, optional `set_root_observation_id`.
9. **Hook** — `on_flow_start`.
10. **Plan** — Redis `get(graph_hash)` or `plan_compiler.compile(snapshot, graph_hash, available_tools=[])` then `cache_set`.
11. **Run** — `runtime.run(...)` with `plan`, `runtime_policy`, `trace_context`, resume args, `on_content_delta`.
12. **Finalize** — `end_event_batching`, refresh response from DB, `idempotency.set_result`.

Guardrails and limits are enforced inside LLM/tool paths via injected services; event batching scopes execution events for the run.

## `resume_flow_run`

Loads the run, validates user and wait state, rebuilds plan from cached snapshot hash or compiler, resolves policy consistent with stored contract, and calls `runtime.run` with input from resume payload (see source for edge cases and lock handling).

## Agent and tool runs

- `create_agent_run`, `complete_agent_run` — agent run lifecycle rows and status transitions via `lifecycle.validate_agent`.
- `create_tool_run` — tool run creation with `lifecycle.validate_tool` where applicable.

## Read APIs

- `get_flow_run`, `get_graph_state` — read persisted run and graph state JSON.
- `list_node_runs`, `list_agent_runs`, `list_execution_events` — list helpers over the repository.

## HTTP surface — the execution plane

`ExecutionPlaneController` (`src/domain/execution/controllers/execution_plane_controller.py`) mounts
at **`/core/v1/executions`** behind `get_auth_context`, and calls `ExecutionBoundary` (rate limit +
access policy) rather than `ExecutionService` directly.

| Method | Path | Status | Notes |
|--------|------|--------|-------|
| POST | `/flow-runs` | 201 (202 async) | Requires `Idempotency-Key`. `?wait=false` returns 202. |
| GET | `/flow-runs/{flow_run_id}` | 200 | Run detail. |
| POST | `/flow-runs/{flow_run_id}:resume` | 200 | Resumes a `WAITING_INPUT` run as a new turn — see [Durable execution](durable-execution.md#resuming-a-waiting-run). |
| GET | `/flow-runs/{flow_run_id}/graph-state` | 200 | Persisted `graph_state` document. |
| POST | `/tool-runs` | 201 | Requires `Idempotency-Key`. Body `ToolRunCreate`. |
| POST | `/tool-runs/{tool_run_id}:execute` | 200 | Executes an existing tool run; returns the raw result dict. |
| GET | `/node-runs` | 200 | List, filterable by `flow_run_id`. |
| GET | `/execution-events` | 200 | List, filterable by `flow_run_id`. |

Agent runs live on the same prefix but are served by `AgentRunController` — see
[Agent runtime → HTTP API](agent-runtime.md#http-api).

!!! note "The `tool-runs` routes are an operator/debug surface"

    Graph execution creates and executes tool runs internally through `ToolExecutor` and
    `ToolOrchestrator`; nothing in the normal request path calls these two endpoints. They exist to
    create or re-drive a single tool run out of band. Because `:execute` runs the side effect
    immediately, treat it as a write, not an inspection call.

## Related

- [Graph runtime overview](graph-runtime/index.md)
- [Runtime policy resolver](runtime-policy-resolver.md)
- [Observability and hooks](observability-and-hooks.md)
- [State machine](state-machine.md)
