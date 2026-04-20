# Tenants — persistence and data

Authoritative SQL shapes live in Alembic migrations. See [Persistence tables](../Glossary/persistence-tables.md).

## Tables (this bounded context)

| Table | Role |
|-------|------|
| `tenant` | Core tenant row (identity, settings hooks) |

Inbound API keys for tenants live in **`tenant_inbound_service_key`** under [Auth](../Auth/index.md).

## Related

- [Tenant term](../Glossary/terms/tenant.md)
- [Tenants overview](index.md)
