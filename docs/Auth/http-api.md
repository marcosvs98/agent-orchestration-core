# Auth — HTTP API

Router: `APIRouter(prefix="/core/v1/auth")` — `src/domain/auth/controllers/auth_controller.py`.

Note: **`issue_tenant_token`** uses **`get_tenant_token_m2m_auth`**, not the default `get_auth_context` on the route definition — see the controller.

## Routes

| Method | Path | Auth | Notes |
|--------|------|------|--------|
| POST | `/core/v1/auth/tenant-token` | M2M | Body: `TenantTokenRequest`. Requires **`Scope.TenantsCreate`** in `auth.scopes`. `tenant_id` from body or auth context; `tenant_id_required` if missing. |
| POST | `/core/v1/auth/inbound-service-keys` | `get_auth_context` | Requires **`Scope.TenantsCreate`**. Body tenant must match authenticated tenant when set. Returns **`InboundServiceKeyCreateResponse`** (includes **secret** once). |
| POST | `/core/v1/auth/inbound-service-keys/{inbound_service_key_id}/revoke` | `get_auth_context` | 204. Same scope and tenant match rules as create. Body: `InboundServiceKeyRevokeRequest`. |

## Scope coupling

Inbound key routes reuse **`Scope.TenantsCreate`** (same as tenant creation in [`tenants_controller`](../Tenants/http-api.md)) — verify this matches your product’s RBAC model before exposing broadly.

## Related

- [Auth overview](index.md)
