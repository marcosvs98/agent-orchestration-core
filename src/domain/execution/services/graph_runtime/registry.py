from __future__ import annotations

from typing import Any, Dict, Type

from domain.agents.repositories.agents_repository import AgentsRepository
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.services.graph_runtime.nodes import (
    ClarificationNode,
    FallbackNode,
    InputModerationNode,
    IntentDetectionNode,
    IntentDetectionLLMFallback,
    IntentExamplesRetriever,
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
from domain.human_sla.services.human_sla_service import HumanSLAService
from domain.llm.ports.moderation_provider import ModerationProviderPort
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
        intent_examples_retriever: IntentExamplesRetriever | None = None,
        llm_moderation_provider: ModerationProviderPort | None = None,
        human_sla_service: HumanSLAService | None = None,
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
        self.intent_examples_retriever = intent_examples_retriever
        self.llm_moderation_provider = llm_moderation_provider
        self.human_sla_service = human_sla_service
        self._registry: Dict[str, Type[NodeExecutor]] = {
            InputModerationNode.node_type: InputModerationNode,
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
                agents_repository = self.agents_repository
                intent_examples_retriever = self.intent_examples_retriever
                if (
                    intent_examples_retriever is None
                    and self.tool_catalog_retriever is not None
                ):
                    intent_examples_retriever = IntentExamplesRetriever(
                        rag_runtime_service=self.tool_catalog_retriever.rag_runtime_service,
                        tracer=tracer,
                    )

                class _IntentNode(base_cls):  # type: ignore[misc]
                    def __init__(self) -> None:
                        llm_fallback = None
                        if llm_executor and prompt_resolver:
                            llm_fallback = IntentDetectionLLMFallback(
                                llm_executor=llm_executor,
                                prompt_resolver=prompt_resolver,
                                tracer=tracer,
                                agent_runtime_resolver=agent_runtime_resolver,
                                completion_budget_policy=completion_budget_policy,
                            )
                        super().__init__(
                            tracer=tracer,
                            agents_repository=agents_repository,
                            intent_examples_retriever=intent_examples_retriever,
                            llm_fallback=llm_fallback,
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
            if node_type == InputModerationNode.node_type:
                base_cls = node_cls or InputModerationNode
                tracer = self.tracer
                llm_moderation_provider = self.llm_moderation_provider

                class _InputModerationNode(base_cls):  # type: ignore[misc]
                    def __init__(self) -> None:
                        if llm_moderation_provider is None:
                            raise ValueError("llm_moderation_provider is required")
                        super().__init__(
                            tracer=tracer,
                            llm_moderation_provider=llm_moderation_provider,
                        )

                return _InputModerationNode
            if node_type == FallbackNode.node_type:
                base_cls = node_cls or FallbackNode
                tracer = self.tracer
                human_sla_service = self.human_sla_service
                llm_executor = self.llm_executor
                prompt_resolver = self.prompt_resolver
                agent_runtime_resolver = self.agent_runtime_resolver
                completion_budget_policy = self.completion_budget_policy

                class _FallbackNode(base_cls):  # type: ignore[misc]
                    def __init__(self) -> None:
                        super().__init__(
                            tracer=tracer,
                            llm_executor=llm_executor,
                            prompt_resolver=prompt_resolver,
                            human_sla_service=human_sla_service,
                            agent_runtime_resolver=agent_runtime_resolver,
                            completion_budget_policy=completion_budget_policy,
                        )

                return _FallbackNode
            if agent_handle and node_cls:
                agent_handle.success(output={"node_cls": node_cls.__name__})
            return node_cls
