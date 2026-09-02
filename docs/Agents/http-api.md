# Agents — HTTP API

Router: `APIRouter(prefix="/core/v1", dependencies=[get_auth_context])` — `src/domain/agents/controllers/agents_controller.py`.

## Routes

| Method | Path | Notes |
|--------|------|--------|
| GET | `/core/v1/agents` | List agents (`limit` query) |
| POST | `/core/v1/agents` | Create agent |
| GET | `/core/v1/agents/{agent_id}/versions` | List versions; optional `status_filter` |
| POST | `/core/v1/agents/{agent_id}/versions` | Create version |
| POST | `/core/v1/agents/{agent_id}/versions/{agent_version_id}:validate` | Validate version |
| POST | `/core/v1/agents/{agent_id}/versions/{agent_version_id}:publish` | Publish — body includes **`ChangeRequest`** |
| POST | `/core/v1/agents/{agent_id}/versions/{agent_version_id}:activate` | Activate — **`ChangeRequest`** |
| POST | `/core/v1/agents/{agent_id}/versions/{agent_version_id}:rollback` | Rollback — **`ChangeRequest`** |
| POST | `/core/v1/agents/{agent_id}/versions/{agent_version_id}:deprecate` | Reserved, not implemented — returns **405** and is hidden from the OpenAPI schema |
| POST | `/core/v1/agents/{agent_id}/versions/{agent_version_id}:disable` | Same |
| POST | `/core/v1/node-agent-bindings` | Create node ↔ agent version binding |
| GET | `/core/v1/agent-versions/{agent_version_id}/nodes` | List bindings for an agent version |

## Lifecycle (conceptual)

```mermaid
flowchart LR
  V[validate] --> P[publish]
  P --> A[activate]
  A --> R[rollback optional]
```

## Related

- [Agents overview](index.md)
