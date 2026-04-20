# Tools — persistence and data

Authoritative SQL shapes live in Alembic migrations. See [Persistence tables](../Glossary/persistence-tables.md).

## Tables (this bounded context)

| Table | Role |
|-------|------|
| `tool` | Registered tool |
| `tool_config` | Versioned tool definition (HTTP/OpenAPI, etc.) |
| `agent_version_tool_binding` | Binds tools to agent versions (see [Agents](../Agents/index.md)) |

Tool **runs** at execution time use runtime tables such as `tool_run` (see **Runtime execution** in the glossary; owned by [Execution](../Execution/index.md)).

## Related

- [Tool config term](../Glossary/terms/tool-config.md)
- [Tools overview](index.md)
