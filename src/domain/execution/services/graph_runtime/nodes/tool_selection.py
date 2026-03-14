from __future__ import annotations

from typing import Any
from uuid import UUID

from domain.agents.repositories.agents_repository import AgentsRepository
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.services.graph_runtime.types import (
    ExecutionContext,
    NodeExecutionStatus,
    NodeResult,
)
from domain.prompts.schemas.prompt import NodeType
from domain.tools.schemas.tool_discovery import ToolCatalogDocument
from domain.tools.schemas.tools import AvailableTool
from domain.tools.services.tool_catalog_indexer import ToolCatalogIndexer
from domain.tools.services.tool_catalog_retriever import ToolCatalogRetriever
from domain.execution.services.graph_runtime.nodes.tool_selection_llm_fallback import (
    ToolSelectionLLMFallback,
)


class ToolSelectionNode:
    """Select tools via semantic retrieval without LLM inference."""

    node_type = NodeType.ToolSelectionNode
    side_effect = False
    deterministic = False
    confidence_threshold = 0.9

    def __init__(
        self,
        tracer: RuntimeTracerPort,
        tool_catalog_retriever: ToolCatalogRetriever,
        agents_repository: AgentsRepository,
        llm_fallback: ToolSelectionLLMFallback | None = None,
        tool_catalog_indexer: ToolCatalogIndexer | None = None,
    ) -> None:
        self.tracer = tracer
        self.tool_catalog_retriever = tool_catalog_retriever
        self.agents_repository = agents_repository
        self.llm_fallback = llm_fallback
        self.tool_catalog_indexer = tool_catalog_indexer

    async def execute(
        self, context: ExecutionContext, config: dict[str, Any] | None = None
    ) -> NodeResult:
        """Perform semantic tool discovery and return ranked candidates."""
        with self.tracer.observe(
            as_type="chain",
            name="domain.execution.nodes.tool_selection.execute",
            input={
                "tenant_id": str(context.tenant_id),
                "node_id": str(context.current_node_id),
            },
        ) as execution_handle:
            user_input = (context.input_payload or {}).get("user_input", "")
            available_tools = self._coerce_available_tools(context.available_tools)
            if not available_tools or not user_input:
                result = self._build_result(available_tools, context)
                if execution_handle:
                    execution_handle.success(
                        output={
                            "selection_mode": "semantic_noop",
                            "reason": "missing_tools_or_input",
                            "candidate_count": len(available_tools),
                            "selected_tools": self._extract_selected_tools(result),
                        }
                    )
                return result

            rag_config_id = await self._resolve_rag_config_id(context)
            if rag_config_id is None:
                result = self._build_result(available_tools, context)
                if execution_handle:
                    execution_handle.success(
                        output={
                            "selection_mode": "semantic_noop",
                            "reason": "rag_config_not_found",
                            "candidate_count": len(available_tools),
                            "selected_tools": self._extract_selected_tools(result),
                        }
                    )
                return result

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.nodes.tool_selection.semantic_retrieval",
                input={
                    "tenant_id": str(context.tenant_id),
                    "available_count": len(available_tools),
                    "user_input_length": len(user_input),
                    "top_k": 5,
                },
            ) as retrieval_handle:
                (
                    candidates,
                    evidence,
                ) = await self.tool_catalog_retriever.retrieve_candidates(
                    tenant_id=context.tenant_id,
                    rag_config_id=rag_config_id,
                    user_input=user_input,
                    available_tools=available_tools,
                    top_k=5,
                )
                if retrieval_handle:
                    retrieval_handle.success(
                        output={
                            "candidate_count": len(candidates),
                            "evidence": evidence,
                            "selected_tools": [
                                {
                                    "name": candidate.name,
                                    "tool_config_id": str(candidate.tool_config_id),
                                    "retrieval_score": candidate.retrieval_score,
                                }
                                for candidate in candidates
                            ],
                        }
                    )

            if (
                not evidence
                and len(candidates) == 1
                and candidates[0].retrieval_score is None
            ):
                context.available_tools = candidates
                result = self._build_result(candidates, context)
                if execution_handle:
                    execution_handle.success(
                        output={
                            "selection_mode": "single_candidate_no_llm",
                            "reason": "no_semantic_evidence_but_single_candidate",
                            "best_score": 0.0,
                            "confidence_threshold": self.confidence_threshold,
                            "candidate_count": len(candidates),
                            "selected_tools": self._extract_selected_tools(result),
                        }
                    )
                return result

            best_score = max(
                [tool.retrieval_score or 0.0 for tool in candidates],
                default=0.0,
            )
            if best_score >= self.confidence_threshold or self.llm_fallback is None:
                context.available_tools = candidates
                result = self._build_result(candidates, context)
                if execution_handle:
                    execution_handle.success(
                        output={
                            "selection_mode": "semantic",
                            "best_score": best_score,
                            "confidence_threshold": self.confidence_threshold,
                            "candidate_count": len(candidates),
                            "selected_tools": self._extract_selected_tools(result),
                        }
                    )
                return result

            context.available_tools = candidates if candidates else available_tools
            llm_result = await self.llm_fallback.execute(context, config)
            await self._index_llm_fallback_selection(
                tenant_id=context.tenant_id,
                user_input=user_input,
                available_tools=context.available_tools,
                llm_result=llm_result,
            )
            if execution_handle:
                execution_handle.success(
                    output={
                        "selection_mode": "llm_fallback",
                        "best_score": best_score,
                        "confidence_threshold": self.confidence_threshold,
                        "fallback_reason": "below_confidence_threshold",
                        "semantic_evidence_count": len(evidence),
                        "selected_tools_confidence_source": "llm_fallback",
                        "candidate_count": len(context.available_tools),
                        "selected_tools": self._extract_selected_tools(llm_result),
                    }
                )
            return llm_result

    def _build_result(
        self,
        tools: list[AvailableTool],
        context: ExecutionContext,
    ) -> NodeResult:
        """Build NodeResult in the format expected by downstream nodes."""
        result_items: list[dict[str, Any]] = []
        for tool in tools:
            result_items.append(
                {
                    "selected_tool": {
                        "name": tool.name,
                        "tool_config_id": str(tool.tool_config_id),
                    },
                    "confidence": tool.retrieval_score if tool.retrieval_score else 0.5,
                }
            )

        output: dict[str, Any] = {"result": result_items}
        next_state = {**(context.state or {}), self.node_type: output}

        return NodeResult(
            node=self.node_type,
            status=NodeExecutionStatus.SUCCESS,
            data=output,
            next_state=next_state,
        )

    async def _index_llm_fallback_selection(
        self,
        *,
        tenant_id: UUID,
        user_input: str,
        available_tools: list[AvailableTool],
        llm_result: NodeResult,
    ) -> None:
        if self.tool_catalog_indexer is None:
            return
        selections = self._extract_selected_tools(llm_result)
        if not selections:
            return
        tools_by_config = {str(tool.tool_config_id): tool for tool in available_tools}
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.nodes.tool_selection.index_llm_fallback_selection",
            input={
                "tenant_id": str(tenant_id),
                "selection_count": len(selections),
            },
        ) as retriever_handle:
            indexed = 0
            for selection in selections:
                tool_config_id = str(selection.get("tool_config_id") or "")
                selected_tool = tools_by_config.get(tool_config_id)
                if selected_tool is None:
                    continue
                document = ToolCatalogDocument(
                    tool_id=selected_tool.tool_id,
                    tool_config_id=selected_tool.tool_config_id,
                    tool_name=selected_tool.name,
                    operation_id=selected_tool.operation_id,
                    method=selected_tool.method,
                    path=selected_tool.path,
                    summary=selected_tool.summary,
                    description=selected_tool.description,
                    request_schema={},
                    response_schema={},
                    examples=[user_input],
                    version="learned",
                )
                await self.tool_catalog_indexer.index_document(
                    tenant_id=tenant_id,
                    document=document,
                )
                indexed += 1
            if retriever_handle:
                retriever_handle.success(
                    output={
                        "indexed_count": indexed,
                        "selection_count": len(selections),
                    }
                )

    async def _resolve_rag_config_id(self, context: ExecutionContext) -> UUID | None:
        """Resolve rag_config_id from node_id -> agent_version -> rag_config_id chain."""
        try:
            node_id = UUID(context.current_node_id)
        except (ValueError, TypeError):
            return None

        agent_version_id = await self.agents_repository.get_agent_version_id_by_node_id(
            node_id
        )
        if not agent_version_id:
            return None

        agent_version = await self.agents_repository.get_agent_version(agent_version_id)
        if agent_version is None:
            return None

        return agent_version.rag_config_id

    @staticmethod
    def _coerce_available_tools(tools: list[object]) -> list[AvailableTool]:
        coerced: list[AvailableTool] = []
        for tool in tools:
            if isinstance(tool, AvailableTool):
                coerced.append(tool)
                continue
            if not isinstance(tool, dict):
                continue
            try:
                coerced.append(AvailableTool.model_validate(tool))
            except Exception:
                continue
        return coerced

    @staticmethod
    def _extract_selected_tools(result: NodeResult) -> list[dict[str, Any]]:
        data = result.data if isinstance(result.data, dict) else {}
        items = data.get("result", []) if isinstance(data, dict) else []
        selected: list[dict[str, Any]] = []
        if not isinstance(items, list):
            return selected
        for item in items:
            if not isinstance(item, dict):
                continue
            selected_tool = item.get("selected_tool")
            if not isinstance(selected_tool, dict):
                continue
            selected.append(
                {
                    "name": selected_tool.get("name"),
                    "tool_config_id": selected_tool.get("tool_config_id"),
                    "confidence": item.get("confidence"),
                }
            )
        return selected
