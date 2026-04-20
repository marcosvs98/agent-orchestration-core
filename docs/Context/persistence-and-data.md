# Context — persistence and data

The **context** bounded context mostly orchestrates **reads/writes through ports**; a subset of persisted state maps to tables listed in [Persistence tables](../Glossary/persistence-tables.md).

## Tables (typical ownership)

| Table | Role |
|-------|------|
| `user_memory_profile` | User memory preferences / profile used by memory retrieval |
| `end_user` | Identity for conversation-scoped features (shared with conversation) |
| `session` | Conversation session rows (shared with conversation) |

RAG chunks and vector metadata live under [RAG — data model](../RAG/data-model-reference.md), not duplicated here.

## Related

- [Context overview](index.md)
- [Services and ports](services-and-ports.md)
