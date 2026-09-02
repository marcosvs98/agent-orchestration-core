# Conversation — persistence and data

Authoritative SQL shapes live in Alembic migrations. See [Persistence tables](../Glossary/persistence-tables.md).

## Tables (this bounded context)

| Table | Role |
|-------|------|
| `session` | Conversation session |
| `end_user` | End-user identity |
| `interaction` | Interaction records for operator read APIs |
| `conversation_summary` | Durable carry-forward summary written when a provider conversation rolls over — see [Token cost and context strategy](../Develop/token-cost-and-context-strategy.md#provider-side-conversation-rollover) |
| `tenant_mcp_credential` | The tenant's own MCP server and keys, loaded per turn by `McpConfigLoader` |

## Related

- [Conversation overview](index.md)
- [Read API](read-api.md)
