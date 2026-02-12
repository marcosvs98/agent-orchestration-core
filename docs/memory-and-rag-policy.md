# Memory and RAG policy

This document describes priority rules for context layers, when memory is written, the use of `doc_type` as memory type, growth controls (TTL and per-user cap), and the optional use of layer weights.

## Priority

1. **Order in prompt:** Tenant RAG context is appended first, then user memory context. The prompt resolver builds the final prompt in this order so the model sees tenant knowledge before user-specific content.

2. **Structured context merge:** When both tenant and user structured context are present, user memory overrides or takes precedence over tenant (User > Tenant). This applies to structured fields such as preferences and profile; vector retrieval is already scoped by `user_id` for user memory.

## When to write

Memory items are written when:

- An active `MemoryPolicyVersion` exists for the tenant and the item’s schema is allowed.
- The write target is enabled for that schema (e.g. `USER_PREFERENCE`, `USER_MEMORY_PROFILE`, `USER_MEMORY_VECTOR`).
- Writes are triggered by:
  - Post-flow hooks (e.g. memory extraction after run completion).
  - Tool outcomes (explicit user or tool output).
  - Policy-allowed schemas and targets; `allow_memory_write` and task flags control whether the runtime may persist memory for a given task.

## doc_type as memory type

The RAG document field `doc_type` (and its representation in `doc_metadata`) is the memory type for vector-stored memory. For example, `USER_MEMORY_ITEM` identifies documents ingested from the memory write pipeline. Filtering and typing of vector memory use `doc_type` (and scope/user_id) to distinguish tenant knowledge from user memory and to support future memory-type filtering.

## Growth control: TTL and per-user cap

- **TTL as primary control:** The main mechanism to control growth of user memory is TTL: documents store `expires_at` in metadata; retrieval filters with `expires_after` so expired documents are not returned. Cleanup or background expiry can be implemented separately; the primary lever is TTL/expires_at so that growth is bounded over time without relying only on a hard cap.

- **Per-user cap as hard limit:** A configurable maximum number of documents per user for USER_MEMORY (`MAX_USER_MEMORY_DOCUMENTS`) is enforced at write time. When the count of USER_MEMORY documents for that `(tenant_id, user_id)` reaches or exceeds the cap, new RAG ingest for that user is skipped (no new document is created). The event `domain.memory.write.cap_reached` is emitted for observability. TTL remains the primary growth control; the cap is a secondary hard limit to avoid unbounded growth.

## Layer weights (optional)

Layer weights are not implemented by default. If, after measuring, the order of context in the prompt is insufficient to achieve the desired behavior, a single multiplier per layer may be added when building the final ordered list for the prompt (e.g. when merging or ranking tenant vs user results). No new abstraction is required; only a numeric multiplier per layer applied at merge/ranking time. Implement only if needed after measurement.
