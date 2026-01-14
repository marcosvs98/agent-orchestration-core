from __future__ import annotations

from typing import Dict, Type

from domain.execution.services.graph_runtime.nodes import (
    ClarificationNode,
    FallbackNode,
    IntentToolSelectionNode,
    ResponseNode,
    ToolExecutionNode,
)
from domain.execution.services.graph_runtime.types import NodeExecutor
from domain.llm.ports.llm_executor import LLMExecutorPort


class NodeRegistry:
    def __init__(self, llm_executor: LLMExecutorPort | None = None) -> None:
        self.llm_executor = llm_executor
        self._registry: Dict[str, Type[NodeExecutor]] = {
            IntentToolSelectionNode.node_type: IntentToolSelectionNode,
            ToolExecutionNode.node_type: ToolExecutionNode,
            ClarificationNode.node_type: ClarificationNode,
            ResponseNode.node_type: ResponseNode,
            FallbackNode.node_type: FallbackNode,
        }

    def resolve(self, node_type: str) -> Type[NodeExecutor] | None:
        node_cls = self._registry.get(node_type)
        if node_type == IntentToolSelectionNode.node_type:
            base_cls = node_cls or IntentToolSelectionNode

            class _IntentNode(base_cls):  # type: ignore[misc]
                def __init__(self) -> None:
                    super().__init__(llm_executor=self.llm_executor)

            return _IntentNode
        return node_cls
