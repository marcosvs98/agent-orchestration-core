# Tenant

## Definition

A **tenant** is the primary **multi-tenant isolation boundary**. Runtime requests, policies, flows, tools, and RAG resources are scoped to a tenant identifier.

## What it is not

- Not a single user: end users and sessions belong to a tenant but are separate entities.
- Not the same as “organization” in external IdPs unless you explicitly map them.

## Code

- `src/domain/tenants/`
- Settings and feature flags often stored as JSON on tenant records (see repositories).

## Persistence

- Table `tenant`. See [persistence tables](../persistence-tables.md).

## Related

- [Flow run](flow-run.md) (tenant-scoped execution)
- [Domain overview](../../Models/domain-overview.md)
