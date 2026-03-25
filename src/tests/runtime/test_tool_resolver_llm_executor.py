from pathlib import Path

from domain.execution.services.graph_runtime.nodes import ToolResolver
from domain.execution.services.graph_runtime.nodes._llm_base import LLMNodeExecutor
from domain.execution.services.graph_runtime.types import NodeExecutionStatus
from domain.llm.schemas.llm import LLMTaskType
from domain.prompts.schemas.prompt import NodeType, PromptIntent


def test_tool_resolver_is_llm_node_executor_with_tool_selection_task():
    assert issubclass(ToolResolver, LLMNodeExecutor)
    assert ToolResolver.node_type == NodeType.ToolResolver
    assert ToolResolver.llm_task == LLMTaskType.TOOL_SELECTION
    assert ToolResolver.prompt_intent == PromptIntent.INTENT_TOOL_SELECTION
    assert ToolResolver.resolve_prompt_passes_node_type is True
    assert ToolResolver.include_available_tools is True
    assert ToolResolver.result_status == NodeExecutionStatus.SUCCESS
    assert ToolResolver.write_next_state is True
    assert ToolResolver.state_key_use_value is False


def test_validate_node_tool_resolver_example_script_exists():
    repo_root = Path(__file__).resolve().parents[3]
    script = (
        repo_root
        / "resources"
        / "scripts"
        / "examples"
        / "nodes"
        / "validate_node_tool_resolver.py"
    )
    assert script.is_file()
