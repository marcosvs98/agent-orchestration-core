# Flow version

## Definition

A **flow version** is an **immutable versioned record** of a flow’s definition at a point in time (draft → validated → published lifecycle in product terms). Published versions are the only ones eligible for snapshot materialization and deployment.

## What it is not

- Not a runtime execution record (see [Flow run](flow-run.md)).
- Not necessarily tied to a single physical graph row without also considering `flow_graph` / snapshot tables.

## Code

- `src/domain/flows/` repositories and services for versioning and publish workflows.

## Persistence

- `flow_version`, linked to `flow` and graph artefacts. See [persistence tables](../persistence-tables.md).

## Related

- [Flow](flow.md), [Flow graph snapshot](flow-graph-snapshot.md)
