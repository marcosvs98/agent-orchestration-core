import pytest

from domain.execution.services.graph_runtime.nodes import (
    ClarificationNode,
    FallbackNode,
    ParamExtractionNode,
    ResponseComposer,
    ToolExecutionNode,
    ToolSelectionNode,
)
from domain.execution.services.graph_runtime.registry import NodeRegistry


def test_node_registry_resolves_valid_node_types():
    """Test that registry resolves node types to appropriate classes."""
    registry = NodeRegistry()

    intent_cls = registry.resolve("ToolSelectionNode")
    assert intent_cls is not None
    assert issubclass(intent_cls, ToolSelectionNode)

    tool_cls = registry.resolve("ToolExecutionNode")
    assert tool_cls is not None
    assert issubclass(tool_cls, ToolExecutionNode)

    clarification_cls = registry.resolve("ClarificationNode")
    assert clarification_cls is not None
    assert issubclass(clarification_cls, ClarificationNode)

    param_cls = registry.resolve("ParamExtractionNode")
    assert param_cls is not None
    assert issubclass(param_cls, ParamExtractionNode)

    assert registry.resolve("ResponseNode") == ResponseComposer
    assert registry.resolve("FallbackNode") == FallbackNode


def test_node_registry_returns_none_for_unknown_type():
    """Test that registry returns None for unknown node types."""
    registry = NodeRegistry()
    assert registry.resolve("UnknownNodeType") is None
    assert registry.resolve("") is None


def test_node_registry_injects_dependencies():
    """Test that registry injects dependencies into nodes that require them."""
    mock_orchestrator = object()
    mock_repository = object()

    registry = NodeRegistry(
        tool_orchestrator=mock_orchestrator,
        execution_repository=mock_repository,
    )

    tool_cls = registry.resolve("ToolExecutionNode")
    assert tool_cls is not None

    instance = tool_cls()
    assert instance.tool_orchestrator is mock_orchestrator
    assert instance.execution_repository is mock_repository
