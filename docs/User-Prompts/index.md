# User prompts — guide

The **user_prompts** bounded context stores **tenant-scoped user prompt** definitions (slug, title, content) for reuse across product features — notably binding to [MCP servers](../MCP/index.md) as MCP **prompts**.

## Package map

| Area | Path |
|------|------|
| Service | `src/domain/user_prompts/services/user_prompts_service.py` |
| Repository | `src/domain/user_prompts/repositories/user_prompts_repository.py` |
| Controller | `src/domain/user_prompts/controllers/user_prompts_controller.py` |
| Schemas | `src/domain/user_prompts/schemas/user_prompts.py` |

Distinguish from [Prompts](../Prompts/index.md) (**node_type** templates) and from prompts embedded in **flow graph nodes**.

## Related

- [HTTP API](http-api.md)
- [MCP registry](../MCP/registry-and-api.md)
