# Flows — HTTP API overview

Router: `APIRouter(prefix="/core/v1", dependencies=[get_auth_context])` — `src/domain/flows/controllers/flows_controller.py`.

Several **`:deprecate`** and **`:disable`** flow-version actions are currently **placeholders** and raise `MethodNotAllowedPlaceholderException` (same pattern as [Agents](../Agents/http-api.md)).

## Flows and versions

| Method | Path |
|--------|------|
| GET | `/core/v1/flows` |
| POST | `/core/v1/flows` |
| GET | `/core/v1/flows/node-templates:system` |
| GET | `/core/v1/flows/{flow_id}` |
| GET | `/core/v1/flows/{flow_id}/versions` |
| POST | `/core/v1/flows/{flow_id}/versions` |
| POST | `/core/v1/flows/{flow_id}/versions/{flow_version_id}:validate` |
| POST | `/core/v1/flows/{flow_id}/versions/{flow_version_id}:publish` |
| POST | `/core/v1/flows/{flow_id}/versions/{flow_version_id}:activate` |
| POST | `/core/v1/flows/{flow_id}/versions/{flow_version_id}:rollback` |
| POST | `/core/v1/flows/{flow_id}/versions/{flow_version_id}:deprecate` |
| POST | `/core/v1/flows/{flow_id}/versions/{flow_version_id}:disable` |

Publish, activate, and rollback typically require a **`ChangeRequest`** body (see controller methods).

## Graph and nodes

| Method | Path |
|--------|------|
| GET | `/core/v1/flows/{flow_id}/versions/{flow_version_id}/nodes` |
| POST | `/core/v1/flows/{flow_id}/versions/{flow_version_id}/graph` |
| POST | `/core/v1/flows/{flow_id}/versions/{flow_version_id}/graph:draft` |
| POST | `/core/v1/flows/{flow_id}/versions/{flow_version_id}/graph:validate` |
| POST | `/core/v1/flows/{flow_id}/versions/{flow_version_id}/graph:compile` |
| POST | `/core/v1/nodes` |
| POST | `/core/v1/flows/{flow_id}/versions/{flow_version_id}/nodes:copy-from-template` |
| POST | `/core/v1/flows/{flow_id}/versions/{flow_version_id}/nodes:custom` |

## Deployments and artifacts

| Method | Path |
|--------|------|
| POST | `/core/v1/flows/{flow_id}/versions/{flow_version_id}/deployments:compose` |
| POST | `/core/v1/flows/{flow_id}/versions/{flow_version_id}/deployments:validate` |
| PUT | `/core/v1/flows/{flow_id}/versions/{flow_version_id}/artifacts:batch-upsert` |

## Routers and rules

| Method | Path |
|--------|------|
| GET | `/core/v1/routers` |
| POST | `/core/v1/routers` |
| POST | `/core/v1/routing-rules` |
| POST | `/core/v1/condition-expressions` |

## Related

- [Flows overview](index.md)
- [Graph and compiler](graph-and-compiler.md)
