# Flows — guide

The **flows** bounded context is the **authoring surface** for conversational products: **flows**, **flow versions**, **graph definitions** (draft vs compiled snapshot), **nodes**, **routers**, **routing rules**, **condition expressions**, and **deployment compose** artifacts. Runtime execution consumes **compiled graph snapshots** via [Execution](../Execution/index.md).

## Package map

| Area | Path |
|------|------|
| Service | `src/domain/flows/services/flows_service.py` |
| Repository | `src/domain/flows/repositories/flows_repository.py` |
| Controller | `src/domain/flows/controllers/flows_controller.py` |
| Graph compile | `flow_graph_compiler.py`, `flow_graph_validator.py`, `flow_graph_draft_validator.py` |
| Conditions | `condition_evaluator.py` (shared concepts with runtime) |

HTTP prefix: **`/core/v1`**.

## Reading order

1. [Persistence and data](persistence-and-data.md) (table index)
2. [Integration and runtime](integration-and-runtime.md)
3. [HTTP API overview](http-api-overview.md)
4. [Graph and compiler](graph-and-compiler.md)
5. [Authoring and persistence](authoring-and-persistence.md)
6. [Graph runtime](../Execution/graph-runtime/index.md)
7. [Glossary terms](../Glossary/index.md): Flow, Flow version, Flow graph snapshot

## Related

- [Execution — demo seed graph](../Execution/demo-seed-graph.md)
- [Documentation map](../AI/documentation-map.md)
