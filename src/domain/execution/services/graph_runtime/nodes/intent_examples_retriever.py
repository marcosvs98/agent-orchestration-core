from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.services.graph_runtime.types import IntentType
from domain.rag.services.rag_runtime_service import RagRuntimeService


class IntentSemanticMatch(BaseModel):
    intent_type: IntentType
    score: float
    metadata: dict[str, object] | None = None


class IntentExamplesRetriever:
    def __init__(
        self,
        rag_runtime_service: RagRuntimeService,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.rag_runtime_service = rag_runtime_service
        self.tracer = tracer

    async def retrieve_best_match(
        self,
        *,
        tenant_id: UUID,
        rag_config_id: UUID,
        user_input: str,
        top_k: int = 1,
    ) -> IntentSemanticMatch | None:
        if not user_input:
            return None
        safe_top_k = max(top_k, 1)
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.nodes.intent_examples_retriever.retrieve_best_match",
            input={
                "tenant_id": str(tenant_id),
                "rag_config_id": str(rag_config_id),
                "top_k": safe_top_k,
                "user_input_length": len(user_input),
            },
        ) as retrieve_handle:
            context = await self.rag_runtime_service.get_context(
                tenant_id=tenant_id,
                rag_config_id=rag_config_id,
                user_id=None,
                user_input=user_input,
                filters_override={
                    "source": "intent_examples",
                    "doc_type": "intent_examples",
                },
                top_k_override=safe_top_k,
            )
            best_match = self._pick_best_match(context.context_items)
            if retrieve_handle:
                retrieve_handle.success(
                    output={
                        "context_item_count": len(context.context_items),
                        "rag_reason": str(context.reason),
                        "matched_intent_type": (
                            best_match.intent_type.value if best_match else None
                        ),
                        "matched_score": best_match.score if best_match else None,
                    }
                )
            return best_match

    def _pick_best_match(
        self,
        context_items: list[Any],
    ) -> IntentSemanticMatch | None:
        best: IntentSemanticMatch | None = None
        for item in context_items:
            item_dump = item.model_dump(mode="json")
            metadata = item_dump.get("metadata")
            if not isinstance(metadata, dict):
                continue
            intent_type = self._normalize_intent_type(metadata.get("intent_type"))
            if intent_type is None:
                continue
            score = float(item_dump.get("score") or 0.0)
            if best is None or score > best.score:
                best = IntentSemanticMatch(
                    intent_type=intent_type,
                    score=score,
                    metadata=metadata,
                )
        return best

    @staticmethod
    def _normalize_intent_type(value: object) -> IntentType | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip().lower()
        if normalized == "execution":
            return IntentType.COMMAND
        if normalized == "query":
            return IntentType.QUERY
        if normalized == "command":
            return IntentType.COMMAND
        if normalized == "conversation":
            return IntentType.CONVERSATION
        if normalized == "update_user_preferences":
            return IntentType.UPDATE_USER_PREFERENCES
        return None
