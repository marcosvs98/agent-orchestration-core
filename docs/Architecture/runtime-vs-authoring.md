# Runtime vs authoring

**Authoring** (design-time) produces versioned, auditable **definitions**. **Runtime** (execution-time) consumes **published** definitions only and records **append-only** execution facts. Mixing the two in the same code path is a common source of bugs; keep boundaries explicit.

## Definitions

| Phase | What mutates | What is stored | Typical services |
|-------|----------------|----------------|------------------|
| Authoring | Drafts, validations, publish workflows | `flow_version`, policies, `authoring_event`, graph drafts | `domain/flows/`, `domain/governance/`, … |
| Materialization | Snapshot/build pipelines | `flow_snapshot`, `flow_deployment`, policy bindings | `domain/flows/`, governance |
| Runtime | **No** published definition rows | `flow_run`, `execution_event`, `node_run`, … | `domain/execution/` |

## Data flow (simplified)

```mermaid
flowchart LR
  subgraph design [Authoring]
    D[Draft graph]
    V[Validate]
    P[Publish version]
  end
  subgraph mat [Materialize]
    C[Compile snapshot]
    Dep[Deploy to environment]
  end
  subgraph run [Runtime]
    R[Start flow run]
    X[Execute nodes]
    E[Emit execution events]
  end
  D --> V --> P --> C --> Dep --> R --> X --> E
```

## Immutability rules

- Published **flow versions** and **policy versions** are not edited in place; new rows supersede.
- **Flow runs** reference explicit snapshot/version identifiers; reruns create **new** runs.
- **Execution events** are observations, not retroactive edits to definitions.

## Code entry points

- Authoring controllers under `src/domain/*/controllers/` (HTTP) mutate drafts through application services.
- Runtime execution enters via `src/domain/execution/` and `graph_runtime/`.
- Cross-cutting tracing: `src/adapters/observability/otel_runtime_tracer.py`.

## Related

- [Flow lifecycle](../Execution/flow-lifecycle.md)
- [Glossary: flow run](../Glossary/terms/flow-run.md)
- [Domain overview](../Models/domain-overview.md)
- [Persistence tables](../Glossary/persistence-tables.md)
