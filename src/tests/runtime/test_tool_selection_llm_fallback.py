from domain.execution.services.graph_runtime.nodes._llm_base import LLMNodeExecutor
from domain.execution.services.graph_runtime.nodes.tool_selection_llm_fallback import (
    ToolSelectionLLMFallback,
)
from domain.execution.services.graph_runtime.types import NodeExecutionStatus
from domain.llm.schemas.llm import LLMTaskType
from domain.prompts.schemas.prompt import NodeType, PromptIntent


def test_tool_selection_llm_fallback_class_attributes():
    assert issubclass(ToolSelectionLLMFallback, LLMNodeExecutor)
    assert ToolSelectionLLMFallback.node_type == NodeType.ToolSelectionNode
    assert ToolSelectionLLMFallback.llm_task == LLMTaskType.TOOL_SELECTION
    assert (
        ToolSelectionLLMFallback.prompt_intent
        == PromptIntent.INTENT_TOOL_SELECTION
    )
    assert ToolSelectionLLMFallback.resolve_prompt_passes_node_type is True
    assert ToolSelectionLLMFallback.include_available_tools is True
    assert ToolSelectionLLMFallback.result_status == NodeExecutionStatus.SUCCESS
    assert ToolSelectionLLMFallback.write_next_state is True
    assert ToolSelectionLLMFallback.state_key_use_value is False
