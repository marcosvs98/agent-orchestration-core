from __future__ import annotations

from typing import Any
from uuid import UUID

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.rag.services.rag_runtime_service import RagRuntimeService
from domain.tools.schemas.tool_discovery import ToolDiscoveryCandidate
from domain.tools.schemas.tools import AvailableTool


class ToolCatalogRetriever:
    def __init__(
        self,
        rag_runtime_service: RagRuntimeService,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.rag_runtime_service = rag_runtime_service
        self.tracer = tracer

    async def retrieve_candidates(
        self,
        *,
        tenant_id: UUID,
        rag_config_id: UUID,
        user_input: str,
        available_tools: list[AvailableTool],
        top_k: int,
        tool_intent_filter: str | None = None,
    ) -> tuple[list[AvailableTool], list[dict[str, Any]]]:
        if not available_tools or not user_input:
            return available_tools[:top_k], []
        lookup: dict[UUID, AvailableTool] = {}
        for tool in available_tools:
            lookup[tool.tool_config_id] = tool
        with self.tracer.observe(
            as_type="retriever",
            name="domain.tools.tool_catalog_retriever.retrieve_candidates",
            input={
                "tenant_id": str(tenant_id),
                "rag_config_id": str(rag_config_id),
                "available_count": len(available_tools),
                "top_k": top_k,
            },
        ) as retrieve_handle:
            filters_override: dict[str, object] = {
                "source": "tool_catalog",
                "doc_type": "tool_catalog",
                "category": "TOOL_CATALOG",
            }
            if tool_intent_filter:
                filters_override["tool_intent"] = tool_intent_filter
            context = await self.rag_runtime_service.get_context(
                tenant_id=tenant_id,
                rag_config_id=rag_config_id,
                user_id=None,
                user_input=user_input,
                filters_override=filters_override,
                top_k_override=max(top_k * 3, top_k),
            )
            ranked = self._rank_candidates(
                context_items=context.context_items, lookup=lookup
            )
            selected = ranked[:top_k]
            if not selected:
                evidence_empty: list[dict[str, Any]] = []
                if retrieve_handle:
                    retrieve_handle.success(
                        output={
                            "context_item_count": len(context.context_items),
                            "ranked_count": len(ranked),
                            "candidate_count": 0,
                            "fallback_used": False,
                            "rag_reason": str(context.reason),
                            "selected_tools": [],
                            "evidence": evidence_empty,
                        }
                    )
                return [], evidence_empty
            candidates = []
            evidence = []
            for item in selected:
                base = lookup[item.tool_config_id]
                candidates.append(
                    base.model_copy(
                        update={
                            "retrieval_score": item.score,
                        }
                    )
                )
                evidence.append(
                    {
                        "tool_config_id": str(item.tool_config_id),
                        "score": item.score,
                        "operation_id": item.metadata.get("operation_id"),
                        "method": item.metadata.get("method"),
                        "path": item.metadata.get("path"),
                    }
                )
            if retrieve_handle:
                retrieve_handle.success(
                    output={
                        "context_item_count": len(context.context_items),
                        "ranked_count": len(ranked),
                        "candidate_count": len(candidates),
                        "fallback_used": False,
                        "rag_reason": str(context.reason),
                        "selected_tools": [
                            {
                                "name": candidate.name,
                                "tool_config_id": str(candidate.tool_config_id),
                                "retrieval_score": candidate.retrieval_score,
                            }
                            for candidate in candidates
                        ],
                        "evidence": evidence,
                    }
                )
            return candidates, evidence

    def _rank_candidates(
        self,
        *,
        context_items: list[Any],
        lookup: dict[UUID, AvailableTool],
    ) -> list[ToolDiscoveryCandidate]:
        best_by_tool: dict[UUID, ToolDiscoveryCandidate] = {}
        for item in context_items:
            item_dump = item.model_dump(mode="json")
            metadata = item_dump.get("metadata") or {}
            tool_config_id = metadata.get("tool_config_id")
            if not tool_config_id:
                continue
            try:
                tool_config_uuid = UUID(str(tool_config_id))
            except ValueError:
                continue
            if tool_config_uuid not in lookup:
                continue
            score = float(item_dump.get("score") or 0.0)
            candidate = ToolDiscoveryCandidate(
                tool_config_id=tool_config_uuid,
                score=score,
                content=str(item_dump.get("content") or ""),
                metadata=metadata,
            )
            existing = best_by_tool.get(tool_config_uuid)
            if existing is None or candidate.score > existing.score:
                best_by_tool[tool_config_uuid] = candidate
        return sorted(best_by_tool.values(), key=lambda item: item.score, reverse=True)
