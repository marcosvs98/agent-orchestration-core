from __future__ import annotations

from typing import Any, Dict, Type

from domain.context.ports.service import MemoryWriteServicePort
from domain.agents.repositories.agents_repository import AgentsRepository
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.services.graph_runtime.nodes import (
    ContentModeration,
    ContextSummarizer,
    HumanFallback,
    IntentClassifier,
    MemoryCommitNode,
    QueryClarifier,
    ResponseBuilder,
    ToolErrorHandlerNode,
    ToolExecutor,
    ToolInputFiller,
    ToolResolver,
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
        memory_write_service: MemoryWriteServicePort | None = None,
        agent_runtime_resolver: AgentRuntimeResolver | None = None,
        completion_budget_policy: CompletionBudgetPolicyPort | None = None,
        tool_catalog_retriever: ToolCatalogRetriever | None = None,
        tool_catalog_indexer: ToolCatalogIndexer | None = None,
        agents_repository: AgentsRepository | None = None,
        llm_moderation_provider: ModerationProviderPort | None = None,
        human_sla_service: HumanSLAService | None = None,
    ) -> None:
        self.llm_executor = llm_executor
        self.prompt_resolver = prompt_resolver
        self.tool_orchestrator = tool_orchestrator
        self.execution_repository = execution_repository
        self.memory_write_service = memory_write_service
        self.tracer = tracer
        self.agent_runtime_resolver = agent_runtime_resolver
        self.completion_budget_policy = completion_budget_policy
        self.tool_catalog_retriever = tool_catalog_retriever
        self.tool_catalog_indexer = tool_catalog_indexer
        self.agents_repository = agents_repository
        self.llm_moderation_provider = llm_moderation_provider
        self.human_sla_service = human_sla_service
        self._registry: Dict[str, Type[NodeExecutor]] = {
            ContentModeration.node_type: ContentModeration,
            ToolResolver.node_type: ToolResolver,
            IntentClassifier.node_type: IntentClassifier,
            ToolInputFiller.node_type: ToolInputFiller,
            ToolExecutor.node_type: ToolExecutor,
            QueryClarifier.node_type: QueryClarifier,
            ToolErrorHandlerNode.node_type: ToolErrorHandlerNode,
            ResponseBuilder.node_type: ResponseBuilder,
            HumanFallback.node_type: HumanFallback,
            MemoryCommitNode.node_type: MemoryCommitNode,
            ContextSummarizer.node_type: ContextSummarizer,
        }

    def resolve(
        self, node_type: str
    ) -> (
        type["_ToolResolver"]
        | type["_IntentClassifier"]
        | type["_ToolInputFiller"]
        | type["NodeExecutor"]
        | None
    ):
        with self.tracer.observe(
            as_type="agent",
            name="domain.execution.node_registry.resolve",
            input={"node_type": node_type},
        ) as agent_handle:
            node_cls = self._registry.get(node_type)
            if node_type == ToolResolver.node_type:
                tracer = self.tracer
                tool_catalog_retriever = self.tool_catalog_retriever
                tool_catalog_indexer = self.tool_catalog_indexer
                agents_repository = self.agents_repository
                llm_executor = self.llm_executor
                prompt_resolver = self.prompt_resolver
                agent_runtime_resolver = self.agent_runtime_resolver
                completion_budget_policy = self.completion_budget_policy

                class _ToolResolver(ToolResolver):  # type: ignore[misc]
                    def __init__(self) -> None:
                        if not llm_executor or not prompt_resolver:
                            raise ValueError(
                                "llm_executor and prompt_resolver required for ToolResolver"
                            )
                        if tool_catalog_retriever is None or agents_repository is None:
                            raise ValueError(
                                "tool_catalog_retriever and agents_repository required for ToolResolver"
                            )
                        super().__init__(
                            tracer=tracer,
                            llm_executor=llm_executor,
                            prompt_resolver=prompt_resolver,
                            agent_runtime_resolver=agent_runtime_resolver,
                            completion_budget_policy=completion_budget_policy,
                            tool_catalog_retriever=tool_catalog_retriever,
                            agents_repository=agents_repository,
                            tool_catalog_indexer=tool_catalog_indexer,
                        )

                return _ToolResolver
            if node_type == IntentClassifier.node_type:
                base_cls = node_cls or IntentClassifier
                llm_executor = self.llm_executor
                prompt_resolver = self.prompt_resolver
                tracer = self.tracer
                agent_runtime_resolver = self.agent_runtime_resolver
                completion_budget_policy = self.completion_budget_policy

                class _IntentClassifier(base_cls):  # type: ignore[misc]
                    def __init__(self) -> None:
                        super().__init__(
                            llm_executor=llm_executor,
                            prompt_resolver=prompt_resolver,
                            tracer=tracer,
                            agent_runtime_resolver=agent_runtime_resolver,
                            completion_budget_policy=completion_budget_policy,
                        )

                return _IntentClassifier
            if node_type == ToolInputFiller.node_type:
                base_cls = node_cls or ToolInputFiller
                tracer = self.tracer
                llm_executor = self.llm_executor
                prompt_resolver = self.prompt_resolver
                agent_runtime_resolver = self.agent_runtime_resolver
                completion_budget_policy = self.completion_budget_policy

                class _ToolInputFiller(base_cls):  # type: ignore[misc]
                    def __init__(self) -> None:
                        super().__init__(
                            llm_executor=llm_executor,
                            prompt_resolver=prompt_resolver,
                            tracer=tracer,
                            agent_runtime_resolver=agent_runtime_resolver,
                            completion_budget_policy=completion_budget_policy,
                        )

                return _ToolInputFiller
            if node_type in {
                QueryClarifier.node_type,
            }:
                base_cls = node_cls or QueryClarifier
                llm_executor = self.llm_executor
                prompt_resolver = self.prompt_resolver
                tracer = self.tracer
                agent_runtime_resolver = self.agent_runtime_resolver
                completion_budget_policy = self.completion_budget_policy

                class _QueryClarifier(base_cls):  # type: ignore[misc]
                    def __init__(self) -> None:
                        super().__init__(
                            llm_executor=llm_executor,
                            prompt_resolver=prompt_resolver,
                            tracer=tracer,
                            agent_runtime_resolver=agent_runtime_resolver,
                            completion_budget_policy=completion_budget_policy,
                        )

                return _QueryClarifier
            if node_type == ToolExecutor.node_type:
                base_cls = node_cls or ToolExecutor
                tool_orchestrator = self.tool_orchestrator
                execution_repository = self.execution_repository
                tracer = self.tracer

                class _ToolExecutor(base_cls):  # type: ignore[misc]
                    def __init__(self) -> None:
                        super().__init__(
                            tool_orchestrator=tool_orchestrator,
                            execution_repository=execution_repository,
                            tracer=tracer,
                        )

                return _ToolExecutor
            if node_type == MemoryCommitNode.node_type:
                base_cls = node_cls or MemoryCommitNode
                memory_write_service = self.memory_write_service
                execution_repository = self.execution_repository
                tracer = self.tracer

                class _MemoryCommitNode(base_cls):  # type: ignore[misc]
                    def __init__(self) -> None:
                        super().__init__(
                            memory_write_service=memory_write_service,
                            execution_repository=execution_repository,
                            tracer=tracer,
                        )

                return _MemoryCommitNode
            if node_type == ResponseBuilder.node_type:
                base_cls = node_cls or ResponseBuilder
                llm_executor = self.llm_executor
                prompt_resolver = self.prompt_resolver
                tracer = self.tracer
                agent_runtime_resolver = self.agent_runtime_resolver
                completion_budget_policy = self.completion_budget_policy

                class _ResponseBuilder(base_cls):  # type: ignore[misc]
                    def __init__(self) -> None:
                        super().__init__(
                            llm_executor=llm_executor,
                            prompt_resolver=prompt_resolver,
                            tracer=tracer,
                            agent_runtime_resolver=agent_runtime_resolver,
                            completion_budget_policy=completion_budget_policy,
                        )

                return _ResponseBuilder
            if node_type == ContextSummarizer.node_type:
                base_cls = node_cls or ContextSummarizer
                llm_executor = self.llm_executor
                prompt_resolver = self.prompt_resolver
                tracer = self.tracer
                agent_runtime_resolver = self.agent_runtime_resolver
                completion_budget_policy = self.completion_budget_policy

                class _ContextSummarizer(base_cls):  # type: ignore[misc]
                    def __init__(self) -> None:
                        super().__init__(
                            llm_executor=llm_executor,
                            prompt_resolver=prompt_resolver,
                            tracer=tracer,
                            agent_runtime_resolver=agent_runtime_resolver,
                            completion_budget_policy=completion_budget_policy,
                        )

                return _ContextSummarizer
            if node_type == ContentModeration.node_type:
                base_cls = node_cls or ContentModeration
                tracer = self.tracer
                llm_moderation_provider = self.llm_moderation_provider

                class _ContentModeration(base_cls):  # type: ignore[misc]
                    def __init__(self) -> None:
                        if llm_moderation_provider is None:
                            raise ValueError("llm_moderation_provider is required")
                        super().__init__(
                            tracer=tracer,
                            llm_moderation_provider=llm_moderation_provider,
                        )

                return _ContentModeration
            if node_type == HumanFallback.node_type:
                base_cls = node_cls or HumanFallback
                tracer = self.tracer
                human_sla_service = self.human_sla_service
                llm_executor = self.llm_executor
                prompt_resolver = self.prompt_resolver
                agent_runtime_resolver = self.agent_runtime_resolver
                completion_budget_policy = self.completion_budget_policy

                class _HumanFallback(base_cls):  # type: ignore[misc]
                    def __init__(self) -> None:
                        super().__init__(
                            tracer=tracer,
                            llm_executor=llm_executor,
                            prompt_resolver=prompt_resolver,
                            human_sla_service=human_sla_service,
                            agent_runtime_resolver=agent_runtime_resolver,
                            completion_budget_policy=completion_budget_policy,
                        )

                return _HumanFallback
            if agent_handle and node_cls:
                agent_handle.success(output={"node_cls": node_cls.__name__})
            return node_cls
