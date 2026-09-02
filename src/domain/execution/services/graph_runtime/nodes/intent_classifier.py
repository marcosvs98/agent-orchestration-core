from __future__ import annotations

from domain.execution.services.graph_runtime.nodes._llm_base import LLMNodeExecutor
from domain.execution.services.graph_runtime.types import NodeExecutionStatus
from domain.llm.schemas.llm import LLMTaskType
from domain.prompts.schemas.prompt import NodeType, PromptIntent


class IntentClassifier(LLMNodeExecutor):
    node_type = NodeType.IntentClassifier
    llm_task = LLMTaskType.INTENT_SELECTION
    prompt_intent = PromptIntent.INTENT_TOOL_SELECTION
    resolve_prompt_passes_node_type = True
    include_available_tools = False
    result_status = NodeExecutionStatus.SUCCESS
    write_next_state = True
    state_key_use_value = False
