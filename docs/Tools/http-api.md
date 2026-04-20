# Tools — HTTP API

Router: `APIRouter(prefix="/core/v1", dependencies=[get_auth_context])` — `src/domain/tools/controllers/tools_controller.py`.

## Tool import and registry

| Method | Path |
|--------|------|
| POST | `/core/v1/tools/import-tools` |
| GET | `/core/v1/tools` |

## Tool configs

| Method | Path |
|--------|------|
| GET | `/core/v1/tool-configs` |
| POST | `/core/v1/tool-configs` |
| POST | `/core/v1/tool-configs/{tool_config_id}:publish` |
| POST | `/core/v1/tool-configs/{tool_config_id}:deprecate` |
| POST | `/core/v1/tool-configs/{tool_config_id}:disable` |

## Agent version bindings

| Method | Path |
|--------|------|
| POST | `/core/v1/agent-version-tool-bindings` |
| GET | `/core/v1/agent-versions/{agent_version_id}/tools` |

## Related

- [Tools overview](index.md)
- [Agents HTTP API](../Agents/http-api.md)
