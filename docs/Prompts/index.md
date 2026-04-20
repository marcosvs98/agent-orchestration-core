# Prompts — guide (node prompts)

The **prompts** bounded context manages **node-level prompt templates** keyed by **`node_type`**. These are **not** the same as [User prompts](../User-Prompts/index.md) (tenant-authored MCP prompt library) nor **inline node prompts** stored on flow graph nodes in [Flows](../Flows/index.md).

## Package map

| Area | Path |
|------|------|
| Service | `src/domain/prompts/services/prompt_service.py` |
| Repository | `src/domain/prompts/repositories/prompt_repository.py` |
| Schemas | `src/domain/prompts/schemas/prompt.py` |

## Reading order

1. [Persistence and data](persistence-and-data.md)
2. [Integration and runtime](integration-and-runtime.md)
3. [HTTP API](http-api.md)

## Related

- [User prompts](../User-Prompts/index.md)
- [LLM-backed nodes](../Execution/graph-runtime/nodes/llm-nodes.md)
