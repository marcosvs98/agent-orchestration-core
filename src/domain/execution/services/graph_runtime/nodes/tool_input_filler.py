from __future__ import annotations

from domain.execution.services.graph_runtime.nodes._llm_base import LLMNodeExecutor
from domain.execution.services.graph_runtime.types import NodeExecutionStatus
from domain.llm.schemas.llm import LLMTaskType
from domain.prompts.schemas.prompt import NodeType, PromptIntent


class ToolInputFiller(LLMNodeExecutor):
    node_type = NodeType.ToolInputFiller
    llm_task = LLMTaskType.SLOT_FILLING
    prompt_intent = PromptIntent.SLOT_FILLING
    resolve_prompt_passes_node_type = False
    include_available_tools = False
    result_status = NodeExecutionStatus.SUCCESS
    write_next_state = True
    state_key_use_value = True
