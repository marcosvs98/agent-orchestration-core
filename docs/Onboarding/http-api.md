# Onboarding — HTTP API

Router: `APIRouter(prefix="/core/v1", dependencies=[get_auth_context])` — `src/domain/onboarding/controllers/onboarding_controller.py`.

## Routes

| Method | Path |
|--------|------|
| GET | `/core/v1/onboardings` |
| POST | `/core/v1/onboardings` |
| POST | `/core/v1/onboarding-runs` |
| GET | `/core/v1/onboarding-runs/{onboarding_run_id}` |
| GET | `/core/v1/onboardings/{onboarding_id}/versions` |
| GET | `/core/v1/onboarding-runs/{onboarding_run_id}/steps` |
| POST | `/core/v1/onboarding-runs/{onboarding_run_id}/steps/{step_run_id}/advance` |

## Related

- [Onboarding overview](index.md)
