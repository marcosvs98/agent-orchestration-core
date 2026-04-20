# RAG overview

**Retrieval-Augmented Generation (RAG)** in this service means: **embedding** user or document text, **storing** chunks in a tenant-scoped vector index, and **retrieving** relevant chunks at inference time under **governance** (policies, activation, limits). Implementation spans `src/domain/rag/` (services, ports, repositories) and persistence for `rag_config`, `vector_store`, `rag_document`, and `rag_chunk` (see [Persistence tables](../Glossary/persistence-tables.md)).

## Indexing vs retrieval (conceptual)

```mermaid
flowchart TB
  subgraph index [Indexing / batch]
    DOC[Documents]
    CH[Chunk + embed]
    VS[(Vector store metadata)]
    DOC --> CH --> VS
  end
  subgraph online [Retrieval / request path]
    Q[User query]
    EQ[Embed query]
    SR[Search similar chunks]
    Q --> EQ --> SR
    VS -.->|dimension/model contract| SR
  end
```

**Vector store** rows define **embedding model** and **dimension** so indexing and query paths stay compatible. See [Vector store](../Glossary/terms/vector-store.md) and [RAG config](../Glossary/terms/rag-config.md).

## Product boundaries

- RAG is optional per flow or task: **activation** logic decides when retrieval runs (see domain `context` and RAG services).
- Caching (`rag_query_cache`, `semantic_answer_cache`) is an optimization layer, not a second source of truth.

## Further reading

- [Embedding orchestration](embedding-orchestration.md) — ports, executor, adapter, vector-store contract
- [Runtime and integration](runtime-and-integration.md) — retrievers, policies, validation script, HTTP API
- [Data model reference](data-model-reference.md) — tables, ER diagrams, ORM pointers
- [GLM-OCR (external)](glm-ocr.md) — optional OCR preprocessing for ingest pipelines
- [Glossary index](../Glossary/index.md), [Domain overview](../Models/domain-overview.md)
