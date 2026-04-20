# Prompts — persistence and data

Authoritative SQL shapes live in Alembic migrations. See [Persistence tables](../Glossary/persistence-tables.md).

## Tables (this bounded context)

| Table | Role |
|-------|------|
| `node_prompt` | Active prompt template per `node_type` (tenant-scoped application concerns may apply) |

Distinguish from **inline** prompts on flow graph nodes ([Flows](../Flows/index.md)) and from [User prompts](../User-Prompts/index.md).

## Related

- [Prompts overview](index.md)
