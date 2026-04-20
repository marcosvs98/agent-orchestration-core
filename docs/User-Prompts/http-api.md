# User prompts — HTTP API

Router: `APIRouter(prefix="/core/v1", dependencies=[get_auth_context])` — `src/domain/user_prompts/controllers/user_prompts_controller.py`.

## Routes

| Method | Path | Notes |
|--------|------|--------|
| GET | `/core/v1/user-prompts` | List for tenant |
| POST | `/core/v1/user-prompts` | Create |
| GET | `/core/v1/user-prompts/{user_prompt_id}` | Get by id |
| DELETE | `/core/v1/user-prompts/{user_prompt_id}` | 204 |

## Related

- [User prompts overview](index.md)
