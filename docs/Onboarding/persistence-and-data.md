# Onboarding — persistence and data

Authoritative SQL shapes live in Alembic migrations. See [Persistence tables](../Glossary/persistence-tables.md).

## Tables (this bounded context)

| Table | Role |
|-------|------|
| `onboarding` | Onboarding program definition |
| `onboarding_version` | Versioned program |
| `onboarding_run` | A run instance |
| `onboarding_step` | Step rows; `step_run` in glossary maps execution-side step tracking to onboarding |

Runtime execution also references `step_run` (see glossary **Runtime execution**) for step execution linkage.

## Related

- [Onboarding overview](index.md)
