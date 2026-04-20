# Agents — persistence and data

Authoritative SQL shapes live in Alembic migrations under `src/infra/database/migrations/versions/`. Cross-check with [Persistence tables](../Glossary/persistence-tables.md).

## Tables (this bounded context)

| Table | Role |
|-------|------|
| `agent` | Tenant-scoped agent definition |
| `agent_version` | Versioned configuration (persona, prompts, compatibility) |
| `node_agent_binding` | Binds an agent version to a flow graph node |
| `agent_version_tool_binding` | Links agent versions to tool configs (see also [Tools](../Tools/index.md)) |

## Related

- [Agent version term](../Glossary/terms/agent-version.md)
- [Agents overview](index.md)
