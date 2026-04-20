# User prompts — persistence and data

Authoritative SQL shapes live in Alembic migrations. See [Persistence tables](../Glossary/persistence-tables.md).

## Tables (this bounded context)

| Table | Role |
|-------|------|
| `user_prompt` | Tenant-scoped reusable prompt (slug, title, content) |

[MCP](../MCP/index.md) may reference user prompts (`mcp_server_user_prompt` in glossary).

## Related

- [User prompts overview](index.md)
