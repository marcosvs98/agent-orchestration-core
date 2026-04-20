"""Lightweight checks for graph runtime node classes (full execution paths covered elsewhere)."""

from domain.execution.services.graph_runtime.nodes.tool_resolver import ToolResolver
from domain.llm.schemas.llm import LLMTaskType
from domain.prompts.schemas.prompt import NodeType, PromptIntent


def test_tool_resolver_node_binding() -> None:
    assert ToolResolver.node_type == NodeType.ToolResolver
    assert ToolResolver.llm_task == LLMTaskType.TOOL_SELECTION
    assert ToolResolver.prompt_intent == PromptIntent.INTENT_TOOL_SELECTION
    assert ToolResolver.resolve_prompt_passes_node_type is True
    assert ToolResolver.include_available_tools is True
    assert ToolResolver.write_next_state is True
