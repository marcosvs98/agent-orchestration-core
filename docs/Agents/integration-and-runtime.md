# Agents — integration and runtime

The **agents** package is consumed at **authoring time** (CRUD, publish, bindings) and at **runtime** when the graph resolves which agent version runs on a node.

## Call graph (simplified)

```mermaid
flowchart TB
  subgraph authoring["Authoring / HTTP"]
    AC[AgentsController]
    AS[AgentsService]
  end
  subgraph flows["Flows"]
    NAB[Node agent bindings]
  end
  subgraph exec["Execution"]
    GR[Graph runtime / agent runtime resolver]
  end
  AC --> AS
  AS --> NAB
  NAB --> GR
```

- **Flows** attach **agent versions** to **nodes** via `node_agent_binding`.
- **Execution** [graph runtime](../Execution/graph-runtime/index.md) resolves the active agent for a node run; tool compatibility uses [Tools — runtime execution](../Tools/runtime-execution.md).

## Related

- [HTTP API](http-api.md)
- [Tools](../Tools/index.md)
