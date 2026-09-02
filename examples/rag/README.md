# RAG examples

Four runnable examples covering the retrieval stack: the chunking-strategy catalog, the
embedding-model pair, retrieval tuning, and the gate chain that decides whether retrieval runs
at all.

Each prints a narrated trace and exits non-zero if the runtime does not behave as described.

| Example | Needs the API? | Covers |
|---------|----------------|--------|
| `chunking_strategies` | no | All four `RagChunkingStrategy` values, their params, bounds and failure modes |
| `corpus_kinds_and_activation` | no | `RagCorpusKind`, and the structural → policy → heuristic gate chain |
| `embedding_dimensions` | yes | `embedding` vs `indexing_embedding`, Matryoshka truncation, dimension guards |
| `retrieval_tuning` | yes | `top_k`, `similarity_threshold`, `filters_override`, ingest dedupe |

## Running

The two offline examples need nothing:

```bash
PYTHONPATH=src uv run python -m examples.rag.chunking_strategies
PYTHONPATH=src uv run python -m examples.rag.corpus_kinds_and_activation
```

The two API examples read `examples/.state/full_tenant_setup.json` for a tenant and token, and
make real OpenAI embedding calls:

```bash
PYTHONPATH=src uv run python -m examples.full_tenant_setup     # once
PYTHONPATH=src uv run python -m examples.rag.retrieval_tuning
PYTHONPATH=src uv run python -m examples.rag.embedding_dimensions
```

## The model in one page

```
ingest ──▶ chunking rule ──▶ indexing embedding ──▶ rag_chunk.embedding (pgvector)
                                                            │
query ───▶ activation gates ──▶ query embedding ────────────┘
                                                            │
                                                    cosine distance
                                                            │
                                          top_k LIMIT, then similarity_threshold
                                                            │
                                                     RagContext
```

**`vector_store`** fixes the physical width of every stored vector. **`rag_chunking_rule`** is a
named, reusable strategy + params. **`rag_config`** binds a store to a rule and adds the embedding
pair, retrieval options and the generation contract. Documents belong to a config; retrieval is
isolated by `rag_config_id`.

## Chunking strategies

| Strategy | Unit | Use when |
|----------|------|----------|
| `TOKEN_WINDOW` | tokens (`cl100k_base`) | Default. Predictable embedding cost per chunk. |
| `RECURSIVE_CHARACTER` | characters | Prose where paragraph and sentence boundaries matter. |
| `SEMANTIC` | tokens | **Currently an alias for `TOKEN_WINDOW`** — see below. |
| `PER_PAGE` | caller-supplied pages | Pre-paginated sources; ingest must send `pages`. |

Shared bounds: `max_chunks_per_document` and `max_document_chars`. When a document exceeds them
the chunker returns `truncated=True` — that means chunks were **dropped**, so the tail of the
document was never embedded and can never be retrieved. Treat it as a data-loss signal.

`SEMANTIC` has no embedding-similarity boundary detection: `_chunks_for_ingest` dispatches it to
the same `_chunk_text` call as `TOKEN_WINDOW`. `chunking_strategies` asserts the two produce
byte-identical output. Choosing it buys a different label in the rule row and nothing else.

`overlap_tokens` is not validated against `target_tokens`. When overlap ≥ target the window cannot
advance a full step, so the chunker falls back to a one-token step and burns through
`max_chunks_per_document`. Keep overlap at 10–20% of target.

## The embedding pair

A config carries two embedding blocks: `embedding` builds the **query** vector, and the optional
`indexing_embedding` builds the **chunk** vectors.

When the store was built by the indexing model and the query width is smaller, the runtime uses
the **indexing** model for the query too, truncated to the query width — and Postgres compares
with `subvector(embedding, 1, query_dimension)`. Both sides then live in the same vector space at
a lower fidelity, which is only valid because `text-embedding-3-*` are Matryoshka models. Nothing
in the code checks that the two aliases are compatible.

The guard is one-directional: a query **narrower** than the store is truncated and works; a query
**wider** than the store is rejected at query time with
`rag_retrieval_embedding_dimension_vector_store_mismatch` — long after the corpus was ingested.
Nothing validates the pair at authoring time. Pick the store width first.

Supported widths: 512, 1024, 1536, 3072.

## Retrieval

`score = 1.0 - cosine_distance`. `top_k` is a SQL `LIMIT` ordered by distance; the similarity
threshold is applied afterwards in Python, so a request can legitimately return fewer items than
`top_k`.

Supported `filters_override` keys are exactly: `source`, `doc_type`, `scope`, `user_id`,
`category`, `tool_intent`, `created_after`, `expires_after`. **Any other key is silently ignored**
— a filter on a metadata field that is not in that list widens the query instead of narrowing it.

The default `similarity_threshold` of `0.50` is aggressive for short queries against short chunks.
Vector search always returns its nearest neighbours; there is no notion of "no answer" in the
index. The threshold is the only thing between an off-topic query and a confidently wrong answer,
so calibrate it on real queries — `retrieval_tuning` prints the score separation between an
on-topic and an off-topic query against the same corpus.

## The activation gate chain

Retrieval frequently "does nothing" for reasons that never reach the vector store.
`RagActivationService.decide` short-circuits in order, and the reason it returns is the field
worth logging:

1. **Structural** — the node's `AITaskContextFlags`. `allow_rag_tenant` for tenant knowledge,
   `allow_user_memory_*` for user memory. No flags means denied, not defaulted open.
2. **Policy** — the active RAG policy version, per LLM task type. A task type missing from
   `defaults` falls back to disabled. `require_published_rag_config` rejects a `DRAFT` config.
3. **Heuristic** — `INPUT_EMPTY`, `INPUT_TOO_SHORT` (`min_query_chars_by_scope`, default 8),
   `INPUT_STRUCTURED` (a payload starting with `{` or `[` when `allow_structured_input` is false).

Only `POLICY_DEFAULT_ALLOW` reaches `get_context`.

## Known defects these examples surface

Reproduced against a live service. The ones that change how you would deploy are written up in
[Known limitations](../../docs/Develop/limitations.md).

**Fixed here — the sliding window never terminated.** `_chunk_text` set `start = end - overlap`,
so once the final window was reached `start` stopped advancing and the same tail chunk was
re-emitted until `max_chunks_per_document`. A 202-token document produced **100 chunks, 4 of them
distinct**, reported `truncated=True`, and cost ~25× the embeddings it needed — while flooding
`top_k` with copies of one chunk. Both `TOKEN_WINDOW` and `SEMANTIC` were affected. Regression
tests are in `tests/unit/rag/test_rag_chunking.py`.

**Open — `/rag-retrieval:preview` cannot see tenant knowledge.** The endpoint calls
`get_context(user_id=auth.principal_id)`, and a non-null `user_id` becomes a hard filter on
`doc_metadata->>'user_id'`. Tenant-wide documents carry no `user_id`, so preview returns
`NO_MATCHES` for exactly the corpus it is most useful for. The runtime path is unaffected — it
passes `user_id=None` for tenant knowledge. `retrieval_tuning` works around this by ingesting a
user-scoped copy of each document.

**Open — ingest dedupe is tenant-wide and crosses configs.** `get_document_by_hash` filters on
`(tenant_id, content_hash)` only — not `rag_config_id`, not `user_id`. Consequences, both
demonstrated in `retrieval_tuning` steps 7 and 8:

- two users storing the same sentence share one row, and the first writer's `user_id` is the one
  retrieval filters on
- a document whose content already exists under **another config** is silently not added to the
  new one, which then can never retrieve it — with a `202 Accepted` response and a background
  task that swallows the skip

Shared boilerplate — a disclaimer, a standard FAQ answer — belongs to whichever config ingested it
first. Vary the content, not just the metadata.
