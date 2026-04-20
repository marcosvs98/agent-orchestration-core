# Auth — integration and runtime

**Auth** issues **tenant-scoped tokens** and manages **inbound service keys**. Downstream controllers depend on **`get_auth_context`** (and related dependencies) rather than calling `AuthService` on every request path.

## Flow

```mermaid
sequenceDiagram
  participant C as Client
  participant A as AuthController
  participant S as AuthService
  participant API as Other domain controllers
  C->>A: Issue token / manage keys
  A->>S: persist / hash
  C->>API: Requests with Bearer / scoped credentials
  Note over API: JWT validation + scopes
```

## Related

- [HTTP API](http-api.md)
- [Governance — HTTP API and scopes](../Governance/http-api-and-scopes.md)
