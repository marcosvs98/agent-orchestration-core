# Glossary

Definitions for **product concepts** and pointers to **persistence**. Use this hub to disambiguate domain language before changing code under `src/domain/` or migrations under `src/infra/database/migrations/`.

## How entries are structured

Each term file includes: **definition**, **what it is not**, **code locations**, **persistence** (where applicable), and **related** links.

## Domain terms (by area)

| Term | Summary |
|------|---------|
| [Tenant](terms/tenant.md) | Multi-tenant isolation boundary; owns configuration and data scope. |
| [Flow](terms/flow.md) | Top-level process definition; groups versions and deployments. |
| [Flow version](terms/flow-version.md) | Immutable published (or draft) version of a flow graph. |
| [Flow graph snapshot](terms/flow-graph-snapshot.md) | Compiled snapshot used for execution and policy binding. |
| [Flow run](terms/flow-run.md) | Single execution instance of a published flow against a snapshot. |
| [Agent version](terms/agent-version.md) | Versioned agent definition and bindings to tools. |
| [Tool config](terms/tool-config.md) | Versioned tool/OpenAPI configuration for execution. |
| [Execution event](terms/execution-event.md) | Append-only runtime observation of execution progress. |
| [Authoring event](terms/authoring-event.md) | Audit trail for design-time changes to artefacts. |
| [RAG config](terms/rag-config.md) | Retrieval configuration for a tenant or flow scope. |
| [Vector store](terms/vector-store.md) | Vector index metadata (model, dimension, metric). |
| [Governance policy versioning](terms/governance-policy-versioning.md) | Pattern: policy root + `*_policy_version` rows. |

## Persistence

| Document | Purpose |
|----------|---------|
| [Persistence tables (SQL index)](persistence-tables.md) | Maps **every** Alembic table name to domain area and typical `src/domain` owner. |

## Related documentation

- [Domain model overview](../Models/domain-overview.md)
- [Runtime vs authoring](../Architecture/runtime-vs-authoring.md)
- [Documentation map (AI)](../AI/documentation-map.md)
- [Architecture overview](../Architecture/ARCHITECTURE.md)
