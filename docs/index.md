# agent-orchestration-core

Multi-tenant **cognitive orchestration**: natural language and API events in, **deterministic graph execution**, retrieval, and **governance** out. The canonical shape of the system is in [Architecture overview](Architecture/ARCHITECTURE.md); this page is the **MkDocs home** — quick entry points and operations.

## Start here

- **[Documentation map (AI)](AI/documentation-map.md)** — task → docs → code (same content as the nav hub **Domain documentation**).
- **[Glossary](Glossary/index.md)** — domain terms and [persistence tables](Glossary/persistence-tables.md).
- **[Architecture overview](Architecture/ARCHITECTURE.md)** — bounded contexts, hexagonal layout, full context table.
- **[Runtime vs authoring](Architecture/runtime-vs-authoring.md)** — design-time vs execution-time rules.
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
- [Flow lifecycle](Execution/flow-lifecycle.md)
- [Tracing and cost](Develop/tracing-and-cost.md)
- [Token cost and context strategy](Develop/token-cost-and-context-strategy.md) — budgets, caches, RAG/context, consulting costs
- [System events reference](Develop/system-events-reference.md) — execution, authoring, and SSE catalogues
- [Coverage incremental loop](Develop/coverage-incremental-loop.md), [Dead code pipeline](Develop/dead-code-pipeline.md)
- [Deployment](Deployment/docker.md)

## Contributing

- [Contributing (docs hub)](Contributing/README.md) — doc conventions and `mkdocs build`
- Repository root **`CONTRIBUTING.md`**, **`DEVELOPMENT.md`**, **`SECURITY.md`** — PR flow, local setup, responsible disclosure (not part of the MkDocs build)
