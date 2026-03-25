from __future__ import annotations

from typing import Any
from uuid import UUID

from domain.agents.repositories.agents_repository import AgentsRepository
from domain.execution.ports.runtime_tracer import ObservationHandle, RuntimeTracerPort
from domain.execution.services.graph_runtime.nodes._llm_base import LLMNodeExecutor
from domain.execution.services.graph_runtime.types import (
    ExecutionContext,
    NodeExecutionStatus,
    NodeResult,
    ToolSelectionMode,
    ToolSelectionReason,
)
from domain.llm.ports.completion_budget_policy import CompletionBudgetPolicyPort
from domain.llm.ports.llm_executor import LLMExecutorPort
from domain.llm.schemas.llm import LLMTaskType
from domain.prompts.schemas.prompt import NodeType, PromptIntent
from domain.tools.schemas.tool_discovery import ToolCatalogDocument
from domain.tools.schemas.tools import AvailableTool
from domain.tools.services.tool_catalog_indexer import ToolCatalogIndexer
from domain.tools.services.tool_catalog_retriever import ToolCatalogRetriever
from domain.execution.services.graph_runtime.agent_runtime_resolver import (
    AgentRuntimeResolver,
)

DEFAULT_TOP_K = 5
MIN_INDEXING_CONFIDENCE = 0.7


class ToolResolver(LLMNodeExecutor):
    node_type = NodeType.ToolResolver
    llm_task = LLMTaskType.TOOL_SELECTION
    prompt_intent = PromptIntent.INTENT_TOOL_SELECTION
    resolve_prompt_passes_node_type = True
    include_available_tools = True
    result_status = NodeExecutionStatus.SUCCESS
    write_next_state = True
    state_key_use_value = False

    def __init__(
        self,
        tracer: RuntimeTracerPort,
        llm_executor: LLMExecutorPort,
        prompt_resolver: Any,
        agent_runtime_resolver: AgentRuntimeResolver | None,
        completion_budget_policy: CompletionBudgetPolicyPort | None,
        tool_catalog_retriever: ToolCatalogRetriever,
        agents_repository: AgentsRepository,
        tool_catalog_indexer: ToolCatalogIndexer | None = None,
    ) -> None:
        super().__init__(
            tracer=tracer,
            llm_executor=llm_executor,
            prompt_resolver=prompt_resolver,
            agent_runtime_resolver=agent_runtime_resolver,
            completion_budget_policy=completion_budget_policy,
        )
        self.tool_catalog_retriever = tool_catalog_retriever
        self.agents_repository = agents_repository
        self.tool_catalog_indexer = tool_catalog_indexer

    async def execute(
        self, context: ExecutionContext, config: dict[str, Any] | None = None
    ) -> NodeResult:
        print('CHEGIOU AQUI ???')
        config = config or {}
        top_k = config.get("top_k", DEFAULT_TOP_K)
        user_input = (context.input_payload or {}).get("user_input", "") or ""

        with self.tracer.observe(
            as_type="chain",
            name="domain.execution.nodes.tool_selection.execute",
            input={
                "tenant_id": str(context.tenant_id),
                "node_id": str(context.current_node_id),
            },
        ) as execution_handle:
            # if not user_input:
            #    result = self._build_result([], context)
            #    self._report_success(
            #        execution_handle,
            #        result,
            #        ToolSelectionMode.SEMANTIC_NOOP,
            #        ToolSelectionReason.MISSING_USER_INPUT,
            #        candidate_count=0,
            #        semantic_evidence_count=0,
            #    )
            #    return result

            rag_config_id = await self._resolve_rag_config_id(context)
            # if rag_config_id is None:
            #    result = self._build_result([], context)
            #    self._report_success(
            #        execution_handle,
            #        result,
            #        ToolSelectionMode.SEMANTIC_NOOP,
            #        ToolSelectionReason.RAG_CONFIG_NOT_FOUND,
            #        candidate_count=0,
            #        semantic_evidence_count=0,
            #    )
            #    return result

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.nodes.tool_selection.semantic_retrieval",
                input={
                    "tenant_id": str(context.tenant_id),
                    "user_input_length": len(user_input),
                    "top_k": top_k,
                },
            ) as retrieval_handle:
                (
                    candidates,
                    evidence,
                ) = await self.tool_catalog_retriever.retrieve_candidates(
                    tenant_id=context.tenant_id,
                    rag_config_id=rag_config_id,
                    user_input=user_input,
                    top_k=top_k,
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
                result = self._build_result([], context)
                self._report_success(
                    execution_handle,
                    result,
                    ToolSelectionMode.SEMANTIC_NOOP,
                    ToolSelectionReason.RAG_RETURNED_NO_CANDIDATES,
                    candidate_count=0,
                    semantic_evidence_count=len(evidence),
                )
                return result

            context.available_tools = candidates
            llm_result = await self._run_llm_after_setup(context, config)
            await self._index_post_llm_selection(
                tenant_id=context.tenant_id,
                user_input=user_input,
                candidate_tools=candidates,
                llm_result=llm_result,
            )
            if execution_handle:
                self._report_success(
                    execution_handle,
                    llm_result,
                    ToolSelectionMode.RAG_WITH_LLM,
                    ToolSelectionReason.LLM_SELECTION,
                    candidate_count=len(candidates),
                    semantic_evidence_count=len(evidence),
                )
            return llm_result

    def _build_result(
        self,
        tools: list[AvailableTool],
        context: ExecutionContext,
    ) -> NodeResult:
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
        candidate_count: int,
        semantic_evidence_count: int,
        best_score: float | None = None,
        confidence_threshold: float | None = None,
        fallback_reason: ToolSelectionReason | None = None,
        selected_tools_confidence_source: str | None = None,
        intent_type: Any = None,
    ) -> None:
        output: dict[str, Any] = {
            "selection_mode": mode.value,
            "reason": reason.value,
            "intent_type": intent_type.value if intent_type else None,
            "candidate_count": candidate_count,
            "semantic_evidence_count": semantic_evidence_count,
            "selected_tools": self._extract_selected_tools(result),
        }
        if best_score is not None:
            output["best_score"] = best_score
        if confidence_threshold is not None:
            output["confidence_threshold"] = confidence_threshold
        if fallback_reason is not None:
            output["fallback_reason"] = fallback_reason.value
        if selected_tools_confidence_source is not None:
            output["selected_tools_confidence_source"] = (
                selected_tools_confidence_source
            )
        if handle:
            handle.success(output=output)

    async def _index_post_llm_selection(
        self,
        *,
        tenant_id: UUID,
        user_input: str,
        candidate_tools: list[AvailableTool],
        llm_result: NodeResult,
    ) -> None:
        if self.tool_catalog_indexer is None:
            return
        selections = self._extract_selected_tools(llm_result)
        if not selections:
            return
        tools_by_config = {str(tool.tool_config_id): tool for tool in candidate_tools}
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.nodes.tool_selection.index_post_llm_selection",
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
        try:
            node_id = UUID(context.current_node_id)
        except (ValueError, TypeError):
            return None
        return await self.agents_repository.resolve_effective_rag_config_id_for_node(
            node_id
        )

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
