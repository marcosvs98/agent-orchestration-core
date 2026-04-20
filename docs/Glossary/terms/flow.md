# Flow

## Definition

A **flow** is the **top-level process** users author: a named graph that progresses through versions, snapshots, and deployments. Runtime always executes **published** materialization (snapshot + deployment), never a mutable draft in place.

## What it is not

- Not a single run: that is a [Flow run](flow-run.md).
- Not the raw draft JSON alone at runtime: compilation produces snapshots consumed by execution.

## Code

- `src/domain/flows/`
- Graph compilation and validation: `src/domain/flows/services/`

## Persistence

- Table `flow`; related `flow_version`, `flow_graph`, `flow_graph_draft`, `flow_graph_snapshot`. See [persistence tables](../persistence-tables.md).

## Related

- [Flow version](flow-version.md), [Flow graph snapshot](flow-graph-snapshot.md), [Flow run](flow-run.md)
- [Runtime vs authoring](../../Architecture/runtime-vs-authoring.md)
