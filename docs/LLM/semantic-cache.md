# Semantic cache

`SemanticCacheService` (`src/domain/llm/services/semantic_cache_service.py`) supports **answer-level** caching for layered inference: embed the user query, find similar stored responses, and persist new answers with a TTL.

## Lookup

`lookup(tenant_id, task_type, user_query, similarity_threshold)`:

1. Embeds `user_query` via `EmbeddingExecutor.execute` with a fixed `EmbeddingContract`: `provider="openai"`, `model="text-embedding-3-small"`, dimension from service init (default `DEFAULT_EMBEDDING_DIMENSION`), `metric="cosine"`, `version=1`, `use_case="retrieval"`, `allow_fallback=False`.
2. Calls `SemanticCacheRepository.search_similar` with the embedding, threshold, and current time (for expiry filtering).
3. On miss: returns `CacheLookupResult(hit=False, query_embedding=<embedding>)` so callers can **reuse** the embedding on persist.
4. On hit: increments hit count via `increment_hit`, wraps the row in `SemanticCacheEntry`, returns `hit=True` and the same `query_embedding`.

## Persist

`persist(...)` stores a new row when layered inference (or another caller) wants to cache an answer:

- If `query_embedding` is **None**, embeds `user_query` with `use_case="indexing"`.
- Computes `expires_at` from `ttl_seconds`.
- Builds `SemanticAnswerCache` ORM (`src/infra/database/models/llm/semantic_answer_cache.py`) with `query_hash = SHA256(user_query)`, `response_json`, `model_alias`, `inference_layer`, optional `similarity_score`, and `hit_count=0`.

## Persistence table

The `semantic_answer_cache` table is listed in [Persistence tables](../Glossary/persistence-tables.md) (cache category). RAG docs also note this table is **not** part of chunk retrieval; it is LLM answer cache ([RAG data model reference](../RAG/data-model-reference.md)).

## See also

- [Context and cache strategy](../Architecture/context-and-cache-strategy.md) — how this cache relates to RAG and the other cache layers
- [Layered inference](layered-inference.md)
- [Embedding orchestration](../RAG/embedding-orchestration.md) — `EmbeddingExecutor` contract details
