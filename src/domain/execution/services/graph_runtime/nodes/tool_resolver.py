from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from domain.agents.repositories.agents_repository import AgentsRepository
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.services.graph_runtime.nodes._llm_base import LLMNodeExecutor
from domain.execution.services.graph_runtime.types import (
    ExecutionContext,
    NodeExecutionStatus,
    NodeResult,
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
        config = config or {}
        top_k = config.get("top_k", 5)
        user_input = (context.input_payload or {}).get("user_input", "") or ""

        rag_config_id: UUID = (
            await self.agents_repository.resolve_effective_rag_config_id_for_node(
                UUID(context.current_node_id)
            )
        )

        agent_version_id = await self.agents_repository.get_agent_version_id_by_node_id(
            UUID(context.current_node_id)
        )

        context.available_tools = await self.tool_catalog_retriever.retrieve_tools(
            tenant_id=context.tenant_id,
            rag_config_id=rag_config_id,
            user_input=user_input,
            top_k=top_k,
            agent_version_id=agent_version_id,
        )
        if context.available_tools:
            llm_result = await self._run_llm_after_setup(context, config)

            asyncio.create_task(
                self._index_post_llm_selection(
                    tenant_id=context.tenant_id,
                    user_input=user_input,
                    retrieved_tools=context.available_tools,
                    llm_result=llm_result,
                    config=config,
                ),
                name=self.llm_task,
            )
            return llm_result

        return NodeResult(
            node=self.node_type,
            status=self.result_status,
            data={"result": []},
        )

    async def _index_post_llm_selection(
        self,
        *,
        tenant_id: UUID,
        user_input: str,
        retrieved_tools: list[AvailableTool],
        llm_result: NodeResult,
        config: dict[str, Any] | None = None,
    ) -> None:
        if self.tool_catalog_indexer is None:
            return
        cfg = config or {}
        selections = self._extract_selected_tools(llm_result)
        if not selections:
            return
        tools_by_config = {str(tool.tool_config_id): tool for tool in retrieved_tools}
        indexed = 0
        min_ic = cfg.get("min_indexing_confidence")
        for selection in selections:
            confidence = float(selection.get("confidence") or 0.0)
            if min_ic is not None and confidence < float(min_ic):
                continue
            tool_config_id = str(selection.get("tool_config_id") or "")
            selected_tool = tools_by_config.get(tool_config_id)
            if selected_tool is None:
                continue
            await self.tool_catalog_indexer.index_document(
                tenant_id=tenant_id,
                document=ToolCatalogDocument(
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
                ),
            )
            indexed += 1


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
