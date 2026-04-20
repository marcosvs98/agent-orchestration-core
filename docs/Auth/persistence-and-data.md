# Auth — persistence and data

Authoritative SQL shapes live in Alembic migrations. See [Persistence tables](../Glossary/persistence-tables.md).

## Tables (this bounded context)

| Table | Role |
|-------|------|
| `tenant_inbound_service_key` | Inbound API keys for machine clients (create/revoke) |

Token issuance may reference **tenant** rows owned by [Tenants](../Tenants/index.md) (`tenant` table).

## Related

- [Auth overview](index.md)
- [Tenants](../Tenants/index.md)
