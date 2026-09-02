# agent-orchestration-core

A self-hostable, multi-tenant agent orchestration platform where every run is pinned to the exact definitions and policies that governed it.

## Start here

- **[Documentation map (AI)](AI/documentation-map.md)** — task → docs → code (same content as the nav hub **Domain documentation**).
- **[Glossary](Glossary/index.md)** — domain terms and [persistence tables](Glossary/persistence-tables.md).
- **[Architecture overview](Architecture/ARCHITECTURE.md)** — bounded contexts, hexagonal layout, full context table.
- **[Runtime vs authoring](Architecture/runtime-vs-authoring.md)** — design-time vs execution-time rules.
- **[Context and cache strategy](Architecture/context-and-cache-strategy.md)** — RAG and CAG techniques in one map.
- **[Domain model overview](Models/domain-overview.md)** — entities and relationships across contexts.

## Domain documentation (overview)

Use the sidebar **Domain documentation** for the full tree (persistence, integration, HTTP per context). High-level map:

| Area | Contexts |
|------|----------|
| Execution stack | [Execution](Execution/index.md), [Flows](Flows/index.md) |
| Inference & memory | [LLM](LLM/index.md), [RAG](RAG/index.md), [Context](Context/index.md) |
| Integrations | [Tools](Tools/index.md), [MCP](MCP/index.md), [User prompts](User-Prompts/index.md) |
| Identity & tenancy | [Tenants](Tenants/index.md), [Auth](Auth/index.md) |
| Agents & conversation | [Agents](Agents/index.md), [Conversation](Conversation/index.md), [Prompts](Prompts/index.md) |
| Policy & HITL | [Governance](Governance/index.md), [AI policy](AI-Policy/index.md), [Human SLA](Human-SLA/index.md) |
| Onboarding | [Onboarding](Onboarding/index.md) |

## Setup and operations

- [Installation](Get-Started/installation.md)
- [Full tenant configuration](Get-Started/full-tenant-configuration.md) — end-to-end tenant setup and governance checklist
- [Flow lifecycle](Execution/flow-lifecycle.md)
- [Tracing and cost](Develop/tracing-and-cost.md)
- [Token cost and context strategy](Develop/token-cost-and-context-strategy.md) — budgets, caches, RAG/context, consulting costs
- [System events reference](Develop/system-events-reference.md) — execution, authoring, and SSE catalogues
- [Known limitations](Develop/limitations.md) — what does not work the way you would assume
- [Deployment](Deployment/docker.md)

## Contributing

- [Contributing (docs hub)](Contributing/README.md) — doc conventions and `mkdocs build`
- Repository root **`CONTRIBUTING.md`**, **`DEVELOPMENT.md`**, **`SECURITY.md`** — PR flow, local setup, responsible disclosure (not part of the MkDocs build)
