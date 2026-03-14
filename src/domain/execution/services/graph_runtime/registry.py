from __future__ import annotations

from typing import Any, Dict, Type

from domain.agents.repositories.agents_repository import AgentsRepository
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.services.graph_runtime.nodes import (
    ClarificationNode,
    FallbackNode,
    IntentDetectionNode,
    ToolSelectionNode,
    ToolSelectionLLMFallback,
    ParamExtractionNode,
    ResponseComposer,
    ToolErrorHandlerNode,
    ToolExecutionNode,
    UserContextEnrichmentNode,
)
from domain.execution.services.graph_runtime.agent_runtime_resolver import (
    AgentRuntimeResolver,
)
from domain.execution.services.graph_runtime.types import NodeExecutor
from domain.llm.ports.completion_budget_policy import CompletionBudgetPolicyPort
from domain.llm.ports.llm_executor import LLMExecutorPort
from domain.tools.services.tool_catalog_indexer import ToolCatalogIndexer
from domain.tools.services.tool_catalog_retriever import ToolCatalogRetriever
from domain.tools.services.tool_orchestrator import ToolOrchestrator
from domain.execution.repositories.execution_repository import ExecutionRepository


class NodeRegistry:
    def __init__(
        self,
        tracer: RuntimeTracerPort,
        llm_executor: LLMExecutorPort | None = None,
        prompt_resolver: Any | None = None,
        tool_orchestrator: ToolOrchestrator | None = None,
        execution_repository: ExecutionRepository | None = None,
        agent_runtime_resolver: AgentRuntimeResolver | None = None,
        completion_budget_policy: CompletionBudgetPolicyPort | None = None,
        tool_catalog_retriever: ToolCatalogRetriever | None = None,
        tool_catalog_indexer: ToolCatalogIndexer | None = None,
        agents_repository: AgentsRepository | None = None,
    ) -> None:
        self.llm_executor = llm_executor
        self.prompt_resolver = prompt_resolver
        self.tool_orchestrator = tool_orchestrator
        self.execution_repository = execution_repository
        self.tracer = tracer
        self.agent_runtime_resolver = agent_runtime_resolver
        self.completion_budget_policy = completion_budget_policy
        self.tool_catalog_retriever = tool_catalog_retriever
        self.tool_catalog_indexer = tool_catalog_indexer
        self.agents_repository = agents_repository
        self._registry: Dict[str, Type[NodeExecutor]] = {
            ToolSelectionNode.node_type: ToolSelectionNode,
            IntentDetectionNode.node_type: IntentDetectionNode,
            ParamExtractionNode.node_type: ParamExtractionNode,
            ToolExecutionNode.node_type: ToolExecutionNode,
            ClarificationNode.node_type: ClarificationNode,
            ToolErrorHandlerNode.node_type: ToolErrorHandlerNode,
            ResponseComposer.node_type: ResponseComposer,
            UserContextEnrichmentNode.node_type: UserContextEnrichmentNode,
            FallbackNode.node_type: FallbackNode,
        }

    def resolve(
        self, node_type: str
    ) -> (
        type["_ToolSelectionNode"]
        | type["_IntentNode"]
        | type["_ParamExtractionNode"]
        | type["NodeExecutor"]
        | None
    ):
        with self.tracer.observe(
            as_type="agent",
            name="domain.execution.node_registry.resolve",
            input={"node_type": node_type},
        ) as agent_handle:
            node_cls = self._registry.get(node_type)
            if node_type == ToolSelectionNode.node_type:
                tracer = self.tracer
                tool_catalog_retriever = self.tool_catalog_retriever
                tool_catalog_indexer = self.tool_catalog_indexer
                agents_repository = self.agents_repository
                llm_executor = self.llm_executor
                prompt_resolver = self.prompt_resolver
                agent_runtime_resolver = self.agent_runtime_resolver
                completion_budget_policy = self.completion_budget_policy

                class _ToolSelectionNode(ToolSelectionNode):  # type: ignore[misc]
                    def __init__(self) -> None:
                        llm_fallback = None
                        if llm_executor and prompt_resolver:
                            llm_fallback = ToolSelectionLLMFallback(
                                llm_executor=llm_executor,
                                prompt_resolver=prompt_resolver,
                                tracer=tracer,
                                agent_runtime_resolver=agent_runtime_resolver,
                                completion_budget_policy=completion_budget_policy,
                            )
                        super().__init__(
                            tracer=tracer,
                            tool_catalog_retriever=tool_catalog_retriever,
                            agents_repository=agents_repository,
                            llm_fallback=llm_fallback,
                            tool_catalog_indexer=tool_catalog_indexer,
                        )

                return _ToolSelectionNode
            if node_type == IntentDetectionNode.node_type:
                base_cls = node_cls or IntentDetectionNode
                llm_executor = self.llm_executor
                prompt_resolver = self.prompt_resolver
                tracer = self.tracer
                agent_runtime_resolver = self.agent_runtime_resolver
                completion_budget_policy = self.completion_budget_policy

                class _IntentNode(base_cls):  # type: ignore[misc]
                    def __init__(self) -> None:
                        super().__init__(
                            llm_executor=llm_executor,
                            prompt_resolver=prompt_resolver,
                            tracer=tracer,
                            agent_runtime_resolver=agent_runtime_resolver,
                            completion_budget_policy=completion_budget_policy,
                        )

                return _IntentNode
            if node_type == ParamExtractionNode.node_type:
                base_cls = node_cls or ParamExtractionNode
                llm_executor = self.llm_executor
                prompt_resolver = self.prompt_resolver
                tracer = self.tracer
                agent_runtime_resolver = self.agent_runtime_resolver
                completion_budget_policy = self.completion_budget_policy

                class _ParamExtractionNode(base_cls):  # type: ignore[misc]
                    def __init__(self) -> None:
                        super().__init__(
                            llm_executor=llm_executor,
                            prompt_resolver=prompt_resolver,
                            tracer=tracer,
                            agent_runtime_resolver=agent_runtime_resolver,
                            completion_budget_policy=completion_budget_policy,
                        )

                return _ParamExtractionNode
            if node_type in {
                ClarificationNode.node_type,
            }:
                base_cls = node_cls or ClarificationNode
                llm_executor = self.llm_executor
                prompt_resolver = self.prompt_resolver
                tracer = self.tracer
                agent_runtime_resolver = self.agent_runtime_resolver
                completion_budget_policy = self.completion_budget_policy

                class _ClarificationNode(base_cls):  # type: ignore[misc]
                    def __init__(self) -> None:
                        super().__init__(
                            llm_executor=llm_executor,
                            prompt_resolver=prompt_resolver,
                            tracer=tracer,
                            agent_runtime_resolver=agent_runtime_resolver,
                            completion_budget_policy=completion_budget_policy,
                        )

                return _ClarificationNode
            if node_type == ToolExecutionNode.node_type:
                base_cls = node_cls or ToolExecutionNode
                tool_orchestrator = self.tool_orchestrator
                execution_repository = self.execution_repository
                tracer = self.tracer

                class _ToolExecutionNode(base_cls):  # type: ignore[misc]
                    def __init__(self) -> None:
                        super().__init__(
                            tool_orchestrator=tool_orchestrator,
                            execution_repository=execution_repository,
                            tracer=tracer,
                        )

                return _ToolExecutionNode
            if node_type == ResponseComposer.node_type:
                base_cls = node_cls or ResponseComposer
                llm_executor = self.llm_executor
                prompt_resolver = self.prompt_resolver
                tracer = self.tracer
                agent_runtime_resolver = self.agent_runtime_resolver
                completion_budget_policy = self.completion_budget_policy

                class _ResponseComposer(base_cls):  # type: ignore[misc]
                    def __init__(self) -> None:
                        super().__init__(
                            llm_executor=llm_executor,
                            prompt_resolver=prompt_resolver,
                            tracer=tracer,
                            agent_runtime_resolver=agent_runtime_resolver,
                            completion_budget_policy=completion_budget_policy,
                        )

                return _ResponseComposer
            if node_type == UserContextEnrichmentNode.node_type:
                base_cls = node_cls or UserContextEnrichmentNode
                tracer = self.tracer

                class _UserContextEnrichmentNode(base_cls):  # type: ignore[misc]
                    def __init__(self) -> None:
                        super().__init__(tracer=tracer)

                return _UserContextEnrichmentNode
            if agent_handle and node_cls:
                agent_handle.success(output={"node_cls": node_cls.__name__})
            return node_cls
