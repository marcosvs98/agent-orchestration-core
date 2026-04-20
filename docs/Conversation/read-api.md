# Conversation — read API

Operator-facing listing APIs for conversation data. Router: `APIRouter(prefix="/core/v1", dependencies=[get_auth_context])` — `src/domain/conversation/controllers/conversation_read_controller.py`.

## Routes

| Method | Path | Response |
|--------|------|----------|
| GET | `/core/v1/interactions` | `PaginatedInteractionsResponse` |
| GET | `/core/v1/sessions` | `PaginatedSessionsResponse` |
| GET | `/core/v1/end-users` | `PaginatedEndUsersResponse` |
| GET | `/core/v1/end-users/{user_id}` | `EndUserDetailResponse` |

Query parameters (pagination, filters) are defined on the controller methods — see source for exact names and defaults.

## Related

- [Conversation overview](index.md)
