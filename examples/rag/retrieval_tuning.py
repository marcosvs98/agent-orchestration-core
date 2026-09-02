from __future__ import annotations

import base64
import json
import os
import time
from typing import Any, Dict, Final, List, Tuple
from uuid import uuid4

from examples.api import ApiClient, DemoState, require_id
from examples.rag._corpus import KNOWLEDGE_DOCUMENTS
from examples.support import expect, field, heading

INGEST_WAIT_SECONDS: Final[int] = int(os.environ.get("AOC_INGEST_WAIT_SECONDS", "60"))
PERMISSIVE_THRESHOLD: Final[float] = 0.15
QUERY: Final[str] = "what is the meal limit while travelling?"


def principal_of(token: str) -> str:
    payload = token.split(".")[1]
    padded = payload + "=" * (-len(payload) % 4)
    return str(json.loads(base64.urlsafe_b64decode(padded)).get("principal_id"))


def provision_corpus(client: ApiClient, state: DemoState, principal_id: str) -> Dict[str, Any]:
    suffix = uuid4().hex[:8]

    store = client.post(
        "/core/v1/vector-stores",
        {
            "name": f"rag-example-store-{suffix}",
            "embedding_model": "text-embedding-3-large",
            "embedding_dimension": 3072,
        },
        label="create vector store",
    )
    store_id = require_id(store, "id", "vector store")

    rule = client.post(
        "/core/v1/rag-chunking-rules",
        {
            "name": f"rag-example-window-{suffix}",
            "status": "ACTIVE",
            "strategy": "TOKEN_WINDOW",
            "params": {
                "strategy": "TOKEN_WINDOW",
                "target_tokens": 120,
                "overlap_tokens": 20,
                "max_chunks_per_document": 100,
                "max_document_chars": 100000,
            },
        },
        label="create chunking rule",
    )
    rule_id = require_id(rule, "id", "chunking rule")

    config = client.post(
        "/core/v1/rag-configs",
        {
            "vector_store_id": store_id,
            "chunking_rule_id": rule_id,
            "corpus_kind": "TENANT_KNOWLEDGE",
            "options": {
                "embedding": {
                    "provider": "OPENAI",
                    "model_alias": "text-embedding-3-small",
                    "dimension": 1536,
                    "model_id": state.get("model_ids")["text-embedding-3-small"],
                },
                "indexing_embedding": {
                    "provider": "OPENAI",
                    "model_alias": "text-embedding-3-large",
                    "dimension": 3072,
                    "model_id": state.get("model_ids")["text-embedding-3-large"],
                },
                "retrieval": {
                    "top_k": 5,
                    "similarity_threshold": PERMISSIVE_THRESHOLD,
                    "filters": None,
                },
                "generation_contract": {"allow_extrapolation": False},
            },
        },
        label="create rag config",
    )
    config_id = require_id(config, "id", "rag config")

    documents: List[Dict[str, Any]] = []
    for doc in KNOWLEDGE_DOCUMENTS:
        documents.append(
            {
                "source": f"rag-example-{suffix}",
                "doc_type": doc["doc_type"],
                "content": f"[{suffix}] {doc['content']}",
                "version": "1",
                "metadata": dict(doc["metadata"]),
            }
        )
        documents.append(
            {
                "source": f"rag-example-{suffix}",
                "doc_type": doc["doc_type"],
                "content": f"[{suffix}] Personal note from {principal_id}. {doc['content']}",
                "version": "1",
                "metadata": {**doc["metadata"], "user_id": principal_id},
            }
        )

    accepted = client.post(
        f"/core/v1/rag-configs/{config_id}/documents:ingest",
        documents,
        label=f"ingest {len(documents)} documents",
    )
    field("job_id", accepted.get("job_id"))

    deadline = time.time() + INGEST_WAIT_SECONDS
    stored: List[Dict[str, Any]] = []
    while time.time() < deadline:
        stored = client.get(
            "/core/v1/rag-documents",
            params={"rag_config_id": config_id, "limit": 200},
            label="poll ingested documents",
        )
        ready = [d for d in stored if d.get("embedding_status") == "COMPLETED"]
        if len(ready) >= len(documents):
            break
        time.sleep(3)

    completed = len([d for d in stored if d.get("embedding_status") == "COMPLETED"])
    field("documents embedded", f"{completed}/{len(documents)}")
    if completed < len(documents):
        raise SystemExit(
            "not every document embedded; retrieval below would be misleading.\n"
            "check OPENAI_API_KEY and re-run."
        )

    client.post(f"/core/v1/rag-configs/{config_id}:validate", label="validate rag config")
    client.post(
        f"/core/v1/rag-configs/{config_id}:publish",
        {"change_type": "PUBLISH", "justification": "rag retrieval example"},
        label="publish rag config",
    )
    return {
        "rag_config_id": config_id,
        "vector_store_id": store_id,
        "chunking_rule_id": rule_id,
        "source": f"rag-example-{suffix}",
        "shared_content": documents[0]["content"],
    }


def preview(
    client: ApiClient,
    rag_config_id: str,
    *,
    query: str = QUERY,
    top_k: int | None = None,
    filters: Dict[str, Any] | None = None,
    label: str = "preview",
) -> Dict[str, Any]:
    body: Dict[str, Any] = {"rag_config_id": rag_config_id, "user_input": query}
    if top_k is not None:
        body["top_k_override"] = top_k
    if filters is not None:
        body["filters_override"] = filters
    return client.post("/core/v1/rag-retrieval:preview", body, label=label)


def show(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = context.get("context_items") or []
    field("eligible", context.get("eligible"))
    field("reason", context.get("reason"))
    field("items", len(items))
    for item in items:
        metadata = item.get("metadata") or {}
        print(
            f"      {float(item.get('score', 0.0)):.4f}  "
            f"{str(metadata.get('topic', '?')):<12} "
            f"user_id={str(metadata.get('user_id', '-')):<16} "
            f"{str(item.get('content'))[:44]!r}"
        )
    return items


def main() -> None:
    print("RAG retrieval: what actually controls what comes back")
    client, state = load_state()
    principal_id = principal_of(state.get("tenant_token"))
    field("principal_id", principal_id)

    heading("1. Provision a dedicated corpus")
    print("  Each document is ingested twice: once tenant-wide (no user_id in metadata)")
    print("  and once scoped to this principal. That difference matters in step 2.")
    print()
    print("  The two copies must differ in CONTENT, not only in metadata: documents are")
    print("  deduplicated on (tenant_id, content_hash) alone - not on rag_config_id and")
    print("  not on user_id - so byte-identical copies collapse into one row and whichever")
    print("  metadata landed first wins. Step 7 demonstrates that directly.")
    corpus = provision_corpus(client, state, principal_id)
    rag_config_id = corpus["rag_config_id"]

    heading("2. The preview endpoint is user-scoped, always")
    print("  POST /core/v1/rag-retrieval:preview calls get_context(user_id=auth.principal_id),")
    print("  and search_similar_chunks turns a non-null user_id into a hard filter on")
    print("  doc_metadata->>'user_id'. Tenant-wide documents carry no user_id, so they can")
    print("  never be returned by preview - only by the runtime, which passes user_id=None")
    print("  for TENANT_KNOWLEDGE.")
    baseline = preview(client, rag_config_id, label="preview (default top_k)")
    items = show(baseline)
    expect(len(items) > 0, "the user-scoped copies are retrievable")
    expect(
        all((item.get("metadata") or {}).get("user_id") == principal_id for item in items),
        "every returned item is the user-scoped copy - the tenant-wide twins are invisible here",
    )

    heading("3. top_k_override bounds the candidate set")
    for top_k in (1, 3, 8):
        context = preview(client, rag_config_id, top_k=top_k, label=f"top_k={top_k}")
        returned = len(context.get("context_items") or [])
        field(f"top_k={top_k}", f"{returned} items")
    print()
    print("  top_k is a LIMIT applied in SQL, ordered by cosine distance ascending. The")
    print("  similarity threshold is applied afterwards in Python, so a request can return")
    print("  fewer items than top_k - that is the threshold working, not a missing index.")

    heading("4. similarity_threshold decides what survives")
    wide = preview(client, rag_config_id, top_k=8, label="scores at threshold 0.15")
    scores = [float(i.get("score", 0.0)) for i in wide.get("context_items") or []]
    field("config threshold", PERMISSIVE_THRESHOLD)
    field("scores", ", ".join(f"{s:.3f}" for s in scores) or "(none)")
    for candidate in (0.20, 0.30, 0.40, 0.50):
        survivors = len([s for s in scores if s >= candidate])
        field(f"would survive >= {candidate:.2f}", f"{survivors}/{len(scores)}")
    print()
    print("  score = 1.0 - cosine_distance. The default in RagRetrievalOptions is 0.50,")
    print("  which is aggressive for short queries against short chunks - measure against")
    print("  your own corpus before trusting it.")

    heading("5. filters_override narrows by document metadata")
    print("  Supported keys: source, doc_type, scope, user_id, category, tool_intent,")
    print("  created_after, expires_after. Anything else is silently ignored.")
    by_doc_type = preview(
        client,
        rag_config_id,
        top_k=8,
        filters={"doc_type": "policy_limits"},
        label="filter doc_type=policy_limits",
    )
    filtered_items = show(by_doc_type)
    expect(
        all((i.get("metadata") or {}).get("topic") == "limits" for i in filtered_items),
        "the doc_type filter narrowed the corpus",
    )

    ignored = preview(
        client,
        rag_config_id,
        top_k=8,
        filters={"topic": "limits"},
        label="filter topic=limits (unsupported key)",
    )
    field("items with unsupported filter", len(ignored.get("context_items") or []))
    expect(
        len(ignored.get("context_items") or []) >= len(filtered_items),
        "an unsupported filter key is ignored rather than rejected",
    )
    print()
    print("  'topic' is real metadata on these documents but is NOT a supported filter key,")
    print("  so the query silently widened instead of narrowing. Use doc_type or category.")

    heading("6. An unrelated query still returns rows")
    miss = preview(
        client,
        rag_config_id,
        query="what is the euro exchange rate today?",
        top_k=5,
        label="unrelated query",
    )
    miss_items = show(miss)
    miss_scores = [float(i.get("score", 0.0)) for i in miss_items]
    best_relevant = max(scores) if scores else 0.0
    best_irrelevant = max(miss_scores) if miss_scores else 0.0
    field("best score, on-topic query", f"{best_relevant:.3f}")
    field("best score, off-topic query", f"{best_irrelevant:.3f}")
    expect(
        best_irrelevant < best_relevant,
        "the off-topic query scores strictly lower than the on-topic one",
    )
    print()
    print("  Vector search always returns its nearest neighbours - there is no notion of")
    print("  'no answer' in the index itself. With similarity_threshold at 0.15 this corpus")
    print("  happily answers a currency question with expense policy. The threshold is the")
    print("  only thing standing between an off-topic query and a confidently wrong answer,")
    print("  so calibrate it on real queries: here anything above ~0.40 separates the two.")
    print()
    print("  Only when every candidate falls below the threshold does get_context return")
    print("  eligible=false with reason=NO_MATCHES, which is the signal the generation")
    print("  contract reads: with allow_extrapolation=false the node must not invent one.")

    heading("7. Ingest is deduplicated on content hash alone")
    before = client.get(
        "/core/v1/rag-documents",
        params={"rag_config_id": rag_config_id, "limit": 200},
        label="count documents before",
    )
    replay = [
        {
            "source": "a-completely-different-source",
            "doc_type": "a_different_doc_type",
            "content": KNOWLEDGE_DOCUMENTS[0]["content"],
            "version": "2",
            "metadata": {"topic": "duplicate", "user_id": "another-user"},
        }
    ]
    client.post(
        f"/core/v1/rag-configs/{rag_config_id}/documents:ingest",
        replay,
        label="re-ingest identical content under new metadata",
    )
    time.sleep(6)
    after = client.get(
        "/core/v1/rag-documents",
        params={"rag_config_id": rag_config_id, "limit": 200},
        label="count documents after",
    )
    field("documents before", len(before))
    field("documents after", len(after))
    expect(
        len(after) == len(before),
        "identical content did not create a second document, despite different "
        "source, doc_type, version and user_id",
    )
    print()
    print("  get_document_by_hash filters on (tenant_id, content_hash) only. Two users")
    print("  storing the same sentence share one row, and the first writer's user_id is")
    print("  the one retrieval will filter on. Vary the content, not just the metadata.")

    heading("8. The dedupe is tenant-wide, so it crosses rag_config boundaries")
    second = client.post(
        "/core/v1/rag-configs",
        {
            "vector_store_id": corpus["vector_store_id"],
            "chunking_rule_id": corpus["chunking_rule_id"],
            "corpus_kind": "TENANT_KNOWLEDGE",
            "options": {
                "embedding": {
                    "provider": "OPENAI",
                    "model_alias": "text-embedding-3-small",
                    "dimension": 1536,
                    "model_id": state.get("model_ids")["text-embedding-3-small"],
                },
                "retrieval": {"top_k": 5, "similarity_threshold": PERMISSIVE_THRESHOLD},
                "generation_contract": {"allow_extrapolation": False},
            },
        },
        label="create a second rag config",
    )
    second_id = require_id(second, "id", "second rag config")
    client.post(
        f"/core/v1/rag-configs/{second_id}/documents:ingest",
        [
            {
                "source": "second-config",
                "doc_type": "policy_reimbursement",
                "content": corpus["shared_content"],
                "version": "1",
                "metadata": {"topic": "reimbursement"},
            }
        ],
        label="ingest content that already exists under config 1",
    )
    time.sleep(6)
    second_docs = client.get(
        "/core/v1/rag-documents",
        params={"rag_config_id": second_id, "limit": 200},
        label="list documents of config 2",
    )
    field("documents visible to config 2", len(second_docs))
    expect(
        len(second_docs) == 0,
        "the document was silently NOT added to the second config because another "
        "config in the same tenant already held that exact content",
    )
    print()
    print("  This is data loss with a 202 response: the caller is told the batch was")
    print("  accepted, the background task swallows the skip, and the second corpus can")
    print("  never retrieve a document it legitimately asked for. Any shared boilerplate")
    print("  - a disclaimer, a standard FAQ answer - belongs to whichever config ingested")
    print("  it first.")

    print()
    field("rag_config_id", rag_config_id)
    print("Done.")


def load_state() -> Tuple[ApiClient, DemoState]:
    state = DemoState().load()
    client = ApiClient(state.get("base_url"), state.get("tenant_token"))
    return client, state


if __name__ == "__main__":
    main()
