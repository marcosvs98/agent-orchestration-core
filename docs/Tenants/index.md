# Tenants — guide

The **tenants** bounded context creates and reads **tenant** records and exposes **current tenant** metadata, **settings**, and an optional **operational summary** for dashboards.

## Package map

| Area | Path |
|------|------|
| Service | `src/domain/tenants/services/tenants_service.py`, `tenant_summary_service.py` |
| Repository | `src/domain/tenants/repositories/tenants_repository.py`, `tenant_summary_repository.py` |
| Controller | `src/domain/tenants/controllers/tenants_controller.py` |
| Schemas | `src/domain/tenants/schemas/tenants.py`, `tenant_operational_summary.py`, … |

HTTP prefix: **`/core/v1/tenants`** (see [HTTP API](http-api.md)).

## Related

- [Tenant glossary](../Glossary/terms/tenant.md)
- [Auth](../Auth/index.md) for token issuance and inbound keys
