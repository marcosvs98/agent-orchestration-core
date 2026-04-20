# Authoring event

## Definition

An **authoring event** records **design-time** changes to artefacts (flows, policies, prompts, etc.): who changed what and when. It complements runtime [Execution events](execution-event.md).

## What it is not

- Not runtime telemetry from graph execution.

## Code

- Authoring pipelines in domain services that publish or mutate versioned entities; persistence via repositories under relevant `src/domain/*/repositories/`.

## Persistence

- `authoring_event`. See [persistence tables](../persistence-tables.md).

## Related

- [Develop: system events reference](../../Develop/system-events-reference.md) — full `AuthoringEventType` catalogue
- [Governance policy versioning](governance-policy-versioning.md)
- [Runtime vs authoring](../../Architecture/runtime-vs-authoring.md)
