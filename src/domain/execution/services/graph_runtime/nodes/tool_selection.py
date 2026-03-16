from __future__ import annotations

from typing import Any
from uuid import UUID

from domain.agents.repositories.agents_repository import AgentsRepository
from domain.execution.ports.runtime_tracer import ObservationHandle, RuntimeTracerPort
from domain.execution.services.graph_runtime.types import (
    ExecutionContext,
    IntentType,
    NodeExecutionStatus,
    NodeResult,
    ToolIntentFilter,
    ToolSelectionMode,
    ToolSelectionReason,
)
from domain.prompts.schemas.prompt import NodeType
from domain.tools.schemas.tool_discovery import ToolCatalogDocument
from domain.tools.schemas.tools import AvailableTool
from domain.tools.services.tool_catalog_indexer import ToolCatalogIndexer
from domain.tools.services.tool_catalog_retriever import ToolCatalogRetriever
from domain.execution.services.graph_runtime.nodes.tool_selection_llm_fallback import (
    ToolSelectionLLMFallback,
)

DEFAULT_TOP_K = 5
DEFAULT_CONFIDENCE_THRESHOLD = 0.9
MIN_INDEXING_CONFIDENCE = 0.7


class ToolSelectionNode:
    """Select tools via structural filtering + semantic retrieval."""

    node_type = NodeType.ToolSelectionNode
    side_effect = False
    deterministic = False

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
        cfg = config or {}
        confidence_threshold = self._config_float(
            cfg, "confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD
        )
        top_k = self._config_int(cfg, "top_k", DEFAULT_TOP_K)

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
            detected_intent = self._resolve_detected_intent(context)
            filtered_tools, tool_intent_filter = self._filter_tools_by_intent(
                tools=available_tools,
                detected_intent=detected_intent,
            )

            if not user_input:
                result = self._build_result(filtered_tools, context)
                self._report_success(
                    execution_handle,
                    result,
                    ToolSelectionMode.SEMANTIC_NOOP,
                    ToolSelectionReason.MISSING_USER_INPUT,
                    intent_type=detected_intent,
                    candidate_count=len(filtered_tools),
                )
                return result

            if len(filtered_tools) == 1:
                context.available_tools = filtered_tools
                result = self._build_result(filtered_tools, context)
                self._report_success(
                    execution_handle,
                    result,
                    ToolSelectionMode.SINGLE_TOOL_AUTO_SELECT,
                    ToolSelectionReason.SINGLE_TOOL_AFTER_INTENT_FILTER,
                    intent_type=detected_intent,
                    candidate_count=1,
                )
                return result

            if not filtered_tools:
                llm_result = await self._execute_llm_fallback(
                    context=context,
                    config=config,
                    candidate_tools=[],
                    reason=ToolSelectionReason.NO_TOOLS_AFTER_INTENT_FILTER,
                    execution_handle=execution_handle,
                    best_score=0.0,
                    semantic_evidence_count=0,
                    detected_intent=detected_intent,
                    confidence_threshold=confidence_threshold,
                )
                if llm_result is not None:
                    return llm_result
                result = self._build_result([], context)
                self._report_success(
                    execution_handle,
                    result,
                    ToolSelectionMode.SEMANTIC_NOOP,
                    ToolSelectionReason.NO_TOOLS_AFTER_INTENT_FILTER,
                    intent_type=detected_intent,
                    candidate_count=0,
                )
                return result

            rag_config_id = await self._resolve_rag_config_id(context)
            if rag_config_id is None:
                result = self._build_result(filtered_tools, context)
                self._report_success(
                    execution_handle,
                    result,
                    ToolSelectionMode.SEMANTIC_NOOP,
                    ToolSelectionReason.RAG_CONFIG_NOT_FOUND,
                    intent_type=detected_intent,
                    candidate_count=len(filtered_tools),
                )
                return result

            tool_intent_filter_str = (
                tool_intent_filter.value if tool_intent_filter else None
            )
            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.nodes.tool_selection.semantic_retrieval",
                input={
                    "tenant_id": str(context.tenant_id),
                    "available_count": len(filtered_tools),
                    "user_input_length": len(user_input),
                    "top_k": top_k,
                    "intent_type": detected_intent.value if detected_intent else None,
                    "tool_intent_filter": tool_intent_filter_str,
                },
            ) as retrieval_handle:
                (
                    candidates,
                    evidence,
                ) = await self.tool_catalog_retriever.retrieve_candidates(
                    tenant_id=context.tenant_id,
                    rag_config_id=rag_config_id,
                    user_input=user_input,
                    available_tools=filtered_tools,
                    top_k=top_k,
                    tool_intent_filter=tool_intent_filter_str,
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

            if not candidates:
                llm_result = await self._execute_llm_fallback(
                    context=context,
                    config=config,
                    candidate_tools=filtered_tools,
                    reason=ToolSelectionReason.RAG_RETURNED_NO_CANDIDATES,
                    execution_handle=execution_handle,
                    best_score=0.0,
                    semantic_evidence_count=len(evidence),
                    detected_intent=detected_intent,
                    confidence_threshold=confidence_threshold,
                )
                if llm_result is not None:
                    return llm_result
                result = self._build_result([], context)
                self._report_success(
                    execution_handle,
                    result,
                    ToolSelectionMode.SEMANTIC_NOOP,
                    ToolSelectionReason.RAG_RETURNED_NO_CANDIDATES,
                    intent_type=detected_intent,
                    candidate_count=0,
                )
                return result

            best_score = max(
                [tool.retrieval_score or 0.0 for tool in candidates],
                default=0.0,
            )
            if best_score >= confidence_threshold:
                selected = [candidates[0]]
                context.available_tools = selected
                result = self._build_result(selected, context)
                self._report_success(
                    execution_handle,
                    result,
                    ToolSelectionMode.HEURISTIC_AUTO_SELECT,
                    ToolSelectionReason.ABOVE_CONFIDENCE_THRESHOLD,
                    intent_type=detected_intent,
                    candidate_count=len(selected),
                    best_score=best_score,
                    confidence_threshold=confidence_threshold,
                )
                return result

            llm_result = await self._execute_llm_fallback(
                context=context,
                config=config,
                candidate_tools=filtered_tools,
                reason=ToolSelectionReason.BELOW_CONFIDENCE_THRESHOLD,
                execution_handle=execution_handle,
                best_score=best_score,
                semantic_evidence_count=len(evidence),
                detected_intent=detected_intent,
                confidence_threshold=confidence_threshold,
            )
            if llm_result is not None:
                return llm_result

            context.available_tools = candidates
            result = self._build_result(candidates, context)
            self._report_success(
                execution_handle,
                result,
                ToolSelectionMode.SEMANTIC,
                ToolSelectionReason.BELOW_CONFIDENCE_THRESHOLD,
                intent_type=detected_intent,
                candidate_count=len(candidates),
                best_score=best_score,
                confidence_threshold=confidence_threshold,
            )
            return result

    async def _execute_llm_fallback(
        self,
        *,
        context: ExecutionContext,
        config: dict[str, Any] | None,
        candidate_tools: list[AvailableTool],
        reason: ToolSelectionReason,
        execution_handle: ObservationHandle | None,
        best_score: float,
        semantic_evidence_count: int,
        detected_intent: IntentType | None,
        confidence_threshold: float,
    ) -> NodeResult | None:
        if self.llm_fallback is None:
            return None
        context.available_tools = candidate_tools
        llm_result = await self.llm_fallback.execute(context, config)
        await self._index_llm_fallback_selection(
            tenant_id=context.tenant_id,
            user_input=(context.input_payload or {}).get("user_input", ""),
            available_tools=context.available_tools,
            llm_result=llm_result,
        )
        if execution_handle and llm_result is not None:
            self._report_success(
                execution_handle,
                llm_result,
                ToolSelectionMode.LLM_FALLBACK,
                reason,
                intent_type=detected_intent,
                candidate_count=len(context.available_tools),
                best_score=best_score,
                confidence_threshold=confidence_threshold,
                fallback_reason=reason,
                semantic_evidence_count=semantic_evidence_count,
                selected_tools_confidence_source="llm_fallback",
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

    def _report_success(
        self,
        handle: ObservationHandle | None,
        result: NodeResult,
        mode: ToolSelectionMode,
        reason: ToolSelectionReason,
        *,
        intent_type: IntentType | None,
        candidate_count: int,
        best_score: float | None = None,
        confidence_threshold: float | None = None,
        fallback_reason: ToolSelectionReason | None = None,
        semantic_evidence_count: int | None = None,
        selected_tools_confidence_source: str | None = None,
    ) -> None:
        output: dict[str, Any] = {
            "selection_mode": mode.value,
            "reason": reason.value,
            "intent_type": intent_type.value if intent_type else None,
            "candidate_count": candidate_count,
            "selected_tools": self._extract_selected_tools(result),
        }
        if best_score is not None:
            output["best_score"] = best_score
        if confidence_threshold is not None:
            output["confidence_threshold"] = confidence_threshold
        if fallback_reason is not None:
            output["fallback_reason"] = fallback_reason.value
        if semantic_evidence_count is not None:
            output["semantic_evidence_count"] = semantic_evidence_count
        if selected_tools_confidence_source is not None:
            output["selected_tools_confidence_source"] = (
                selected_tools_confidence_source
            )
        if handle:
            handle.success(output=output)

    @staticmethod
    def _config_float(config: dict[str, Any], key: str, default: float) -> float:
        raw = config.get(key)
        if raw is None:
            return default
        if isinstance(raw, (int, float)):
            return float(raw)
        return default

    @staticmethod
    def _config_int(config: dict[str, Any], key: str, default: int) -> int:
        raw = config.get(key)
        if raw is None:
            return default
        if isinstance(raw, int):
            return raw
        if isinstance(raw, float):
            return int(raw)
        return default

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
                confidence = float(selection.get("confidence") or 0.0)
                if confidence < MIN_INDEXING_CONFIDENCE:
                    continue
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

    def _resolve_detected_intent(self, context: ExecutionContext) -> IntentType | None:
        intent_slice = context.get_node_output(NodeType.IntentDetectionNode)
        result = intent_slice.get("result") if isinstance(intent_slice, dict) else None
        if not isinstance(result, list) or not result:
            return None
        first = result[0]
        if not isinstance(first, dict):
            return None
        intent_type = first.get("intent_type")
        if not isinstance(intent_type, str):
            return None
        normalized = intent_type.strip().lower()
        if normalized == "execution":
            return IntentType.COMMAND
        if normalized == "query":
            return IntentType.QUERY
        if normalized == "command":
            return IntentType.COMMAND
        if normalized == "conversation":
            return IntentType.CONVERSATION
        return None

    def _filter_tools_by_intent(
        self,
        *,
        tools: list[AvailableTool],
        detected_intent: IntentType | None,
    ) -> tuple[list[AvailableTool], ToolIntentFilter | None]:
        if detected_intent == IntentType.QUERY:
            filtered = [tool for tool in tools if (tool.method or "").upper() == "GET"]
            return filtered, ToolIntentFilter.QUERY
        if detected_intent == IntentType.COMMAND:
            filtered = [
                tool
                for tool in tools
                if (tool.method or "").upper() in {"POST", "PUT", "PATCH", "DELETE"}
            ]
            return filtered, ToolIntentFilter.COMMAND
        return tools, None

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
