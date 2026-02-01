from __future__ import annotations

from typing import Any, Dict, Type

from domain.execution.services.graph_runtime.nodes import (
    ClarificationNode,
    FallbackNode,
    IntentToolSelectionNode,
    ParamExtractionNode,
    ResponseNode,
    ToolExecutionNode,
)
from domain.execution.services.graph_runtime.types import NodeExecutor
from domain.llm.ports.llm_executor import LLMExecutorPort
from domain.tools.services.tool_orchestrator import ToolOrchestrator
from domain.execution.repositories.execution_repository import ExecutionRepository


class NodeRegistry:
    def __init__(
        self,
        llm_executor: LLMExecutorPort | None = None,
        prompt_resolver: Any | None = None,
        tool_orchestrator: ToolOrchestrator | None = None,
        execution_repository: ExecutionRepository | None = None,
    ) -> None:
        self.llm_executor = llm_executor
        self.prompt_resolver = prompt_resolver
        self.tool_orchestrator = tool_orchestrator
        self.execution_repository = execution_repository
        self._registry: Dict[str, Type[NodeExecutor]] = {
            IntentToolSelectionNode.node_type: IntentToolSelectionNode,
            ParamExtractionNode.node_type: ParamExtractionNode,
            ToolExecutionNode.node_type: ToolExecutionNode,
            ClarificationNode.node_type: ClarificationNode,
            ResponseNode.node_type: ResponseNode,
            FallbackNode.node_type: FallbackNode,
        }

    def resolve(
        self, node_type: str
    ) -> (
        type["_IntentNode"] | type["_ParamExtractionNode"] | type["NodeExecutor"] | None
    ):
        node_cls = self._registry.get(node_type)
        if node_type == IntentToolSelectionNode.node_type:
            base_cls = node_cls or IntentToolSelectionNode
            llm_executor = self.llm_executor
            prompt_resolver = self.prompt_resolver

            class _IntentNode(base_cls):  # type: ignore[misc]
                def __init__(self) -> None:
                    super().__init__(
                        llm_executor=llm_executor,
                        prompt_resolver=prompt_resolver,
                    )

            return _IntentNode
        if node_type == ParamExtractionNode.node_type:
            base_cls = node_cls or ParamExtractionNode
            llm_executor = self.llm_executor
            prompt_resolver = self.prompt_resolver

            class _ParamExtractionNode(base_cls):  # type: ignore[misc]
                def __init__(self) -> None:
                    super().__init__(
                        llm_executor=llm_executor,
                        prompt_resolver=prompt_resolver,
                    )

            return _ParamExtractionNode
        if node_type == ClarificationNode.node_type:
            base_cls = node_cls or ClarificationNode
            llm_executor = self.llm_executor
            prompt_resolver = self.prompt_resolver

            class _ClarificationNode(base_cls):  # type: ignore[misc]
                def __init__(self) -> None:
                    super().__init__(
                        llm_executor=llm_executor,
                        prompt_resolver=prompt_resolver,
                    )

            return _ClarificationNode
        if node_type == ToolExecutionNode.node_type:
            base_cls = node_cls or ToolExecutionNode
            tool_orchestrator = self.tool_orchestrator
            execution_repository = self.execution_repository

            class _ToolExecutionNode(base_cls):  # type: ignore[misc]
                def __init__(self) -> None:
                    super().__init__(
                        tool_orchestrator=tool_orchestrator,
                        execution_repository=execution_repository,
                    )

            return _ToolExecutionNode
        if node_type == ResponseNode.node_type:
            base_cls = node_cls or ResponseNode
            llm_executor = self.llm_executor
            prompt_resolver = self.prompt_resolver

            class _ResponseNode(base_cls):  # type: ignore[misc]
                def __init__(self) -> None:
                    super().__init__(
                        llm_executor=llm_executor,
                        prompt_resolver=prompt_resolver,
                    )

            return _ResponseNode
        return node_cls
