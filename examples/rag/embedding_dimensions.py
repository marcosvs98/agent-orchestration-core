from __future__ import annotations

from typing import Tuple
from uuid import uuid4

from examples.api import ApiClient, ApiError, DemoState, require_id
from examples.rag.chunking_strategies import chunker
from examples.support import expect, field, heading

from domain.rag.schemas.rag import (
    SUPPORTED_EMBEDDING_DIMENSIONS,
    RagConfigOptions,
    RagEmbeddingOptions,
)


class VectorStoreStub:
    def __init__(self, embedding_model: str, embedding_dimension: int) -> None:
        self.embedding_model = embedding_model
        self.embedding_dimension = embedding_dimension
        self.metric = "cosine"
        self.version = 1


def resolve(options: RagConfigOptions, store: VectorStoreStub) -> RagEmbeddingOptions:
    return chunker()._query_embedding_options_for_retrieval(options=options, vector_store=store)


def options_for(
    *,
    query_model: str,
    query_dimension: int,
    index_model: str | None = None,
    index_dimension: int | None = None,
) -> RagConfigOptions:
    indexing = None
    if index_model is not None and index_dimension is not None:
        indexing = RagEmbeddingOptions(model_alias=index_model, dimension=index_dimension)
    return RagConfigOptions(
        embedding=RagEmbeddingOptions(model_alias=query_model, dimension=query_dimension),
        indexing_embedding=indexing,
    )


def main() -> None:
    print("RAG embeddings: one model to index, a cheaper one to query")
    field("supported dimensions", ", ".join(str(d) for d in SUPPORTED_EMBEDDING_DIMENSIONS))
    print()
    print("  A rag_config carries TWO embedding blocks:")
    print("    embedding           - used for the QUERY at retrieval time")
    print("    indexing_embedding  - used for the CHUNKS at ingest time (optional)")
    print("  They are allowed to differ, and _query_embedding_options_for_retrieval decides")
    print("  what actually gets used for the query vector.")

    heading("1. No indexing_embedding: the query block is used verbatim")
    store = VectorStoreStub("text-embedding-3-small", 1536)
    resolved = resolve(
        options_for(query_model="text-embedding-3-small", query_dimension=1536), store
    )
    field("resolved model", resolved.model_alias)
    field("resolved dimension", resolved.dimension)
    expect(resolved.dimension == 1536, "the query embedding block is used as declared")

    heading("2. Matryoshka: index with the large model, query at a smaller width")
    print("  When the store was built by the indexing model AND the query width is smaller,")
    print("  the INDEXING model is used to build the query vector, truncated to the query")
    print("  width. Postgres then compares with subvector(embedding, 1, query_dimension),")
    print("  so a 3072-d stored vector is cut to its first 1536 dimensions.")
    store = VectorStoreStub("text-embedding-3-large", 3072)
    options = options_for(
        query_model="text-embedding-3-small",
        query_dimension=1536,
        index_model="text-embedding-3-large",
        index_dimension=3072,
    )
    resolved = resolve(options, store)
    field("declared query model", options.embedding.model_alias)
    field("resolved query model", resolved.model_alias)
    field("resolved dimension", resolved.dimension)
    expect(
        resolved.model_alias == "text-embedding-3-large",
        "the INDEXING model wins, so query and chunk vectors share one vector space",
    )
    expect(resolved.dimension == 1536, "but it is truncated to the declared query width")
    print()
    print("  This only works because text-embedding-3-* are Matryoshka models: a prefix of")
    print("  the vector is still a valid, lower-fidelity embedding. Mixing two unrelated")
    print("  models this way would compare vectors from different spaces and score noise -")
    print("  nothing in the code prevents that, so the alias pair is yours to get right.")

    heading("3. Guards")
    store = VectorStoreStub("text-embedding-3-large", 3072)
    mismatched = options_for(
        query_model="text-embedding-3-small",
        query_dimension=1536,
        index_model="text-embedding-3-large",
        index_dimension=1024,
    )
    resolved = resolve(mismatched, store)
    field("indexing dim != store dim", f"falls back to {resolved.model_alias}")
    expect(
        resolved.model_alias == "text-embedding-3-small",
        "when indexing_embedding does not match the store, the query block is used",
    )

    equal_width = options_for(
        query_model="text-embedding-3-large",
        query_dimension=3072,
        index_model="text-embedding-3-large",
        index_dimension=3072,
    )
    resolved = resolve(equal_width, store)
    field("query dim == store dim", f"uses {resolved.model_alias} at {resolved.dimension}")
    expect(resolved.dimension == 3072, "no truncation when the widths already agree")

    heading("4. The runtime refuses a query wider than the store")
    client, state = load_state()
    suffix = uuid4().hex[:8]
    narrow_store = client.post(
        "/core/v1/vector-stores",
        {
            "name": f"rag-dim-example-{suffix}",
            "embedding_model": "text-embedding-3-small",
            "embedding_dimension": 1536,
        },
        label="create a 1536-d vector store",
    )
    narrow_store_id = require_id(narrow_store, "id", "vector store")
    rule = client.post(
        "/core/v1/rag-chunking-rules",
        {
            "name": f"rag-dim-rule-{suffix}",
            "status": "ACTIVE",
            "strategy": "TOKEN_WINDOW",
            "params": {"strategy": "TOKEN_WINDOW", "target_tokens": 120, "overlap_tokens": 20},
        },
        label="create chunking rule",
    )
    rule_id = require_id(rule, "id", "chunking rule")
    too_wide = client.post(
        "/core/v1/rag-configs",
        {
            "vector_store_id": narrow_store_id,
            "chunking_rule_id": rule_id,
            "corpus_kind": "TENANT_KNOWLEDGE",
            "options": {
                "embedding": {
                    "provider": "OPENAI",
                    "model_alias": "text-embedding-3-large",
                    "dimension": 3072,
                    "model_id": state.get("model_ids")["text-embedding-3-large"],
                },
                "retrieval": {"top_k": 5, "similarity_threshold": 0.2},
                "generation_contract": {"allow_extrapolation": False},
            },
        },
        label="create config whose query width exceeds the store",
    )
    too_wide_id = require_id(too_wide, "id", "rag config")
    print("  The config was accepted: nothing validates the pair at authoring time.")

    try:
        client.post(
            "/core/v1/rag-retrieval:preview",
            {"rag_config_id": too_wide_id, "user_input": "qualquer pergunta"},
            label="preview against the mismatched config",
        )
        raise SystemExit("FAILED: expected the dimension guard to reject this query")
    except ApiError as exc:
        field("preview", f"{exc.status_code}")
        expect(
            "rag_retrieval_embedding_dimension_vector_store_mismatch" in exc.body,
            "retrieval refuses a query wider than the stored vectors",
        )
    print()
    print("  The guard is one-directional: a query NARROWER than the store is truncated and")
    print("  works, a query WIDER than the store is rejected at query time - long after the")
    print("  corpus was ingested. Pick the store width first, then keep every query width")
    print("  at or below it.")

    heading("Choosing the pair")
    print("  index 3072 / query 1536   best recall per query token; the default in the")
    print("                            provisioning example")
    print("  index 1536 / query 1536   simplest; one model everywhere")
    print("  index 3072 / query 512    cheapest queries, noticeably weaker ranking")
    print("  query > store width       rejected at retrieval time - never ship it")

    print()
    print("Done.")


def load_state() -> Tuple[ApiClient, DemoState]:
    state = DemoState().load()
    client = ApiClient(state.get("base_url"), state.get("tenant_token"))
    return client, state


if __name__ == "__main__":
    main()
