# Governance policy versioning

## Definition

Governance policies (access, rate limits, RAG, memory, billing, execution limits, etc.) follow a common **two-level pattern**:

1. **Policy root** row (current editable metadata / identity).
2. **`*_policy_version`** rows holding immutable version snapshots referenced by runtime and snapshots.

Runtime effective policy for a deployment often flows through **flow snapshot** binding tables (see [Flow graph snapshot](flow-graph-snapshot.md)).

## What it is not

- Not eight completely unrelated concepts: the same versioning idea repeats per policy type.

## Code

- `src/domain/governance/` and related controllers/services per policy type.

Full guide: [Governance overview](../../Governance/index.md) (policy types, HTTP API, enforcement, resolution).

**Exception:** `runtime_policy` stores `policy_definition` on the **same** row (no separate `runtime_policy_version` table). See [Policy model and versioning](../../Governance/policy-model-and-versioning.md).

## Persistence

- Pairs such as `access_policy` / `access_policy_version`, `rate_limit_policy` / `rate_limit_policy_version`, etc. See [persistence tables](../persistence-tables.md).

## Related

- [Governance overview](../../Governance/index.md)
- [Authoring event](authoring-event.md)
- [Domain overview](../../Models/domain-overview.md)
