from __future__ import annotations

from typing import Any
from uuid import UUID

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.rag.schemas import RagContext
from domain.rag.schemas.rag import RagCorpusKind
from domain.rag.services.rag_runtime_service import RagRuntimeService
from domain.tools.repositories.tools_repository import ToolsRepository
from domain.tools.schemas.tool_discovery import ToolDiscoveryCandidate
from domain.tools.schemas.tools import AvailableTool

MAX_TOOL_CATALOG_TOP_K = 5
TOOL_CATALOG_RECALL_TOP_K_MULTIPLIER = 3
TOOL_CATALOG_SIMILARITY_THRESHOLD_CAP = 0.42


class ToolCatalogRetriever:
    def __init__(
        self,
        rag_runtime_service: RagRuntimeService,
        tracer: RuntimeTracerPort,
        tools_repository: ToolsRepository,
    ) -> None:
        self.rag_runtime_service = rag_runtime_service
        self.tracer = tracer
        self.tools_repository = tools_repository

    async def retrieve_candidates(
        self,
        *,
        tenant_id: UUID,
        rag_config_id: UUID,
        user_input: str,
        top_k: int | None = None,
        tool_intent_filter: str | None = None,
    ) -> tuple[list[AvailableTool], list[dict[str, Any]]]:
        k = MAX_TOOL_CATALOG_TOP_K
        if top_k is not None:
            k = min(max(1, top_k), MAX_TOOL_CATALOG_TOP_K)
        #if not user_input:
        #    return [], []
        with self.tracer.observe(
            as_type="retriever",
            name="domain.tools.tool_catalog_retriever.retrieve_candidates",
            input={
                "tenant_id": str(tenant_id),
                "rag_config_id": str(rag_config_id),
                "top_k": k,
            },
        ) as retrieve_handle:
            filters_override: dict[str, object] = {
                "source": "tool_catalog",
                "doc_type": "tool_catalog",
                "category": RagCorpusKind.TOOL_CATALOG.value,
            }
            if tool_intent_filter:
                filters_override["tool_intent"] = tool_intent_filter
            context: RagContext = await self.rag_runtime_service.get_context(
                tenant_id=tenant_id,
                rag_config_id=rag_config_id,
                user_id=None,
                user_input=user_input,
                filters_override=filters_override,
                #top_k_override=max(
                #    k * TOOL_CATALOG_RECALL_TOP_K_MULTIPLIER,
                #    k,
                #),
                top_k_override=top_k,
                similarity_threshold_cap=TOOL_CATALOG_SIMILARITY_THRESHOLD_CAP,
            )
            ranked: list[ToolDiscoveryCandidate] = self._rank_from_rag_global(
                context_items=context.context_items,
            )
            selected: list[ToolDiscoveryCandidate] = ranked[:k]
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
            ordered_ids = [item.tool_config_id for item in selected]
            score_by_id = {item.tool_config_id: item.score for item in selected}
            rows = await self.tools_repository.list_published_tool_configs_with_tools_by_config_ids(
                tenant_id=tenant_id,
                tool_config_ids=ordered_ids,
            )
            by_config_id: dict[UUID, tuple[Any, Any]] = {}
            for cfg, tool in rows:
                by_config_id[cfg.tool_config_id] = (cfg, tool)
            candidates: list[AvailableTool] = []
            evidence: list[dict[str, Any]] = []
            for item in selected:
                row = by_config_id.get(item.tool_config_id)
                if row is None:
                    continue
                cfg, tool = row
                score = score_by_id.get(item.tool_config_id, 0.0)
                at = self._to_available_tool(cfg, tool, score)
                candidates.append(at)
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

    @staticmethod
    def _to_available_tool(
        config: Any,
        tool: Any,
        retrieval_score: float,
    ) -> AvailableTool:
        config_data = config.config or {}
        return AvailableTool.model_validate(
            {
                "name": tool.name,
                "tool_id": config.tool_id,
                "tool_config_id": config.tool_config_id,
                "summary": config_data.get("summary"),
                "description": config_data.get("description"),
                "operation_id": config_data.get("operation_id"),
                "method": config_data.get("method"),
                "path": config_data.get("path"),
                "retrieval_score": retrieval_score,
            }
        )

    def _rank_from_rag_global(
        self,
        *,
        context_items: list[Any],
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
            score: float = float(item_dump.get("score") or 0.0)
            candidate: ToolDiscoveryCandidate = ToolDiscoveryCandidate(
                tool_config_id=tool_config_uuid,
                score=score,
                content=str(item_dump.get("content") or ""),
                metadata=metadata,
            )
            existing = best_by_tool.get(tool_config_uuid)
            if existing is None or candidate.score > existing.score:
                best_by_tool[tool_config_uuid] = candidate
        return sorted(best_by_tool.values(), key=lambda item: item.score, reverse=True)
