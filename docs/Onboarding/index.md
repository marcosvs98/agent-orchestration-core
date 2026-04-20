# Onboarding — guide

The **onboarding** bounded context defines **onboarding programs** (with versions) and tracks **onboarding runs** and **step runs**, including advancing steps. It is separate from [Flows](../Flows/index.md) runtime execution but may orchestrate product setup journeys.

## Package map

| Area | Path |
|------|------|
| Service | `src/domain/onboarding/services/onboarding_service.py` |
| Repository | `src/domain/onboarding/repositories/onboarding_repository.py` |
| Controller | `src/domain/onboarding/controllers/onboarding_controller.py` |
| Schemas | `src/domain/onboarding/schemas/onboarding.py` |

## Related

- [HTTP API](http-api.md)
- [Persistence tables](../Glossary/persistence-tables.md) — `onboarding`, `onboarding_version`, `onboarding_run`, …
