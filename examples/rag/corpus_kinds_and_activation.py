from __future__ import annotations

from typing import Dict, Optional

from domain.ai_policy.schemas.ai import AITaskContextFlags
from domain.context.services.rag_activation_service import RagActivationService
from domain.governance.schemas.rag_policy import RagActivationDecisionReason, RagActivationScope
from domain.rag.schemas.rag import RagCorpusKind
from examples.support import expect, field, heading


def activation() -> RagActivationService:
    return RagActivationService(
        repository=None,
        rag_repository=None,
        tools_repository=None,
        rag_policy_service=None,
        tracer=None,
    )


def structural(scope: RagActivationScope, flags: AITaskContextFlags | None) -> bool:
    return activation()._structural_gate(scope=scope, task_flags=flags)


def heuristic(
    scope: RagActivationScope,
    user_input: str | None,
    *,
    min_chars: Optional[Dict[RagActivationScope, int]] = None,
    allow_structured: bool = False,
) -> Optional[RagActivationDecisionReason]:
    return RagActivationService._heuristic_reason(
        scope=scope,
        user_input=user_input,
        min_chars_by_scope=min_chars if min_chars is not None else {},
        allow_structured_input=allow_structured,
    )


def main() -> None:
    print("RAG corpus kinds, and the gate chain that decides whether retrieval runs at all")

    heading("1. The three corpus kinds")
    field("RagCorpusKind", ", ".join(k.value for k in RagCorpusKind))
    print()
    print("  TENANT_KNOWLEDGE  shared documentation for the whole tenant. Retrieved with")
    print("                    user_id=None, so every user sees the same corpus.")
    print("  USER_MEMORY       per end-user facts written by MemoryCommitNode and the")
    print("                    memory extractor. Retrieved with a hard user_id filter, so")
    print("                    one user can never read another's memory.")
    print("  TOOL_CATALOG      phrasings that describe what a tool does. Retrieved by")
    print("                    ToolResolver with filters source=doc_type=tool_catalog and")
    print("                    category=TOOL_CATALOG, then intersected with the agent")
    print("                    version's tool bindings.")
    print()
    print("  corpus_kind is a label on the rag_config. search_similar_chunks never reads")
    print("  it: the query is isolated by rag_config_id, and then narrowed by whatever")
    print("  metadata filters the caller passes. So two corpora only stay apart because")
    print("  they live in different configs - a tool-catalog document ingested into a")
    print("  knowledge config is returned by any unfiltered query against that config.")

    heading("2. Gate 1 - structural: the NODE decides")
    print("  Every node row carries AITaskContextFlags. RagActivationService._structural_gate")
    print("  reads them before any policy is consulted, so a node that was created without")
    print("  the right flag can never retrieve, whatever the tenant policy says.")

    none_allowed = AITaskContextFlags()
    tenant_only = AITaskContextFlags(allow_rag_tenant=True)
    memory_only = AITaskContextFlags(allow_user_memory_vector=True)
    both = AITaskContextFlags(allow_rag_tenant=True, allow_user_memory_vector=True)

    for label, flags in (
        ("no flags", none_allowed),
        ("allow_rag_tenant", tenant_only),
        ("allow_user_memory_vector", memory_only),
        ("both", both),
    ):
        tenant_gate = structural(RagActivationScope.TENANT_KNOWLEDGE, flags)
        memory_gate = structural(RagActivationScope.USER_MEMORY_VECTOR, flags)
        field(label, f"TENANT_KNOWLEDGE={tenant_gate}  USER_MEMORY_VECTOR={memory_gate}")

    expect(
        structural(RagActivationScope.TENANT_KNOWLEDGE, memory_only) is False,
        "a memory-only node cannot reach tenant knowledge",
    )
    expect(
        structural(RagActivationScope.TENANT_KNOWLEDGE, None) is False,
        "a node with no flags at all is denied, not defaulted open",
    )
    print()
    print("  This is why the provisioning example sets allow_rag_tenant on every node:")
    print("  without it ToolResolver retrieves nothing and selects no tool.")

    heading("3. Gate 2 - policy: the TENANT decides, per task type")
    print("  The active rag policy version carries a per-task-type block:")
    print("    intent_selection / slot_filling / clarification / response_render /")
    print("    memory_extraction")
    print("  each with tenant_knowledge and user_memory_vector toggles and an optional")
    print("  allowed_tool_config_ids allowlist. A task type missing from `defaults` falls")
    print("  back to disabled, so adding a new LLM task silently turns its retrieval off")
    print("  until the policy is updated.")
    field("scopes", ", ".join(s.value for s in RagActivationScope))
    print()
    print("  require_published_rag_config=true additionally refuses a rag_config that is")
    print("  still DRAFT - reason RAG_CONFIG_NOT_PUBLISHED. That is the setting that makes")
    print("  'ingest then forget to publish' a silent no-retrieval state.")

    heading("4. Gate 3 - heuristics: the INPUT decides")
    print("  Cheap guards that stop the service paying for an embedding it cannot use.")

    cases = [
        ("empty string", "", {}, False),
        ("whitespace only", "   ", {}, False),
        ("shorter than min_query_chars", "hi", {RagActivationScope.TENANT_KNOWLEDGE: 8}, False),
        ("long enough", "what is the meal limit", {RagActivationScope.TENANT_KNOWLEDGE: 8}, False),
        ("json payload, structured denied", '{"amount": 120}', {}, False),
        ("json payload, structured allowed", '{"amount": 120}', {}, True),
    ]
    for label, text, min_chars, allow_structured in cases:
        reason = heuristic(
            RagActivationScope.TENANT_KNOWLEDGE,
            text,
            min_chars=min_chars,
            allow_structured=allow_structured,
        )
        field(label, reason.value if reason is not None else "allowed")

    expect(
        heuristic(
            RagActivationScope.TENANT_KNOWLEDGE,
            "hi",
            min_chars={RagActivationScope.TENANT_KNOWLEDGE: 8},
        )
        is not None,
        "a query below min_query_chars_by_scope is refused before embedding",
    )
    expect(
        heuristic(RagActivationScope.TENANT_KNOWLEDGE, "what is the meal limit") is None,
        "a normal question passes every heuristic gate",
    )
    print()
    print("  The default min is 8 characters when the scope is absent from the policy map.")
    print("  Short but meaningful queries - a product code, a ticket id - are dropped by")
    print("  this gate, so raise min_query_chars_by_scope deliberately rather than by")
    print("  copying the demo values.")

    heading("5. The full chain")
    print("  decide() short-circuits in this order, and the reason it returns is the")
    print("  single most useful field when retrieval 'silently does nothing':")
    print()
    print("    STRUCTURAL_DENY          node flags forbid this scope")
    print("    POLICY_MISSING           no active rag policy version for the tenant")
    print("    POLICY_DENY              the policy disables this scope for this task type")
    print("    RAG_CONFIG_MISSING       no rag_config_id resolved for the node")
    print("    RAG_CONFIG_NOT_FOUND     the id does not exist")
    print("    RAG_CONFIG_TENANT_MISMATCH  it belongs to another tenant")
    print("    RAG_CONFIG_NOT_PUBLISHED require_published_rag_config and it is DRAFT")
    print("    USER_ID_MISSING          USER_MEMORY_VECTOR without a user")
    print("    INPUT_EMPTY / INPUT_TOO_SHORT / INPUT_STRUCTURED   heuristic gates")
    print("    TOOL_CONFIG_EXPLICIT_DENY / _ALLOW   per-tool allowlist")
    print("    POLICY_DEFAULT_ALLOW     retrieval runs")
    print()
    print("  Only the last one reaches get_context. Everything above it returns an empty")
    print("  context with a reason and never touches the vector store.")

    heading("6. Where each corpus is read from")
    print("  TENANT_KNOWLEDGE  MemoryRetrievalService -> tenant knowledge reader, user_id=None")
    print("  USER_MEMORY       MemoryRetrievalService -> user memory reader, user_id=<end user>,")
    print("                    optionally reranked by temporal decay (see runtime policy")
    print("                    memory_retrieval.temporal_scoring)")
    print("  TOOL_CATALOG      ToolCatalogRetriever, called by the ToolResolver node")
    print()
    print("  Temporal decay multiplies each score by exp(-age / half_life_seconds) and")
    print("  re-sorts, fetching candidate_multiplier x top_k candidates first so recent")
    print("  items can overtake older ones. It is off by default.")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
