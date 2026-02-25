from __future__ import annotations

from typing import Any, Dict, Type

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.services.graph_runtime.nodes import (
    ClarificationNode,
    FallbackNode,
    IntentDetectionNode,
    ToolSelectionNode,
    ParamExtractionNode,
    ResponseComposer,
    ToolErrorHandlerNode,
    ToolExecutionNode,
    UserContextEnrichmentNode,
)
from domain.execution.services.graph_runtime.types import NodeExecutor
from domain.llm.ports.llm_executor import LLMExecutorPort
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
    ) -> None:
        self.llm_executor = llm_executor
        self.prompt_resolver = prompt_resolver
        self.tool_orchestrator = tool_orchestrator
        self.execution_repository = execution_repository
        self.tracer = tracer
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
        type["_IntentNode"] | type["_ParamExtractionNode"] | type["NodeExecutor"] | None
    ):
        with self.tracer.observe(
            as_type="agent",
            name="domain.execution.node_registry.resolve",
            input={"node_type": node_type},
        ) as agent_handle:
            node_cls = self._registry.get(node_type)
            if node_type in {
                ToolSelectionNode.node_type,
                IntentDetectionNode.node_type,
            }:
                base_cls = node_cls or ToolSelectionNode
                llm_executor = self.llm_executor
                prompt_resolver = self.prompt_resolver
                tracer = self.tracer

                class _IntentNode(base_cls):  # type: ignore[misc]
                    def __init__(self) -> None:
                        super().__init__(
                            llm_executor=llm_executor,
                            prompt_resolver=prompt_resolver,
                            tracer=tracer,
                        )

                return _IntentNode
            if node_type == ParamExtractionNode.node_type:
                base_cls = node_cls or ParamExtractionNode
                llm_executor = self.llm_executor
                prompt_resolver = self.prompt_resolver
                tracer = self.tracer

                class _ParamExtractionNode(base_cls):  # type: ignore[misc]
                    def __init__(self) -> None:
                        super().__init__(
                            llm_executor=llm_executor,
                            prompt_resolver=prompt_resolver,
                            tracer=tracer,
                        )

                return _ParamExtractionNode
            if node_type in {
                ClarificationNode.node_type,
            }:
                base_cls = node_cls or ClarificationNode
                llm_executor = self.llm_executor
                prompt_resolver = self.prompt_resolver
                tracer = self.tracer

                class _ClarificationNode(base_cls):  # type: ignore[misc]
                    def __init__(self) -> None:
                        super().__init__(
                            llm_executor=llm_executor,
                            prompt_resolver=prompt_resolver,
                            tracer=tracer,
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

                class _ResponseComposer(base_cls):  # type: ignore[misc]
                    def __init__(self) -> None:
                        super().__init__(
                            llm_executor=llm_executor,
                            prompt_resolver=prompt_resolver,
                            tracer=tracer,
                        )

                return _ResponseComposer
            if node_type == UserContextEnrichmentNode.node_type:
                base_cls = node_cls or UserContextEnrichmentNode
                tracer = self.tracer

                class _UserContextEnrichmentNode(base_cls):  # type: ignore[misc]
                    def __init__(self) -> None:
                        super().__init__(tracer=tracer)

                return _UserContextEnrichmentNode
            if agent_handle:
                agent_handle.success(output={"node_cls": node_cls.__name__})
            return node_cls
