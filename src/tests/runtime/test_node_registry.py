import pytest

from domain.execution.services.graph_runtime.nodes import (
    ClarificationNode,
    FallbackNode,
    IntentToolSelectionNode,
    ResponseNode,
    ToolExecutionNode,
)
from domain.execution.services.graph_runtime.registry import NodeRegistry


def test_node_registry_resolves_valid_node_types():
    registry = NodeRegistry()
    assert registry.resolve("IntentToolSelectionNode") == IntentToolSelectionNode
    assert registry.resolve("ToolExecutionNode") == ToolExecutionNode
    assert registry.resolve("ClarificationNode") == ClarificationNode
    assert registry.resolve("ResponseNode") == ResponseNode
    assert registry.resolve("FallbackNode") == FallbackNode


def test_node_registry_returns_none_for_unknown_type():
    registry = NodeRegistry()
    assert registry.resolve("UnknownNodeType") is None
    assert registry.resolve("") is None
