# Tenants — HTTP API

Router: `APIRouter(prefix="/core/v1/tenants", dependencies=[get_auth_context])` — `src/domain/tenants/controllers/tenants_controller.py`.

## Routes

| Method | Path | Notes |
|--------|------|--------|
| POST | `/core/v1/tenants` | Idempotent create by `external_id`; requires scope **`tenants:create`** (`Scope.TenantsCreate`). Returns 200 if exists, 201 if created. |
| GET | `/core/v1/tenants/current` | Current tenant profile |
| GET | `/core/v1/tenants/current/summary` | Operational summary (`TenantSummaryService` when wired) |
| GET | `/core/v1/tenants/current/settings` | Tenant settings |

## Related

- [Tenants overview](index.md)
- [Auth HTTP API](../Auth/http-api.md)
