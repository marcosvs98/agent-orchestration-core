# Auth — HTTP API

Router: `APIRouter(prefix="/core/v1/auth")` — `src/domain/auth/controllers/auth_controller.py`.

Note: **`issue_tenant_token`** uses **`get_tenant_token_m2m_auth`**, not the default `get_auth_context` on the route definition — see the controller.

## Routes

| Method | Path | Auth | Notes |
|--------|------|------|--------|
| POST | `/core/v1/auth/tenant-token` | M2M | Body: `TenantTokenRequest`. Requires **`Scope.TenantsCreate`** in `auth.scopes`. `tenant_id` from body or auth context; `tenant_id_required` if missing. |
| POST | `/core/v1/auth/inbound-service-keys` | `get_auth_context` | Requires **`Scope.TenantsCreate`**. Body tenant must match authenticated tenant when set. Returns **`InboundServiceKeyCreateResponse`** (includes **secret** once). |
| POST | `/core/v1/auth/inbound-service-keys/{inbound_service_key_id}/revoke` | `get_auth_context` | 204. Same scope and tenant match rules as create. Body: `InboundServiceKeyRevokeRequest`. |
| POST | `/core/v1/auth/admin/api-keys` | **`get_admin_auth`** | 201. Platform-operator bootstrap — see below. |

## `POST /core/v1/auth/admin/api-keys`

The bootstrap path: it mints an inbound service key for a tenant **without** already holding a token
for that tenant, which is what makes the first credential obtainable.

Auth is the **`X-Admin-Key`** header matching **`ADMIN_API_KEY`**, compared with
`secrets.compare_digest` (`src/utils/auth.py`). A tenant JWT is not accepted. If `ADMIN_API_KEY` is
unset the route answers **503 `admin_endpoint_not_configured`**; a wrong or missing header answers
**401 `invalid_admin_key`**.

The handler synthesizes an admin `AuthContext` (`principal_type: machine`, scope `tenants:create`,
no tenant) and delegates to the same `create_inbound_service_key` the tenant-scoped route uses, so
`tenant_id` comes from the **request body**. Body is `InboundServiceKeyCreateRequest`; the response
is `InboundServiceKeyCreateResponse`, which carries the **secret once**.

This is the same trust tier as [`/admin/llm`](../Governance/http-api-and-scopes.md#llm-admin-prefix-adminllm):
one shared key that can issue credentials for **any** tenant. Terminate it at the gateway rather
than exposing it with the tenant API.

## Scope coupling

The two tenant-scoped inbound key routes reuse **`Scope.TenantsCreate`** (same as tenant creation in [`tenants_controller`](../Tenants/http-api.md)) — verify this matches your product’s RBAC model before exposing broadly.

## Related

- [Auth overview](index.md)
