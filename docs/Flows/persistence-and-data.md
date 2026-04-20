# Flows — persistence and data

This page lists **SQL tables** owned by the **flows** authoring domain. **Row-level authoring lifecycle**, draft vs snapshot semantics, and compile flow are documented in **[Authoring and persistence](authoring-and-persistence.md)** — that page remains the single deep-dive for flow data.

## Tables (from glossary)

See [Persistence tables](../Glossary/persistence-tables.md) sections **Flows (authoring)** and **Deployments / materialization**, including:

| Table | Role |
|-------|------|
| `flow`, `flow_version` | Flow identity and versions |
| `flow_graph`, `flow_graph_draft`, `flow_graph_snapshot` | Draft vs compiled graph |
| `node`, `node_template`, `condition_expression` | Nodes and edge conditions |
| `flow_snapshot`, `flow_deployment`, `snapshot_binding` | Bundles and environment slots |

Runtime execution tables (`flow_run`, `graph_state`, …) belong to [Execution](../Execution/index.md), not this page.

## Related

- [Authoring and persistence](authoring-and-persistence.md) (canonical detail)
- [Flows overview](index.md)
