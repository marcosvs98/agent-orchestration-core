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


class NodeRegistry:
    def __init__(
        self,
        llm_executor: LLMExecutorPort | None = None,
        prompt_resolver: Any | None = None,
    ) -> None:
        self.llm_executor = llm_executor
        self.prompt_resolver = prompt_resolver
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
        return node_cls
