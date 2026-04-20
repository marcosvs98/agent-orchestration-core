# Conversation — persistence and data

Authoritative SQL shapes live in Alembic migrations. See [Persistence tables](../Glossary/persistence-tables.md).

## Tables (this bounded context)

| Table | Role |
|-------|------|
| `session` | Conversation session |
| `end_user` | End-user identity |
| `interaction` | Interaction records for operator read APIs |

## Related

- [Conversation overview](index.md)
- [Read API](read-api.md)
