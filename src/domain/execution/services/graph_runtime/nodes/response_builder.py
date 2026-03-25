from __future__ import annotations

from domain.execution.services.graph_runtime.nodes._llm_base import LLMNodeExecutor
from domain.execution.services.graph_runtime.types import NodeExecutionStatus
from domain.llm.schemas.llm import LLMTaskType
from domain.prompts.schemas.prompt import NodeType, PromptIntent


class ResponseBuilder(LLMNodeExecutor):
    node_type = NodeType.ResponseBuilder
    llm_task = LLMTaskType.RESPONSE_RENDER
    prompt_intent = PromptIntent.RESPONSE_RENDER
    resolve_prompt_passes_node_type = True
    include_available_tools = True
    result_status = NodeExecutionStatus.SUCCESS
    write_next_state = True
    state_key_use_value = False
