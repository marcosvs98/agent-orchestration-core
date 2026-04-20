# Flow graph snapshot

## Definition

A **flow graph snapshot** is a **compiled, immutable** representation of the executable graph (nodes, edges, conditions) used when building **flow snapshots** for deployment and execution. Runtime node types come from this materialized structure (e.g. resolver, response builder), not from ad-hoc authoring tables alone.

## What it is not

- Not the same as `flow_graph_draft` (work in progress).
- Not a [Flow run](flow-run.md): it is definition material, not an execution instance.

## Code

- `src/domain/flows/` (compilation)
- `src/domain/execution/services/graph_runtime/` (execution over compiled structures)

## Persistence

- `flow_graph_snapshot`, `flow_snapshot`, `snapshot_binding`, `snapshot_effective_policy`, `flow_deployment`. See [persistence tables](../persistence-tables.md).

## Related

- [Flow version](flow-version.md), [Flow run](flow-run.md)
- [Execution flow lifecycle](../../Execution/flow-lifecycle.md)
