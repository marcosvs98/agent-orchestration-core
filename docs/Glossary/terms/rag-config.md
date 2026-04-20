# RAG config

## Definition

**RAG config** captures **retrieval** settings for a tenant or scope: which vector store, chunking, models, and policies apply. Runtime RAG services use this with [Vector store](vector-store.md) metadata to ensure indexing and query embeddings stay consistent.

## What it is not

- Not the vector index itself: physical chunks live in `rag_document` / `rag_chunk` (and provider-specific storage).
- Not a single prompt: prompts are versioned separately where applicable.

## Code

- `src/domain/rag/`

## Persistence

- `rag_config`, `rag_chunking_rule`, RAG caches. See [persistence tables](../persistence-tables.md).

## Related

- [Vector store](vector-store.md)
- [RAG overview](../../RAG/index.md), [Runtime and integration](../../RAG/runtime-and-integration.md), [Data model reference](../../RAG/data-model-reference.md)
