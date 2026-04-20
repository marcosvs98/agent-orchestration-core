# Tools — guide

The **tools** bounded context registers **HTTP (and related) tool definitions** per tenant, manages **tool_config** lifecycle (publish / deprecate / disable), imports tools (e.g. OpenAPI), binds tools to **agent versions**, and orchestrates **tool runs** during execution via **`ToolOrchestrator`**.

## Package map

| Area | Path |
|------|------|
| Service | `tools_service.py`, `tool_orchestrator.py`, `openapi_parser.py`, catalog indexer/retriever |
| Repository | `tools_repository.py` |
| Controller | `tools_controller.py` |
| Ports | `ports/tool_executor.py`, `ports/secret_resolver.py` |

## Split reading

1. [HTTP API](http-api.md) — authoring and registry
2. [Runtime execution](runtime-execution.md) — orchestrator + execution plane
3. [MCP](../MCP/index.md) — exposes tool configs to MCP clients

## Related

- [Tool config glossary](../Glossary/terms/tool-config.md)
- [Execution](../Execution/index.md)
