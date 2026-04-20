# AI policy — persistence and data

Authoritative SQL shapes live in Alembic migrations. See [Persistence tables](../Glossary/persistence-tables.md).

## Tables (this bounded context)

| Table | Role |
|-------|------|
| `ai_execution_policy` | Per-tenant AI execution policy root |
| `ai_execution_policy_version` | Versioned policy payload |
| `node_ai_execution_policy_binding` | Binds a node to an AI execution policy version |
| `model` | Model catalog rows surfaced through this domain |

`llm_*` pricing and provider tables are shared with [LLM](../LLM/index.md); see the **LLM / pricing** section in the glossary.

## Related

- [AI policy overview](index.md)
- [Governance — policy model](../Governance/policy-model-and-versioning.md)
