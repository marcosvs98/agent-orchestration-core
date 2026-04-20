# Vector store

## Definition

A **vector store** record defines **embedding model name**, **dimension**, **metric**, and related invariants so that **indexing** (offline/batch) and **retrieval** (online query) use compatible vectors. It is the contract anchor for embedding orchestration.

## What it is not

- Not the full content store alone: documents/chunks reference it.
- Not an LLM chat model: it is specifically the embedding index configuration.

## Code

- `src/domain/rag/` (runtime, repositories)
- Embedding adapters under `src/domain/rag/adapters/`

## Persistence

- `vector_store`. See [persistence tables](../persistence-tables.md).

## Related

- [RAG config](rag-config.md)
- [RAG overview](../../RAG/index.md)
