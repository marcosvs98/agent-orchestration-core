# Flow run

## Definition

A **flow run** is a **single runtime execution** of a published flow against a specific snapshot/deployment. It progresses through states (created → running → completed/failed/cancelled) and owns **node runs**, **tool runs**, **agent runs**, and **execution events**.

## What it is not

- Not authoring: it never mutates published definitions.
- Not merely an HTTP request object: persistence spans the whole execution lifecycle.

## Code

- `src/domain/execution/` services, state machine, graph runtime under `graph_runtime/`.

## Persistence

- `flow_run`, `flow_run_lock`, `graph_state`, `execution_event`, `node_run`, `agent_run`, `tool_run`, etc. See [persistence tables](../persistence-tables.md).

## Related

- [Flow graph snapshot](flow-graph-snapshot.md)
- [Execution event](execution-event.md)
- [Flow lifecycle](../../Execution/flow-lifecycle.md)
