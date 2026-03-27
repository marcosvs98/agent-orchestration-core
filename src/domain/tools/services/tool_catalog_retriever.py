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

    async def retrieve_tools(
        self,
        *,
        tenant_id: UUID,
        rag_config_id: UUID,
        user_input: str,
        top_k: int | None = None,
    ) -> list[AvailableTool]:

        filters_override: dict[str, object] = {
            "source": "tool_catalog",
            "doc_type": "tool_catalog",
            "category": RagCorpusKind.TOOL_CATALOG.value,
        }
        context: RagContext = await self.rag_runtime_service.get_context(
            tenant_id=tenant_id,
            rag_config_id=rag_config_id,
            user_id=None,
            user_input=user_input,
            filters_override=filters_override,
            top_k_override=top_k or MAX_TOOL_CATALOG_TOP_K,
            similarity_threshold_cap=TOOL_CATALOG_SIMILARITY_THRESHOLD_CAP,
        )
        selected: list[ToolDiscoveryCandidate] = (
            self._get_tools_from_recovery_context(
                context_items=context.context_items,
            )
        )
        score_by_id = {item.tool_config_id: item.score for item in selected}
        rows = await self.tools_repository.list_published_tool_configs_with_tools_by_config_ids(
            tenant_id=tenant_id,
            tool_config_ids=list({item.tool_config_id for item in selected}),
        )
        by_config_id: dict[UUID, tuple[Any, Any]] = {}
        for tool_config, tool in rows:
            by_config_id[tool_config.tool_config_id] = (tool_config, tool)
        retrieved_tools: list[AvailableTool] = []
        for item in selected:
            row = by_config_id.get(item.tool_config_id)
            if row is None:
                continue
            tool_config, tool = row
            retrieval_score = score_by_id.get(item.tool_config_id, 0.0)
            retrieved_tools.append(
                AvailableTool.model_validate(
                    {
                        "name": tool.name,
                        "tool_id": tool.tool_id,
                        "tool_config_id": tool_config.tool_config_id,
                        "operation_id": tool_config.config.get("operation_id"),
                        "method": tool_config.config.get("method"),
                        "retrieval_score": retrieval_score,
                    }
                )
            )

        return retrieved_tools

    @staticmethod
    def _get_tools_from_recovery_context(
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
