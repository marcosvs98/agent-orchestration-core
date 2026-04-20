# Observability and hooks

`src/domain/execution/services/observability/hooks.py` defines the **hook interface** used by `RuntimeExecutor` and `ExecutionService` to broadcast lifecycle milestones to **persistence** and **domain side effects** without hard-coding the database inside the executor loop.

## `ExecutionEventHook` (abstract)

Methods (all async):

- `on_flow_start`
- `on_node_start`
- `on_node_complete`
- `on_edge_evaluated`
- `on_flow_complete`
- `on_flow_failed`

Implementations decide what to persist or process.

## `CompositeHook`

Runs a **list** of hooks in order. If a subscriber after the first fails, errors are logged; if the **first** hook fails, that exception is re-raised after the loop (`on_flow_start`, etc., follow the same pattern per method).

## `DbExecutionEventHook`

Maps hook calls to **`append_execution_event`** on `ExecutionRepository` with appropriate `ExecutionEventType` values (e.g. `FlowStarted`, `NodeStarted`, `NodeCompleted`, edge-evaluated events). Uses `RuntimeTracerPort.observe` with `as_type="event"` for each emission. Failures in `_safe_emit` are logged and swallowed for resilience.

Other hook classes in the same module (e.g. memory extraction) attach to `on_node_complete` / flow end — see the file for the current list and constructor dependencies.

## Pointers

- [Tracing and cost](../Develop/tracing-and-cost.md) — Langfuse / trace ids
- [System events reference](../Develop/system-events-reference.md) — `ExecutionEventType` catalogue
- [Graph runtime / runtime executor](graph-runtime/runtime-executor.md) — when hooks fire
