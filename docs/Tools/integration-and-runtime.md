# Tools — integration and runtime

**Tools** covers **registry/authoring** and **runtime orchestration** (`ToolOrchestrator`) invoked from execution.

## Runtime path

```mermaid
flowchart LR
  subgraph tools["domain/tools"]
    TO[ToolOrchestrator]
  end
  subgraph exec["Execution"]
    TR[tool_run]
    NODE[Tool nodes]
  end
  NODE --> TO
  TO --> TR
```

- [Runtime execution](runtime-execution.md) for orchestrator details.
- [MCP](../MCP/index.md) may expose the same tool configs to external MCP clients.

## Related

- [Agents](../Agents/index.md)
- [Execution](../Execution/index.md)
