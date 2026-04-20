# Prompts — HTTP API

Router: `APIRouter(prefix="/core/v1", dependencies=[get_auth_context])` — `src/domain/prompts/controllers/prompt_controller.py`.

| Method | Path | Notes |
|--------|------|-------|
| GET | `/core/v1/nodes/{node_type}/prompt` | Returns active prompt; 404-style validation if missing |
| POST | `/core/v1/nodes/{node_type}/prompt` | Create/update; body `node_type` must match path; sets `created_by` from auth |
| DELETE | `/core/v1/nodes/{node_type}/prompt` | 204 |

## Related

- [Prompts overview](index.md)
