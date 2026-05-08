# Conversation — SSE and runtime

## Streaming endpoint

| Method | Path | Response |
|--------|------|----------|
| POST | `/core/v1/conversations` | **`EventSourceResponse`** (SSE) |

Controller: `src/domain/conversation/controllers/conversation_controller.py`  
Router: `prefix="/core/v1"`, `dependencies=[get_auth_context_or_api_key]`.

### Headers

- **`Idempotency-Key`** — **required**; missing → `RouterValidationException` (`missing_idempotency_key`).
- **`Last-Event-ID`** — optional; must parse to non-negative int or validation error.
- **`X-Trace-Id`** — optional UUID for tracing (see controller).

### Request body

The conversation contract uses `agent_id` as selector and keeps `user_input` / `input_parts` for user text and multimodal input.

### Boundary behaviour

`ConversationBoundary.send_message` (see `src/services/conversation_boundary.py`):

1. **`RateLimitService.enforce`** with `action=Scope.ExecutionFlowRunCreate`.
2. **`AccessPolicyService.authorize`** with the same action string and `auth.scopes`.
3. Delegates to **`ConversationService.execute_turn`**.

### Runtime path

The endpoint runs in direct low-friction mode:

- `ConversationService` creates minimal interaction audit.
- `agent_id` is resolved to active version for system prompt.
- `OpenAIProviderAdapter.infer_conversation_stream` performs `responses.create(stream=True)`.
- OpenAI events are mapped to internal SSE events.

### SSE event contract

- `connected`
- `content_delta`
- `tool_progress`
- `done`
- `error`

## Sequence

```mermaid
sequenceDiagram
  participant Client
  participant CC as ConversationController
  participant CB as ConversationBoundary
  participant CS as ConversationService
  participant OAI as OpenAIProviderAdapter
  Client->>CC: POST + Idempotency-Key
  CC->>CB: send_message
  CB->>CB: rate_limit + access_policy
  CB->>CS: execute_turn
  CS->>OAI: infer_conversation_stream
  CS-->>Client: SSE events
```

## Related

- [Conversation overview](index.md)
- [Read API](read-api.md)
